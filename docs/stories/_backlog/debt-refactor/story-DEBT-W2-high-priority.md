# Story DEBT-W2: High Priority -- DB Hygiene + Accessibility

**Story ID:** DEBT-W2
**Epic:** DEBT-EPIC-001
**Wave:** 2
**Priority:** HIGH
**Effort:** ~35.5h
**Agents:** @dev (Devin) + @data-engineer (Delta)

---

## Descricao

Resolve all HIGH and MEDIUM severity items not addressed in Wave 1. This wave focuses on three tracks: (1) database hygiene including migration squash and JSONB constraints, (2) frontend accessibility improvements for onboarding/login/mensagens, and (3) frontend architecture improvements (Framer Motion lazy-loading, react-hook-form migration). The migration squash (DB-008) must be the LAST database item due to its dependency chain.

## Debitos Incluidos

| ID | Debito | Severidade | Horas |
|----|--------|-----------|-------|
| DEBT-FE-018 | Mensagens status badges are color-only (no icon, no SR text) | MEDIUM | 1 |
| DEBT-FE-019 | Onboarding progress bar has no accessible semantics | MEDIUM | 1 |
| DEBT-FE-020 | Login mode toggle lacks tab/keyboard semantics | MEDIUM | 1 |
| DEBT-DB-004 | pipeline_items.search_id TEXT vs search_sessions UUID mismatch | MEDIUM | 1.5 |
| DEBT-DB-010 | JSONB columns without size governance | MEDIUM | 2 |
| DEBT-DB-022 | quota.py last-resort upsert fallback not truly atomic | MEDIUM | 2 |
| DEBT-FE-023 | No focus management after search completes | MEDIUM | 2 |
| DEBT-DB-009 | Stripe price IDs hardcoded in 4 migrations | MEDIUM | 3 |
| DEBT-CI-001 | tests.yml vs backend-tests.yml vs backend-ci.yml -- unclear PR gate | MEDIUM | 3 |
| DEBT-DB-008 | 85 migrations with 7 handle_new_user redefinitions -- squash needed | MEDIUM | 5 |
| DEBT-FE-004 | Framer Motion (~50KB gzip) loaded globally, used in 9 files only | MEDIUM | 6 |
| DEBT-FE-003 | Inconsistent form handling -- 3 pages react-hook-form, rest raw useState | MEDIUM | 8 |

## Tasks

### Track A: Database Hygiene (@data-engineer, ~14.5h)

- [ ] **DB-004 (1.5h):** Add CHECK constraint or migration comment documenting that `pipeline_items.search_id` is intentionally TEXT (not UUID FK). If FK is desired, create migration adding proper UUID reference
- [ ] **DB-010 (2h):** Add JSONB CHECK constraints to relevant columns using `NOT VALID` for zero-downtime, then run `VALIDATE CONSTRAINT` separately. Target columns: `search_sessions.metadata`, `pipeline_items.notes`, others identified in audit
- [ ] **DB-022 (2h):** Fix quota.py upsert fallback -- either make it truly atomic with `INSERT ... ON CONFLICT DO UPDATE` in a single statement, or remove the misleading fallback path and let the error propagate. Add unit test for the fixed path
- [ ] **DB-009 (3h):** Create env-based seed script that replaces hardcoded Stripe price IDs in migrations. New migrations reference `os.environ["STRIPE_PRICE_XXX"]` or a config table. Document in `backend/.env.example`
- [ ] **DB-008 (5h, LAST):** Create squash baseline migration. Verify with CI job: fresh PostgreSQL 17 -> apply squash -> apply remaining migrations -> `pg_dump --schema-only` diff against production. Add weekly CI validation job. MUST run after DB-001 (W1), DB-002 (W1), and DB-009 (this wave) are all merged

### Track B: Frontend Accessibility (@dev, ~5h)

- [ ] **FE-018 (1h):** Add icon + screen-reader text to Mensagens status badges (not just color). Use `<span class="sr-only">` for badge labels. Add visual icon (checkmark, clock, x) alongside color
- [ ] **FE-019 (1h):** Add `role="progressbar"`, `aria-valuenow`, `aria-valuemin="0"`, `aria-valuemax="100"`, and `aria-label="Progresso do cadastro"` to onboarding step indicator
- [ ] **FE-020 (1h):** Refactor login mode toggle to use `role="tablist"` container with `role="tab"` buttons, `aria-selected`, and arrow key navigation per WAI-ARIA tabs pattern
- [ ] **FE-023 (2h):** After search completes, programmatically shift focus to results header (`<h2>` or `<section aria-label>`). Use `useEffect` on results change. Depends on FE-002 (Wave 1) `aria-live` region being in place

### Track C: Frontend Architecture (@dev, ~14h)

- [ ] **FE-004 (6h):** Lazy-load Framer Motion via `next/dynamic` for landing page only. Replace Framer Motion usage on authenticated pages (9 files) with CSS transitions/animations. Verify with `npm run build` + bundle analyzer that framer-motion chunks do not load on /buscar, /dashboard, /pipeline
- [ ] **FE-003 (8h):** Migrate `/login`, `/recuperar-senha`, `/redefinir-senha` forms to react-hook-form + zod validation schema. Replace raw useState form handling. Ensure consistent real-time validation UX across all auth forms. Write jest tests for validation schemas

### Track D: CI Cleanup (@dev, ~3h)

- [ ] **CI-001 (3h):** Audit all CI workflow files: `tests.yml`, `backend-tests.yml`, `backend-ci.yml`, `frontend-tests.yml`, `e2e.yml`, `deploy.yml`, `migration-gate.yml`, `migration-check.yml`
- [ ] Document the role of each workflow (PR gate vs post-merge vs scheduled) in a table in `.github/WORKFLOWS.md`
- [ ] Remove redundant workflows or add clear `name:` labels distinguishing them
- [ ] Ensure exactly ONE workflow is the PR gate for backend and ONE for frontend

## Criterios de Aceite

- [ ] AC1: Migration squash replays cleanly on fresh PostgreSQL 17 -- `pg_dump --schema-only` diff is empty vs production
- [ ] AC2: Weekly CI job validates squash + remaining migrations (added to `.github/workflows/`)
- [ ] AC3: JSONB constraints applied without downtime (NOT VALID + VALIDATE pattern)
- [ ] AC4: quota.py upsert is either truly atomic or fallback path removed (no misleading code)
- [ ] AC5: CI workflow roles documented -- each file has clear purpose, no redundancy
- [ ] AC6: Framer Motion only loads on landing page -- bundle analyzer confirms no chunks on /buscar
- [ ] AC7: All auth forms (/login, /recuperar-senha, /redefinir-senha) use react-hook-form + zod
- [ ] AC8: Onboarding progress bar has role="progressbar" with correct aria attributes
- [ ] AC9: Login mode toggle navigable via Tab + arrow keys per WAI-ARIA tabs pattern
- [ ] AC10: Search results completion triggers focus shift (screen reader announces results)
- [ ] AC11: Mensagens badges distinguishable without color (icon + SR text present)
- [ ] AC12: DB-009 Stripe price IDs no longer hardcoded in migration files

## Testes Requeridos

- [ ] `python scripts/run_tests_safe.py --parallel 4` -- full backend suite, 0 new failures
- [ ] `npm test` -- full frontend suite, 0 new failures
- [ ] `npm run test:e2e` -- E2E tests pass
- [ ] `pytest -k "test_quota" -v` -- quota upsert fix verified
- [ ] Jest tests for zod validation schemas (login, recuperar-senha, redefinir-senha)
- [ ] Migration squash CI job passes on fresh database
- [ ] `npm run build` -- bundle size stable or reduced; bundle analyzer screenshot in PR
- [ ] Manual a11y: NVDA/VoiceOver test on login mode toggle (arrow key navigation works)

## Dependencias

- **Blocked by:** DEBT-W1 (Wave 1) -- specifically DB-001 (enum unification) and DB-002 (FK fix) must be merged before DB-008 squash
- **Blocks:** Wave 4 (DEBT-W4) for remaining LOW items
- **Internal dependency chain:** DB-001 (W1) -> DB-009 (this wave) -> DB-008 (this wave, LAST)
- **FE-023 depends on:** FE-002 (Wave 1) aria-live region being in place

## Definition of Done

- [ ] All tasks completed (Tracks A-D)
- [ ] All acceptance criteria met (AC1-AC12)
- [ ] Tests written and passing
- [ ] Code reviewed by @qa + @data-engineer
- [ ] No regressions (backend + frontend + E2E)
- [ ] CI workflows documented in `.github/WORKFLOWS.md`
