# BACKLOG — Trust Audit: Copy vs Capacidade (2026-03)

**Origem:** Conselho CTO Advisory Board — Auditoria de Promessas
**Data:** 2026-03-01
**Esforço total:** ~8-10 semanas com 1 dev
**Objetivo:** Alinhar promessas user-facing com capacidade real do sistema

---

## Plano de Execução

```
SEMANA 1-2 (Imediato) ──────────────────────────────────────────────

  ┌─────────────────────┐   ┌─────────────────────┐
  │ STORY-350 (M)       │   │ STORY-352 (S)       │
  │ Fix "+98%" copy     │   │ Fix "24/7" copy     │
  │ [copy + métrica]    │   │ [copy + BANNED]     │
  │ FE: DataSources,    │   │ FE: comparisons,    │
  │     valueProps,      │   │     TrustSignals,   │
  │     comparisons      │   │     valueProps       │
  │ BE: metrics.py       │   │ FE: ajuda/page      │
  └─────────────────────┘   └─────────────────────┘
         │                          │
         ▼                          ▼
  Sem dependências entre si — EXECUTAR EM PARALELO


SEMANA 3-5 (Sprint 1) ──────────────────────────────────────────────

  ┌─────────────────────┐   ┌─────────────────────┐
  │ STORY-351 (L)       │   │ STORY-354 (XL)      │
  │ Instrumentar "87%"  │   │ LLM graceful        │
  │ [observability +    │   │ degradation         │
  │  copy dinâmica]     │   │ [PENDING_REVIEW]    │
  │ BE: filter.py,      │   │ BE: llm_arbiter,    │
  │     metrics,         │   │     schemas,         │
  │     pipeline,        │   │     pipeline,        │
  │     analytics        │   │     job_queue,       │
  │ FE: StatsSection    │   │     progress         │
  └─────────────────────┘   │ FE: SearchResults,  │
         │                   │     useSearch        │
         │                   └─────────────────────┘
         ▼                          │
  PARALELO: Não tocam nos          ▼
  mesmos arquivos. 351 é       354 é a mais complexa.
  BE filter/stats + FE Stats.  BE LLM/pipeline + FE results.
  Zero overlap.                Começar cedo no sprint.


SEMANA 6-7 (Sprint 2) ──────────────────────────────────────────────

  ┌────────────┐  ┌────────────┐  ┌────────────┐
  │ STORY-355  │  │ STORY-356  │  │ STORY-357  │
  │ (M)        │  │ (S)        │  │ (M)        │
  │ ROI honest │  │ Pipeline   │  │ Auth token │
  │ defaults   │  │ backend    │  │ refresh    │
  │            │  │ enforce    │  │            │
  │ FE: roi.ts │  │ BE: routes │  │ FE: proxy  │
  │   pricing  │  │  /pipeline │  │   useSearch│
  │   planos   │  │ FE: modal  │  │   supabase │
  │   vProps   │  │            │  │            │
  └────────────┘  └────────────┘  └────────────┘
       │               │               │
       ▼               ▼               ▼
  TODAS 3 EM PARALELO — zero overlap de arquivos
  355=FE copy, 356=BE pipeline route, 357=FE auth proxy


SEMANA 8-10 (Sprint 3) ─────────────────────────────────────────────

  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐
  │ STORY-353  │  │ STORY-358  │  │ STORY-359  │  │ STORY-360  │
  │ (L)        │  │ (M)        │  │ (S)        │  │ (S)        │
  │ SLA infra  │  │ "1000+/dia"│  │ SSE trans- │  │ Preço      │
  │ suporte    │  │ instrument │  │ parência   │  │ inconsis-  │
  │            │  │            │  │            │  │ tência     │
  │ BE: msgs,  │  │ BE: metrics│  │ FE: Loading│  │ FE: planos │
  │   cron,    │  │   cron,    │  │   Progress │  │ BE: billing│
  │   admin    │  │   analytics│  │   hooks    │  │            │
  │ DB: migr.  │  │ FE: Sidebar│  │            │  │            │
  └────────────┘  └────────────┘  └────────────┘  └────────────┘
       │               │               │               │
       ▼               ▼               ▼               ▼
  TODAS 4 EM PARALELO
  353=BE msgs/admin, 358=BE metrics/FE sidebar,
  359=FE loading, 360=FE planos/BE billing
  Mínimo overlap (353+358 tocam metrics.py — sequenciar)
```

---

## Ordem de Execução Detalhada

### FASE 1 — Imediato (Semana 1-2): Copy Defensiva

| Ordem | Story | Est | Foco | Paralelo? |
|-------|-------|-----|------|-----------|
| 1a | **STORY-350** | M | Remover "+98%", criar métrica de fontes | SIM, com 352 |
| 1b | **STORY-352** | S | Remover "24/7", adicionar BANNED | SIM, com 350 |

**Justificativa:** São fixes de copy puro (risco imediato de credibilidade). Podem ser mergeadas no mesmo dia. Zero risco técnico. Desbloqueiam toda a comunicação externa.

### FASE 2 — Sprint 1 (Semana 3-5): Instrumentação + Resiliência LLM

| Ordem | Story | Est | Foco | Paralelo? |
|-------|-------|-----|------|-----------|
| 2a | **STORY-354** | XL | LLM PENDING_REVIEW, ARQ reclassify, SSE | SIM, com 351 |
| 2b | **STORY-351** | L | Prometheus counters, discard rate endpoint | SIM, com 354 |

**Justificativa:** 354 é a mais complexa e de maior impacto (elimina "oportunidades invisíveis"). Começar cedo. 351 instrumenta filter.py enquanto 354 instrumenta llm_arbiter.py — zero overlap.

### FASE 3 — Sprint 2 (Semana 6-7): Segurança + UX

| Ordem | Story | Est | Foco | Paralelo? |
|-------|-------|-----|------|-----------|
| 3a | **STORY-356** | S | Pipeline backend enforcement | SIM, com 355+357 |
| 3b | **STORY-355** | M | ROI calculator honest defaults | SIM, com 356+357 |
| 3c | **STORY-357** | M | Auth token pre-emptive refresh | SIM, com 355+356 |

**Justificativa:** Três stories independentes. 356 é backend (pipeline.py), 355 é frontend (roi.ts, pricing), 357 é frontend (proxy, auth). Zero conflito.

### FASE 4 — Sprint 3 (Semana 8-10): Observabilidade + Consistência

| Ordem | Story | Est | Foco | Paralelo? |
|-------|-------|-----|------|-----------|
| 4a | **STORY-353** | L | SLA infra (migration + cron + admin) | SIM, com 358-360 |
| 4b | **STORY-358** | M | Instrumentar "1000+/dia" | SIM, com 353/359/360 |
| 4c | **STORY-359** | S | SSE degradação transparente | SIM, com 353/358/360 |
| 4d | **STORY-360** | S | Fix inconsistência preços | SIM, com 353/358/359 |

**Nota:** 353 e 358 ambas tocam `metrics.py` e `cron_jobs.py`. Fazer 353 primeiro nestes arquivos, depois 358.

---

## Grafo de Dependências

```
STORY-350 ──┐
            ├── (nenhuma dependência)
STORY-352 ──┘

STORY-351 ──── (independente)
STORY-354 ──── (independente)

STORY-355 ──── (independente)
STORY-356 ──── (independente)
STORY-357 ──── (independente)

STORY-353 ──── depende soft de STORY-352 (copy "24h" já ajustada)
STORY-358 ──── conflito de arquivo com STORY-353 (metrics.py, cron_jobs.py)
STORY-359 ──── (independente)
STORY-360 ──── (independente)
```

**Conclusão:** As 11 stories são quase totalmente independentes. A única dependência real é:
- **STORY-353 ← STORY-352** (soft: a copy "24h" deve estar ajustada antes de criar infra de SLA)
- **STORY-358 ←→ STORY-353** (conflito de arquivo: sequenciar dentro do Sprint 3)

---

## Resumo de Paralelismo

| Sprint | Stories em paralelo | Dev-weeks |
|--------|--------------------|-----------|
| Imediato | 350 + 352 | 1.5 |
| Sprint 1 | 351 + 354 | 3.0 |
| Sprint 2 | 355 + 356 + 357 | 2.5 |
| Sprint 3 | 353 + 358 + 359 + 360 | 3.0 |
| **Total** | | **~10 semanas** |

Com 2 devs paralelos, reduz para ~5-6 semanas.

---

## Quick Wins (podem ir para produção em <1 dia)

1. **STORY-352** (S) — trocar 3 strings + adicionar BANNED
2. **STORY-350** AC1+AC2+AC4 — trocar copy + adicionar BANNED (sem a métrica)
3. **STORY-360** AC5 — unificar FAQ com objeto PRICING existente

---

_Gerado pelo Conselho CTO Advisory Board — 2026-03-01_
