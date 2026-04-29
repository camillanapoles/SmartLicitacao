# Story DEBT-W3: Structural Refactoring

**Story ID:** DEBT-W3
**Epic:** DEBT-EPIC-001
**Wave:** 3
**Priority:** CRITICAL
**Effort:** ~76h
**Agents:** @dev (Devin) + @architect (Atlas)

---

## Descricao

Decompose the 5 largest backend monoliths (filter.py 3,871 LOC, pncp_client.py 2,515 LOC, search_cache.py 2,512 LOC, schemas.py 2,121 LOC, job_queue.py 2,152 LOC + cron_jobs.py 2,039 LOC) into domain-specific packages. This is the highest-risk, highest-reward wave -- it eliminates the #1 source of merge conflicts and reduces cognitive load for all developers. Each item ships as a separate PR with full test validation against the Wave 0 baseline.

**HARD PREREQUISITE:** Wave 0 (DEBT-W0) MUST be complete before any PR in this wave merges. The safety net tests are the only way to detect regressions during restructuring.

## Debitos Incluidos

| ID | Debito | Severidade | Horas |
|----|--------|-----------|-------|
| DEBT-SYS-020 | startup/ module exists but main.py still does most initialization | LOW | 3 |
| DEBT-SYS-004 | 69 top-level Python files -- no package grouping | HIGH | 12 |
| DEBT-SYS-012 | 11 filter_*.py + filter.py -- ambiguous ownership, stale docstrings | MEDIUM | 3 |
| DEBT-SYS-001 | **filter.py at 3,871 LOC -- core matching logic not fully migrated** | **CRITICAL** | 8 |
| DEBT-SYS-002 | **schemas.py at 2,121 LOC -- all Pydantic models in one file** | **CRITICAL** | 6 |
| DEBT-SYS-010 | main.py still has 7 endpoints despite startup/ decomposition | MEDIUM | 4 |
| DEBT-SYS-009 | quota.py at 1,622 LOC -- mixes plan, quota, rate limiting, trial | HIGH | 4 |
| DEBT-SYS-006 | search_cache.py at 2,512 LOC -- L1, L2, SWR, serialization | HIGH | 4 |
| DEBT-SYS-005 | job_queue.py (2,152 LOC) + cron_jobs.py (2,039 LOC) monoliths | HIGH | 6 |
| DEBT-SYS-007 | webhooks/stripe.py at 1,192 LOC -- 10+ event types in single handler | HIGH | 6 |
| DEBT-SYS-016 | onboarding/page.tsx (783 LOC) + signup/page.tsx (703 LOC) | MEDIUM | 4 |
| DEBT-FE-005 | 6 pages exceed 500 LOC without component decomposition | MEDIUM | 16 |

## Tasks

Execute in this EXACT order. Each task is a separate PR.

### Step 1: SYS-020 -- Complete startup/ module extraction (~3h)
- [ ] Move remaining initialization logic from main.py to startup/ submodules
- [ ] main.py should only import from startup/ and call `create_app()`
- [ ] Verify: `uvicorn main:app --reload` still works
- [ ] PR validation: `python scripts/run_tests_safe.py --parallel 4`

### Step 2: SYS-004 -- Backend package grouping (~12h, GATEWAY)
- [ ] Create package directories: `backend/filter/`, `backend/search/`, `backend/billing/`, `backend/jobs/`, `backend/cache/`
- [ ] Add `__init__.py` to each package with backward-compat re-exports
- [ ] Move files into packages (DO NOT rename yet -- just relocate):
  - `filter/` -- filter.py + all filter_*.py submodules
  - `search/` -- search_pipeline.py, search_cache.py, search_context.py, search_state_manager.py, consolidation.py
  - `billing/` -- quota.py, services/billing.py, webhooks/stripe.py
  - `jobs/` -- job_queue.py, cron_jobs.py, worker_lifecycle.py
  - `cache/` -- cache.py, redis_client.py, redis_pool.py
- [ ] Create backward-compat shims at old locations: `from filter import *` etc.
- [ ] Update all non-test imports to use new paths
- [ ] PR validation: full test suite, zero failures, test count >= baseline

### Step 3: SYS-012 + SYS-001 -- filter.py decomposition (~11h)
- [ ] Clean up filter_*.py naming: remove ambiguous prefixes, add clear docstrings
- [ ] Migrate remaining logic from filter.py (3,871 LOC) into submodules:
  - `filter/matching.py` -- core keyword matching engine
  - `filter/density.py` -- density scoring (already exists as filter_density.py)
  - `filter/pipeline.py` -- orchestration of filter chain (UF -> value -> keyword -> LLM -> status)
  - Keep `filter/__init__.py` as re-export hub (< 500 LOC)
- [ ] Update all imports in non-test code
- [ ] Verify: `wc -l backend/filter/__init__.py` < 500
- [ ] PR validation: full test suite + Wave 0 filter tests (QA-DEBT-005) all pass

### Step 4: SYS-002 -- schemas.py split by domain (~6h)
- [ ] Create `backend/schemas/` package:
  - `schemas/search.py` -- BuscaRequest, BuscaResponse, SearchResult, etc.
  - `schemas/billing.py` -- PlanInfo, SubscriptionStatus, CheckoutRequest, etc.
  - `schemas/pipeline.py` -- PipelineItem, PipelineStage, etc.
  - `schemas/user.py` -- UserProfile, ProfileContext, etc.
  - `schemas/common.py` -- shared base models, validators
  - `schemas/__init__.py` -- re-export ALL models for backward compatibility
- [ ] `from schemas import BuscaRequest` must still work (backward compat)
- [ ] PR validation: full test suite, zero import errors

### Step 5: SYS-010 -- main.py endpoint extraction (~4h)
- [ ] Move remaining 7 endpoints from main.py to appropriate routes/ modules
- [ ] main.py should contain only: app creation, middleware, router includes, startup events
- [ ] Target: main.py < 200 LOC
- [ ] PR validation: all routes still respond correctly, test suite passes

### Step 6: SYS-009 -- quota.py split (~4h)
- [ ] Split into `billing/plan_definitions.py`, `billing/quota_checker.py`, `billing/rate_limiter.py`, `billing/trial_manager.py`
- [ ] Keep `quota.py` as backward-compat re-export (< 100 LOC)
- [ ] Requires DB-022 (Wave 2) to be fixed first -- don't split buggy code
- [ ] PR validation: `pytest -k "test_quota" -v` + full suite

### Step 7: SYS-006 -- search_cache.py split (~4h)
- [ ] Split into `cache/l1_memory.py`, `cache/l2_supabase.py`, `cache/swr_manager.py`, `cache/key_generator.py`
- [ ] Keep `search_cache.py` as backward-compat re-export
- [ ] Verify: cache patch pattern `supabase_client.get_supabase` still works in tests
- [ ] PR validation: `pytest -k "test_cache" -v` + full suite

### Step 8: SYS-005 -- job_queue + cron_jobs split (~6h)
- [ ] Split job_queue.py by domain: `jobs/search_jobs.py`, `jobs/billing_jobs.py`, `jobs/report_jobs.py`, `jobs/maintenance_jobs.py`
- [ ] Split cron_jobs.py by schedule: `jobs/cron_daily.py`, `jobs/cron_hourly.py`, `jobs/cron_weekly.py`
- [ ] Requires QA-DEBT-001 (Wave 0) cron tests to exist as safety net
- [ ] PR validation: cron test file passes + full suite

### Step 9: SYS-007 -- Stripe webhook handler split (~6h)
- [ ] Split `webhooks/stripe.py` by event type:
  - `webhooks/stripe_checkout.py` -- checkout.session.completed
  - `webhooks/stripe_subscription.py` -- subscription created/updated/deleted
  - `webhooks/stripe_invoice.py` -- invoice paid/failed
  - `webhooks/stripe_customer.py` -- customer created/updated
  - `webhooks/stripe_payment.py` -- payment_intent events
  - `webhooks/stripe_router.py` -- event routing + signature verification
- [ ] Requires QA-DEBT-006 (Wave 0) webhook test matrix as safety net
- [ ] PR validation: webhook test matrix passes + full suite

### Step 10: SYS-016 + FE-005 -- Frontend page decomposition (~20h, parallel with backend)
- [ ] **SYS-016 (4h):** Decompose onboarding/page.tsx (783 LOC) into step components: `OnboardingStep1.tsx`, `OnboardingStep2.tsx`, `OnboardingStep3.tsx`, `OnboardingProgress.tsx`
- [ ] **SYS-016 (cont.):** Decompose signup/page.tsx (703 LOC) into: `SignupForm.tsx`, `SignupOAuth.tsx`, `SignupSuccess.tsx`
- [ ] **FE-005 (16h):** Decompose remaining 4 pages > 500 LOC, in order:
  1. planos/page.tsx -> `PlanCard.tsx`, `PlanComparison.tsx`, `PlanFAQ.tsx`
  2. login/page.tsx -> `LoginForm.tsx`, `LoginModeToggle.tsx`, `LoginOAuth.tsx`
  3. admin/page.tsx -> `AdminStats.tsx`, `AdminUsers.tsx`, `AdminActions.tsx`
  4. conta/page.tsx -> `AccountProfile.tsx`, `AccountBilling.tsx`, `AccountDanger.tsx`
- [ ] Each decomposed page should be < 200 LOC (orchestration only)
- [ ] Jest tests for new components where business logic exists

## Per-Step Validation Protocol

Before EACH PR:
1. Record test count: `pytest --co -q | wc -l` (must be >= Wave 0 baseline)
2. Run full suite: `python scripts/run_tests_safe.py --parallel 4` -- 0 new failures
3. Run frontend suite: `npm test` -- 0 new failures
4. Verify backward-compat re-exports work: no import errors in non-test code

After ALL Wave 3 PRs merged:
5. Add CI guard: `grep -r "from filter import" --include="*.py" backend/ | grep -v tests/` must return 0 results (all should use `from filter.matching import ...` etc.)
6. Verify no file in restructured packages exceeds 1,000 LOC

## Criterios de Aceite

- [ ] AC1: No restructured file exceeds 1,000 LOC (`wc -l` on all files in new packages)
- [ ] AC2: `filter/__init__.py` < 500 LOC (orchestration + re-exports only)
- [ ] AC3: `schemas/__init__.py` re-exports ALL models -- `from schemas import BuscaRequest` still works
- [ ] AC4: main.py < 200 LOC (app creation + middleware + router includes only)
- [ ] AC5: Test count >= Wave 0 baseline after every step (recorded in each PR)
- [ ] AC6: CI import path guard passes: no old-style `from filter import` in non-test backend code
- [ ] AC7: All 11 PRs pass full test suite independently
- [ ] AC8: Each frontend page after decomposition < 200 LOC
- [ ] AC9: No new test failures introduced (delta = 0 across all 11 PRs)
- [ ] AC10: Backward-compat shims exist at old file locations during transition period

## Testes Requeridos

- [ ] `python scripts/run_tests_safe.py --parallel 4` -- after EACH of 11 PRs
- [ ] `npm test` -- after each frontend PR
- [ ] `pytest -k "test_filter"` -- specifically after Steps 3
- [ ] `pytest -k "test_cache"` -- specifically after Step 7
- [ ] `pytest -k "test_quota"` -- specifically after Step 6
- [ ] `pytest -k "test_cron"` -- specifically after Step 8
- [ ] `pytest -k "test_stripe_webhook"` -- specifically after Step 9
- [ ] Import path CI guard after all PRs merged

## Dependencias

- **Blocked by:** DEBT-W0 (Wave 0, HARD GATE) -- all safety net tests must exist before any restructuring
- **Blocked by:** DEBT-W2 items DB-022 (quota fix, for Step 6) and CI-001 (CI clarity, for confidence)
- **Blocks:** Wave 4 (DEBT-W4) for polish items
- **Internal order:** SYS-020 -> SYS-004 (gateway) -> all other SYS items. Frontend can run in parallel.

## Definition of Done

- [ ] All 11 PRs merged
- [ ] All acceptance criteria met (AC1-AC10)
- [ ] Per-step validation protocol followed for every PR
- [ ] Import path CI guard added and passing
- [ ] Code reviewed by @architect + @qa
- [ ] No regressions (backend + frontend + E2E)
- [ ] Backward-compat re-exports documented (removal planned for Wave 4 or next sprint)
