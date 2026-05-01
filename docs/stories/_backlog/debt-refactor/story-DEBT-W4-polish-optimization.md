# Story DEBT-W4: Polish + Optimization

**Story ID:** DEBT-W4
**Epic:** DEBT-EPIC-001
**Wave:** 4
**Priority:** LOW
**Effort:** ~97h
**Agents:** Team (all agents, opportunistic)

---

## Descricao

Resolve all remaining LOW and MEDIUM debt items. Unlike Waves 0-3, this wave is designed to be interleaved with feature work over 4 weeks -- items are independent and can be picked up opportunistically when touching related code. Includes DB micro-optimizations, frontend polish (skeletons, design tokens, blog cleanup), backend documentation, CI security audits, and two deferred items that trigger only at scale thresholds.

## Debitos Incluidos

### DB Hygiene -- Trivial Fixes (~9h)

| ID | Debito | Severidade | Horas |
|----|--------|-----------|-------|
| DEBT-DB-005 | user_subscriptions active index missing created_at | LOW | 0.5 |
| DEBT-DB-012 | organizations.plan_type CHECK overly permissive | LOW | 0.5 |
| DEBT-DB-013 | reconciliation_log no pg_cron retention job | LOW | 0.5 |
| DEBT-DB-014 | backend/migrations/ directory redundant | LOW | 0.5 |
| DEBT-DB-015 | Legacy plans ON DELETE RESTRICT (intentional -- document) | LOW | 0.5 |
| DEBT-DB-017 | pg_cron scheduling collision at 4:00 UTC | LOW | 0.5 |
| DEBT-DB-019 | select("*") on search_sessions in sessions.py | LOW | 1 |
| DEBT-DB-007 | handle_new_user() TOCTOU race error message improvement | LOW | 1 |
| DEBT-DB-016 | No CHECK constraint on search_sessions.error_code | LOW | 1 |
| DEBT-DB-021 | select("*") on profiles in 8+ call sites | LOW | 2 |

### Frontend Polish (~25h)

| ID | Debito | Severidade | Horas |
|----|--------|-----------|-------|
| DEBT-FE-024 | Pricing page CTA button has no inline loading state | LOW | 1 |
| DEBT-FE-021 | Planos FAQ accordion has no ARIA disclosure pattern | LOW | 1.5 |
| DEBT-FE-011 | Duplicate LoadingProgress + AddToPipelineButton across dirs | LOW | 2 |
| DEBT-FE-006 | Search hooks: 3,287 LOC in 9 hooks -- needs documentation | LOW | 4 |
| DEBT-FE-009 | Blog TODO placeholders (60+ instances) | LOW | 4 |
| DEBT-FE-013 | No skeleton loaders for admin, conta, alertas, mensagens, planos | LOW | 4 |
| DEBT-FE-014 | EnhancedLoadingProgress at 452 LOC -- decompose | LOW | 4 |
| DEBT-FE-016 | Raw CSS var() instead of Tailwind semantic classes | LOW | 4 |

### Backend Cleanup (~15h)

| ID | Debito | Severidade | Horas |
|----|--------|-----------|-------|
| DEBT-SYS-018 | Backend docs/ currency unknown -- audit and update | LOW | 2 |
| DEBT-SYS-019 | scripts/ utility scripts not in CI test suite | LOW | 2 |
| DEBT-SYS-014 | 40+ feature flags, some permanently enabled/disabled | MEDIUM | 3 |
| DEBT-SYS-015 | 58 API proxy routes, generic factory underused | LOW | 4 |
| DEBT-SYS-017 | backend/clients/ -- 5 clients with no shared base class | LOW | 4 |

### Testing + QA (~18h)

| ID | Debito | Severidade | Horas |
|----|--------|-----------|-------|
| DEBT-CI-002 | No pip-audit or npm audit in CI pipeline | LOW | 2 |
| QA-DEBT-008 | No requirements.txt lockfile with hashes (supply chain risk) | LOW | 2 |
| QA-DEBT-007 | Frontend pages with zero tests: onboarding, mensagens, redefinir-senha, ajuda, features | MEDIUM | 8 |
| DEBT-SYS-011 | Test LOC (140K) is 1.8x source LOC (77K) -- uneven distribution audit | MEDIUM | 8 |

### Deferred -- Scale-Dependent (~26h, trigger-based)

| ID | Debito | Severidade | Horas | Trigger |
|----|--------|-----------|-------|---------|
| DEBT-DB-003 | profiles table 20+ columns (wide table) | LOW | 10 | At 10K users or 30+ columns |
| DEBT-DB-011 | search_sessions 24 columns (wide table) | LOW | 16 | At 1M rows |

## Tasks

### Track A: DB Micro-Fixes (~9h, batch into 1-2 migrations)

- [ ] **DB-005:** Add index on user_subscriptions(status, created_at) -- defer if < 10K subscriptions
- [ ] **DB-012:** Tighten organizations.plan_type CHECK to match actual plan enum values
- [ ] **DB-013:** Create pg_cron job to DELETE from reconciliation_log WHERE created_at < NOW() - INTERVAL '90 days'
- [ ] **DB-014:** Remove `backend/migrations/` directory (redundant with `supabase/migrations/`)
- [ ] **DB-015:** Document ON DELETE RESTRICT on legacy plans as intentional in migration comment
- [ ] **DB-017:** Stagger pg_cron jobs: spread 4:00 UTC cluster across 4:00-4:30 UTC (5-minute intervals)
- [ ] **DB-019:** Replace `select("*")` with column projection in sessions.py (list only needed columns)
- [ ] **DB-007:** Improve handle_new_user() error message on phone uniqueness TOCTOU race
- [ ] **DB-016:** Add CHECK constraint on search_sessions.error_code to match SearchErrorCode enum values
- [ ] **DB-021:** Replace `select("*")` with column projection in 8+ profiles call sites

### Track B: Frontend Polish (~25h)

- [ ] **FE-024:** Add inline loading spinner to Planos page CTA button during Stripe checkout redirect
- [ ] **FE-021:** Implement WAI-ARIA disclosure pattern on Planos FAQ accordion (`aria-expanded`, `aria-controls`, `id` references)
- [ ] **FE-011:** Consolidate duplicate `LoadingProgress` and `AddToPipelineButton` -- keep one canonical version, delete duplicates
- [ ] **FE-006:** Write JSDoc documentation for all 9 search hooks (useSearch, useSearchExecution, useSearchResults, etc.) explaining purpose, parameters, return values, and usage examples
- [ ] **FE-009:** Replace 60+ Blog TODO placeholders with actual content or remove blog pages entirely
- [ ] **FE-013:** Add skeleton loaders: start with Planos page (conversion anxiety), then Admin, Conta. Use Tailwind `animate-pulse` pattern
- [ ] **FE-014:** Decompose EnhancedLoadingProgress (452 LOC) into: `ProgressBar.tsx`, `ProgressSteps.tsx`, `ProgressAnimation.tsx`
- [ ] **FE-016:** Replace raw `var(--color-*)` CSS with Tailwind semantic classes. Audit with: `grep -r "var(--" frontend/app/ --include="*.tsx" | wc -l` (target: < 50)

### Track C: Backend Cleanup (~15h)

- [ ] **SYS-018:** Audit `backend/docs/` -- update or delete stale documentation files
- [ ] **SYS-019:** Add smoke tests for utility scripts in `scripts/` (at minimum: import succeeds, --help works)
- [ ] **SYS-014:** Audit all 40+ feature flags in config.py. Remove flags that have been permanently enabled/disabled for > 3 months. Document remaining flags with purpose and expected removal date
- [ ] **SYS-015:** Create generic API proxy factory in `frontend/app/api/` and migrate at least 10 of 58 proxy routes to use it. Document pattern for future routes
- [ ] **SYS-017:** Create `backend/clients/base.py` with shared retry, timeout, circuit breaker, logging. Refactor 5 clients to extend it

### Track D: Testing + QA (~18h)

- [ ] **CI-002:** Add `pip-audit` step to backend CI workflow. Add `npm audit --audit-level=high` to frontend CI. Fail on HIGH+ vulnerabilities only
- [ ] **QA-008:** Generate `requirements.txt` lockfile with hashes: `pip-compile --generate-hashes requirements.in -o requirements.txt`
- [ ] **QA-007:** Write basic render + interaction tests for untested frontend pages: onboarding (render all 3 steps), mensagens (render empty state), redefinir-senha (form submission), ajuda (render sections), features (render feature list)
- [ ] **SYS-011:** Audit test LOC distribution. Identify test files with > 50% duplication (copy-pasted setup). Extract shared fixtures into conftest. Target: reduce test LOC by 10% without losing coverage

### Track E: Deferred Items (trigger-based, NOT scheduled)

- [ ] **DB-003:** When profiles exceeds 30 columns OR user count > 10K: extract preferences, notification settings, and billing details into separate tables with 1:1 FK
- [ ] **DB-011:** When search_sessions exceeds 1M rows: extract metadata JSONB into separate table, implement table partitioning by created_at (monthly)

## Criterios de Aceite

- [ ] AC1: No known CRITICAL items remaining in assessment (0/4)
- [ ] AC2: No known HIGH items remaining in assessment (0/14)
- [ ] AC3: Backend test coverage >= 70% (`pytest --cov`)
- [ ] AC4: Frontend test coverage >= 60% (`npm run test:coverage`)
- [ ] AC5: Bundle size stable or improved vs pre-Wave-4 baseline (`npm run build`)
- [ ] AC6: `pip-audit` and `npm audit` added to CI, passing on HIGH+ threshold
- [ ] AC7: Feature flag count reduced by >= 10 (from 40+ to 30 or fewer)
- [ ] AC8: `var(--` occurrences in frontend < 50 (from ~1,754)
- [ ] AC9: Duplicate components consolidated (1 LoadingProgress, 1 AddToPipelineButton)
- [ ] AC10: At least 5 untested frontend pages have basic render tests
- [ ] AC11: All deferred items documented with trigger conditions and monitoring queries

## Testes Requeridos

- [ ] `python scripts/run_tests_safe.py --parallel 4` -- full backend suite, 0 new failures
- [ ] `npm test` -- full frontend suite, 0 new failures
- [ ] `npm run test:e2e` -- E2E tests pass
- [ ] `pytest --cov` -- coverage >= 70%
- [ ] `npm run test:coverage` -- coverage >= 60%
- [ ] `pip-audit` -- 0 HIGH+ vulnerabilities
- [ ] `npm audit --audit-level=high` -- 0 HIGH+ vulnerabilities
- [ ] New frontend page tests render without errors

## Dependencias

- **Blocked by:** DEBT-W2 (Wave 2) and DEBT-W3 (Wave 3) for structural items
- **Blocks:** Nothing -- this is the final wave
- **Independent items:** All items in this wave can be done independently of each other
- **Deferred items:** DB-003 and DB-011 have scale-based triggers, not time-based

## Notes

- This wave is designed for opportunistic execution. Pick items when touching related code.
- Priority within the wave: Track D (testing/QA) > Track A (DB) > Track B (FE) > Track C (backend)
- DB-003 and DB-011 monitoring: add Supabase dashboard queries for row counts + column counts
- FE-016 is the largest cosmetic item (4h) -- consider pairing with any Tailwind refactoring work
- SYS-011 test audit may reveal more duplication than expected -- timebox to 8h, document findings even if not fully resolved

## Definition of Done

- [ ] All non-deferred tasks completed (~71h of work)
- [ ] All acceptance criteria met (AC1-AC11)
- [ ] Deferred items documented with monitoring queries and trigger thresholds
- [ ] Tests written and passing
- [ ] Code reviewed
- [ ] No regressions (backend + frontend + E2E)
- [ ] Technical debt assessment updated: all items marked RESOLVED or DEFERRED with rationale
