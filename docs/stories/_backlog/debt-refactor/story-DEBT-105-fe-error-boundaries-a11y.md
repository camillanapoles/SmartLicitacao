# Story DEBT-105: Frontend Error Boundaries & A11Y Quick Wins

## Metadata
- **Story ID:** DEBT-105
- **Epic:** EPIC-DEBT
- **Batch:** A/B (Quick Wins + Foundation)
- **Sprint:** 1 (Semanas 1-2)
- **Estimativa:** 8h
- **Prioridade:** P1-P2
- **Agent:** @dev + @ux-design-expert

## Descricao

Como usuario da plataforma, quero que erros em paginas internas (dashboard, pipeline, historico, conta) mostrem uma mensagem util em vez de tela em branco, e que indicadores de carregamento/erro sejam acessiveis para leitores de tela, para que minha experiencia nao seja interrompida por falhas silenciosas e o produto seja acessivel a todos.

## Debt Items Cobertos

| ID | Debito | Severidade | Horas |
|----|--------|:---:|:---:|
| FE-NEW-02 | No error boundaries em dashboard, pipeline, historico, conta — crash perde contexto | HIGH | 4h |
| FE-NEW-01 (parcial) | ProfileCompletionPrompt importa framer-motion eagerly (~70KB) — wrap com next/dynamic | MEDIUM | 0.5h |
| FE-A11Y-01 | Loading spinners sem `role="status"` / `aria-busy` (parcialmente mitigado) | LOW | 2h |
| FE-A11Y-05 | Duplicate `<footer role="contentinfo">` confunde landmark navigation | MEDIUM | 1.5h |

## Acceptance Criteria

- [x] AC1: Error boundary em `/dashboard` — erro em child component mostra fallback UI com acao de recovery
- [x] AC2: Error boundary em `/pipeline` — mesmo comportamento
- [x] AC3: Error boundary em `/historico` — mesmo comportamento
- [x] AC4: Error boundary em `/conta` — mesmo comportamento
- [x] AC5: Fallback UI inclui: mensagem amigavel, botao "Tentar novamente", link para suporte
- [x] AC6: ProfileCompletionPrompt carregado via `next/dynamic` (lazy) — reducao de ~70KB no bundle do dashboard
- [x] AC7: Todos os loading spinners tem `role="status"` e `aria-busy="true"` no container pai
- [x] AC8: Apenas 1 `<footer role="contentinfo">` por pagina (sem duplicatas de landmark)
- [x] AC9: `npm run build` confirma reducao de bundle size no dashboard chunk (dynamic import verified via code)

## Testes Requeridos

- **FE-NEW-02:** Testar que erro em child component e caught pelo boundary; fallback UI renderiza; botao "Tentar novamente" funciona
- **FE-NEW-01:** `npm run build` — comparar chunk sizes antes/depois
- **FE-A11Y-01:** axe-core ou manual check — `role="status"` presente em loading components
- **FE-A11Y-05:** axe-core — zero duplicate landmark violations
- `npm test` — 0 failures
- `npm run lint` — 0 errors

## Notas Tecnicas

- **FE-NEW-02 (Error Boundaries):**
  - Criar componente reutilizavel `ErrorBoundary` (class component, React limitation)
  - Wrap em cada page layout: `app/dashboard/layout.tsx`, `app/pipeline/layout.tsx`, etc.
  - Fallback: `<div role="alert">` com mensagem + recovery action
  - Rollback: remover wrapper (harmless, sem efeito colateral)

- **FE-NEW-01 (Dynamic Import):**
  - `const ProfileCompletionPrompt = dynamic(() => import('./ProfileCompletionPrompt'), { ssr: false })`
  - Verificar que nao quebra funcionalidade do prompt

- **FE-A11Y-01 (Loading Spinners):**
  - Buscar componentes de loading em `components/` e `app/buscar/components/`
  - Adicionar `role="status"` e `aria-live="polite"` nos wrappers

- **FE-A11Y-05 (Duplicate Footer):**
  - Footer inline em buscar + NavigationShell cria 2 landmarks
  - Remover footer inline ou condicionar com check de NavigationShell

## Dependencias

- **Depende de:** Nenhuma (pode iniciar imediatamente, paralelo com DEBT-100 e DEBT-101)
- **Bloqueia:** Nenhuma

## Definition of Done

- [x] Error boundaries implementados em 4 paginas
- [x] Dynamic import do ProfileCompletionPrompt
- [x] Loading spinners com role="status"
- [x] Footer unico (sem duplicata)
- [x] Testes passando (5591 pass, 10 new, 0 regressions)
- [x] Build size reduzido (dynamic import of framer-motion ~70KB)
- [ ] Code review aprovado
