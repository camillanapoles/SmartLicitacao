# Story: Backend Optimization + Feature Flag Governance + DB Opportunistic

**Story ID:** DEBT-v3-006
**Epic:** DEBT-v3
**Phase:** 3 (Optimization)
**Priority:** P2
**Estimated Hours:** 87h
**Agent:** @dev (backend), @data-engineer (DB items)
**Status:** PLANNED

---

## Objetivo

Completar a decomposicao dos modulos de media complexidade do backend (consolidation, routes, SSE, PNCP client), unificar feature flag governance entre backend e frontend, resolver debitos oportunisticos de database, e realizar avaliacao de escalabilidade. Este e o sprint de otimizacao que solidifica a arquitetura pos-decomposicao da Phase 2.

---

## Debitos Cobertos

### Backend Module Decomposition (~56h)

| ID | Debt | Severity | Hours |
|----|------|----------|-------|
| SYS-006 | `consolidation.py` 1,394 LOC — multi-source orchestration, dedup, partial results, degradation | HIGH | 16h |
| SYS-007 | Sync + async PNCP client coexistence — circuit breaker e retry duplicados | HIGH | 12h |
| SYS-012 | Route files 11,138 LOC / 37 modules — `search.py` (784), `user.py` (698) | MEDIUM | 16h |
| SYS-013 | SSE reliability fragility — `bodyTimeout(0)` desabilita timeout protection | MEDIUM | 12h |

### Backend Cleanup (~20h)

| ID | Debt | Severity | Hours |
|----|------|----------|-------|
| SYS-008 | Feature flag sprawl: 30+ flags sem governance — sem lifecycle, sem expiration | HIGH | 8h |
| SYS-009 | Root `filter_*.py` duplicacao com `filter/` package | MEDIUM | 8h |
| SYS-010 | LLM timeout config espalhado por multiplos modulos | MEDIUM | 4h |

### Feature Flag Governance Cross-Cutting (~5h)

| ID | Debt | Severity | Hours |
|----|------|----------|-------|
| CROSS-003 | Feature flag governance ausente — backend 30+ flags + frontend hardcoded gates | MEDIUM | 2h (coord) |
| CROSS-005 | LLM dependency spans layers — config scattered, cost untracked | MEDIUM | 2h (coord) |
| SYS-011 | Schemas scattered entre `schemas/` dir e root | MEDIUM | 4h |

### Database Opportunistic (~5h)

| ID | Debt | Severity | Hours |
|----|------|----------|-------|
| DB-004 | `classification_feedback.user_id` referencia `auth.users` — pattern antigo reintroduzido | MEDIUM | 2h |
| DB-006 | `ingestion_checkpoints.crawl_batch_id` sem FK enforced | MEDIUM | 2h |
| DB-021 | `check_and_increment_quota()` e `increment_quota_atomic()` sem SECURITY DEFINER search_path | MEDIUM | 1h |

### Scaling Architecture (~8h)

| ID | Debt | Severity | Hours |
|----|------|----------|-------|
| CROSS-006 | Scaling constraint — SIGSEGV forca single-process; L1 cache, SSE queues, progress tracker assumem um processo | CRITICAL | 8h (eval) |

---

## Acceptance Criteria

### Backend Decomposition
- [ ] AC1: `consolidation.py` decomposto: `consolidation/orchestrator.py`, `consolidation/dedup.py`, `consolidation/partial_results.py`, `consolidation/degradation.py` — cada <400 LOC
- [ ] AC2: Sync PNCP client removido — apenas async client ativo. `asyncio.to_thread()` wrapper removido.
- [ ] AC3: Route files maiores (search.py, user.py) decompostos em sub-modulos ou helper files
- [ ] AC4: SSE reliability melhorada: configurable timeout (nao hardcoded `bodyTimeout(0)`), Railway idle handling documentado
- [ ] AC5: `test_consolidation*.py` passam (usar `SimpleNamespace` nao `MagicMock` para ConsolidationResult)

### Feature Flag Governance
- [ ] AC6: Inventario de todos 30+ feature flags documentado com: name, purpose, introduced_date, deprecated_since (se aplicavel)
- [ ] AC7: Campo `deprecated_since` adicionado ao config para flags marcadas para remocao
- [ ] AC8: Flags sem referencia ativa no code removidas
- [ ] AC9: Target: <20 flags ativas
- [ ] AC10: Frontend `useFeatureFlags` unificado com backend flag service

### Cleanup
- [ ] AC11: Root `filter_*.py` files removidos — todos imports apontam para `filter/` package
- [ ] AC12: LLM timeouts centralizados em `config.py` (single source: `LLM_TIMEOUT_SECONDS`)
- [ ] AC13: Schemas consolidados em `schemas/` directory — nenhum schema file na root

### Database
- [ ] AC14: `classification_feedback.user_id` FK atualizado para `profiles.id` (pattern padrao)
- [ ] AC15: `ingestion_checkpoints.crawl_batch_id` FK adicionado com `NOT VALID` + `VALIDATE` + `ON DELETE CASCADE`
- [ ] AC16: `check_and_increment_quota()` e `increment_quota_atomic()` com `SET search_path = public`

### Scaling Architecture
- [ ] AC17: Documento de arquitetura para multi-processo: Redis coordination para L1 cache, SSE queues, progress tracker
- [ ] AC18: Trigger conditions documentados: upgrade para P1 quando >200 daily searches OR >10 concurrent
- [ ] AC19: Custo estimado de implementacao multi-processo documentado

---

## Technical Notes

**SYS-006 (consolidation) decomposition:**
- Extract dedup logic into `consolidation/dedup.py` (priority-based dedup PNCP=1 > PCP=2)
- Extract partial results handling into `consolidation/partial_results.py`
- Extract degradation logic into `consolidation/degradation.py`
- Orchestrator remains as thin coordinator

**SYS-007 (PNCP client unification):**
- Remove legacy sync `PNCPClient` entirely
- Verify no code path uses sync client (grep for `PNCPClient` vs `AsyncPNCPClient`)
- Circuit breaker and retry logic exist only in async client

**SYS-013 (SSE reliability):**
- Current: `bodyTimeout(0)` in frontend proxy disables all timeout protection
- Better: configurable timeout (e.g., 180s) with proper cleanup on timeout
- Document Railway idle timeout behavior and mitigation
- Consider SSE reconnection protocol for dropped connections

**Feature flag governance:**
- Run `grep -r "config\.\|os.environ\|getenv" backend/ | grep -i "enabled\|flag\|feature"` to inventory
- Create `docs/feature-flags.md` with registry
- Remove flags that have been "always on" for >2 sprints

---

## Tests Required

- [ ] Full backend suite: `python scripts/run_tests_safe.py --parallel 4`
- [ ] Frontend feature flag tests updated for unified service
- [ ] Consolidation tests with `SimpleNamespace` (not `MagicMock`)
- [ ] Import audit: zero references to removed root files
- [ ] Flag inventory verified: <20 active

---

## Dependencies

- **REQUIRES:** DEBT-v3-004 (SYS-001 enables SYS-009 cleanup; SYS-005 enables cache-related cleanup)
- **ENABLES:** Clean architecture for future feature development

---

## Definition of Done

- [ ] All ACs pass
- [ ] Backend tests pass (zero regressions)
- [ ] Frontend tests pass (zero regressions)
- [ ] No backend module >500 LOC in decomposed areas
- [ ] Feature flag inventory documented
- [ ] Scaling architecture ADR documented
- [ ] Code reviewed
