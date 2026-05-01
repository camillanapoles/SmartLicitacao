# Story CONV-CTA-001: Hero CTA trial em /contratos/orgao/[cnpj]

## Status
InReview

## Epic
[EPIC-CONV-DIAG-2026-04-30](EPIC-CONV-DIAG-2026-04-30.md)

## Story

**As a** visitante orgânico GSC que aterrissa em `/contratos/orgao/{cnpj}`,
**I want** ver um CTA claro e desejável de "Teste grátis por 14 dias" no topo e no rodapé da página,
**so that** eu tenha um caminho óbvio para entrar no produto — atualmente a página tem 292 linhas e ZERO match para `/signup|trial|cadastr` (apenas `<LeadCapture>` no rodapé que captura email para newsletter, NÃO leva ao trial).

**Diagnóstico GSC 28d (2026-04-30):** 4 das 10 top URLs GSC são `/contratos/orgao/[cnpj]` (`75095679000149`, `24772162000106`, `83026781000110` + 1 truncado), absorvendo ≥12 clicks/mês — atualmente desperdiçados.

## Acceptance Criteria

1. **AC1 — Hero CTA proeminente:** Adicionar CTA visível dentro do bloco hero (`/mnt/d/pncp-poc/frontend/app/contratos/orgao/[cnpj]/page.tsx:152-171`), abaixo do `<p>` de CNPJ/Atualizado, com:
   - Headline: "Quer monitorar [orgao_nome] e descobrir oportunidades antes da concorrência?"
   - Subheadline: "O SmartLic rastreia novos editais e contratos automaticamente."
   - CTA primário: `<Link href="/signup?utm_source=programmatic&utm_medium=cta&utm_campaign=conv-cta-001&utm_content=contratos-orgao&page_cnpj={cnpj}">Teste grátis por 14 dias</Link>`
   - Subtext sob o botão: "Sem cartão de crédito · 14 dias grátis"

2. **AC2 — CTA secundário em rodapé:** Substituir/complementar o `<LeadCapture>` em `page.tsx:281-285` por um bloco CTA forte similar ao de `frontend/app/fornecedores/[cnpj]/page.tsx:382-397` (template aprovado: `bg-blue-50 rounded-lg p-6 text-center` com h2 + p + Link). O `<LeadCapture>` pode permanecer como secundário se o user preferir email.

3. **AC3 — UTM compatível com BlogInlineCTA pattern:** Os UTM params seguem o padrão estabelecido em `frontend/app/blog/components/BlogInlineCTA.tsx:25` (`utm_source`, `utm_medium`, `utm_content`, `utm_campaign`). Diferenças justificadas:
   - `utm_source=programmatic` (não `blog`) — diferenciar tipo de página
   - `utm_campaign=conv-cta-001` — atribuir aos relatórios deste epic
   - Custom param `page_cnpj={cnpj}` — permite Mixpanel breakdown por órgão exato

4. **AC4 — Mixpanel `cta_clicked` tracking:** Adicionar onClick handler que dispara `trackEvent('cta_clicked', { cta_name: 'contratos_orgao_hero'|'contratos_orgao_footer', destination: '/signup', page_type: 'contratos_orgao', page_cnpj: cnpj, orgao_nome: stats.orgao_nome })` — usando `useAnalytics()` (precisa converter componente para client component OU adicionar onClick em wrapper client). **Preferência:** criar `<TrackingLink>` reutilizável em `frontend/components/TrackingLink.tsx` se ainda não existir.

5. **AC5 — Mobile responsive:** CTAs DEVEM ser legíveis e clicáveis em viewport 360px (Pixel 5 / iPhone SE). Botão min-height 44px (já é padrão no `fornecedores/[cnpj]:392-396`).

6. **AC6 — A11y:** `<Link>` com texto descritivo (não "Clique aqui"). `<section>` com `aria-labelledby` apontando para o h2. Contraste WCAG AA verificado (já é no `bg-blue-50 + bg-blue-600` template).

7. **AC7 — Não quebrar SSG/ISR:** A página atual é `revalidate = 14400` (4h) com `generateStaticParams() => []` (SSR on-demand). Modificações DEVEM preservar esse contrato (memory `feedback_isr_fetch_cache_alignment_next16.md`). Componente client (TrackingLink) DEVE estar em `'use client'` separado para não quebrar SSG.

8. **AC8 — Templates correlatos atualizados (escopo gated):** Listar (NÃO executar — escopo CONV-CTA-002 W2) outros programmatic templates que precisam do mesmo tratamento: `/cnpj/[cnpj]`, `/orgaos/[slug]`, `/municipios/[slug]`, `/observatorio/[slug]`, `/observatorio/raio-x-*/[id]`, `/contratos/[setor]`, `/contratos/[setor]/[uf]`. Documentar em `docs/stories/2026-04/CONV-CTA-002-audit-programmatic-templates.story.md` (criar com Status: Draft, sem ACs detalhados — placeholder para W2).

9. **AC9 — Testes:**
   - `frontend/__tests__/contratos/orgao-cta.test.tsx` — render → 2 CTAs visíveis (hero + footer) + UTM params corretos no href
   - E2E (opcional W1, P0 W2 via CONV-INST-004): visit `/contratos/orgao/{seed-cnpj}` → click CTA hero → assert URL inclui `utm_campaign=conv-cta-001`

## 🤖 CodeRabbit Integration

> **CodeRabbit Integration**: focus — ISR safety (não converter page.tsx em 'use client'), TrackingLink accessibility, UTM consistency com BlogInlineCTA pattern, mobile tap target 44px.

## Tasks / Subtasks

- [x] Task 1 — Criar `TrackingLink` component (AC4)
  - [x] `frontend/components/TrackingLink.tsx` ('use client', wrapper sobre `<Link>` com onClick → trackEvent)
  - [x] Props: `href`, `eventName`, `eventProps`, `children`, `className`
- [x] Task 2 — Hero CTA em contratos/orgao (AC1, AC3, AC4, AC5, AC6)
  - [x] Adicionar bloco em `page.tsx:152-171`
  - [x] Usar `<TrackingLink>`
- [x] Task 3 — Footer CTA em contratos/orgao (AC2, AC3, AC4)
  - [x] Substituir/complementar `<LeadCapture>` linha 281-285
- [x] Task 4 — Placeholder story CONV-CTA-002 (AC8)
  - [x] Criar `docs/stories/2026-04/CONV-CTA-002-audit-programmatic-templates.story.md` com Status: Draft + lista de paths a auditar
- [x] Task 5 — Testes (AC9)

## Dev Notes

### Files to modify
- `frontend/app/contratos/orgao/[cnpj]/page.tsx` (linhas 152-171, 281-285)

### Files to create
- `frontend/components/TrackingLink.tsx`
- `frontend/__tests__/contratos/orgao-cta.test.tsx`
- `docs/stories/2026-04/CONV-CTA-002-audit-programmatic-templates.story.md` (placeholder)
- `frontend/__tests__/components/TrackingLink.test.tsx`

### Reference templates
- **CTA aprovado (fornecedores):** `frontend/app/fornecedores/[cnpj]/page.tsx:382-397` — copiar estrutura visual
- **UTM padrão (blog):** `frontend/app/blog/components/BlogInlineCTA.tsx:25` — copiar formato

### IDS Decision (REUSE > ADAPT > CREATE)
- **REUSE:** Template visual de `fornecedores/[cnpj]:382-397`, padrão UTM de `BlogInlineCTA:25`, `useAnalytics().trackEvent`, `<Link>` Next.js
- **ADAPT:** `contratos/orgao/[cnpj]/page.tsx` (adicionar 2 sections sem alterar fetch/ISR)
- **CREATE:** `TrackingLink.tsx` (sem equivalente direto — `BlogInlineCTA` é específico de blog)

### Memory references
- `feedback_build_hammers_backend_cascade.md` — preservar `AbortSignal.timeout(10000)` linha 55 + ISR 14400
- `feedback_isr_fetch_cache_alignment_next16.md` — não converter page.tsx em 'use client' inteiro
- `feedback_sen_fe_001_recidiva_sitemap.md` — após fix, grep global por programmatic templates sem CTA (CONV-CTA-002 W2 cobre)

### Testing
- Framework: Jest + RTL
- Mock: `next/link` é auto-mockado em jest.setup
- Assertion: `screen.getAllByText(/Teste grátis por 14 dias/i)` retorna 2 elementos; `screen.getByRole('link', { name: /Teste grátis/ })[0].getAttribute('href')` contém `utm_campaign=conv-cta-001`

## Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2026-04-30 | 0.1 | Story drafted from EPIC-CONV-DIAG-2026-04-30 W1 — confirmed ZERO CTA via grep on /contratos/orgao/[cnpj]/page.tsx | @sm |
| 2026-04-30 | 0.2 | PO validation GO 10/10 — Status Draft → Ready. Maior alavanca do W1 (4 das top 10 GSC URLs). Template aprovado em fornecedores/[cnpj]:382-397 + UTM pattern em BlogInlineCTA:25 = REUSE estrita. AC7 ISR safety call-out impede regressão (memory `feedback_isr_fetch_cache_alignment_next16.md`). AC8 desbloqueia CONV-CTA-002 W2 com placeholder. Pronto. | @po |
| 2026-05-01 | 1.0 | Implementação completa — TrackingLink.tsx criado, 2 CTAs (hero+footer) em page.tsx, 6 testes passando, CONV-CTA-002 placeholder Draft criado. Status: InProgress → InReview. | @dev |
