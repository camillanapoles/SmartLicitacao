# Flowchart — Módulo `pipeline-kanban`

> Gerado pelo **Reversa Archaeologist** em 2026-04-27 · Confiança 🟢 CONFIRMADO

## POST /pipeline (create)

```mermaid
flowchart TD
    A[POST /pipeline + JWT] --> B[require_auth]
    B --> C[_check_pipeline_write_access]
    C --> C1{is_master?}
    C1 -->|sim| F
    C1 -->|não| C2[require_active_plan]
    C2 -->|trial expired| X1[403 trial_expired]
    C2 -->|ok| C3{caps.allow_pipeline?}
    C3 -->|não| X2[403 pipeline_not_available]
    C3 -->|sim| F[_check_pipeline_limit]
    F --> F1{plan_id == free_trial?}
    F1 -->|não| INS
    F1 -->|sim| F2[count items WHERE user_id]
    F2 --> F3{count >= 5?}
    F3 -->|sim| X3[403 PIPELINE_LIMIT_EXCEEDED]
    F3 -->|não| INS[upsert ignore_duplicates]
    INS --> INS1{result.data?}
    INS1 -->|sim| OK[201 PipelineItemResponse]
    INS1 -->|não, conflict| FETCH[SELECT existing]
    FETCH --> OK2[200 PipelineItemResponse]
```

## PATCH /pipeline/{id} — optimistic locking

```mermaid
flowchart TD
    A[PATCH id + body version=N] --> B[require_auth + write_access]
    B --> C{payload válido?}
    C -->|stage inválido| X1[422]
    C -->|payload vazio| X2[422]
    C -->|ok| D{version sent?}
    D -->|não| E[UPDATE WHERE id AND user_id]
    D -->|sim| F[UPDATE WHERE id AND user_id AND version=N SET version=N+1]
    F --> G{rows affected > 0?}
    G -->|sim| OK[200 updated]
    G -->|não| H[SELECT id, version WHERE id, user_id]
    H -->|exists| X3[409 version conflict]
    H -->|not exists| X4[404]
    E --> G
```

## GET /pipeline (list with fail-open)

```mermaid
flowchart TD
    A[GET /pipeline?stage&limit&offset] --> B[require_auth]
    B --> C[_check_pipeline_read_access try]
    C -->|HTTPException| X[propaga 403]
    C -->|outra exc| W[warn fail-open]
    C -->|ok| D{stage in VALID?}
    D -->|inválido| X2[422]
    D -->|ok ou null| Q[SELECT * count=exact ORDER updated_at DESC RANGE]
    Q -->|CircuitBreakerOpenError| Y[200 items=empty + header X-Cache-Status: stale-due-to-cb-open]
    Q -->|ok| P[parse rows skip malformed]
    P --> OK[200 PipelineListResponse]
    Q -->|other Exception| X3[500]
    W --> Q
```

## GET /pipeline/alerts

```mermaid
flowchart TD
    A[GET /pipeline/alerts] --> B[require_auth + read_access fail-open]
    B --> C[deadline = now + 7d]
    C --> D[SELECT * WHERE user_id AND stage NOT IN enviada,resultado AND data_encerramento NOT NULL AND data_encerramento ≤ deadline ORDER asc]
    D -->|exception| E[warn + return 200 items=empty]
    D -->|ok| OK[200 PipelineAlertsResponse]
```

## Frontend drag-drop (PipelineKanban.tsx)

```mermaid
sequenceDiagram
    participant U as User
    participant K as PipelineKanban (DndContext)
    participant H as usePipeline hook
    participant API as /api/pipeline (proxy)
    participant BE as Backend

    U->>K: drag card from coluna A para B
    K->>K: onDragEnd(event)
    K->>H: updateItem(id, {stage: B, version: N})
    H->>H: optimistic update local items
    H->>API: PATCH /pipeline/{id}
    API->>BE: PATCH com Authorization header
    alt success (200)
        BE-->>H: PipelineItemResponse com version=N+1
        H->>K: replace item local
    else version conflict (409)
        BE-->>H: 409
        H->>H: revert optimistic + refetch
        H->>U: toast "atualizado por outra operação"
    else 404
        H->>H: remove item local
    end
```

## Estados

| Estado | Origem | Comportamento |
|--------|--------|---------------|
| Trial active + caps.allow_pipeline | profiles + plan_billing_periods | Full RW |
| Trial expired | trial_expires_at < now | Read-only (STORY-265 AC15), badge âmbar |
| Pago | subscription_status=active | Full RW, sem limite |
| CB open | supabase circuit breaker | Read 200 com items=[], write 5xx |
| Master/admin | profiles.is_master/is_admin | Bypass de quota+limit |
