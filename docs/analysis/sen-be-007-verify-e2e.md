# SEN-BE-007 — End-to-end verification (AC10)

Run these checks after each deploy that touches `backend/routes/sitemap_*.py` or
`frontend/app/sitemap.ts`. Cross-references PR #535 (AC1-AC8) and this PR
(AC9-AC12 finalize).

## 1. Sub-sitemap availability (4 shards)

Sub-sitemaps `0..4` must each return HTTP 200 and contain at least one
`<url>` entry. Empty content is the failure mode that has historically gone
unnoticed (sitemap-4.xml = 0 URLs in production for weeks before
SEN-BE-007).

```bash
for n in 0 1 2 3 4; do
  status=$(curl -sI "https://smartlic.tech/sitemap-${n}.xml" | head -1 | tr -d '\r')
  count=$(curl -s "https://smartlic.tech/sitemap-${n}.xml" | grep -c "<url>")
  echo "sitemap-${n}.xml: ${status} | <url>=${count}"
done
```

Expected:

```
sitemap-0.xml: HTTP/2 200 | <url>= ~35    (core static)
sitemap-1.xml: HTTP/2 200 | <url>= ~60    (sector landing)
sitemap-2.xml: HTTP/2 200 | <url>= >0     (setor x UF combos — was 0 pre-fix)
sitemap-3.xml: HTTP/2 200 | <url>= ~500   (blog/content)
sitemap-4.xml: HTTP/2 200 | <url>= >100   (entities — was 404 pre-fix)
```

A `<url>` count of `0` on shard 4 indicates the regression we are gating
against. Shard 2 with `0` indicates the licitacoes-indexable upstream is
still returning empty combos.

## 2. Sitemap index reachable

```bash
curl -sI "https://smartlic.tech/sitemap_index.xml" | head -1
curl -sI "https://smartlic.tech/sitemap.xml" | head -1
```

Both must return `HTTP/2 200`. Pre-fix `sitemap_index.xml` returned `404`.

## 3. Backend latency budget (post-MV)

The `/v1/sitemap/licitacoes-indexable` endpoint must answer within 5
seconds. Before SEN-BE-007 it had a 90s budget; the materialised view
(when AC9 lands) should drop typical latency below 1s.

```bash
time curl -s "https://api.smartlic.tech/v1/sitemap/licitacoes-indexable" -o /dev/null
```

Expected: `real < 5s`. Anything `>5s` regresses AC9 and should re-trigger
ISR null-cache cycles within 24 hours.

## 4. Empty-payload smoke check

The frontend retry wrapper distinguishes `null` (transient — retried) from
`empty_data` (no indexable combos — accepted, logged). Confirm Sentry is
receiving the new breadcrumbs:

- Open https://confenge.sentry.io/projects/smartlic-frontend/?statsPeriod=24h
- Filter by tag `sitemap_outcome` — verify presence of `success`,
  `empty_data`, or `http_error` events. Pre-AC11 only `fetch_error` was
  emitted.

## 5. Search Console resubmission

After verifying steps 1-4, resubmit the sitemap index in Google Search
Console (`https://search.google.com/search-console/sitemaps`) and watch
the "Discovered URLs" counter for shard 4 over the next 48h. Pre-fix the
counter showed `0`; post-fix it should match the count from step 1.
