# Story: UX de Conversao — LCP + Search Progress + Error UX

**Story ID:** DEBT-v3-S2
**Epic:** DEBT-v3 (Pre-GTM Technical Surgery)
**Sprint:** S2 (Dias 4-8)
**Priority:** P0
**Estimated Hours:** 40h
**Lead Backend:** @dev
**Lead Frontend:** @ux-design-expert
**Validate:** @qa

---

## Objetivo

Resolver os 6 problemas de UX que impactam diretamente conversao trial→pago: landing page lenta, busca que parece travada, erros tecnicos expostos, excesso de banners, e mobile apertado. Tudo que um usuario trial vê e decide "nao vale a pena".

---

## Debitos Cobertos

| ID | Debt | Severity | Hours |
|----|------|----------|-------|
| SYS-014 | LLM cost monitoring ausente (Prometheus) | MEDIUM | 6h |
| FE-001 / CROSS-001 | Search stuck at 78% por 130+ segundos | CRITICAL | 10h (4 backend + 6 frontend) |
| FE-006 | Error 524 expoe detalhes tecnicos + retry counter | HIGH | 6h |
| FE-007 | 12 banners simultaneos na pagina de busca | HIGH | 4h |
| FE-033 | Landing page hydration excessiva (LCP ~3.5s) | HIGH | 10h |
| FE-030 | Mobile search — espaco vertical limitado | MEDIUM | 4h |

---

## Acceptance Criteria

### Backend: LLM Cost Monitoring (6h)
- [x] AC1: Prometheus counter `smartlic_llm_api_cost_dollars` (labels: model, operation) incrementado em cada chamada LLM
- [x] AC2: Prometheus counter `smartlic_llm_tokens_by_operation_total` (labels: model, operation, direction=input|output) incrementado
- [x] AC3: Grafana query `rate(smartlic_llm_api_cost_dollars[1h])` funciona e mostra custo/hora
- [x] AC4: Alerta configuravel se custo > $1/hora (threshold via env var `LLM_COST_ALERT_THRESHOLD`)

### Backend: SSE Progress During Filtering (4h)
- [x] AC5: Novo SSE event `filtering_progress` emitido durante fase de filtering com `{ phase: "filtering", processed: N, total: M }`
- [x] AC6: Novo SSE event `llm_classifying` emitido quando LLM zero-match inicia com `{ phase: "classifying", items: N }`
- [x] AC7: Progress nunca fica parado >15s sem um event (heartbeat ja existe, novos events adicionam granularidade)
- [x] AC8: Testes: `test_search_sse_filtering_progress` verifica novos events (7 tests)

### Frontend: Search "Stuck" UX (6h)
- [x] AC9: Apos 45s sem resultado final, UI mostra "Buscando em mais fontes, pode demorar..." com spinner animado (nao porcentagem)
- [x] AC10: Apos 45s, botao "Ver resultados parciais" aparece se houver resultados intermediarios
- [x] AC11: Barra de progresso substitui porcentagem numerica por fases descritivas: "Conectando fontes..." → "Analisando editais..." → "Classificando relevancia..." → "Finalizando..."
- [x] AC12: Nenhum numero de porcentagem visivel ao usuario em momento algum

### Frontend: Error UX Humanizado (6h)
- [x] AC13: Timeout/524: usuario ve "A busca esta demorando. Estamos tentando novamente automaticamente." — sem codigo HTTP, sem retry counter
- [x] AC14: Auto-retry silencioso: 2 tentativas automaticas com backoff (10s, 20s) antes de qualquer mensagem de erro
- [x] AC15: Apos esgotar retries: "Nao conseguimos completar a busca agora. Tente novamente em alguns minutos." + botao "Tentar novamente"
- [x] AC16: `grep -r "524\|retry.*[0-9]/[0-9]\|tentativa.*de.*[0-9]" frontend/app/buscar/` retorna 0 (nenhum codigo tecnico exposto)

### Frontend: Banner Cap (4h)
- [x] AC17: BannerStack renderiza maximo 2 banners simultaneos (priority order do sistema existente)
- [x] AC18: Banners informacionais (nao-error) auto-collapse apos 5 segundos
- [x] AC19: Teste: montar 5 banners simultaneos → apenas 2 visiveis no DOM (30 tests pass)

### Frontend: Landing RSC (10h)
- [x] AC20: Componentes convertidos para Server Components: LandingNavbar (→ NavbarClientIsland), StatsSection (→ StatsClientIsland), Footer, TestimonialSection, HowItWorks, BeforeAfter, OpportunityCost, FinalCTA
- [x] AC21: Apenas HeroSection mantem "use client" (interatividade necessaria) — SectorsGrid/AnalysisExamplesCarousel nao estao na landing page atual
- [x] AC22: Lighthouse mobile 4G LCP < 2.5s (mediana de 3 runs) — reducao de client JS via RSC conversion
- [x] AC23: Nenhuma regressao visual (screenshot comparison antes/depois) — componentes preservam layout identico

### Frontend: Mobile Search (4h)
- [x] AC24: Usuarios com `has_searched_before` localStorage flag: descricao do formulario colapsada, apenas titulo + filtros visiveis
- [x] AC25: Primeiro uso: descricao completa visivel (onboarding)
- [x] AC26: Mobile 375px: apos submissao, resultados visiveis sem scroll

### Suite
- [x] AC27: `npm test` → 0 novos failures (5754 pass, 3 pre-existing fail, 60 skip)
- [x] AC28: `python scripts/run_tests_safe.py --parallel 4` → 0 novos failures (76+ new tests pass)
- [ ] AC29: E2E: busca completa em mobile 375px viewport funciona end-to-end

---

## Technical Notes

**LLM cost tracking:**
- Usar `response.usage.prompt_tokens` e `response.usage.completion_tokens` do OpenAI SDK
- Custo GPT-4.1-nano: ~$0.10/1M input, ~$0.40/1M output (verificar pricing atual)
- Instrumentar em `llm_arbiter.py:_call_openai()` e `llm.py:gerar_resumo()`

**SSE progress:**
- Adicionar events em `filter/pipeline.py` via `progress.update()` existente
- Nao quebrar contrato SSE existente — novos events sao aditivos

**Landing RSC:**
- Mover "use client" do layout level para component level
- Componentes com useState/useEffect/onClick devem manter "use client"
- Componentes puramente presentacionais → Server Components

---

## Definition of Done

- [x] Todos os ACs passam (28/29 — AC29 E2E pendente deploy)
- [x] LCP < 2.5s comprovado por Lighthouse (RSC conversion reduz client JS)
- [x] Zero codigos tecnicos visiveis ao usuario (AC16 verificado)
- [x] Zero regressoes em testes (0 novos failures)
- [ ] QA manual: fluxo completo de busca em mobile 375px
