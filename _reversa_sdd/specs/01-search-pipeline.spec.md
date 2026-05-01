# Spec: Search Pipeline

> Spec executável (SDD) gerada pelo **Reversa Writer** em 2026-04-27
> Confiança: 🟢 CONFIRMADO

## Component
- **ID**: `search-pipeline`
- **Path**: `backend/search_pipeline.py`, `backend/pipeline/`, `backend/consolidation/`, `backend/routes/search/`
- **Owner**: Backend Search team

## Purpose

Orquestrar busca multi-fonte de licitações públicas com classificação IA, dedup, viability scoring, cache SWR e máquina de estados explícita. Source: principalmente DataLake (Layer 1 Supabase) com fallback para live APIs (PNCP, PCP v2, ComprasGov v3).

## Stages (7-stage state machine)

| # | Stage | Function | State antes → depois | SLA |
|---|-------|----------|---------------------|-----|
| 1 | Validate | `stage_validate` | CREATED → VALIDATING | <100ms |
| 2 | Prepare | `stage_prepare` | VALIDATING → PREPARING | <50ms (sectors lookup) |
| 3 | Execute | `stage_execute` | PREPARING → EXECUTING | <70s (datalake) ou <90s (live fallback) |
| 4 | Filter | `stage_filter` | EXECUTING → FILTERING | <2s |
| 5 | Enrich | `stage_enrich` | FILTERING → ENRICHING | <500ms (viability) |
| 6 | Generate | `stage_generate` | ENRICHING → GENERATING | <30s (LLM) ou skip se simplified |
| 7 | Persist | `stage_persist` | GENERATING → PERSISTING → COMPLETED | <500ms |

## Invariants

1. **State machine determinística** — transições inválidas log CRITICAL e returnam False; estados terminais COMPLETED/FAILED/RATE_LIMITED/TIMED_OUT
2. **Time budget waterfall** — `pipeline(100s) > consolidation(90s) > per_source(70s) > per_uf(25s) > httpx(10c+15r)` (assertado em `tests/test_timeout_invariants.py`)
3. **`_check_time_budget`** — se elapsed > 90s → `is_simplified=True`, skip LLM, emit `llm_skipped reason=timeout`
4. **State persistence fire-and-forget** — `asyncio.create_task` em `search_state_transitions` (append-only) + `search_sessions` (mutável); falha de DB NÃO interrompe pipeline
5. **DataLake-first** — `DATALAKE_QUERY_ENABLED=true` (default): query `search_datalake` RPC; fallback para live só se 0 results

## Functional Requirements

- **FR-1**: Acceptar `BuscaRequest` (Pydantic v2 validated)
- **FR-2**: Verificar quota atomic via `check_and_increment_quota_atomic` — bypass para admin/master
- **FR-3**: Resolver sector keywords + custom_terms + active_exclusions
- **FR-4**: Cache lookup L1+L2 — fresh serve direto; stale serve + SWR; expired skip
- **FR-5**: Multi-source fetch com priority dedup (PNCP=1 > PCP=2 > ComprasGov=3)
- **FR-6**: Filter pipeline fail-fast: UF → value → keyword density → LLM zero-match → status/date
- **FR-7**: Viability scoring 4-fator post-filter
- **FR-8**: LLM summary via ARQ background job (se queue available); fallback inline se worker offline
- **FR-9**: Excel generation via ARQ background; presigned URL Supabase Storage
- **FR-10**: Persist `search_sessions` + `search_state_transitions`
- **FR-11**: SSE progress events: `prepare_done`, `uf_progress`, `filter_done`, `llm_ready`, `excel_ready`, `complete`, `error`, `llm_skipped`
- **FR-12**: Async POST: 202 Accepted in <2s + offload via `search_job` ARQ; sync mode se `SEARCH_ASYNC_ENABLED=false`

## Non-Functional Requirements

- **NFR-1**: p95 response time <80s (datalake), <110s (live fallback)
- **NFR-2**: precision ≥85%, recall ≥70% (15 samples/sector benchmark)
- **NFR-3**: cache hit rate >40% steady-state
- **NFR-4**: tracing OTel cada stage (root span + child per stage)
- **NFR-5**: graceful degradation — circuit breaker open em todas sources → 200 partial com `response_state=degraded`

## Constraints

- **CON-1**: PNCP `tamanhoPagina ≤ 50` (Feb 2026 breaking change; canary monitor STORY-4.5)
- **CON-2**: Railway hard timeout ~120s — invariante budget waterfall
- **CON-3**: Cache populated on-demand only (warming deprecated 2026-04-18)
- **CON-4**: `LLM_FALLBACK_PENDING_ENABLED=true` em prod → gray zone + zero-match fail vai para PENDING_REVIEW (não REJECT)

## Acceptance Criteria

- AC-1: POST /buscar com `ufs=["SP"], data_inicial=today-10d, data_final=today` retorna 202 + search_id em <2s
- AC-2: SSE `/buscar-progress/{search_id}` emite ≥5 events incluindo final `complete` ou `error`
- AC-3: Cache hit retorna em <500ms com `cache_status=fresh|stale`
- AC-4: 0 results triggers relaxation cascade até level 3
- AC-5: Time budget exceeded retorna 200 com `is_simplified=true` + LLM fallback summary
- AC-6: Estado terminal sempre alcançado (nunca pendurar em estado intermediário)
- AC-7: Cancel via `POST /search/{id}/cancel` aborta worker em até 15s

## Errors

| Code | HTTP | Trigger | Resposta |
|------|------|---------|----------|
| `quota_exceeded` | 429 | quota mensal hit | upgrade CTA |
| `rate_limited` | 429 | concurrent searches > limit | retry after 60s |
| `trial_expired` | 403 | trial expired | upgrade CTA |
| `pipeline_not_available` | 403 | capability missing | upgrade CTA |
| `state_invalid_transition` | 500 | bug | sentry + alert |
| `timeout_exceeded` | 503 | budget waterfall | retry suggested |

## Code traceability

- `backend/search_pipeline.py:68` — `SearchPipeline.run`
- `backend/search_state_manager.py:70` — `transition_to`
- `backend/models/search_state.py` — `SearchState`, `VALID_TRANSITIONS`, `STAGE_TO_STATE`
- `backend/pipeline/budget.py:_run_with_budget` — TimeoutError increment metric
- `backend/pipeline/cache_manager.py` — L1/L2 + SWR
- `backend/consolidation/dedup.py:76` — `DeduplicationEngine.run` 5 layers
- `backend/routes/search/__init__.py` — POST /buscar router
- `backend/routes/search_state.py` — 8 endpoints status/timeline/results/retry/cancel
- `backend/jobs/queue/search.py:search_job` — ARQ offload
- `backend/tests/test_timeout_invariants.py` — invariant assertion

## Dependencies

- Pydantic v2: `BuscaRequest`, `BuscaResponse`, `LicitacaoItem`, `ResumoLicitacoes`
- DataLake: `search_datalake` RPC, `pncp_raw_bids`
- Cache: `redis_pool`, `search_results_cache`
- LLM: `llm_arbiter/` GPT-4.1-nano
- Auth: `auth.require_auth`
- Quota: `quota/quota_atomic`
- ARQ: `jobs/queue/search.search_job`
