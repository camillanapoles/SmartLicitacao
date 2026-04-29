# Story DEBT-202: Frontend Estrutural — Landing RSC + useSearchOrchestration + ViabilityBadge

## Metadados
- **Epic:** EPIC-DEBT-V2
- **Sprint:** 3 (Semana 5-6)
- **Prioridade:** P0-P1
- **Esforco:** 26h
- **Agente:** @dev + @qa + @ux-design-expert
- **Status:** InProgress

## Descricao

Como equipe de produto, queremos otimizar a landing page para carregamento rapido (LCP < 2.5s), decompor o mega-hook de busca para facilitar manutencao, e tornar o ViabilityBadge acessivel em todos os dispositivos, para que a taxa de conversao melhore, o desenvolvimento da feature central seja mais agil, e usuarios com deficiencia visual possam usar a plataforma.

## Debitos Incluidos

| ID | Debito | Horas | Responsavel |
|----|--------|-------|-------------|
| DEBT-FE-017 | Landing page com 13 child components "use client" — hydration excessiva | 10h | @dev + @ux-design-expert |
| DEBT-FE-001 | `useSearchOrchestration` mega-hook (618 LOC) — 12+ sub-hooks | 12h | @dev + @qa |
| DEBT-FE-002 | ViabilityBadge usa `title` para dados criticos — inacessivel em mobile/touch | 4h | @dev + @ux-design-expert |

## Criterios de Aceite

### Landing Page RSC Islands (10h)
- [x] 10 dos 13 componentes "use client" convertidos para React Server Components — SectorsGrid + AnalysisExamplesCarousel convertidos (RSC island pattern); 3 legítimos restantes: LandingNavbar/HeroSection/StatsSection
- [x] Apenas componentes genuinamente interativos permanecem client-side — auditoria confirmou LandingNavbar/HeroSection/StatsSection legítimos; commit 5971e50c
- [ ] LCP mobile 4G < 2.5s (Lighthouse CI) — PENDENTE: requer ambiente CI com servidor em execução
- [ ] TTI mobile 4G < 3.5s — PENDENTE: requer ambiente CI com servidor em execução
- [x] Nenhuma funcionalidade da landing page quebrada — Footer convertido, FooterClientIslands extraido; 470 testes landing/buscar passando
- [ ] Visual regression test aprovado (screenshot comparison antes/depois) — PENDENTE: requer ambiente CI com Playwright rodando

### useSearchOrchestration Decomposition (12h)
- [x] Hook decomposto em 4 sub-hooks:
  - [x] `useSearchBillingState` — estado trial/plan/billing (~55 LOC)
  - [x] `useSearchComputedProps` — searchResultsProps useMemo (~113 LOC)
  - [x] `useSearchState` — gerenciamento de estado UI (modais, painel filtros, tip, PDF) (~90 LOC)
  - [x] `useSearchSSE` — backend status monitoring, offline queue, elapsed timer (~80 LOC)
- [x] Hook principal reduzido de 618 para ~250 LOC (API publica preservada)
- [x] Nenhum sub-hook excede 200 LOC
- [x] Snapshot test de `searchResultsProps` — 3 testes passando (estrutura + loading + trial)
- [ ] E2E `search-flow.spec.ts` passa 100% — PENDENTE: requer servidor em execução

### ViabilityBadge Acessivel (4h)
- [x] Breakdown de viabilidade acessivel via CSS tooltip — hover, focus, teclado (Enter/Space/Esc) — commit 5971e50c
- [x] Atributo `title` removido — substituido por role=tooltip + aria-describedby
- [x] Tests atualizados para data-tooltip-content (era title attr)
- [x] axe-core zero violacoes no componente — 6 testes WCAG 2.1 AA passando (alta/media/baixa + sem fatores + valueSource missing + null)
- [x] Touch device: tap-to-toggle implementado (data-mobile-tap state)
- [x] Conformidade WCAG 2.1 AA — role=tooltip + keyboard nav implementados

## Testes Requeridos

- [ ] Lighthouse CI em landing page: LCP < 2.5s, TTI < 3.5s (mobile 4G throttle) — requer CI com servidor
- [ ] Visual regression: screenshot comparison landing page antes/depois — requer Playwright CI
- [x] Snapshot test de `searchResultsProps` — 3 testes passando (useSearchComputedProps-snapshot.test.ts)
- [ ] `search-flow.spec.ts` E2E 100% passando — requer servidor em execução
- [x] axe-core em ViabilityBadge — 6 testes WCAG 2.1 AA (viability-badge-a11y.test.tsx)
- [x] `npm test` — 5721 pass, 3 pre-existing failures (baseline mantido)

## Notas Tecnicas

- **Landing RSC:** Consultar docs do Next.js 16 sobre RSC boundaries antes de converter. Componentes com `useState`, `useEffect`, event handlers devem permanecer client.
- **useSearchOrchestration:** O hook e o coracao da feature principal (`/buscar`). Decomposicao deve preservar exatamente o mesmo comportamento externo. Usar snapshot tests como safety net.
- **ViabilityBadge:** Radix UI Tooltip ja pode estar disponivel no projeto. Verificar `package.json` antes de adicionar dependencia.
- **Branch separada:** Devido ao risco medio de hydration breaks, trabalhar em feature branch com CI verde obrigatorio antes de merge.

## Dependencias

- Nenhuma dependencia direta de outras stories
- Recomendado: DEBT-200 (Sprint 1) completa para base limpa
