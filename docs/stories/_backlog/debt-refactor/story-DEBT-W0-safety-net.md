# Story DEBT-W0: Safety Net -- Testes para Modulos Descobertos

**Story ID:** DEBT-W0
**Epic:** DEBT-EPIC-001
**Wave:** 0
**Priority:** HIGH
**Effort:** ~24h
**Agents:** @qa (Quinn) + @dev (Devin)

---

## Descricao

Write comprehensive tests for 6 production-critical backend modules that currently have ZERO test coverage. This is a hard prerequisite before any Wave 3 restructuring -- without these tests, refactoring monolithic files (filter.py, cron_jobs.py, search_cache.py, webhooks/stripe.py) would be flying blind with no safety net to detect regressions.

This story is **purely additive** -- no production code changes, only new test files. It can run in parallel with Wave 1.

## Debitos Incluidos

| ID | Debito | Severidade | Horas |
|----|--------|-----------|-------|
| QA-DEBT-001 | `cron_jobs.py` (2,039 LOC) has ZERO test files | HIGH | 6 |
| QA-DEBT-002 | `supabase_client.py` (537 LOC, circuit breaker) has ZERO test files | HIGH | 4 |
| QA-DEBT-005 | 11 `filter_*.py` submodules have no individual test files | MEDIUM | 6 |
| QA-DEBT-006 | Webhook handler coverage incomplete -- not all 10+ event types tested | MEDIUM | 4 |
| QA-DEBT-003 | `search_state_manager.py` (544 LOC) has ZERO test files | MEDIUM | 3 |
| QA-DEBT-004 | `worker_lifecycle.py` (125 LOC) has ZERO test files | MEDIUM | 1 |

## Tasks

### QA-DEBT-001: cron_jobs.py tests (~6h)
- [ ] Create `backend/tests/test_cron_jobs.py`
- [ ] Test all 15+ scheduled task functions (each with success + failure path)
- [ ] Mock Supabase and Redis dependencies
- [ ] Verify cron schedule registration (functions are callable, correct async signatures)
- [ ] Test error handling -- each task must not crash the scheduler on failure

### QA-DEBT-002: supabase_client.py + SupabaseCircuitBreaker tests (~4h)
- [ ] Create `backend/tests/test_supabase_client.py`
- [ ] Test circuit breaker state transitions: CLOSED -> OPEN -> HALF-OPEN -> CLOSED
- [ ] Test sliding window failure counting (10-window, 50% threshold)
- [ ] Test cooldown period (60s, mock time)
- [ ] Test trial calls during HALF-OPEN (3 trial calls before full CLOSED)
- [ ] Test thread-safety of `supabase_cb` singleton (concurrent access)
- [ ] Test `get_supabase()` returns client in CLOSED state, raises in OPEN state

### QA-DEBT-005: filter_*.py submodule tests (~6h)
- [ ] Create `backend/tests/test_filter_basic.py` -- basic filtering logic
- [ ] Create `backend/tests/test_filter_density.py` -- keyword density scoring
- [ ] Create `backend/tests/test_filter_keywords.py` -- keyword matching, synonyms
- [ ] Create `backend/tests/test_filter_recovery.py` -- recovery/fallback paths
- [ ] Create `backend/tests/test_filter_status.py` -- status inference filtering
- [ ] Create `backend/tests/test_filter_uf.py` -- UF (state) filtering
- [ ] Create `backend/tests/test_filter_utils.py` -- utility functions
- [ ] Create `backend/tests/test_filter_value.py` -- value range filtering
- [ ] Each file: minimum 5 test cases covering happy path, edge cases, empty input

### QA-DEBT-006: Stripe webhook handler test matrix (~4h)
- [ ] Audit existing `test_stripe_webhook.py` for covered event types
- [ ] Add tests for ALL 10+ Stripe event types handled in `webhooks/stripe.py`:
  - `checkout.session.completed`
  - `customer.subscription.created`
  - `customer.subscription.updated`
  - `customer.subscription.deleted`
  - `invoice.paid`
  - `invoice.payment_failed`
  - `customer.created`
  - `customer.updated`
  - `payment_intent.succeeded`
  - `payment_intent.payment_failed`
  - Any other event types found in handler
- [ ] Test signature verification (valid, invalid, missing)
- [ ] Test idempotency -- same event ID processed twice should not duplicate state changes
- [ ] Test `profiles.plan_type` sync on every webhook that changes subscription state

### QA-DEBT-003: search_state_manager.py tests (~3h)
- [ ] Create `backend/tests/test_search_state_manager.py`
- [ ] Test state machine transitions: PENDING -> RUNNING -> COMPLETED
- [ ] Test state machine transitions: PENDING -> RUNNING -> FAILED
- [ ] Test invalid transitions are rejected (e.g., COMPLETED -> RUNNING)
- [ ] Test concurrent state updates (asyncio-safe)
- [ ] Test state persistence and retrieval

### QA-DEBT-004: worker_lifecycle.py tests (~1h)
- [ ] Create `backend/tests/test_worker_lifecycle.py`
- [ ] Test startup sequence (worker initialization)
- [ ] Test shutdown sequence (graceful cleanup)
- [ ] Test reconnection logic on connection failure
- [ ] Mock ARQ dependency using conftest `_isolate_arq_module` pattern

## Criterios de Aceite

- [ ] AC1: All 12+ new test files created and passing: `python scripts/run_tests_safe.py --parallel 4`
- [ ] AC2: Test count increased by >= 150 from baseline 7,332 (measure with `pytest --co -q | wc -l`)
- [ ] AC3: Zero new failures introduced -- existing 7,332 tests still pass
- [ ] AC4: Each new test file has a module-level docstring explaining what production module it covers
- [ ] AC5: Circuit breaker tests cover all 3 states (CLOSED, OPEN, HALF-OPEN) with assertions on state transitions
- [ ] AC6: Webhook test matrix covers 100% of event types found in `webhooks/stripe.py`
- [ ] AC7: Filter submodule tests each have >= 5 test cases (40+ total across 8 files)
- [ ] AC8: Baseline test count recorded in `docs/prd/technical-debt-assessment.md` appendix for Wave 3 reference

## Testes Requeridos

- [ ] `python scripts/run_tests_safe.py --parallel 4` -- full suite, 0 new failures
- [ ] `pytest backend/tests/test_cron_jobs.py -v` -- all cron tasks covered
- [ ] `pytest backend/tests/test_supabase_client.py -v` -- CB state machine verified
- [ ] `pytest backend/tests/test_filter_basic.py backend/tests/test_filter_density.py backend/tests/test_filter_keywords.py backend/tests/test_filter_recovery.py backend/tests/test_filter_status.py backend/tests/test_filter_uf.py backend/tests/test_filter_utils.py backend/tests/test_filter_value.py -v` -- all submodules covered
- [ ] `pytest backend/tests/test_stripe_webhook.py -v` -- all event types covered
- [ ] `pytest backend/tests/test_search_state_manager.py -v` -- state transitions verified
- [ ] `pytest backend/tests/test_worker_lifecycle.py -v` -- lifecycle events verified

## Dependencias

- **Blocked by:** Nothing -- this is the first wave
- **Blocks:** ALL of Wave 3 (DEBT-W3). Hard gate: no restructuring PR merges until this story is complete.
- **Parallel with:** Wave 1 (DEBT-W1) -- these are additive tests, no production code changes

## Notes

- Use conftest `_isolate_arq_module` autouse fixture for ARQ mocking (never raw `sys.modules["arq"] = ...`)
- Use `@pytest.mark.timeout(30)` default; `@pytest.mark.timeout(60)` for slow integration tests
- Patch `supabase_client.get_supabase` (not `search_cache.get_supabase`) per project conventions
- Reset `supabase_cb` global singleton between tests via conftest autouse fixture

## Definition of Done

- [ ] All tasks completed
- [ ] All acceptance criteria met (AC1-AC8)
- [ ] Tests written and passing (12+ new files, 150+ new tests)
- [ ] Code reviewed by @qa
- [ ] No regressions (full suite green)
- [ ] Baseline test count recorded for Wave 3 reference
