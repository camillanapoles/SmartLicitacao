# BILL-SYNC-001: Bidirectional Stripe ↔ DB sync for `plan_billing_periods` (webhook forward + admin reverse)

**Status:** InReview
**Origem:** Reversa Audit 2026-04-27 (`_reversa_sdd/review-report.md` Gap-9) + decisão CTO 2026-04-27 (AMBOS forward webhook + reverse admin trigger)
**Prioridade:** P2 — data integrity / operational efficiency
**Complexidade:** S (1-2 dias)
**Owner:** @dev + @data-engineer
**Tipo:** Integration / Data Sync
**Companion de:** STORY-360 (Done — frontend lê DB, mas sync é manual)

---

## Contexto

STORY-360 (Done) estabeleceu `plan_billing_periods` table como source-of-truth para preços do frontend (`GET /v1/plans` lê DB). Mas sync com Stripe (master das prices) é **manual** — admin precisa atualizar tabela quando Stripe muda. Implicações:

1. Drift silencioso: Stripe atualiza price → DB stale → frontend mostra preço antigo → checkout cobra preço diferente
2. Admin overhead: cada price change = update manual SQL
3. Sem detecção: drift só descoberto via complaint usuário ou audit manual

Reversa Audit Gap-9: *"sync `plan_billing_periods` ↔ Stripe é manual ou automático? Frequência?"*.

**Decisão CTO 2026-04-27:** AMBOS direções:
- **Forward** Stripe → DB (webhook automático em `product.updated`/`price.updated`)
- **Reverse** DB → Stripe (admin trigger manual quando admin edita preço local — usado raramente, mas previne drift na direção contrária)

---

## Decisão

1. Adicionar handlers Stripe webhook `product.updated` + `price.updated` em `webhooks/handlers/`
2. Reconciliation cron daily (backup contra webhook miss)
3. Admin endpoint `POST /v1/admin/plans/{plan_id}/sync-to-stripe` (reverse direction, audit-logged)
4. Admin UI mostra last sync timestamp + drift indicator

---

## Critérios de Aceite

### Backend — Forward Sync (Stripe → DB)

- [x] **AC1:** Handler `backend/webhooks/handlers/stripe_product_price.py`:
  - Função `handle_product_updated(event)` — atualiza `plan_billing_periods` rows com `stripe_product_id` matching
  - Função `handle_price_updated(event)` — atualiza price/interval/currency
  - Idempotência via `events_processed` (existente)
- [x] **AC2:** Registrar handlers em `backend/webhooks/stripe.py`:
  ```python
  EVENT_HANDLERS = {
      ...existing,
      'product.updated': handle_product_updated,
      'price.updated': handle_price_updated,
      'price.created': handle_price_created,
      'price.deleted': handle_price_deleted,  # soft-delete em DB
  }
  ```
- [x] **AC3:** Configure webhook signature verify (existente em `webhooks/stripe.py`) cobre novos events
- [x] **AC4:** Add events na config Stripe Dashboard (manual step documentado em ADR)
- [x] **AC5:** Trigger Sentry warning `billing.sync.product_updated` com diff (old/new price) para tracking visibility

### Backend — Reconciliation Cron

- [x] **AC6:** Job ARQ cron `jobs/cron/billing_reconciliation.py::reconcile_stripe_prices`:
  - Diário 03 UTC
  - Lista todas prices Stripe via API + cross-reference `plan_billing_periods`
  - Detecta drifts (price difference, missing entries, deleted in Stripe ainda em DB)
  - Logs cada drift; auto-fix se confidence high (apenas update price); flag manual review se ambíguo
  - Output: report `drift_report` em `billing_reconciliation_runs` table
- [x] **AC7:** Sentry alert quando drift count >0 (não-zero é abnormal pós-webhook implementation)

### Backend — Reverse Sync (DB → Stripe)

- [x] **AC8:** Endpoint `POST /v1/admin/plans/{plan_billing_period_id}/sync-to-stripe`:
  - Admin only
  - Body: confirma admin entendeu (`{ "i_understand_this_modifies_stripe": true }`)
  - Cria nova Stripe price (Stripe não permite update price; sempre cria nova + arquiva antiga)
  - Atualiza `plan_billing_periods.stripe_price_id` para nova
  - Audit log em `admin_billing_audit_log`
- [x] **AC9:** Reject reverse sync se últimas 24h tiveram forward sync (evita loop) — flag para revisão manual

### Frontend — Admin UI

- [x] **AC10:** `frontend/app/admin/billing/sync/page.tsx`:
  - Tabela de plans com colunas: name, price_db, price_stripe, last_synced_at, drift?
  - Indicador visual: 🟢 in-sync, 🟡 drift detected (last 24h), 🔴 drift > 24h
  - Botão "Sync from Stripe now" (force forward sync)
  - Botão "Push DB to Stripe" (reverse, com confirmation modal)
  - Histórico reconciliation runs (last 30)

### ADR + Tests

- [x] **AC11:** ADR `docs/adr/ADR-BILL-SYNC-001-bidirectional-strategy.md`:
  - Por que webhook não suficiente sozinho (cron backup)
  - Por que reverse sync existe (raros casos edge: admin precisa alterar local primeiro)
  - Stripe price immutability (sempre cria nova, archived old)
  - Conflict resolution: webhook always wins on race (most recent timestamp)
- [x] **AC12:** Tests `backend/tests/test_stripe_sync.py`:
  - Webhook product.updated atualiza DB
  - Webhook price.updated atualiza price
  - Reconciliation detecta drift sintético
  - Reverse sync cria new Stripe price + archives old
  - Loop guard rejeita reverse após webhook recente
- [x] **AC13:** Tests `frontend/__tests__/admin/billing-sync.test.tsx`: drift indicator render, sync buttons disable durante in-flight

---

## Arquivos Impactados

**Novos:**
- `backend/webhooks/handlers/stripe_product_price.py`
- `backend/jobs/cron/billing_reconciliation.py`
- `backend/routes/admin_billing_sync.py`
- `supabase/migrations/20260427216000_billing_reconciliation_runs.sql` + `.down.sql`
- `supabase/migrations/20260427216100_admin_billing_audit_log.sql` + `.down.sql`
- `backend/tests/test_stripe_sync.py`
- `frontend/app/admin/billing/sync/page.tsx`
- `frontend/__tests__/admin/billing-sync.test.tsx`
- `docs/adr/ADR-BILL-SYNC-001-bidirectional-strategy.md`

**Modificados:**
- `backend/webhooks/stripe.py` — registrar 4 novos event handlers (`product.updated`, `price.updated/created/deleted`)
- `backend/jobs/queue/config.py` — adicionar reconciliation cron na schedule

---

## Riscos

- **R1 (Médio):** Webhook Stripe pode chegar fora de ordem (out-of-sequence updates). **Mitigação:** AC1 idempotência via `events_processed` + comparar `event.created` timestamp ao decidir aplicar
- **R2 (Médio):** Reverse sync pode quebrar checkouts em flight (price ID muda enquanto user em Stripe checkout). **Mitigação:** AC8 cria nova price sem deletar antiga; antiga continua válida 24h grace period
- **R3 (Médio):** Reconciliation cron + webhook concorrentes podem causar race. **Mitigação:** AC9 loop guard 24h + lock distribuído Redis em reconciliation
- **R4 (Baixo):** Stripe API rate limits em reconciliation. **Mitigação:** paginação + sleep entre páginas

---

## Dependências

- Stripe webhook secret configurado (existente)
- @data-engineer review schema billing_reconciliation_runs antes do @dev pickup
- Stripe Dashboard config: enable `product.updated` + `price.updated/created/deleted` events (manual step pré-deploy)

---

## Change Log

| Data | Agente | Ação |
|------|--------|------|
| 2026-04-27 | @sm | Story criada via Reversa Audit Gap-9 + CTO decision (AMBOS forward webhook + reverse admin trigger). Status=Draft → @po validation |
| 2026-04-27 | @po | Validation 10/10 → **GO**. Gap real confirmado vs STORY-360 (Done — frontend lê DB, mas sync upstream era manual). Webhook idempotency + loop guard 24h bem-pensados. Status Draft → Ready. |
| 2026-04-28 | @dev | Implementation complete. 3 backend modules + 3 migrations + 1 frontend page + 30 backend tests + 7 frontend tests, all passing. ADR `ADR-BILL-SYNC-001-bidirectional-strategy.md` written. Ruff + mypy clean on new files. api-types regenerated. Status Ready → InReview. |

---

## File List

### Created
- `backend/webhooks/handlers/stripe_product_price.py` — 4 forward-sync handlers (product.updated, price.created/updated/deleted) with 24h race guard + out-of-order event protection
- `backend/jobs/cron/billing_reconciliation.py` — daily ARQ-style reconciliation cron with auto-fix, dry-run mode, Redis NX lock, Sentry alerting
- `backend/routes/admin_billing_sync.py` — admin endpoints: GET /billing-sync, GET /reconciliation-runs, POST /{id}/sync-to-stripe, POST /reconcile-now
- `backend/tests/test_stripe_product_price_webhook.py` — 14 tests (handlers + dispatcher routing + signature verify + idempotency)
- `backend/tests/test_billing_reconciliation.py` — 9 tests (drift detection, auto-fix, dry-run, lock, Sentry alert)
- `backend/tests/test_admin_billing_sync.py` — 7 tests (reverse sync, race guard, auth gate, drift listing)
- `frontend/app/admin/billing/sync/page.tsx` — admin UI: drift indicator, last sync timestamps, sync buttons, reconciliation runs panel, confirmation modal
- `frontend/__tests__/admin/billing-sync.test.tsx` — 7 tests
- `supabase/migrations/20260428101050_plan_billing_periods_sync_tracking.sql` (+ `.down.sql`) — adds stripe_product_id, last_forward_synced_at, last_reverse_synced_at, is_archived
- `supabase/migrations/20260428101100_billing_reconciliation_runs.sql` (+ `.down.sql`) — reconciliation history table
- `supabase/migrations/20260428101200_admin_billing_audit_log.sql` (+ `.down.sql`) — reverse-sync audit trail
- `docs/adr/ADR-BILL-SYNC-001-bidirectional-strategy.md` — architectural decision record

### Modified
- `backend/webhooks/stripe.py` — wired the 4 new event types into the dispatcher's elif chain (line 184+)
- `backend/jobs/cron/scheduler.py` — register `start_billing_reconciliation_task`
- `backend/startup/routes.py` — register `admin_billing_sync_router`
- `frontend/app/api-types.generated.ts` — regenerated from FastAPI OpenAPI

### Test Results

| Suite | Result |
|---|---|
| New BILL-SYNC tests | 30/30 pass (≤12s) |
| Existing webhook+billing regression | 84/84 pass (≤23s) |
| Frontend admin/billing-sync | 7/7 pass |
| Ruff (new files) | clean |
| Mypy (new files) | clean |
| Webhook idempotency | covered by `TestIdempotency::test_duplicate_event_skipped` |
| 24h race guard | covered by `TestPriceUpdatedHandler::test_race_guard_skips_recent_reverse_sync` and `TestReverseSyncRaceGuard::test_rejects_when_recent_forward_sync` |
