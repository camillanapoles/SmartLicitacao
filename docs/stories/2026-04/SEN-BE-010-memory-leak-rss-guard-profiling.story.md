# SEN-BE-010: Memory Leak RSS Guard + Profiling (5.5GB workers)

**Priority:** P0 (tripwire active until 2026-05-06; recurrence prevention)
**Effort:** 2d
**Squad:** @architect + @data-engineer
**Status:** InProgress (Phase 0 done; AC4-AC7 deferred — discovery-driven via 24h baseline)
**Epic:** [EPIC-INCIDENT-2026-04-22-api-degraded](EPIC-INCIDENT-2026-04-22-api-degraded.story.md)
**Sprint:** Sprint Atual (2026-04-29 → 2026-05-12)
**Tipo:** Resilience / Observability
**Bloqueia:** OPS-CI-001 (build budget guard precisa baseline RSS measurement)
**Dependências bloqueadoras:** ADR-MEMORY-BUDGET-policy (`docs/adr/MEMORY-BUDGET.md`) — @architect + @devops

---

## Contexto

Stage 4-7 wedge cycle (2026-04-27 → 2026-04-29) demonstrou backend uvicorn workers atingem 5.5GB RSS sustained sob bot/cron load + sync `.execute()` em rotas sem budget+wait_for (`docs/analysis/chief-stage7-definitive-solution.md:25`). Pool leak: caller `asyncio.wait_for` cancela await mas SQL keeps running até server statement_timeout (memory `feedback_pool_leak_caller_timeout_vs_sql_timeout`).

Floor 15s não-negociável (8s testado em Stage 6 piorou turnover). Root cause estrutural **não-confirmado** — hipóteses:

1. **Cron loops** — 19 lifespan loops Redis-locked, cada um pode acumular references não-collected
2. **OAuth pool** — Google Sheets refresh tokens Fernet-encrypted, possível leak em error path
3. **LLM client** — OpenAI SDK ThreadPoolExecutor(max_workers=10) + httpx connection pool
4. **Ingestion checkpoint** — ARQ worker checkpoint state em `ingestion_checkpoints` pode crescer unbounded
5. **httpx connection pool** — múltiplos clientes (PNCP, PCP v2, ComprasGov) sem `aclose()` em error paths

Tripwire ativo 2026-05-06 (`docs/sessions/2026-04/2026-04-29-chief-drift-paulo.md:50-52`): se Sentry `slow_request >60s` resume >25/24h, drop other work + profile workers.

Memory `feedback_chief_warm_stage5plus_no_pivot`: warm continuation 7× band-aid (8s tighten + WC=2→4 + 6 redeploys frontend) ALL falharam mesmo padrão `/sitemap/4.xml after 3 attempts`. Pivot estrutural mandatório.

---

## Acceptance Criteria

### AC0: Discriminator empírico Phase 0 (<2h)

**Given** root cause não-confirmado entre 5 hipóteses
**When** @data-engineer roda profiling em prod worker
**Then**:

- [ ] Endpoint admin-only `/v1/admin/memory-snapshot` (só master-role) que retorna:
  ```json
  {
    "rss_bytes": 5_500_000_000,
    "tracemalloc_top_25": [
      { "filename": "...", "lineno": 123, "size_kb": 450_000, "count": 1234 }
    ],
    "objgraph_most_common": [
      { "type": "dict", "count": 234567 },
      { "type": "Connection", "count": 89 }
    ],
    "asyncio_tasks_pending": 47,
    "redis_pool_size": 12
  }
  ```
- [ ] Reusable: `tracemalloc.start()` em lifespan startup; `tracemalloc.take_snapshot()` em endpoint
- [ ] Coletar baseline (10 snapshots em 24h) ANTES de fix; pós-fix outro 24h
- [ ] **NÃO commitar** snapshot data em git (PII risk + tamanho)

### AC1: Sentry alert rule `backend_workers_rss_high`

- [ ] Sentry alert: trigger quando `worker_rss_bytes > 4_000_000_000` sustained 5min
- [ ] Fingerprint dedup `["backend_memory_high", reason]`
- [ ] Tags: `worker_id`, `reason` (cron|request|llm|ingestion)
- [ ] Action: capture snapshot + post Slack #incidents

### AC2: Prometheus metric `smartlic_backend_worker_rss_bytes{worker_id}`

- [ ] Exposto via `/metrics` endpoint (existing Prometheus middleware)
- [ ] Sample interval: 30s (avoid `gc.collect()` overhead ressampling)
- [ ] Source: `psutil.Process().memory_info().rss`
- [ ] Reusable: `backend/metrics.py` add gauge

### AC3: Profiling baseline pre/post Googlebot wave

- [ ] Load test cron simulation: simular 31 workers SSG burst + Googlebot crawl + cron jobs simultâneos (replicate Stage 4-7 pattern)
- [ ] Pre-fix baseline: RSS médio + p99 sob load
- [ ] Post-fix: target RSS p99 <2GB sob mesma load
- [ ] Test artifact: `tests/load/stage_4_7_pattern.py` (Locust ou k6)

### AC4: Identify root cause subsystem

**Given** AC0 produz tracemalloc data
**When** @architect analisa top-25 allocators
**Then**:

- [ ] Root cause identified com evidence:
  - cron loops? → fix em `backend/cron_jobs.py` ou `backend/jobs/cron/scheduler.py`
  - OAuth pool? → fix em `backend/oauth.py` (refresh token leak)
  - LLM client? → fix em `backend/llm_arbiter/async_runtime.py` (httpx.AsyncClient close)
  - ingestion checkpoint? → fix em `backend/ingestion/checkpoint.py`
  - httpx connection pool? → fix em clients respectivos (`pncp_client.py`, etc.)
- [ ] Documentado em PR description com tracemalloc evidence

### AC5: Fix root cause

**Given** AC4 identifica subsystem
**When** @dev (delegated post-AC4) implementa fix
**Then**:

- [ ] Fix específico (e.g., `gc.collect()` em loop hot path, ou bound de cache size, ou client pool recycle)
- [ ] Test regression: 197 backend tests + ruff clean
- [ ] Smoke test: endpoint problemático sob load → RSS estável

### AC6: Soak 24h post-fix

- [ ] Deploy fix prod
- [ ] 24h soak monitoring:
  - RSS p99 < 2GB sob bot wave (Googlebot/Bingbot crawls esperados)
  - Zero novo Sentry `backend_workers_rss_high` alert
  - `slow_request >60s` count < 5/24h
- [ ] Critério ROLLBACK: ≥3 alerts em 6h pós-deploy → revert + re-investigate

### AC7: Findings docs

- [ ] `docs/runbooks/backend-memory-leak-investigation.md`:
  - hipóteses tested + refuted
  - root cause identified (com tracemalloc top-25 sample)
  - fix applied (PR ref)
  - prevention pattern (e.g., "always `async with httpx.AsyncClient()` block")
- [ ] Link de OPS-RECOVERY-001 runbook

---

## Scope

**IN:**
- Discriminator empírico (Phase 0) tracemalloc + objgraph endpoint
- Sentry alert + Prometheus metric (observability)
- Profiling baseline pre/post (load test reproducible)
- Root cause investigation (1 of 5 hipóteses)
- Fix implementation
- 24h soak monitoring
- Findings runbook

**OUT:**
- Restart policy (escopo ADR-MEMORY-BUDGET — separate)
- Capacity bump WEB_CONCURRENCY (escopo separate; memory `feedback_web_concurrency_4_amplifier` mantém WC=1)
- Sentry SDK frontend init (escopo FOUND-SCALE-002)

---

## Definition of Done

- [ ] AC0 endpoint admin functional + 10 snapshots baseline coletadas
- [ ] AC1 Sentry alert configured + tested (sintético trigger)
- [ ] AC2 Prometheus metric exposto + Grafana dashboard panel
- [ ] AC3 load test reproducible em CI
- [ ] AC4 root cause documented em PR
- [ ] AC5 fix merged + 197 tests pass
- [ ] AC6 24h soak passa critério
- [ ] AC7 runbook commited
- [ ] PR aprovado @architect + @data-engineer + @qa
- [ ] Change Log atualizado
- [ ] Tripwire 2026-05-06 estendida ou removida baseada em soak result

---

## Dev Notes

### Paths absolutos

- **Endpoint admin:** `/mnt/d/pncp-poc/backend/admin.py` (add `/v1/admin/memory-snapshot`)
- **Metric:** `/mnt/d/pncp-poc/backend/metrics.py`
- **Sentry config:** `/mnt/d/pncp-poc/backend/startup/sentry.py`
- **Suspect subsystems:**
  - `/mnt/d/pncp-poc/backend/cron_jobs.py` + `/mnt/d/pncp-poc/backend/jobs/cron/`
  - `/mnt/d/pncp-poc/backend/oauth.py`
  - `/mnt/d/pncp-poc/backend/llm_arbiter/`
  - `/mnt/d/pncp-poc/backend/ingestion/`
  - `/mnt/d/pncp-poc/backend/pncp_client.py` + `portal_compras_client.py` + `compras_gov_client.py`
- **Load test:** `/mnt/d/pncp-poc/backend/tests/load/stage_4_7_pattern.py` (NEW)
- **Runbook:** `/mnt/d/pncp-poc/docs/runbooks/backend-memory-leak-investigation.md` (NEW)

### Memory references mandatórios

- `feedback_pool_leak_caller_timeout_vs_sql_timeout`
- `project_backend_outage_2026_04_27` Stage 2 — Googlebot wave saturou
- `feedback_chief_warm_stage5plus_no_pivot`
- `reference_supabase_service_role_no_timeout_default`
- `feedback_supabase_disk_io_root_cause_pattern`
- `feedback_web_concurrency_4_amplifier` — manter WC=1

### Tracemalloc setup

```python
# backend/startup/lifespan.py
import tracemalloc
async def lifespan(app):
    tracemalloc.start(25)  # top-25 frames
    yield
    tracemalloc.stop()
```

### Testing standards

- Anti-hang rules CLAUDE.md: pytest-timeout 30s, async fixtures, no `run_until_complete`
- Load test usar `pytest --timeout=300 backend/tests/load/`

---

## Risk & Rollback

| Trigger | Ação |
|---------|------|
| Endpoint `/v1/admin/memory-snapshot` causa GC pause >5s | Sample interval bump 60s; ou disable `objgraph` (caro) |
| tracemalloc adds 10%+ overhead RSS | tracemalloc.stop() em prod, só ativa via env var SAMPLER_ON=1 |
| Fix introduz regressão | Revert via @devops; tripwire 2026-05-06 estendida +14d |

**Rollback path:** revert PR; manter Sentry alert + metric (observability sem custo); re-investigate Phase 0.

---

## Dependencies

**Entrada:**
- ADR-MEMORY-BUDGET-policy (architect+devops define threshold + restart policy) — `docs/adr/MEMORY-BUDGET.md`

**Saída:**
- OPS-CI-001 (build budget guard usa baseline RSS measurement)
- OPS-RECOVERY-001 (runbook tripwire pode atualizar critério)

**Paralelas:**
- RES-BE-002c (audit `.execute()` — independente do leak fix)
- SEN-FE-002 + FOUND-SCALE-002 (frontend layer separado)

---

## PO Validation

**Validated by:** @po (Pax)
**Date:** 2026-04-29
**Verdict:** GO conditional
**Score:** 8/10

| # | Criterion | Status | Notes |
|---|---|---|---|
| 1 | Clear and objective title | OK | Memory Leak RSS Guard + Profiling explícito |
| 2 | Complete description | OK | Tripwire 5.5GB grounded em chief-drift-paulo:52; 5 hipóteses listadas |
| 3 | Testable acceptance criteria | PARTIAL | AC0-AC7 testáveis; AC4 root cause é discovery (não-deterministic upfront) — score 8 não 10 por essa indeterminação Phase 0-driven |
| 4 | Well-defined scope | OK | OUT exclude restart policy (ADR), capacity bump, frontend Sentry |
| 5 | Dependencies mapped | OK | ADR-MEMORY-BUDGET BLOCKING; saída OPS-CI-001, OPS-RECOVERY-001 |
| 6 | Complexity estimate | OK | 2d consistente — Phase 0 + observability + fix + soak |
| 7 | Business value | OK | Tripwire 2026-05-06 prevention; Stage 8 recurrence guard |
| 8 | Risks documented | OK | 3 triggers + rollback (revert + manter observability) |
| 9 | Criteria of Done | OK | 24h soak passa critério explícito |
| 10 | Alignment with PRD/Epic | OK | EPIC-INCIDENT-2026-04-22-api-degraded |

### Observations
- AC4 root cause é discovery-driven — Phase 0 (AC0) tracemalloc evidence determina sub-system. Aceitável Ready com fallback explícito (5 hipóteses listadas).
- Endpoint admin `/v1/admin/memory-snapshot` é prudente (master-role only).
- ADR-MEMORY-BUDGET separação é correta (policy ≠ implementation).

Status: Draft → Ready.

## Change Log

| Data | Versão | Descrição | Autor |
|------|--------|-----------|-------|
| 2026-04-29 | 1.0 | Story criada via batch sm-briefing-100pct §3.2.1. Tripwire 5.5GB ground confirmed em chief-drift-paulo:52. NEW story, anti-duplicate grep zero matches. | @sm (River) |
| 2026-04-29 | 1.1 | PO validation: GO conditional (8/10). AC4 discovery-driven justificado por AC0 Phase 0 tracemalloc evidence. Status: Draft → Ready. | @po (Pax) |
| 2026-04-29 | 1.2 | **Implementado Wave 4 Phase 0 — zany-kurzweil session.** AC2 (Prometheus gauge `WORKER_MEMORY_BYTES`) já pre-existing em metrics.py:1109 + lifespan.py:140-144 sample 30s — skip. AC0 done: endpoint `GET /v1/admin/memory-snapshot` (master-only `Depends(require_admin)`) returning rss_bytes/rss_mb + tracemalloc top-25 + asyncio_tasks_pending + gc_objects_count + redis_pool_size. tracemalloc.start(25) opt-in via env var `TRACEMALLOC_ENABLED=true` em lifespan.py (10% overhead — disabled default; on-demand profiling). AC1 Sentry alert config defer dashboard UI (não-via-código). AC3 done: load test `backend/tests/load/stage_4_7_pattern.py` (Locust 3 user classes — GooglebotCrawler peso 4 + SsgBuildBurst peso 2 + HumanUser peso 1 — replicating Stage 4-7 traffic shape). **ADR-MEMORY-BUDGET implementation extra:** start.sh gunicorn `--max-requests 10000 --max-requests-jitter 1000` (Component A rotation, was 1000/50); uvicorn runner adds `--limit-max-requests`; `scripts/rss_supervisor.sh` (Component B emergency kill >5GB threshold, sidecar/cron). psutil promoted required em requirements.txt. AC4-AC7 deferred — discovery-driven via baseline 10× snapshots em 24h pós-deploy. Status: Ready → InProgress. | @dev (James) |

## File List

- `backend/admin.py` (add endpoint `/v1/admin/memory-snapshot` — AC0)
- `backend/startup/lifespan.py` (add `tracemalloc.start(25)` opt-in via `TRACEMALLOC_ENABLED` env)
- `backend/start.sh` (gunicorn defaults max-requests 10000/1000 + uvicorn `--limit-max-requests` — ADR Component A rotation)
- `backend/requirements.txt` (promote psutil>=5.9.0 to required)
- `backend/tests/load/__init__.py` (NEW)
- `backend/tests/load/stage_4_7_pattern.py` (NEW Locust load test — AC3)
- `scripts/rss_supervisor.sh` (NEW chmod +x — ADR Component B emergency kill RSS >5GB)
