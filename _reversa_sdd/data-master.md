# Data Master — Análise Completa do Banco

> Gerado pelo **Reversa Data Master** em 2026-04-27
> Fonte: `supabase/migrations/` (183 arquivos), `backend/migrations/` (12 legacy), `data-dictionary.md`

## 1. Stack

- **Database**: Supabase Postgres 17
- **Auth**: Supabase Auth (`auth.users` schema, JWT JWKS)
- **Storage**: Supabase Storage (signed URLs)
- **Connection**: PostgREST + direct via service-role key
- **RLS**: enabled em todas user-scoped tables
- **pg_cron**: scheduled jobs (purge, cleanup) com `cron_job_health` view monitorada
- **Migrations**: source of truth em `supabase/migrations/` (CRIT-050 auto-apply em deploy)

## 2. Tables (48 total)

### Core User & Auth

| # | Table | PK | FKs | RLS | Retention |
|---|-------|-----|-----|-----|-----------|
| 1 | `profiles` | `id (uuid)` | → `auth.users.id` | `user_id = auth.uid()` | infinite |
| 2 | `monthly_quota` | `(user_id, year, month)` | → `profiles` | self | infinite |
| 3 | `audit_events` | `id` | optional `user_id` | admin only | 90d |
| 4 | `mfa_recovery_codes` | `id` | → `profiles` | self | until used |
| 5 | `mfa_recovery_attempts` | `id` | → `profiles` | self | 30d |
| 6 | `user_oauth_tokens` | `(user_id, provider)` | → `profiles` | self | until revoke |

**Notable columns em `profiles`:**
- `id` (uuid, PK, references auth.users.id)
- `email`, `name`, `phone`
- `plan_type` (text, CHECK constraint enum, default 'free_trial' — synced via trigger)
- `trial_expires_at` (timestamptz)
- `is_admin` (bool, default false)
- `is_master` (bool, default false)
- `whatsapp_consent` (bool, STORY-007)
- `stripe_customer_id`, `stripe_default_pm_id` (2026-04-20 mig)
- `context_jsonb` (PerfilContexto: cnae, ufs, faixa_valor, porte, experiencia, ...)
- `subscription_status` (active, past_due, canceled, expired, trialing)
- `created_at`, `updated_at`

### Plans & Billing

| # | Table | PK | Notes |
|---|-------|-----|-------|
| 7 | `plans` | `id (text)` | catalog hardcoded sync |
| 8 | `plan_features` | `(plan_id, feature)` | feature flags por plan |
| 9 | `plan_billing_periods` | `id (uuid)` | source of truth pricing (monthly/sem/annual) |
| 10 | `user_subscriptions` | `id (uuid)` | Stripe sync; status, period_end |
| 11 | `stripe_webhook_events` (events_processed) | `id (text)` | idempotência (CRIT-072) |
| 12 | `reconciliation_log` | `id` | Stripe ↔ DB drift |
| 13 | `trial_email_log` | `id` | (lifecycle email tracking) |
| 14 | `trial_email_dlq` | `id` | dead letter queue (failed sends) |
| 15 | `trial_extensions` | `id` | manual extensions |
| 16 | `trial_exit_surveys` | `id` | exit feedback |

### Search & Pipeline

| # | Table | PK | Notes |
|---|-------|-----|-------|
| 17 | `search_sessions` | `search_id (uuid)` | mutável durante pipeline |
| 18 | `search_state_transitions` | `(search_id, sequence)` | append-only, todas transições |
| 19 | `search_results_cache` | `params_hash (text)` | TTL 24h pg_cron `cleanup-search-cache` |
| 20 | `search_results_store` | `(search_id, field)` | TTL 24h pg_cron `cleanup-search-store` |
| 21 | `pipeline_items` | `id (uuid)` | unique(user_id, pncp_id), version locking |
| 22 | `classification_feedback` | `id` | upsert por (user, search, bid) |
| 23 | `saved_filter_presets` | `id` | custom filter saves |
| 24 | `shared_analyses` | `id`, `hash (text)` | public read by hash |

### DataLake (Layer 1 ETL)

| # | Table | PK | Retention |
|---|-------|-----|-----------|
| 25 | `pncp_raw_bids` | `(content_hash)` ou `id` | 400d (`purge_old_bids` 7 UTC daily) |
| 26 | `pncp_supplier_contracts` | `(content_hash)` | similar |
| 27 | `enriched_entities` | `cnpj` | refresh ~30d (BrasilAPI) |
| 28 | `indice_municipal` | `(municipio, uf)` | refresh job |
| 29 | `ingestion_checkpoints` | `id` | active progress |
| 30 | `ingestion_runs` | `id` | 90d audit |

### Notifications & Engagement

| # | Table | PK | Notes |
|---|-------|-----|-------|
| 31 | `alerts` | `id` | per-user saved searches → email |
| 32 | `alert_sent_items` | `id` | dedup já enviado |
| 33 | `alert_runs` | `id` | execution log |
| 34 | `alert_preferences` | `user_id` | 1:1 |
| 35 | `conversations` | `id` | InMail threads |
| 36 | `messages` | `id` | thread messages |
| 37 | `tour_events` | `id` | Shepherd telemetry |
| 38 | `cta_tracking` | `id` | CTA click events |

### Multi-tenant & Growth

| # | Table | PK | Notes |
|---|-------|-----|-------|
| 39 | `organizations` | `id` | multi-seat consultoria |
| 40 | `organization_members` | `(org_id, user_id)` | role membership |
| 41 | `partners` | `id` | partner program |
| 42 | `partner_referrals` | `id` | attribution |
| 43 | `referrals` | `id` | user-to-user referral |
| 44 | `leads`, `report_leads`, `founding_leads` | `id` | landing forms capture |

### Operations

| # | Table | PK | Notes |
|---|-------|-----|-------|
| 45 | `health_checks` | `id` | 7d retention |
| 46 | `incidents` | `id` | manual + auto |
| 47 | `seo_metrics` | `id` | snapshots GSC + sitemap |
| 48 | `google_sheets_exports` | `id` | export history |

## 3. RPCs (PostgreSQL functions)

| RPC | Args | Returns | Purpose |
|-----|------|---------|---------|
| `upsert_pncp_raw_bids(rows jsonb)` | bid array | row count | ETL upsert content_hash dedup |
| `purge_old_bids(retention_days int)` | days | count | retention cleanup |
| `cleanup_search_cache()` | — | count | TTL via pg_cron |
| `cleanup_search_store()` | — | count | similar |
| `search_datalake(filters jsonb)` | params | bids[] | full-text search principal <100ms p95 |
| `get_panorama_setor(setor_id, days, uf)` | — | panorama | SEO programmatic |
| `get_contratos_orgao(cnpj, ...)` | — | contratos | SEO |
| `get_contratos_setor(setor, uf)` | — | contratos | SEO |
| `get_top_fornecedores_setor(setor_id)` | — | fornecedores | SEO |
| `get_alertas_setor_uf(setor_id, uf)` | — | preview | público |
| `check_and_increment_quota_atomic(user_id, year, month, limit int)` | — | (allowed, current, limit) | race-safe quota |
| `get_cron_health()` | — | jsonb | pg_cron monitoring |
| `get_table_columns_simple(table_name)` | — | columns | introspection (admin) |

## 4. Indexes Notáveis

| Index | Table | Type | Purpose |
|-------|-------|------|---------|
| GIN `objeto_tsvector` | `pncp_raw_bids` | GIN tsvector('portuguese') | full-text search |
| Trigram `objeto` | `pncp_raw_bids` | gin_trgm_ops | similar-string search |
| Composite `(setor, uf, data_publicacao DESC)` | `pncp_raw_bids` | btree | filtered ordered queries |
| `cnpj_orgao` | `pncp_raw_bids` | btree (SEO-013) | orgao profile queries |
| `(user_id, created_at DESC)` | `search_sessions` | composite | dashboard queries |
| `params_hash` | `search_results_cache` | PK btree | cache lookup |
| Unique `(user_id, pncp_id)` | `pipeline_items` | btree | idempotent insert |
| `user_id` partial WHERE NOT NULL | many tables | btree (RLS support) | RLS performance (2026-03-07 mig) |
| Trigram `municipio` | `pncp_supplier_contracts` (`psc_municipio_trgm`) | gin_trgm_ops | (memory: planner não-pick com ORDER+LIMIT) |
| `state` | `search_state_transitions` | composite (search_id, sequence) | timeline queries |

## 5. RLS Policies

Todas tables com `user_id` têm RLS ativo:
- SELECT: `user_id = auth.uid()`
- INSERT: `user_id = auth.uid()` (defesa via service-role bypass + `.eq("user_id")` defense-in-depth)
- UPDATE: `user_id = auth.uid()`
- DELETE: `user_id = auth.uid()` (com exceções admin-only)

Exceções:
- `audit_events`: admin-only
- `incidents`: admin write, public read
- `health_checks`: system write, admin read
- `pncp_raw_bids`, `pncp_supplier_contracts`: público SELECT (SEO programmatic via service-role bypass)
- `plans`, `plan_features`, `plan_billing_periods`: público SELECT
- `shared_analyses`: SELECT por hash sem auth (public share)

`statement_timeout`:
- anon: 3s (memory)
- authenticated: 8s
- service_role: NULL (sem timeout) — backend usa service-role + risco pool exhaustion (memory `reference_supabase_service_role_no_timeout_default`)

## 6. pg_cron Schedules

| Job | Schedule | Function | Notes |
|-----|----------|----------|-------|
| `purge-old-bids` | `0 7 * * *` (07 UTC daily) | `purge_old_bids(400)` | STORY-1.2 |
| `cleanup-search-cache` | env | `cleanup_search_cache()` | 24h TTL |
| `cleanup-search-store` | env | `cleanup_search_store()` | 24h TTL |

Monitor: `cron_job_health` view + `get_cron_health()` RPC + ARQ hourly `cron_monitoring_job` (Sentry alert se >25h sem rodar).

## 7. Migrations Policy (STORY-6.3)

- **Source of truth**: `supabase/migrations/YYYYMMDDHHMMSS_description.sql`
- **Pair `.down.sql` mandatory** (STORY-6.2) — block PR se faltar
- **Apply**: `npx supabase db push --include-all` (CI auto-apply em `deploy.yml`)
- **NOTIFY pgrst** após push para reload schema cache
- Smoke test verifica no PGRST205 errors
- Legacy `backend/migrations/` (12 arquivos): histórico audit only, NÃO executar

## 8. Migration CI Flow (CRIT-050) — 3 layers

1. **PR Warning** (`migration-gate.yml`): lista pending + valida `.down.sql` paired
2. **Push Alert** (`migration-check.yml`): block se unapplied detected
3. **Auto-Apply** (`deploy.yml`): `supabase db push` pós-deploy

## 9. Lacunas

- 🔴 RLS policies não-documentadas exhaustively (precisa export `SELECT polname, polrelid::regclass FROM pg_policy`)
- 🟡 `service_role` sem statement_timeout (memory) — risco identificado mas não-fixed
- 🔴 `psc_municipio_trgm` index criado mas planner não-pick com ORDER+LIMIT (memory) — query rewrite pendente
- 🟡 Foreign keys: investigar CASCADE vs RESTRICT consistency (e.g., `pipeline_items.user_id` ON DELETE CASCADE?)
- 🟢 Migration `.down.sql` paired enforcement live via CI

## 10. ERD ASCII (resumido)

```
auth.users
   │ 1:1
   ▼
profiles ────┬───────────────────────────────────────┬──────────────┬─────────┬────────────┐
   │         │                                       │              │         │            │
   │         │  1:N                                  │  1:N         │  1:1    │  1:N       │
   │         ▼                                       ▼              ▼         ▼            ▼
   │  search_sessions ─── 1:N ──► search_state_   pipeline_items  monthly_  alerts ─ 1:N ─ alert_sent_items
   │                                  transitions                  quota                 alert_runs
   │  classification_feedback   ◄── 1:N ──┘                                              alert_preferences (1:1)
   │  conversations ────── 1:N ──► messages
   │  user_subscriptions
   │  trial_email_log ◄ webhook tracking ◄ Resend
   │  user_oauth_tokens
   │  saved_filter_presets
   │  shared_analyses
   │  trial_exit_surveys, trial_extensions
   │  mfa_recovery_codes, mfa_recovery_attempts
   │  organization_members ────► organizations
   ▼
plans ◄─ FK ── user_subscriptions
   │
   ▼
plan_features (1:N), plan_billing_periods (1:N)

ETL Layer (system-owned, no user FK):
pncp_raw_bids (400d retention)
pncp_supplier_contracts
enriched_entities (CNPJ master)
indice_municipal
ingestion_runs ─── 1:N ─── ingestion_checkpoints

Operations:
stripe_webhook_events (idempotency)
reconciliation_log
health_checks
incidents
audit_events
seo_metrics

Growth:
partners ─── 1:N ─── partner_referrals
referrals
leads, report_leads, founding_leads
```
