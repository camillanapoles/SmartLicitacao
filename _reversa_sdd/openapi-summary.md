# OpenAPI Summary — SmartLic v0.5

> Gerado pelo **Reversa Writer** em 2026-04-27
> Source-of-truth: `frontend/app/api-types.generated.ts` (autogen via `npm run generate:api-types` + STORY-2.1 codegen)
> Total: **187 endpoints** em **65 routers** (registrados em `startup/routes.py`)

## Versioning

- Prefixo: `/v1/*` para todas APIs autenticadas e públicas
- Exceções (root): `/health/live`, `/health/ready`, `/sources/health`, `/webhooks/stripe`
- Self-prefixed: `/v1/admin/*` (admin_trace, admin_cron, admin_llm_cost, slo)

## Tag Groups

| Tag | Endpoints | Owner |
|-----|-----------|-------|
| `search` | 9 | Search team |
| `pipeline` | 5 | Pipeline team |
| `billing` | 5 | Billing team |
| `auth-signup` / `auth-check` / `auth-email` / `oauth` | 5 | Auth team |
| `user` | 13 | User team |
| `analytics` | 6 | Analytics |
| `messages` | 6 | Support |
| `feedback` | 3 | ML Quality |
| `alerts` | 7 | Notifications |
| `onboarding` | 2 | GTM |
| `health` / `health-core` | 11 | SRE |
| `admin` | ~25 | Admin/SRE |
| `MFA` | 4 | Security |
| `organizations` | 8 | Multi-tenant |
| `partners` / `referral` | 8 | Growth |
| `sectors` | 3 | Public |
| `subscriptions` / `founding` / `conta` / `trial` | 8 | Billing |
| `feature-flags` | 4 (admin+public) | DevOps |
| `metrics` | 3 | SRE |
| `seo_admin` / `admin-slo` | 3 | SEO/SRE |
| `observatorio` / `blog-stats` / `*-publicos` | ~30 | SEO programmatic |
| `sitemap` | 5 | SEO |
| `daily_digest` / `weekly_digest` | 4 | Email |
| `share` / `lead-capture` / `relatorio` / `bid-analysis` / `reports` | 8 | Misc |
| `export` / `calculadora` / `comparador` / `indice-municipal` / `notifications` / `emails` / `trial-emails` / `feedback` | ~15 | Various |

## Endpoint Inventory (sumário)

### Auth & Onboarding (15)

```
POST   /v1/auth/signup                       SignupRequest → SignupResponse
GET    /v1/auth/check-email
GET    /v1/auth/check-phone
POST   /v1/auth/validate-signup-email
POST   /v1/auth/resend-confirmation
GET    /v1/auth/status
GET    /api/auth/google
GET    /api/auth/google/callback
DELETE /api/auth/google
GET    /v1/mfa/status
POST   /v1/mfa/recovery-codes
POST   /v1/mfa/verify-recovery
POST   /v1/mfa/regenerate-recovery
POST   /v1/first-analysis                    FirstAnalysisRequest → FirstAnalysisResponse
POST   /v1/onboarding/tour-event             TourEventRequest → 204
```

### Search (9)

```
POST   /v1/buscar                            BuscaRequest → SearchQueuedResponse | BuscaResponse
GET    /v1/buscar-progress/{search_id}       SSE
GET    /v1/buscar-results/{search_id}
GET    /v1/search/{search_id}/status         → SearchStatusResponse
GET    /v1/search/{search_id}/timeline
GET    /v1/search/{search_id}/results
GET    /v1/search/{search_id}/zero-match
POST   /v1/search/{search_id}/regenerate-excel
POST   /v1/search/{search_id}/retry
POST   /v1/search/{search_id}/cancel
```

### Pipeline (5)

```
POST   /v1/pipeline                          PipelineItemCreate → PipelineItemResponse (201)
GET    /v1/pipeline                          → PipelineListResponse
PATCH  /v1/pipeline/{item_id}                PipelineItemUpdate → PipelineItemResponse
DELETE /v1/pipeline/{item_id}                → 200
GET    /v1/pipeline/alerts                   → PipelineAlertsResponse
```

### Billing & Subscriptions (13)

```
GET    /v1/plans                             → BillingPlansResponse
POST   /v1/checkout                          → CheckoutResponse
POST   /v1/billing-portal
GET    /v1/subscription/status
POST   /v1/billing/setup-intent              → SetupIntentResponse
POST   /v1/api/subscriptions/update-billing-period
POST   /v1/api/subscriptions/cancel
POST   /v1/api/subscriptions/cancel-feedback
POST   /v1/founding/checkout                 → FoundingCheckoutResponse
GET    /v1/conta/cancelar-trial
POST   /v1/conta/cancelar-trial
POST   /v1/trial/extend                      → ExtendResponse
GET    /v1/trial/extensions                  → ExtensionsStatusResponse
GET    /v1/api/plans                         → PlansResponse
POST   /webhooks/stripe                      Stripe events (signature gated)
```

### User (13)

```
POST   /v1/change-password
GET    /v1/me                                → UserProfileResponse
GET    /v1/trial-status                      → TrialStatusResponse
GET    /v1/user/recommended-plan             → RecommendedPlanResponse
PUT    /v1/profile/context                   → PerfilContextoResponse
GET    /v1/profile/context                   → PerfilContextoResponse
GET    /v1/profile/completeness              → ProfileCompletenessResponse
GET    /v1/profile/alert-preferences         → AlertPreferencesResponse
PUT    /v1/profile/alert-preferences         → AlertPreferencesResponse
DELETE /v1/me                                → DeleteAccountResponse
GET    /v1/me/export                         (LGPD data export)
POST   /v1/trial/exit-survey                 → ExitSurveyResponse (201)
GET    /v1/admin/trial-exit-surveys          (admin)
```

### Analytics (6)

```
GET    /v1/analytics/summary                 → SummaryResponse
GET    /v1/analytics/searches-over-time      → SearchesOverTimeResponse
GET    /v1/analytics/top-dimensions          → TopDimensionsResponse
GET    /v1/analytics/trial-value             → TrialValueResponse
GET    /v1/analytics/new-opportunities       → NewOpportunitiesResponse
POST   /v1/analytics/track-cta               → 204
```

### Messages (6)

```
POST   /v1/api/messages/conversations           → CreateConversationResponse (201)
GET    /v1/api/messages/conversations           → ConversationsListResponse
GET    /v1/api/messages/conversations/{id}      → ConversationDetail
POST   /v1/api/messages/conversations/{id}/reply → ReplyStatusResponse (201)
PATCH  /v1/api/messages/conversations/{id}/status → StatusResponse
GET    /v1/api/messages/unread-count            → UnreadCountResponse
```

### Feedback (3)

```
POST   /v1/feedback                          FeedbackRequest → FeedbackResponse (201)
DELETE /v1/feedback/{feedback_id}            → FeedbackDeleteResponse
GET    /v1/admin/feedback/patterns           → FeedbackPatternsResponse (admin)
```

### Alerts (7)

```
POST   /v1/alerts                            (201)
GET    /v1/alerts                            → AlertListResponse
PATCH  /v1/alerts/{alert_id}
DELETE /v1/alerts/{alert_id}                 (200)
GET    /v1/alerts/{alert_id}/unsubscribe     HTML
GET    /v1/alerts/{alert_id}/preview         → AlertPreviewResponse
GET    /v1/alerts/{alert_id}/history         → AlertHistoryResponse
```

### Health (11)

```
GET    /health                               → HealthResponse
GET    /health/live
GET    /health/ready
GET    /health/cache
GET    /health/tasks
GET    /health/sources                       → SourcesHealthResponse
GET    /sources/health                       (alt)
GET    /status
GET    /status/incidents
GET    /status/uptime-history
GET    /                                     → RootResponse
```

### Admin (~25)

```
GET    /v1/admin/users                       → AdminUsersListResponse
POST   /v1/admin/users                       → AdminCreateUserResponse
DELETE /v1/admin/users/{user_id}             → AdminDeleteUserResponse
PUT    /v1/admin/users/{user_id}             → AdminUpdateUserResponse
POST   /v1/admin/users/{user_id}/reset-password → AdminResetPasswordResponse
POST   /v1/admin/users/{user_id}/assign-plan → AdminAssignPlanResponse
PUT    /v1/admin/users/{user_id}/credits     → AdminUpdateCreditsResponse
GET    /v1/admin/filter-stats
GET    /v1/admin/cache/metrics
GET    /v1/admin/cache/{params_hash}
DELETE /v1/admin/cache/{params_hash}
DELETE /v1/admin/cache
GET    /v1/admin/reconciliation/history
POST   /v1/admin/reconciliation/trigger
GET    /v1/admin/support-sla
GET    /v1/admin/trial-metrics
GET    /v1/admin/at-risk-trials
GET    /v1/admin/search-trace/{search_id}
POST   /v1/admin/cb/reset
GET    /v1/admin/schema-contract-status
GET    /v1/admin/cron-status
POST   /v1/admin/trigger-contracts-backfill
POST   /v1/admin/trigger-bids-backfill
POST   /v1/admin/clear-contracts-checkpoints
GET    /v1/admin/llm-cost
GET    /v1/admin/seo-metrics                 → SEOMetricsResponse
GET    /v1/admin/slo
GET    /v1/admin/slo/alerts
GET    /v1/admin/feature-flags               → FeatureFlagListResponse
PATCH  /v1/admin/feature-flags/{flag_name}   → FeatureFlagUpdateResponse
POST   /v1/admin/feature-flags/reload        → FeatureFlagReloadResponse
GET    /v1/admin/partners
POST   /v1/admin/partners                    (201)
GET    /v1/admin/partners/{partner_id}/referrals
GET    /v1/admin/partners/{partner_id}/revenue
GET    /v1/admin/trial-emails/preview
POST   /v1/admin/trial-emails/test-send
```

### Organizations (8)

```
GET    /v1/organizations/me
POST   /v1/organizations                     (201)
GET    /v1/organizations/{org_id}
POST   /v1/organizations/{org_id}/invite
POST   /v1/organizations/{org_id}/accept
DELETE /v1/organizations/{org_id}/members/{target_user_id}
GET    /v1/organizations/{org_id}/dashboard
PUT    /v1/organizations/{org_id}/logo
```

### Partner & Referral (5)

```
GET    /v1/partner/dashboard
GET    /v1/referral/code                     → ReferralCodeResponse
GET    /v1/referral/stats                    → ReferralStatsResponse
POST   /v1/referral/redeem                   → ReferralRedeemResponse
```

### Public Sectors (3)

```
GET    /v1/sectors                           → list[SectorListItem]
GET    /v1/sectors/trending                  → list[TrendingSector]
GET    /v1/sectors/{slug}/stats              → SectorStatsResponse
```

### SEO Programmatic Public (~30)

```
GET    /v1/observatorio/...                  (panorama setor + UF)
GET    /v1/blog/stats/setor/{setor_id}       → SectorBlogStats
GET    /v1/blog/stats/setor/{setor_id}/uf/{uf} → SectorUfStats
GET    /v1/blog/stats/cidade/{cidade}        → CidadeStats
GET    /v1/blog/stats/cidade/{cidade}/setor/{setor_id} → CidadeSectorStats
GET    /v1/blog/stats/panorama/{setor_id}    → PanoramaStats
GET    /v1/blog/stats/contratos/{setor_id}   → ContratosSetorStats
GET    /v1/blog/stats/contratos/{setor_id}/uf/{uf} → ContratosSetorUfStats
GET    /v1/blog/stats/contratos/cidade/{cidade} → ContratosCidadeStats
GET    /v1/empresa/...                       (CNPJ profile)
GET    /v1/orgao/{slug}                      (orgao publico)
GET    /v1/contratos/{setor}                 (e variações)
GET    /v1/dados-publicos/...
GET    /v1/municipios/{slug}/...
GET    /v1/itens/...
GET    /v1/compliance/{cnpj}
GET    /v1/indice-municipal/...
GET    /v1/alertas/{setor_id}/uf/{uf}        → AlertasResponse
GET    /v1/comparador/buscar                 → ComparadorSearchResponse
GET    /v1/comparador/bids                   → ComparadorBidsResponse
GET    /v1/calculadora/...
GET    /v1/daily-digest/...
GET    /v1/weekly-digest/...
```

### Sitemap (5)

```
GET    /v1/sitemap-licitacoes.xml
GET    /v1/sitemap-licitacoes-do-dia.xml
GET    /v1/sitemap-orgaos.xml
GET    /v1/sitemap-cnpjs.xml
POST   /v1/sitemap-cnpjs/...                 (admin trigger)
```

### Export (3)

```
POST   /v1/export/pdf                        → application/pdf
POST   /v1/api/export/google-sheets          → GoogleSheetsExportResponse
GET    /v1/api/export/google-sheets/history  → GoogleSheetsExportHistoryResponse
```

### Sessions (2)

```
GET    /v1/sessions                          → SessionsListResponse
GET    /v1/sessions/{search_id}/download
```

### Bid Analysis & Reports (3)

```
POST   /v1/bid-analysis/{bid_id}             → DeepBidAnalysis
POST   /v1/reports/diagnostico
POST   /v1/relatorio-2026-t1/request         → RelatorioResponse
```

### Share (2)

```
POST   /v1/share/analise                     → ShareAnaliseResponse
GET    /v1/share/analise/{hash}              → SharedAnalisePublic
```

### Lead Capture (1)

```
POST   /v1/lead-capture                      → LeadCaptureResponse
```

### Emails (2)

```
POST   /v1/emails/send-welcome               → WelcomeEmailResponse
GET    /v1/emails/unsubscribe                HTML
```

### Trial Emails (4)

```
GET    /v1/trial-emails/unsubscribe          HTML
POST   /v1/trial-emails/webhook              (Resend webhook, HMAC verify GAP)
GET    /v1/admin/trial-emails/preview        admin
POST   /v1/admin/trial-emails/test-send      admin
```

### Feature Flags Public (1)

```
GET    /v1/api/features/me                   → UserFeaturesResponse
```

### Metrics (3)

```
GET    /v1/metrics/discard-rate
GET    /v1/metrics/daily-volume              → DailyVolumeResponse
POST   /v1/metrics/sse-fallback              → 204
```

### Notifications (2)

```
GET    /v1/notifications/new-bids-count      → NewBidsCountResponse
DELETE /v1/notifications/new-bids-count
```

## Response Models de Destaque

Ver `backend/schemas/` (88 BaseModels). Source de codegen frontend: `frontend/app/api-types.generated.ts`.

## Authentication

| Tipo | Aplicação |
|------|-----------|
| Bearer JWT (Supabase Auth) | maioria endpoints `/v1/*` |
| (none — public) | `/observatorio`, `/sectors`, `/sitemap*`, `/blog/stats`, `/calculadora`, `/comparador`, `/lead-capture`, `/share/analise/{hash}`, `/health/*`, `/auth/check-*` |
| Stripe signature | `/webhooks/stripe` |
| Resend HMAC | `/v1/trial-emails/webhook` (GAP — não impl) |
| User-OAuth Google | `/v1/api/export/google-sheets/*` |
| Admin role | `/v1/admin/*` |

## Status Codes Convention

- `200` OK normal
- `201` Created
- `202` Accepted (async — `POST /buscar` queued)
- `204` No Content (track-cta, tour-event, sse-fallback, delete notif)
- `400` Bad Request (Stripe signature)
- `401` Unauthorized
- `403` Forbidden (trial_expired, plan_capability_missing, admin_required)
- `404` Not Found
- `409` Conflict (optimistic lock, unique violation)
- `422` Validation Error (Pydantic)
- `429` Too Many Requests (quota, rate limit)
- `500` Internal Server Error
- `503` Service Unavailable (timeout, CB open)

## Cache layers (transparent — não exposto via API)

- **Search results cache** (per-request): L1 InMemoryCache (4h) + L2 Supabase `search_results_cache` (24h). Afeta `POST /v1/buscar`. Detalhes em spec `01-search-pipeline.spec.md` FR-4.
- **LLM summary cache** (PR #160, 2026-05-08): Redis SETEX TTL=7d em `llm:summary:{sha256}`. Wrapper `get_or_generate_resumo_cached` (`backend/llm.py:841`) substitui `gerar_resumo()` em `pipeline/stages/generate.py:273` (síncrono no pipeline `/v1/buscar`) e `jobs/queue/jobs.py:428` (`llm_summary_job` ARQ background, dispara após `POST /v1/buscar` em modo async). Cache hit reduz latência da etapa LLM da ordem de segundos para <50ms p95 e elimina custo OpenAI da chamada repetida. Falha de Redis é graceful — chama OpenAI direto. Detalhes em spec `14-llm-response-cache.spec.md`. Métricas: `smartlic_llm_summary_cache_{hits,misses}_total`.

## CI Gate

`.github/workflows/api-types-check.yml` extrai schema da FastAPI app e compara com `frontend/app/api-types.generated.ts`. Drift bloqueia PR.

Regen local:
```bash
cd backend && uvicorn main:app --port 8000 &
npm --prefix frontend run generate:api-types
git add frontend/app/api-types.generated.ts
```
