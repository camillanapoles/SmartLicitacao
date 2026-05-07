# Founders Analytics Events

Schema reference for all analytics events related to the Plano Fundadores (epic:fundadores).

## Frontend (Mixpanel)

| Event | Props | Trigger |
|-------|-------|---------|
| `founders_page_view` | `{utm_source, utm_medium, utm_campaign, src, seats_remaining, deadline_at}` | /fundadores page mount |
| `founders_banner_view` | `{route, dismissed_count}` | FoundersTopBanner mount |
| `founders_banner_click` | `{route}` | CTA click in banner |
| `founders_banner_dismiss` | `{route}` | Dismiss button click |
| `founders_ribbon_view` | `{route, variant}` | FoundersRibbon mount in pSEO |
| `founders_ribbon_click` | `{route, variant}` | FoundersRibbon CTA click |
| `founders_cta_click` | `{cta_location, src}` | Any CTA on /fundadores page |
| `founders_checkout_start` | `{email_provided, src}` | Form submit on /fundadores |
| `founders_pseo_conversion` | `{from_route, variant}` | Arrival at /fundadores from pSEO ribbon |

## Backend (Prometheus)

| Metric | Labels | Description |
|--------|--------|-------------|
| `smartlic_founders_checkout_success_total` | `offer_version` | Webhook: lifetime entitlement activated |
| `smartlic_founders_checkout_failed_total` | `reason` | Checkout rejection (`cap_violated`, `db_error`, etc.) |

### Label values

**`offer_version`**
- `v2_lifetime` — current offer (one-time R$997, issued epic:fundadores v2)

**`reason`**
- `cap_violated` — BIZ-FOUND-002 race guard detected over-sell after completion flip
- `db_error` — Supabase error when marking lead as completed
- `deadline_passed` — Checkout attempted after offer deadline (logged, not a webhook path)

## Usage

Import from `@/lib/analytics/founders`:

```typescript
import { trackFoundersPageView } from '@/lib/analytics/founders';

// On /fundadores page mount
trackFoundersPageView({
  utm_source: searchParams.get('utm_source'),
  utm_medium: searchParams.get('utm_medium'),
  utm_campaign: searchParams.get('utm_campaign'),
  src: searchParams.get('src'),
  seats_remaining: offerData?.seats_remaining,
  deadline_at: offerData?.deadline_at,
});
```

## Notes

- All frontend functions use a `safeTrack` wrapper — they never throw, even in SSR
  or when Mixpanel has not been initialized (cookie consent not given).
- Backend counters are instrumented in `backend/webhooks/handlers/founding.py`
  via the `mark_founding_lead_completed` webhook handler (Stripe
  `checkout.session.completed` with `metadata.source == "founding"`).
- The optimistic `founders_checkout_success_total` increment happens immediately
  after the DB flip; if the BIZ-FOUND-002 race guard reverts the row, a
  `founders_checkout_failed_total{reason="cap_violated"}` counter is also
  incremented. The net value of `success - cap_violated` gives the true
  net-completed count.
