# MFA-EXT-001: MFA Enforcement Policy — Consultoria Mandatory + Bruteforce Trigger

**Priority:** P1 (segurança gate)
**Effort:** M (3-4 dias)
**Squad:** @dev + @architect
**Status:** Ready
**Epic:** [EPIC-MON-SUBS-2026-04](EPIC-MON-SUBS-2026-04.md) ou EPIC-RES-BE
**Sprint:** Sprint 3 (após user input)
**Dependências bloqueadoras:** STORY-317 MFA TOTP (status MEDIUM Sprint 3) · ADR policy decision (USER)

---

## Contexto

`backend/routes/mfa.py` 4 endpoints (Reversa code-analysis Module 6). MFA opcional atualmente. Review-report.md Gap-4: política não-documentada. Quando MFA é obrigatório? Triggers?

Memory `reference_admin_bypass_paywall` registra: `is_admin=True` ignora trial/quota. Admin role sem MFA = security risk maior.

`routes/mfa.py:10` callsites com `.execute()` async antipattern (REF-SCALE-001 batch 3) — paralelo.

---

## User Input — RESPONDIDO 2026-04-28

| # | Pergunta | Resposta |
|---|----------|----------|
| Q1 | MFA mandatory `is_admin=True`? | **Sim** |
| Q2 | MFA mandatory `is_master=True`? | **Sim** |
| Q3 | MFA mandatory `consultoria` plan? | **Sim** (multi-user org business-critical) |
| Q4 | MFA mandatory `smartlic_pro`? | **Não** (opt-in user choice) |
| Q5 | Bruteforce trigger | **5 falhas em 15min** → próxima tentativa requer MFA |
| Q6 | Novo IP trigger | **Country-level** (geolocation país difere de last login) |
| Q7 | Recovery codes | **10 single-use** |

Detalhes em ADR `docs/adr/mfa-policy.md` (criado).

---

## Acceptance Criteria (pós-input)

### AC1: ADR policy

- [ ] `docs/adr/mfa-policy.md` documenta Q1-Q7

### AC2: Plan-based mandatory enforcement

- [ ] `backend/auth.py::require_auth` adiciona check pós JWT validation:
  - SELECT user.is_admin, is_master, plan_type
  - Se policy require MFA + user.mfa_enabled=False → HTTP 403 + redirect /conta/mfa/setup
- [ ] Admin/master/consultoria login flow: força setup MFA se ainda não-enabled

### AC3: Bruteforce trigger

- [ ] `backend/auth.py` track failed attempts em Redis: `bruteforce:{user_id}` counter TTL 15min
- [ ] Pós N=Q5 falhas → require MFA enforce na próxima tentativa (mesmo se policy normal não exige)
- [ ] Reset counter on success

### AC4: New IP trigger (Q6)

- [ ] `last_login_ip` em `profiles` table (migration adicionar coluna)
- [ ] Compare IP geolocation pais nivel; if differs → require MFA challenge

### AC5: Recovery codes

- [ ] `mfa_recovery_codes` table (existing per CLAUDE.md DB-005)
- [ ] Generate Q7=10 codes on MFA setup
- [ ] Single-use enforcement

### AC6: Tests

- [ ] `test_mfa_policy_enforcement.py`:
  - Admin user without MFA → 403 + setup redirect
  - Pro user without MFA → 200 (opt-in)
  - 5 failed attempts → next attempt requires MFA
  - New IP → MFA challenge

### AC7: Frontend handle

- [ ] `frontend/app/login/page.tsx` handle 403 → redirect `/conta/mfa/setup`
- [ ] `frontend/app/conta/mfa/page.tsx` setup wizard

---

## Scope

**IN:** ADR + plan-based + bruteforce + new-IP + recovery codes + tests + frontend handle
**OUT:** Hardware key support (FIDO2 separate) · MFA bypass via support ticket

---

## Definition of Done

- [ ] User Q1-Q7 em ADR
- [ ] Auth pipeline enforce policy
- [ ] Bruteforce + new-IP triggers active
- [ ] 4 test scenarios pass
- [ ] Suite passa
- [ ] @po validation GO

---

## Dev Notes

- `routes/mfa.py` 4 endpoints + 10 `.execute()` callsites (REF-SCALE-001 batch 3 covers async fix)
- `auth.py:require_auth` JWT 3-strategy (JWKS ES256 > PEM > HS256)
- Redis pattern: `bruteforce:{user_id}` similar `rate_limiter.py` token bucket
- Memory `reference_admin_bypass_paywall` reforça: admin = privileged → MFA mandatory

---

## Risk & Rollback

| Trigger | Ação |
|---|---|
| Existing admin sem MFA bloqueia ao deploy | Migration phase: 7d grace window com email warn antes de enforcement hard |
| Bruteforce false-positive (legitimate user 5x typo password) | TTL 15min auto-reset; recovery via support |
| New IP triggers em VPN/mobile users | Q6 default: country-level not IP-exact; user can confirm new device once |

**Rollback:** feature flag `MFA_POLICY_ENFORCED=false` (default true post-deploy); revert to opt-in se issue crítico.

---

## Dependencies

**Entrada:** User Q1-Q7 · STORY-317 MFA TOTP
**Saída:** habilita compliance enterprise / consultoria sales

---

## PO Validation

**Validated by:** @po (Pax)
**Date:** 2026-04-28
**Verdict:** GO
**Score:** 10/10

### 10-Point Checklist

| # | Criterion | ✓/✗ | Notes |
|---|-----------|-----|-------|
| 1 | Clear and objective title | ✓ | Consultoria mandatory + bruteforce trigger explícito. |
| 2 | Complete description | ✓ | Q1-Q7 respondidos; memory `reference_admin_bypass_paywall` reforça blast radius. |
| 3 | Testable acceptance criteria | ✓ | 7 ACs com 4 test scenarios (admin, pro, bruteforce, new IP). |
| 4 | Well-defined scope | ✓ | OUT exclude FIDO2 + bypass via support. |
| 5 | Dependencies mapped | ✓ | STORY-317 MFA TOTP. |
| 6 | Complexity estimate | ✓ | M (3-4d). |
| 7 | Business value | ✓ | Compliance enterprise/consultoria sales gate. |
| 8 | Risks documented | ✓ | 7d grace window pré-enforcement hard. |
| 9 | Criteria of Done | ✓ | 5 itens. |
| 10 | Alignment with PRD/Epic | ✓ | EPIC-MON-SUBS ou EPIC-RES-BE. |

Status: Blocked → Ready.

---

## Change Log

| Data | Versão | Descrição | Autor |
|---|---|---|---|
| 2026-04-28 | 1.0 | Story criada — recria fictícia state.json sm_handoff. Bloqueada user input Q1-Q7. Origem: `_reversa_sdd/sm-briefing-refactor.md` + sm-briefing.md sec.2.3 + review-report.md Gap-4. | @sm (River) |
| 2026-04-28 | 1.1 | User input Q1-Q7 respondidas: admin+master+consultoria mandatory, pro opt-in, bruteforce 5/15min, country-level new-IP, 10 recovery codes. ADR `docs/adr/mfa-policy.md` criado. PO validation: GO (10/10). Status: Blocked → Ready. | @po (Pax) |
