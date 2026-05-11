# REF-MON-002: Stripe Webhook Handlers ABC Base — Idempotency Unification

**Priority:** P2
**Effort:** M (3-5 dias)
**Squad:** @dev + @architect
**Status:** InReview
**Epic:** [EPIC-TD-2026Q2](EPIC-TD-2026Q2/)
**Sprint:** Sprint 3
**Dependências bloqueadoras:** story-debt-0-webhook-audit Done (DEBT-324 single registration confirmed)

---

## Contexto

`webhooks/handlers/` 5 arquivos (1900 LOC total): subscription.py 572L, invoice.py 507L, checkout.py 351L, founding.py, _shared.py. Repetem 4 patterns:

1. Sig validation (delegated to `webhooks/stripe.py:82`)
2. `INSERT ON CONFLICT DO NOTHING` em `stripe_webhook_events` (idempotency)
3. `invalidate_plan_status_cache(user_id)` post plan_type change
4. `_activate_plan` flow

`webhooks/stripe.py` 253L já é dispatcher fino (correct). Esta story extrai shared infra para ABC base, reduzindo 1900L → ~1200L total + base ~250L.

Distinção vs `story-debt-0-webhook-audit` Done: aquela cobriu DEBT-324 (single registration audit + dedupe). Esta story refatora cada handler internal structure (ortogonal).

---

## Acceptance Criteria

### AC1: ABC `WebhookHandler` em `_base.py`

- [ ] `backend/webhooks/handlers/_base.py`:
  ```python
  from abc import ABC, abstractmethod
  from typing import Any
  
  class WebhookHandler(ABC):
      event_type: str  # class attr — set by subclass
      
      @abstractmethod
      async def process(self, payload: dict, sb: SupabaseClient) -> None: ...
      
      def idempotency_key(self, payload: dict) -> str:
          return payload["id"]  # Stripe event id default
      
      async def handle(self, payload: dict, sb: SupabaseClient) -> None:
          key = self.idempotency_key(payload)
          claim = await self._claim_idempotency(sb, key)
          if not claim:
              return  # already processed
          try:
              await self.process(payload, sb)
              await self._mark_processed(sb, key)
              await invalidate_plan_status_cache(self._user_id_from_payload(payload))
          except Exception as e:
              await self._mark_failed(sb, key, str(e))
              raise
  ```

### AC2: Migrate 4 handlers para herança ABC

- [ ] `checkout.py` → `class CheckoutCompletedHandler(WebhookHandler)`, `class CheckoutAsyncSucceededHandler(WebhookHandler)`, etc.
- [ ] `subscription.py` → 4 handlers (created/updated/deleted/trial_will_end)
- [ ] `invoice.py` → 3 handlers
- [ ] `founding.py` → 1 handler
- [ ] Cada handler: ~50-100L (vs 100-200L atual)

### AC3: Decorator `@webhook_handler`

- [ ] `_base.py` adiciona registry pattern:
  ```python
  HANDLERS_REGISTRY: dict[str, WebhookHandler] = {}
  
  def webhook_handler(event_type: str):
      def decorator(cls):
          instance = cls()
          instance.event_type = event_type
          HANDLERS_REGISTRY[event_type] = instance
          return cls
      return decorator
  ```

### AC4: `webhooks/stripe.py` dispatcher consume registry

- [ ] Substituir if-elif chain por `HANDLERS_REGISTRY[event_type].handle(payload, sb)`
- [ ] Fallback log "Unhandled event type" preservado

### AC5: Tests

- [ ] `test_webhook_base.py`: ABC base — idempotency replay 2x → 1 efeito
- [ ] Each handler: existing tests in `test_stripe_webhook_*.py` continuam passando
- [ ] Registry: HANDLERS_REGISTRY auto-populated quando handlers imported

### AC6: Documentação

- [ ] `docs/architecture/webhook-handlers.md` documenta ABC + registry pattern

---

## Scope

**IN:** ABC base + 4 handler migrations + dispatcher refactor + registry + tests
**OUT:** Add new event types (separate stories) · Stripe SDK upgrade

---

## Definition of Done

- [ ] ABC + registry funcional
- [ ] 4 handlers migrated
- [ ] Tests pass + Stripe CLI integration
- [ ] LOC redução: 1900 → ~1200 + 250 (base) = saving ~450L
- [ ] Suite passa
- [ ] @po validation GO

---

## Dev Notes

- `webhooks/stripe.py:253L` dispatcher
- `webhooks/handlers/_shared.py:resolve_user_id` — pode mover para `_base.py`
- `quota/quota_core.py:invalidate_plan_status_cache` — chama no `handle()` template method
- Padrão `WebhookHandler` ABC similar a strategy pattern em REF-VAL-002 (LLM)

---

## Risk & Rollback

| Trigger | Ação |
|---|---|
| Idempotency template breaks subtle handler logic | Revert per-handler até confirmar; ABC opt-in inicialmente |
| Registry not populated em deploy (lazy import) | Eager import no `webhooks/__init__.py` |

**Rollback:** revert handler files; dispatcher volta if-elif chain.

---

## Dependencies

**Entrada:** story-debt-0-webhook-audit Done
**Saída:** habilita REF-MON-001 admin split (cleaner tests) · BILL-SYNC-001 pricing handler herda ABC

---

## PO Validation

**Validated by:** @po (Pax)
**Date:** 2026-04-28
**Verdict:** GO
**Score:** 10/10

### 10-Point Checklist

| # | Criterion | ✓/✗ | Notes |
|---|-----------|-----|-------|
| 1 | Clear and objective title | ✓ | ABC base + idempotency unification explícito. |
| 2 | Complete description | ✓ | Distinção vs story-debt-0-webhook-audit (Done) clarificada. |
| 3 | Testable acceptance criteria | ✓ | 6 ACs com idempotency replay test + LOC reduction quantitativa. |
| 4 | Well-defined scope | ✓ | OUT exclude new event types + Stripe SDK upgrade. |
| 5 | Dependencies mapped | ✓ | story-debt-0-webhook-audit Done. |
| 6 | Complexity estimate | ✓ | M (3-5d) coerente. |
| 7 | Business value | ✓ | LOC saving ~450L + future webhook handlers easier. |
| 8 | Risks documented | ✓ | Per-handler revert se ABC template breaks. |
| 9 | Criteria of Done | ✓ | 5 itens com LOC reduction confirmation. |
| 10 | Alignment with PRD/Epic | ✓ | EPIC-TD-2026Q2 idempotency unification. |

Status: Draft → Ready.

---

## Change Log

| Data | Versão | Descrição | Autor |
|---|---|---|---|
| 2026-04-28 | 1.0 | Story criada via batch — origem `_reversa_sdd/sm-briefing-refactor.md` REF-MON-002. | @sm (River) |
| 2026-04-28 | 1.1 | PO validation: GO (10/10). Status: Draft → Ready. | @po (Pax) |
