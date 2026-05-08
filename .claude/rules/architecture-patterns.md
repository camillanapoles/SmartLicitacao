---
paths:
  - "backend/**"
  - "frontend/**"
---

# Key Architecture Patterns — SmartLic

## Data Architecture (3 Layers)

**Layer 1: Periodic Ingestion (ETL → Supabase)**
- ARQ cron jobs: full daily (2am BRT), incremental 3x/day (8am/2pm/8pm BRT), purge daily (4am BRT)
- Table `pncp_raw_bids` (~1.5M rows @ 400d): open + historical bids — content_hash dedup, GIN full-text index (Portuguese), **400-day retention** (STORY-OBS-001 — required by observatório/SEO programmatic pages)
- Table `pncp_supplier_contracts` (~2M+ rows): historical contracts feeding SEO organic inbound (drives 10k+ programmatic ISR pages) — 3x/week full crawl (mon/wed/fri 06 UTC), incremental same days {12,18,0}h UTC
- Config: `backend/ingestion/` (config, crawler, transformer, loader, checkpoint, scheduler)
- Checkpoint tracking: `ingestion_checkpoints` + `ingestion_runs` tables for resumable crawls
- Feature flag: `DATALAKE_ENABLED` (default true)

**Layer 2: Search Pipeline (queries local DB, NOT live APIs)**
- `DATALAKE_QUERY_ENABLED=true` (default): `execute.py` → `query_datalake()` → `search_datalake` RPC
- PostgreSQL full-text search (tsquery Portuguese) with UF/date/modality/value/esfera filters, returns <100ms at p95
- Fallback: if datalake returns 0 results, falls through to live multi-source API fetch
- Async-first (CRIT-072): POST /buscar → 202 in <2s, results via SSE + polling
- SSE chain: bodyTimeout(0) + heartbeat(15s) > Railway idle(60s) | SSE inactivity timeout(120s)

**Layer 3: Search Results Cache (passive, per-request)**
- L1: InMemoryCache (4h, hot/warm/cold priority)
- L2: Supabase `search_results_cache` (24h, persistent)
- SWR (per-request reactive): when a request touches a stale entry (6-24h), serve stale + trigger background revalidation in `cache/swr.py::trigger_background_revalidation` (max 3 concurrent, 180s timeout)
- **No proactive warming.** Cache warming jobs deprecated 2026-04-18 (STORY-CIG-BE-cache-warming-deprecate). DataLake p95 <100ms made pre-population pure waste.

**Legacy Fallback: Live API Fetch (only when datalake returns 0 or DATALAKE_QUERY_ENABLED=false)**
- `pncp_client.py` (PNCP), `portal_compras_client.py` (PCP v2), `compras_gov_client.py` (ComprasGov v3)
- Per-source circuit breakers, priority-based dedup (PNCP=1 > PCP=2), phased UF batching
- Timeout chain: ARQ Job(300s) > Pipeline(110s) > Consolidation(100s) > PerSource(80s) > PerUF(30s)

## LLM Classification
- Keywords match -> "keyword" source (>5% density)
- Low density -> "llm_standard" (2-5%), "llm_conservative" (1-2%)
- Zero match -> "llm_zero_match" (GPT-4.1-nano YES/NO)
- Fallback = PENDING_REVIEW on LLM failure when `LLM_FALLBACK_PENDING_ENABLED=true` (gray zone + zero-match); hard REJECT when disabled
- Classification SLA: precision >= 85%, recall >= 70% (benchmark-validated, 15 samples/sector). NOT zero FN/FP — impossible with ambiguous government text.
- Observability: `smartlic_filter_decisions_by_setor_total`, `smartlic_llm_fallback_rejects_total`, `smartlic_feedback_negative_total` Prometheus counters

## SSE Progress Tracking
- `search_id` links SSE stream to POST request
- Dual-connection: `GET /buscar-progress/{id}` (SSE) + `POST /buscar` (JSON)
- In-memory asyncio.Queue-based tracker
- Frontend graceful fallback: if SSE fails, uses time-based simulation

## ARQ Job Queue
- LLM summaries + Excel generation dispatched as background jobs
- Immediate response with fallback summary (`gerar_resumo_fallback()`)
- SSE events `llm_ready` / `excel_ready` update result in real-time
- Web + Worker separated via `PROCESS_TYPE` in `start.sh`
