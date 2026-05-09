# MFA-ENFORCE-EXT-001: MFA Enforcement Extended Coverage (post MFA-EXT-001)

**Priority:** P2
**Effort:** S (4-8h)
**Squad:** @dev (lead) + @qa
**Status:** Ready
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

- [ ] Listar endpoints que mudam estado high-impact (delete, role-change, financial)
- [ ] Cross-ref com ADR mfa-policy.md decision tree
- [ ] Output: tabela endpoint → decisão (require MFA / skip / N/A)

### AC2: Apply `require_mfa` dependency

- [ ] Para cada endpoint marcado "require": aplicar dependency FastAPI `require_mfa` (existente de MFA-EXT-001)
- [ ] Frontend: trigger step-up modal (Supabase Auth MFA challenge) antes de chamar endpoint
- [ ] 401 response code se MFA challenge não satisfeito (não 403 — UX pivot p/ challenge)

### AC3: Test coverage

- [ ] `backend/tests/test_mfa_enforcement_extended.py` — test cada endpoint novo
- [ ] E2E Playwright: org owner mudando role → MFA prompt → success path

### AC4: Audit log

- [ ] Endpoints MFA-required logam audit event (Mixpanel `mfa_challenge_satisfied` + Supabase audit table se existir)

---

## Files

| Arquivo | Ação |
|---------|------|
| `backend/routes/organizations.py` | Edit (apply `require_mfa`) |
| `backend/routes/profile.py` | Edit |
| `backend/routes/billing.py` | Edit |
| `frontend/components/MfaChallengeModal.tsx` | Edit (extend triggers) |
| `backend/tests/test_mfa_enforcement_extended.py` | Create |

---

## Definition of Done

- [ ] Inventory completo + decisão por endpoint
- [ ] Test suite green 100%
- [ ] E2E Playwright PASS
- [ ] Audit log eventos visíveis Mixpanel
- [ ] `review-report.md §10.4` score +3pts target

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
