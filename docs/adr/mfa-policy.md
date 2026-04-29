# ADR: MFA Enforcement Policy

**Status:** Accepted
**Date:** 2026-04-28
**Decisão:** User via AskUserQuestion
**Story:** [MFA-EXT-001](../stories/2026-04/MFA-EXT-001-consultoria-mandatory-and-bruteforce-trigger.story.md)

---

## Context

`backend/routes/mfa.py` 4 endpoints, MFA opcional atualmente. Review-report.md Gap-4: política não-documentada. Memory `reference_admin_bypass_paywall`: `is_admin=True` ignora trial/quota — admin sem MFA = security risk maior.

## Decision

### Mandatory enforcement por role/plan

| Conta | MFA Status |
|-------|-----------|
| `is_admin=True` | **MANDATORY** |
| `is_master=True` | **MANDATORY** |
| `plan_type='consultoria'` | **MANDATORY** (multi-user org business-critical) |
| `plan_type='smartlic_pro'` | Opt-in user choice |
| `plan_type='founding_member'` | Opt-in user choice |
| `plan_type='free_trial'` | Opt-in user choice |

### Bruteforce trigger

- **5 failed login attempts em 15min window** → próxima tentativa requer MFA mesmo se policy normal não exige
- Counter Redis: `bruteforce:{user_id}` TTL 15min
- Reset on successful login

### New IP / Geolocation trigger

- **Country-level** geolocation comparison (last_login_country vs current_request_country)
- Se country differs → step-up MFA challenge required
- VPN/mobile users entre países: false-positive aceitável (re-confirm device once)

### Recovery codes

- **10 single-use codes** generated on MFA setup
- Stored hashed em `mfa_recovery_codes` table
- LGPD-compatible: user pode regenerate (invalidate previous)

## Consequences

### Positivas
- Admin/master account takeover prevention (blast radius máximo)
- Consultoria plan compliance enterprise-grade
- Bruteforce mitigation sem hard-lockout (UX preserve)
- Country-level trigger evita VPN false-positive vs IP-exact

### Negativas
- Friction signup consultoria (mandatory setup)
- 7d grace window pré-enforcement hard para existing admin sem MFA (migration phase)
- 10 codes = user storage burden; perda = lockout risk (mitigation: regenerate via support)

### Implementação (MFA-EXT-001)

- `backend/auth.py::require_auth` adiciona check pós-JWT validation
- Plan-based policy: SELECT user.is_admin, is_master, plan_type → enforce per ADR table
- Bruteforce: Redis counter `bruteforce:{user_id}` com pattern similar `rate_limiter.py`
- New IP: `last_login_ip` + `last_login_country` em `profiles` table (migration)
- Recovery codes: existing `mfa_recovery_codes` table (CLAUDE.md DB-005)
- Frontend `/conta/mfa/setup` wizard

## Monitoring

- Mixpanel event `mfa_bruteforce_triggered` per occurrence
- Sentry alert em new-IP false-positive spike (signal de geolocation wrong)
- Admin dashboard `/v1/admin/mfa-coverage` (separate STORY)

## Revision

ADR canonical até policy mudar. Adicionar FIDO2/hardware key = future ADR + new STORY.
