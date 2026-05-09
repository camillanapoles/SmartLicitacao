# Spec: Onboarding & Analytics

> Spec executável (SDD) gerada pelo **Reversa Writer** em 2026-05-08
> Confiança: 🟢 CONFIRMADO

## Component
- **ID**: `onboarding-analytics`
- **Path**: `backend/routes/onboarding.py`, `backend/routes/analytics.py`, `backend/utils/cnae_mapping.py`, `frontend/app/onboarding/`, `frontend/app/dashboard/`, `frontend/components/tour/`

## Purpose

Dois sub-módulos:
1. **Onboarding** — wizard 3-step (CNAE → UFs → confirmação) → first-analysis auto-dispatch (GTM-004, TTV target <5min). Tour Shepherd.js com telemetria.
2. **Analytics** — 6 endpoints de dashboard pessoal (aggregações de `search_sessions`) + Shepherd.js tour telemetria.

## Sub-Módulo 1: Onboarding Wizard

### State Machine (3-step frontend)

```
[*] → Step1: load /onboarding
Step1 → Step2: react-hook-form + Zod onboardingStep1Schema OK
Step2 → Step3: Zod step2Schema OK + UFs ≥ 1
Step3 → FirstAnalysis: confirmação (POST /v1/first-analysis)
FirstAnalysis → Buscar: redirect /buscar?search_id={id}
Step1 ↔ Step2 ↔ Step3: back navigation permitido
```

**Schemas Zod (frontend):**
- `onboardingStep1Schema` — CNAE code + empresa nome + porte
- `step2Schema` — UFs array (≥1 required)
- Step3 — review screen (sem validação adicional)

### First-Analysis Flow (GTM-004)

```
User: Confirmar (Step3)
  → Frontend: trackEvent('onboarding_completed', {...})
  → POST /v1/first-analysis (FirstAnalysisRequest)
      → require_auth + require_active_plan
      → map_cnae_to_setor(cnae) → setor_id | "diversos"
      → search_id = uuid4()
      → build BuscaRequest automático (setor, UFs, date_range default 10d)
      → asyncio.create_task(SearchPipeline.run(buscaRequest, search_id))
      → 202 FirstAnalysisResponse(search_id=search_id)
  → Frontend: router.push('/buscar?search_id={search_id}')
  → GET /buscar-progress/{search_id} (SSE stream)
```

### CNAE → Setor Mapping (`utils/cnae_mapping.py`)

```python
# Hardcoded mapping (GAP-8: cobertura parcial)
CNAE_SETOR_MAP = {
  "4711302": "alimentos",
  "8299799": "servicos_prediais",
  ...
}

def map_cnae_to_setor(cnae: str) -> str:
    """Returns setor_id or 'diversos' if CNAE not mapped."""
    return CNAE_SETOR_MAP.get(cnae, "diversos")
```

**Gap documentado (Gap-8):** mapping hardcoded sem cobertura completa dos CNAEs — fallback para "diversos". Migration futura para tabela DB (backlog).

### Tour Shepherd.js (Telemetria)

```
POST /v1/onboarding/tour-event
  → body: {tour_id, event: "complete"|"skip", steps_seen: int[]}
  → 204 (fire-and-forget)
  → DB INSERT tour_events(user_id, tour_id, event, steps_seen, created_at)
```

### Backend Endpoints (Onboarding)

| Método | Path | Auth | Descrição |
|--------|------|------|-----------|
| `POST` | `/v1/first-analysis` | user + active_plan | dispatch first search auto |
| `POST` | `/v1/onboarding/tour-event` | user | telemetria tour Shepherd.js |

## Sub-Módulo 2: Analytics Dashboard

### Endpoints (6)

| Método | Path | Auth | Descrição |
|--------|------|------|-----------|
| `GET` | `/v1/analytics/summary` | user | métricas agregadas globais |
| `GET` | `/v1/analytics/searches-over-time` | user | histórico temporal de buscas |
| `GET` | `/v1/analytics/top-dimensions` | user | top 5 UFs e setores por uso |
| `GET` | `/v1/analytics/trial-value` | user | valor trial (para upgrade CTA) |
| `GET` | `/v1/analytics/new-opportunities` | user | novas oportunidades desde última busca |
| `POST` | `/v1/analytics/track-cta` | public | rastrear CTA cliques em SEO pages |

### Summary Aggregation

```sql
SELECT
  COUNT(*) AS total_searches,
  COUNT(*) FILTER (WHERE excel_downloaded) AS total_downloads,
  SUM(results_count) AS total_opportunities,
  SUM(total_value) AS total_value,
  COUNT(*) FILTER (WHERE state='COMPLETED') AS successful_searches
FROM search_sessions
WHERE user_id = :me

-- Derived:
-- hours_saved = total_searches * 2.5  (magic constant, Gap-6)
-- avg_results = total_opportunities / total_searches
-- success_rate = successful_searches / total_searches
-- member_since = profiles.created_at
```

### Top Dimensions (UFs + Setores)

```sql
-- Top UFs
SELECT uf, COUNT(*) as count, SUM(total_value) as value
FROM search_sessions, unnest(ufs) AS uf
WHERE user_id = :me
GROUP BY uf ORDER BY count DESC LIMIT 5

-- Top Setores
SELECT setor_id, COUNT(*) as count, SUM(total_value) as value
FROM search_sessions
WHERE user_id = :me
GROUP BY setor_id ORDER BY count DESC LIMIT 5
```

### New Opportunities (DEBT-127)

```
GET /v1/analytics/new-opportunities
  → get last successful search_session (ORDER created_at DESC LIMIT 1)
      → nenhuma: {has_previous_search: false, count: 0}
      → exists:
          state == COMPLETED?
            → Não (UX-431 AC2): {label: "retry/pending", ...}
            → Sim: re-query DataLake desde last_search_at
                   → count novas bids
                   → {has_previous_search: true, count: N, last_search_at: ...}
```

### CTA Tracking (Público)

```
POST /v1/analytics/track-cta
  → body: {cta: str, source: str}
  → 204 (fire-and-forget)
  → DB INSERT cta_tracking(cta, source, user_agent, ip_hash, ts)
```

### Response Schemas

```python
# SummaryResponse
{
  "total_searches": int,
  "total_downloads": int,
  "total_opportunities": int,
  "total_value": float,
  "hours_saved": float,  # total_searches * 2.5
  "avg_results": float,
  "success_rate": float,
  "member_since": datetime
}

# TopDimensionsResponse
{
  "top_ufs": [{"uf": str, "count": int, "value": float}],
  "top_sectors": [{"setor_id": str, "name": str, "count": int, "value": float}]
}

# NewOpportunitiesResponse
{
  "has_previous_search": bool,
  "count": int,
  "last_search_at": datetime | None,
  "days_since": int | None
}
```

## Functional Requirements

**Onboarding:**
- **FR-1**: Wizard 3-step com validação Zod em cada transição; back navigation preserva estado
- **FR-2**: `POST /v1/first-analysis` mapeia CNAE → setor_id, constrói BuscaRequest automático, retorna 202 + search_id em <2s
- **FR-3**: `map_cnae_to_setor` retorna "diversos" para CNAEs não mapeados (sem exceção)
- **FR-4**: `POST /v1/onboarding/tour-event` persiste telemetria fire-and-forget (nunca bloqueia UX)

**Analytics:**
- **FR-5**: `GET /summary` agrega todas search_sessions do user com 5 métricas derivadas
- **FR-6**: `GET /top-dimensions` retorna top 5 UFs + top 5 setores por frequência
- **FR-7**: `GET /new-opportunities` re-query DataLake desde última busca COMPLETED
- **FR-8**: `POST /track-cta` público (sem auth), persiste IP anonimizado (hash)
- **FR-9**: `GET /searches-over-time` retorna série temporal (diária/semanal) de buscas
- **FR-10**: `GET /trial-value` calcula valor estimado monetizado no trial (para upgrade CTA)

## Non-Functional Requirements

- **NFR-1**: `POST /v1/first-analysis` retorna 202 em <2s (pipeline dispatch async)
- **NFR-2**: `GET /summary` <200ms (index em `search_sessions.user_id, created_at`)
- **NFR-3**: Tour event: fire-and-forget (timeout 1s, ignora falha)
- **NFR-4**: TTV target (GTM-004): onboarding completado → primeiro resultado ≤5min

## Constraints

- **CON-1**: First-analysis USA o mesmo `SearchPipeline.run` do endpoint `/buscar` (sem duplicação)
- **CON-2**: `hours_saved = total_searches * 2.5` é constante magic (Gap-6) — não calculada empiricamente
- **CON-3**: CNAE mapping em hardcoded dict (GAP-8) — fallback "diversos" evita erro 500
- **CON-4**: CTA tracking usa IP hash (não IP raw) — LGPD compliant

## Acceptance Criteria

- AC-1: Wizard Step1→Step2→Step3 preserva form state no back navigation
- AC-2: `POST /v1/first-analysis` com CNAE mapeado → search_id retornado em <2s
- AC-3: CNAE sem mapeamento → setor="diversos" (sem 4xx)
- AC-4: Tour skip → `tour_events` INSERT com `event=skip, steps_seen=[...]`
- AC-5: `GET /summary` retorna `hours_saved = total_searches * 2.5`
- AC-6: `GET /new-opportunities` sem busca prévia → `{has_previous_search: false}`
- AC-7: SSE `/buscar-progress/{id}` disponível imediatamente após `POST /v1/first-analysis`

## Errors

| Code | HTTP | Trigger |
|------|------|---------|
| `plan_not_active` | 403 | trial expirado em `/v1/first-analysis` |
| `invalid_cnae` | 422 | CNAE formato inválido (Pydantic) |
| `search_dispatch_failed` | 500 | SearchPipeline não iniciou |
| `no_sessions_found` | 200 | analytics sem search_sessions (não erro, empty state) |

## Code Traceability

- `backend/routes/onboarding.py` — `POST /v1/first-analysis`, `POST /v1/onboarding/tour-event`
- `backend/utils/cnae_mapping.py` — `map_cnae_to_setor`, `CNAE_SETOR_MAP`
- `backend/routes/analytics.py` — 5 GET endpoints + POST track-cta
- `backend/schemas/` (onboarding, analytics schemas)
- `frontend/app/onboarding/page.tsx` — wizard 3-step UI
- `frontend/components/tour/` — Shepherd.js wrapper + step utilities
- `frontend/app/dashboard/page.tsx` — analytics dashboard consumer

## Dependencies

- `SearchPipeline` (`backend/search_pipeline.py`) — first-analysis dispatch
- Supabase (`search_sessions`, `tour_events`, `cta_tracking`, `profiles`)
- Auth: `require_auth`, `require_active_plan`
- `backend/sectors_data.yaml` (setor names para top_sectors response)
- Frontend: `react-hook-form`, `zod`, Shepherd.js, Mixpanel (`trackEvent`)
