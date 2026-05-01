# STORY-DEBT-2: Landing Page RSC + Framer Motion Islands

**Epic:** EPIC-DEBT-2026
**Batch:** 2
**Prioridade:** P1
**Estimativa:** 10h
**Agente:** @dev (implementacao) + @ux-design-expert (visual validation) + @qa (validacao)

## Descricao

A landing page (`app/(marketing)/page.tsx`) e um Server Component, mas todos 13 componentes filhos usam `"use client"`. Apenas 3 precisam de Framer Motion para animacoes. Os outros 10 usam `"use client"` apenas para `useState`, `useEffect`, ou `useInView` -- tudo substituivel por CSS ou lightweight alternatives.

Isso forca o browser a baixar e hidratar todo o JavaScript da landing page antes de renderizar, prejudicando LCP (>3s estimado) e SEO no ponto de entrada mais critico do funil de aquisicao.

**Abordagem:** Islands architecture -- converter 10 de 13 componentes para RSC, manter 3 client islands para Framer Motion (HeroSection, SectorsGrid, AnalysisExamplesCarousel).

**Debt IDs:** TD-M07

## Acceptance Criteria

- [ ] AC1: 10 dos 13 componentes da landing convertidos para Server Components (sem `"use client"` directive)
- [ ] AC2: 3 componentes mantidos como client islands: HeroSection, SectorsGrid, AnalysisExamplesCarousel (os que usam Framer Motion)
- [ ] AC3: `useInView` substituido por CSS `animation-timeline: view()` ou lightweight IntersectionObserver wrapper nos componentes convertidos
- [ ] AC4: `npm run build` completa sem erros (Next.js detecta RSC import violations em build time)
- [ ] AC5: Lighthouse CI (mobile, 3G throttled): LCP < 2.5s, TTFB < 800ms
- [ ] AC6: Client JS bundle da landing page reduzido em pelo menos 40KB gzipped (medir antes/depois com `next/bundle-analyzer`)
- [ ] AC7: Visual regression test: Playwright screenshots em 3 breakpoints (375px, 768px, 1440px) com diff < 1% comparado ao baseline
- [ ] AC8: Animacoes de scroll (fade-in, slide-up) continuam funcionando visualmente identico ao estado anterior

## Tasks

- [ ] T1: Baseline -- capturar metricas atuais: Lighthouse scores, bundle size (`ANALYZE=true npm run build`), Playwright screenshots em 3 breakpoints. Documentar no PR. (1h)
- [ ] T2: Identificar os 13 componentes filhos e classificar: quais usam Framer Motion (client), quais usam apenas useState/useEffect/useInView (convertible). (0.5h)
- [ ] T3: Converter componentes sem hooks primeiro (pure render) -- zero risk. Build e test apos cada conversao. (2h)
- [ ] T4: Substituir `useInView` por CSS `animation-timeline: view()` com fallback para `@supports` ou lightweight IntersectionObserver wrapper sem `"use client"`. (2h)
- [ ] T5: Converter componentes que usavam apenas useState para controle de visibilidade -- substituir por CSS `:target` ou server-driven. (2h)
- [ ] T6: Validar 3 client islands (HeroSection, SectorsGrid, AnalysisExamplesCarousel) continuam com animacoes corretas. (0.5h)
- [ ] T7: Capturar metricas pos-conversao e calcular delta. Lighthouse CI check. (1h)
- [ ] T8: Visual regression: comparar screenshots pre/pos em 3 breakpoints. (1h)

## Testes Requeridos

- **Build:** `npm run build` sucesso (RSC import errors caught at build time)
- **Lighthouse:** LCP < 2.5s, TTFB < 800ms (mobile, 3G throttled)
- **Bundle:** `ANALYZE=true npm run build` -- delta documentado, target -40KB+ gzipped
- **Visual regression:** Playwright screenshots 375px/768px/1440px, pixel diff < 1%
- **E2E:** `npm run test:e2e` -- landing page tests pass
- **Frontend:** `npm test` -- zero regressions (5733 pass)

## Definition of Done

- [ ] All ACs checked
- [ ] Before/after metrics documented in PR (Lighthouse, bundle size, screenshots)
- [ ] Tests pass (build + Lighthouse + visual + e2e + unit)
- [ ] No regressions
- [ ] Code reviewed
- [ ] UX specialist sign-off on visual regression screenshots

## File List

- `frontend/app/(marketing)/page.tsx` (landing page -- already RSC)
- `frontend/app/(marketing)/components/*.tsx` (13 child components -- 10 to convert)
- `frontend/components/landing/*.tsx` (alternative location for landing components)
- `frontend/next.config.js` (possibly add `bundleAnalyzer` config)
- `frontend/package.json` (add `@next/bundle-analyzer` if not present)

## Notas

- **Independente de outros batches:** TD-M07 nao depende de TD-H01 (protected pages RSC). Correcao do QA -- o DRAFT original incorretamente encadeava estas tarefas.
- **Risk mitigation:** Converter UM componente de cada vez, `npm run build` apos cada conversao. Reverte facil se algo quebrar.
- **CSS `animation-timeline: view()`:** Suporte em Chrome 115+, Firefox 114+. Safari nao suporta (Jun 2025). Precisa de fallback com `@supports` -- componente simplesmente aparece sem animacao em browsers sem suporte (degradacao graceful).
- **Framer Motion e o gatekeeper:** Qualquer componente que importa `framer-motion` DEVE permanecer `"use client"`. Next.js falha o build se RSC importar client-only module.
- **`next/bundle-analyzer`:** Se nao instalado, `npm install @next/bundle-analyzer` e configurar em `next.config.js`.
