# Flowchart — Módulo `search`

> Gerado pelo **Reversa Archaeologist** em 2026-04-27

## 1. Pipeline de 7 estágios

```mermaid
flowchart TD
  A[POST /buscar] --> B[stage_validate]
  B -->|HTTPException 403/429/503| Z1[FAILED / RATE_LIMITED]
  B --> C[stage_prepare]
  C --> D[stage_execute]
  D -->|timeout| Z2[TIMED_OUT]
  D --> E[stage_filter]
  E --> TB{elapsed > 90s ?}
  TB -->|sim| TBSimp[is_simplified=True · skip LLM]
  TB -->|não| F
  TBSimp --> F[stage_enrich · viability]
  F --> G[stage_post_filter_llm · zero-match]
  G --> H[stage_generate · LLM resumo + Excel]
  H -->|queue mode| Hjob[ARQ job dispatched · llm_status=processing]
  H --> I[stage_persist · DB write]
  Hjob --> I
  I --> J[COMPLETED]
  J --> K[BuscaResponse]
```

## 2. Máquina de estados (`SearchState`)

```mermaid
stateDiagram-v2
  [*] --> CREATED
  CREATED --> VALIDATING
  CREATED --> FAILED
  VALIDATING --> FETCHING
  VALIDATING --> FAILED
  VALIDATING --> RATE_LIMITED
  FETCHING --> FILTERING
  FETCHING --> FAILED
  FETCHING --> TIMED_OUT
  FILTERING --> ENRICHING
  FILTERING --> FAILED
  ENRICHING --> GENERATING
  ENRICHING --> FAILED
  GENERATING --> PERSISTING
  GENERATING --> FAILED
  PERSISTING --> COMPLETED
  PERSISTING --> FAILED
  COMPLETED --> [*]
  FAILED --> [*]
  RATE_LIMITED --> [*]
  TIMED_OUT --> [*]
```

## 3. Cache SWR (per-request)

```mermaid
flowchart TD
  Q[Request chega] --> L1{L1 InMemory hit?}
  L1 -->|sim| Age1{idade}
  L1 -->|não| L2{L2 Supabase hit?}
  Age1 -->|0-6h fresh| Serve1[Serve direto · cache_status=fresh]
  Age1 -->|6-24h stale| Serve2[Serve + dispara revalidação · cache_status=stale]
  Age1 -->|>24h expired| L2
  L2 -->|sim| Age2{idade}
  L2 -->|não| Live[Live fetch · multi-source]
  Age2 -->|fresh| Serve3[Serve + popula L1]
  Age2 -->|stale| Serve4[Serve + revalida BG]
  Age2 -->|expired| Live
  Live --> Pop[Popula L1 + L2]
  Pop --> Resp[Response]
  Serve1 --> Resp
  Serve2 --> Resp
  Serve3 --> Resp
  Serve4 --> Resp
```

## 4. Dedup Engine (5 layers)

```mermaid
flowchart LR
  In[List - UnifiedProcurement] --> L1[Layer 1: source_id exact]
  L1 --> L2[Layer 2: dedup_key exact + priority winner]
  L2 --> Fuz{DEDUP_FUZZY_ENABLED?}
  Fuz -->|sim| L3[Layer 3: Fuzzy Jaccard]
  Fuz -->|não| Out
  L3 --> L4[Layer 4: Process-number CNPJ-seq/year]
  L4 --> L5[Layer 5: Title-prefix cross-org]
  L5 --> Out[Deduped + merge-enriched]
```

## 5. Time Budget Waterfall

```
Railway proxy     [================== 120s ==================]
Gunicorn worker   [============== 110s ===============]
Pipeline budget   [============ 100s =============]
  Consolidation   [========== 90s ==========]
    PerSource     [======= 70s =======]
      PerUF       [=== 25s ===]
        httpx     [10c+15r]
```

Invariante: `pipeline(100) > consolidation(90) > per_source(70) > per_uf(25) > (per_modality 20 + httpx 15)` — assertado em `tests/test_timeout_invariants.py`.
