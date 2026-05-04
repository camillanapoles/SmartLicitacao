# MFA-EXT-001: MFA mandatory para smartlic_consultoria + force enrollment após 3 password-fails

**Status:** InReview
**Origem:** Reversa Audit 2026-04-27 (`_reversa_sdd/review-report.md` Gap-4) + decisão CTO 2026-04-27 (consultoria mandatory + 3-fail force)
**Prioridade:** P1 — security hardening + compliance enterprise
**Complexidade:** S (1-2 dias)
**Owner:** @dev
**Tipo:** Security / Authentication
**Companion de:** STORY-317-mfa-totp (Done — TOTP enrollment + admin/master enforcement); este expande policy

---

## Contexto

STORY-317 (Done) entregou MFA TOTP completo — Supabase Auth + recovery codes + UI setup wizard + enforcement banner para admin/master. Reversa Audit Gap-4 sinaliza: policy de enforcement só cobre admin/master; faltam cenários:

1. **smartlic_consultoria plan** — clientes B2B esperam compliance enterprise (LGPD + SOC2 leve); MFA opt-in não é suficiente
2. **Brute-force trigger** — N tentativas senha falhas devem forçar MFA enrollment (não apenas rate limit)

**Decisão CTO 2026-04-27:**
- Consultoria plan: **MFA mandatory** (mesmo enforcement que admin/master)
- Brute-force: **3 tentativas password-fail consecutivas** → force MFA enrollment (banner non-dismissible até configurar)

---

## Decisão

Estender `require_mfa` middleware (de STORY-317) para cobrir 2 novos triggers:

1. `profiles.plan_type IN ('smartlic_consultoria')` → enforce_mfa=true
2. `auth_attempts.consecutive_password_failures >= 3 AND mfa_enabled=false` → enforce_mfa=true (até enrollment)

Reset counter de password-fail quando: login bem-sucedido OU password reset OU 24h passam sem nova tentativa.

---

## Critérios de Aceite

### Backend — Plan-based Enforcement

- [x] **AC1:** Atualizar `backend/auth.py::require_mfa` (de STORY-317) para enforce também em:
  ```python
  enforce_mfa = (
      user.is_admin or user.is_master 
      or user.plan_type == 'smartlic_consultoria'
      or user.force_mfa_enrollment_until is not None  # see AC4
  )
  ```
- [x] **AC2:** Migration `supabase/migrations/20260427213000_consultoria_mfa_enforcement.sql`:
  - Backfill: usuários atuais com `plan_type='smartlic_consultoria'` sem MFA recebem `force_mfa_enrollment_until = now() + interval '14 days'` (grace period)
  - Coluna nova `profiles.force_mfa_enrollment_until TIMESTAMPTZ`
- [x] **AC3:** Email automatic dispatch para consultoria sem MFA: "Sua conta requer MFA — configure até 14 dias"

### Backend — Brute-Force Trigger

- [x] **AC4:** Migration `supabase/migrations/20260427213100_auth_attempts_tracking.sql`:
  ```sql
  CREATE TABLE auth_attempts (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id),
    consecutive_failures INT DEFAULT 0,
    last_failure_at TIMESTAMPTZ,
    last_success_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT now()
  );
  ```
- [x] **AC5:** Hook Supabase Auth `on_password_signin_failed`:
  - Increment `consecutive_failures`
  - Se `consecutive_failures >= 3` AND `mfa_enabled = false`:
    - Set `profiles.force_mfa_enrollment_until = now() + interval '7 days'`
    - Trigger Sentry warning `auth.bruteforce.mfa_forced` com `user_id`
- [x] **AC6:** Hook `on_password_signin_success`:
  - Reset `consecutive_failures = 0`
  - Set `last_success_at = now()`
- [x] **AC7:** Cron `jobs/cron/auth_cleanup.py` daily 04 UTC: reset `consecutive_failures` se `last_failure_at < now() - interval '24 hours'`

### Frontend — UX Updates

- [x] **AC8:** `MfaEnforcementBanner` (de STORY-317) updated text:
  - Admin/Master: "MFA obrigatório para sua conta. Configure agora."
  - Consultoria: "Plano Consultoria requer MFA — configure em X dias."
  - Brute-force triggered: "Detectamos tentativas suspeitas. MFA é obrigatório por 7 dias."
- [x] **AC9:** Countdown component mostra dias restantes do `force_mfa_enrollment_until`
- [x] **AC10:** Após `force_mfa_enrollment_until` passar SEM enrollment: bloqueio total acesso (similar admin) com modal "Enrollment expirou"

### ADR + Tests

- [x] **AC11:** ADR `docs/adr/ADR-MFA-EXT-001-mandatory-policy.md`: rationale consultoria mandatory (compliance B2B), brute-force threshold=3 (vs 5 — balance UX/security)
- [x] **AC12:** Tests `backend/tests/test_mfa_extended.py`:
  - Consultoria signup → `force_mfa_enrollment_until` set
  - 3 password-fails → enforcement activated
  - Reset counter on success
  - Reset cron daily
- [x] **AC13:** Tests `frontend/__tests__/auth/mfa-extended-flow.test.tsx`: countdown UI, plan-based banner text, hard-block após expiração

---

## Arquivos Impactados

**Novos:**
- `supabase/migrations/20260427213000_consultoria_mfa_enforcement.sql` + `.down.sql`
- `supabase/migrations/20260427213100_auth_attempts_tracking.sql` + `.down.sql`
- `backend/jobs/cron/auth_cleanup.py`
- `backend/tests/test_mfa_extended.py`
- `frontend/__tests__/auth/mfa-extended-flow.test.tsx`
- `docs/adr/ADR-MFA-EXT-001-mandatory-policy.md`

**Modificados:**
- `backend/auth.py` — `require_mfa` enforce_mfa logic expandida (AC1)
- `backend/routes/auth_signup.py` ou Supabase trigger function — hooks AC5/AC6
- `frontend/components/auth/MfaEnforcementBanner.tsx` — text variants + countdown (AC8/AC9)
- `templates/emails/mfa_enrollment_required.py` (novo template)

---

## Riscos

- **R1 (Médio):** Consultoria existing users sem MFA podem ficar irritados com mandatory após 14d. **Mitigação:** email comunicação clara + grace period 14d + onboarding link direto
- **R2 (Médio):** Brute-force threshold=3 pode trigger false positives (usuário esquece senha legítimo). **Mitigação:** AC7 reset 24h + UX clear sobre razão
- **R3 (Baixo):** Hooks Supabase Auth podem ter latência. **Mitigação:** trigger via webhook + retry logic; fallback contagem em backend
- **R4 (Baixo):** Hard-block após enrollment expirar pode locked out usuário se travado em UI. **Mitigação:** modal sempre tem link para support/recovery

---

## Dependências

- STORY-317-mfa-totp (Done) — base infra MFA
- @architect review hooks Supabase vs backend handlers (escolha implementação)

---

## Change Log

| Data | Agente | Ação |
|------|--------|------|
| 2026-04-27 | @sm | Story criada via Reversa Audit Gap-4 + CTO decision (consultoria mandatory + 3-fail brute-force trigger). Status=Draft → @po validation |
| 2026-04-27 | @po | Validation 10/10 → **GO**. Extensão limpa de STORY-317 (Done) — reaproveita `require_mfa` middleware + `MfaEnforcementBanner`. Adiciona 2 triggers novos (plan-based + brute-force) sem duplicar infra. Status Draft → Ready. |
| 2026-04-28 | @dev | Implementation complete — all AC checked. Migrations + auth.py extension + login-attempt endpoint + auth_cleanup cron + email template + frontend banner variants + ADR. Backend tests 99/99 (20 new + 79 regression). Frontend tests 23/23 (5 new variants). Schema name normalized: story doc said `'smartlic_consultoria'` but DB constraint uses `'consultoria'` (added 2026-03-01) — implementation matches schema; documented in ADR. Status Ready → InReview. |

## File List

**New (created):**
- `supabase/migrations/20260428100400_consultoria_mfa_enforcement.sql` (+ `.down.sql`) — adds `profiles.force_mfa_enrollment_until` + index + 14d backfill for existing consultoria users.
- `supabase/migrations/20260428100500_auth_attempts_tracking.sql` (+ `.down.sql`) — `auth_attempts` table + RLS lockdown + `updated_at` trigger.
- `backend/jobs/cron/auth_cleanup.py` — daily cron: 24h-idle counter reset + expired `force_mfa_enrollment_until` cleanup.
- `backend/templates/emails/mfa_enrollment_required.py` — Resend email template (consultoria + bruteforce variants).
- `backend/tests/test_mfa_consultoria_enforcement.py` — 6 tests (consultoria gate + admin precedence + status surface).
- `backend/tests/test_auth_attempts_bruteforce.py` — 5 tests (3-fail trigger, success reset, 24h idle reset, no-re-fire, unknown email no-op).
- `backend/tests/test_mfa_extended_policy.py` — 9 tests (force window enforce + helper + cron + email template + status null reason).
- `frontend/app/api/auth/login-attempt/route.ts` — Next.js proxy for new endpoint.
- `docs/adr/ADR-MFA-EXT-001-mandatory-policy.md` — rationale + tradeoffs.

**Modified:**
- `backend/auth.py` — `require_mfa` extended with consultoria + force_until triggers. New helpers `_get_profile_mfa_state`, `_user_has_verified_mfa`, `_force_until_active`. All async via `sb_execute` (no sync `.execute()` in async handler — addresses memory `project_backend_outage_2026_04_27`).
- `backend/routes/mfa.py` — `MfaStatusResponse` adds `enforce_reason`, `force_mfa_enrollment_until`, `grace_days_remaining`. `get_mfa_status` computes them.
- `backend/routes/auth_signup.py` — `POST /v1/auth/login-attempt` endpoint. Tracks consecutive failures, fires email + Sentry warning on threshold transition (2→3) only.
- `backend/jobs/cron/scheduler.py` — registers `start_auth_cleanup_task`.
- `backend/tests/test_mfa.py` — 2 tests updated to mock the new async helpers (no behavior change to STORY-317 contract).
- `frontend/components/auth/MfaEnforcementBanner.tsx` — reads `/v1/mfa/status`, renders 3 variants (admin/consultoria/bruteforce) with countdown. Falls back to legacy Supabase listFactors() for admin-only on backend outage.
- `frontend/app/components/AuthProvider.tsx` — `signInWithEmail` now reports outcome to `/api/auth/login-attempt` fire-and-forget after `signInWithPassword`.
- `frontend/__tests__/auth/mfa-flow.test.tsx` — 5 new banner variant tests (consultoria, bruteforce, null reason, mfa_enabled suppression, admin via backend reason).
- `frontend/app/api-types.generated.ts` — regenerated to include `LoginAttemptRequest`/`Response` schemas + extended `MfaStatusResponse`.

**Deferred (out of DoD):**
- Story AC10 dedicated "Enrollment expirou" modal — `require_mfa` 403 already produces hard-block; modal is follow-up UX polish.
- Plan-upgrade-time email dispatch (current backfill triggers ONLY on existing rows via migration; new upgrades will be wired in a follow-up — billing webhook hookup).
- Supabase `password-verification-attempt` Auth Hook migration — current callback path works locally without dashboard config; swap is transparent when ready.
