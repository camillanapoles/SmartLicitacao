# Flowchart — Módulo `schemas+contracts`

> Gerado pelo **Reversa Archaeologist** em 2026-04-27 · Confiança 🟢 CONFIRMADO

## Validation pipeline (request → handler)

```mermaid
flowchart TD
    A[HTTP request POST /v1/buscar] --> B[FastAPI parse body]
    B --> C[Pydantic v2 BuscaRequest validate]
    C -->|ufs vazio| X1[422 ufs min_length=1]
    C -->|data inválida| X2[422 invalid date]
    C -->|range > 30d| X3[422 date_range_exceeded]
    C -->|future date| X4[422 future_date]
    C -->|valor_minimo > valor_maximo| X5[422 invalid_value_range]
    C -->|termos com SQL/XSS| X6[422 unsafe_search_query]
    C -->|ok| H[handler async def]
    H --> R[Pipeline.run ctx]
    R --> RM[response_model=BuscaResponse]
    RM --> RS[Pydantic serialize JSON]
    RS --> A2[200 OK]
```

## Schema source-of-truth → frontend codegen (STORY-2.1)

```mermaid
flowchart LR
    BE[backend/schemas/*.py Pydantic] -->|response_model=| OA[FastAPI OpenAPI schema]
    OA -->|extract via app.openapi| CI[CI: .github/workflows/api-types-check.yml]
    CI -->|openapi-typescript| GEN[frontend/app/api-types.generated.ts]
    GEN -->|re-export| TY[frontend/app/types.ts BuscaResult, LicitacaoItem, Resumo]
    TY --> COMP[components consume strongly-typed]
    CI -->|drift?| FAIL[block PR until regen]
```

## PNCP shape canary (STORY-4.5)

```mermaid
flowchart TD
    A[ARQ cron pncp_canary every 600s] --> B[probe tamanhoPagina=51]
    B --> B1{HTTP < 400?}
    B1 -->|sim| X1[Sentry FATAL max_page_size_changed - dedup 6h]
    B1 -->|não, expected ≥ 400| C[probe tamanhoPagina=50]
    C --> C1{success?}
    C1 -->|não| F1[increment _consecutive_failures]
    F1 --> F2{_consecutive_failures ≥ PNCP_CANARY_FAIL_THRESHOLD?}
    F2 -->|sim| X2[Sentry canary_3x_failed]
    F2 -->|não| END[ok]
    C1 -->|sim| V[validate response vs pncp_search_response.schema.json]
    V -->|fail| X3[Sentry shape_drift dedup 6h]
    V -->|ok| END
```

## Re-export pattern (DEBT-302)

```mermaid
flowchart TD
    OLD[Legacy import: from schemas import BuscaRequest] --> INIT[schemas/__init__.py]
    INIT --> S1[from schemas.search import *]
    INIT --> S2[from schemas.user import *]
    INIT --> S3[from schemas.pipeline import *]
    INIT --> S4[from schemas.billing import *]
    INIT --> SN[... 12 submodules]
    S1 --> M1[BuscaRequest, BuscaResponse, LicitacaoItem, ResumoLicitacoes]
    S2 --> M2[SignupRequest, UserProfileResponse]
    S3 --> M3[PipelineItemCreate, ...]
    OLD --> RESOLVE[resolve via re-export]
    RESOLVE --> CALL[handler usa BuscaRequest]
```

## Enum hierarchy

```mermaid
flowchart LR
    SC[schemas/common.py] --> E1[StatusLicitacao str]
    SC --> E2[EsferaGovernamental str]
    SC --> E3[ModalidadeContratacao IntEnum 1-12]
    SC --> E4[FeedbackVerdict str RELEVANT/IRRELEVANT/AMBIGUOUS]
    SC --> E5[FeedbackCategory str]
    SC --> E6[ConversationStatus str open/closed/awaiting_user/awaiting_support]
    SC --> E7[ConversationCategory str]
    SC --> E8[PorteEmpresa str MEI/ME/EPP/MEDIA/GRANDE]
    SC --> E9[ExperienciaLicitacoes str NENHUMA/INICIANTE/EXPERIENTE]
    E1 --> USE1[BuscaRequest.status]
    E2 --> USE2[BuscaRequest.esferas]
    E3 --> USE3[BuscaRequest.modalidades]
```
