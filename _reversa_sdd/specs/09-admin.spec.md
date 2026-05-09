# Spec: Admin

> Spec executável (SDD) gerada pelo **Reversa Writer** em 2026-05-08
> Confiança: 🟢 CONFIRMADO

## Component
- **ID**: `admin`
- **Path**: `backend/admin.py` (1132 LOC), `backend/routes/admin_trace.py`, `backend/routes/admin_cron.py`, `backend/routes/admin_llm_cost.py`, `backend/routes/slo.py`, `backend/routes/seo_admin.py`, `backend/routes/feature_flags.py`, `frontend/app/admin/`

## Purpose

Console de administração com 17+ endpoints para gestão de usuários, cache, reconciliação Stripe-DB, SLA support, métricas de trial, feature flags runtime e observabilidade. Acesso exclusivo a `is_admin=True` ou `is_master=True` (RBAC boolean, não granular — LGPD flag para futuro RBAC granular).

## RBAC

### `require_admin` Dependency

```python
async def require_admin(user: dict = Depends(require_auth)) -> dict:
    user_id = user["id"]
    # 1. check env ADMIN_USER_IDS whitelist (UUID validated)
    if user_id in get_admin_ids():
        return user
    # 2. fallback: check DB profiles.is_admin OR profiles.is_master
    if _is_admin_from_supabase(user_id):
        return user
    raise HTTPException(403, "admin_required")
```

**Defense-in-depth:**
- Tier 1: `ADMIN_USER_IDS` env var (UUID v4 validated — commit 7cf341ed)
- Tier 2: DB `profiles.is_admin` OR `profiles.is_master` flag

**Admin bypass:** `is_admin=True` bypassa quota+trial+pipeline_limit.

## Endpoints Principais (admin.py — 17)

### User Management

| Método | Path | Descrição |
|--------|------|-----------|
| `GET` | `/v1/admin/users` | listar users (search, page, filters) — `_sanitize_search_input` Issue #205 |
| `POST` | `/v1/admin/users` | criar user (email+plan+trial_expires_at) |
| `DELETE` | `/v1/admin/users/{user_id}` | deletar user (auth + DB) |
| `PUT` | `/v1/admin/users/{user_id}` | atualizar user (plan_type, trial_expires_at, is_admin) |
| `POST` | `/v1/admin/users/{user_id}/reset-password` | reset password via Supabase Admin API |
| `POST` | `/v1/admin/users/{user_id}/assign-plan` | atribuir plano + Stripe subscription |
| `PUT` | `/v1/admin/users/{user_id}/credits` | atualizar créditos/quota manual |

### Cache Management

| Método | Path | Descrição |
|--------|------|-----------|
| `GET` | `/v1/admin/cache/metrics` | métricas L1+L2 (hit rate, entries, size) |
| `GET` | `/v1/admin/cache/{params_hash}` | inspecionar entry específica |
| `DELETE` | `/v1/admin/cache/{params_hash}` | invalidar entry específica |
| `DELETE` | `/v1/admin/cache` | invalidar todo cache |

### Reconciliation & Ops

| Método | Path | Descrição |
|--------|------|-----------|
| `GET` | `/v1/admin/reconciliation/history` | histórico de reconciliações Stripe↔DB |
| `POST` | `/v1/admin/reconciliation/trigger` | trigger manual reconciliação |
| `GET` | `/v1/admin/support-sla` | métricas SLA suporte (avg response time, open tickets) |
| `GET` | `/v1/admin/trial-metrics` | métricas trial (conversões, expirations, quota usage) |
| `GET` | `/v1/admin/at-risk-trials` | trials em risco (baixo engajamento, próximos à expiração) |
| `GET` | `/v1/admin/filter-stats` | estatísticas de classificação LLM por setor |

## Endpoints Auxiliares (routers separados)

### admin_trace.py
- `GET /v1/admin/traces` — OTel trace search por user_id/search_id
- `GET /v1/admin/traces/{trace_id}` — trace detail com spans

### admin_cron.py
- `GET /v1/admin/cron-status` — pg_cron job health via `get_cron_health()` RPC

### admin_llm_cost.py
- `GET /v1/admin/llm-cost` — custo acumulado OpenAI tokens (por model, por período)

### slo.py
- `GET /v1/slo/metrics` — SLO dashboard (p50/p95/p99 latency, error rate, uptime)
- `GET /v1/slo/incidents` — histórico de incidentes

### seo_admin.py
- `GET /v1/admin/seo/sitemap-stats` — URLs por sitemap, last_generated
- `POST /v1/admin/seo/reindex` — trigger re-geração de snapshots SEO

### feature_flags.py (runtime toggle)
- `GET /v1/admin/feature-flags` — listar flags e valores atuais
- `PATCH /v1/admin/feature-flags/{flag}` — toggle flag (persiste em Redis ou DB)

## Feature Flags

Flags configuráveis em runtime (sem redeploy):

| Flag | Default | Descrição |
|------|---------|-----------|
| `DATALAKE_QUERY_ENABLED` | `true` | DataLake como source primária |
| `LLM_ZERO_MATCH_ENABLED` | `true` | classificação zero-match via LLM |
| `LLM_ARBITER_ENABLED` | `true` | arbiter completo |
| `VIABILITY_ASSESSMENT_ENABLED` | `true` | scoring 4-fatores |
| `SYNONYM_MATCHING_ENABLED` | `true` | matching com sinônimos |
| `FEEDBACK_ENABLED` | `true` | feedback loop ativo |
| `SEARCH_ASYNC_ENABLED` | `true` | POST /buscar async (202) vs sync |
| `LLM_FALLBACK_PENDING_ENABLED` | `true` | gray zone em LLM failure |

## List Users — Sanitization (Issue #205)

```python
def _sanitize_search_input(search: str) -> str:
    """Remove SQL injection chars, truncate to 100 chars."""
    # strip SQL special chars: ;, --, ', ", \
    sanitized = re.sub(r"[;'\"\\\-\-]", "", search)
    return sanitized[:100].strip()
```

**User validation:** `_validate_user_id_param` enforce UUID v4 format antes de qualquer DB query. `_validate_plan_id_param` valida contra plan catalog.

## Trial Metrics (`GET /v1/admin/trial-metrics`)

```
SELECT profiles WHERE plan_type='free_trial'
  → total_trials
  → trials_expiring_3d (trial_expires_at <= now+3d)
  → trials_expiring_7d
  → total_converted (plan_type != 'free_trial' AND had_trial)
  → conversion_rate = total_converted / (total_converted + total_expired)
  → avg_searches_per_trial

SELECT search_sessions (trial users only)
  → quota_usage_by_tier (0-25%, 25-50%, 50-75%, 75-100%)
```

## At-Risk Trials (`GET /v1/admin/at-risk-trials`)

```
criteria:
  - trial_expires_at < now + 5d
  AND (
    total_searches = 0 (never activated)
    OR last_search_at < now - 3d (dormant)
    OR search_success_rate < 0.5 (high failure rate)
  )
ORDER BY trial_expires_at ASC LIMIT 50
```

## Frontend Admin Pages

| Route | Descrição |
|-------|-----------|
| `/admin` | Dashboard overview |
| `/admin/users` | User management table + search |
| `/admin/cache` | Cache metrics + invalidation |
| `/admin/metrics` | SLO + observability |
| `/admin/feature-flags` | Runtime flag toggles |
| `/admin/emails` | Trial email management |
| `/admin/partners` | Partner program management |
| `/admin/seo` | SEO admin tools |

## Invariants

1. **RBAC double-check** — env whitelist + DB flag (defense-in-depth)
2. **UUID v4 validation** — todos user_id params validados antes de DB query (commit 7cf341ed)
3. **Search input sanitization** — `_sanitize_search_input` em `/admin/users?search=` (Issue #205)
4. **Admin bypass** — admin/master ignoram quota + trial_expires_at + pipeline_limit
5. **Feature flags persist** — Redis (ephemeral) ou DB (durável) dependendo do flag

## Functional Requirements

- **FR-1**: `GET /admin/users` com paginação + search sanitizado + filters (plan, trial_status)
- **FR-2**: `POST /admin/users` cria user via Supabase Admin API + define plan
- **FR-3**: `DELETE /admin/users/{id}` deleta auth + profiles (cascade)
- **FR-4**: `PUT /admin/users/{id}/assign-plan` cria/atualiza Stripe subscription
- **FR-5**: `GET /admin/cache/metrics` retorna L1 entries + hit_rate + L2 size
- **FR-6**: `DELETE /admin/cache` invalida L1 InMemoryCache + L2 Redis
- **FR-7**: `POST /admin/reconciliation/trigger` chama `reconcile_stripe_db()` síncrono
- **FR-8**: `GET /admin/cron-status` chama RPC `get_cron_health()` retorna JSON
- **FR-9**: `PATCH /admin/feature-flags/{flag}` persiste toggle, retorna novo estado
- **FR-10**: `GET /admin/at-risk-trials` retorna ≤50 users ordenados por urgência

## Non-Functional Requirements

- **NFR-1**: Todos endpoints protegidos por `require_admin` (401/403 em não-admin)
- **NFR-2**: List users paginação padrão 25 por página (max 100)
- **NFR-3**: Feature flag toggle <100ms (Redis SET)
- **NFR-4**: Reconciliation pode demorar >10s — não usar timeout padrão da rota (exempto)

## Constraints

- **CON-1**: RBAC granular NÃO implementado (Gap-1 review-report) — apenas boolean admin/master
- **CON-2**: Org RBAC (`organizations` + `organization_members`) sem enforcement em admin endpoints
- **CON-3**: Admin pages são CSR (Client Side Render) no frontend — sem SSR/ISR
- **CON-4**: `route_timeout_middleware` exempta admin endpoints (podem demorar mais)

## Acceptance Criteria

- AC-1: User sem `is_admin=True` recebe 403 em qualquer endpoint `/admin/*`
- AC-2: `GET /admin/users?search='; DROP TABLE--` retorna lista vazia (sanitized) sem 500
- AC-3: `DELETE /admin/cache` → L1 entries = 0 pós-call
- AC-4: `PATCH /admin/feature-flags/LLM_ARBITER_ENABLED` toggle → novo valor retornado + persistido
- AC-5: `GET /admin/at-risk-trials` retorna apenas trials com `expires_at < now+5d`
- AC-6: `GET /admin/cron-status` retorna shape `{status, count, jobs[...]}` com pg_cron data

## Errors

| Code | HTTP | Trigger |
|------|------|---------|
| `admin_required` | 403 | user sem role admin/master |
| `user_not_found` | 404 | user_id não existe |
| `invalid_user_id` | 422 | UUID v4 format inválido |
| `invalid_plan_id` | 422 | plan_id não existe no catálogo |
| `stripe_error` | 400/503 | Stripe API error em assign-plan |
| `flag_not_found` | 404 | feature flag name não reconhecido |

## Code Traceability

- `backend/admin.py:43` — `router = APIRouter(prefix="/admin")`
- `backend/admin.py:221` — `require_admin` dependency
- `backend/admin.py:259` — `list_users` (GET /admin/users)
- `backend/admin.py:323` — `create_user`
- `backend/admin.py:375` — `delete_user`
- `backend/admin.py:409` — `update_user`
- `backend/admin.py:487` — `assign_plan`
- `backend/admin.py:680` — `get_cache_metrics_endpoint`
- `backend/admin.py:801` — `get_reconciliation_history`
- `backend/admin.py:942` — `get_trial_metrics`
- `backend/admin.py:1049` — `get_at_risk_trials`
- `backend/routes/feature_flags.py` — flag CRUD
- `backend/routes/admin_cron.py` — cron-status
- `backend/routes/slo.py` — SLO metrics + incidents
- `backend/authorization.py:get_admin_ids` — UUID v4 validated whitelist

## Dependencies

- Supabase Admin API (user CRUD — service_role)
- Supabase (`profiles`, `user_subscriptions`, `search_sessions`, `conversations`, `classification_feedback`)
- Stripe SDK (assign-plan, reconciliation)
- Redis (cache invalidation, feature flags ephemeral)
- `cache/` package (L1 InMemoryCache + L2 Redis)
- `services/billing.py` (reconciliation)
- pg_cron via `get_cron_health()` RPC
