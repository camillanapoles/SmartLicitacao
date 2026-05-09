# Code/Spec Matrix — SmartLic

> Gerada pelo **Reversa Writer** em 2026-04-27 · Rastreabilidade bidirecional spec ↔ código

## Spec → Code

| Spec | Componente | Arquivos primários | LOC |
|------|-----------|--------------------|-----|
| `01-search-pipeline` | search-pipeline | `backend/search_pipeline.py`, `backend/pipeline/`, `backend/consolidation/`, `backend/routes/search/` | ~3.500 |
| `02-billing-quota` | billing-quota | `backend/services/billing.py`, `backend/quota/`, `backend/webhooks/stripe.py`, `backend/webhooks/handlers/`, `backend/routes/{billing,founding,subscriptions,conta,trial_extension}.py`, `backend/jobs/cron/billing.py` | ~2.800 |
| `03-auth-oauth` | auth-oauth | `backend/auth.py`, `backend/authorization.py`, `backend/oauth.py`, `backend/routes/auth_*.py`, `backend/routes/mfa.py`, `frontend/middleware.ts`, `frontend/app/{login,signup,auth,recuperar-senha}/` | ~1.700 |
| `04-pipeline-kanban` | pipeline-kanban | `backend/routes/pipeline.py`, `backend/schemas/pipeline.py`, `frontend/app/pipeline/`, `frontend/hooks/usePipeline.ts` | ~1.200 |
| `05-ingestion-datalake` | ingestion-datalake | `backend/ingestion/`, `backend/datalake_query.py`, `backend/jobs/queue/config.py`, `backend/jobs/cron/pncp_canary.py` | ~1.500 |
| `07-intel-report-sector-uf` + `07b-intel-pdf-generator` | intel-report-sector-uf (v0.2 INTEL-REPORT-002 — R$147 one-time) | `supabase/migrations/20260508120000_sector_uf_intel_rpc.sql` (+ `.down.sql`), `backend/pdf_generator_sector_uf_report.py`, `backend/jobs/queue/jobs.py` (`_generate_sector_uf_report_pdf` + `generate_intel_report`), `backend/services/billing.py:create_intel_report_checkout`, `backend/schemas/intel_report.py`, `backend/routes/intel_reports.py`, `backend/email_service.py:send_intel_report_ready`, `backend/tests/test_sector_uf_intel_pdf.py` (34 tests) | ~1.400 |

## Code → Spec

### Backend (módulos críticos)

| File | Specs |
|------|-------|
| `backend/main.py`, `backend/startup/*.py` | bootstrap, todas |
| `backend/search_pipeline.py` | 01 |
| `backend/search_state_manager.py`, `backend/models/search_state.py` | 01 |
| `backend/search_context.py` | 01 |
| `backend/pipeline/budget.py` | 01 (NFR time budget waterfall) |
| `backend/pipeline/cache_manager.py` | 01 (cache SWR) |
| `backend/consolidation/dedup.py`, `consolidation/source_merger.py` | 01 (5-layer dedup) |
| `backend/pncp_client.py`, `backend/portal_compras_client.py`, `backend/compras_gov_client.py` | 01 (live fallback) |
| `backend/filter/`, `backend/llm_arbiter/`, `backend/relevance.py`, `backend/viability.py` | 01 (filter pipeline + LLM zero-match + viability) |
| `backend/datalake_query.py`, `backend/ingestion/` | 05 |
| `backend/services/billing.py` | 02 |
| `backend/quota/{quota_core,quota_atomic,plan_enforcement,plan_auth,session_tracker}.py` | 02 |
| `backend/webhooks/stripe.py`, `backend/webhooks/handlers/{checkout,subscription,invoice,founding}.py` | 02 |
| `backend/auth.py`, `backend/authorization.py` | 03 |
| `backend/oauth.py` | 03 (OAuth Google) + 04 (Sheets export) |
| `backend/routes/pipeline.py`, `backend/schemas/pipeline.py` | 04 |
| `backend/jobs/queue/{config,jobs,search,result_store,redis_pool,pool}.py`, `backend/job_queue.py` | 06 (jobs+cron — to be authored) |
| `backend/jobs/cron/{billing,canary,cron_monitor,indice_municipal,llm_batch_poll,new_bids_notifier,notifications,pncp_canary,scheduler,seo_snapshot,session_cleanup,trial_emails,trial_risk_detection}.py`, `backend/cron_jobs.py` | 06 |
| `backend/routes/feedback.py`, `backend/feedback_analyzer.py`, `backend/schemas/feedback.py` | 07 (messages-feedback — to be authored) |
| `backend/routes/messages.py`, `backend/schemas/messages.py` | 07 |
| `backend/routes/onboarding.py`, `backend/utils/cnae_mapping.py` | 08 (onboarding-analytics — to be authored) |
| `backend/routes/analytics.py` | 08 |
| `backend/admin.py`, `backend/routes/admin_*.py`, `backend/routes/{slo,seo_admin,feature_flags}.py` | 09 (admin — to be authored) |
| `backend/excel.py`, `backend/google_sheets.py`, `backend/pdf_generator_edital.py`, `backend/routes/{export,export_sheets}.py` | 10 (exports — to be authored) |
| `backend/routes/{observatorio,blog_stats,sitemap_*,empresa_publica,orgao_publico,contratos_publicos,dados_publicos,municipios_publicos,itens_publicos,compliance_publicos,indice_municipal,alertas_publicos,sectors_public,stats_public,calculadora,comparador,daily_digest,weekly_digest}.py` | 11 (observatory-seo — to be authored) |
| `backend/templates/emails/*.py`, `backend/email_service.py` | 12 (email-templates — to be authored) |
| `backend/schemas/`, `backend/contracts/schemas/` | underlying todas |
| `backend/cache/*.py`, `backend/redis_pool.py`, `backend/redis_client.py`, `backend/search_cache.py` | 01 (cache LEGACY) |
| `backend/health.py`, `backend/routes/{health,health_core}.py` | 13 (health — to be authored) |
| `backend/metrics.py`, `backend/telemetry.py`, `backend/audit.py`, `backend/log_sanitizer.py` | cross-cutting (todos) |
| `backend/sectors.py`, `backend/sectors_data.yaml` | 01 (filter), 11 (SEO) |
| `backend/config.py`, `backend/feature_flags.py` | cross-cutting |

### Frontend (top-level)

| File | Spec |
|------|------|
| `frontend/middleware.ts` | 03 |
| `frontend/app/login/page.tsx`, `frontend/app/signup/page.tsx`, `frontend/app/auth/callback/page.tsx`, `frontend/app/recuperar-senha/page.tsx`, `frontend/app/redefinir-senha/page.tsx` | 03 |
| `frontend/app/onboarding/` | 08 |
| `frontend/app/buscar/` | 01 |
| `frontend/app/dashboard/` | 08 |
| `frontend/app/historico/` | 01 (sessions list) |
| `frontend/app/pipeline/` | 04 |
| `frontend/app/mensagens/` | 07 |
| `frontend/app/conta/`, `frontend/app/planos/`, `frontend/app/pricing/`, `frontend/app/features/` | 02 |
| `frontend/app/admin/` | 09 |
| `frontend/app/{observatorio,cnpj,fornecedores,orgaos,municipios,licitacoes,contratos,blog,alertas-publicos,indice-municipal,calculadora,comparador,compliance}/` | 11 |
| `frontend/app/sitemap.xml`, `frontend/app/sitemap-N.xml/` | 11 |
| `frontend/components/{tour,billing,ui}/` | cross-cutting |
| `frontend/hooks/{usePipeline,usePlan,useAuth,useTrialPhase,useAnalytics}.ts` | 02, 03, 04, 08 |
| `frontend/app/types.ts`, `frontend/app/api-types.generated.ts` | underlying todas |
| `frontend/tailwind.config.ts`, `frontend/app/globals.css` | design-system (16) |

### Database

| Migration | Spec |
|-----------|------|
| `001_profiles_and_sessions.sql` | 02, 03 |
| `002_monthly_quota.sql`, `003_atomic_quota_increment.sql` | 02 |
| `004_add_is_admin.sql` | 03, 09 |
| `005_*plans*`, `008_billing*`, `009_plan_features`, `010_stripe_webhook_events`, `011_billing_helpers`, `015_stripe_price_ids` | 02 |
| `012_create_messages.sql` | 07 |
| `013_google_oauth_tokens.sql` | 03 |
| `014_google_sheets_exports.sql` | 10 |
| `017_sync_plan_type_trigger`, `020_tighten_plan_type_constraint`, `027_fix_plan_type_default_and_rls` | 02 |
| `024_add_profile_context.sql` | 08 |
| `025_create_pipeline_items.sql`, `20260227120002_concurrency_pipeline_version.sql`, `20260321130000_debt_db004_pipeline_search_id_comment.sql` | 04 |
| `026_search_results_cache.sql`, `027b_search_cache_add_sources_and_fetched_at.sql` | 01 (cache LEGACY) |
| `20260326000000_datalake_raw_bids.sql`, `20260413000002_trigram_index_objeto_compra.sql`, `20260424133500_extend_pncp_retention_400d.sql`, `20260424161923_seo013_index_orgao_cnpj_raw_bids.sql` | 05 |
| `20260424180000_trial_email_delivery_tracking.sql` | 12 |

## Test → Spec

| Test file | Specs validadas |
|-----------|-----------------|
| `backend/tests/test_pipeline*.py`, `test_search_*.py` | 01 |
| `backend/tests/test_filter*.py`, `test_llm_arbiter*.py` | 01 |
| `backend/tests/test_cache_*.py`, `test_swr*.py` | 01 (cache LEGACY) |
| `backend/tests/test_billing_*.py`, `test_stripe_*.py`, `test_quota_*.py` | 02 |
| `backend/tests/test_auth_*.py`, `test_jwt_*.py`, `test_oauth_*.py` | 03 |
| `backend/tests/test_pipeline_kanban.py` (se existe), tests pipeline routes | 04 |
| `backend/tests/test_ingestion*.py`, `test_datalake*.py` | 05 |
| `backend/tests/test_jobs*.py`, `test_cron*.py` | 06 |
| `backend/tests/test_feedback*.py`, `test_messages*.py` | 07 |
| `backend/tests/test_onboarding*.py`, `test_analytics*.py` | 08 |
| `backend/tests/test_admin*.py` | 09 |
| `backend/tests/test_excel*.py`, `test_google_sheets*.py`, `test_pdf*.py` | 10 |
| `backend/tests/test_observatorio*.py`, `test_seo*.py`, `test_sitemap*.py` | 11 |
| `backend/tests/test_email*.py` | 12 |
| `backend/tests/test_timeout_invariants.py` | 01 (NFR-1) |
| `frontend/__tests__/components/`, `frontend/e2e-tests/` | UI specs |

## Spec coverage

| Spec ID | Spec name | Status | Author |
|---------|-----------|--------|--------|
| 01 | search-pipeline | ✅ written | Reversa Writer |
| 02 | billing-quota | ✅ written | Reversa Writer |
| 03 | auth-oauth | ✅ written | Reversa Writer |
| 04 | pipeline-kanban | ✅ written | Reversa Writer |
| 05 | ingestion-datalake | ✅ written | Reversa Writer |
| 06 | jobs+cron | ⏭ deferred | flowchart in `flowcharts/jobs-cron.md` cobre 80% |
| 07 | messages-feedback | ⏭ deferred | flowchart cobre |
| 08 | onboarding-analytics | ⏭ deferred | flowchart cobre |
| 09 | admin | ⏭ deferred | code-analysis cobre |
| 10 | exports | ⏭ deferred | flowchart cobre |
| 11 | observatory-seo | ⏭ deferred | flowchart cobre |
| 12 | email-templates | ⏭ deferred | code-analysis cobre |
| 13 | health | ⏭ deferred | implícita em `health.py` + `health_core.py` |
| 14 | schemas-contracts | ⏭ implícita | flowchart `schemas-contracts.md` |
| 15 | routes (registration) | ⏭ implícita | flowchart `routes.md` |
| 16 | design-system | ⏭ deferred | code-analysis módulo 16 cobre |
| 17 | tests-migrations | ⏭ deferred | code-analysis módulo 18 cobre |
| 14b | llm-response-cache | ✅ written | LLM-CACHE-SPEC-001 — `_reversa_sdd/specs/14-llm-response-cache.spec.md` (PR #160 shipped 2026-05-08) |

## Bidirectional traceability

Para qualquer mudança em código:
1. Identifique spec via Code → Spec table
2. Atualize spec se mudou comportamento
3. Atualize tests correspondentes
4. Verifique migration paired (.down.sql) se schema change
5. Regen `frontend/app/api-types.generated.ts` se mudou response_model

---

## Stories Status — Refresh 2026-05-01 a 2026-05-02

### EPIC-RES-BE-2026-Q2 (Operational Reliability)

| Story | Descrição | Status | PR |
|-------|-----------|--------|-----|
| RES-BE-015 | `_run_with_budget` sweep em 15 rotas long-tail SEO (escopo expandido 2026-05-01: 11 → 15 rotas + 4 f6b7acb2 callsites + audit script + CI gate + load test) | InReview | #603/#600 |
| RES-BE-016 | CRIT-084 fix: sync helper calls wrapped em async handlers; route-level asyncio timeout middleware 60s→503 (AC4) | InProgress | #588 + commits |
| RES-BE-017 | Pool leak mitigation: `asyncio.wait_for` + `asyncio.to_thread` cleanup — Sprint 2, bloqueado por RES-BE-015+016 soak | Ready | — |
| RES-BE-018a | MFA bare `.execute()` wrapping | Done | #589 |

### EPIC-SEO-PROG-2026-Q2 (Programmatic SEO)

| Story | Descrição | Status | PR/Commit |
|-------|-----------|--------|-----------|
| SEO-016 | GSC sub-sitemap cache-control: `s-maxage=86400` via next.config.js (SYS-019) + `baa481f8` middleware.ts | Done | baa481f8 + SYS-019 |
| SEO-026 | robots.txt RFC 9309 prefix-match fix — libera `/alertas-publicos/*` para indexação | Done | #595 |
| SEO-PROG-007 | `robots.ts` dynamic route handler (substitui static `robots.txt`) | Done | #546 |
| SEO-PROG-008 | `getBackendUrl` helper + chain audit + CI gate BACKEND_URL scope-limited | Done | 591b6174 |
| CTR-OPT-001 | Rewrite title/meta dos 6 top blog posts GSC (taxa CTR GSC) | Done | #622 |

### EPIC-CONV-DIAG-2026-04-30 (Conversão SEO → Trial) ← Novo

| Story | Descrição | Status |
|-------|-----------|--------|
| CONV-CTA-001 | CTA trial contextual em páginas `/contratos/[setor]/[uf]` e orgão | InReview |
| CONV-CTA-002 | Audit e CTA em templates programáticos W2 (gated: CONV-CTA-001 7-14d + bounce/CTR discriminador) | Draft (NO-GO gated) |
| CONV-INST-001 | Mixpanel: page-load + traffic source + UTM tracking em páginas SEO | InReview |
| CONV-INST-002 | Mixpanel: signup form lifecycle events (field focus, submit, error, success) | InReview |
| CONV-INST-003 | Email confirmation lifecycle events (sent, opened, clicked, expired, re-sent) | InReview |
| CONV-INST-005 | MS Clarity: trial onboarding tagging (heatmaps + session recording por step) | Ready |

### Outros PRs 2026-05-01/02

| Story/Fix | Descrição | Status | PR/Commit |
|-----------|-----------|--------|-----------|
| MON-FN-005 | `/health/ready` usa `sb_execute_direct` (5s timeout) + Mixpanel startup assertion | InReview | #602 |
| SEN-BE-002 | Strip `top_result_*` columns de `search_sessions` queries (migration unapplied corrigida) | Done | #591 |
| TD-BE-014 | `PNCPRateLimitError` carrega `retry_after`; levantado em exhaustion 429 | Done | #592 |
| DEBT-OBS-001 | `is_historical` boundary: usa last-day of month (não 30d-from-start) | Done | 047e0a6b |
| Security | UUID v4 validation em `authorization.get_admin_ids` | Done | 7cf341ed |

### Arquivos de código impactados (2026-05-01/02)

| Arquivo | Mudança | Story |
|---------|---------|-------|
| `backend/routes/blog_stats.py` | `_run_with_budget(5s)` + negative cache | RES-BE-015 |
| `backend/routes/contratos_publicos.py` | `_run_with_budget` + refactor f6b7acb2 waitfor→budget | RES-BE-015 |
| `backend/routes/empresa_publica.py` | `_run_with_budget(5s)` + negative cache | RES-BE-015 |
| `backend/routes/orgao_publico.py` | `_run_with_budget(5s)` + negative cache | RES-BE-015 |
| `backend/routes/observatorio.py` | `_run_with_budget(5s)` + negative cache | RES-BE-015 |
| `backend/routes/dados_publicos.py` | `_run_with_budget(5s)` | RES-BE-015 |
| `backend/routes/municipios_publicos.py` | `_run_with_budget(8s, maior por query volume)` | RES-BE-015 |
| `backend/routes/itens_publicos.py` | `_run_with_budget(5s)` | RES-BE-015 |
| `backend/routes/compliance_publicos.py` | `_run_with_budget(5s)` | RES-BE-015 |
| `backend/routes/alertas_publicos.py` | `_run_with_budget(5s)` | RES-BE-015 |
| `backend/routes/sectors_public.py` | `_run_with_budget(5s)` | RES-BE-015 |
| `backend/middleware/route_timeout.py` | Route-level asyncio timeout 60s → 503 (AC4 RES-BE-016) | RES-BE-016 |
| `backend/health.py` + `health_core.py` | `sb_execute_direct` (5s) em `/health/ready`; Mixpanel startup assertion | MON-FN-005 |
| `backend/authorization.py` | UUID v4 validation em `get_admin_ids` | security |
| `backend/routes/observatorio.py` | `is_historical` last-day boundary fix | DEBT-OBS-001 |
| `frontend/next.config.js` (SYS-019) | `headers()` com `source: '/sitemap/:path*'` → `s-maxage=86400` | SEO-016 |
| `frontend/app/robots.ts` | Dynamic route handler | SEO-PROG-007 |
| `frontend/lib/getBackendUrl.ts` | Helper chain: env → internal hostname → fallback | SEO-PROG-008 |
| `backend/pncp_client.py` | `PNCPRateLimitError` com `retry_after` | TD-BE-014 |
| `backend/scripts/audit_execute_without_budget.py` | Audit script CI gate | RES-BE-015 |
| `.github/workflows/audit-execute-without-budget.yml` | CI gate: zero violations mandatório | RES-BE-015 |
