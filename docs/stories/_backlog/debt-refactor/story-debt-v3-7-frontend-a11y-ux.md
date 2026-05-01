# Story: Frontend Accessibility + UX Improvements

**Story ID:** DEBT-v3-007
**Epic:** DEBT-v3
**Phase:** 3 (Optimization)
**Priority:** P2
**Estimated Hours:** 42h
**Agent:** @dev, @ux-design-expert
**Status:** PLANNED

---

## Objetivo

Resolver o cluster de debitos de acessibilidade e UX que afeta conformidade com WCAG 2.1 AA (Lei 13.146/2015) e qualidade geral da experiencia. Inclui aria-live gaps, dark mode contrast, pipeline drag announcements, ErrorBoundary gaps, e melhorias de mobile UX.

---

## Debitos Cobertos

### Accessibility (~18h)

| ID | Debt | Severity | Hours |
|----|------|----------|-------|
| FE-009 | `aria-live` incompleto para search results — 6 banners sem aria-live, results count pouco explicito | MEDIUM | 2h |
| FE-012 | SVG icons sem `role="img"` ou `aria-label` — prioridade: status icons em `/historico` e `/mensagens` | MEDIUM | 3h |
| FE-014 | Forms sem `aria-describedby` para campos com hints | MEDIUM | 3h |
| FE-028 | Dark mode brand-blue contrast — `#116dff` vs `#121212` falha AA para texto <18px. Fix: `--brand-blue-dark: #3388ff` | MEDIUM | 2h |
| FE-034 | Pipeline kanban sem drag announcements — `DndContext` sem `accessibility` prop para screen readers | MEDIUM | 4h |
| FE-018 | Dark mode contrast em search form — borders em interactive elements (`border border-ink/10`) | MEDIUM | 2h |

### UX Improvements (~16h)

| ID | Debt | Severity | Hours |
|----|------|----------|-------|
| FE-008 | `/admin` usa `useState` + fetch manual em vez de SWR | MEDIUM | 4h |
| FE-010 | `mensagens/page.tsx` 591 LOC — extrair ConversationList, ConversationDetail, MessageComposer | MEDIUM | 8h |
| FE-030 | Mobile search espaco vertical limitado — form ocupa viewport, resultados invisiveis sem scroll | MEDIUM | 4h |

### Infrastructure (~8h)

| ID | Debt | Severity | Hours |
|----|------|----------|-------|
| FE-016 | Sem ErrorBoundary em SWRProvider/UserProvider — hierarquia de 7 providers sem boundary | MEDIUM | 3h |
| FE-020 | Sem edge caching para endpoints estaveis — `/api/setores` e `/api/plans` sem Cache-Control | MEDIUM | 2h |

---

## Acceptance Criteria

### Accessibility
- [ ] AC1: Todos 6 banners restantes tem `aria-live="polite"` ou `aria-live="assertive"` (conforme urgencia)
- [ ] AC2: Search results count anunciado via `aria-live` region quando resultados carregam
- [ ] AC3: Todos SVG status icons em `/historico` e `/mensagens` tem `role="img"` + `aria-label` descritivo
- [ ] AC4: Todos campos de form com hints visuais tem `aria-describedby` linkando ao hint text
- [ ] AC5: `--brand-blue-dark: #3388ff` (~5.2:1 contrast ratio) aplicado no dark mode
- [ ] AC6: Pipeline kanban: `DndContext` com `accessibility` prop — announcements para `onDragStart`, `onDragOver`, `onDragEnd`, `onDragCancel` em portugues
- [ ] AC7: Pipeline cards com `aria-roledescription="item ordenavel"`
- [ ] AC8: Dark mode search form: borders visiveis em interactive elements

### UX
- [ ] AC9: `/admin` migrado para SWR com `revalidateOnFocus` e error handling
- [ ] AC10: `mensagens/page.tsx` decomposto em 3+ componentes — cada <200 LOC
- [ ] AC11: Mobile (375px): form de busca colapsa descricao para returning users (`has_searched_before` localStorage flag)
- [ ] AC12: Mobile: titulo do form visivel para wayfinding mesmo com form colapsado

### Infrastructure
- [ ] AC13: ErrorBoundary wrapping SWRProvider e UserProvider — fallback UI amigavel
- [ ] AC14: `/api/setores` com `Cache-Control: public, s-maxage=3600, stale-while-revalidate=86400`
- [ ] AC15: `/api/plans` com `Cache-Control: public, s-maxage=3600, stale-while-revalidate=86400`

---

## Technical Notes

**FE-028 Dark mode contrast:**
- Current: `#116dff` on `#121212` background = ~4.5:1 (fails AA for <18px text)
- Fix: CSS custom property `--brand-blue-dark: #3388ff` (5.2:1 ratio)
- Apply ONLY in dark mode media query / class
- Do NOT change light mode blue

**FE-034 Pipeline drag announcements:**
- @dnd-kit `DndContext` accepts `accessibility` prop
- Define PT-BR announcements: "Arrastando card [titulo]. Sobre coluna [nome]."
- Add `aria-roledescription="item ordenavel"` to each SortableItem
- Test with screen reader (VoiceOver/NVDA)

**FE-010 Mensagens decomposition:**
- Extract `ConversationList` (sidebar with conversation list)
- Extract `ConversationDetail` (message thread display)
- Extract `MessageComposer` (input + send)
- Page becomes thin compositor

**FE-030 Mobile search:**
- Use `localStorage.getItem('has_searched_before')` flag
- First visit: full form with description
- Return visits: collapsed form, expandable on tap
- Always show search title for wayfinding

---

## Tests Required

- [ ] axe-core audit: zero critical/serious violations on search page, pipeline, mensagens
- [ ] Dark mode contrast: automated check for brand-blue ratio >= 4.5:1
- [ ] `admin-swr.test.tsx` — SWR integration tests
- [ ] `mensagens-components.test.tsx` — decomposed components
- [ ] `pipeline-a11y.test.tsx` — drag announcements, aria attributes
- [ ] Mobile viewport test (375px): form collapse behavior
- [ ] ErrorBoundary test: simulated error shows fallback UI
- [ ] Frontend full suite: `npm test` (zero new failures)

---

## Dependencies

- **REQUIRES:** DEBT-v3-005 (FE-005 directory consolidation helps clean imports for FE-010)
- **ENABLES:** Better a11y compliance for marketing/legal claims

---

## Definition of Done

- [ ] All ACs pass
- [ ] axe-core zero critical violations
- [ ] Frontend tests pass (zero regressions)
- [ ] Dark mode contrast verified (5.2:1 minimum for brand-blue)
- [ ] Mobile tested at 375px viewport
- [ ] Code reviewed
