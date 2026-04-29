# Story: Backend Monolith Decomposition (5 modules)

**Story ID:** DEBT-v3-004
**Epic:** DEBT-v3
**Phase:** 2 (Foundation)
**Priority:** P1
**Estimated Hours:** 120h
**Agent:** @dev
**Status:** PLANNED

---

## Objetivo

Decompor os 5 maiores monolitos do backend para que nenhum modulo exceda 500 LOC. Este e o maior investimento do epic e o de maior risco de regressao (100+ test files afetados). O filter package (6,422 LOC) e o mais critico — contem a logica de negocios central de classificacao.

---

## Debitos Cobertos

| ID | Debt | Severity | Hours |
|----|------|----------|-------|
| SYS-001 | Filter package 6,422 LOC — `filter/pipeline.py` (1,883), `filter/keywords.py` (1,170). Target: <500 LOC/modulo. | CRITICAL | 40h + 10h overhead |
| SYS-003 | `cron_jobs.py` 2,251 LOC — cache cleanup, PNCP canary, session cleanup, cache warming, trial emails em um arquivo | HIGH | 16h |
| SYS-004 | `job_queue.py` 2,229 LOC — ARQ config, Redis pool, job definitions misturados | HIGH | 16h |
| SYS-005 | Cache package 2,379 LOC em 14 files + root shims — SWR interleaved com persistencia | HIGH | 24h |
| SYS-002 | SIGSEGV single-process constraint — C extensions (cryptography, chardet, hiredis) causam SIGSEGV intermitente | CRITICAL | 24h |

---

## Acceptance Criteria

### SYS-001: Filter Package Decomposition (50h)
- [ ] AC1: `filter/pipeline.py` decomposto em modulos <500 LOC: `pipeline_stages.py`, `pipeline_executor.py`, `pipeline_config.py`
- [ ] AC2: `filter/keywords.py` decomposto em: `keyword_matcher.py`, `density_scorer.py`, `synonym_resolver.py`
- [ ] AC3: `filter/__init__.py` re-exports mantidos para backward compatibility (zero breaking imports)
- [ ] AC4: Todos os 15-20 `test_filter*.py` passam sem modificacao de assert (podem precisar de import path updates)
- [ ] AC5: Todos os 10+ `test_search*.py` e 5+ `test_classification*.py` passam
- [ ] AC6: `wc -l` de cada modulo no filter/ confirma <500 LOC

### SYS-003: Cron Jobs Decomposition (16h)
- [ ] AC7: `cron_jobs.py` decomposto em `jobs/cron/` sub-package: `cache_cleanup.py`, `pncp_canary.py`, `session_cleanup.py`, `cache_warming.py`, `trial_emails.py`
- [ ] AC8: `jobs/cron/__init__.py` re-exports ARQ cron settings
- [ ] AC9: Todos `test_cron*.py` passam (ARQ mock pattern via conftest atualizado se paths mudam)

### SYS-004: Job Queue Decomposition (16h)
- [ ] AC10: `job_queue.py` decomposto em: `jobs/config.py` (ARQ settings), `jobs/pool.py` (Redis pool), `jobs/definitions.py` (job functions)
- [ ] AC11: WorkerSettings exportado de `jobs/__init__.py`
- [ ] AC12: `test_job*.py` e `test_arq*.py` passam

### SYS-005: Cache Consolidation (24h)
- [ ] AC13: SWR logic separada de persistence logic: `cache/swr.py`, `cache/persistence.py`, `cache/memory.py`
- [ ] AC14: Root shims (`search_cache.py` 118 LOC re-export) removidos — imports diretos para `cache/` package
- [ ] AC15: Mock pattern `supabase_client.get_supabase` continua funcionando para todos cache tests
- [ ] AC16: L1 (InMemory) e L2 (Supabase) claramente separados em modulos distintos

### SYS-002: SIGSEGV Investigation (24h)
- [ ] AC17: Benchmark de capacidade documentado: max concurrent searches, max memory, SIGSEGV reproduction conditions
- [ ] AC18: Teste com cryptography >= 46.x ou 47.x (se disponivel) documentado
- [ ] AC19: Arquitetura Redis para coordenacao multi-processo desenhada (ADR document)
- [ ] AC20: Trigger conditions para upgrade de prioridade documentados: >200 daily searches OR >10 concurrent

---

## Technical Notes

**Order of execution:**
1. SYS-014 (DEBT-v3-002) MUST be done first — safety net for refactoring
2. SYS-001 (filter) — highest risk, do first while context is fresh
3. SYS-003 + SYS-004 — can be parallelized, similar patterns
4. SYS-005 (cache) — do after cron/jobs since some cache warming logic moves
5. SYS-002 (SIGSEGV) — investigation can happen in parallel

**Critical: Test maintenance budget**
- Budget 20-30% overhead for test path updates
- Use `__init__.py` re-exports during transition (remove in DEBT-v3-008)
- Run `python scripts/run_tests_safe.py --parallel 4` after each decomposition
- Known pollution patterns: `sys.modules` injection, `importlib.reload`, global singleton leakage

**Filter decomposition strategy:**
- Start with `filter/pipeline.py` (1,883 LOC) — extract stage functions into `pipeline_stages.py`
- Then `filter/keywords.py` (1,170 LOC) — extract density scoring into `density_scorer.py`
- Keep `filter_stats.py`, `term_parser.py`, `synonyms.py`, `status_inference.py` as-is (already <500 LOC)
- Use `SimpleNamespace` not `MagicMock` for ConsolidationResult in tests

**Cache consolidation strategy:**
- Current: 14 files + root shims = complex dependency graph
- Target: `cache/` package with clear layers (memory, persistence, swr, admin)
- Mock pattern MUST stay: patch `supabase_client.get_supabase` (not `search_cache.get_supabase`)

---

## Tests Required

- [ ] Full backend suite: `python scripts/run_tests_safe.py --parallel 4` (7,656+ pass, 0 new failures)
- [ ] LOC audit: `wc -l` for all decomposed modules confirms <500 LOC target
- [ ] Import path audit: `grep -r "from filter." backend/` confirms no broken imports
- [ ] Import path audit: `grep -r "from cron_jobs" backend/` confirms no broken imports
- [ ] Import path audit: `grep -r "from job_queue" backend/` confirms no broken imports
- [ ] Import path audit: `grep -r "from search_cache" backend/` confirms no broken imports

---

## Dependencies

- **REQUIRES:** DEBT-v3-002 (SYS-014 — LLM cost monitoring as safety net)
- **ENABLES:** DEBT-v3-006 (SYS-009 root filter cleanup, SYS-019 root cache shim removal)

---

## Definition of Done

- [ ] All ACs pass
- [ ] Zero test regressions
- [ ] No module >500 LOC in decomposed packages
- [ ] `__init__.py` re-exports in place for backward compatibility
- [ ] SIGSEGV benchmark and architecture ADR documented
- [ ] Code reviewed
