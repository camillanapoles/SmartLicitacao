# Análise Técnica do Código — SmartLic

> Gerado pelo **Reversa Archaeologist** em 2026-04-27
> `doc_level=completo` · Fonte: `.reversa/context/modules.json`
> Escala de confiança: 🟢 CONFIRMADO · 🟡 INFERIDO · 🔴 LACUNA

---

## Módulo 1 — `search` 🟢

**Caminho:** `backend/search_pipeline.py`, `backend/pipeline/`, `backend/consolidation/`, `backend/search_context.py`, `backend/search_state_manager.py`, `backend/models/search_state.py`, `backend/routes/search/`, `frontend/app/buscar/`

**Propósito:** Pipeline orquestrador de 7 estágios (8 com `_time_budget_check`) que executa busca de licitações com cache-first, async dispatch, máquina de estados explícita e métricas Prometheus.

### Arquivos primários

| Arquivo | LOC | Papel |
|---------|-----|-------|
| `search_pipeline.py` | 147 | Thin orchestrator — `SearchPipeline.run()` percorre `_STAGE_TABLE` |
| `search_state_manager.py` | 544 | `SearchStateMachine` + persistência fire-and-forget |
| `search_context.py` | 137 | Dataclass `SearchContext` (input/intermediário/output entre estágios) |
| `models/search_state.py` | (~80+) | Enum `SearchState`, `VALID_TRANSITIONS`, `TERMINAL_STATES`, `STAGE_TO_STATE` |
| `pipeline/stages/validate.py` | 204 | Stage 1 — quota/rate limit/admin |
| `pipeline/stages/prepare.py` | 157 | Stage 2 — sector resolution + keywords |
| `pipeline/stages/execute.py` | 1.240 | Stage 3 — multi-source fetch (datalake → live fallback) |
| `pipeline/stages/filter_stage.py` | 418 | Stage 4 — keyword/density filter |
| `pipeline/stages/enrich.py` | 117 | Stage 5 — viability scoring |
| `pipeline/stages/post_filter_llm.py` | 129 | Pós-filtro LLM zero-match |
| `pipeline/stages/generate.py` | 580 | Stage 6 — LLM summary + Excel |
| `pipeline/stages/persist.py` | 162 | Stage 7 — DB write |
| `pipeline/budget.py` | 93 | Time budget enforcement |
| `pipeline/cache_manager.py` | 358 | L1/L2 cache + SWR |
| `consolidation/dedup.py` | 566 | `DeduplicationEngine` (5 layers) |
| `consolidation/source_merger.py` | 559 | Merge multi-source records |
| `routes/search/__init__.py` | (~?) | POST `/buscar`, com router agregador |
| `routes/search/sse.py` | (~?) | GET `/buscar-progress/{id}` SSE |
| `routes/search/state.py` | (~?) | Background results, async search |
| `routes/search/status.py` | (~?) | `/search/{id}/{status,timeline,results}` |
| `routes/search/retry.py` | (~?) | `/search/{id}/{retry,cancel}` |

### Funções-chave

| Função | Arquivo | Confiança |
|--------|---------|-----------|
| `SearchPipeline.run(ctx) → BuscaResponse` | `search_pipeline.py:68` | 🟢 |
| `SearchPipeline._run_stages(ctx, root_span)` | `search_pipeline.py:85` | 🟢 |
| `SearchPipeline._check_time_budget(ctx)` | `search_pipeline.py:131` | 🟢 — abort LLM se elapsed > 90s |
| `SearchStateMachine.transition_to(to_state, stage, details)` | `search_state_manager.py:70` | 🟢 — valida + log + DB fire-and-forget |
| `validate_transition(from, to)` | `models/search_state.py` | 🟢 — consulta `VALID_TRANSITIONS` |
| `DeduplicationEngine.run(records)` | `consolidation/dedup.py:76` | 🟢 — 5 layers em sequência |
| `stage_validate(pipeline, ctx)` | `pipeline/stages/validate.py:23` | 🟢 — quota/rate/admin |

### Algoritmos

1. **Máquina de estados determinística** (CRIT-003)
   - 11 estados (`CREATED`→`COMPLETED`/`FAILED`/`RATE_LIMITED`/`TIMED_OUT`)
   - Transições inválidas rejeitadas com log CRITICAL e retornam `False`
   - Cada transição persistida em `search_state_transitions` (append-only) + atualiza `search_sessions` (mutável) via `asyncio.create_task` (não-bloqueante)

2. **Time Budget Waterfall** (`pipeline/budget.py`, STORY-4.4)
   - Pipeline 100s > Consolidation 90s > PerSource 70s > PerUF 25s > httpx (10c+15r)
   - Invariante: assertado em `tests/test_timeout_invariants.py`
   - Métrica `smartlic_pipeline_budget_exceeded_total{phase,source}` em cada timeout

3. **`_check_time_budget` (GTM-STAB-003 AC4)**
   - Se `elapsed > 90s` ou deadline expirado → `ctx.is_simplified = True` (skip LLM)
   - Emite evento SSE `llm_skipped, reason=timeout`

4. **Cache SWR per-request** (`pipeline/cache_manager.py`)
   - Fresh (0-6h) → serve direto
   - Stale (6-24h) → serve + dispara `trigger_background_revalidation` (max 3 concorrentes, 180s timeout)
   - Expired (>24h) → não serve
   - Cache populado on-demand (warming proativo deprecated 2026-04-18)

5. **Dedup Engine** (`consolidation/dedup.py`)
   - Layer 1: `source_id` exact (mesmo PNCP ID datalake + live)
   - Layer 2: `dedup_key` exact (mesmo edital cross-source — wins por priority)
   - Layer 3: Fuzzy Jaccard (mesmo conteúdo, edital numbers diferentes) — toggled `DEDUP_FUZZY_ENABLED`
   - Layer 4: Process-number (sequenciais do mesmo CNPJ-órgão) — regex `r"-(\d{4,6})/(\d{4})$"`
   - Layer 5: Title-prefix (cross-org duplicates)
   - Merge-enrichment: campos `valor_estimado`, `modalidade`, `orgao`, `objeto` do duplicado se faltarem no winner

6. **Stopwords PT-BR** (frozen set em `dedup.py:36`) — 27 termos para Jaccard

### Estruturas de dados

`SearchContext` (dataclass, `search_context.py`) — 7 seções:

| Seção | Campos principais |
|-------|------------------|
| Input | `request: BuscaRequest`, `user: dict`, `start_time`, `tracker: ProgressTracker`, `quota_pre_consumed`, `deadline_ts` |
| Stage 1 outputs | `is_admin`, `is_master`, `quota_info: QuotaInfo` |
| Stage 2 outputs | `sector: Sector`, `active_keywords: set`, `custom_terms`, `min_match_floor_value`, `active_exclusions`, `active_context_required` |
| Stage 3 outputs | `licitacoes_raw`, `is_partial`, `data_sources`, `degradation_reason`, `failed_ufs`, `succeeded_ufs`, `is_truncated`, `truncated_ufs`, `cached`, `cached_at`, `cache_status` (`fresh`/`stale`), `cache_level` (`supabase`/`redis`/`local`), `from_cache`, `response_state` (`live`/`cached`/`degraded`/`empty_failure`), `sources_degraded`, `live_fetch_in_progress` |
| Stage 4 outputs | `licitacoes_filtradas`, `filter_stats`, `hidden_by_min_match`, `filter_relaxed`, `relaxation_level` (0/1/2/3), `is_simplified`, `zero_match_budget_exceeded`, `zero_match_classified/deferred/candidates`, `filter_summary`, `zero_match_job_id` |
| Stage 6 outputs | `resumo: ResumoLicitacoes`, `excel_base64`, `download_url`, `excel_available`, `upgrade_message`, `licitacao_items`, `llm_source` (`ai`/`fallback`/`processing`), `queue_mode`, `llm_status`, `excel_status`, `bid_analysis_status`, `user_profile` |
| Stage 7 outputs | `session_id`, `response: BuscaResponse` |

`SearchState` (Enum):
```
CREATED → VALIDATING → FETCHING → FILTERING → ENRICHING → GENERATING → PERSISTING → COMPLETED
                                            ↓ FAILED / TIMED_OUT / RATE_LIMITED (terminais)
```

### Constantes / Feature flags

| Flag/Const | Default | Origem |
|-----------|---------|--------|
| `_STAGE_TABLE` | 9 entradas | `search_pipeline.py:24` |
| `DATALAKE_QUERY_ENABLED` | `True` | `config.py` |
| `DATALAKE_ENABLED` | `True` | `config.py` |
| `LLM_ZERO_MATCH_ENABLED` | inferido `True` | `config.py` |
| `DEDUP_FUZZY_ENABLED` | inferido `True` | `config.py` |
| `DEDUP_FUZZY_THRESHOLD` | inferido (Jaccard floor) | `config.py` |
| `_MERGE_FIELDS` | `("valor_estimado","modalidade","orgao","objeto")` | `dedup.py:34` |
| Time budget abort | 90s elapsed | `search_pipeline.py:136` |

### Métricas Prometheus

- `smartlic_search_duration_seconds{sector,uf_count,cache_status}` (histogram)
- `smartlic_active_searches` (gauge)
- `smartlic_searches_total{sector,result_status,search_mode}` (counter — `result_status`: success/empty/partial)
- `smartlic_pipeline_budget_exceeded_total{phase,source}`
- `DEDUP_FIELDS_MERGED{field}`, `DEDUP_FUZZY_HITS`

### Tracing OpenTelemetry

- Root span: `search_pipeline` com atributos `search.id`, `search.sector`, `search.ufs`, `search.user_id`, `search.result_status`, `search.duration_ms`, `search.total_raw`, `search.total_filtered`
- Child spans: `pipeline.{validate,prepare,fetch,filter,enrich,post_filter_llm,generate,persist}`

### Endpoints HTTP

| Método | Path | Handler |
|--------|------|---------|
| POST | `/buscar` | `routes/search/__init__.py::buscar_licitacoes` (definido no `__init__` por compat de mock — STORY-3.1) |
| GET | `/buscar-progress/{search_id}` | `routes/search/sse.py` (SSE, asyncio.Queue tracker) |
| GET | `/v1/search/{search_id}/status` | `routes/search/status.py` |
| GET | `/v1/search/{search_id}/timeline` | `routes/search/status.py` |
| GET | `/v1/search/{search_id}/results` | `routes/search/status.py` |
| POST | `/v1/search/{search_id}/retry` | `routes/search/retry.py` |
| POST | `/v1/search/{search_id}/cancel` | `routes/search/retry.py` |

### Fluxo de erros

- `HTTPException 403/429/503` propagam de `stage_validate` (admin/quota/rate)
- Estado `FAILED` é alcançável de qualquer outro estado
- `TIMED_OUT` apenas a partir de `FETCHING`
- `RATE_LIMITED` apenas a partir de `VALIDATING`
- Estados terminais (COMPLETED/FAILED/RATE_LIMITED/TIMED_OUT) sem transições outgoing

### Frontend

`frontend/app/buscar/` — página principal de busca (~33 componentes em `app/buscar/components/`):
- `SearchForm`, `SearchResults`, `FilterPanel`, `UfProgressGrid`
- `EnhancedLoadingProgress` (consome SSE)
- `CacheBanner`, `DegradationBanner`, `PartialResultsPrompt`, `SourcesUnavailable`, `ErrorDetail`
- `LlmSourceBadge`, `ViabilityBadge`, `FeedbackButtons`, `ReliabilityBadge`

### Dependências de outros módulos

`auth`, `quota`, `cache`, `filter`, `llm-arbiter`, `viability`, `consolidation`, `clients`, `routes`, `schemas`, `metrics`, `telemetry`, `progress`, `excel`, `jobs`

### Complexidade

**Alta** — 7 estágios, máquina de estados de 11 nós, 5 layers de dedup, cache SWR com 3 níveis, time budget waterfall em 5 níveis, async + sync coexistindo, 71 route modules dependentes.

### Lacunas e riscos identificados

- 🟡 `routes/search/__init__.py` define `buscar_licitacoes` em vez do submódulo `post_handler` apenas por compat de `@patch("routes.search.X")` em testes — fricção arquitetural.
- 🟡 `_check_time_budget` usa `asyncio.get_event_loop().create_task(...)` — pattern frágil em event loop fechado (CRIT-072 refactors em andamento).
- 🟢 Backward-compat shims em `backend/search/{cache,context,pipeline,state_manager}.py` (2 LOC cada) — re-exports.

---

## Módulo 2 — `ingestion-datalake` 🟢

**Caminho:** `backend/ingestion/`, `backend/datalake_query.py`

**Propósito:** ETL Layer 1 — crawler periódico PNCP → Supabase `pncp_raw_bids` (~50K rows abertos + retenção 400d) + `supplier_contracts` (~2M+ rows históricos para SEO orgânico). Camada de query (`datalake_query.py`) substitui live API quando `DATALAKE_QUERY_ENABLED=true`.

### Arquivos primários

| Arquivo | LOC | Papel |
|---------|-----|-------|
| `ingestion/config.py` | 106 | Feature flags, schedule UTC, batch sizes, modalidades, UFs, retention |
| `ingestion/scheduler.py` | 414 | ARQ cron jobs (`ingestion_full_crawl_job`, incremental, purge, contracts) |
| `ingestion/crawler.py` | 692 | Orquestra crawl por UF/modalidade reusando `AsyncPNCPClient._fetch_page_async` |
| `ingestion/contracts_crawler.py` | 772 | Crawler dedicado de `supplier_contracts` (SEO) |
| `ingestion/loader.py` | 316 | `bulk_upsert` via RPC `upsert_pncp_raw_bids` + `purge_old_bids` |
| `ingestion/transformer.py` | 223 | `transform_pncp_item` + `compute_content_hash` (SHA-256 dedup) |
| `ingestion/checkpoint.py` | 285 | Persiste/lê `ingestion_checkpoints`, cria `ingestion_runs` |
| `ingestion/enricher.py` | 460 | Enriquecimento de campos derivados |
| `ingestion/metrics.py` | 174 | Counters Prometheus (`INGESTION_RECORDS_FETCHED/UPSERTED`, `INGESTION_UFS_PROCESSED/FAILED`, etc.) |
| `datalake_query.py` | 536 | `query_datalake()` via RPC `search_datalake` + cache TTL in-memory |

### Funções-chave

| Função | Arquivo | Confiança |
|--------|---------|-----------|
| `crawl_uf_modalidade(client, uf, modalidade, date_start, date_end, crawl_batch_id, max_pages)` | `crawler.py:62` | 🟢 |
| `crawl_full()` | `crawler.py` | 🟢 — chamado pelo job ARQ |
| `crawl_incremental()` | `crawler.py` | 🟢 |
| `transform_pncp_item(raw_item, source, crawl_batch_id) → dict` | `transformer.py:51` | 🟢 |
| `compute_content_hash(item) → str` | `transformer.py:30` | 🟢 — SHA-256 de `objeto+valor+situacao` |
| `bulk_upsert(records, batch_size=500) → dict[str,int]` | `loader.py:44` | 🟢 — `inserted/updated/unchanged` |
| `_apply_date_fallbacks(records)` | `loader.py:21` | 🟢 — STORY-2.12 AC4 |
| `purge_old_bids(retention_days)` | `loader.py` | 🟢 — chama RPC homônimo |
| `get_last_checkpoint(uf, modalidade, source)` | `checkpoint.py:25` | 🟢 |
| `save_checkpoint`, `mark_checkpoint_failed`, `create_ingestion_run`, `complete_ingestion_run` | `checkpoint.py` | 🟢 |
| `query_datalake(ufs, data_inicial, data_final, modalidades?, keywords?, custom_terms?, valor_min/max?, esferas?, modo_busca, limit=2000) → list[dict]` | `datalake_query.py:86` | 🟢 |
| `_cache_get`, `_cache_put`, `_cache_key` | `datalake_query.py:41-79` | 🟢 — TTL 1h, max 50 entradas |
| `ingestion_full_crawl_job(ctx)` | `scheduler.py:54` | 🟢 — ARQ cron 5 UTC daily |

### Algoritmos

1. **Schedule pg_cron + ARQ duplicados** (defesa em profundidade)
   - Full: 5 UTC daily (2am BRT) — ARQ
   - Incremental: 11/17/23 UTC (8am/2pm/8pm BRT) — ARQ
   - Purge: 7 UTC daily (4am BRT) — ARQ + pg_cron `purge-old-bids`
   - Timeouts ARQ: full 4h, incremental 1h, purge 10min

2. **Concurrency**
   - `INGESTION_CONCURRENT_UFS=5` (Semaphore)
   - `INGESTION_BATCH_SIZE_UFS=5` por batch
   - `INGESTION_BATCH_DELAY_S=2.0` entre batches
   - `INGESTION_MAX_PAGES=50` por (UF, modalidade)
   - `INGESTION_UPSERT_BATCH_SIZE=500` (limite Supabase 1MB)

3. **Content-hash dedup** (`transformer.py:30`)
   - `objeto.lower().strip() + "|" + valor + "|" + situacao.lower().strip()`
   - SHA-256 hex
   - RPC `upsert_pncp_raw_bids` retorna `inserted/updated/unchanged`

4. **Checkpoint resumable**
   - Tabela `ingestion_checkpoints` (uf, modalidade, source, status, last_date)
   - Incremental crawl: `get_last_checkpoint()` + 1d overlap (catch late-arriving)
   - Fallback: `today - INGESTION_INCREMENTAL_DAYS=3`
   - `mark_checkpoint_failed` em exceção; retry no próximo cron

5. **Date fallback defensivo (STORY-2.12 AC4)**
   - `data_publicacao` ou `data_abertura` NULL → `now() - 1d`
   - Pareado com COALESCE no DB (`20260414133000_search_datalake_coalesce_dates.sql`)

6. **Datalake query cache** (`datalake_query.py:24-79`)
   - TTL 1h, max 50 entradas
   - Eviction: oldest expiry first
   - Cache key date-independent para `modo_busca="abertas"` (RPC ignora datas)

7. **Multi-column FTS** (STORY-437)
   - `tsvector` weights A/B/C
   - `websearch_to_tsquery` para custom terms
   - Trigram fallback quando FTS retorna 0

8. **Hybrid semantic search (STORY-438)**
   - Feature flag `EMBEDDING_ENABLED`
   - `text-embedding-3-small` em batch de 100
   - pgvector embeddings em `pncp_raw_bids.objeto_embedding`
   - Embedding failures não bloqueiam upsert (graceful degradation)

9. **Notify failure (DEBT-04 AC4)**
   - Sentry `capture_message(level="error")` com tags `ingestion.job`
   - Slack webhook via `services/slack_notifier.notify_ingestion_failure`

### Estruturas de dados

`pncp_raw_bids` (linhas — schema inferido):
- `numero_controle_pncp` (PK), `objeto_compra`, `valor_total_estimado`, `situacao_compra`
- `orgao_*`, `unidade_*`, `uf`, `municipio`
- `modalidade_id`, `modalidade_nome`
- `data_publicacao`, `data_abertura`, `data_encerramento`
- `content_hash` (SHA-256), `crawl_batch_id`, `source` (`pncp`)
- `objeto_embedding` (pgvector, opt-in)
- `created_at`, `updated_at`

`ingestion_checkpoints`:
- `uf`, `modalidade_id`, `source`, `status` (`completed`/`failed`/`running`), `last_date`, `created_at`

`ingestion_runs`:
- `run_id` (UUID), `crawl_type` (`full`/`incremental`), `started_at`, `completed_at`, `ufs_processed`, `records_upserted`, `errors`, `final_status`

### Constantes / Feature flags

| Flag | Default | Propósito |
|------|---------|-----------|
| `DATALAKE_ENABLED` | `true` | Habilita ingestion |
| `DATALAKE_QUERY_ENABLED` | `true` | Pipeline lê do datalake |
| `INGESTION_FULL_CRAWL_HOUR_UTC` | `5` | 2am BRT |
| `INGESTION_INCREMENTAL_HOURS` | `[11,17,23]` | 8am/2pm/8pm BRT |
| `INGESTION_DATE_RANGE_DAYS` | `7` | DISK-IO-002 (era 10) |
| `INGESTION_INCREMENTAL_DAYS` | `3` | Fallback se sem checkpoint |
| `INGESTION_BATCH_SIZE_UFS` | `5` | UFs por batch |
| `INGESTION_BATCH_DELAY_S` | `2.0` | Entre batches |
| `INGESTION_MAX_PAGES` | `50` | PNCP max page (não tamanhoPagina) |
| `INGESTION_CONCURRENT_UFS` | `5` | Semaphore |
| `INGESTION_UPSERT_BATCH_SIZE` | `500` | Limite Supabase 1MB |
| `INGESTION_MODALIDADES` | `[4,5,6,7,8,12]` | Concorrência, Pregão Eletr/Pres, Direta, Inex, Credenciamento |
| `INGESTION_UFS` | 27 (todas BR + DF) | — |
| `INGESTION_RETENTION_DAYS` | `400` | STORY-OBS-001 (era 30) |
| `INGESTION_PURGE_GRACE_DAYS` | `400` | Não purga bids ainda abertos |
| `INGESTION_BACKFILL_DAYS` | `365` | API max |
| `INGESTION_BACKFILL_CHUNK_DAYS` | `7` | Para evitar 50-page cap |
| `EMBEDDING_ENABLED` | inferido `false` | STORY-438 pgvector |
| `_CACHE_TTL` (datalake_query) | `3600` | 1h |
| `_CACHE_MAX_ENTRIES` | `50` | LRU evict |
| `_EMBEDDING_BATCH_SIZE` | `100` | OpenAI batch |

### Métricas Prometheus

`INGESTION_RECORDS_FETCHED`, `INGESTION_RECORDS_UPSERTED`, `INGESTION_UFS_PROCESSED`, `INGESTION_UFS_FAILED`, `INGESTION_PAGES_FETCHED`, `INGESTION_RUN_DURATION`

### Dependências de outros módulos

`pncp_client` (`AsyncPNCPClient`), `supabase_client`, `services/slack_notifier`, `metrics`, `cache` (in-mem TTL local)

### RPCs Supabase consumidos

- `upsert_pncp_raw_bids(p_records jsonb)` → `(inserted int, updated int, unchanged int)`
- `purge_old_bids(p_retention_days int)` → count
- `search_datalake(...)` → list of bid rows

### Lacunas

- 🟡 `ingestion/enricher.py` (460 LOC) não inspecionado — provável transformação de campos derivados (cidade normalizada, esfera, etc.)
- 🟡 `contracts_crawler.py` paralelo dedicado — schedule e tabela `supplier_contracts` requer análise data-master
- 🔴 Schema completo de `pncp_raw_bids` (índices GIN, RLS, triggers) é responsabilidade do Data Master

---

## Módulo 3 — `filter-llm-viability` 🟢

**Caminho:** `backend/filter/`, `backend/llm_arbiter/`, `backend/relevance.py`, `backend/viability.py`, `backend/llm.py`, `backend/sectors.py`, `backend/sectors_data.yaml`

**Propósito:** Decisão de relevância de cada licitação. Pipeline de filtros (UF → valor → keywords/density → status/data → LLM zero-match) seguido de scoring de viabilidade ortogonal (4 fatores). LLM arbitrer (GPT-4.1-nano) classifica gray zone + zero-match.

### Arquivos primários

| Arquivo | LOC | Papel |
|---------|-----|-------|
| `filter/__init__.py` | 42 | Facade pattern (`from filter import X`) |
| `filter/pipeline.py` | 1.918 | `aplicar_todos_filtros` — orquestrador |
| `filter/keywords.py` | 1.116 | `match_keywords`, normalização, exclusões globais, exemptions por setor |
| `filter/density.py` | 165 | Co-occurrence + proximity (gray zone classification) |
| `filter/status.py` | 204 | Status inference + filtro `prazo aberto` |
| `filter/uf.py` | 196 | Filtro UF |
| `filter/value.py` | 113 | Filtro valor mínimo/máximo |
| `filter/stats.py` | 249 | Tracker de métricas filter (Prometheus) |
| `filter/utils.py` | 63 | Utilitários compartilhados |
| `llm_arbiter/__init__.py` | 118 | Facade re-export (TD-009) |
| `llm_arbiter/classification.py` | 648 | OpenAI client, cache LRU + Redis, `LLMClassification` Pydantic, `classify_contract_primary_match` |
| `llm_arbiter/prompt_builder.py` | 378 | `_build_*_prompt` para sector/term/zero-match/batch |
| `llm_arbiter/zero_match.py` | 289 | `_classify_zero_match_batch` (até 20 itens/call) + `classify_contract_recovery` |
| `llm_arbiter/async_runtime.py` | 217 | STORY-4.1: `gather_classifications`, semaphore, async client |
| `llm_arbiter/batch_api.py` | 276 | OpenAI Batch API (`submit_batch`, `poll_batch`) |
| `relevance.py` | 128 | `score_relevance`, `calculate_min_matches`, `should_include` |
| `viability.py` | 391 | `ViabilityAssessment` 0-100 com 4 fatores |
| `llm.py` | 638 | LLM helpers para resumo executivo |
| `sectors.py` | 273 | Loader de `sectors_data.yaml` |
| `sectors_data.yaml` | (~?) | **20 setores** (não 15 como afirma CLAUDE.md) |

### Funções-chave

| Função | Arquivo | Confiança |
|--------|---------|-----------|
| `aplicar_todos_filtros(licitacoes, request, ctx)` | `filter/pipeline.py` | 🟢 |
| `match_keywords(text, keywords)` | `filter/keywords.py` | 🟢 |
| `_strip_org_context(text)` | `filter/keywords.py` | 🟢 — remove ruído de nome de órgão |
| `score_relevance(matched, total, phrase_match) → 0..1` | `relevance.py:22` | 🟢 |
| `calculate_min_matches(total) → int` | `relevance.py:51` | 🟢 — `max(1, min(ceil(t/3), 3))` |
| `should_include(matched, total, has_phrase) → bool` | `relevance.py:80` | 🟢 — A: matched≥min, B: phrase override |
| `count_phrase_matches(matched_terms) → int` | `relevance.py:115` | 🟢 |
| `classify_contract_primary_match(item, sector, ...)` | `llm_arbiter/classification.py` | 🟢 |
| `_classify_zero_match_batch(items, setor_name, setor_id, termos, search_id)` | `llm_arbiter/zero_match.py:63` | 🟢 |
| `_parse_batch_response(raw, expected_count)` | `llm_arbiter/zero_match.py:36` | 🟢 — regex `^\d+[\.\):\s]*\s*(YES|NO|SIM|NAO|NÃO)$` |
| `gather_classifications(items, ...)` | `llm_arbiter/async_runtime.py` | 🟢 — bounded concurrency |
| `submit_batch / poll_batch / list_pending_batch_ids` | `llm_arbiter/batch_api.py` | 🟢 — OpenAI Batch API |
| `assess_viability(item, request, profile?) → ViabilityAssessment` | `viability.py` | 🟢 |
| `_score_modalidade(mod) → (int, label)` | `viability.py:102` | 🟢 |
| `_score_timeline(data_str) → (int, label)` | `viability.py:132` | 🟢 |
| `_score_value_fit(valor, range) → (int, label)` | `viability.py:157` | 🟢 |
| `_score_geography(uf_lic, ufs_busca) → (int, label)` | `viability.py:187` | 🟢 |
| `_porte_modality_bonus(porte, mod) → int` | `viability.py:215` | 🟢 — STORY-260 AC7 |
| `_arbiter_cache_set/get` | `classification.py:73-79` | 🟢 — LRU + Redis L2 |

### Algoritmos

1. **Pipeline de filtros (fail-fast)** — ordem fixa em `aplicar_todos_filtros`:
   1. UF check (mais rápido)
   2. Value range check
   3. Keyword matching (density scoring) → 4 caminhos:
      - `>5%` keyword density → source `keyword`
      - `2-5%` → `llm_standard` (gray zone, LLM clarifica)
      - `1-2%` → `llm_conservative` (gray zone)
      - `0%` → `llm_zero_match` (LLM YES/NO batch)
   4. Status / date validation
   5. Viability assessment (post-filter, ortogonal)

2. **Min-match floor** (STORY-178 AC2.2):
   - `min_matches = max(1, min(ceil(total_terms / 3), 3))`
   - Tabela: 1-3 termos→1, 4-6→2, 7+→3 (cap)
   - Override por phrase match exato (multi-word)
   - `score = min(1.0, matched/total + 0.15 * phrase_count)`

3. **LLM cache 2-tier** (HARDEN-009):
   - L1 in-memory `OrderedDict` LRU max 5000 (`LRU_MAX_SIZE` env)
   - L2 Redis prefixo `smartlic:arbiter:`
   - Key = MD5 do input (objeto + sector + prompt version)
   - Métricas: `ARBITER_CACHE_{HITS,MISSES,EVICTIONS,SIZE}`

4. **Batch zero-match (UX-402)**
   - Até 20 itens por LLM call
   - Resposta esperada: `1. YES\n2. NO\n3. SIM\n...`
   - Regex parser tolera variações `YES|NO|SIM|NAO|NÃO`
   - **AC5 zero-noise:** count mismatch → `None` → reject ALL (não classifica nenhum)

5. **Async LLM runtime (STORY-4.1)**
   - Semaphore bounded (`get_max_concurrent`)
   - `gather_classifications` paraleliza com cap
   - `run_bounded_in_thread` — wrap sync chamadas
   - Async client lazy initialization

6. **Negative examples por setor** (STORY-328 AC13)
   - `_SECTOR_NEGATIVE_EXAMPLES` — armadilhas por sector_id
   - Ex: `informatica` rejeita "Uniformes para Secretaria de Tecnologia"
   - 13+ setores com 2-4 exemplos cada

7. **Viability — 4 fatores ponderados (D-04)**
   - **Modalidade 30%** — Pregão Eletrônico=100, Presencial=80, Concorrência=70/60, Credenciamento=50, Dispensa=40
   - **Timeline 25%** — `>14d=100`, `7-14d=80`, `3-7d=60`, `1-3d=30`, encerrada=10
   - **Value Fit 25%** — dentro range setor=100, abaixo (≥50%)=60, abaixo (<50%)=20, acima (≤2x)=60, acima (>2x)=20, valor=0=50 neutro (CRIT-FLT-003 AC1)
   - **Geography 20%** — UF na busca=100, mesma macro-região=60, distante=30
   - Output level: alta>70, media 40-70, baixa<40
   - **Porte bonus** (STORY-260 AC7) — empresa pequena × Pregão Eletr. → +bonus

8. **Macro-regiões BR** (`viability.py:79`)
   - norte, nordeste, centro_oeste, sudeste, sul (mapping completo)
   - Reverse map UF → region pré-computado

9. **OpenAI Batch API** (STORY-4.1)
   - Submit jobs assíncronos para classificação massiva
   - Poll status periodicamente
   - Custo: ~50% comparado a synchronous
   - `list_pending_batch_ids` para retomar

### Estruturas de dados

`ViabilityFactors` (Pydantic):
- `modalidade: int 0-100`, `modalidade_label`
- `timeline: int 0-100`, `timeline_label`
- `value_fit: int 0-100`, `value_fit_label`
- `geography: int 0-100`, `geography_label`

`ViabilityAssessment` (Pydantic):
- `viability_score: int 0-100`
- `viability_level: Literal["alta","media","baixa"]`
- `factors: ViabilityFactors`

`LLMClassification` (Pydantic):
- Campos inferidos: `decision: bool`, `confidence: float`, `reasoning?: str`, `evidence?: str`, `source: Literal["keyword","llm_standard","llm_conservative","llm_zero_match"]`

`Sector` (de `sectors_data.yaml`):
- `name: str`
- `description: str`
- `max_contract_value: int` (ex: R$5M)
- `viability_value_range: tuple[float, float]` (ex: [50000, 2000000])
- `keywords: list[str]`
- `exclusions: list[str]?`
- `context_required_keywords: list[str]?`

**Setores (20):** vestuario, alimentos, informatica, mobiliario, papelaria, engenharia, software_desenvolvimento, software_licencas, servicos_prediais, produtos_limpeza, medicamentos, equipamentos_medicos, insumos_hospitalares, vigilancia, transporte_servicos, frota_veicular, manutencao_predial, engenharia_rodoviaria, materiais_eletricos, materiais_hidraulicos.
**🟡 Discrepância:** CLAUDE.md afirma 15, YAML tem 20.

### Constantes / Feature flags

| Const | Valor | Origem |
|-------|-------|--------|
| `LLM_MODEL` | `gpt-4.1-nano` | env `LLM_ARBITER_MODEL` |
| `LLM_MAX_TOKENS` | `1` | env `LLM_ARBITER_MAX_TOKENS` |
| `LLM_TEMPERATURE` | `0` | env `LLM_ARBITER_TEMPERATURE` |
| `LLM_ENABLED` | `true` | env `LLM_ARBITER_ENABLED` |
| `LLM_STRUCTURED_MAX_TOKENS` | `800` | env `LLM_STRUCTURED_MAX_TOKENS` |
| `LLM_TIMEOUT_S` | `5` | env `OPENAI_TIMEOUT_S` (5× p99) |
| `_PRICING_INPUT_PER_M` | `0.10` USD/M | gpt-4.1-nano |
| `_PRICING_OUTPUT_PER_M` | `0.40` USD/M | — |
| `_ARBITER_CACHE_MAX` | `5000` | env `LRU_MAX_SIZE` |
| `PHRASE_MATCH_BONUS` | `0.15` | `relevance.py:17` |
| `MIN_MATCH_DIVISOR` | `3` | `relevance.py:18` |
| `MIN_MATCH_CAP` | `3` | `relevance.py:19` |
| `LLM_ZERO_MATCH_ENABLED` | `true` | feature flag |
| `LLM_FALLBACK_PENDING_ENABLED` | `true` | gray zone fallback → PENDING_REVIEW |
| `LLM_ARBITER_ENABLED` | `true` | — |
| `VIABILITY_ASSESSMENT_ENABLED` | `true` | — |
| `SYNONYM_MATCHING_ENABLED` | `true` | — |
| `DEFAULT_MODALITY_SCORE` | `50` | viability default |
| `DEFAULT_VALUE_RANGE` | `(50_000, 5_000_000)` | viability fallback |
| `LLM_ZERO_MATCH_BATCH_TIMEOUT` | (env) | — |

### Métricas Prometheus

`smartlic_filter_decisions_by_setor_total{setor,decision,source}`
`smartlic_llm_fallback_rejects_total`
`smartlic_feedback_negative_total`
`LLM_CALLS{model,result}`, `LLM_DURATION{model}` (histograma)
`EVIDENCE_PREFIX_STRIPPED`
`ARBITER_CACHE_{SIZE,HITS,MISSES,EVICTIONS}`
`LLM_FALLBACK_REJECTS_TOTAL`

### SLA (CLAUDE.md)
- Precision ≥ 85%
- Recall ≥ 70%
- Benchmark: 15 samples/sector
- **Não é zero FN/FP** — impossível com texto governamental ambíguo

### Dependências de outros módulos

`config`, `metrics`, `sectors`, `redis_client` (cache L2), `openai`, `pydantic`

### Lacunas

- 🟡 LLM cache prefix Redis hardcoded `smartlic:arbiter:` — não toca pelo env (consciente)
- 🟡 Negative examples só cobrem 13/20 setores (`_SECTOR_NEGATIVE_EXAMPLES`)
- 🔴 `filter/pipeline.py` (1.918 LOC) é o maior arquivo do filter — provável foco de refactor futuro

---

## Módulo 4 — `cache` 🔴 **LEGADO/OBSOLETO**

> **Status confirmado pelo usuário (2026-04-27):** Cache de resultados de busca é legacy. Substituído por ingestion ETL periódico → query direto Supabase DataLake. Warming proativo deprecated 2026-04-18 (STORY-CIG-BE-cache-warming-deprecate). Código permanece no repo mas não deve ser estendido — qualquer modificação em hot path de busca deve passar por `ingestion-datalake` + DataLake query (Layer 1+2), não por este módulo.

**Caminho:** `backend/cache/`, `backend/redis_pool.py`, `backend/search_cache.py`

**Propósito original (legado):** Cache multi-nível para resultados de busca: L1 Supabase (24h persistente) → L2 Redis/InMemory (4h fresh) → L3 local file (24h emergência). SWR per-request com revalidação background gated por circuit breaker. Cascade read invertido (L2→L1→L3) para latência ótima.

**Por que foi obsoleto:** DataLake query latência <100ms p95 tornou pré-população overhead puro. Layer 3 search-results cache tornou-se redundante: dados já estão localmente em `pncp_raw_bids` + `supplier_contracts` populados via crawler periódico (full daily 5UTC + incremental 3x/dia). Pipeline de busca consulta `search_datalake` RPC diretamente.

**Componentes legados ainda referenciados em prod:**
- `redis_pool.py` ainda **ativo e necessário** — usado por SSE (Redis Streams cross-worker), feature flags caching, ARQ queue state, rate limiter token bucket. NÃO obsoleto. O legado é apenas o uso de cache como camada de search results.
- `cache/manager.py` + `cache/cascade.py` + `cache/swr.py` — search-results cache (legado).
- `cache/admin.py` — endpoints `/health/cache` ainda servidos mas valor diagnóstico baixo agora.

**Mantido como referência arqueológica abaixo, sem detalhamento adicional.**

---

## Módulo 5 — `billing-quota` 🟢

**Caminho:** `backend/quota/`, `backend/services/billing.py`, `backend/webhooks/stripe.py`, `backend/webhooks/handlers/`, `backend/routes/billing.py`, `backend/billing/` (legacy 8-LOC shims)

**Propósito:** Gestão de planos, quota mensal, trial 14 dias, integração Stripe (checkout + subscriptions + webhooks). 8 planos definidos hardcoded (`free_trial`, `smartlic_pro`, `founding_member`, `consultoria`, + 3 legados + `master`/`free`). Stripe lida com proration nativamente (sem cálculo manual).

### Arquivos primários

| Arquivo | LOC | Papel |
|---------|-----|-------|
| `quota/__init__.py` | 113 | Facade re-export (TD-007: ex-`quota.py` 1660 LOC split) |
| `quota/quota_core.py` | 376 | `PLAN_CAPABILITIES`, cache TTL 5min, `PlanCapabilities` TypedDict |
| `quota/quota_atomic.py` | 271 | `check_and_increment_quota_atomic`, race-free PostgreSQL `ON CONFLICT DO UPDATE` |
| `quota/plan_enforcement.py` | 537 | `check_quota`, `require_active_plan`, multi-layer fallback |
| `quota/plan_auth.py` | 178 | Auth dependency injection |
| `quota/session_tracker.py` | 335 | `register_search_session`, `save_search_session`, `update_search_session_status` |
| `services/billing.py` | 110 | `update_stripe_subscription_billing_period` (proration_behavior=create_prorations), `get_next_billing_date` |
| `webhooks/stripe.py` | 253 | Dispatcher router fino — sig validation + idempotency + asyncio timeout |
| `webhooks/handlers/checkout.py` | (~?) | `checkout.session.completed`, async_payment_succeeded/failed |
| `webhooks/handlers/subscription.py` | (~?) | `customer.subscription.{created,updated,deleted,trial_will_end}` |
| `webhooks/handlers/invoice.py` | (~?) | `invoice.payment_{succeeded,failed,action_required}` |
| `webhooks/handlers/founding.py` | (~?) | STORY-BIZ-001 founding member abandonment |
| `webhooks/handlers/_shared.py` | (~?) | `resolve_user_id` |
| `routes/billing.py` | 383 | Endpoints `GET /plans`, `POST /checkout`, `POST /billing-portal`, `GET /subscription/status` |
| `billing/__init__.py` | 8 | Shim |

### Funções-chave

| Função | Arquivo | Confiança |
|--------|---------|-----------|
| `check_quota(user_id) → QuotaInfo` | `plan_enforcement.py:92` | 🟢 — multi-layer fallback |
| `check_and_increment_quota_atomic(user_id, max_quota?)` | `quota_atomic.py` | 🟢 — race-free |
| `check_and_increment_org_quota_atomic(...)` | `quota_atomic.py` | 🟢 — STORY-322 multi-user org |
| `get_monthly_quota_used(user_id) → int` | `quota_atomic.py:34` | 🟢 — fail-open em DB error |
| `increment_monthly_quota(user_id, max_quota?) → int` | `quota_atomic.py:63` | 🟢 — atomic ON CONFLICT |
| `get_current_month_key() → str` | `quota_atomic.py:20` | 🟢 — `YYYY-MM` |
| `get_quota_reset_date() → datetime` | `quota_atomic.py:25` | 🟢 — 1º próximo mês UTC |
| `get_plan_from_profile(user_id, sb?) → str?` | `plan_enforcement.py:36` | 🟢 — safety net via `profiles.plan_type` |
| `get_user_org_plan(user_id)` | `quota_atomic.py` | 🟢 — STORY-322 |
| `get_plan_capabilities() → dict` | `quota_core.py` | 🟢 — cache TTL 5min |
| `_load_plan_capabilities_from_db()` | `quota_core.py` | 🟢 |
| `invalidate_plan_status_cache(user_id)` | `quota_core.py:59` | 🟢 — chamado por todos webhook handlers |
| `clear_plan_capabilities_cache()` | `quota_core.py` | 🟢 |
| `_cache_plan_status / _get_cached_plan_status` | `quota_core.py:34-56` | 🟢 — bounded LRU 1000 |
| `get_trial_phase(user_id) → TrialPhaseInfo?` | `plan_enforcement.py` | 🟢 |
| `register_search_session / save_search_session / update_search_session_status` | `session_tracker.py` | 🟢 |
| `update_stripe_subscription_billing_period(...)` | `services/billing.py:15` | 🟢 |
| `get_next_billing_date(user_id) → datetime?` | `services/billing.py:77` | 🟢 |
| `stripe_webhook(request)` (POST `/webhooks/stripe`) | `webhooks/stripe.py:82` | 🟢 |
| Handlers `_handle_*` em `webhooks/handlers/` | — | 🟢 |

### Algoritmos

1. **Quota check multi-layer fallback** (`check_quota`)
   - Nunca cai pra `free_trial` em erro DB ("fail to last known plan")
   - Camadas em ordem:
     1. `user_subscriptions` ativa (primária)
     2. `_get_cached_plan_status` (5min TTL, fallback Supabase CB open)
     3. `profiles.plan_type` (safety net — atualizado sincronamente em `_activate_plan` e por admin)
     4. `_UNKNOWN_PLAN_DEFAULTS`
   - `get_plan_from_profile` mapeia legacy values: `master→sala_guerra`, `premium→maquina`, `basic→consultor_agil`, `free→free_trial`

2. **Atomic quota increment** (race-free, Issue #189)
   - PostgreSQL `INSERT ... ON CONFLICT (user_id, month_year) DO UPDATE SET searches_count = monthly_quota.searches_count + 1`
   - Evita lost updates sob concorrência
   - Quota reset lazy: novo `month_year` retorna 0; rows antigos ignorados

3. **Stripe Webhook Idempotência (STORY-307 AC1)**
   - `INSERT ON CONFLICT DO NOTHING` em `stripe_webhook_events`
   - Se `claim_result.data` vazio → evento já existe
   - **Stuck recovery** (AC6/AC7): se `status='processing'` por >5min → log WARN + retomar
   - 3 estados finais: `completed`, `failed`, `timeout`

4. **Stripe Webhook Timeout** (SYS-024)
   - `asyncio.wait_for(_process_event(), timeout=30s)`
   - TimeoutError → marca event `status='timeout'` + retorna HTTP 504

5. **Stripe Signature Validation**
   - `stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)`
   - Falha → HTTP 400 (ValueError ou `SignatureVerificationError`)
   - Sem signature → HTTP 400

6. **Cache de plano 2-tier**
   - `_plan_status_cache`: `dict[user_id, (plan_id, monotonic_ts)]` — bounded 1000 entradas, TTL 5min, threading.Lock
   - `_plan_capabilities_cache`: snapshot do PLAN_CAPABILITIES carregado de DB (TTL 5min)
   - Webhook handlers chamam `invalidate_plan_status_cache(user_id)` + `clear_plan_capabilities_cache()` após plan_type update (HARDEN-008)

7. **Trial 14 dias (STORY-264/277/319)**
   - Sem cartão de crédito
   - Mesmas capabilities que `smartlic_pro` (full product)
   - Rate limit anti-abuse: `max_requests_per_min=2` (STORY-264 AC2)
   - `trial_will_end` webhook: Stripe dispara 3d antes (STORY-CONV-003a AC4) → enviar email

8. **Grace period (`SUBSCRIPTION_GRACE_DAYS=3`)**
   - MED-SEC-002: era 7d, reduzido pra 3d (abusable)
   - Após expiração da subscription, mantém capabilities por 3d antes de downgrade

9. **Founding Member (MAYDAY-A2)**
   - Mesmas capabilities que `smartlic_pro`
   - 50% off (R$197/mês vs R$397)
   - Abandonment tracking (STORY-BIZ-001) via `checkout.session.expired`

10. **Org Quota** (STORY-322)
    - `consultoria` plan = multi-user org
    - 5000 req/mês compartilhados (1000 × 5 members)
    - `check_and_increment_org_quota_atomic` atomic em `org_subscriptions`

### Estruturas de dados

`PlanCapabilities` (TypedDict — `quota_core.py:85`):
- `max_history_days: int`
- `allow_excel: bool`
- `allow_pipeline: bool`
- `max_requests_per_month: int`
- `max_requests_per_min: int`
- `max_summary_tokens: int`
- `priority: str` (PlanPriority value)

`PlanPriority` Enum: `low | normal | high | critical`

`QuotaInfo` (Pydantic — `quota_core.py`):
- 🟡 Schema inferido: `plan_id, plan_name, capabilities, used_this_month, remaining_this_month, reset_date, in_trial?, trial_phase?, can_search: bool, error_message?`

`TrialPhaseInfo` (Pydantic):
- 🟡 Schema inferido: `started_at, expires_at, days_remaining, phase: Literal["active","ending","expired"]`

### Tabelas DB referenciadas

| Tabela | Papel |
|--------|-------|
| `profiles` | `plan_type` (safety net), `is_admin`, `is_master`, `trial_expires_at`, `stripe_customer_id` |
| `user_subscriptions` | Subscription ativa (`is_active`, `stripe_subscription_id`, `expires_at`, `billing_period`, `created_at`) |
| `monthly_quota` | (`user_id`, `month_year`, `searches_count`) — atomic increment |
| `org_subscriptions` | STORY-322 multi-user |
| `stripe_webhook_events` | (`id` PK, `type`, `status`, `received_at`, `processed_at`, `payload`) — idempotency + audit |
| `plan_billing_periods` | source of truth pricing (sync de Stripe — STORY-277/360) |
| `plan_features` | features por plano |
| `partner_referrals` | STORY referrals (`_create_partner_referral_async`, `_mark_partner_referral_churned`) |

### Constantes / Feature flags

| Const | Valor |
|-------|-------|
| `PLAN_CAPABILITIES_CACHE_TTL` | 300s (5min) |
| `PLAN_STATUS_CACHE_TTL` | 300s (5min) |
| `PLAN_STATUS_CACHE_MAXSIZE` | 1000 (DEBT-323 bounded) |
| `SUBSCRIPTION_GRACE_DAYS` | 3 (MED-SEC-002, era 7) |
| `WEBHOOK_DB_TIMEOUT_S` | 30s (SYS-024) |
| `STRIPE_WEBHOOK_SECRET` | env (validação assinatura) |
| `STRIPE_SECRET_KEY` | env |

### Planos hardcoded — `PLAN_CAPABILITIES`

| Plano | Preço | history_days | excel | pipeline | req/mês | req/min | summary_tokens | priority |
|-------|-------|--------------|-------|----------|---------|---------|----------------|----------|
| `free_trial` | R$0 (14d) | 365 | ✅ | ✅ | 1.000 | 2 | 10.000 | normal |
| `smartlic_pro` | R$397/mês | 1.825 (5y) | ✅ | ✅ | 1.000 | 60 | 10.000 | normal |
| `founding_member` | R$197/mês | 1.825 | ✅ | ✅ | 1.000 | 60 | 10.000 | normal |
| `consultoria` | R$997/mês (org) | 1.825 | ✅ | ✅ | 5.000 | 10 | 10.000 | high |
| `consultor_agil` (legacy) | R$297/mês | 30 | ❌ | ❌ | 50 | 10 | 200 | normal |
| `maquina` (legacy) | R$597/mês | 365 | ✅ | ✅ | 300 | 30 | 500 | high |
| `sala_guerra` (legacy) | R$1.497/mês | 1.825 | ✅ | ✅ | 1.000 | 60 | 10.000 | critical |
| `master` | — | 99999 | ✅ | ✅ | 99999 | 120 | 10.000 | high |
| `free` (legado prod) | — | 7 | ❌ | ❌ | 10 | 2 | 200 | low |

### Eventos Stripe tratados (12)

```
checkout.session.completed
checkout.session.async_payment_succeeded
checkout.session.async_payment_failed
checkout.session.expired (founding member)
customer.subscription.created
customer.subscription.updated
customer.subscription.deleted
customer.subscription.trial_will_end
invoice.payment_succeeded
invoice.payment_failed
invoice.payment_action_required
```
+ todos os outros logados como `Unhandled event type`

### Pricing — `PLAN_BILLING_PERIODS` (STORY-277/360)

Pro: R$397 mensal · R$357 semestral (10% off) · R$297 anual (25% off)
Consultoria: R$997 mensal · R$897 sem (10%) · R$797 anual (20%)

**Source of truth:** tabela `plan_billing_periods` (sincronizada de Stripe). NÃO hardcoded em `PLAN_PRICES` — esse é só fallback de mensagens de erro.

### Métricas Prometheus

🟡 Inferido: `BILLING_WEBHOOK_*`, `QUOTA_CHECKS_TOTAL{plan,result}`, `QUOTA_EXCEEDED_TOTAL`. Re-leitura específica em fase futura.

### Rotas HTTP (`routes/billing.py`)

| Método | Path | Papel |
|--------|------|-------|
| GET | `/plans` | Lista pública de planos |
| POST | `/checkout` | Cria Stripe Checkout Session |
| POST | `/billing-portal` | Gera link Stripe Customer Portal |
| GET | `/subscription/status` | Status atual da subscription |
| POST | `/webhooks/stripe` | Webhook Stripe (signature gated) |

### Dependências

`stripe`, `supabase_client`, `cache.redis_cache` (nota: cache imports legados — usado em handlers para invalidação), `quota`, `auth`, `services/email_service` (transactional emails)

### Lacunas

- 🟡 `billing/__init__.py` (8 LOC) e `billing/{quota,service}.py` (2 LOC cada) são shims legados — re-exports para tests antigos
- 🟡 Plan IDs em produção: 9 valores (`free_trial`, `smartlic_pro`, `founding_member`, `consultoria`, `consultor_agil`, `maquina`, `sala_guerra`, `master`, `free`) — mistura de planos atuais + legados + admin + safety
- 🔴 Schema completo de `QuotaInfo`/`TrialPhaseInfo` Pydantic não inspecionado neste passo

---

## Módulo 6 — `auth-oauth` 🟢

**Caminho:** `backend/auth.py`, `backend/authorization.py`, `backend/oauth.py`, `backend/routes/auth_*.py`, `frontend/middleware.ts`, `frontend/app/login/`, `frontend/app/signup/`, `frontend/app/auth/`

**Propósito:** Autenticação Supabase JWT (HS256→ES256 transition, JWKS dinâmico) com cache 2-tier (L1 60s + L2 Redis 5min). OAuth Google via Fernet-encrypted tokens (Sheets export). Authorization layer (admin/master roles, RLS bypass para admins). Frontend middleware Next.js com CSP enforcing + 8 rotas protegidas.

### Arquivos primários

| Arquivo | LOC | Papel |
|---------|-----|-------|
| `backend/auth.py` | 433 | JWT validation local (PyJWT + JWKS PyJWKClient), cache L1 LRU + L2 Redis, `require_auth`, `get_current_user` |
| `backend/authorization.py` | 180 | `check_user_roles`, `get_admin_ids`, `get_master_quota_info`, `ErrorCode` |
| `backend/oauth.py` | 474 | OAuth 2.0 Google (Sheets), Fernet AES-256, refresh, CSRF state |
| `backend/routes/auth_check.py` | 126 | Endpoint validação token |
| `backend/routes/auth_email.py` | 150 | Magic link / email auth |
| `backend/routes/auth_oauth.py` | 280 | `/google`, `/google/callback`, `DELETE /google` |
| `backend/routes/auth_signup.py` | 293 | Signup endpoint |
| `frontend/middleware.ts` | 361 | CSP enforcing + route guards via `@supabase/ssr` |

### Funções-chave

| Função | Arquivo | Confiança |
|--------|---------|-----------|
| `get_current_user(credentials)` | `auth.py:231` | 🟢 — async dependency |
| `require_auth(...)` | `auth.py` | 🟢 — wrapper que rejeita None |
| `_get_jwt_key_and_algorithms(token)` | `auth.py` | 🟢 — JWKS > PEM > HS256 |
| `_get_jwks_client()` | `auth.py:117` | 🟢 — lazy init |
| `reset_jwks_client()` | `auth.py:218` | 🟢 — para test/rotation |
| `_cache_store_memory(token_hash, user_data)` | `auth.py:62` | 🟢 — LRU evict + metrics |
| `_redis_cache_get / _redis_cache_set` | `auth.py:81-107` | 🟢 — fire-and-forget L2 |
| `check_user_roles(user_id) → (is_admin, is_master)` | `authorization.py:35` | 🟢 — CB-aware |
| `get_admin_ids() → set[str]` | `authorization.py:29` | 🟢 — env override |
| `get_master_quota_info(is_admin)` | `authorization.py` | 🟢 — bypass quota |
| OAuth: `get_authorization_url`, `handle_callback`, `_encrypt_token`, `_decrypt_token`, `_refresh_access_token` | `oauth.py` | 🟢 |
| Frontend `addSecurityHeaders(response)` | `middleware.ts:35` | 🟢 — CSP + 8 headers |

### Algoritmos

1. **JWT validation 3-strategy fallback** (`_get_jwt_key_and_algorithms`)
   - **Strategy 1 (preferred):** JWKS endpoint via `PyJWKClient` (Supabase ES256, rotated Feb 2026) — fetch dinâmico, cache 5min
   - **Strategy 2:** PEM public key via `SUPABASE_JWT_SECRET` (ES256, formato BEGIN PUBLIC KEY)
   - **Strategy 3:** HS256 symmetric secret legacy
   - Sem nenhum → HTTP 401 "Autenticação indisponível"

2. **Cache 2-tier auth (DEBT-014 SYS-010+SYS-018)**
   - L1: `OrderedDict` LRU max 1000, TTL 60s, key = `SHA256(full_token)` (STORY-210 AC3 — colisão <2^-128)
   - L2: Redis prefixo `smartlic:auth:`, TTL 300s (5min), shared entre Gunicorn workers
   - Fast path: L1 hit → return + `move_to_end` (LRU refresh)
   - L2 hit → promove a L1 + return
   - L2 miss → JWT decode local (sem chamar Supabase API)
   - Promote: bem-sucedido decode → `_cache_store_memory` + `_redis_cache_set` (fire-and-forget)
   - Métricas: `AUTH_CACHE_HITS{level="memory|redis"}`, `AUTH_CACHE_MISSES`, `AUTH_CACHE_EVICTIONS`, `AUTH_CACHE_SIZE`

3. **JWT decode com audience verification (STORY-210 AC7)**
   - `audience="authenticated"` (Supabase default — antes era `verify_aud=False`)
   - `algorithms` lista variável: `["ES256"]` para JWKS/PEM, `["HS256"]` para legacy
   - Erros tratados: `ExpiredSignatureError`, `InvalidTokenError` → ambos HTTP 401 com mensagens distintas

4. **Role check com Circuit Breaker (STORY-291)**
   - CB Supabase aberto → `(False, False)` imediato (sem retry, fail-fast)
   - 1 retry com `asyncio.sleep(0.3)` em outras exceções
   - Fallback: `is_admin` column ausente → SELECT só `plan_type`
   - Hierarquia: `is_admin → is_master automático` (admin implies master)
   - `plan_type == "master"` → `is_master=True` mesmo sem `is_admin`
   - `ADMIN_USER_IDS` env (comma-separated) → bypass adicional via `get_admin_ids()`

5. **OAuth Google Token Encryption (STORY-180)**
   - `Fernet` (AES-256 GCM) via `cryptography`
   - `ENCRYPTION_KEY` env (base64-encoded, 32 bytes)
   - Production check: missing key → `RuntimeError`
   - Dev fallback: `b"0"*32` (INSECURE)
   - Pad/trim para 32 bytes determinísticos
   - Tokens nunca logados em plaintext
   - Auto-refresh via `_refresh_access_token`
   - CSRF protection: `state` parameter random `secrets.token_urlsafe`
   - Storage: `google_oauth_tokens` table (encrypted at rest)

6. **Frontend Middleware Route Guard (`middleware.ts`)**
   - **Protected routes** (8): `/buscar, /historico, /conta, /admin, /dashboard, /pipeline, /mensagens, /planos/obrigado`
   - **Public routes:** `/login, /signup, /planos, /auth/callback`
   - **Cacheable content (Cloudflare CDN):** `/blog, /licitacoes, /glossario, /calculadora, /sobre, /cnpj, /features, /pricing`
   - `@supabase/ssr` `createServerClient` com `getAll/setAll` cookie pattern
   - Sem session em protected route → redirect `/login`
   - Em public route com session → redirect `/dashboard`

7. **CSP enforcing (STORY-311)**
   - **AC1:** Promoted from Report-Only para enforcing `Content-Security-Policy`
   - **SEO-FIX (DEBT-108):** static SHA-256 hash em vez de per-request nonce — nonce forçava `headers()` async → dynamic rendering → Cache-Control:private → CDN não cacheava → pior CWV/SEO
   - **`script-src`:** `'self' 'unsafe-inline' https://js.stripe.com https://static.cloudflareinsights.com https://cdnjs.cloudflare.com https://cdn.sentry.io https://www.clarity.ms https://www.googletagmanager.com`
   - **`'unsafe-inline'` aceito como risk** (industry consensus Feb 2026 vercel/next.js#89754: Next.js 16 RSC inject inline scripts dinâmicos por request)
   - **`'strict-dynamic'` removido** — quebrava `<script src>` de domínio allowlisted em /_next/static/chunks/*.js
   - **DEBT-116:** `style-src 'unsafe-inline'` aceito (Tailwind injeta inline)
   - `connect-src` whitelist: Supabase, Stripe, Sentry, Mixpanel, Railway, Clarity
   - `frame-src` só Stripe (checkout iframe)
   - `object-src 'none'`, `base-uri 'self'`
   - `report-uri /api/csp-report` + `report-to csp-endpoint`

8. **Outros security headers (STORY-300/311)**
   - `Cross-Origin-Opener-Policy: same-origin` (AC6)
   - **COEP skipped** (AC7) — `require-corp` quebra Stripe checkout iframe (sem CORP headers)
   - `X-DNS-Prefetch-Control: off` (AC8)
   - HSTS preload no edge Railway

### Estruturas de dados

`HTTPAuthorizationCredentials` (FastAPI):
- `scheme: str` (e.g. "Bearer")
- `credentials: str` (raw token)

JWT payload claims usados:
- `sub` (user_id)
- `email`
- `role` (default `authenticated`)
- `aud` (default `authenticated`)
- `exp` (expiration)
- `iat`
- demais claims passthrough

### Tabelas DB

| Tabela | Papel |
|--------|-------|
| `profiles` | `id` (=auth.users.id PK), `is_admin`, `is_master` (deprecated, derivado de plan_type), `plan_type`, `email`, `created_at` |
| `auth.users` | Supabase Auth managed (não modificado direto) |
| `google_oauth_tokens` | `user_id`, `encrypted_access_token`, `encrypted_refresh_token`, `expires_at`, `scope`, `created_at`, `updated_at` |

### Constantes / Feature flags

| Const | Valor |
|-------|-------|
| `CACHE_TTL` (auth L1) | 60s |
| `REDIS_CACHE_TTL` (auth L2) | 300s |
| `MAX_CACHE_ENTRIES` | 1000 |
| `_REDIS_KEY_PREFIX` | `smartlic:auth:` |
| `SUPABASE_URL` | env (req) |
| `SUPABASE_JWT_SECRET` | env (PEM ou HS256) |
| `SUPABASE_ANON_KEY` | env |
| `SUPABASE_SERVICE_ROLE_KEY` | env |
| `ADMIN_USER_IDS` | env (CSV de UUIDs lowercase) |
| `GOOGLE_OAUTH_CLIENT_ID` | env |
| `GOOGLE_OAUTH_CLIENT_SECRET` | env |
| `GOOGLE_OAUTH_REDIRECT_URI` | env (default localhost) |
| `ENCRYPTION_KEY` | env (base64, 32 bytes) — RuntimeError em prod se ausente |
| `GOOGLE_SHEETS_SCOPE` | `https://www.googleapis.com/auth/spreadsheets` |

### Métricas Prometheus

`AUTH_CACHE_HITS{level=memory|redis}`, `AUTH_CACHE_MISSES`, `AUTH_CACHE_EVICTIONS`, `AUTH_CACHE_SIZE`

### Endpoints HTTP

| Método | Path | Handler |
|--------|------|---------|
| GET | `/me` | `routes/user.py` |
| POST | `/auth/check` | `routes/auth_check.py` |
| POST | `/auth/signup` | `routes/auth_signup.py` |
| POST | `/auth/email/...` | `routes/auth_email.py` (magic link) |
| GET | `/google` | `routes/auth_oauth.py` (authorization URL) |
| GET | `/google/callback` | `routes/auth_oauth.py` |
| DELETE | `/google` | `routes/auth_oauth.py` (revoke) |

### Frontend rotas

| Rota | Tipo |
|------|------|
| `/login` | Public — `@supabase/ssr` redirect logged-in → `/dashboard` |
| `/signup` | Public |
| `/auth/callback` | OAuth callback handler |
| `/recuperar-senha` | Password reset request |
| `/redefinir-senha` | Password reset confirm |

### Dependências

`pyjwt`, `pyjwt[crypto]`, `cryptography.fernet`, `google-auth-oauthlib`, `httpx`, `redis`, `supabase`, `fastapi.security.HTTPBearer`, `@supabase/ssr` (frontend), `@supabase/supabase-js`

### Decisões arquiteturais notáveis

- 🟢 Local JWT validation em vez de Supabase API call (CRITICAL FIX 2026-02-11) — 95% redução latência, eliminou intermittent failures
- 🟢 ES256 JWKS dinâmico para suportar rotação Supabase Feb 2026 (STORY-227 Track 1)
- 🟢 SHA-256 hash via `hashlib` (não `hash()` Python — não-determinístico cross-process) — STORY-203 SYS-M02
- 🟢 CSP migrado de nonce para hash estático (SEO-FIX) — preservou CDN cacheability
- 🟡 `'unsafe-inline'` em `script-src` é "accepted risk" — sem upstream fix Next.js 16 RSC

### Subseção 6.M — MFA TOTP enroll/verify (refresh 2026-05-09 — DOC-COVERAGE-001)

> Adendo: extensão de Module 6 para fechar a lacuna "🔴 STORY-317 MFA TOTP recovery codes" da revisão 2026-04-27. Cobertura PR #677 (enroll/verify endpoints) + PR #700 (recovery codes hashed bcrypt + lockout protection).

**Caminho adicional:** `backend/routes/auth_mfa.py`, `backend/auth.py:_mfa_*`, migrations `20260228160000_add_mfa_recovery_codes.sql` + `20260428100400_consultoria_mfa_enforcement.sql`

**Endpoints (4):**

| Método | Rota | Função |
|--------|------|--------|
| `POST` | `/v1/auth/mfa/enroll` | gera secret TOTP + QR provisioning URI; user escaneia em Google Authenticator/Authy/1Password |
| `POST` | `/v1/auth/mfa/verify` | verifica token TOTP enviado pelo user para concluir enrollment; ativa MFA; gera 8 recovery codes (one-shot, exibidos uma única vez) |
| `POST` | `/v1/auth/mfa/login` | post-password 2FA challenge — verifica token TOTP ou recovery code; emite session cookie completo |
| `DELETE` | `/v1/auth/mfa` | desactiva MFA (require password re-confirm) — purga `mfa_recovery_codes` |

**Tabelas (já em §2 data-master):**
- `mfa_recovery_codes(id, user_id, code_hash bcrypt, used_at)` — recovery codes pre-hashed bcrypt cost=12; one-time use (UPDATE used_at após verify success)
- `mfa_recovery_attempts(id, user_id, attempted_at, success bool)` — rate-limit (>5 fails em 30min → lockout 1h)

**Algoritmos:**

1. **Enrollment** — `pyotp.random_base32()` gera secret 32-char; armazena em `profiles.mfa_secret` (Fernet-encrypted, defesa em profundidade); `pyotp.totp.TOTP(secret).provisioning_uri(...)` gera otpauth URI codificada em QR.
2. **Verify (TOTP)** — `pyotp.totp.TOTP(secret).verify(code, valid_window=1)` — `valid_window=1` permite ±30s drift (defesa contra clock skew, padrão RFC 6238).
3. **Recovery code verify** — itera `mfa_recovery_codes WHERE user_id` e tenta `bcrypt.checkpw(code_input, code_hash)`; primeiro match win; UPDATE `used_at = now()` (não-removido — auditoria).
4. **Lockout** — `mfa_recovery_attempts` audit + COUNT(*) com `WHERE attempted_at > now() - interval '30m' AND success = false`. >= 5 → 401 com `Retry-After: 3600s`.

**Enforcement Policy (PR #700 — Consultoria plan):**
- Migration `20260428100400_consultoria_mfa_enforcement.sql` adiciona check em `enforce_mfa_for_plan(plan_id)` SECDEF function
- `consultoria` plan-id é o único que força MFA enrollment para login (gate em `/auth/login` step 2)
- Outros planos: MFA é opt-in via `/v1/auth/mfa/enroll`
- Memory `feedback_secdef_search_path_trap` cumprida — function tem `SET search_path = public, pg_temp`

**Confiança:** 🟢 CONFIRMADO via migrations + routes shipped.

### Lacunas

- 🟡 `_decrypt_token` em `oauth.py` não inspecionado — provável Fernet decrypt + handle InvalidToken (token revogado, key rotacionada)
- 🟡 `routes/auth_email.py` (magic link / email auth) não detalhado — Supabase delegated
- 🟢 STORY-317 MFA TOTP recovery codes — RESOLVED 2026-05-09 (PRs #677, #700) — ver Subseção 6.M acima

---

### Arquivos primários

| Arquivo | LOC | Papel |
|---------|-----|-------|
| `cache/manager.py` | 444 | `save_to_cache` 3-level fallback + `get_from_cache` cascade |
| `cache/cascade.py` | 196 | `get_from_cache_cascade` — L2→L1→L3 read |
| `cache/swr.py` | 372 | Background revalidation, dedup lock Redis, budget |
| `cache/_ops.py` | 352 | `_process_cache_hit`, tracking, degradation, level promotion |
| `cache/admin.py` | 283 | Métricas, invalidate, inspect (rotas admin) |
| `cache/enums.py` | 198 | `CacheLevel`, `CacheStatus`, `CachePriority`, hash utilities |
| `cache/supabase.py` | 171 | I/O L1 Supabase (`_save_to_supabase`, `_get_from_supabase`) |
| `cache/redis.py` | 87 | I/O L2 Redis |
| `cache/local_file.py` | 157 | I/O L3 disk + HARDEN-018 size eviction |
| `cache/memory.py` | 8 | InMemory shim |
| `redis_pool.py` | 497 | Pool unificado + `InMemoryCache` fallback (LRU 10K) |
| `search_cache.py` | 116 | Legacy entrypoint (testing target) |

### Funções-chave

| Função | Arquivo | Confiança |
|--------|---------|-----------|
| `save_to_cache(user_id, params, results, sources, fetch_duration_ms?, coverage?)` | `manager.py:61` | 🟢 |
| `get_from_cache_cascade(user_id, params, allow_expired=False)` | `cascade.py:55` | 🟢 |
| `compute_search_hash(params) → str` | `enums.py:105` | 🟢 — SHA com normalização ISO 8601 |
| `compute_search_hash_without_dates(params)` | `enums.py` | 🟢 — STORY-306 AC8 fallback legacy |
| `classify_priority(access_count, last_accessed_at, is_saved_search) → CachePriority` | `enums.py:63` | 🟢 |
| `trigger_background_revalidation(user_id, params, request_data, search_id?)` | `swr.py:86` | 🟢 |
| `_is_revalidating(params_hash)` / `_mark_revalidating` / `_clear_revalidating` | `swr.py:30-83` | 🟢 — Redis SETEX nx=True |
| `record_cache_fetch_failure / is_cache_key_degraded` | `_ops.py` | 🟢 — backoff por chave |
| `_process_cache_hit(...)` / `_process_cache_hit_allow_expired(...)` | `_ops.py` | 🟢 |
| `get_cache_metrics / invalidate_cache_entry / invalidate_all_cache / inspect_cache_entry` | `admin.py` | 🟢 |
| `get_redis_pool() → AsyncRedis?` | `redis_pool.py` | 🟢 — singleton com fallback |
| `get_fallback_cache() → InMemoryCache` | `redis_pool.py` | 🟢 |
| `_check_cache_dir_size() → int` | `local_file.py:18` | 🟢 — eviction oldest-first |
| `_all_sources_down()` | `cascade.py:27` | 🟢 — CRIT-081 |

### Algoritmos

1. **Save 3-level fallback** (waterfall L1→L2→L3)
   - L1 Supabase tenta primeiro (skip se `user_id == WARMING_USER_ID`)
   - L2 Redis em fallback (`logger.warning`)
   - L3 local file em último (mesmo padrão fallback warn)
   - Cada camada increment `_track_cache_operation` com level + duration

2. **Read cascade L2→L1→L3** (invertido para latência)
   - L2 (Redis/InMemory) primeiro pois mais rápido
   - L1 (Supabase) se L2 miss — promove para L2 implicitamente
   - L3 (local) só se ambos miss
   - Legacy fallback: se `CACHE_LEGACY_KEY_FALLBACK=true` e hash atual miss → tenta `compute_search_hash_without_dates` (resultado marcado `cache_fallback=true` com `cache_date_range`)

3. **SWR Background Revalidation** (B-01)
   - `trigger_background_revalidation` chamado por pipeline quando `cache_status=stale`
   - Dedup via Redis `SETEX revalidating:{hash} 1 EX={ttl} NX` (atomic)
   - Budget: `MAX_CONCURRENT_REVALIDATIONS=3` (env), `REVALIDATION_COOLDOWN_S` configurável
   - Circuit breaker check antes de disparar (CRIT-081 — não revalida se todas sources degraded)

4. **Priority tiering (B-02)**
   - HOT: `recent_access (24h) AND access_count≥3` ou `is_saved_search AND recent_access`
   - WARM: `recent_access AND access_count≥1`
   - COLD: caso contrário
   - TTL Redis por priority: HOT=2h, WARM=6h, COLD=1h

5. **Cache Status (idade)**
   - FRESH: 0-4h (`CACHE_FRESH_HOURS=4`, alinhado com `REDIS_CACHE_TTL_SECONDS=14400`)
   - STALE: 4-24h (`CACHE_STALE_HOURS=24`)
   - EXPIRED: >24h (não serve a menos que `allow_expired=True`)

6. **Hash determinístico (STORY-306)**
   - Inclui: `setor_id, ufs (sorted), status, modalidades (sorted), modo_busca, date_from/to (ISO 8601 normalized), termos_busca, valor_minimo/maximo, esferas (sorted), municipios (sorted), exclusion_terms (sorted)`
   - `_normalize_date` aceita 4 formatos (`YYYY-MM-DD`, ISO+TZ, `DD/MM/YYYY`)
   - `compute_search_hash_without_dates` para fallback legacy

7. **Local file eviction (HARDEN-018)**
   - Max 200MB; quando excede, ordena por `mtime` ascendente e deleta até atingir target 100MB
   - Não bloqueia (best-effort)

8. **Redis Pool (STORY-217 + CRIT-026-ROOT)**
   - Singleton async `redis.Redis`
   - `POOL_MAX_CONNECTIONS=50` (era 20 — 2 Gunicorn workers + ARQ + SSE)
   - `socket_timeout=30s` (era 5s — redis-py issue 2807: `socket_timeout` aplicado ao parse inteiro, não per-read)
   - `socket_connect_timeout=10s` (era 5s)
   - Fallback `InMemoryCache` LRU 10.000 entradas
   - Tracking fallback: `_fallback_since` + warn periódico após 5min, repetir 60s

9. **Track + degradation per key**
   - `record_cache_fetch_failure(key)` incrementa contador + timestamp
   - `is_cache_key_degraded(key)` verifica backoff exponencial — chave problemática vai para "skip"
   - `calculate_backoff_minutes(failures)` exponencial

### Estruturas de dados

`CacheLevel` Enum: `supabase | redis | local | miss`
`CacheStatus` Enum: `fresh | stale | expired`
`CachePriority` Enum: `hot | warm | cold`

`InMemoryCache` (`redis_pool.py:62`):
- `_store: OrderedDict[str, tuple[value, expiry?]]`
- `_max_entries: int = 10_000`
- API: `get/set/setex/delete/exists/keys`
- LRU eviction (move_to_end + popitem(last=False))

### Tabelas DB referenciadas

- `search_results_cache` (Supabase L1):
  - PK `params_hash`, `user_id`, `params jsonb`, `results jsonb`, `sources jsonb`, `created_at`, `updated_at`, `access_count`, `last_accessed_at`, `is_saved_search?`, `coverage jsonb?`, `fetch_duration_ms?`
  - TTL 24h via pg_cron `cleanup-search-cache`

### Constantes / Feature flags

| Const | Valor |
|-------|-------|
| `CACHE_FRESH_HOURS` | 4 (STORY-306) |
| `CACHE_STALE_HOURS` | 24 |
| `LOCAL_CACHE_TTL_HOURS` | 24 |
| `LOCAL_CACHE_MAX_SIZE_MB` | 200 |
| `LOCAL_CACHE_TARGET_SIZE_MB` | 100 |
| `REDIS_CACHE_TTL_SECONDS` | 14.400 (4h) |
| `REDIS_TTL_BY_PRIORITY` | HOT=2h, WARM=6h, COLD=1h |
| `POOL_MAX_CONNECTIONS` | 50 |
| `POOL_SOCKET_TIMEOUT` | 30s |
| `POOL_SOCKET_CONNECT_TIMEOUT` | 10s |
| `INMEMORY_MAX_ENTRIES` | 10.000 |
| `_FALLBACK_WARNING_THRESHOLD_S` | 300 (5min) |
| `_FALLBACK_WARNING_INTERVAL_S` | 60 |
| `CACHE_PARTIAL_HIT_THRESHOLD` | 0.5 (env) |
| `MAX_CONCURRENT_REVALIDATIONS` | env (default 3, ver CLAUDE.md) |
| `REVALIDATION_COOLDOWN_S` | env |
| `CACHE_LEGACY_KEY_FALLBACK` | env |
| `WARMING_USER_ID` | env (skip L1 saves) |
| `LOCAL_CACHE_DIR` | platform-aware (`/tmp/smartlic_cache` ou `%TEMP%\smartlic_cache`) |

### Métricas Prometheus

`CACHE_HITS{level}`, `CACHE_MISSES{level}`, `_track_cache_operation` (custom counter), tempos p95/p99 por operação

### Dependências

`utils/error_reporting`, `metrics`, `redis`, `supabase_client`, `pncp_client.get_circuit_breaker` (cross-check), `config`

### Lacunas

- 🟢 Backward-compat shims (`cache/core.py`, `cache/memory.py`, `cache/redis_pool.py`) com 2-8 LOC — re-exports para tests legados
- 🟡 Cache warming (proativo) **deprecated 2026-04-18** (STORY-CIG-BE-cache-warming-deprecate). Cache populado on-demand. `WARMING_USER_ID` ainda referenciado para skip L1 — código morto residual?
- 🟡 `_get_revalidation_lock` lazy — `asyncio.Lock` criado primeira vez dentro do loop (precaução contra "different event loop" errors)

---

## Módulo 7 — `pipeline-kanban` 🟢

**Caminho:** `backend/routes/pipeline.py`, `backend/schemas/pipeline.py`, `frontend/app/pipeline/`, `frontend/hooks/usePipeline.ts`

**Propósito:** CRUD kanban de oportunidades. 5 stages (`descoberta → análise → preparando → enviada → resultado`). Optimistic locking (`version`). Trial limit 5 itens (`TRIAL_PAYWALL_MAX_PIPELINE`). Read-only quando trial expired (STORY-265 AC15).

### Arquivos primários

| Arquivo | LOC | Papel |
|---------|-----|-------|
| `backend/routes/pipeline.py` | 497 | 5 endpoints CRUD + alerts. Admin client (ISSUE-021 reverteu user-scoped). |
| `backend/schemas/pipeline.py` | 84 | `PipelineItemCreate/Update/Response/ListResponse/AlertsResponse`, `VALID_PIPELINE_STAGES` set, `PIPELINE_STAGE_LABELS` dict. |
| `frontend/app/pipeline/page.tsx` | 406 | Page Next.js client; Tour Shepherd; trial limit modal; mobile/desktop split. |
| `frontend/app/pipeline/PipelineKanban.tsx` | 222 | @dnd-kit DndContext + 5 PipelineColumn. Code-split via dynamic import (`ssr:false`). |
| `frontend/app/pipeline/PipelineColumn.tsx` | 74 | useDroppable por stage. |
| `frontend/app/pipeline/PipelineCard.tsx` | 181 | useDraggable card; deadline border-red <7d. |
| `frontend/app/pipeline/PipelineMobileTabs.tsx` | (~150) | Mobile fallback tabs em vez de drag. |
| `frontend/hooks/usePipeline.ts` | 234 | Fetch/update/remove com retry + optimistic update. |

### Endpoints (router `tags=["pipeline"]`)

| Método | Rota | Auth | Quota gate |
|--------|------|------|-----------|
| `POST /pipeline` | create | `require_auth` | `_check_pipeline_write_access` + `_check_pipeline_limit` |
| `GET /pipeline?stage&limit&offset` | list | `require_auth` | `_check_pipeline_read_access` (fail-open) |
| `PATCH /pipeline/{id}` | update stage/notes | `require_auth` | `_check_pipeline_write_access` + version check (409 se mismatch) |
| `DELETE /pipeline/{id}` | remove | `require_auth` | `_check_pipeline_write_access` |
| `GET /pipeline/alerts` | <7d deadlines | `require_auth` | `_check_pipeline_read_access` (fail-open) |

### Algoritmos

1. **Optimistic locking (STORY-307 AC9-12)**
   - `PATCH` com `version=N` → `WHERE id=$id AND user_id=$uid AND version=N` + `SET version=N+1`
   - 0 rows affected → check existence → 404 (não existe) ou 409 (version mismatch)
   - Backward compat: se `version` é `None`, update sem check

2. **Idempotent insert (ISSUE-021)**
   - `upsert(on_conflict='user_id,pncp_id', ignore_duplicates=True)`
   - Empty result → fetch existing row, return 200 com PipelineItemResponse
   - Evita 409 noise em retry de POST

3. **Trial limit (STORY-356/446)**
   - Trial users: 5 itens max (`TRIAL_PAYWALL_MAX_PIPELINE`)
   - `count("exact")` por user_id; ≥ limit → 403 `{error_code: "PIPELINE_LIMIT_EXCEEDED", limit, current}`
   - Master/admin bypass

4. **Trial expired read-only (STORY-265 AC2/AC3/AC15)**
   - Read access: trial expired permitido (incentivo conversão)
   - Write access: `require_active_plan` bloqueia trial expired
   - Frontend: `isTrialReadOnly` ⇒ `<ReadOnlyKanban>` (DndContext sem sensors)

5. **Alerts: deadline window**
   - `data_encerramento ≤ now + 7d AND data_encerramento NOT NULL AND stage NOT IN ('enviada','resultado')`
   - Order asc por `data_encerramento`

6. **Defense-in-depth**
   - Toda query inclui `.eq("user_id", user_id)` mesmo com admin client (ISSUE-021 fix)
   - RLS desativado de fato (admin client = service-role)

7. **Fail-open reads (ISSUE-038)**
   - `CircuitBreakerOpenError` → 200 OK com items=[] + header `X-Cache-Status: stale-due-to-cb-open`
   - Malformed rows skipped (warning log) em vez de 500
   - `_check_pipeline_read_access` exception → fail-open

### Estruturas de dados

`PipelineStage` Literal: `"descoberta" | "analise" | "preparando" | "enviada" | "resultado"`

`STAGES_ORDER` (frontend, fixed): `[descoberta, analise, preparando, enviada, resultado]`

`STAGE_CONFIG` (frontend, label/color/icon): `🔍 📋 📝 📤 🏁`

### Tabelas DB referenciadas

`pipeline_items`:
- `id uuid pk`, `user_id uuid fk profiles`, `pncp_id text`, `objeto text`, `orgao text?`, `uf char(2)?`, `valor_estimado numeric?`, `data_encerramento timestamptz?`, `link_pncp text?`, `stage text` (CHECK in VALID_STAGES), `notes text?`, `search_id text?` (DEBT-120), `version int default 1`, `created_at`, `updated_at`
- Unique constraint: `(user_id, pncp_id)`
- Migration: `025_create_pipeline_items.sql` + `20260227120002_concurrency_pipeline_version.sql` + `20260321130000_debt_db004_pipeline_search_id_comment.sql`

### Constantes / Feature flags

| Const | Valor |
|-------|-------|
| `VALID_STAGES` (backend) | set de 5 stages |
| `VALID_PIPELINE_STAGES` (schemas) | mesmo set |
| `TRIAL_PAYWALL_MAX_PIPELINE` | 5 (env) |
| `PIPELINE_LIMIT` (frontend) | 5 (hardcoded const, STORY-446) |
| `PIPELINE_TOUR_STORAGE_KEY` | `"onboarding_pipeline_tour_completed"` |

### Dependências

`auth.require_auth`, `quota.check_quota / require_active_plan`, `authorization.has_master_access`, `supabase_client.get_supabase / sb_execute`, `log_sanitizer.mask_user_id`, frontend `@dnd-kit/core` (lazy), `Shepherd.js` (Tour).

### Lacunas

- 🟡 SYS-023: GET /pipeline migrou parcialmente para user-scoped client; outros 4 endpoints permanecem admin client (RLS bypassed). Defense-in-depth via `.eq("user_id")` é a única proteção horizontal.
- 🔴 Capability `allow_pipeline` é checada no quota check — não há capability matrix documentada explicitamente em código (espalhada em `quota_core`).
- 🟡 `query.update({**payload, "version": sb.table().version + 1} if False else payload)` linha 357 — código morto `if False else` (cleanup pendente).

---
## Módulo 8 — `jobs+cron` 🟢

**Caminho:** `backend/job_queue.py`, `backend/cron_jobs.py` (façades), `backend/jobs/queue/`, `backend/jobs/cron/`, `backend/cron/`

**Propósito:** Background processing via ARQ (Redis-backed async job queue). Worker process separado do web (`PROCESS_TYPE=worker`). 7 functions ARQ + 19 cron loops (lifespan-driven) + 9 ARQ cron jobs (worker-driven).

### Arquivos primários

| Arquivo | LOC | Papel |
|---------|-----|-------|
| `job_queue.py` | 172 | Façade legacy: pool singleton, `enqueue_job`, re-exports de `jobs.queue.*`. State `_arq_pool` mora aqui (test compat). |
| `cron_jobs.py` | 124 | Façade legacy: re-exports de `jobs.cron.*` + `cron.cache`. State `_pncp_cron_status_lock`, `_pncp_recovery_epoch` mora aqui. |
| `jobs/queue/config.py` | 164 | `WorkerSettings` + lista `_worker_cron_jobs` (ARQ scheduler). 9 cron jobs ARQ. |
| `jobs/queue/jobs.py` | 437 | `llm_summary_job`, `excel_generation_job`, `bid_analysis_job`, `daily_digest_job`, `email_alerts_job`, `reclassify_pending_bids_job`, `classify_zero_match_job`. |
| `jobs/queue/search.py` | 158 | `search_job` (offload pipeline), `_persist_*_to_redis/supabase`. |
| `jobs/queue/result_store.py` | 181 | Cancel flags, concurrent slots, pending review, zero-match results em Redis. |
| `jobs/cron/scheduler.py` | 34 | `register_all_cron_tasks()` lista de loops disparados via lifespan startup. |
| `jobs/cron/canary.py` | 125 | PNCP health canary (`tamanhoPagina=51` probe). |
| `jobs/cron/billing.py` | 354 | 5 loops: reconciliation, pre-dunning, revenue share, plan reconciliation, stripe events purge. |
| `jobs/cron/notifications.py` | 287 | 5 loops: alerts, trial sequence, support SLA, daily volume, sector stats. |
| `jobs/cron/cron_monitor.py` | 198 | STORY-1.1: pg_cron health monitor (Sentry alert se >25h sem rodar). |
| `jobs/cron/pncp_canary.py` | 67 | STORY-4.5: breaking change canary (max_page_size, shape drift). |
| `jobs/cron/seo_snapshot.py` | 33 | Snapshot SEO programático. |
| `jobs/cron/indice_municipal.py` | 84 | Atualização índice municipal. |
| `jobs/cron/new_bids_notifier.py` | 161 | Notificação saved searches → user emails. |
| `jobs/cron/llm_batch_poll.py` | 75 | OpenAI Batch API polling. |
| `jobs/cron/session_cleanup.py` | 119 | Limpa search_sessions stale 24h, expired results 12h. |
| `jobs/cron/trial_risk_detection.py` | 137 | Trial churn risk score. |
| `cron/cache.py`, `cron/billing.py`, `cron/health.py`, etc. | (~?) | Backward-compat shims. |

### Algoritmos / Lifecycles

1. **ARQ Worker Pool (`get_arq_pool`)**
   - Singleton lazy. `RedisSettings` derivado de `REDIS_URL` (fallback rediss para SSL).
   - `conn_timeout=10`, `conn_retries=5`, `conn_retry_delay=2.0`, `max_connections=50`, `retry_on_timeout=True`, `retry_on_error=[TimeoutError,ConnectionError,OSError]`.
   - Reconnect: 3 tentativas com backoff `2^attempt`. Se falhar, retorna `None` (graceful degradation).
   - `pool.ping()` antes de retornar; se falhar, recria pool.

2. **Worker Alive Check (CRIT-033)**
   - `_check_worker_alive`: verifica `arq:queue:health-check` key existence
   - Cache 15s (`_WORKER_CHECK_INTERVAL`)
   - Pipeline usa `is_queue_available()` para decidir async dispatch vs inline mode
   - Se worker offline → pipeline executa LLM+Excel inline (degradação)

3. **Enqueue Job (`enqueue_job`)**
   - Captura trace_id/span_id e injeta em `kwargs._trace_id/_span_id` para distributed tracing
   - Retorna `Job` instance ou `None` (queue down)
   - Logs `Enqueued job: {function_name} (id={job.job_id})`

4. **Cancel Flags (STORY-281)**
   - Redis key `smartlic:search_cancel:{search_id}` TTL 600s
   - Worker checa periodicamente em `search_job` e aborta se set
   - `set_cancel_flag/check_cancel_flag/clear_cancel_flag`

5. **WorkerSettings ARQ**
   - `max_jobs=10` (concorrência por worker)
   - `job_timeout=300s` (5min)
   - `max_tries=3` (retry com `retry_delay=5s`)
   - `health_check_interval=30s`
   - 7 functions registered + ingestion functions condicional + cron_monitoring_job

6. **Cron Jobs ARQ (`_worker_cron_jobs`)**
   - `daily_digest_job` (DIGEST_HOUR_UTC, timeout 1800)
   - `email_alerts_job` (ALERTS_HOUR_UTC, timeout 1800)
   - `cron_monitoring_job` (hourly minute=0, timeout 300)
   - `ingestion_full_crawl_job` (hour=INGESTION_FULL_CRAWL_HOUR_UTC, timeout 14400)
   - `ingestion_incremental_job` (hours=INGESTION_INCREMENTAL_HOURS, timeout 3600)
   - `ingestion_purge_job` (hour=full+2, timeout 600)
   - `contracts_full_crawl_job` (weekday set, hour=full+1, timeout=`CONTRACTS_FULL_CRAWL_TIMEOUT`)
   - `contracts_incremental_job` (weekday set, hours={12,18,0})
   - `enrich_entities_job` (08:00 UTC, timeout 7200)
   - `enrich_municipios_job` (09:00 UTC, timeout 3600)

7. **Lifespan Cron Loops (não-ARQ)** — disparados em `register_all_cron_tasks()` no FastAPI startup:
   - `health_canary` (PNCP sentinel)
   - `cache_cleanup`
   - `session_cleanup`, `results_cleanup`
   - `reconciliation`, `pre_dunning`, `revenue_share`, `plan_reconciliation`, `stripe_events_purge`
   - `alerts`, `trial_sequence`, `support_sla`, `daily_volume`, `sector_stats`
   - `seo_snapshot`, `indice_municipal`, `new_bids_notifier`, `pncp_canary`, `llm_batch_poll`

8. **Worker Startup Hardening (CRIT-038/051)**
   - `_worker_on_startup` configura logging para stdout
   - Hardena Redis pool: `socket_timeout=30s`, `socket_connect_timeout=10s`, `socket_keepalive=True`

9. **Trace Context Propagation**
   - `enqueue_job` injeta `_trace_id`/`_span_id` em kwargs
   - Worker functions extraem e re-link span (OTel)

### Estruturas de dados

- `WorkerSettings` (ARQ class) — functions, cron_jobs, on_startup, max_jobs=10, job_timeout=300
- `_pncp_cron_status: dict` (`status, latency_ms, updated_at`) — canonical home em `cron_jobs.py`
- `_pncp_recovery_epoch: int` — bumped quando canary se recupera (resgata circuit breakers)

### Tabelas DB referenciadas

- `search_sessions` (cleanup stale 24h)
- `search_results` (cleanup expired 12h)
- `stripe_events` (purge >RETENTION_DAYS)
- `search_alerts`, `trial_email_log`, `messages`, `daily_volume`, `sector_stats`
- pg_cron monitorado: `purge-old-bids`, `cleanup-search-cache`, `cleanup-search-store`

### Constantes / Feature flags

| Const | Valor |
|-------|-------|
| `ARQ max_jobs` | 10 |
| `ARQ job_timeout` | 300s |
| `ARQ max_tries` | 3 |
| `ARQ health_check_interval` | 30s |
| `_WORKER_CHECK_INTERVAL` | 15s |
| `_CANCEL_TTL` | 600s |
| `_CONCURRENT_SEARCH_TTL` | 600s |
| `RECONCILIATION_LOCK_TTL`, `REVENUE_SHARE_LOCK_TTL`, `PLAN_RECONCILIATION_LOCK_TTL` | env |
| `STRIPE_EVENTS_RETENTION_DAYS` | env |
| `STRIPE_PURGE_INTERVAL_SECONDS` | env |
| `PRE_DUNNING_INTERVAL_SECONDS` | env |
| `TRIAL_SEQUENCE_INTERVAL_SECONDS` | env |
| `TRIAL_SEQUENCE_BATCH_SIZE` | env |
| `ALERTS_LOCK_KEY/TTL` | env |
| `SESSION_STALE_HOURS` | (24?) |
| `SESSION_OLD_DAYS` | env |
| `RESULTS_CLEANUP_INTERVAL_SECONDS` | env |
| `HEALTH_CANARY_INTERVAL_SECONDS` | env |
| `CLEANUP_INTERVAL_SECONDS` | env |
| `INGESTION_FULL_CRAWL_HOUR_UTC` | 5 (2am BRT default) |
| `INGESTION_INCREMENTAL_HOURS` | {11,17,23} |
| `CONTRACTS_CRAWL_WEEKDAYS` | mon,wed,fri (default) |
| `CONTRACTS_INGESTION_ENABLED` | true (default) |
| `DIGEST_ENABLED` / `DIGEST_HOUR_UTC` | env |
| `ALERTS_ENABLED` / `ALERTS_HOUR_UTC` | env |

### Métricas Prometheus

- `smartlic_pncp_canary_consecutive_failures`
- `smartlic_pncp_max_page_size_changed_total`
- `smartlic_pncp_canary_shape_drift_total`
- Reconciliation, dunning custom counters

### Dependências

`arq>=0.27`, `redis.asyncio`, `supabase_client`, `email_service`, `stripe`, `ingestion.scheduler`, `telemetry`, `metrics`

### Lacunas

- 🟡 Dois sistemas de cron paralelos: ARQ cron (worker-driven) + lifespan loops (web/worker startup-driven). Razão histórica — alguns loops precisam de Redis lock distribuído (`ALERTS_LOCK_KEY`).
- 🔴 Cron loops em web process: se WEB_CONCURRENCY>1, cada Gunicorn worker tenta startar todos os loops. Locks Redis previnem duplicação mas há overhead.
- 🟢 Cache warming/refresh ARQ jobs **deprecated 2026-04-18** (cache_jobs.py.template é placeholder).
- 🟡 `cron_monitor` checa pg_cron health mas não valida que ARQ cron está rodando (gap de auto-monitor).
- 🔴 `_arq_pool` global state não thread-safe — protegido por `_pool_lock` asyncio mas tests podem mutar diretamente (test compat workaround).

---
## Módulo 9 — `routes` 🟢

**Caminho:** `backend/routes/` (71 módulos), `backend/startup/routes.py` (registration), `backend/admin/`, `backend/webhooks/stripe.py`

**Propósito:** Camada HTTP. 65 APIRouters → 187 endpoints. Registração centralizada em `startup/routes.py::register_routes`. Prefixos: `/v1/*` (maioria), `/health/*` (root), `/webhooks/stripe` (root).

### Arquivos primários

| Arquivo | LOC | Endpoints | Tag |
|---------|-----|-----------|-----|
| `routes/search/` (subpkg) | (~?) | POST /buscar + 5 SSE/state | search |
| `routes/search_state.py` | (~?) | 8 endpoints `/search/{id}/{status,timeline,results,zero-match,regenerate-excel,retry,cancel}` | search |
| `routes/user.py` | 888 | 13 endpoints (`/me`, `/profile/*`, `/trial/*`) | user |
| `routes/billing.py` | (~?) | 5 endpoints (`/plans`, `/checkout`, `/billing-portal`, `/subscription/status`, `/billing/setup-intent`) | billing |
| `routes/pipeline.py` | 497 | 5 CRUD + alerts | pipeline |
| `routes/alerts.py` | (~?) | 7 endpoints CRUD + unsubscribe + preview + history | alerts |
| `routes/onboarding.py` | (~?) | `/first-analysis`, `/onboarding/tour-event` | onboarding |
| `routes/messages.py` | (~?) | 6 endpoints CRUD + unread-count | messages |
| `routes/analytics.py` | (~?) | 6 endpoints (summary, time series, dimensions, trial-value, new-opps, track-cta) | analytics |
| `routes/feedback.py` | (~?) | POST/DELETE feedback + admin patterns | feedback |
| `routes/auth_signup.py` | 293 | POST /auth/signup | auth-signup |
| `routes/auth_check.py` | 126 | check-email, check-phone | auth-check |
| `routes/auth_email.py` | 150 | validate-signup-email, resend-confirmation, status | auth-email |
| `routes/auth_oauth.py` | 280 | google + callback + DELETE | oauth |
| `routes/admin_*.py` | (~?) | trace, cron, llm-cost, feature-flags | admin |
| `routes/observatorio.py`, `routes/blog_stats.py`, `routes/calculadora.py`, `routes/comparador.py`, `routes/dados_publicos.py`, `routes/empresa_publica.py`, `routes/orgao_publico.py`, `routes/contratos_publicos.py`, `routes/municipios_publicos.py`, `routes/itens_publicos.py`, `routes/compliance_publicos.py`, `routes/indice_municipal.py`, `routes/alertas_publicos.py`, `routes/sectors_public.py`, `routes/stats_public.py`, `routes/daily_digest.py`, `routes/weekly_digest.py` | (~?) | SEO programmatic + observatório (público sem auth) | observatorio/blog/etc |
| `routes/sitemap_*.py` (5 arquivos) | (~?) | XML sitemap dinâmicos (cnpjs, orgaos, licitacoes, licitacoes_do_dia) | sitemap |
| `routes/health_core.py` | (~?) | `/health/live`, `/health/ready`, `/sources/health` (root, não-v1) | health-core |
| `routes/health.py` | (~?) | health, status (incidents/uptime), tasks, sources, cache | health |
| `routes/slo.py` | (~?) | `/v1/admin/slo`, `/v1/admin/slo/alerts` | admin-slo |
| `routes/organizations.py` | (~?) | 8 endpoints multi-tenant (orgs/me, members, invite, accept, dashboard, logo) | organizations |
| `routes/partners.py` | (~?) | dashboard + admin/partners CRUD | partners |
| `routes/referral.py` | (~?) | code, stats, redeem | referral |
| `routes/relatorio.py` | (~?) | POST /relatorio-2026-t1/request | relatorio |
| `routes/share.py` | (~?) | POST /share/analise + GET hash | share |
| `routes/trial_extension.py` | 75 | extend, extensions | trial |
| `routes/trial_emails.py` | 213 | unsubscribe, webhook resend, admin preview/test-send | trial-emails |
| `routes/conta.py` | (~?) | cancelar-trial info+ação | conta |
| `routes/founding.py` | (~?) | POST /founding/checkout | founding |
| `routes/lead_capture.py` | (~?) | POST /lead-capture | lead-capture |
| `routes/mfa.py` | (~?) | status, recovery-codes, verify-recovery, regenerate | MFA |
| `routes/notifications.py` | (~?) | new-bids-count GET/DELETE | notifications |
| `routes/feature_flags.py` | (~?) | admin GET/PATCH/POST reload + public | feature-flags |
| `routes/seo_admin.py` | (~?) | GET admin/seo-metrics | seo_admin |
| `routes/metrics_api.py` | (~?) | discard-rate, daily-volume, sse-fallback | metrics |
| `routes/plans.py` | (~?) | GET /api/plans | plans |
| `routes/export.py`, `routes/export_sheets.py` | (~?) | PDF + Google Sheets | export |
| `routes/subscriptions.py` | (~?) | update-billing-period, cancel, cancel-feedback | subscriptions |
| `routes/calculadora.py` | (~?) | calculadora pública | calculadora |
| `routes/comparador.py` | (~?) | comparador buscar, bids | comparador |
| `routes/bid_analysis.py` | (~?) | POST /bid-analysis/{bid_id} | bid-analysis |
| `routes/reports.py` | (~?) | POST /reports/diagnostico | reports |
| `routes/sessions.py` | (~?) | sessions list + download | sessions |
| `routes/emails.py` | (~?) | send-welcome + unsubscribe HTML | emails |
| `routes/admin_trace.py` | (~?) | search-trace + cb/reset + schema-contract-status | admin |
| `routes/admin_cron.py` | (~?) | trigger backfills + clear checkpoints | admin |
| `routes/admin_llm_cost.py` | (~?) | llm-cost dashboard | admin |
| `routes/features.py` | (~?) | GET /api/features/me | features |
| `startup/routes.py` | 138 | `register_routes(app)` — registra 64 routers em `/v1`, 4 self-prefixed, stripe webhook em root | — |

### Endpoints — Mapa por prefixo

| Prefixo | Routers | Endpoints (#) |
|---------|---------|---------------|
| `/v1` (auto via register_routes) | 60+ routers | ~150 |
| `/health/*`, `/status/*`, `/sources/health` (root) | health_core, health | 11 |
| `/v1/admin/*` (auto-prefixed) | admin, admin_trace, admin_cron, admin_llm_cost, slo, seo_admin, feature_flags, partners admin | ~25 |
| `/webhooks/stripe` (root, single registration DEBT-324) | stripe_webhook_router | 1 |
| `/auth/*` (router prefix) | auth_check, auth_email, auth_signup | 5 |
| `/api/*` (mix /api/auth, /api/messages, /api/export, /api/subscriptions, /api/plans, /api/features) | oauth, messages, export_sheets, subscriptions, plans, features | ~20 |

### Padrões

1. **Auth dependency injection** — quase todos endpoints usam `user: dict = Depends(require_auth)`.
2. **Pydantic response_model** — 80%+ rotas declaram `response_model=` (alimenta OpenAPI → STORY-2.1 codegen).
3. **Tags** consistente por router (alimenta agrupamento Swagger UI).
4. **Public routes** (sem auth): `routes/*_publicos.py`, `observatorio.py`, `blog_stats.py`, `sectors_public.py`, `stats_public.py`, `dados_publicos.py`, `alertas_publicos.py`, `comparador.py`, `lead_capture.py`, `calculadora.py`, sitemap_*, share GET, emails unsubscribe, trial_emails unsubscribe + webhook.
5. **Self-prefixed routers** (`/v1/admin`): admin_trace, admin_cron, admin_llm_cost, slo. Não recebem prefixo extra em `register_routes`.
6. **Idempotency**: webhooks usam `events_processed` table; mutations críticas usam optimistic locking ou unique constraints.

### Lacunas

- 🔴 71 arquivos em `routes/` mas só 60 registrados em `_v1_routers` — 11 órfãos? Investigar `_sitemap_cache_headers.py`, `nul` (artefato wsl?), `search_sse.py`, `search_status.py`, `search_state.py` (talvez incluídos via `routes/search/__init__.py`).
- 🟡 Inconsistência prefixos: alguns routers com `prefix="/v1/admin"` próprio + apêndice `/v1/` causaria duplicação — register_routes só prefixa quando router não tem self-prefix (não está garantido por código, só convenção).
- 🟡 187 endpoints, mas SDD do redator deve focar nos críticos (search, billing, pipeline, alerts, auth, webhooks, organizations, MFA).
- 🟢 `nul` arquivo (WSL/Windows reserved name) — provável corrupção; não importável.

---
## Módulo 10 — `schemas+contracts` 🟢

**Caminho:** `backend/schemas/` (12 submodules), `backend/contracts/schemas/` (JSON Schema), `frontend/app/api-types.generated.ts`, `frontend/app/types.ts`

**Propósito:** Pydantic v2 BaseModels para input/output validation + OpenAPI schema source. JSON Schema externo para contratos com PNCP API (canary). 88 classes registradas (1003 LOC só em search.py).

### Arquivos primários

| Arquivo | LOC | Conteúdo |
|---------|-----|----------|
| `schemas/__init__.py` | (~?) | Re-export `from schemas.X import *` para 12 submodules. Backward-compat: `from schemas import X` ainda funciona. |
| `schemas/common.py` | (~?) | Enums (`StatusLicitacao`, `EsferaGovernamental`, `ModalidadeContratacao`, `FeedbackCategory`, `FeedbackVerdict`, `PorteEmpresa`, `ExperienciaLicitacoes`, `ConversationStatus`, `ConversationCategory`), validators (`validate_uuid`, `validate_password`, `validate_plan_id`, `sanitize_search_query`), patterns (`UUID_V4_PATTERN`, `PLAN_ID_PATTERN`, `SAFE_SEARCH_PATTERN`), `ERROR_CODES`, `SearchErrorCode`. |
| `schemas/search.py` | 1003 | `BuscaRequest`, `BuscaResponse`, `LicitacaoItem`, `ResumoLicitacoes`, `ResumoEstrategico`, `Recomendacao`, `ExtractedProcurement`, `SearchQueuedResponse`, `SearchStatusResponse`, `FilterStats`, `DataSourceStatus`, `CoverageMetadata`, `SourceInfo`, `SetoresResponse`, `SearchStats` TypedDict. |
| `schemas/messages.py` | 98 | `CreateConversationRequest/Response`, `ConversationsListResponse`, `ConversationDetail`, `ConversationSummary`, `ReplyRequest/Status`, `MessageResponse`, `UnreadCountResponse`. |
| `schemas/user.py` | 363 | `SignupRequest/Response`, `UserProfileResponse`, `TrialStatusResponse`, `PerfilContexto/Response`, `ProfileCompletenessResponse`, `DeleteAccountResponse`, `ExitSurvey*`. |
| `schemas/health.py` | 79 | `HealthResponse`, `HealthDependencies`, `RedisMetrics`, `SourcesHealthResponse`, `RootResponse`. |
| `schemas/billing.py` | (~?) | `BillingPlansResponse`, `CheckoutResponse`, `SetupIntentResponse`. |
| `schemas/admin.py` | (~?) | `AdminUsersListResponse`, `AdminCreateUserResponse`, `AdminUpdateUserResponse`, `AdminAssignPlanResponse`, `AdminUpdateCreditsResponse`, `AdminResetPasswordResponse`, `AdminDeleteUserResponse`. |
| `schemas/pipeline.py` | 83 | `PipelineItemCreate/Update/Response/ListResponse/AlertsResponse`, `VALID_PIPELINE_STAGES`, `PIPELINE_STAGE_LABELS`. |
| `schemas/feedback.py` | 74 | `FeedbackRequest/Response/DeleteResponse/PatternsResponse`, `FeedbackPatternBreakdown`, `FPKeywordSuggestion`. |
| `schemas/export.py` | (~?) | `GoogleSheetsExport*`. |
| `schemas/share.py` | 43 | `ShareAnaliseRequest/Response`, `SharedAnalisePublic`. |
| `schemas/stats.py` | 151 | Stats schemas para SEO/blog (`SectorBlogStats`, `CidadeStats`, `PanoramaStats`, etc.). |
| `schemas/contract.py` | (~?) | `SchemaContractViolation` (RuntimeError) + helpers. |
| `contracts/schemas/pncp_search_response.schema.json` | 102 | JSON Schema draft 2020-12 — 16 campos required em `data[]` + 5 paginação. |

### Algoritmos / Patterns

1. **Re-export pattern (DEBT-302)**
   - `schemas/__init__.py` faz `from schemas.search import *` etc.
   - Backward-compat: imports legados `from schemas import BuscaRequest` continuam funcionando após decomposição
   - Submodules organizados por domínio (search, billing, admin, etc.)

2. **Validators centralizados (`schemas/common.py`)**
   - `validate_uuid(v)` — regex `UUID_V4_PATTERN`
   - `validate_password(v)` — bcrypt-compat min length, complexidade
   - `validate_plan_id(v)` — `PLAN_ID_PATTERN` (whitelist)
   - `sanitize_search_query(v)` — strip + `SAFE_SEARCH_PATTERN`
   - `ERROR_CODES` dict — códigos centralizados (CRIT-005 strict typing)
   - Pydantic `field_validator` + `model_validator` para validações cross-field (e.g., `data_inicial <= data_final`, `valor_minimo <= valor_maximo`)

3. **Enums**
   - `StatusLicitacao` (str): RECEBENDO_PROPOSTA, EM_HOMOLOGACAO, ENCERRADA, CANCELADA, etc.
   - `EsferaGovernamental` (str): FEDERAL, ESTADUAL, MUNICIPAL, DISTRITAL
   - `ModalidadeContratacao` (IntEnum): 1, 2, 3, 4, 5, 6, 7, 8, 12, ... (PNCP codes)
   - `FeedbackVerdict` (str): RELEVANT, IRRELEVANT, AMBIGUOUS
   - `PorteEmpresa` (str): MEI, ME, EPP, MEDIA, GRANDE
   - `ExperienciaLicitacoes` (str): NENHUMA, INICIANTE, EXPERIENTE

4. **JSON Schema canary contract (`pncp_search_response.schema.json`)**
   - Draft 2020-12
   - Validado em `pncp_canary.py` (STORY-4.5) — alerta Sentry `shape_drift` se PNCP retorna payload sem campos required
   - 16 fields em `data[]` itens (e.g., `cnpjOrgao`, `valorTotalEstimado`, `dataAberturaProposta`)
   - 5 fields paginação (`paginaAtual`, `temProximaPagina`, `totalPaginas`, `totalRegistros`)
   - `additionalProperties: true` — tolera campos novos PNCP sem quebrar

5. **Pydantic → TypeScript codegen (STORY-2.1)**
   - Source of truth: `frontend/app/api-types.generated.ts` (gerado via `openapi-typescript`)
   - CI gate: `.github/workflows/api-types-check.yml` extrai OpenAPI da FastAPI app, compara com committed
   - Alimentado por `response_model=` em todas rotas (80%+ coverage)
   - Re-export via `frontend/app/types.ts` mapeia para nomes UI-friendly (`BuscaResult`, `LicitacaoItem`, `Resumo`)

6. **`SchemaContractViolation` exception**
   - Lançada quando contrato JSON Schema é violado em runtime
   - Capturada por canary, convertida em Sentry event `shape_drift`

### Estruturas de dados (highlights)

- `BuscaRequest` (validação cross-field):
  - `ufs: list[UF]` (min_length=1)
  - `data_inicial`, `data_final` (YYYY-MM-DD, range ≤ 30d, não-futuro)
  - `setor_id`, `termos_busca` (sanitized), `modalidades`, `valor_minimo/maximo`, `esferas`, `municipios`, `exclusion_terms`
  - `mode: Literal['default', 'simplified']`, `force_refresh: bool`
- `LicitacaoItem`: 30+ campos (PNCP raw + enriched)
- `ResumoLicitacoes` (LLM output): `panorama: str`, `pontos_atencao: list[str]`, `recomendacoes: list[Recomendacao]`, `estrategia_alvo`, `setor_dominante`
- `BuscaResponse`: 25+ campos (search_id, licitacoes, resumo, excel_url, llm_status, cache_status, response_state, ...)

### Constantes / Patterns

| Pattern | Uso |
|---------|-----|
| `UUID_V4_PATTERN` | Auth, search_id, item_id |
| `PLAN_ID_PATTERN` | Whitelist plan_ids |
| `SAFE_SEARCH_PATTERN` | Strip caracteres SQL/XSS de termos |
| `VALID_PIPELINE_STAGES` | Set de 5 stages |
| `PIPELINE_STAGE_LABELS` | Display labels PT-BR |
| `ERROR_CODES` | Error codes centralizados |

### Dependências

`pydantic>=2`, `email-validator`, `jsonschema`, regex compiled patterns

### Lacunas

- 🟡 `schemas.py` (singular, não-pasta) **não existe** — é uma pasta `schemas/` que faz re-export. Imports `from schemas import X` resolvem via `__init__.py`. (DEBT-302 transition)
- 🔴 88 classes podem ter overlap não-documentado (ex: `LicitacaoItem` vs `ExtractedProcurement` vs `UnifiedProcurement`).
- 🟡 JSON Schema canary é a ÚNICA validação contratual com PNCP — payload PCP/ComprasGov não tem schema check.
- 🟢 `additionalProperties: true` no canary é intencional — tolera novos campos PNCP sem alarme.

---
## Módulo 11 — `messages+feedback` 🟢

**Caminho:** `backend/routes/messages.py`, `backend/routes/feedback.py`, `backend/feedback_analyzer.py`, `backend/schemas/messages.py`, `backend/schemas/feedback.py`

**Propósito:** Dois subsistemas distintos — (1) **Messages**: InMail support conversations (user ↔ admin) com threads. (2) **Feedback**: classificação loop de qualidade (user marca bid como correct/false_positive/false_negative) + análise de padrões (bi-gram extraction).

### Arquivos primários

| Arquivo | LOC | Papel |
|---------|-----|-------|
| `routes/messages.py` | 395 | 6 endpoints `/api/messages/*` (CRUD conversations + replies + status + unread) |
| `routes/feedback.py` | 208 | 3 endpoints (`POST /feedback`, `DELETE /feedback/{id}`, `GET /admin/feedback/patterns`) |
| `feedback_analyzer.py` | 173 | `analyze_feedback_patterns`, `_extract_fp_keywords`, `_suggest_exclusions`, `_extract_bigrams`, `_find_co_occurring_words` |
| `schemas/messages.py` | 98 | DTOs conversations |
| `schemas/feedback.py` | 74 | `FeedbackRequest/Response/PatternsResponse`, enums |

### Endpoints

**Messages (`/api/messages` prefix, tag `messages`):**

| Método | Rota | Notas |
|--------|------|-------|
| `POST /conversations` | create + first message | requires user. body: subject, message, category |
| `GET /conversations` | list user's threads | filter by status/category, pagination |
| `GET /conversations/{id}` | thread detail + messages | RLS: user owner OR admin |
| `POST /conversations/{id}/reply` | append message | sets status=`awaiting_user` ou `awaiting_support` |
| `PATCH /conversations/{id}/status` | mudar status (admin) | open/closed/awaiting_user/awaiting_support |
| `GET /unread-count` | unread por user | usa `last_read_at` |

**Feedback (no prefix, tag `feedback`):**

| Método | Rota | Auth |
|--------|------|------|
| `POST /feedback` | submit upsert | require_auth + rate limit `USER_FEEDBACK_RATE_LIMIT/h` |
| `DELETE /feedback/{id}` | own only (LGPD AC9) | require_auth + ownership check |
| `GET /admin/feedback/patterns?setor_id&days` | analysis | require_admin |

### Algoritmos

1. **Feedback Upsert (AC5)**
   - SELECT por `(user_id, search_id, bid_id)` — se existe, UPDATE, senão INSERT
   - `record` inclui setor_id, user_verdict, reason (max 500 chars), category, bid_objeto (max 200), bid_valor, bid_uf, confidence_score, relevance_source

2. **Rate Limit (AC1)**
   - Count feedback do user nas últimas 1h
   - Se ≥ `USER_FEEDBACK_RATE_LIMIT` → 429

3. **Pattern Analysis (`analyze_feedback_patterns`)**
   - Breakdown: count por verdict (`correct`, `false_positive`, `false_negative`)
   - **Precision estimate** = correct / (correct + fp)
   - FP categories: Counter de `category` em fp_feedbacks
   - Top FP keywords: keyword aparece em >5 FPs e <2 corrects → suggest exclusion ou co-occurrence rule
   - Suggested exclusions: bi-grams >3 FPs e 0 corrects (top 10)

4. **Bi-gram extraction (`_extract_bigrams`)**
   - Regex `\b\w+\b` → words lowercase
   - Pares consecutivos `{words[i]} {words[i+1]}`
   - Counter

5. **Co-occurring words (`_find_co_occurring_words`)**
   - Para keyword K, em textos que contêm K, conta palavras vizinhas (não-stopword, len>2)
   - Top 5 mais frequentes
   - Stopwords PT-BR: 25 termos (de, do, da, para, com, em, por, e, ...)

6. **FP Observability**
   - `FEEDBACK_NEGATIVE_TOTAL{setor}.inc()` Prometheus counter quando verdict ∈ {`false_positive`, `false_negative`}

7. **Feature flag (AC10)**
   - `_check_feedback_enabled` → 503 se `USER_FEEDBACK_ENABLED` flag off (runtime)

8. **Messages threading**
   - `conversations`: id, user_id, subject, status, category, last_read_at_user/admin, created_at, updated_at
   - `messages` (table): conversation_id, sender_role (user/admin), body, created_at
   - Status transitions: `open` → `awaiting_support`/`awaiting_user`/`closed`
   - Unread count: `messages WHERE conversation.user_id=$me AND created_at > last_read_at_user AND sender_role='admin'`

### Estruturas de dados

`FeedbackVerdict` Enum: `correct | false_positive | false_negative | ambiguous`
`FeedbackCategory` Enum: (lista de categorias FP — modalidade errada, valor fora da faixa, geografia, escopo, etc.)
`ConversationStatus` Enum: `open | closed | awaiting_user | awaiting_support`
`ConversationCategory` Enum: support category

### Tabelas DB referenciadas

- `classification_feedback`: id, user_id, search_id, bid_id, setor_id, user_verdict, reason, category, bid_objeto, bid_valor, bid_uf, confidence_score, relevance_source, created_at, updated_at
- `conversations`: id, user_id, subject, status, category, last_read_at_user, last_read_at_admin, created_at, updated_at
- `messages`: id, conversation_id, sender_role, body, created_at

### Constantes / Feature flags

| Const | Valor |
|-------|-------|
| `USER_FEEDBACK_RATE_LIMIT` | env (default ~10/h) |
| `USER_FEEDBACK_ENABLED` | feature flag |
| `MESSAGES_ENABLED` | env |
| FP keyword threshold | fp_count > 5 AND correct_count < 2 |
| Bigram exclusion threshold | fp ≥ 3 AND correct == 0 (top 10) |

### Lacunas

- 🔴 Messages não tem rate limit (spam vector). Só auth.
- 🟡 Análise de padrões puramente keyword/bigram (sem embeddings). Eficaz mas não captura sinônimos/contexto.
- 🟡 Stopwords PT-BR hardcoded em `_find_co_occurring_words` (deveria reusar `consolidation/dedup.py:36` set).
- 🟢 `precision_estimate` não conta false_negatives (intencional — fórmula clássica P = TP/(TP+FP)).

---
## Módulo 12 — `onboarding+analytics` 🟢

**Caminho:** `backend/routes/onboarding.py`, `backend/routes/analytics.py`, `frontend/app/onboarding/`, `backend/utils/cnae_mapping.py`

**Propósito:** **Onboarding** — wizard 3-step (CNAE → UFs+valor → confirmação) que mapeia CNAE→setor e dispara `first-analysis` automática (GTM-004, time-to-first-value <5min). **Analytics** — Personal Dashboard com 6 endpoints agregando search_sessions.

### Arquivos primários

| Arquivo | LOC | Papel |
|---------|-----|-------|
| `backend/routes/onboarding.py` | 194 | POST `/first-analysis` + `/onboarding/tour-event` (telemetry Shepherd tour) |
| `backend/routes/analytics.py` | 547 | 6 endpoints (summary, searches-over-time, top-dimensions, trial-value, new-opportunities, track-cta) |
| `backend/utils/cnae_mapping.py` | (~?) | `map_cnae_to_setor(cnae) -> setor_id`, `get_setor_name(setor_id)` |
| `frontend/app/onboarding/page.tsx` | (~300) | Wizard state machine + react-hook-form + Zod |
| `frontend/app/onboarding/components/OnboardingStep1.tsx` | (~?) | CNAE input + objetivo |
| `frontend/app/onboarding/components/OnboardingStep2.tsx` | (~?) | UFs multi-select + faixa de valor + porte/experiência |
| `frontend/app/onboarding/components/OnboardingStep3.tsx` | (~?) | Confirmação + first-analysis dispatch |
| `frontend/app/onboarding/components/OnboardingProgress.tsx` | (~?) | Progress bar 3 steps |
| `frontend/lib/schemas/forms.ts` | (~?) | `onboardingStep1Schema`, `onboardingStep2Schema` Zod |

### Endpoints onboarding

| Método | Rota | Notas |
|--------|------|-------|
| `POST /v1/first-analysis` | dispara busca automática | require_auth + require_active_plan (STORY-265 AC5) |
| `POST /v1/onboarding/tour-event` | telemetry tour Shepherd | 204 fire-and-forget |

### Endpoints analytics (`/v1/analytics`)

| Método | Rota | Response model | Aggregation source |
|--------|------|---------------|-------------------|
| `GET /summary` | `SummaryResponse` | total_searches, downloads, opportunities, value_discovered, hours_saved, avg_results, success_rate, member_since | `search_sessions` agg |
| `GET /searches-over-time?period=` | `SearchesOverTimeResponse` | time-series buckets | bucket por dia/semana |
| `GET /top-dimensions` | `TopDimensionsResponse` | top_ufs (DimensionItem[]), top_sectors | unnest `ufs` + count |
| `GET /trial-value` | `TrialValueResponse` | (ROI estimado, oportunidades descobertas) | trial-specific |
| `GET /new-opportunities` | `NewOpportunitiesResponse` | count, has_previous_search, last_search_at, days_since_last, label | DEBT-127 |
| `POST /track-cta` | 204 | track CTA click | inserção em events table |

### Algoritmos

1. **CNAE → Setor mapping (GTM-004 AC1)**
   - `map_cnae_to_setor(cnae)` → setor_id
   - Tabela hardcoded `utils/cnae_mapping.py` (~5 dígitos CNAE → 1 dos 20 setores)
   - Fallback: `setor_id="diversos"` se não match

2. **First Analysis Flow**
   - Generate `search_id = uuid.uuid4()`
   - Build `BuscaRequest` automaticamente:
     - `setor_id` from CNAE map
     - `ufs` from profile.ufs_atuacao (default ["SP"])
     - `data_inicial`/`data_final` last 10 days
     - `valor_minimo`/`valor_maximo` from profile (default 100k-500k)
     - `status=RECEBENDO_PROPOSTA`
   - Dispatch `SearchPipeline.run` em background task
   - Return `search_id` para frontend SSE conectar

3. **Analytics Aggregation (Summary)**
   - `total_searches = COUNT(search_sessions WHERE user_id=$me)`
   - `total_downloads = COUNT(WHERE excel_downloaded=true)`
   - `total_opportunities = SUM(results_count)`
   - `total_value_discovered = SUM(total_value)`
   - `estimated_hours_saved = total_searches * 2.5h` (constante manual research)
   - `avg_results_per_search = total_opps / total_searches`
   - `success_rate = COUNT(state=COMPLETED) / total_searches`
   - `member_since = profiles.created_at`

4. **Top Dimensions (UFs/sectors)**
   - SQL `unnest(ufs)` → group by → count + sum value → top 5
   - `top_sectors` similar com setor_id

5. **New Opportunities (DEBT-127)**
   - Get user's last successful search (`state=COMPLETED ORDER BY created_at DESC LIMIT 1`)
   - Re-execute como query DataLake desde `last_search_at`
   - Return count + days_since_last_search
   - **UX-431 AC2**: se mais recente está failed/pending, label indica problema

6. **Trial Value (ROI estimate)**
   - Calcula opportunities descobertas no trial * avg ticket
   - Compara contra plan price → shows ROI

7. **Tour Event Telemetry**
   - POST com `{tour_id, event, steps_seen}` → insere em `tour_events` table
   - `event ∈ {started, completed, skipped}`
   - Powered by Shepherd.js no frontend

### Estruturas de dados

`OnboardingData` (frontend):
```ts
{
  cnae: string,                            // CNAE 5 dígitos
  objetivo_principal: string,              // texto livre
  ufs_atuacao: UF[],                       // ["SP", "RJ", ...]
  faixa_valor_min: number,                 // R$ 100k default
  faixa_valor_max: number,                 // R$ 500k default
  porte_empresa: PorteEmpresa,             // ME/EPP/MEDIA/GRANDE
  experiencia_licitacoes: ExperienciaLicitacoes,
}
```

`PerfilContexto` (backend, STORY-260) — saved em `profiles.context_jsonb`:
- Mesmo shape + `setores_de_interesse`, `regioes_atuacao`, `tipos_de_servico`

### Tabelas DB referenciadas

- `search_sessions` (analytics agg source)
- `profiles.context_jsonb` (PerfilContexto)
- `tour_events` (Shepherd.js telemetry)
- `cta_tracking` (events de CTA click)

### Constantes / Feature flags

| Const | Valor |
|-------|-------|
| `ENABLE_NEW_PRICING` | env |
| Estimated hours per search | 2.5h (hardcoded em `get_analytics_summary`) |
| Default faixa valor | 100k - 500k |
| Default porte | EPP |
| Default experiencia | INICIANTE |

### Lacunas

- 🟡 `estimated_hours_saved = total_searches * 2.5` — constante mágica, não-rastreada para validação empírica.
- 🔴 CNAE mapping fixo em código, não-versionado em DB. Adições requerem deploy. Considerar migração para tabela `cnae_setor_map`.
- 🟡 `track-cta` insere em events table mas não há endpoint admin para query (precisa SQL direto).
- 🟢 `OnboardingProgress` 3-step + Shepherd tour overlay (STORY-313 AC9-15).

---
## Módulo 13 — `admin` 🟢

**Caminho:** `backend/admin.py`, `backend/routes/admin_*.py`, `backend/cache/admin.py`, `backend/schemas/admin.py`, `frontend/app/admin/`

**Propósito:** Operações privilegiadas. Two-tier auth: `is_admin` (full power) ou `is_master` (limited). User CRUD, plan assignment, credits adjustment, cache inspection/eviction, reconciliation trigger, support SLA, trial metrics, at-risk trials, filter stats, SEO admin, LLM cost, schema contracts, cron status.

### Arquivos primários

| Arquivo | LOC | Endpoints | Tag |
|---------|-----|-----------|-----|
| `backend/admin.py` | 1.132 | 17 endpoints `/v1/admin/*` (users CRUD + cache + reconciliation + SLA + trial metrics) + helpers `require_admin`, `_get_admin_ids`, `_is_admin_from_supabase`, `_sanitize_search_input` | admin |
| `backend/routes/admin_trace.py` | 194 | 3 endpoints `/v1/admin/{search-trace, cb/reset, schema-contract-status}` | admin |
| `backend/routes/admin_cron.py` | 94 | 4 endpoints `/v1/admin/{cron-status, trigger-contracts-backfill, trigger-bids-backfill, clear-contracts-checkpoints}` | admin |
| `backend/routes/admin_llm_cost.py` | 44 | 1 endpoint `/v1/admin/llm-cost` (dashboard cost por modelo/source) | admin |
| `backend/routes/seo_admin.py` | 59 | 1 endpoint `/v1/admin/seo-metrics` | seo_admin |
| `backend/routes/feature_flags.py` | (~?) | admin GET/PATCH/POST reload + public GET | admin/feature-flags |
| `backend/routes/slo.py` | (~?) | `/v1/admin/slo`, `/v1/admin/slo/alerts` | admin-slo |
| `backend/cache/admin.py` | (~?) | helpers para `/cache/metrics`, `/cache/{hash}` |
| `backend/schemas/admin.py` | (~?) | `AdminUsersListResponse`, `AdminCreateUserResponse`, `AdminUpdateUserResponse`, `AdminAssignPlanResponse`, `AdminUpdateCreditsResponse`, `AdminResetPasswordResponse`, `AdminDeleteUserResponse` |
| `frontend/app/admin/page.tsx` | (~?) | Admin home dashboard |
| `frontend/app/admin/cache/page.tsx` | (~?) | Cache inspector |
| `frontend/app/admin/feature-flags/page.tsx` | (~?) | Toggle flags |
| `frontend/app/admin/metrics/page.tsx` | (~?) | Prometheus metrics view |
| `frontend/app/admin/seo/page.tsx` | (~?) | SEO metrics dashboard |
| `frontend/app/admin/slo/page.tsx` | (~?) | SLO + alerts |
| `frontend/app/admin/partners/page.tsx` | (~?) | Partner management |
| `frontend/app/admin/emails/page.tsx` | (~?) | Email logs |

### Endpoints (consolidados)

**User management (`/v1/admin/users*`):**

| Método | Rota | Função |
|--------|------|--------|
| `GET /users?search&limit&offset&plan_filter` | list_users | Sanitized search; pagination |
| `POST /users` | create_user | email + password + plan |
| `DELETE /users/{user_id}` | delete_user | UUID validated; LGPD |
| `PUT /users/{user_id}` | update_user | name, email, phone, plan, is_admin |
| `POST /users/{user_id}/reset-password` | reset_password | gen temp password + email |
| `POST /users/{user_id}/assign-plan` | assign_plan | atomic plan transition |
| `PUT /users/{user_id}/credits` | update_credits | quota override |

**Cache admin (`/v1/admin/cache*`):**

| Método | Rota | Função |
|--------|------|--------|
| `GET /cache/metrics` | metrics dashboard | hits/misses por level |
| `GET /cache/{params_hash}` | inspect single entry | params, results, sources, age |
| `DELETE /cache/{params_hash}` | evict single | clear L1+L2+L3 |
| `DELETE /cache` | nuke all (CB-protected) | dangerous, requires confirm |

**Operations (`/v1/admin/*`):**

| Método | Rota | Função |
|--------|------|--------|
| `GET /admin/filter-stats` | filter pipeline metrics | `filter_stats_tracker.snapshot()` |
| `GET /reconciliation/history` | Stripe-DB reconciliation logs | last N runs |
| `POST /reconciliation/trigger` | manual trigger | invokes `run_reconciliation` job |
| `GET /support-sla` | response time stats | conversations awaiting_support TTR |
| `GET /trial-metrics` | trial funnel | active/expired/converted/churned |
| `GET /at-risk-trials` | risk score | trial_risk_detection output |
| `GET /search-trace/{search_id}` | full trace | OTel spans + state transitions |
| `POST /cb/reset` | reset circuit breaker | (per-source) |
| `GET /schema-contract-status` | last canary results | PNCP shape drift state |
| `GET /cron-status` | pg_cron health | `cron_job_health` view |
| `POST /trigger-{contracts,bids}-backfill` | manual ingestion run | enqueues ARQ job |
| `POST /clear-contracts-checkpoints` | reset ingestion state | for re-crawl |
| `GET /llm-cost?days&model` | cost dashboard | OpenAI usage |
| `GET /seo-metrics` | SEO dashboard | GSC + sitemap stats |
| `GET /slo`, `GET /slo/alerts` | SLO dashboard | error budget burn rate |
| `GET /feature-flags`, `PATCH /feature-flags/{flag_name}`, `POST /feature-flags/reload` | runtime toggle | reload sem restart |

### Algoritmos

1. **Auth: `require_admin`**
   - Bearer token → `require_auth` → user_id
   - Check `_get_admin_ids()` (env `ADMIN_USER_IDS` whitelist)
   - Fallback `_is_admin_from_supabase` (profiles.is_admin=true)
   - Cache 60s LRU para reduzir lookups

2. **Sanitize search input (Issue #205)**
   - Whitelist `[\w\s\-_.@]` regex
   - Remove SQL comments `--`
   - Strip PostgREST operators (`.eq.`, `.ilike.`, etc.)
   - Cap 100 chars

3. **UUID validation (Issue #203)**
   - `validate_uuid(user_id)` antes de qualquer query

4. **Log sanitization (Issue #168)**
   - `mask_user_id`: `abc12345...` (first 8 chars)
   - `sanitize_dict`: emails masked, secrets redacted
   - `log_admin_action`: structured JSON com action/target/diff

5. **Atomic plan assignment**
   - `POST /users/{id}/assign-plan` com optimistic lock via `version`
   - Updates `profiles.plan_type` + cria registro em `plan_billing_periods` se applicable
   - Sync com Stripe se subscription existe

6. **Reconciliation (cron + manual)**
   - Compara `subscriptions` table com Stripe Dashboard
   - Detecta drift: subscription cancelada no Stripe mas active no DB (ou vice-versa)
   - Lock distribuído via Redis `RECONCILIATION_LOCK_KEY`

7. **Trial metrics**
   - active = `WHERE plan_type='free_trial' AND trial_expires_at > now`
   - expired = `WHERE plan_type='free_trial' AND trial_expires_at < now`
   - converted = `WHERE plan_type != 'free_trial' AND first_trial_at IS NOT NULL`
   - Conversion rate = converted / (converted + expired + active)

### Estruturas de dados

- `AdminUsersListResponse`: items + total + facets {by_plan, by_role}
- `AdminCreateUserResponse`: id, email, plan_type, created_at
- `AdminUpdateCreditsResponse`: new_quota, plan_id

### Tabelas DB referenciadas

- `profiles` (users metadata, is_admin, is_master flags)
- `auth.users` (Supabase Auth)
- `plan_billing_periods`
- `subscriptions`
- `search_results_cache`, `search_sessions`, `search_state_transitions`
- `events_processed` (Stripe webhook audit)
- `tour_events`, `cta_tracking`
- `conversations`, `messages` (support SLA)
- `trial_email_log` (delivery)
- `feature_flags` (runtime)

### Constantes / Feature flags

| Const | Valor |
|-------|-------|
| `ADMIN_USER_IDS` | env CSV |
| Sanitize input cap | 100 chars |
| Admin lookup cache TTL | 60s |

### Lacunas

- 🔴 Privilege separation: `is_admin` é boolean (all-or-nothing). Não há RBAC granular (ex: cache_only_admin vs user_admin). Compliance LGPD pode exigir.
- 🟡 1.132 LOC em `admin.py` (mono-arquivo) — candidato a decomposição (auth helpers, user CRUD, cache admin, ops admin separados).
- 🟢 Frontend `app/admin/` tem 7 sub-páginas mas auth é client-side via `useAuth + planInfo.is_admin` — backend gates são a defesa real.

---
## Módulo 14 — `exports` 🟢

**Caminho:** `backend/excel.py`, `backend/google_sheets.py`, `backend/pdf_generator_edital.py`, `backend/routes/export.py`, `backend/routes/export_sheets.py`, `backend/oauth.py`

**Propósito:** Exportação de resultados em 3 formatos: (1) **Excel** xlsx via openpyxl (header verde + 11 colunas + totais SUM + meta sheet); (2) **Google Sheets** via API v4 batchUpdate com OAuth user-scoped; (3) **PDF** 1-page por edital (WeasyPrint/ReportLab via `pdf_generator_edital`).

### Arquivos primários

| Arquivo | LOC | Papel |
|---------|-----|-------|
| `backend/excel.py` | 315 | `create_excel(licitacoes, paywall_preview, total_before_paywall, org_name) -> BytesIO`, `sanitize_for_excel`, `parse_datetime` |
| `backend/google_sheets.py` | 436 | `class GoogleSheetsExporter`, batch API, OAuth credentials, formatting |
| `backend/pdf_generator_edital.py` | (~200) | `generate_edital_pdf(bid_data, plan_type)` ReportLab; viability badge color; trial watermark footer |
| `backend/routes/export.py` | 118 | POST `/export/pdf` endpoint (10s timeout via `asyncio.wait_for`) |
| `backend/routes/export_sheets.py` | 264 | POST `/api/export/google-sheets` + GET `/api/export/google-sheets/history` |
| `backend/oauth.py` | 474 | OAuth Google flow; Fernet AES-256 encrypted refresh tokens; CSRF state |

### Endpoints

| Método | Rota | Auth | Notas |
|--------|------|------|-------|
| `POST /v1/export/pdf` | require_auth | trial=watermark; sync wrapped in `asyncio.to_thread`; 10s timeout |
| `POST /v1/api/export/google-sheets` | require_auth + Google OAuth linked | batch API; up to 10k rows; preserves share links on update |
| `GET /v1/api/export/google-sheets/history` | require_auth | Lista exports prévios |

### Algoritmos

1. **Excel `create_excel` (`excel.py`)**
   - Header row green `#2E7D32` + white text bold
   - 11 columns: Codigo, Objeto, Orgao, UF, Municipio, Modalidade, Valor (BRL), Data Pub, Data Encerr, Link, Setor
   - Currency formatting `R$ #,##0.00` (Brazilian)
   - Date format `dd/mm/yyyy`
   - Hyperlinks em "Link" via `=HYPERLINK(url, "Abrir")`
   - Totals row: `=SUM(G2:G{N})` em coluna Valor (`compute_robust_total` para excluir NaN/strings)
   - Meta sheet: search params, total found, generated_at, user_email
   - `paywall_preview=True` + `total_before_paywall>N`: limita rows + adiciona row "+ X bids ocultas — assine para ver"
   - `sanitize_for_excel(value)` regex remove caracteres XML inválidos (openpyxl rejeita)

2. **Google Sheets `GoogleSheetsExporter`**
   - OAuth user credentials (Fernet-decrypted refresh token)
   - `spreadsheets().create({"properties":{"title":...}})` ou `update` em existing
   - `batchUpdate` ops: setBackgroundColor, setTextFormat, setNumberFormat, addBanding, autoResizeColumns
   - Performance: ~3-5s para 1000 rows
   - Cap 10k rows por export
   - Retorna `{spreadsheet_id, url, exported_at}`
   - Privacy: spreadsheets privadas por default (apenas creator)

3. **PDF `generate_edital_pdf`**
   - ReportLab Canvas A4 portrait
   - `_sanitize(value)`: strip + escape XML
   - `_format_currency(value)`: `R$ 1.234,56`
   - `_format_date(date_str)`: ISO → `DD/MM/YYYY`
   - `_viability_color(level)`: HIGH=green, MEDIUM=yellow, LOW=red
   - `_viability_label(level, score)`: badge text
   - Layout: header (logo + brand), body (objeto, orgão, UF, valor, datas, modalidade), viability box, AI summary (se presente), recomendação, footer
   - Trial: watermark "SMARTLIC TRIAL" diagonal cinza translúcido
   - Output: `bytes` (in-memory)
   - Sync; wrapped em `asyncio.to_thread` no router

4. **OAuth Flow (`oauth.py`)**
   - 3 endpoints: `/api/auth/google`, `/api/auth/google/callback`, `DELETE /api/auth/google`
   - State CSRF: random URL-safe token, persistido em Redis 10min
   - Exchange code→tokens em callback
   - **Fernet AES-256** encrypt `refresh_token` (env `OAUTH_FERNET_KEY`)
   - Save em `user_oauth_credentials` table: user_id, provider='google', encrypted_refresh, scope, expires_at, created_at
   - Refresh on-demand: decrypt → `Credentials.from_authorized_user_info` → `request.refresh(http)`
   - Scopes: `https://www.googleapis.com/auth/spreadsheets`
   - DELETE: revoke remoto + delete row

5. **PDF timeout handling**
   - `asyncio.wait_for(..., timeout=10.0)` → 503 com mensagem PT-BR
   - Outros erros → 500 com `exc_info=True` log

6. **Filename safety**
   - `_safe_filename(text, max_len=60)` em `routes/export.py`: NFKD normalize → ASCII → strip non-alphanumeric → fallback "edital"
   - Format: `SmartLic_{safe_title}_{YYYY-MM-DD}.pdf`

### Estruturas de dados

`PdfEditalRequest` (Pydantic):
- Core: objeto, orgao, uf, municipio, valor, data_encerramento, data_publicacao, modalidade, link, numero_compra, pncp_id
- Viability: viability_level, viability_score, viability_factors
- AI: resumo_executivo, recomendacao

`GoogleSheetsExportRequest`: search_id ou licitacoes inline + spreadsheet_id (update mode)

### Tabelas DB referenciadas

- `user_oauth_credentials`: user_id, provider, encrypted_refresh, scope, expires_at
- `google_sheets_exports`: id, user_id, spreadsheet_id, url, row_count, created_at

### Constantes / Feature flags

| Const | Valor |
|-------|-------|
| Excel max rows | sem limite (mas paywall_preview limita p/ trial) |
| Sheets max rows | 10.000 |
| PDF timeout | 10s |
| OAuth state TTL | 10min Redis |
| Fernet key | env `OAUTH_FERNET_KEY` |

### Dependências

`openpyxl`, `google-api-python-client`, `google-auth`, `google-auth-oauthlib`, `reportlab`, `cryptography.fernet`

### Lacunas

- 🟡 PDF é sync wrapped em `asyncio.to_thread` — bloqueia 1 worker thread por request. Concurrent requests podem saturar pool. Considerar ARQ background job se uso aumentar.
- 🔴 Excel `create_excel` é monolítico (315 LOC). Header/footer/styling poderia ser modular.
- 🟢 Trial watermark em PDF é uma bandeira vertical translúcida — não-removível por user (visual deterrent).
- 🟡 OAuth refresh token Fernet — se `OAUTH_FERNET_KEY` rotacionar, todos tokens existentes ficam unreadable. Não há key rotation handler.
- 🟡 Excel `compute_robust_total` em `utils/value_sanitizer` — precisa investigar se trata negativos, NULLs, strings.

---
## Módulo 15 — `observatory+seo-programmatic` 🟢

**Caminho:** `backend/routes/{observatorio,blog_stats,sitemap_*,empresa_publica,orgao_publico,contratos_publicos,dados_publicos,municipios_publicos,itens_publicos,compliance_publicos,indice_municipal,alertas_publicos,sectors_public,stats_public,calculadora,comparador,daily_digest,weekly_digest}.py` (18 routers, ~8.300 LOC), `frontend/app/{observatorio,cnpj,fornecedores,orgaos,municipios,licitacoes/[setor],contratos,blog/*,alertas-publicos,indice-municipal,calculadora,comparador,compliance}/`

**Propósito:** SEO orgânico programmatic. Páginas dinâmicas sem-auth com ISR (Next.js `revalidate=3600`). Powered by DataLake (`pncp_raw_bids` + `supplier_contracts` ~2M+ rows). Drives inbound. Sitemap dinâmico (Pro 1: licitacoes, Pro 2: contratos, Pro 3: cnpjs, Pro 4: orgaos, Pro 5: licitacoes do dia).

### Arquivos primários (backend)

| Arquivo | LOC | Propósito |
|---------|-----|-----------|
| `routes/observatorio.py` | 473 | Endpoints `observatorio/*` panorama setor + UF |
| `routes/blog_stats.py` | 1.179 | 8+ endpoints stats blog programmatic (setor/UF/cidade/contratos/panorama) |
| `routes/empresa_publica.py` | 659 | `/empresa/{cnpj}` — perfil B2G de fornecedor (contratos ganhos) |
| `routes/contratos_publicos.py` | 801 | `/contratos/{setor}`, `/contratos/{setor}/{uf}`, `/contratos/cidade/{cidade}`, `/contratos/orgao/{cnpj}` |
| `routes/orgao_publico.py` | 424 | `/orgao/{cnpj}` — perfil B2G de órgão público |
| `routes/municipios_publicos.py` | 538 | `/municipios/{slug}` |
| `routes/itens_publicos.py` | 522 | itens granulares (pesquisa por unidade) |
| `routes/compliance_publicos.py` | 289 | `/compliance/{cnpj}` — sanctions check |
| `routes/dados_publicos.py` | 282 | dataset público raw |
| `routes/indice_municipal.py` | 282 | índice municipal scoring |
| `routes/alertas_publicos.py` | 149 | `/alertas/{setor_id}/uf/{uf}` — public preview |
| `routes/sectors_public.py` | 356 | `/sectors`, `/sectors/trending`, `/sectors/{slug}/stats` |
| `routes/stats_public.py` | 448 | macro stats |
| `routes/calculadora.py` | 145 | calculadora viability/ROI público |
| `routes/comparador.py` | 179 | comparador editais |
| `routes/sitemap_licitacoes.py` | 281 | XML sitemap por setor |
| `routes/sitemap_orgaos.py` | 254 | XML sitemap orgãos |
| `routes/sitemap_cnpjs.py` | 307 | XML sitemap fornecedores |
| `routes/sitemap_licitacoes_do_dia.py` | 156 | Daily fresh sitemap |
| `routes/_sitemap_cache_headers.py` | (~?) | Cache-Control helpers |
| `routes/daily_digest.py` | 311 | daily digest data feed |
| `routes/weekly_digest.py` | 282 | weekly digest |

### Arquivos primários (frontend)

| Path | Tipo |
|------|------|
| `app/observatorio/[slug]/page.tsx` | dynamic route ISR 1h |
| `app/observatorio/raio-x-{setor,municipio,orgao,alerta}/[id]/page.tsx` | observatório raio-X |
| `app/cnpj/[cnpj]/page.tsx` | perfil de fornecedor |
| `app/fornecedores/[cnpj]/page.tsx` | (alt route) |
| `app/orgaos/[slug]/page.tsx` | perfil órgão |
| `app/municipios/[slug]/page.tsx` | perfil município |
| `app/licitacoes/[setor]/page.tsx` | listagem por setor |
| `app/contratos/[setor]/[uf]/page.tsx` | listagem por setor+UF |
| `app/contratos/orgao/[cnpj]/page.tsx` | contratos por órgão |
| `app/blog/{contratos,licitacoes,panorama,programmatic}/[setor]/page.tsx` | conteúdo programático blog |
| `app/blog/licitacoes/cidade/[city]/page.tsx` | blog por cidade |
| `app/alertas-publicos/[setor]/[uf]/page.tsx` | preview público |
| `app/indice-municipal/[municipio-uf]/page.tsx` | índice municipal |
| `app/calculadora/embed/page.tsx` | iframe-friendly embed |
| `app/comparador/page.tsx` | comparador |
| `app/compliance/[cnpj]/page.tsx` | sanctions check |
| `app/sitemap*.xml` (route handlers) | dynamic XML |

### Algoritmos / Patterns

1. **DataLake-backed queries**
   - 90% das rotas SEO consultam `pncp_raw_bids` (400d retention) ou `supplier_contracts` (~2M+ rows)
   - RPC functions Postgres: `get_panorama_setor`, `get_contratos_orgao`, `get_top_fornecedores_setor`, `get_alertas_setor_uf`, etc.
   - Full-text search Português `tsquery` em `objeto` column (GIN index)
   - Filters: setor_id, UF, modalidade, esfera, valor range, data range

2. **ISR + Sitemap pattern (SEN-FE-001 fix)**
   - Frontend: `export const revalidate = 3600` (1h) em todas páginas SEO
   - Fetches usam `next: {revalidate: 3600}` (NÃO `cache: 'no-store'`)
   - Antipattern resolvido: misturar `revalidate` com `no-store` quebra SSG e dispara 4146 build-time fetches simultâneos (memória project_backend_outage_2026_04_27)

3. **Sitemap dinâmico**
   - Sitemap index `/sitemap.xml` aponta para 4 sub-sitemaps:
     - `/sitemap-licitacoes.xml` (por setor)
     - `/sitemap-orgaos.xml`
     - `/sitemap-cnpjs.xml` (fornecedores)
     - `/sitemap-licitacoes-do-dia.xml` (fresh, daily)
   - Backend gera XML on-demand com cache headers (`max-age=3600 stale-while-revalidate=86400`)
   - Cap por sitemap: 50.000 URLs (limite Google)

4. **Slugify**
   - Cidade/órgão/setor → URL slug: NFKD normalize → ASCII → lowercase → kebab-case
   - Reverse map: slug → entity_id em DB

5. **Rate limiting (público)**
   - Mais permissivo que rotas autenticadas
   - Token bucket per-IP com cap maior

6. **Negative cache (incident memory)**
   - Após project_backend_outage_2026_04_27: rotas adicionaram negative cache em DB failure (não estavam tendo, causou cascade)
   - PR #529 implementou em perfil-b2g + fornecedor

7. **Schema.org JSON-LD**
   - Páginas blog injetam FAQPage JSON-LD (SEO-021)
   - Empresa pages injetam Organization
   - Listagem injetam ItemList

8. **Trial conversion CTAs**
   - Páginas SEO mostram banner "Quer ver mais? Crie conta gratis 14 dias"
   - Tracked via `analytics.track-cta` quando user clica

### Estruturas de dados

`PanoramaStats`: total_contratos, valor_total, top_orgaos, top_fornecedores, evolução temporal
`SectorBlogStats`: setor_id, setor_name, total_bids, total_value, top_uf, ...
`CidadeStats`, `CidadeSectorStats`, `OrgaoProfile`, `FornecedorProfile` (CNPJ → contratos histórico)
`ComparadorBidsResponse`: bids comparáveis side-by-side

### Tabelas DB referenciadas

- `pncp_raw_bids` (1.5M rows, 400d retention)
- `supplier_contracts` (~2M+ rows)
- `entities` (CNPJ master, BrasilAPI enriched)
- `municipios` (IBGE enriched)
- `sanctions_master` (compliance)
- `panorama_snapshots` (SEO snapshot job, daily)
- `indice_municipal_scores`
- `sector_keywords` (DB-backed sector definitions)

### Constantes / Feature flags

| Const | Valor |
|-------|-------|
| ISR revalidate | 3600s (1h) |
| Sitemap cache | max-age=3600, swr=86400 |
| Sitemap URL cap per file | 50.000 |
| `OBSERVATORY_ENABLED`, `BLOG_ENABLED` | feature flags |

### Lacunas

- 🔴 18 routers em `routes/*_publicos.py` — duplicação de lógica de slugify/normalize/cache. Considerar shared `routes/_seo_helpers.py`.
- 🟡 Sitemaps generation é on-demand sem pre-caching. Picos de Googlebot (project_backend_outage_2026_04_27 Stage 2) saturam backend.
- 🟢 SEO programmatic é vacuum aquisição (memory: SmartLic baseline 126 clicks/9.9k impr 28d, CTR 1.3%) — alvo on-page pivot sob STORY-2026-04-26.
- 🟡 Frontend `app/blog/programmatic/[setor]` parece overlap com `app/blog/licitacoes/[setor]` — investigar.

---
## Módulo 16 — `design-system` 🟢

**Caminho:** `frontend/tailwind.config.ts`, `frontend/app/globals.css`, `frontend/components/ui/`, `frontend/components/`

**Propósito:** Tailwind 3 + CSS Variables theme-tokens approach. WCAG AA-validated color contrast. Premium SaaS aesthetic (STORY-174). Design tokens mapeiam para CSS vars permitindo dark mode + multiple themes. Component library com Storybook.

### Arquivos primários

| Arquivo | LOC | Papel |
|---------|-----|-------|
| `frontend/tailwind.config.ts` | (~150) | Theme extend — colors via `var(--canvas)` etc., fontFamily (body/display/data), borderRadius (input=4px, button=6px, card=8px, modal=12px), shadows STORY-174 |
| `frontend/app/globals.css` | (~300) | CSS variables: `--canvas`, `--ink/-secondary/-muted/-faint`, `--brand-navy/-blue/-blue-hover/-blue-subtle`, `--surface-{0,1,2,elevated}`, `--success/-subtle`, `--error/-subtle`, `--warning/-subtle`, `--gem-{sapphire,emerald,amethyst,ruby}`, `--chart-{1..10}`, `--ring`, `--ink-disabled`, `--surface-disabled`. Dark mode via `[data-theme=dark]` |
| `frontend/components/ui/button.tsx` | (~?) | Primary button variants (default, outline, ghost, destructive, link) |
| `frontend/components/ui/Input.tsx`, `Label.tsx`, `Pagination.tsx`, `CurrencyInput.tsx`, `AnimateOnScroll.tsx` | (~?) | Atomic components |
| `frontend/components/{Modal,EmptyState,ErrorMessage,ErrorStateWithRetry,PageHeader,ViabilityBadge}.tsx` | (~?) | Pattern components |
| `frontend/components/*.stories.tsx` (8 stories) | — | Storybook docs |

### Token Categories

| Token | Light value | Contrast vs canvas | WCAG |
|-------|-------------|---------------------|------|
| `--canvas` | `#ffffff` | base | — |
| `--ink` | `#1e2d3b` | 12.6:1 | AAA ✅ |
| `--ink-secondary` | `#3d5975` | 5.5:1 | AA ✅ |
| `--ink-muted` | `#6b7a8a` | 5.1:1 | AA ✅ (P2-6 fix) |
| `--ink-faint` | `#c0d2e5` | 1.9:1 | decorative only |
| `--brand-navy` | `#0a1e3f` | 14.8:1 | AAA ✅ |
| `--brand-blue` | `#116dff` | 4.8:1 | AA ✅ |
| `--brand-blue-hover` | `#0d5ad4` | 6.2:1 | AA+ ✅ |
| `--success` | `#16a34a` | 4.7:1 | AA ✅ |
| `--error` | `#dc2626` | 5.9:1 | AA ✅ |
| `--warning` | `#ca8a04` | 5.2:1 | AA ✅ |
| `--ink-disabled` | `#6B7280` | 4.6:1 vs `--surface-disabled` | AA ✅ (STORY-2.5) |

### Typography

| Token | Font |
|-------|------|
| `--font-body` | sans-serif (Inter) |
| `--font-display` | sans-serif (display) |
| `--font-data` | monospace |

### Spacing / Radius

- 4px base grid: spacing-1=4px, 2=8px, 3=12px, 4=16px, 6=24px, 8=32px, 16=64px
- Radius: input=4px, button=6px, card=8px, modal=12px

### Padrões

1. **CSS-vars via Tailwind**: `bg-[var(--surface-1)]`, `text-[var(--ink)]`, semantic aliases (`primary`, `secondary`, `accent`)
2. **Dark mode**: `darkMode: "class"` — toggle via `<html class="dark">` ou `data-theme=dark`
3. **Decorative-only colors**: `--ink-faint`, `--brand-blue-subtle`, `--success-subtle`, `--error-subtle`, `--warning-subtle` — não-contraste-AA, só backgrounds
4. **DEBT-012**: Não usar hex direto; sempre via tokens. Story-2.5 STORY validou tokens para disabled state
5. **Animations**: `AnimateOnScroll` (Framer Motion) para reveal-on-scroll
6. **Component composition**: shadcn-style ui/ + opinionated wrappers em components/
7. **Storybook**: 8+ stories validam visual states; integrado com Chromatic? (não confirmed)

### Dependências

`tailwindcss@3`, `framer-motion`, `lucide-react` (ícones), `@radix-ui/react-*`, `class-variance-authority`, `tailwind-merge`

### Lacunas

- 🟡 Tokens-de-design não documentados em arquivo separado (`design-tokens.md`); única fonte é `globals.css` + Tailwind config
- 🔴 Storybook coverage incompleta (~8/40+ componentes têm stories)
- 🟢 WCAG AA validado contraste — bem-documentado em comentários

---

## Módulo 17 — `email-templates` 🟢

**Caminho:** `backend/templates/emails/`, `backend/email_service.py`, `backend/jobs/cron/notifications.py`, `backend/jobs/cron/trial_emails.py`

**Propósito:** Email transactional + lifecycle (trial 6-step, dunning, alerts, digests). Render HTML responsive (Gmail/Outlook/Apple Mail compat). Provider Resend (`smartlic.tech` verified). Webhook delivery tracking.

### Arquivos primários

| Arquivo | Papel |
|---------|-------|
| `templates/emails/base.py` | `email_base(title, body_html, unsubscribe_url, is_transactional)` — wrapper HTML responsive (mso compat); footer com company info + privacy. AC17/AC18 |
| `templates/emails/trial.py` | STORY-321 AC7-9: 6-email trial sequence — Day 0 Welcome, Day 3 Engagement, Day 7 Paywall alert, Day 10 Valor acumulado, Day 13 Último dia, Day 16 Expirado (reengage 20% off cupom). `_format_brl(value)`, `_stats_block(stats, show_pipeline)` |
| `templates/emails/billing.py` | Checkout success, payment failed, refund |
| `templates/emails/dunning.py` | Pre-dunning + dunning sequence (cartão expirando) |
| `templates/emails/welcome.py`, `welcome_subscriber.py` | Welcome email (signup) |
| `templates/emails/digest.py`, `alert_digest.py` | Daily/weekly digest opportunities |
| `templates/emails/quota.py` | Quota warning |
| `templates/emails/day3_activation.py` | STORY-310 retired (replaced by trial.py) |
| `templates/emails/share_activation.py` | Quando user é compartilhado um análise |
| `templates/emails/referral_welcome.py`, `referral_converted.py` | Programa referral |
| `templates/emails/panorama_t1_delivery.py` | Relatório T1 |
| `templates/emails/boleto_reminder.py` | Boleto vencendo |
| `email_service.py` | Resend SDK wrapper, template renderer, retry, logging em `trial_email_log` |

### Constantes

| Const | Valor |
|-------|-------|
| `SMARTLIC_GREEN` | `#2E7D32` (header) |
| `SMARTLIC_DARK` | `#1B5E20` |
| `FRONTEND_URL` | `https://smartlic.tech` |
| Trial sequence | 6 emails (Day 0/3/7/10/13/16) |
| From address | `tiago@smartlic.tech` (memory: outreach pessoal) |

### Algoritmos

1. **`email_base` wrapper**
   - HTML5 doctype + `<meta viewport>` + MSO conditional comments
   - Inline styles (compat Gmail)
   - Footer: company info, privacy link, address
   - `is_transactional=True` → no unsubscribe (AC17)
   - `unsubscribe_url` opcional (promo only)

2. **Trial sequence dispatch (`_trial_sequence_loop`)**
   - Cron interval `TRIAL_SEQUENCE_INTERVAL_SECONDS`
   - Query users em trial WHERE day_in_trial ∈ {0,3,7,10,13,16} AND email_log NÃO tem record para esse day
   - Batch `TRIAL_SEQUENCE_BATCH_SIZE` por iteração
   - Render template + send via Resend
   - INSERT `trial_email_log` com `delivery_status=null` (atualizado por webhook)

3. **Webhook delivery tracking (memory)**
   - 2026-04-24 migration `20260424180000_trial_email_delivery_tracking.sql` live
   - Resend webhook → POST `/v1/trial-emails/webhook`
   - HMAC verify (gap aberto: ainda não impl)
   - Updates `trial_email_log.delivery_status` = `delivered`, `bounced`, `complained`, `opened`, `clicked`

4. **Dunning sequence**
   - Pre-dunning: cartão expira em 7d → email reminder
   - Dunning Day 1, 3, 7, 14: cobrança falhada → upsell update_payment_method
   - Após Day 14: subscription canceled (Stripe)

5. **Stats block (`_stats_block`)**
   - searches_count, opportunities_found, total_value_estimated, pipeline_items
   - Format BRL: `R$ 1.2M`, `R$ 500k`, `R$ 1.234`

### Tabelas DB referenciadas

- `trial_email_log`: user_id, day_in_trial, sent_at, delivery_status, opened_at, clicked_at, message_id (Resend), template_name
- `email_unsubscribes`: user_id, category, unsubscribed_at
- `email_events`: webhook events history

### Lacunas

- 🔴 HMAC webhook signature verify ainda gap (memory `reference_trial_email_log_delivery_status_null.md`)
- 🟡 Email rendering puramente Python f-strings — não usa Jinja2 (XSS risk se user data não-escaped)
- 🟢 Resend `tiago@smartlic.tech` + reply-to `tiago.sasaki@gmail.com` para outreach pessoal (memory)

---

## Módulo 18 — `tests+migrations` 🟢

**Caminho:** `backend/tests/` (445 arquivos), `frontend/__tests__/`, `frontend/e2e-tests/` (228 arquivos), `supabase/migrations/` (183 .sql), `backend/migrations/` (12 legacy)

**Propósito:** Suíte de qualidade. Backend: pytest 5131+ tests passing. Frontend: Jest 2681+ tests passing. E2E: Playwright 60 critical flows. CI gates obrigatórios pré-merge. Schema migrations via Supabase CLI + Python Alembic legacy.

### Backend Tests

| Categoria | Pasta | Notas |
|-----------|-------|-------|
| Pipeline | `tests/test_pipeline*.py`, `test_search_*.py` | 7+ stages com unit + integration tests |
| Filter | `tests/test_filter*.py`, `test_llm_arbiter*.py` | 15+ test files density + zero-match |
| Cache | `tests/test_cache_*.py`, `test_swr*.py` | Layered cache + SWR |
| Billing | `tests/test_billing_*.py`, `test_stripe_*.py`, `test_quota_*.py` | Webhook integration + atomic quota |
| Auth | `tests/test_auth_*.py`, `test_jwt_*.py`, `test_oauth_*.py` | JWT 3-strategy + OAuth Fernet |
| Integration | `tests/integration/` | E2E backend flows |
| Stories | `tests/test_story_*.py`, `test_crit*.py`, `test_debt*.py`, `test_gtm*.py` | Story-driven test files |
| Timeouts | `tests/test_timeout_invariants.py` | Pipeline budget assertion |
| Migrations | `tests/test_migrations.py` | Pairing + idempotency |

**Anti-Hang Rules** (CRITICAL — CLAUDE.md):
- pytest-timeout 30s default
- `pytest --timeout=30 -q` periodicamente
- ARQ mock cleanup automático via `conftest._isolate_arq_module`
- subprocess `Popen.communicate(timeout=X)` mandatory
- `timeout_method = "thread"` (Windows compat)

**Patrones de mocking** (must follow):
- Auth: `app.dependency_overrides[require_auth]`
- Cache: `patch("supabase_client.get_supabase")`
- Config: `@patch("config.FLAG_NAME", False)`
- LLM: `@patch("llm_arbiter._get_client")`
- Quota: tests `/buscar` MUST mock `check_and_increment_quota_atomic`

### Frontend Tests

| Categoria | Pasta | Tools |
|-----------|-------|-------|
| Components | `__tests__/components/` | RTL + Jest |
| Hooks | `__tests__/hooks/` | renderHook |
| API proxy | `__tests__/api/` | jest mocks |
| E2E flows | `e2e-tests/` | Playwright headless + headed |

**Polyfills** (`jest.setup.js`):
- `crypto.randomUUID` (jsdom lacks)
- `EventSource` (SSE testing)

**Coverage thresholds:** Backend 70%, Frontend 60%.

### Supabase Migrations

- 183 arquivos `supabase/migrations/` (numbered + timestamped formats)
- **Source of truth** para SQL schema (STORY-6.3)
- Pairs `.sql` + `.down.sql` obrigatório (STORY-6.2 — migration-gate.yml block)
- Apply via `npx supabase db push` (CI auto-apply em deploy.yml)
- pg_cron schedules em migrations: `purge-old-bids` (07 UTC), `cleanup-search-cache`, `cleanup-search-store`
- Memory: `.down.sql` causa duplicate-key se CLI 2.x rodar paired (workaround stash)

### Backend Migrations Legacy

- 12 arquivos `backend/migrations/` (Python Alembic-style)
- **Histórico audit only** — não-executados por CI
- Não adicionar novos aqui (STORY-6.3 policy)

### CI Workflow Gates

| Workflow | Tipo | Block? |
|----------|------|--------|
| Backend Tests | pytest --cov | required |
| Frontend Tests | jest + cov | required |
| Validate PR Metadata | body sections | warning only |
| Lighthouse | a11y/perf | warning only |
| migration-gate | pending migrations + pairing | warning + block on missing .down.sql |
| migration-check | unapplied alert | block |
| api-types-check | drift detection | block |
| E2E Playwright | critical flows | required (selective) |

### Lacunas

- 🔴 5131 backend tests é ótimo coverage mas LOC produção ~30k+ (~17%) — tests pesados em integration, magrinhos em utils
- 🟡 E2E 60 tests é seletivo; race conditions em SSE/SWR não cobertos exhaustively
- 🟢 Anti-hang rules conftest é state-of-the-art para Windows/WSL
- 🟡 Migration `nul` arquivo em routes/ (Windows reserved name) — corrupção WSL

### Adendos 2026-05-08 → 2026-05-09 (DOC-COVERAGE-001)

#### SEC-TEST-2026-001 (PR #947) — OWASP Top-5 baseline

Substitui Issue #201 (escopo monolítico stale >5d). 69 tests passing em `backend/tests/security/`:

| Categoria OWASP | LOC | Files |
|-----------------|-----|-------|
| Broken Access Control / Auth bypass | 10 tests | `test_auth_bypass.py` |
| Injection (SQLi) | 32 tests | `test_sqli.py` (parametrized fuzz strings) |
| SSRF | 12 tests | `test_ssrf.py` (URL allowlist + redirect handling) |
| Stripe webhook spoofing | 8 tests | `test_stripe_signature.py` (HMAC negative paths) |
| Rate-limit bypass | 7 tests | `test_rate_limit_bypass.py` |

**CI workflow:** `security-tests.yml` (dedicated, separate from `backend-tests.yml`) — required check, fail-fast.

**Doc:** `docs/security/test-baseline.md` com roadmap SEC-TEST-002+ (OWASP A05/A06/A09 + SSRF-fuzz expansion).

**Score impact:** Test/CI gates 84→89% (+5), RBAC/Security 77→83% (+6) — consolidado em review-report §11.

#### TEST-ERR-RECOVERY-2026-001 (PR #946) — Error recovery coverage

Substitui Issue #236 (TD-TEST-025 stale). 24 tests em 7 arquivos cobrindo paths de incident 2026-04:

| Path | Test file | Origin incident |
|------|-----------|-----------------|
| Pipeline timeout | `backend/tests/recovery/test_pipeline_timeout.py` | CRIT-084 worker no-timeout |
| Pool exhaustion | `backend/tests/recovery/test_pool_exhaust.py` | POOL-LEAK-001 (`feedback_pool_leak_caller_timeout_vs_sql_timeout`) |
| Redis ConnectionError fallback | `backend/tests/recovery/test_redis_fallback.py` | Disk IO degradation 2026-04-29 |
| Stripe retry idempotency | `backend/tests/integration/test_stripe_retry.py` | webhook 3-day retry pattern |
| OpenAI 503 fallback | `backend/tests/recovery/test_openai_fallback.py` | LLM_FALLBACK_PENDING_ENABLED |
| SSE reconnect | `frontend/__tests__/recovery/sse-reconnect.test.tsx` | EventSource exponential backoff |
| API backoff | `frontend/__tests__/recovery/api-backoff.test.tsx` | 429/503 client retry |

**Doc:** `docs/testing/recovery-coverage.md`.

#### Godmodule LOC CI gate (PRs #903, #909) — ARCH-100-001

Story `ARCH-100-001-godmodule-tracker.md` — tracker arquivo único `>1000 LOC` é code smell.

**Workflow:** `.github/workflows/godmodule-loc-gate.yml` falha PR se algum file aumentar acima do baseline registrado em `.godmodule-loc-baseline.json`. Decrement allowed (refactor incentive).

**Files atualmente flagados (snapshot baseline):**
- `backend/pipeline/stages/execute.py` — 1240 LOC
- `backend/pipeline/stages/generate.py` — 580 LOC (under threshold but watched)
- `backend/dedup/engine.py` — wraps consolidation (566 LOC)
- `backend/source_merger.py` — 559 LOC

**Política:** novos PR não podem aumentar contagem dos top-5 godmodules; refactor encorajado via `simplify` skill.

---

## Módulo 19 — `intel-reports` 🟢 (refresh 2026-05-09 — DOC-COVERAGE-001)

**Caminho:** `backend/routes/intel_reports.py`, `backend/services/billing.py:create_intel_report_checkout`, `backend/jobs/queue/jobs.py:_generate_*_report_pdf`, `backend/pdf_generator.py`, `backend/pdf_generator_sector_uf_report.py`, `backend/schemas/intel_report.py`, `backend/email_service.py:send_intel_report_ready`

**Propósito:** Pipeline one-time purchase de relatórios PDF com IA — `Stripe checkout → webhook handler → ARQ job → RPC SQL → LLM narrative → ReportLab PDF → Storage upload → email + dashboard delivery`. v0.1 cnpj_supplier (R$67) e v0.2 sector_uf (R$147) compartilham skeleton; diferenciam-se em payload, RPC, PDF generator e email template.

### Arquivos primários

| Arquivo | LOC (empírico via wc -l no refresh) | Papel |
|---------|-------------------------------------|-------|
| `backend/routes/intel_reports.py` | (medir empiricamente em refresh subsequente — file existe) | `POST /v1/intel-reports/checkout`, `GET /v1/intel-reports/me`, `GET /v1/intel-reports/{id}/download` |
| `backend/services/billing.py:create_intel_report_checkout` | função | Stripe Checkout Session mode=payment; metadata `intel_report_id` para idempotency webhook |
| `backend/jobs/queue/jobs.py:_generate_cnpj_supplier_report_pdf` | função ARQ | v0.1 worker — RPC `cnpj_supplier_intel` + LLM + PDF |
| `backend/jobs/queue/jobs.py:_generate_sector_uf_report_pdf` | função ARQ | v0.2 worker — RPC `sector_uf_intel` + PDF (sem LLM step? — verificar via spec 07) |
| `backend/pdf_generator.py:CNPJSupplierReport` | classe | ReportLab template v0.1 (ver spec 07b) |
| `backend/pdf_generator_sector_uf_report.py:SectorUFReport` | classe | ReportLab template v0.2 |
| `backend/schemas/intel_report.py` | Pydantic | `IntelReportKind`, `CnpjSupplierPayload`, `SectorUFPayload` |
| `backend/email_service.py:send_intel_report_ready` | função | Resend wrapper (template `intel-report-ready` ou `intel-report-ready-sector`) |

### Funções-chave

| Função | Confiança |
|--------|-----------|
| `POST /v1/intel-reports/checkout` (route handler) | 🟢 — cria intel_report row pending + Stripe session |
| `_handle_checkout_session_completed` (em `billing.py` Stripe webhook) | 🟢 — idempotency via `stripe_webhook_events` + UPDATE intel_report status='paid' + ARQ enqueue |
| `_generate_cnpj_supplier_report_pdf(ctx, intel_report_id)` | 🟢 — RPC + LLM + PDF + Storage + email |
| `_generate_sector_uf_report_pdf(ctx, intel_report_id)` | 🟢 — RPC + PDF + Storage + email (skeleton sibling) |
| `CNPJSupplierReport(payload, narrative_md).render() → bytes` | 🟢 |
| `SectorUFReport(payload, narrative_md).render() → bytes` | 🟢 |

### Algoritmos

1. **Idempotência ponta-a-ponta:**
   - Stripe webhook `stripe_webhook_events.event_id` UNIQUE constraint (já em §11 jobs+cron Module 8)
   - `intel_report_purchases.stripe_payment_intent_id` UNIQUE — barreira final contra double-fulfillment
   - ARQ retry policy `max_tries=3, exponential 1m/5m/30m` em falhas transient
2. **LLM narrative composition (v0.1):** prompt template em `prompts/intel_cnpj_narrative.txt` (não-inspecionado neste passo); GPT-4.1-nano; chamada com `max_tokens` calibrado (cost mgmt) — ver spec 13.
3. **PDF rendering (ReportLab):** ver spec 07b — header/footer com signed_url, paginação, charts via matplotlib serialized.
4. **Storage upload:** bucket `intel-reports` (privado); `signedUrl(path, expiresIn=600s)` para download; `expires_at = NOW() + 30d` em `intel_report_purchases`.
5. **Email delivery:** Resend `from=tiago@smartlic.tech` (memory `reference_resend_personal_tone_send`) com link signed_url 7d; fallback `email_status='bounced'` registra mas dashboard preserva acesso.
6. **Failure paths:** ver `_reversa_sdd/flowcharts/intel-reports.md` Flow 3 (webhook delivery / PDF timeout / Storage upload / email retry).

### Estruturas de dados

`IntelReportKind` (Pydantic Enum):
- `cnpj_supplier` (R$67, v0.1)
- `sector_uf` (R$147, v0.2)

`intel_report_purchases` row (ver data-master §11.3 para schema completo).

### Métricas Prometheus / Sentry

- `smartlic_intel_report_generated_total{kind}` (counter)
- `smartlic_intel_report_generation_duration_seconds{kind}` (histogram)
- `smartlic_intel_report_failed_total{kind, reason}` (counter — reasons: `llm_timeout`, `storage_upload`, `email_send`, `rpc_timeout`)
- Sentry `capture_exception` em qualquer falha terminal (após retries esgotados)

### Dependências

`billing` (Stripe webhook), `arq` (job queue), `supabase_client` (RPCs), `openai` (LLM v0.1), `reportlab` (PDF), `supabase.storage` (bucket), `resend` (email)

### Lacunas

- 🟡 v0.2 sector_uf não claro se usa LLM narrative (spec 07 indica que sim mas implementação em `_generate_sector_uf_report_pdf` pode delegar tudo a ReportLab determinístico)
- 🔴 Refund flow `status='refunded'` é manual (admin via Stripe Dashboard) — story `INTEL-FAIL-REFUND-001` no backlog para automatizar
- 🟢 Specs SDD 07 + 07b + 13 cobrem requisitos funcionais (ver `_reversa_sdd/specs/`)

---

## Módulo 20 — `plans-capabilities-runtime` 🟢 (refresh 2026-05-09 — DOC-COVERAGE-001)

> **Decisão:** módulo separado vs extensão de Module 5 (billing-quota). Module 5 cobre cycle-billing (Stripe lifecycle, plan_billing_periods sync, dunning). Module 20 cobre runtime capability cache layer (carrega `capabilities` jsonb do plano em memória, TTL 30s, source-of-truth para enforcement). Overlap <70% — separar.

**Caminho:** `backend/quota/plan_enforcement.py`, `backend/quota/quota_core.py`, migration `supabase/migrations/20260509011633_plans_capabilities_table.sql`

**Propósito:** Runtime cache de capabilities por plano (`max_history_days`, `allow_excel`, `allow_pipeline`, `max_requests_per_month`, `max_requests_per_min`, `max_summary_tokens`, `priority`). Source of truth migrou de hardcoded dict (`PLAN_CAPABILITIES` em `quota_core.py`) para `public.plans.capabilities` jsonb (TD-GTM-003 / PR #916 issue #192).

### Arquivos primários

| Arquivo | Papel |
|---------|-------|
| `backend/quota/plan_enforcement.py` | enforcement points (decorator `enforce_capability` em routes) |
| `backend/quota/quota_core.py:_load_plan_capabilities_from_db()` | loader — query `public.plans` + cache TTL=30s |
| `backend/quota/quota_core.py:plan_capabilities_cache` | dict in-memory `{plan_id → {capabilities, version, fetched_at}}` |

### Funções-chave

| Função | Confiança |
|--------|-----------|
| `_load_plan_capabilities_from_db()` | 🟢 — query SELECT id, capabilities, version FROM plans + populate cache |
| `get_plan_capabilities(plan_id) → dict` | 🟢 — cache hit fresh (<30s) → return; stale → refresh + return |
| `enforce_capability(name)` (decorator) | 🟢 — wraps route; bloqueia 403 se `capabilities[name] == false` |
| `enforce_quota(name, count)` (decorator) | 🟢 — wraps route; check `monthly_quota` + atomic increment |

### Algoritmos

1. **Cache TTL=30s:** balance entre latência (cache miss = 1 SELECT à plans) e freshness (admin altera plan capability via Supabase Studio → max 30s para propagar). Não usa Redis pubsub (memory `feedback_handoff_stale_30h` — pubsub daemon-thread foi anti-pattern revertido em DATA-CNAE-001 #679).
2. **Fail-safe:** se DB unreachable, cache NÃO é flushed — serve último valor conhecido (CLAUDE.md "fail to last known plan"). Sentry `capture_message(level=warning)` em refresh failure.
3. **Versioning:** `plans.version` int monotonically incremented em capability change. Clientes (frontend localStorage 1h TTL) podem enviar `If-None-Match: version=N` em GET /me/capabilities → backend retorna 304 se version === client.

### Trigger audit (em DB layer):

`plans_audit_trigger` AFTER INSERT/UPDATE/DELETE → `plans_audit_trigger_fn()` insere row em `public.plans_audit` (ver data-master §11.2). Permite reconstruir histórico completo de capabilities.

### Métricas Prometheus

- `smartlic_plan_capability_cache_hits_total{plan_id}` (counter)
- `smartlic_plan_capability_cache_miss_total{plan_id, reason}` (counter — reasons: `expired`, `cold_start`, `db_error`)
- `smartlic_plan_capability_db_load_duration_seconds` (histogram)

### Dependências

`supabase_client` (SELECT plans), `metrics`, internal cache dict

### Lacunas

- 🟢 Migration TD-GTM-003 self-test invariant (`SELECT count(*) WHERE is_active AND capabilities IS NULL = 0`) garante consistency em apply-time
- 🟡 Cache cold-start (primeira request pós-deploy) faz query bloqueante 1x — hot-path latency espike pode aparecer em SLO p99 (não medido)
- 🟡 Cross-pod cache coherence (Railway com 1 worker) é trivial; se escalar para >1 replica, cada uma terá cache independente — drift máximo 30s (aceitável dado TTL)

---

## Módulo 21 — `llm-summary-cache` 🟢 (DOC-COVERAGE-002)

> Módulo de cache para resumos executivos LLM (Issue #160). Cacheia o output de `gerar_resumo()` em Redis com TTL=7d, key SHA-256 do payload ordenado. Falha de Redis = graceful — chama OpenAI direto.

**Caminho:** `backend/llm.py:841-909` (`get_or_generate_resumo_cached`), `backend/cache_module.py` (Redis client)

**Propósito:** Evitar chamadas repetidas ao OpenAI para o mesmo conjunto de bids. Cache hit reduz latência de segundos para <50ms p95 e elimina custo OpenAI da chamada repetida.

### Arquivos primários

| Arquivo | Papel |
|---------|-------|
| `backend/llm.py` | `get_or_generate_resumo_cached()` — async wrapper com cache-aside |
| `backend/cache_module.py` | singleton `redis_cache` (Redis client, reexportado) |

### Funções-chave

| Função | Confiança |
|--------|-----------|
| `get_or_generate_resumo_cached(licitacoes, ...)` → `ResumoLicitacoes` | 🟢 — cache-aside: try read → hit? return. miss? call OpenAI → store → return |
| `_build_resumo_cache_key(licitacoes, sector_name, termos_busca, setor_id)` → `str` | 🟢 — SHA-256 do payload sorted JSON |
| `recompute_temporal_alerts(resumo, licitacoes)` | 🟢 — re-aplica alertas temporais pós-cache hit |

### Algoritmos

1. **Cache key:** `llm:summary:{sha256(sorted bid IDs + search params)}`. Determinístico para o mesmo conjunto de bids.
2. **Cache-aside:** `redis_cache.get(key)` → hit → `ResumoLicitacoes.model_validate_json()` + recompute temporal alerts. Miss → `gerar_resumo()` → `redis_cache.setex(key, TTL=7d, json)`.
3. **Graceful degradation:** qualquer exceção Redis (conexão, timeout, OOM) é logada como debug e ignorada — `gerar_resumo()` é chamado direto.
4. **Empty-input short-circuit:** `if not licitacoes: return gerar_resumo(...)` sem cache (determinístico e rápido).

### Métricas Prometheus

- `smartlic_llm_summary_cache_hits_total` (counter)
- `smartlic_llm_summary_cache_misses_total` (counter)

### Constantes/Feature Flags

| Constante | Valor | Local |
|-----------|-------|-------|
| `_LLM_SUMMARY_CACHE_TTL` | `7 * 24 * 3600` (7 dias) | `backend/llm.py` |

### Dependências

`cache_module` (Redis), `llm.py` (gerar_resumo), `schemas/search.py` (ResumoLicitacoes)

### Lacunas

- 🟢 Cache warming não implementado (intencional — DataLake p95 <100ms torna pre-population waste)
- 🟢 Redis connection failure cai direto para OpenAI — sem circuit breaker intermediário
- 🟡 TTL de 7d pode servir summary obsoleto se dados do DataLake forem atualizados retroativamente (não acontece no modelo append-only atual)

---

## Módulo 22 — `bulkhead-concurrency` 🟢 (DOC-COVERAGE-002)

> STORY-296: Per-source bulkhead pattern com semáforos isolados para cada fonte de dados (PNCP, PCP, ComprasGov). Garante que exaustão de uma fonte não degrade as demais.

**Caminho:** `backend/bulkhead.py` (225 LOC)

**Propósito:** Isolamento de concorrência por fonte. Cada fonte tem seu próprio `asyncio.Semaphore` e budget de timeout. Se uma fonte fica lenta, suas conexões não consomem slots das outras.

### Arquivos primários

| Arquivo | Papel |
|---------|-------|
| `backend/bulkhead.py` | `SourceBulkhead` class + module-level registry |
| `backend/config.py` | configurações `PNCP_BULKHEAD_CONCURRENCY`, `PCP_BULKHEAD_CONCURRENCY`, `COMPRASGOV_BULKHEAD_CONCURRENCY` |

### Funções-chave

| Função | Confiança |
|--------|-----------|
| `SourceBulkhead.__init__(name, max_concurrent, timeout)` | 🟢 — cria semáforo + contadores |
| `SourceBulkhead.execute(coro, timeout)` → `T` | 🟢 — acquire semáforo (50% budget) → execute (50% budget) → release |
| `initialize_bulkheads()` → `dict` | 🟢 — cria e registra bulkheads para PNCP, PCP, ComprasGov |
| `get_bulkhead(source_name)` → `Optional[SourceBulkhead]` | 🟢 — lookup no registry |
| `get_all_bulkheads()` → `dict` | 🟢 — snapshot para health/debug endpoints |

### Algoritmos

1. **Timeout bipartido:** `total_timeout / 2` para acquire do semáforo, `total_timeout / 2` para execução. Se acquire excede, `BulkheadAcquireTimeoutError` é raised — caller marca UF como `skipped` (não `error`).
2. **Pool exhausted tracking:** quando `active >= max_concurrent`, incrementa `_exhausted_count` e emite `SOURCE_POOL_EXHAUSTED` Prometheus + log warning.
3. **Health status:** `healthy` (<80% utilization), `degraded` (>=80%), `exhausted` (full).

### Estruturas de dados

```python
class SourceBulkhead:
    _semaphore: asyncio.Semaphore
    _active: int       # current active operations
    _exhausted_count: int  # cumulative exhaustion events
```

### Constantes/Feature Flags

| Constante | Default | Config |
|-----------|---------|--------|
| `PNCP_BULKHEAD_CONCURRENCY` | 5 | `config.py` |
| `PCP_BULKHEAD_CONCURRENCY` | 3 | `config.py` |
| `COMPRASGOV_BULKHEAD_CONCURRENCY` | 3 | `config.py` |
| `PNCP_SOURCE_TIMEOUT` | 70 | `config.py` |
| `PCP_SOURCE_TIMEOUT` | 40 | `config.py` |
| `COMPRASGOV_SOURCE_TIMEOUT` | 40 | `config.py` |

### Métricas Prometheus

- `smartlic_bulkhead_acquire_timeout_total{source}` — acquire timeout
- `smartlic_source_active_requests{source}` — gauge, active operations
- `smartlic_source_pool_exhausted_total{source}` — pool exhaustion events
- `smartlic_source_semaphore_wait_seconds{source}` — histogram, wait duration >10ms

### Dependências

`asyncio`, `metrics` (Prometheus counters)

### Lacunas

- 🟢 Registry module-level permite teste via `reset_registry()` + `initialize_bulkheads()`
- 🟡 `_exhausted_count` é monotônico (nunca reseta) — pode mascarar melhora após deploy
- 🟡 SRE não tem alerta para `rate(smartlic_source_pool_exhausted_total[5m]) > 0` (TODO)

---

## Módulo 23 — `cnae-db-mapping` 🟢 (DOC-COVERAGE-002)

> DATA-CNAE-001: Sistema de mapeamento CNAE (Classificação Nacional de Atividades Econômicas) para setores SmartLic. Substitui hardcoded dict por DB table + admin CRUD + LRU cache.

**Caminho:** `backend/utils/cnae_mapping.py` (120 LOC), `backend/routes/admin_cnae_mapping.py` (150 LOC), migration `20260511120000_cnae_setor_mapping.sql`

**Propósito:** Permitir admins editarem mapeamentos CNAE→setor em runtime sem redeploy. Source-of-truth primário é `public.cnae_setor_mapping` (DB), com fallback hardcoded.

### Arquivos primários

| Arquivo | Papel |
|---------|-------|
| `backend/utils/cnae_mapping.py` | `lookup_cnae_setor()` — DB-first fallback dict + `invalidate_cnae_cache()` |
| `backend/routes/admin_cnae_mapping.py` | CRUD admin endpoints para `cnae_setor_mapping` |
| `supabase/migrations/20260511120000_cnae_setor_mapping.sql` | DDL + seed 59 entries |
| `backend/utils/cnae_mapping.py` (CNAE_TO_SETOR dict) | hardcoded fallback (59 entries, snapshot 2026-05-07) |

### Funções-chave

| Função | Confiança |
|--------|-----------|
| `lookup_cnae_setor(cnae_code)` → `Optional[str]` | 🟢 — DB first, fallback dict, LRU cached |
| `invalidate_cnae_cache()` | 🟢 — limpa `@functools.lru_cache` |
| `GET /v1/admin/cnae-mapping?setor=<id>` | 🟢 — list filtered by sector |
| `POST /v1/admin/cnae-mapping` | 🟢 — create entry + invalidate cache |
| `PATCH /v1/admin/cnae-mapping/{cnae_code}` | 🟢 — update entry + invalidate cache |
| `DELETE /v1/admin/cnae-mapping/{cnae_code}` | 🟢 — soft delete (notes='deleted') + invalidate cache |

### Algoritmos

1. **DB-first lookup:** `SELECT setor_id FROM cnae_setor_mapping WHERE cnae_code = $1` → cache resultado. Se DB unreachable ou cnae_code não encontrado, fallback hardcoded `CNAE_TO_SETOR` dict.
2. **Cache invalidation:** admin CRUD endpoints chamam `invalidate_cnae_cache()` (limpa `@functools.lru_cache`). Broadcast entre pods Railway não implementado (1 worker apenas).
3. **59 IBGE CNAE 2.3 subclasses mapeadas** (coverage ~4.5% de ~1300 ativas). Expansão via admin CRUD.

### Estruturas de dados

Tabela `public.cnae_setor_mapping`:
- `cnae_code TEXT PK` — prefixo IBGE 4 dígitos
- `setor_id TEXT NOT NULL` — SmartLic sector id
- `confidence NUMERIC(3,2) DEFAULT 1.00`
- `fallback_setor_id TEXT NULL`
- `notes TEXT NULL` (valor 'deleted' = soft delete)

### Constantes/Feature Flags

| Constante | Local | Notas |
|-----------|-------|-------|
| `CNAE_TO_SETOR` dict (59 entries) | `utils/cnae_mapping.py` | Fallback hardcoded, snapshot 2026-05-07 |

### Métricas Prometheus

Nenhuma específica. Erros capturados por logging.

### Dependências

`supabase_client` (SELECT + admin CRUD), `functools` (LRU cache)

### Lacunas

- 🟢 DB migration com seed de 59 entries
- 🟡 Cross-pod cache invalidation não implementado (1 worker, sem Redis pubsub)
- 🟡 Soft-delete via `notes='deleted'` é frágil — sem coluna `is_active`
- 🟡 Coverage ~4.5% IBGE CNAE 2.3 — expansão contínua necessária

---

## Módulo 24 — `webhook-abc` 🟢 (DOC-COVERAGE-002)

> REF-MON-002: ABC base + registry pattern para webhooks Stripe. Unifica 12 eventos Stripe sob um contrato comum com idempotência em dois layers (dispatcher + handler).

**Caminho:** `backend/webhooks/handlers/_base.py` (220 LOC), `backend/webhooks/handlers/_registry.py` (240 LOC), `backend/webhooks/stripe.py` (dispatcher)

**Propósito:** Framework reutilizável para handlers de webhook com template method (`handle()` → `process()`), idempotência in-handler, e registro via decorator `@webhook_handler`.

### Arquivos primários

| Arquivo | Papel |
|---------|-------|
| `backend/webhooks/handlers/_base.py` | `WebhookHandler` ABC + `HANDLERS_REGISTRY` + `@webhook_handler` decorator |
| `backend/webhooks/handlers/_registry.py` | Adapter classes: wraps free-function handlers em `WebhookHandler` subclasses |
| `backend/webhooks/stripe.py` | Dispatcher: signature → idempotency → routing via `HANDLERS_REGISTRY` |
| `backend/webhooks/handlers/checkout.py` | checkout.session.completed, async_payment_succeeded/failed |
| `backend/webhooks/handlers/subscription.py` | customer.subscription.created/updated/deleted/trial_will_end |
| `backend/webhooks/handlers/invoice.py` | invoice.payment_succeeded/failed/action_required |
| `backend/webhooks/handlers/founding.py` | founding lead lifecycle side-effects |
| `backend/webhooks/handlers/stripe_product_price.py` | product.updated, price.created/updated/deleted |
| `backend/webhooks/handlers/_shared.py` | shared utilities (resolve_user_id) |

### Funções-chave

| Função | Confiança |
|--------|-----------|
| `WebhookHandler.handle(sb, event)` | 🟢 — template method: claim idempotency → process() |
| `WebhookHandler.process(sb, event)` | 🟢 — abstract, implementado por cada handler |
| `WebhookHandler.idempotency_key(event)` | 🟢 — default: `event.id`, override para chave de negócio (e.g. `invoice.id`) |
| `webhook_handler(event_type)` decorator | 🟢 — class decorator: instancia + registra em HANDLERS_REGISTRY |
| `_resolve(attr_name)` | 🟢 — late-binding para patches de teste continuarem funcionando |
| Stripe dispatcher (`webhooks/stripe.py`) | 🟢 — signature HMAC → INSERT idempotency → dispatch via registry |

### Algoritmos

1. **Dispatcher layer (load-bearing):** `stripe_webhook_events` table com `id` = Stripe event ID. INSERT ON CONFLICT DO NOTHING — duplicatas Stripe são filtradas antes de qualquer handler rodar.
2. **Handler layer (best-effort):** `WebhookHandler._claim_idempotency()` faz upsert na mesma tabela com `ignore_duplicates=True`. Falha → proceed (fail-open). Útil para handlers invocados fora do dispatcher (reconciliation) ou handlers com idempotency key customizada.
3. **Template method:** `handle()` → claim idempotency → `process()` (business logic). Subclasses implementam apenas `process()`.
4. **Backward compatibility:** Adapter classes em `_registry.py` delegam via `_resolve()` às funções existentes em `webhooks.stripe`. Test patches de `webhooks.stripe._handle_*` continuam funcionando.
5. **16 eventos Stripe registrados:** checkout (4), subscription (4), invoice (3), product/price (4), payment_intent (1) — alguns compartilham handler.

### Estruturas de dados

```python
class WebhookHandler(ABC):
    event_type: ClassVar[str] = ""
    
    async def handle(self, sb, event) -> None:  # template method
    async def process(self, sb, event) -> None:  # abstract
    def idempotency_key(self, event) -> str:      # override point

HANDLERS_REGISTRY: dict[str, WebhookHandler] = {}
```

### Constantes/Feature Flags

| Constante | Valor | Local |
|-----------|-------|-------|
| `_HANDLER_IDEMPOTENCY_BUDGET_S` | 5.0s | `_base.py` |
| Dispatcher timeout | 30s | `stripe.py` |

### Métricas Prometheus

Nenhuma específica do ABC. Contadores de eventos no dispatcher legado.

### Dependências

`stripe` (SDK), `supabase_client` (idempotency + profiles sync), `asyncio`, `abc`, `pipeline.budget` (timeout)

### Lacunas

- 🟢 In-handler idempotency claim é fail-open — não substitui dispatcher layer
- 🟢 `_resolve()` late-binding permite monkey-patching em testes
- 🟡 Cross-pod idempotency não testada (Railway single worker)
- 🟡 Resend/trial-emails webhook tem HMAC verify separado (não usa este ABC)

---
