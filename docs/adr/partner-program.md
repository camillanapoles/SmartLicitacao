# ADR: Partner Program Policy

**Status:** Accepted
**Date:** 2026-05-06
**Issue:** [#597](https://github.com/tjsasakifln/PNCP-poc/issues/597)

---

## Context

The partner program already has production surfaces:

- `partners` and `partner_referrals` tables.
- `backend/routes/partners.py` admin and partner dashboard endpoints.
- `backend/services/partner_service.py` signup attribution, coupon lookup, revenue share calculation, and monthly reporting.

The commercial rules were not documented as a durable ADR. This created drift risk between implementation, GTM materials, and future payout automation.

## Decision

| Policy | Canonical rule | Notes |
|--------|----------------|-------|
| Commission | 20% lifetime revenue share | Applies to new partners unless a partner row has an explicit negotiated `revenue_share_pct`. |
| Attribution | Last-click partner attribution with 30-day window | Signup attribution wins when present; Stripe coupon attribution is fallback. A 30-day expiry must be enforced by the payout automation story before money movement. |
| Payout cadence | Pix payout monthly on day 5 | Monthly report generation is not the same as payout execution. |
| Partner onboarding | Self-service with CPF/CNPJ | Partner identity data is required before payout activation. |
| Source of truth | Database partner rows plus this ADR | Session memory is not an operational source of truth. |

## Consequences

New partners should default to 20% unless an admin explicitly sets another percentage. Existing partner rows keep their stored `revenue_share_pct`; this ADR does not backfill commercial contracts.

The current backend can calculate monthly revenue share, but does not yet execute Pix payouts, enforce a 30-day attribution expiry, or verify CPF/CNPJ before payout activation. Those items remain implementation follow-up.

## Implementation Follow-Up

Create a Product Owner/Scrum Master story for payout automation covering:

- CPF/CNPJ collection and validation for partners.
- 30-day last-click attribution expiry.
- Monthly Pix payout queue on day 5.
- Admin approval/audit trail before payout execution.
- Reconciliation between calculated `partner_referrals.revenue_share_amount` and paid amounts.

Story creation is intentionally left to @po/@sm authority under the project Constitution.

## References

- `backend/routes/partners.py`
- `backend/services/partner_service.py`
- `docs/stories/STORY-323-revenue-share-tracking.md`
- `docs/GTM-PLAYBOOK-2026-Q2.md`
