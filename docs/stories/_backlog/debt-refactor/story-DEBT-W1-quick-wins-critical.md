# Story DEBT-W1: Quick Wins + Critical Fixes

**Story ID:** DEBT-W1
**Epic:** DEBT-EPIC-001
**Wave:** 1
**Priority:** CRITICAL
**Effort:** ~26.25h
**Agents:** @dev (Devin) -- backend + frontend

---

## Descricao

Ship all items under 4 hours plus all CRITICAL-severity fixes in 3 thematic PRs. This wave addresses the highest-impact, lowest-effort debt: accessibility violations on the main search page (/buscar), broken skip-link navigation, non-atomic account deletion, dual subscription tracking, and a dead data source consuming pipeline budget. Organized into 3 PRs per QA recommendation to balance review throughput with coherence.

## Debitos Incluidos

| ID | Debito | Severidade | Horas | PR |
|----|--------|-----------|-------|----|
| DEBT-FE-022 | Protected layout missing `id="main-content"` (root cause of FE-008 skip-link) | HIGH | 0.25 | PR 1 |
| DEBT-FE-001 | react-hook-form in devDependencies, used in 3 production pages | HIGH | 0.5 | PR 1 |
| DEBT-DB-006 | trial_email_log RLS enabled but no explicit policies | MEDIUM | 0.5 | PR 1 |
| DEBT-DB-020 | No composite index on search_sessions(user_id, created_at DESC) | MEDIUM | 0.5 | PR 1 |
| DEBT-DB-002 | classification_feedback FK references auth.users on fresh install | HIGH | 1 | PR 1 |
| DEBT-FE-017 | Login form lacks aria-invalid and aria-describedby | HIGH | 1.5 | PR 1 |
| DEBT-FE-002 | **SearchForm zero ARIA -- no role="search", no aria-label** | **CRITICAL** | 3 | PR 1 |
| DEBT-DB-018 | **Account deletion cascade misses tables -- non-transactional** | **HIGH** | 3 | PR 1 |
| DEBT-SYS-013 | ComprasGov v3 down since Mar 2026 but still active in pipeline | MEDIUM | 2 | PR 2 |
| DEBT-SYS-008 | api-types.generated.ts 5,177 LOC bundle impact -- verify tree-shaking | MEDIUM | 2 | PR 2 |
| DEBT-SYS-003 | **pncp_client.py imports sync `requests` alongside async `httpx`** | **CRITICAL** | 4 | PR 2 |
| DEBT-FE-015 | BottomNav wrong Dashboard icon | LOW | 0.5 | PR 3 |
| DEBT-FE-012 | Feature-gated pages (/alertas, /mensagens) show broken state | MEDIUM | 2 | PR 3 |
| DEBT-FE-007 | **Missing error boundaries on onboarding, signup, login, planos** | **HIGH** | 3 | PR 3 |
| DEBT-DB-001 | Dual subscription_status tracking -- profiles vs user_subscriptions | HIGH | 3 | PR 3 |
| DEBT-FE-008 | Skip-link broken on all protected pages (subsumed by FE-022, 0h) | HIGH | 0 | PR 1 |

## Tasks

### PR 1 -- Security + Accessibility (~10.25h)

- [ ] Add `id="main-content"` to the `<main>` tag in protected layout component (fixes FE-022 + FE-008)
- [ ] Move `react-hook-form` from `devDependencies` to `dependencies` in `frontend/package.json`
- [ ] Create Supabase migration: add RLS policy for `trial_email_log` table (SELECT for authenticated users on own rows)
- [ ] Create Supabase migration: `CREATE INDEX CONCURRENTLY idx_search_sessions_user_created ON search_sessions(user_id, created_at DESC)`
- [ ] Create Supabase migration: fix `classification_feedback` FK to use idempotent `IF NOT EXISTS` pattern
- [ ] Add `aria-invalid={!!errors.email}` and `aria-describedby="email-error"` to login form email/password inputs
- [ ] Add conditional error `<span id="email-error" role="alert">` below each login input
- [ ] Add `role="search"` and `aria-label="Buscar licitacoes"` to SearchForm container
- [ ] Add `aria-label` to all SearchForm interactive elements (sector select, UF checkboxes, date inputs)
- [ ] Add `aria-live="polite"` region for search result count announcement
- [ ] Restructure account deletion: use CASCADE from profiles, wrap Stripe-dependent deletes in transaction
- [ ] Write integration test: simulate auth.users delete failure, verify profiles + children remain intact

### PR 2 -- Backend Cleanup (~8h)

- [ ] Disable ComprasGov v3 source: set feature flag `COMPRAS_GOV_ENABLED=False` as default in config.py
- [ ] Add config comment documenting ComprasGov outage since March 2026 and re-evaluation date
- [ ] Remove ComprasGov from health endpoint active sources list
- [ ] Run `npm run build` with bundle analyzer, verify api-types.generated.ts is tree-shaken by Next.js
- [ ] If not tree-shaken: split api-types.generated.ts into domain-specific type files (search, billing, pipeline)
- [ ] Document findings in PR description regardless of outcome
- [ ] Remove sync `requests` import from `pncp_client.py` -- keep only async `httpx`
- [ ] Remove `requests` from `requirements.txt` if no other module imports it
- [ ] Update `asyncio.to_thread()` wrapper to use httpx directly instead of sync requests fallback
- [ ] Verify all PNCP client methods work with httpx-only: `pytest -k "test_pncp" -v`

### PR 3 -- Frontend Polish (~8h)

- [ ] Fix BottomNav Dashboard icon: replace with correct icon from Lucide/Heroicons set
- [ ] Create `ComingSoonPage` component with distinctive design (NOT generic EmptyState): illustration, "Em breve" heading, optional email notification toggle
- [ ] Wrap `/alertas` and `/mensagens` pages with `ComingSoonPage` when feature-gated
- [ ] Create `ErrorBoundary` wrapper component (or use existing if one exists in components/)
- [ ] Wrap `/onboarding`, `/signup`, `/login`, `/planos` pages with ErrorBoundary
- [ ] ErrorBoundary: show friendly Portuguese error message + "Tentar novamente" button + Sentry error report
- [ ] Unify subscription_status enums: create Supabase migration adding sync trigger from `user_subscriptions` to `profiles.subscription_status`
- [ ] Document canonical source of truth (user_subscriptions) in migration comment
- [ ] Test enum sync with unit test: update user_subscriptions -> verify profiles.subscription_status matches

## Criterios de Aceite

- [ ] AC1: axe-core on /buscar returns 0 critical WCAG violations (extend `accessibility-audit.spec.ts`)
- [ ] AC2: Skip-link (Tab -> Enter on first focusable) navigates to `#main-content` on /dashboard, /pipeline, /historico
- [ ] AC3: Login form shows inline error with `aria-invalid="true"` and linked `aria-describedby` on validation failure
- [ ] AC4: Account deletion is atomic -- integration test proves partial failure leaves consistent state
- [ ] AC5: ComprasGov disabled -- health endpoint shows 2 active sources (PNCP + PCP)
- [ ] AC6: `pncp_client.py` has zero imports of `requests` module -- only `httpx`
- [ ] AC7: `npm run build` succeeds with no increase in bundle size (record before/after)
- [ ] AC8: ErrorBoundary catches render errors on /onboarding, /signup, /login, /planos without page crash
- [ ] AC9: /alertas and /mensagens show `ComingSoonPage` instead of API errors
- [ ] AC10: Subscription status enum is unified with sync trigger (verified by integration test)
- [ ] AC11: All 3 PRs merged, zero test regressions in both backend and frontend suites

## Testes Requeridos

- [ ] `python scripts/run_tests_safe.py --parallel 4` -- full backend suite, 0 new failures
- [ ] `npm test` -- full frontend suite, 0 new failures
- [ ] `npm run test:e2e` -- E2E tests pass
- [ ] `pytest -k "test_pncp" -v` -- PNCP client works with httpx-only
- [ ] `pytest -k "test_account_deletion" -v` -- deletion atomicity verified
- [ ] `pytest -k "test_stripe_webhook" -v` -- subscription sync trigger works
- [ ] Playwright axe-core audit on /buscar, /login -- 0 critical violations
- [ ] Manual keyboard test: Tab through /buscar, verify all elements reachable and labeled

## Dependencias

- **Blocked by:** Nothing (parallel with Wave 0)
- **Blocks:** Wave 2 (DEBT-W2) -- DB-002 FK fix feeds into Wave 2 migration chain
- **Info dependency:** DB-001 enum unification informs SYS-007 (Wave 3) and SYS-009 (Wave 3)

## Definition of Done

- [ ] All tasks completed (3 PRs merged)
- [ ] All acceptance criteria met (AC1-AC11)
- [ ] Tests written and passing
- [ ] Code reviewed
- [ ] No regressions (backend + frontend + E2E)
- [ ] Bundle size recorded (before/after) in PR description
