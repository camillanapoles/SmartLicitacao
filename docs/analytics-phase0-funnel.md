# Phase 0 Analytics Funnel — B2G Reposicionamento

## Funnel Definition (Mixpanel Insights)

Step 1: `page_load` on `/consultoria-b2g`
Step 2: `form_started`
Step 3: `form_submitted`
Step 4: `lead_captured`

Breakdown: `modalidade_interesse`

## Phase 0 Gate Metric
- ≥10 distinct form_submitted (unique session)
- ≥1 modalidade ≠ "nao_sei"
- window: 14 days post-deploy (2026-05-07 → 2026-05-21)

## Super-property: pseo_origin
Registered when referrer pathname matches: /cnpj, /orgaos, /licitacoes, /municipios, /observatorio, /blog

## Setup Notes
- Funnel must be configured manually in Mixpanel Dashboard > Reports > Funnels
- Events schema documented in frontend/lib/analytics-events.ts
- Gate evaluation doc: docs/sessions/2026-05/2026-05-21-phase0-gate-decision.md
