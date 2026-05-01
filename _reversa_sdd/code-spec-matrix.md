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

## Bidirectional traceability

Para qualquer mudança em código:
1. Identifique spec via Code → Spec table
2. Atualize spec se mudou comportamento
3. Atualize tests correspondentes
4. Verifique migration paired (.down.sql) se schema change
5. Regen `frontend/app/api-types.generated.ts` se mudou response_model
