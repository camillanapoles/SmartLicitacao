# MFA Enforcement Coverage Inventory (MFA-ENFORCE-EXT-001 AC1)

**Date:** 2026-05-09
**Author:** @dev (autonomous)
**Story:** MFA-ENFORCE-EXT-001
**ADR:** [docs/adr/mfa-policy.md](../adr/mfa-policy.md)
**Baseline:** MFA-EXT-001 shipped `require_mfa` dependency in `backend/auth.py` but did NOT wire it into any route (`grep "Depends(require_mfa)" backend/` returns 0 results).

## Decision tree (per ADR mfa-policy.md)

Endpoints requiring MFA = high-impact state changes:
1. **Financial** (irreversible value transfer or account binding)
2. **Account-level destructive** (delete, password change)
3. **Authorization changes** (role/permission elevation)
4. **Sensitive PII writes** (email change, document change)

## Endpoint inventory

| Endpoint | Module | Decision | Rationale | Notes |
|----------|--------|----------|-----------|-------|
| `POST /v1/billing-portal` | `routes/billing.py` | **REQUIRE MFA** | Financial — Stripe customer portal redirect (cancel sub, update card) | Story listed as `/v1/billing/portal`; actual path is `/billing-portal` |
| `POST /v1/change-password` | `routes/user.py` | **REQUIRE MFA** | Credential rotation; existing rate limit alone insufficient | STORY-210 AC12 already rate-limits 5/15min |
| `DELETE /v1/me` | `routes/user.py` | **REQUIRE MFA** | LGPD Art. 18 VI — irreversible account deletion + Stripe sub cancel + auth user delete | Multi-table cascade |
| `POST /v1/api/subscriptions/cancel` | `routes/subscriptions.py` | **REQUIRE MFA** | Financial — cancels active subscription, ends paid access | |
| `POST /v1/api/subscriptions/update-billing-period` | `routes/subscriptions.py` | **REQUIRE MFA** | Financial — changes Stripe price (annual ⇄ monthly), prorated charge | |
| `POST /v1/checkout` | `routes/billing.py` | Skip | New subscription creation; signup-equivalent step (user explicitly initiating) | Adding MFA here harms conversion |
| `POST /v1/founding/checkout` | `routes/founding.py` | Skip | Same rationale as checkout |
| `POST /v1/conta/cancelar-trial` | `routes/conta.py` | Skip | Trial cancellation — not financial loss; user signaling intent | |
| `POST /v1/api/subscriptions/cancel-feedback` | `routes/subscriptions.py` | Skip | Survey response, no state change | |

## Endpoints listed in story but NOT present in codebase

These are documented as N/A — no scope creep into MFA-EXT-001 territory:

| Story-listed endpoint | Reality | Disposition |
|-----------------------|---------|-------------|
| `POST /v1/organizations/{id}/members/{user}/role` | Does not exist (no role-change endpoint in `routes/organizations.py`) | N/A — defer to RBAC-ORG-002 follow-up if endpoint is added |
| `DELETE /v1/organizations/{id}` | Does not exist | N/A — defer |
| `PATCH /v1/profile` (email/CPF/CNPJ) | Does not exist; only `PUT /profile/context` (business context JSONB, no PII) | N/A — defer until partner program self-service CPF/CNPJ endpoint is built |
| API key/token management | Does not exist (no first-party API keys) | N/A |

## Frontend

Story Files lists `frontend/components/MfaChallengeModal.tsx`. **This file does not exist.** The current MFA UX is `frontend/components/auth/MfaEnforcementBanner.tsx` — reason-driven banner that reads `/v1/mfa/status` and surfaces admin/consultoria/bruteforce variants universally. No new triggers needed; backend 403 + `X-MFA-Required` header are already understood by the existing enforcement model. AC2 frontend deferred (no work required).

## Response code

ADR mfa-policy.md and existing implementation use **HTTP 403** with `X-MFA-Required: true` + `X-MFA-Reason: {admin|consultoria|bruteforce}` headers. Story's "401 challenge" suggestion is a future UX pivot that conflicts with the shipped MFA-EXT-001 contract (existing tests assert 403). Keeping 403 to preserve `MfaEnforcementBanner` parity. 401-step-up is a separate story.
