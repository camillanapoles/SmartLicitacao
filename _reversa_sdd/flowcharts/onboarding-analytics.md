# Flowchart — Módulo `onboarding+analytics`

> Gerado pelo **Reversa Archaeologist** em 2026-04-27 · Confiança 🟢 CONFIRMADO

## Onboarding wizard (3-step)

```mermaid
stateDiagram-v2
    [*] --> Step1: load /onboarding
    Step1 --> Step2: react-hook-form + Zod onboardingStep1Schema OK
    Step2 --> Step3: Zod step2Schema OK + UFs ≥1
    Step3 --> FirstAnalysis: confirmação
    FirstAnalysis --> Buscar: search_id retornado
    Step1 --> Step1: edit (back navigation)
    Step2 --> Step1: back
    Step3 --> Step2: back
```

## First analysis flow (GTM-004)

```mermaid
sequenceDiagram
    participant U as User (Step3)
    participant F as Frontend
    participant API as POST /v1/first-analysis
    participant CNAE as utils.cnae_mapping
    participant P as SearchPipeline
    participant SSE as GET /buscar-progress/{id}

    U->>F: Confirmar
    F->>F: trackEvent onboarding_completed
    F->>API: POST FirstAnalysisRequest profile
    API->>API: require_auth + require_active_plan
    API->>CNAE: map_cnae_to_setor cnae
    CNAE-->>API: setor_id ou "diversos"
    API->>API: search_id = uuid4
    API->>API: build BuscaRequest auto
    API->>P: dispatch async SearchPipeline.run
    API-->>F: 202 FirstAnalysisResponse search_id
    F->>F: router.push /buscar?search_id=
    F->>SSE: GET /buscar-progress/{id}
    SSE-->>F: streaming events progress
    P-->>SSE: progress events
```

## Analytics — summary aggregation

```mermaid
flowchart TD
    A[GET /v1/analytics/summary] --> B[require_auth]
    B --> C[SELECT search_sessions WHERE user_id=me]
    C --> D[total_searches = COUNT]
    C --> E[total_downloads = COUNT WHERE excel_downloaded]
    C --> F[total_opportunities = SUM results_count]
    C --> G[total_value = SUM total_value]
    G --> H[hours_saved = total_searches * 2.5]
    C --> I[avg_results = total_opps / total_searches]
    C --> J[success_rate = COUNT state=COMPLETED / total]
    K[SELECT profiles.created_at] --> L[member_since]
    D & E & F & G & H & I & J & L --> R[200 SummaryResponse]
```

## Top dimensions (UFs + sectors)

```mermaid
flowchart TD
    A[GET /v1/analytics/top-dimensions] --> B[require_auth]
    B --> C[SQL unnest ufs]
    C --> D[GROUP BY uf, COUNT, SUM value]
    D --> E[ORDER DESC LIMIT 5]
    E --> F[top_ufs DimensionItem array]
    B --> G[GROUP BY setor_id, COUNT, SUM value]
    G --> H[top_sectors]
    F & H --> R[200 TopDimensionsResponse]
```

## New opportunities (DEBT-127)

```mermaid
flowchart TD
    A[GET /v1/analytics/new-opportunities] --> B[require_auth]
    B --> C[get last successful search_session WHERE user_id=me ORDER created_at DESC LIMIT 1]
    C -->|nenhuma| X1[has_previous_search=false count=0]
    C -->|exists| D[last_search_at, days_since]
    D --> E{state==COMPLETED?}
    E -->|não, UX-431 AC2| L[label = retry/pending]
    E -->|sim| F[re-query DataLake desde last_search_at]
    F --> G[count = novos bids]
    L & G --> R[200 NewOpportunitiesResponse]
```

## Tour event telemetry

```mermaid
sequenceDiagram
    participant T as Shepherd Tour
    participant F as Frontend hook
    participant API as POST /v1/onboarding/tour-event
    participant DB as tour_events table

    T->>F: onComplete or onSkip
    F->>API: POST tour_id, event, steps_seen
    API-->>F: 204 (fire-and-forget)
    API->>DB: INSERT tour_events
```
