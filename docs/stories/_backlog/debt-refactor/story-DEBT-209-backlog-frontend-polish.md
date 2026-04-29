# Story DEBT-209: Backlog Oportunistico — Frontend Polish e Design System

## Metadados
- **Epic:** EPIC-DEBT-V2
- **Sprint:** Backlog (resolver durante feature work)
- **Prioridade:** P3 (Baixa)
- **Esforco:** 17h
- **Agente:** @dev + @ux-design-expert
- **Status:** COMPLETED

## Descricao

Como equipe de frontend, queremos resolver debitos cosmeticos e de design system acumulados (SVGs inconsistentes, tokens de cor hardcoded, focus order, SEO thin content, admin sem SWR), para que o codebase frontend seja mais consistente e mantenivel.

## Debitos Incluidos

| ID | Debito | Horas | Trigger para Resolver |
|----|--------|-------|-----------------------|
| DEBT-FE-005 | `/admin` usa `useState` + `fetch` manual — inconsistente com SWR | 4h | Durante feature work em admin |
| DEBT-FE-009 | SVGs inline vs lucide-react — MobileDrawer com 10+ SVGs inline | 3h | Durante refactor de MobileDrawer |
| DEBT-FE-010 | Raw hex values vs tokens semanticos — inconsistencias em componentes | 4h | Durante refactor visual |
| DEBT-FE-012 | Focus order em BuscarModals — modais sobrepostos confundem focus | 2h | Durante work em BuscarModals |
| DEBT-FE-015 | SEO pages thin content — `/como-*` com risco de penalidade | 4h | Antes de campanha SEO |

## Criterios de Aceite

### Admin SWR Migration (4h)
- [x] Paginas `/admin` e `/admin/cache` migradas para SWR para data fetching
- [x] `useState` + `fetch` manual substituidos por `useSWR` hooks
- [x] Revalidation automatica consistente com resto do app
- [x] Loading/error states usando mesmo padrao do app

### SVGs Migration (3h)
- [x] 10+ SVGs inline em MobileDrawer substituidos por componentes lucide-react
- [x] Consistencia visual mantida (tamanho, cor, stroke-width)
- [x] Bundle size nao aumenta (lucide-react e tree-shakeable)

### Tokens Semanticos (4h)
- [x] Raw hex values (`#1a1a1a`, `#f3f4f6`, etc.) substituidos por tokens Tailwind
- [x] Inventario de hex values hardcoded criado
- [x] Componentes secundarios atualizados
- [x] Dark mode compatibilidade preservada

### Focus Order (2h)
- [x] Modais sobrepostos em `/buscar` gerenciam focus trap corretamente
- [x] Fechar modal interno retorna focus para modal externo (ou elemento trigger)
- [x] Tab order logico dentro de cada modal

### SEO Pages (4h)
- [x] Paginas `/como-*` com conteudo expandido (minimo 300 palavras por pagina)
- [x] Structured data (Schema.org) adicionado onde aplicavel
- [x] Meta descriptions unicas e descritivas

## Testes Requeridos

- [x] `npm test` — suite completa frontend passa
- [ ] axe-core em paginas modificadas
- [ ] Focus trap test manual em BuscarModals
- [ ] Visual regression nos componentes com SVGs migrados

## Notas Tecnicas

- **Nao justifica sprint dedicado.** Cada item deve ser resolvido quando o desenvolvedor estiver trabalhando na area afetada.
- **SVGs inline:** Verificar se todos os SVGs inline no MobileDrawer tem equivalente em lucide-react antes de migrar.
- **Tokens semanticos:** Priorizar componentes com maior uso. Usar Tailwind CSS variables para temas.

## Dependencias

- Nenhuma — independente de todas as outras stories
- DEBT-FE-012 (focus order) pode se beneficiar de DEBT-202 (useSearchOrchestration decomposicao)
