# Spec: Pipeline Kanban

> Spec executável (SDD) gerada pelo **Reversa Writer** em 2026-04-27
> Confiança: 🟢 CONFIRMADO

## Component
- **ID**: `pipeline-kanban`
- **Path**: `backend/routes/pipeline.py`, `backend/schemas/pipeline.py`, `frontend/app/pipeline/`, `frontend/hooks/usePipeline.ts`

## Purpose

CRUD kanban de oportunidades B2G. 5 stages canonical. Optimistic locking para concurrent edits. Trial cap 5 itens. Read-only mode pós-trial-expired (incentivo conversão).

## Stages

```
descoberta → analise → preparando → enviada → resultado
```

Frontend permite drag livre (não enforce sequence). Backend valida `stage ∈ VALID_PIPELINE_STAGES`.

## Invariants

1. **Optimistic locking** — UPDATE com WHERE version=$N + SET version=$N+1; 0 rows affected → 409 Conflict
2. **Idempotent insert** — `upsert(on_conflict='user_id,pncp_id', ignore_duplicates=true)` evita 409 noise
3. **Trial limit 5** — `_check_pipeline_limit` count antes de INSERT
4. **Defense-in-depth** — admin client + `.eq("user_id", user_id)` em TODAS queries (ISSUE-021 fix)
5. **Fail-open reads** — `CircuitBreakerOpenError` → 200 com items=[] + header `X-Cache-Status: stale-due-to-cb-open`
6. **Skip malformed rows** — ISSUE-038: warn log + continuar em vez de 500

## Functional Requirements

- **FR-1**: `POST /v1/pipeline` create item (require_auth + write_access + limit check)
- **FR-2**: `GET /v1/pipeline?stage&limit&offset` list user items (require_auth + read_access fail-open)
- **FR-3**: `PATCH /v1/pipeline/{item_id}` update stage and/or notes; optional version param para optimistic locking
- **FR-4**: `DELETE /v1/pipeline/{item_id}` remove item
- **FR-5**: `GET /v1/pipeline/alerts` items com data_encerramento < now+7d AND stage NOT IN ('enviada','resultado')
- **FR-6**: Frontend kanban drag-drop @dnd-kit code-split (lazy)
- **FR-7**: Trial expired view-only mode (`<ReadOnlyKanban>` com DndContext sem sensors)
- **FR-8**: Mobile fallback `<PipelineMobileTabs>` (sem drag, tabs stage-by-stage)
- **FR-9**: Tour Shepherd.js auto-start primeira visita (`PIPELINE_TOUR_STORAGE_KEY`)
- **FR-10**: CTA upsell pós-add-to-pipeline (`<TrialUpsellCTA variant="post-pipeline">`)

## Non-Functional Requirements

- **NFR-1**: List p95 <300ms (eager load all user items)
- **NFR-2**: Write p95 <500ms
- **NFR-3**: Mobile-friendly (responsive ≤768px)
- **NFR-4**: Bundle size — @dnd-kit code-split → reduces initial 80KB
- **NFR-5**: WCAG AA (keyboard navigation, ARIA labels)

## Constraints

- **CON-1**: Trial cap 5 (`TRIAL_PAYWALL_MAX_PIPELINE`)
- **CON-2**: Master/admin bypass capability + limit
- **CON-3**: Stage CHECK constraint em DB (não permite valor fora de set)
- **CON-4**: Stripe handles ALL subscription state — não rebaixar trial→pago client-side

## Acceptance Criteria

- AC-1: `POST` sucesso retorna 201 com `PipelineItemResponse` incluindo `version=1`
- AC-2: `POST` duplicate (mesmo user_id+pncp_id) retorna 200 com row existente (idempotente)
- AC-3: `PATCH` com `version=N` correto retorna 200 e `version=N+1`
- AC-4: `PATCH` com `version=N` stale retorna 409 com mensagem clara
- AC-5: `PATCH` em item não-existente retorna 404
- AC-6: `GET` com `stage=invalid` retorna 422
- AC-7: `GET` durante CB open retorna 200 vazio com header X-Cache-Status
- AC-8: Trial 6º item via POST retorna 403 com `error_code=PIPELINE_LIMIT_EXCEEDED`
- AC-9: Trial expired GET retorna items mas POST/PATCH/DELETE retornam 403
- AC-10: Drag-drop frontend dispatcha PATCH com optimistic update local
- AC-11: Tour auto-start na primeira visita (storage key check)
- AC-12: Mobile (≤768px) renderiza `PipelineMobileTabs` em vez de kanban

## Errors

| Code | HTTP | Trigger |
|------|------|---------|
| `pipeline_not_available` | 403 | caps.allow_pipeline=false |
| `trial_expired` | 403 | trial expirou em write |
| `PIPELINE_LIMIT_EXCEEDED` | 403 | trial 5 itens hit |
| `version_conflict` | 409 | optimistic lock fail |
| `item_not_found` | 404 | wrong item_id ou cross-user |
| `stage_invalid` | 422 | stage fora VALID_PIPELINE_STAGES |
| `payload_empty` | 422 | PATCH sem campos |

## Code traceability

- `backend/routes/pipeline.py` — 5 endpoints + 3 helpers
- `backend/routes/pipeline.py:_check_pipeline_write_access` — gate
- `backend/routes/pipeline.py:_check_pipeline_limit` — trial cap
- `backend/routes/pipeline.py:_check_pipeline_read_access` — fail-open
- `backend/schemas/pipeline.py` — DTOs + VALID_PIPELINE_STAGES
- `frontend/app/pipeline/page.tsx` — page + tour + modals
- `frontend/app/pipeline/PipelineKanban.tsx` — DndContext + 5 columns (lazy)
- `frontend/app/pipeline/PipelineColumn.tsx` — useDroppable
- `frontend/app/pipeline/PipelineCard.tsx` — useDraggable + deadline border
- `frontend/app/pipeline/PipelineMobileTabs.tsx` — mobile fallback
- `frontend/hooks/usePipeline.ts` — CRUD + optimistic update
- Migrations: `025_create_pipeline_items.sql`, `20260227120002_concurrency_pipeline_version.sql`, `20260321130000_debt_db004_pipeline_search_id_comment.sql`

## Dependencies

- `@dnd-kit/core`, `@dnd-kit/sortable` (frontend, code-split)
- Shepherd.js (tour)
- Supabase admin client + RLS bypass via service-role
- `auth.require_auth`, `quota.require_active_plan`, `authorization.has_master_access`
