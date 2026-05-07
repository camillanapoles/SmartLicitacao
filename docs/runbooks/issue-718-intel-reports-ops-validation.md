# Issue #718: Intel Reports Ops Validation

Status: local triage documented on 2026-05-05.

## Scope

This runbook records the pre-launch validation for Intel Reports billing and analytics from GitHub issue #718.

Do not treat local code inspection as evidence for Railway variables or Mixpanel dashboard counts. Those checks require production access.

## Local Findings

- Stripe webhook dispatcher `backend/webhooks/stripe.py` claims every verified Stripe event in `stripe_webhook_events` before routing by `event.type`.
- Duplicate event IDs return `{"status": "already_processed"}` after the existing-row/stuck-event check.
- `payment_intent.succeeded` is not routed to a one-time purchase handler today. It is logged as an unhandled event, then marked completed in `stripe_webhook_events`.
- The existing one-time purchase implementation story is `docs/stories/2026-04/MON-REP-01-stripe-one-time-purchases-webhook.md`, currently Draft.
- The canonical one-time purchase table for Intel Reports should be `purchases`, not `profiles`, `user_subscriptions`, or a separate `intel_report_purchases` table. Intel report specificity belongs in `purchases.product_type`, `purchases.product_params`, and downstream report tables from MON-REP-02+.

## Required External Checks

Run these with production access before closing issue #718:

```bash
railway variables --service bidiq-backend --kv | grep MIXPANEL_TOKEN
```

Expected result: non-empty `MIXPANEL_TOKEN`.

In Mixpanel, verify both events have count greater than zero in the last 7 days:

- `paywall_hit`
- `trial_started`

If either count is zero, keep #718 open and investigate analytics ingestion before deploying Intel Reports purchases.

## One-Time Purchase Guardrails

When MON-REP-01 or #628 starts implementation:

- Reuse `/webhooks/stripe` as the only Stripe webhook entry point.
- Keep `stripe_webhook_events.id` as the first replay barrier for all event types, including `payment_intent.succeeded`.
- Add the payment handler behind the dispatcher; do not bypass the dispatcher with a second webhook endpoint.
- Persist Intel Reports purchases in `purchases`.
- Keep unique constraints on `purchases.stripe_checkout_session_id` and `purchases.stripe_payment_intent_id`.
- Make report delivery idempotent using a unique `purchase_id` in the generated-report/delivery table.

## Local Evidence Added

`backend/tests/test_stripe_webhook_matrix.py::TestIdempotency::test_payment_intent_succeeded_replay_is_deduped_before_delivery` simulates a replay of `payment_intent.succeeded` and verifies:

- first delivery claims the event and returns success;
- replay returns `already_processed`;
- no purchase/subscription table is touched while the one-time handler is absent.
