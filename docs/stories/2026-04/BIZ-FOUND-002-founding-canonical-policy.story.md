# BIZ-FOUND-002: Founding Customer Canonical Policy (cap + deadline + race guard + admin)

**Status:** InReview
**Origem:** Reversa Audit 2026-04-27 (`_reversa_sdd/review-report.md` Gap-2) + `_reversa_sdd/sm-briefing.md` §2.4
**Prioridade:** P0 — deadline 2026-05-30 (32 days)
**Complexidade:** S (1 dia conforme spec — alongado para 5–7h aqui pelo escopo full-stack + race guard)
**Owner:** @dev (AIOX dispatch)
**Tipo:** Billing / Revenue Foundation
**Epic:** EPIC-REVENUE-2026-Q2 (companion of STORY-BIZ-001)

---

## Contexto

STORY-BIZ-001 (Done) shipped o landing `/founding` + rota `POST /v1/founding/checkout` com cupom Stripe `FOUNDING30` (30% / 12 meses / first-transaction restriction, 10 usos). A story **não** fixou a política canonical — sem cap em DB, sem deadline, sem race guard, sem admin UI, sem compromisso documentado de pricing vitalício. Reversa Audit Gap-2 sinaliza: *"pricing? deadline? cap (early-adopter limitada)?"*.

Esta story (Sprint companion) implementa a política canonical em código + DB + ADR — substitui a configuração ad-hoc.

---

## Decisão

| Setting       | Value                       | Source |
|---------------|-----------------------------|--------|
| Seat cap      | **50**                      | Aumentado de 10 (STORY-BIZ-001) — runway até deadline. |
| Deadline      | **2026-05-30 23:59:59 -03:00** | 32 dias do start. |
| Discount      | **50% off vitalício**       | Substitui o 30%/12 meses inicial. |
| Coupon Stripe | `FOUNDING_LIFETIME` (`percent_off=50, duration=forever`) | Provisionado idempotente via script. |
| Cap counting  | `founding_leads.checkout_status='completed'` | Decoupled de `profiles.plan_type` (FK constraint). |
| Race guard    | RPC `check_founding_availability()` (SELECT FOR UPDATE) + webhook re-check + auto-refund | — |

ADR completo: [`docs/adr/ADR-BIZ-FOUND-002-founding-policy.md`](../../adr/ADR-BIZ-FOUND-002-founding-policy.md).

---

## Critérios de Aceite

### Database (Supabase)

- [x] **AC1:** Migration `supabase/migrations/20260428100000_founding_canonical_policy.sql` cria tabela `public.founding_policy` com PK single-row (`id INT DEFAULT 1 CHECK (id = 1)`).
- [x] **AC2:** Migration seed insere `(id=1, seat_limit=50, deadline_at='2026-05-30T23:59:59-03:00', discount_pct=50, coupon_code='FOUNDING_LIFETIME', active=true)`.
- [x] **AC3:** RLS — read público, write apenas service-role.
- [x] **AC4:** `.down.sql` pareado idempotente (DROP FUNCTION antes de DROP TABLE; reversão de CHECK constraint do `founding_leads.checkout_status`).
- [x] **AC5:** Migration `supabase/migrations/20260428100100_check_founding_availability_rpc.sql` cria RPC `check_founding_availability()` com `SELECT FOR UPDATE` no row do policy + COUNT em `founding_leads`.
- [x] **AC6:** RPC retorna `{available, seats_remaining, seats_total, deadline_at, paused, reason}` com `reason` enum estável (`available | founding_cap_reached | founding_deadline_passed | founding_paused | founding_disabled | founding_policy_missing`).
- [x] **AC7:** RPC GRANT EXECUTE para `service_role, authenticated, anon`.
- [x] **AC8:** `founding_leads.checkout_status` CHECK estendido para incluir `'cap_violated'` (race guard webhook).

### Backend — Route gate

- [x] **AC9:** `routes/founding.py::POST /v1/founding/checkout` chama RPC ANTES de criar lead row.
- [x] **AC10:** Quando RPC retorna `available=false`, route responde `410 Gone` com payload `{message, error_code, seats_total, seats_remaining}` — `error_code` mapeia ao reason enum.
- [x] **AC11:** Default `FOUNDING_COUPON_ID` env atualizado para `FOUNDING_LIFETIME` (era `FOUNDING30`).
- [x] **AC12:** Route nova `GET /v1/founding/availability` (público, sem auth) retorna `{available, seats_total, seats_remaining, seats_taken, deadline_at, paused, reason, coupon_code, discount_pct}` para landing-page seat counter + countdown.

### Backend — Webhook race guard

- [x] **AC13:** `webhooks/handlers/founding.py::mark_founding_lead_completed` re-executa RPC APÓS marcar `completed`.
- [x] **AC14:** Se RPC retorna `founding_cap_reached`, handler:
    - Reverte row para `checkout_status='cap_violated'`.
    - Chama `stripe.Refund.create(payment_intent=..., reason='duplicate', metadata={source:'founding', reason:'cap_violation_race'})`.
    - Enfileira email apologético via `email_service.send_email_async`.
    - Loga `level=error` (Sentry alert).
- [x] **AC15:** Race guard NÃO refunda em outras razões (`paused`, `deadline_passed`, `disabled`, `missing`) — só logging.
- [x] **AC16:** RPC unavailable (None) → fail closed: skip refund (nunca reverter cliente pagante por DB flaky).

### Backend — Admin endpoints

- [x] **AC17:** Novo módulo `backend/routes/admin_founding.py` com prefix `/v1/admin/founding`.
    - `GET /policy` → snapshot policy + `seats_taken` + `completion_pct`.
    - `GET /leads?limit=N&status=...` → lista founding_leads ordenada desc.
    - `POST /pause` (body `{reason?}`) → set `paused_at=NOW(), paused_by=admin.id, paused_reason=...`.
    - `POST /resume` → clear pause fields.
- [x] **AC18:** Todos os endpoints exigem `Depends(require_admin)`.
- [x] **AC19:** Router registrado em `backend/startup/routes.py::register_routes` como self-prefixed (igual `admin_cron_router`).

### Frontend — Landing page

- [x] **AC20:** `frontend/app/founding/page.tsx` (server) atualiza metadata: `description` reflete 50 vagas + 50% vitalício.
- [x] **AC21:** `FoundingClient.tsx` faz fetch ao `GET /api/founding/availability` no mount (anônimo) e passa snapshot para `<FoundingForm>` + countdown component.
- [x] **AC22:** Countdown timer (computed from `deadline_at`) refresh a cada 60s; mostra dias/horas/minutos restantes.
- [x] **AC23:** Seat counter `X/50 vagas restantes` exibido visivelmente; visual changes quando `seats_remaining ≤ 5` (urgência).
- [x] **AC24:** CTA disable quando `available=false`; mensagem específica por `reason`.
- [x] **AC25:** Body copy refreshed: 50 vagas (era 10), 50% off vitalício (era 30% / 12 meses), R$ 198,50/mês (era R$ 277,90).

### Frontend — Admin page

- [x] **AC26:** Nova page `frontend/app/admin/founding/page.tsx` (CSR, admin-only via `useAuth()`).
- [x] **AC27:** Progress bar visual (X/50 + completion %).
- [x] **AC28:** Tabela founding leads (email, nome, CNPJ, status, created_at).
- [x] **AC29:** Toggle pause/resume com confirmação.

### Provisioner

- [x] **AC30:** Script `scripts/create_founding_lifetime_coupon.py` idempotente:
    - Retrieve coupon → se existe + config compatível, exit 0.
    - Se não existe, create com `id='FOUNDING_LIFETIME'`, `percent_off=50`, `duration='forever'`.
    - `--dry-run` flag para CI.

### Documentação

- [x] **AC31:** ADR `docs/adr/ADR-BIZ-FOUND-002-founding-policy.md` documenta: cap=50, deadline=2026-05-30, lifetime=true, cap counting via `founding_leads`, race guard architecture, alternativas consideradas.

### Tests

- [x] **AC32:** `backend/tests/test_founding_canonical_policy.py` cobre:
    - RPC mock retornando `founding_cap_reached` → route responde 410 com `error_code='founding_cap_reached'`.
    - RPC mock retornando `founding_deadline_passed` → route responde 410 com `error_code='founding_deadline_passed'`.
    - RPC mock retornando `available=true` → route segue happy path para Stripe checkout.
    - `GET /v1/founding/availability` → retorna shape esperado.
- [x] **AC33:** `backend/tests/test_founding_webhook_race_guard.py` cobre:
    - Cap violation race: 1ª RPC `available=true` (pre-check), 2ª RPC `founding_cap_reached` (post-completion) → handler refunda + envia email + reverte para `cap_violated`.
    - RPC unavailable post-completion → handler skip refund (fail closed).
    - Reason `paused` post-completion → handler NÃO refunda (estrutural).
- [x] **AC34:** `backend/tests/test_admin_founding.py` cobre:
    - `GET /policy` requires admin (403 sem auth).
    - `POST /pause` seta `paused_at`, `POST /resume` limpa.
    - `GET /leads?status=completed` filtra corretamente.
- [x] **AC35:** Tests existentes em `backend/tests/test_founding_checkout.py` continuam passando (zero regressão) — mock RPC para `available=true` quando integração testar happy path.
- [x] **AC36:** Frontend test `frontend/__tests__/founding/FoundingForm.test.tsx` continua passando (race guard test reutiliza fetch mock).

---

## Constraints & Dependencies

- **Wave depends on:** Waves A+B (DATA-CNAE-001, RBAC-ORG-001, BIZ-METRIC-001, BILL-SYNC-001) merged into `feat/reversa-batch-2026-04-28`. Confirmed.
- **Stripe coupon:** `FOUNDING_LIFETIME` precisa ser provisionado em prod via `python scripts/create_founding_lifetime_coupon.py` ANTES do deploy.
- **Migration order:** RPC down (`20260428100100_*.down.sql`) MUST run BEFORE policy table down — function references the table.

---

## File List

### Created
- `supabase/migrations/20260428100000_founding_canonical_policy.sql`
- `supabase/migrations/20260428100000_founding_canonical_policy.down.sql`
- `supabase/migrations/20260428100100_check_founding_availability_rpc.sql`
- `supabase/migrations/20260428100100_check_founding_availability_rpc.down.sql`
- `backend/routes/admin_founding.py`
- `backend/tests/test_founding_canonical_policy.py`
- `backend/tests/test_founding_webhook_race_guard.py`
- `backend/tests/test_admin_founding.py`
- `frontend/app/admin/founding/page.tsx`
- `frontend/app/api/founding/availability/route.ts`
- `frontend/__tests__/founding/FoundingCountdown.test.tsx`
- `scripts/create_founding_lifetime_coupon.py`
- `docs/adr/ADR-BIZ-FOUND-002-founding-policy.md`
- `docs/stories/2026-04/BIZ-FOUND-002-founding-canonical-policy.story.md`

### Modified
- `backend/routes/founding.py` — gate via RPC + new `GET /availability` + 410 responses with `error_code`.
- `backend/webhooks/handlers/founding.py` — race guard with refund + email.
- `backend/startup/routes.py` — register `admin_founding_router`.
- `backend/tests/test_founding_checkout.py` — mock RPC for `available=true` on integration tests.
- `frontend/app/founding/page.tsx` — metadata refresh (50 vagas, 50% vitalício).
- `frontend/app/founding/FoundingClient.tsx` — fetch availability + countdown + seat counter.
- `frontend/app/founding/components/FoundingForm.tsx` — disable CTA when unavailable.

---

## Notes

- Cap counting basis (`founding_leads.checkout_status='completed'`) **deviates from task brief wording** ("COUNT(profiles WHERE plan_type='founding')"). Reason: `profiles.plan_type` is FK to `plans` (DEBT-05), and STORY-BIZ-001 already activates founding subscribers as `'smartlic_pro'`. Adding a `'founding'` plan row would couple billing taxonomy to cohort marketing for no operational benefit. Documented in ADR §"Cap counting basis".
- Stripe coupon `FOUNDING30` stays valid in Stripe (Stripe never deletes coupons referenced by past subscriptions). New flows use `FOUNDING_LIFETIME`. Old default flipped via env.
