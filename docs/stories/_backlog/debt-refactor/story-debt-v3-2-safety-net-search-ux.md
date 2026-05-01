# Story: Safety Net LLM + Search UX Critical

**Story ID:** DEBT-v3-002
**Epic:** DEBT-v3
**Phase:** 1 (Quick Wins)
**Priority:** P0
**Estimated Hours:** 42h
**Agent:** @dev (backend SYS-014 + CROSS-001), @ux-design-expert (FE-001/006/007/033)
**Status:** PLANNED

---

## Objetivo

Estabelecer a rede de seguranca de custos LLM antes de qualquer refatoracao, e resolver os 4 problemas criticos de UX da busca que afetam ~10% dos usuarios em trial: progresso travado em 78%, erro 524 expondo detalhes tecnicos, sobrecarga de banners, e landing page lenta.

---

## Debitos Cobertos

### Backend Safety Net (~6h)

| ID | Debt | Severity | Hours |
|----|------|----------|-------|
| SYS-014 | LLM cost monitoring ausente — sem Prometheus counters para API costs. Erro de refatoracao removendo MAX_ZERO_MATCH_ITEMS passaria despercebido ate conta mensal. | MEDIUM (P0) | 6h |

### Search UX Critical (~36h)

| ID | Debt | Severity | Hours |
|----|------|----------|-------|
| FE-001 | Busca trava em 78% por 130+ segundos — usuarios nao distinguem "trabalhando" de "quebrado" | CRITICAL | 12h |
| CROSS-001 | SSE chain fragility — coordenacao backend (eventos pos-fetch) + frontend ("longer than expected" UI) | HIGH | 4h (coord) |
| FE-006 | Erro 524 expoe detalhes tecnicos — retry counter (1/3, 2/3, 3/3) sinaliza fragilidade | HIGH | 6h |
| FE-007 | 12 banners na pagina de busca — sobrecarga cognitiva no core page | HIGH | 8h |
| FE-033 | Landing page hydration excessiva — 13 componentes client-side, apenas 3 precisam de JS | HIGH | 10h |

---

## Acceptance Criteria

### SYS-014: LLM Cost Monitoring
- [ ] AC1: Prometheus counter `smartlic_llm_api_calls_total` com labels: `model`, `endpoint` (classification/summary/zero_match)
- [ ] AC2: Prometheus histogram `smartlic_llm_api_cost_usd` estimando custo por chamada (tokens * rate)
- [ ] AC3: Prometheus counter `smartlic_llm_tokens_total` com labels: `model`, `type` (prompt/completion)
- [ ] AC4: Alert threshold configuravel via env var `LLM_MONTHLY_BUDGET_USD` (default: 50)
- [ ] AC5: Log WARNING quando custo acumulado no dia exceder `LLM_MONTHLY_BUDGET_USD / 30`

### FE-001 + CROSS-001: Search Progress
- [ ] AC6: Backend emite SSE events `filtering_started`, `llm_classification_started`, `viability_started` durante fases pos-fetch
- [ ] AC7: Frontend mostra "longer than expected" UI apos 45 segundos sem novo evento
- [ ] AC8: "Longer than expected" UI oferece opcao de ver resultados parciais ja disponiveis
- [ ] AC9: Progress bar nunca fica parada no mesmo percentual por mais de 15 segundos (anima sub-steps)
- [ ] AC10: Deploy backend primeiro (eventos aditivos), frontend handles tanto shape antigo quanto novo

### FE-006: Error Messaging
- [ ] AC11: Primeiras 2 tentativas de retry sao silenciosas (sem UI visivel)
- [ ] AC12: Apos todas tentativas esgotadas, exibe banner calmo sem codigos HTTP, sem contador
- [ ] AC13: Pulsing dot sutil durante retry silencioso (status indicator, nao progress bar)
- [ ] AC14: Mensagem de erro focada em acao ("Tente novamente em alguns instantes") nao em causa tecnica

### FE-007: Banner Overload
- [ ] AC15: BannerStack `maxVisible: 2` — maximo 2 banners visiveis simultaneamente
- [ ] AC16: Banners informacionais auto-colapsam apos 5 segundos
- [ ] AC17: Row expandivel "N mais notificacoes" quando > 2 banners ativos
- [ ] AC18: Consolidar CacheBanner + ExpiredCacheBanner + RefreshBanner em unico componente com estados

### FE-033: Landing Page RSC
- [ ] AC19: 10 dos 13 componentes da landing convertidos para Server Components
- [ ] AC20: Apenas HeroSection, SectorsGrid, AnalysisExamplesCarousel permanecem "use client"
- [ ] AC21: LCP medido via Lighthouse CI < 2.5s (target < 2.0s) em mobile 4G throttled
- [ ] AC22: Zero regressao visual (screenshot comparison)
- [ ] AC23: Elementos interativos (CTA buttons, navigation) funcionais pos-conversao

---

## Technical Notes

**SYS-014 Implementation:**
- Adicionar counters em `llm_arbiter.py` (classification), `llm.py` (summaries), e zero-match calls
- Usar `openai.usage` do response para contagem precisa de tokens
- Tabela de custo: GPT-4.1-nano input $0.10/1M, output $0.40/1M (verificar pricing atual)

**FE-001 + CROSS-001:**
- Backend: Adicionar `yield_progress()` calls em `search_pipeline.py` entre fases
- Frontend: `EnhancedLoadingProgress` deve animar micro-steps dentro de cada fase
- Timeout chain: bodyTimeout(0) + heartbeat(15s) > Railway idle(60s) ja configurados (CRIT-012)

**FE-033 RSC Conversion:**
- Verificar Next.js 16 RSC behavior antes de iniciar (Context7 docs)
- Componentes que usam `useState`, `useEffect`, `onClick` DEVEM permanecer client
- Server Components podem import client components (mas nao vice-versa)
- Branch separada recomendada para mudanca de risco

---

## Tests Required

- [ ] `test_llm_metrics.py` — verifica counters incrementam em chamadas LLM
- [ ] `test_search_progress_events.py` — verifica novos SSE events emitidos
- [ ] `error-messaging.test.tsx` — silent retry behavior, calm banner
- [ ] `banner-stack.test.tsx` — max visible, auto-collapse, expandable row
- [ ] `landing-page.test.tsx` — RSC rendering, interactive elements
- [ ] Lighthouse CI integration test — LCP assertion

---

## Definition of Done

- [ ] All ACs pass
- [ ] Backend tests pass (zero regressions via `run_tests_safe.py --parallel 4`)
- [ ] Frontend tests pass (zero regressions)
- [ ] Lighthouse LCP < 2.5s
- [ ] E2E search flow passes
- [ ] No regressions
- [ ] Code reviewed
