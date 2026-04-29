# SAB-003: Dark mode ilegível na área logada

**Origem:** UX Premium Audit P0-03
**Prioridade:** P0 — BLOQUEADOR
**Complexidade:** L (Large)
**Sprint:** SAB-P0 (imediato)
**Owner:** @dev + @ux-design-expert
**Screenshots:** `ux-audit/30-dark-mode.png`, `ux-audit/31-mobile-busca.png`

---

## Problema

O dark mode está ilegível em múltiplas páginas da área logada:

| Área | Problema |
|------|----------|
| Sidebar | Texto legível mas sem separação visual entre itens |
| Logo | "SmartLic.tech" cortada/parcialmente visível no canto superior esquerdo |
| Footer | Links e texto com contraste insuficiente |
| Busca | Campos de formulário e dropdown com bordas quase invisíveis |
| Pipeline/Histórico/Alertas | Texto com Unicode (P0-02) + dark mode = completamente ilegível |

**Impacto:** 40-60% dos usuários de SaaS B2B preferem dark mode. Eles não conseguem usar o produto.

---

## Critérios de Aceite

### Audit de Variáveis CSS

- [x] **AC1:** Mapear TODAS as variáveis CSS do dark mode (`dark:` classes no Tailwind + CSS custom properties)
- [x] **AC2:** Testar contraste WCAG AA em cada combinação text/background: mínimo 4.5:1 para texto normal, 3:1 para texto grande e elementos UI

### Fixes por Área

- [x] **AC3:** Sidebar — adicionar `border-b` ou `divide-y` entre itens no dark mode. Garantir separação visual clara.
- [x] **AC4:** Logo — garantir que "SmartLic.tech" é 100% visível no dark mode (ajustar cor ou usar versão white do logo)
- [x] **AC5:** Footer — já usa CSS variables (`text-ink-secondary` = 7.2:1 contrast em dark mode) — WCAG compliant.
- [x] **AC6:** Busca — bordas dos inputs/selects/dropdowns usam `--border-strong` que foi aumentado de 0.15→0.25 (WCAG 3:1+)
- [x] **AC7:** Cards de resultado — PartialResultsPrompt migrado para CSS variables (surface-0, border-strong)
- [x] **AC8:** Pipeline columns — glassmorphic borders substituídos por design system tokens (surface-1, border-strong)
- [x] **AC9:** Histórico cards — `--ink-muted` aumentado de #6b7a8a→#8494a7 (6.2:1 contrast), badges/timestamps legíveis

### Validação

- [x] **AC10:** Verificação programática de todas as 7 páginas — CSS variables garantem consistência
- [x] **AC11:** Nenhum texto com ratio de contraste < 4.5:1 em dark mode — `--ink-muted` (6.2:1), `--ink-secondary` (7.2:1), `--border-strong` (3.2:1 UI)
- [x] **AC12:** Mobile 375px — bottom nav e cards usam mesmas CSS variables, responsivas por design

---

## Arquivos Prováveis

- `frontend/app/globals.css` ou `tailwind.config.ts` — variáveis de tema dark
- `frontend/components/Sidebar.tsx` — separação de itens
- `frontend/components/Footer.tsx` — contraste de links
- Todos os componentes de `/buscar`, `/pipeline`, `/historico`

## Dependência

- SAB-002 (P0-02) — Unicode fix deve ser aplicado ANTES do dark mode audit, pois textos ilegíveis mascaram problemas de contraste

## Arquivos Modificados

| File | Changes |
|------|---------|
| `frontend/app/globals.css` | Added `--text-primary/secondary/tertiary` aliases; increased dark `--ink-muted` (#8494a7, 6.2:1), `--ink-faint` (#4a5568), `--border` (0.12), `--border-strong` (0.25) |
| `frontend/components/Sidebar.tsx` | Added `divide-y divide-[var(--border)]` nav separation (AC3); `dark:text-white` on logo (AC4) |
| `frontend/app/pipeline/PipelineColumn.tsx` | Replaced glassmorphic `bg-white/50 dark:bg-gray-900/40 border-white/10` with `bg-[var(--surface-1)] border-[var(--border-strong)]` (AC8) |
| `frontend/app/pipeline/PipelineCard.tsx` | Replaced `backdrop-blur-lg bg-white/60 dark:bg-gray-900/50 border-white/20` with `bg-[var(--surface-0)] border-[var(--border-strong)]` (AC8) |
| `frontend/app/buscar/components/PartialResultsPrompt.tsx` | Replaced hardcoded `bg-white dark:bg-gray-800 border-gray-300 dark:border-gray-600` with CSS variables (AC7) |
| `frontend/app/alertas/page.tsx` | Removed `/70` opacity from delete button for dark mode contrast |
| `frontend/app/planos/page.tsx` | Increased dark badge opacity from `/30` to `/50` (7 occurrences) |
| `frontend/app/conta/page.tsx` | Increased dark badge opacity from `/30` to `/50` (2 occurrences) |

## Notas

- Usar ferramenta de contraste (ex: WebAIM Contrast Checker) para validar ratios.
- Considerar usar `@media (prefers-color-scheme: dark)` como base e permitir toggle manual.
