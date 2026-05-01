# BILL-SYNC-001: Stripe `product.updated` + `price.updated` Webhook Handlers

**Priority:** P1
**Effort:** M (3-4 dias)
**Squad:** @dev + @data-engineer
**Status:** Ready
**Epic:** [EPIC-MON-SUBS-2026-04](EPIC-MON-SUBS-2026-04.md)
**Sprint:** Sprint 2-3
**Dependências bloqueadoras:** STORY-360 (Done — `plan_billing_periods` source of truth direção Stripe→DB via GET /plans)

---

## Contexto

`plan_billing_periods` table é canonical pricing per CLAUDE.md "Source of truth: `plan_billing_periods` table (synced from Stripe)". STORY-360 (Done) implementou direção GET /plans (frontend consume DB). Mas mecânica de sync inverso (Stripe Dashboard pricing change → DB update + cache invalidate) **não documentada**.

`backend/webhooks/stripe.py` 253L dispatcher trata 12 eventos (CLAUDE.md billing section), mas **não trata** `product.updated`, `price.updated`. Manual update Stripe Dashboard exige manual sync DB → desync risk.

`webhooks/handlers/` 5 handlers existentes: checkout.py, subscription.py, invoice.py, founding.py, _shared.py. Esta story adiciona `pricing.py` handler.

---

## Acceptance Criteria

### AC1: `webhooks/handlers/pricing.py`

- [ ] Novo arquivo `backend/webhooks/handlers/pricing.py`:
  ```python
  async def _handle_product_updated(payload: dict, sb: SupabaseClient) -> None:
      product_id = payload["data"]["object"]["id"]
      # SELECT * FROM plans WHERE stripe_product_id=$1
      # UPDATE plans SET name, description, metadata
      pass
  
  async def _handle_price_updated(payload: dict, sb: SupabaseClient) -> None:
      price_id = payload["data"]["object"]["id"]
      # UPDATE plan_billing_periods SET unit_amount, currency, interval
      pass
  ```
- [ ] Idempotency via `stripe_webhook_events` table (existing pattern)
- [ ] Cache invalidation: `clear_plan_capabilities_cache()` post-update

### AC2: Register em `webhooks/stripe.py`

- [ ] Dispatcher router em `webhooks/stripe.py` adicionar:
  ```python
  "product.updated": pricing._handle_product_updated,
  "price.updated": pricing._handle_price_updated,
  ```

### AC3: Stripe Dashboard webhook config

- [ ] @devops adiciona `product.updated`, `price.updated` em Stripe Dashboard webhook subscription
- [ ] Documentar em `docs/runbooks/stripe-webhook-events.md` lista total 14 events (12 existentes + 2 novos)

### AC4: Cron safety net

- [ ] `backend/jobs/cron/billing.py` adicionar `sync_stripe_pricing_safety` 1×/dia 4 UTC:
  - Lista all `prices` Stripe API
  - Compara com `plan_billing_periods` table
  - Reconcile diff via UPDATE
  - Sentry alert se diff >0 (sinal de webhook miss)

### AC5: Frontend cache invalidation

- [ ] `frontend/hooks/usePlan.ts` localStorage cache TTL 1hr (CLAUDE.md) — verify invalidate path
- [ ] Sem mudança required (ja existe per STORY-360)

### AC6: Tests

- [ ] `test_stripe_webhook_pricing.py`:
  - `product.updated` → plans table updated
  - `price.updated` → plan_billing_periods updated
  - Idempotency: replay event 2x → 1 efeito
  - Cache invalidate verified
- [ ] Integration: trigger via Stripe CLI `stripe trigger product.updated`

---

## Scope

**IN:** 2 webhook handlers + dispatcher register + cron safety net + Stripe Dashboard config + tests
**OUT:** Stripe metered billing (separate MON-API-02) · pricing variants (separate STORY-277 Done) · plan capabilities matrix change (separate)

---

## Definition of Done

- [ ] handlers/pricing.py + dispatcher registered
- [ ] Stripe Dashboard config updated
- [ ] Cron safety net active
- [ ] Tests pass + Stripe CLI integration test
- [ ] Suite passa
- [ ] @po validation GO

---

## Dev Notes

- `webhooks/stripe.py:253L` dispatcher
- `webhooks/handlers/_shared.py:resolve_user_id` pattern
- `quota/quota_core.py:clear_plan_capabilities_cache` invalidation
- Memory `reference_pr_validation_sections` — PR body precisa ## Summary, ## Testing Plan, ## Closes
- DEBT-017 + SHIP-004 + STORY-360 audit confirma: GET /plans direção covered; product/price webhooks são GAP real

---

## Risk & Rollback

| Trigger | Ação |
|---|---|
| Webhook handler bug → DB incorrect price | Cron safety net (AC4) reconcile 1×/dia; manual revert via admin endpoint |
| Stripe webhook miss | Cron safety net cobre; Sentry alarme |
| Cache invalidate falha | TTL 5min mitiga; manual flush via admin |

**Rollback:** revert handlers + dispatcher; remove Stripe Dashboard webhook subscription.

---

## Dependencies

**Entrada:** STORY-360 Done · Stripe Dashboard write access
**Saída:** habilita pricing experimentation (mudar Stripe Dashboard ↔ DB sincronizam automaticamente)

---

## PO Validation

**Validated by:** @po (Pax)
**Date:** 2026-04-28
**Verdict:** GO
**Score:** 10/10

### 10-Point Checklist

| # | Criterion | ✓/✗ | Notes |
|---|-----------|-----|-------|
| 1 | Clear and objective title | ✓ | Webhook events explicitos (product.updated, price.updated). |
| 2 | Complete description | ✓ | Audit STORY-360+DEBT-017+SHIP-004 documentado. Gap real isolado. |
| 3 | Testable acceptance criteria | ✓ | 6 ACs com idempotency replay test + Stripe CLI integration. |
| 4 | Well-defined scope | ✓ | OUT exclude metered billing + capabilities matrix. |
| 5 | Dependencies mapped | ✓ | STORY-360 Done + Stripe Dashboard write access. |
| 6 | Complexity estimate | ✓ | M (3-4d) realistic. |
| 7 | Business value | ✓ | Permite pricing experimentation sem deploy. |
| 8 | Risks documented | ✓ | Cron safety net + manual revert via admin. |
| 9 | Criteria of Done | ✓ | 5 itens. |
| 10 | Alignment with PRD/Epic | ✓ | EPIC-MON-SUBS pricing source-of-truth. |

Status: Draft → Ready.

---

## Change Log

| Data | Versão | Descrição | Autor |
|---|---|---|---|
| 2026-04-28 | 1.0 | Story criada — recria fictícia state.json sm_handoff. Reduzido escopo: STORY-360 (Done) cobriu direção Stripe→DB via /plans; esta story cobre só product.updated + price.updated webhook handlers (gap real). Origem: `_reversa_sdd/sm-briefing-refactor.md` FOUND-MON-002. | @sm (River) |
| 2026-04-28 | 1.1 | PO validation: GO (10/10). Status: Draft → Ready. | @po (Pax) |
