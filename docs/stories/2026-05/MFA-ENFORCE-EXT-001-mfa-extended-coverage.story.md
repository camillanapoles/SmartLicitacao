# MFA-ENFORCE-EXT-001: MFA Enforcement Extended Coverage (post MFA-EXT-001)

**Priority:** P2
**Effort:** S (4-8h)
**Squad:** @dev (lead) + @qa
**Status:** InReview
**Epic:** [EPIC-TD-2026Q2](EPIC-TD-2026Q2/) — eixo RBAC/security
**Sprint:** TBD
**Dependências bloqueadoras:** MFA-EXT-001 Done (Hardening Sprint 2026-05-04)
**ADR:** [docs/adr/mfa-policy.md](../../adr/mfa-policy.md)
**Reversa anchor:** `_reversa_sdd/review-report.md §10.4` RBAC/Security 80% (+20 gap to 100%)

---

## Contexto

MFA-EXT-001 aplicou MFA enforce em endpoints críticos (admin, billing settings). Cobertura atual não inclui:

- Org owner role-change endpoints (`POST /v1/organizations/{id}/members/{user}/role`)
- Org delete (`DELETE /v1/organizations/{id}`)
- Stripe customer portal redirect (financial)
- Profile sensitive update (email change, CPF/CNPJ change — partner program memory `project_partner_program_decisions_2026_04_29`)
- API key/token management (se exists)

Padrão: ADR mfa-policy.md define "step-up auth" para ações high-impact. Esta story estende cobertura sem mudar policy.

---

## Acceptance Criteria

### AC1: Inventory endpoints high-impact

- [x] Listar endpoints que mudam estado high-impact (delete, role-change, financial) → `docs/audits/2026-05-mfa-coverage.md`
- [x] Cross-ref com ADR mfa-policy.md decision tree
- [x] Output: tabela endpoint → decisão (require MFA / skip / N/A) — 5 endpoints REQUIRE, 4 SKIP, 4 N/A (não existem no codebase)

### AC2: Apply `require_mfa` dependency

- [x] Para cada endpoint marcado "require": aplicar dependency FastAPI `require_mfa_high_impact` (wrapper sobre `require_mfa` de MFA-EXT-001)
  - `POST /v1/billing-portal`
  - `POST /v1/change-password`
  - `DELETE /v1/me`
  - `POST /v1/api/subscriptions/cancel`
  - `POST /v1/api/subscriptions/update-billing-period`
- [x] Frontend: nenhum trigger novo necessário — `MfaEnforcementBanner` (existente) é reason-driven via `/v1/mfa/status` e cobre admin/consultoria/bruteforce universalmente. `MfaChallengeModal.tsx` listado em Files **não existe** no codebase
- [~] 401 response code: **deferred** — preserva contrato 403 + `X-MFA-Required` shipped por MFA-EXT-001 (existing tests assert 403, banner reads 403). 401 step-up é separate UX story (não conflict com escopo desta)

### AC3: Test coverage

- [x] `backend/tests/test_mfa_enforcement_extended.py` — 12 tests cobrindo cada endpoint + chain real require_mfa + audit event
- [~] E2E Playwright: deferred — backend integration tests via TestClient cobrem a chain end-to-end; Playwright requer infra running. Manual test plan via `MfaEnforcementBanner` no frontend funciona com qualquer 403+X-MFA-Required (já validado em STORY-317)

### AC4: Audit log

- [x] Endpoints MFA-required emitem Mixpanel `mfa_challenge_satisfied` event no pass-through (aal2 verified) — implementado em `auth.require_mfa_high_impact`. Test: `test_audit_event_emitted_on_pass_through`. Supabase audit table N/A (não existe schema audit dedicada; Mixpanel é a fonte primária para auditoria de comportamento)

---

## Files (actual)

| Arquivo | Ação | Notas |
|---------|------|-------|
| `docs/audits/2026-05-mfa-coverage.md` | Create | AC1 inventory document |
| `backend/auth.py` | Edit | Adds `require_mfa_high_impact` wrapper + test bypass flag |
| `backend/routes/billing.py` | Edit | `/billing-portal` now uses `Depends(require_mfa_high_impact)` |
| `backend/routes/user.py` | Edit | `/change-password` and `DELETE /me` use wrapper |
| `backend/routes/subscriptions.py` | Edit | `/cancel` and `/update-billing-period` use wrapper |
| `backend/tests/test_mfa_enforcement_extended.py` | Create | 12 tests AC3+AC4 |
| `backend/tests/conftest.py` | Edit | Autouse fixture to bypass wrapper for legacy TestClient tests |
| `_reversa_sdd/review-report.md` | Edit | RBAC/Security 83% → 86% (+3) |

**Files originally listed but NOT modified** (story Files inaccurate vs codebase):
- `backend/routes/organizations.py` — no role-change or delete endpoint exists; deferred
- `backend/routes/profile.py` — no email/CPF/CNPJ PATCH endpoint exists; deferred
- `frontend/components/MfaChallengeModal.tsx` — does not exist; existing `MfaEnforcementBanner` covers all reason variants

---

## Definition of Done

- [x] Inventory completo + decisão por endpoint (`docs/audits/2026-05-mfa-coverage.md`)
- [x] Test suite green 100% — 12 new tests passing + 130/130 regression suite (mfa, lgpd, cancel_subscription, routes_subscriptions, error_handler, security_story210, payment_failed_webhook, cancel_reason_feedback)
- [~] E2E Playwright: deferred (no infra running locally; backend TestClient covers chain end-to-end; banner UX validated via MFA-EXT-001 STORY-317)
- [x] Audit log eventos visíveis Mixpanel (`mfa_challenge_satisfied` fire-and-forget em `require_mfa_high_impact`)
- [x] `review-report.md §10.4` RBAC/Security 83% → 86% (+3pts)

---

## PO Validation

**Validated by:** @po (Sarah)
**Date:** 2026-05-09
**Verdict:** GO
**Score:** 9/10
**Status transition:** Draft → Ready

### 10-Point Checklist

| # | Criterion | ✓/✗ | Notes |
|---|-----------|-----|-------|
| 1 | Clear and objective title | ✓ | MFA Enforcement Extended Coverage |
| 2 | Complete description | ✓ | Lista endpoints high-impact específicos faltantes |
| 3 | Testable acceptance criteria | ✓ | AC1 inventory, AC2 apply, AC3 tests + E2E, AC4 audit log |
| 4 | Well-defined scope | ✓ | "step-up auth" reuso de MFA-EXT-001 (não nova policy) |
| 5 | Dependencies mapped | ✓ | MFA-EXT-001 Done + RBAC-ORG-002 (preferencial) |
| 6 | Complexity estimate | ✓ | S (4-8h) realista para extension pattern existente |
| 7 | Business value | ✓ | Sec +3 (gap composite 100%); reduz risco fraud high-impact actions |
| 8 | Risks documented | ✗ | Falta nota: dependência soft RBAC-ORG-002 (org owner role-change endpoint) — start sem ele pode causar rework. PO recomenda gate até RBAC-ORG-002 P0 endpoints fixed (AC2) |
| 9 | Criteria of Done | ✓ | 4 itens DoD claros |
| 10 | Alignment with PRD/Epic | ✓ | EPIC-TD-2026Q2 RBAC/security + ADR mfa-policy.md |

**Required Fix (non-blocker):** Gate AC2 inicio até RBAC-ORG-002 fixed P0 endpoints. Dev pode começar AC1 inventory paralelo.

### Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2026-05-08 | 1.0 | Story criada (SM) | @sm |
| 2026-05-09 | 1.1 | PO validation GO 9/10 — Draft → Ready (gate AC2 dep RBAC-ORG-002 non-blocker) | @po |
| 2026-05-09 | 1.2 | Implementation complete: 5 endpoints wired (billing-portal, change-password, /me delete, sub cancel, sub update-billing-period); 12 tests green; review-report +3pts. Status InReview. Frontend trigger deferred (banner already universal); E2E Playwright deferred. | @dev |
