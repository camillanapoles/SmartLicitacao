# BIZ-FOUND-002: Founding Plan Canonical Policy + Cap Enforcement

**Priority:** P0 (deadline 2026-05-30 — 32 dias)
**Effort:** S (1d pós-input) + M (3d implementação)
**Squad:** @pm + @dev + @data-engineer
**Status:** Ready
**Epic:** [EPIC-REVENUE-2026-Q2](EPIC-REVENUE-2026-Q2/)
**Sprint:** Sprint 1-2 (após user input)
**Dependências bloqueadoras:** STORY-BIZ-001 (Done — Stripe coupon implementado) · ADR pendente user input

---

## Contexto

`STORY-BIZ-001` (Done) implementou Stripe coupon + abandonment tracking via `checkout.session.expired`. Mas **não fixou** policy canonical: cap de seats, deadline absoluto, lifetime price guarantee. Sem cap, signups acima do break-even consomem unit economics negativos. Memory `state.json sm_handoff` registrou deadline 2026-05-30 (33d, agora 32d).

`backend/services/billing.py:PLAN_CAPABILITIES` define `founding_member` com mesma capabilities `smartlic_pro` por R$197/mês (50% off). `routes/founding.py` 239L tem `POST /v1/founding/checkout` mas sem enforcement de cap.

`founding_leads` table existe; `founding` plan_type em uso.

---

## User Input — RESPONDIDO 2026-04-28

| # | Pergunta | Resposta |
|---|----------|----------|
| Q1 | Cap de seats founding? | **50 seats** |
| Q2 | Deadline absoluto? | **2026-05-30** (32d a partir 2026-04-28) |
| Q3 | Lifetime price guarantee? | **Permanente enquanto subscription ativa** (R$197/mês indefinidamente até cancel) |
| Q4 | Comportamento pós-cap reached? | **HTTP 410 + redirect /pricing** |
| Q5 | Comportamento pós-deadline? | **Mantém R$397/mês** (soft transition, sem 410) |

Detalhes em ADR `docs/adr/founding-plan-canonical.md` (criado).

---

## Acceptance Criteria (pós-user input)

### AC1: ADR canonical

- [ ] `docs/adr/founding-plan-canonical.md` registra: cap (Q1), deadline (Q2), lifetime guarantee (Q3), pós-cap behavior (Q4), pós-deadline behavior (Q5)
- [ ] Linked from CLAUDE.md "Billing & Auth" section

### AC2: `founding_caps` table

- [ ] Migration `supabase/migrations/YYYYMMDDHHMMSS_founding_caps.sql`:
  ```sql
  CREATE TABLE founding_caps (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    seat_limit INTEGER NOT NULL,
    current_seats INTEGER NOT NULL DEFAULT 0,
    deadline_at TIMESTAMPTZ NOT NULL,
    lifetime_price_cents INTEGER NOT NULL DEFAULT 19700,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
  );
  INSERT INTO founding_caps VALUES (1, <Q1>, 0, '<Q2>'::timestamptz, 19700, NOW());
  ```
- [ ] Paired `.down.sql` rollback
- [ ] Trigger increment `current_seats` on `user_subscriptions` insert where `plan_type='founding_member'`

### AC3: Cap enforcement em `POST /v1/founding/checkout`

- [ ] `backend/routes/founding.py` valida ANTES de criar Stripe session:
  - SELECT `current_seats, seat_limit, deadline_at` FROM `founding_caps`
  - Se `current_seats >= seat_limit` → HTTP 410 GONE com body `{"reason": "cap_reached", "next": "/pricing"}` (Q4)
  - Se `NOW() > deadline_at` → HTTP 410 GONE (Q5 default)
- [ ] Race-free check: incrementar via `INSERT ON CONFLICT DO UPDATE WHERE current_seats < seat_limit`

### AC4: Admin endpoint `/v1/admin/founding-status`

- [ ] `backend/admin.py` ou `routes/admin_*.py`:
  - GET retorna `{seat_limit, current_seats, remaining, deadline_at, days_until_deadline}`
  - Permission: `is_admin OR is_master`

### AC5: Email automático

- [ ] `templates/emails/founding_deadline_reminder.py` (novo template)
- [ ] `jobs/cron/billing.py` adicionar `founding_deadline_warning` cron — 7d antes deadline, envia email aos founding members confirmando lifetime guarantee
- [ ] Validate template HTML render via `test_email_template_founding.py`

### AC6: Frontend

- [ ] `frontend/app/founding/page.tsx` consome `/v1/admin/founding-status` (sem auth — público) e mostra "X / Y seats restantes"
- [ ] Botão checkout disabled se `remaining=0`
- [ ] `frontend/components/billing/FoundingCounter.tsx` (novo)

### AC7: Tests

- [ ] `test_founding_cap_enforcement.py`: cap reached → 410, deadline passed → 410, success → 200
- [ ] Race condition: 2 requests simultâneos com `current_seats=seat_limit-1` → exatamente 1 sucede
- [ ] Migration round-trip via `.down.sql`

---

## Scope

**IN:** ADR + table + cap enforcement + admin endpoint + email reminder + frontend counter + tests
**OUT:** mudança de pricing canônico (Q3 fixa) · partner/affiliate program founding (separate STORY-323) · grandfathering legacy founding members (assume os atuais respeitam ADR)

---

## Definition of Done

- [ ] ADR + migration + paired down.sql aplicados
- [ ] Cap enforcement validado em integration test
- [ ] Admin endpoint funcional + RBAC
- [ ] Email reminder cron registered
- [ ] Frontend counter live
- [ ] Suite backend passa (0 regressions)
- [ ] User Q1-Q5 documented em ADR
- [ ] @po validation GO

---

## Dev Notes

- `routes/founding.py:239L` referência atual
- `services/billing.py:PLAN_CAPABILITIES["founding_member"]` — preço lifetime guarantee enforce vs Stripe price
- Memory `feedback_n2_below_noise_eng_theater`: pre-revenue n=2; cap baixo (≤100) defensável

---

## Risk & Rollback

| Trigger | Ação |
|---|---|
| Cap reached antes de prep marketing | Cron alert Sentry quando `remaining<=10` (P1 follow-up) |
| Lifetime guarantee conflita Stripe price update futura | ADR documenta: founding subscriptions imutáveis vs Stripe products |
| Race condition signup simultâneo | RPC atomic `INSERT ON CONFLICT DO UPDATE WHERE current_seats < seat_limit RETURNING current_seats` |

**Rollback:** revert migration + revert routes/founding.py changes; founding signups voltam sem cap (estado pre-story).

---

## Dependencies

**Entrada:** User Q1-Q5 · STORY-BIZ-001 Done (Stripe coupon)
**Saída:** habilita marketing campaign deadline-driven · habilita reporting unit economics founding cohort

---

## PO Validation

**Validated by:** @po (Pax)
**Date:** 2026-04-28
**Verdict:** GO
**Score:** 10/10

### 10-Point Checklist

| # | Criterion | ✓/✗ | Notes |
|---|-----------|-----|-------|
| 1 | Clear and objective title | ✓ | Founding canonical policy + cap enforcement explícito. |
| 2 | Complete description | ✓ | Q1-Q5 respondidos; ADR linked. |
| 3 | Testable acceptance criteria | ✓ | 7 ACs com cap enforcement race-free + admin endpoint + email reminder. |
| 4 | Well-defined scope | ✓ | OUT exclude pricing change + grandfathering. |
| 5 | Dependencies mapped | ✓ | STORY-BIZ-001 Done. |
| 6 | Complexity estimate | ✓ | S (1d) + M (3d) coerente pós-input. |
| 7 | Business value | ✓ | P0 deadline 2026-05-30, 32d. Unit econ protection. |
| 8 | Risks documented | ✓ | Race-free RPC + Sentry alarm remaining<=10. |
| 9 | Criteria of Done | ✓ | 7 itens. |
| 10 | Alignment with PRD/Epic | ✓ | EPIC-REVENUE-2026-Q2 + ADR canonical. |

Status: Blocked → Ready.

---

## Change Log

| Data | Versão | Descrição | Autor |
|---|---|---|---|
| 2026-04-28 | 1.0 | Story criada via `/sm crie todas stories` — recria fictícia state.json sm_handoff. Bloqueada em user input Q1-Q5. Origem: `_reversa_sdd/sm-briefing-refactor.md` FOUND-MON-003 + state.json sm_handoff. | @sm (River) |
| 2026-04-28 | 1.1 | User input Q1-Q5 respondidas: 50 seats, 2026-05-30, lifetime permanente, cap=410+redirect, deadline=R$397. ADR `docs/adr/founding-plan-canonical.md` criado. PO validation: GO (10/10). Status: Blocked → Ready. | @po (Pax) |
