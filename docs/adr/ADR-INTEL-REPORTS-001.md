---
id: ADR-INTEL-REPORTS-001
title: Intel Reports One-Time Purchase Architecture
status: Accepted
authors: [@dev, @pm]
date: 2026-05-12
deciders: [Tiago Sasaki]
---

# ADR-INTEL-REPORTS-001: Intel Reports One-Time Purchase Architecture

## Context

SmartLic's DataLake contains ~2M supplier contracts and 1.5M bids. This data represents an unmonetized asset: users can search and filter bids through the subscription pipeline, but there is no product for deep, offline-ready competitive intelligence.

Two product requirements drove the Intel Reports feature:

1. **CNPJ company report** (INTEL-REPORT-001, R$197.00): a deep 8-12 page PDF analyzing a specific company's government contract portfolio, sector exposure, geographic distribution, and historical trends. Targeted at B2G sales teams researching prospects or competitors.

2. **Sector/UF market report** (INTEL-REPORT-002, R$147.00): an aggregated market analysis for a given sector in a given state — top players, total contract value, modalidade distribution, and trend analysis.

Key architectural constraints:

- **One-time purchase** (not subscription): users buy individual reports via Stripe checkout. This avoids subscription coupling for what is inherently an episodic purchase.
- **PDF delivery**: ReportLab generates A4 PDFs server-side. WeasyPrint was evaluated but rejected (see Alternatives).
- **DataLake as source**: reports are generated from the existing `cnpj_supplier_intel` and `sector_uf_intel` DataLake RPCs, avoiding a separate data pipeline.
- **Railway compatibility**: PDF generation must work within Railway's ephemeral filesystem and 120s proxy timeout.
- **Reporting latency**: PDF generation runs synchronously for small reports; complex reports can be up to ~30s.

## Decision

1. **DataLake RPC as canonical data source**: all report data is aggregated by Supabase RPCs (`cnpj_supplier_intel` for company reports, `sector_uf_intel` for sector reports). These RPCs query the existing DataLake tables (`pncp_supplier_contracts`, `pncp_raw_bids`) with aggregation logic. Using RPCs instead of direct SQL in application code provides:

   - Performance isolation: RPC execution is bounded by `statement_timeout`
   - Centralized tuning: a slow aggregation is fixed in the RPC, not in every caller
   - Permission boundary: RPCs run with `SECURITY DEFINER` and explicit `search_path`

2. **LLM summary enhancement**: the raw aggregated data is optionally enhanced with a GPT-4.1-nano executive summary (trend narrative, key insights). The LLM call is budget-gated via the existing monthly budget cap.

3. **PDF generation via ReportLab** (`backend/pdf_generator_intel_report.py`): chosen over WeasyPrint because:

   - ReportLab is pure Python with no system dependencies (WeasyPrint requires Pango, Cairo, GDK-Pixbuf — unavailable on Railway without apt-get)
   - ReportLab produces deterministic output: same data always produces byte-identical PDF (important for caching)
   - Shared conventions with `pdf_generator_edital.py`: same brand colors, table styles, and page template

4. **One-time Stripe checkout** (not subscription): implemented via `services/billing.py::create_intel_report_checkout` using inline `price_data`. Products are NOT pre-created in Stripe Dashboard — prices are defined in `backend/schemas/intel_report.py::INTEL_REPORT_PRICES`:

   ```python
   INTEL_REPORT_PRICES = {
       "cnpj": 19700,       # R$197.00
       "sector_uf": 14700,  # R$147.00
   }
   ```

5. **Purchase lifecycle** tracked in `intel_report_purchases` table (created by migration #628):

   | Status | Meaning | Transition |
   |--------|---------|------------|
   | `pending` | Checkout created, awaiting payment | → `generating` |
   | `generating` | Payment confirmed, PDF generation in progress | → `ready` or `failed` |
   | `ready` | PDF available for download | expires after configurable TTL |
   | `failed` | Generation error | manual retry via support |

6. **Authentication and ownership**: PDF download requires authentication AND ownership verification (user_id match). Reports are not publicly accessible.

### Route design

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/v1/intel-reports/checkout` | Create Stripe checkout session |
| GET | `/v1/intel-reports/` | List user's purchases |
| GET | `/v1/intel-reports/{id}` | Poll purchase status |
| GET | `/v1/intel-reports/{id}/download` | Stream PDF (auth + ownership) |

## Consequences

### Positive

- Unlocks a new revenue stream (one-time purchase, not subscription) using the existing DataLake as data source — no new ingestion pipeline needed.
- ReportLab PDF generation has zero system dependencies: works on Railway without apt-get, no Docker build changes.
- RPC-based aggregation means the data pipeline stays in the database (tunable via SQL) rather than leaking into application code.
- One-time checkout avoids subscription coupling: Intel Reports can be purchased by users on any plan, including trial-expired users who cannot access the pipeline.
- Pricing is configurable in Python without Stripe Dashboard changes (though production Stripe products may be pre-created for reliability).

### Negative / Risks

- **R1 (Medium)**: PDF generation for complex reports (e.g. a company with 10k+ contracts) can approach the Railway 120s proxy timeout. Mitigation: report data is pre-aggregated by the RPC; the PDF generator only formats pre-computed numbers. If a specific report exceeds the timeout, generation can be moved to a background ARQ job.
- **R2 (Low)**: `price_data` inline (no pre-created Stripe Price) means the price lives in two places: `INTEL_REPORT_PRICES` in code and the Stripe Checkout session. If they drift, checkout fails. Mitigation: integration tests + Stripe Dashboard verification on deploy.
- **R3 (Low)**: The `intel_report_purchases` table has no automated cleanup for expired PDFs. Storage will grow over time. Mitigation: a pg_cron cleanup job can be added if storage exceeds 1GB.
- **R4 (Low)**: LLM summary adds ~2-5s to generation time. Mitigation: LLM call is conditional — skipped if monthly budget is exceeded. The data tables are always included regardless of LLM availability.

### Neutral

- The existing `webhooks/handlers/checkout.py` had to be extended to handle Intel Report-specific checkout events (`handle_intel_report_payment_failed`). This follows the ABC pattern established by ADR-WEBHOOK-ABC-001.
- PDF download uses `StreamingResponse` rather than pre-generating to disk. The PDF is generated on-demand at download time and streamed to the client. This avoids ephemeral filesystem storage on Railway.

## Alternatives Considered

| Alternative | Why rejected |
|-------------|--------------|
| **WeasyPrint for PDF** | Requires system libraries (Pango, Cairo, GDK-Pixbuf). These are not available on Railway without `apt-get`, adding ~200MB to the build image and slowing deploys. |
| **Node.js Puppeteer for PDF** | Would require a separate frontend service or a subprocess call. Adds ~300MB Chromium dependency. ReportLab is simpler and faster for the table-heavy report format. |
| **Subscription-gated reports** | Would require Intel Report users to hold an active subscription, excluding the most likely buyer (a non-subscriber researching a single competitor). One-time purchase is the correct monetization model for episodic intelligence. |
| **Client-side PDF generation** | The DataLake query and aggregation are server-side (RPC). Transmitting raw contract data to the client for PDF generation would expose more data than necessary and require a heavy JS PDF library. |
| **Async ARQ job for all generation** | Adds latency (job queue wait + polling). Synchronous generation works for current report sizes (<30s). Async generation is reserved for the failure case or future complex reports. |

## References

- `backend/routes/intel_reports.py` — Route definitions
- `backend/schemas/intel_report.py` — Pydantic schemas + price configuration
- `backend/pdf_generator_intel_report.py` — ReportLab PDF generation
- `backend/services/billing.py` — `create_intel_report_checkout` service function
- `backend/webhooks/handlers/checkout.py` — Intel Report webhook handlers
- `supabase/migrations/` — `intel_report_purchases` table migration (#628)
- ADR-WEBHOOK-ABC-001 — Webhook handler ABC pattern
- Issue [#630](https://github.com/tjsasakifln/PNCP-poc/issues/630) — Intel Reports feature
