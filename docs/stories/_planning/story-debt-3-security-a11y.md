# STORY-DEBT-3: Stripe Webhook Decomposition + Accessibility Fixes

**Epic:** EPIC-DEBT-2026
**Batch:** 3
**Prioridade:** P1
**Estimativa:** 17h (+ 4h jest-axe pre-requisite from Batch 5, recommended to pull forward)
**Agente:** @dev (implementacao) + @qa (validacao)

## Descricao

Dois temas complementares de qualidade: (1) decompor o monolito de Stripe webhooks (1192 LOC, 10+ event types em uma handler function) para melhorar auditabilidade de billing, e (2) corrigir gaps de acessibilidade que bloqueiam expansao para clientes governamentais (WCAG 2.1 AA).

**Pre-requisito de Batch 0:** DEBT-324 (webhook audit) DEVE estar completo antes de iniciar DEBT-307. O audit informa se double-processing ocorreu e qual URL manter.

**Debt IDs:** DEBT-307, TD-H04, TD-NEW-02, TD-H02

## Acceptance Criteria

### Stripe Webhook Decomposition (DEBT-307)
- [ ] AC1: `webhooks/stripe.py` decomposto em handler functions separadas por event type (ex: `handle_checkout_session_completed()`, `handle_invoice_paid()`, `handle_customer_subscription_updated()`, etc.)
- [ ] AC2: Dispatcher function central roteia por `event.type` para handlers individuais
- [ ] AC3: Cada handler tem seu proprio test file ou test class com pelo menos 2 test cases (happy path + error)
- [ ] AC4: `pytest --cov=webhooks` mostra >90% coverage nos handlers
- [ ] AC5: Todos os testes existentes de webhook continuam passando sem modificacao (exceto import paths se necessario)

### Pipeline Screen Reader Announcements (TD-H04)
- [ ] AC6: `DndContext` no pipeline kanban recebe prop `accessibility` com custom announcements em portugues (ex: "Card {titulo} movido para coluna {destino}")
- [ ] AC7: Cards do pipeline tem `aria-roledescription="item ordenavel"` (ou equivalente em portugues)
- [ ] AC8: Teste Playwright a11y: Tab -> Space (pick up) -> Arrow (move) -> Space (drop) produz announcement visivel no accessibility tree

### Viability Badge Text Alternatives (TD-NEW-02)
- [ ] AC9: Viability badges renderizam texto alem de cor: "Alta", "Media", "Baixa" visivel no badge (nao apenas color coding)
- [ ] AC10: Badges passam WCAG 1.4.1 (informacao nao transmitida apenas por cor). Verificavel via axe-core scan com zero violations em `/buscar`.

### Unify /buscar Auth Pattern (TD-H02)
- [ ] AC11: `/buscar` usa o mesmo auth layout que outras paginas protegidas (via `(protected)/layout.tsx`)
- [ ] AC12: Header/nav consistente entre `/buscar` e demais paginas protegidas (dashboard, pipeline, historico)
- [ ] AC13: Duplicate `id="main-content"` resolvido como parte da unificacao de layout (complementa TD-NEW-01 do Batch 1)

## Tasks

### Pre-requisite (recomendado puxar do Batch 5)
- [ ] T0: Instalar `jest-axe` e configurar matchers em `jest.setup.js`. Criar 1 smoke test a11y para `/buscar` como baseline. (4h -- TD-L01)

### Webhook Decomposition
- [ ] T1: Criar estrutura `webhooks/handlers/` com um file por event type group: `checkout.py`, `invoice.py`, `subscription.py`, `payment_method.py`. (1h)
- [ ] T2: Extrair handler logic de `webhooks/stripe.py` para handlers individuais. Manter dispatcher central em `stripe.py`. (3h)
- [ ] T3: Adicionar testes unitarios para cada handler (2 cases minimo por handler). (2h)

### Accessibility Fixes
- [ ] T4: Adicionar `accessibility` prop ao `DndContext` no pipeline com announcements em portugues. Adicionar `aria-roledescription` nos cards. (2h)
- [ ] T5: Atualizar viability badges para incluir texto label alem da cor (Alta/Media/Baixa). Garantir contraste suficiente. (2h)
- [ ] T6: Unificar `/buscar` para usar `(protected)/layout.tsx`. Resolver inconsistencia de header/nav. (3h)
- [ ] T7: Run axe-core scan em `/buscar` e `/pipeline`. Zero critical/serious violations. (1h)

### Validation
- [ ] T8: Full test suite backend + frontend. Zero regressions. (1h)

## Testes Requeridos

- **DEBT-307:** `pytest --cov=webhooks` >90%. Replay all existing webhook tests. Per-handler unit tests (2+ cases each).
- **TD-H04:** Playwright a11y test: keyboard DnD produces screen reader announcement. `aria-roledescription` present on pipeline cards.
- **TD-NEW-02:** axe-core scan on `/buscar` -- zero violations for WCAG 1.4.1.
- **TD-H02:** Visual comparison: header/nav identical across `/buscar`, `/dashboard`, `/pipeline`.
- **Full suite:** `python scripts/run_tests_safe.py --parallel 4` (7656 pass), `npm test` (5733 pass)

## Definition of Done

- [ ] All ACs checked
- [ ] Webhook handlers individually tested with >90% coverage
- [ ] axe-core scan passes on /buscar and /pipeline
- [ ] Tests pass (backend + frontend + e2e)
- [ ] No regressions
- [ ] Code reviewed

## File List

### Webhook Decomposition
- `backend/webhooks/stripe.py` (decompose into dispatcher)
- `backend/webhooks/handlers/` (new directory)
- `backend/webhooks/handlers/__init__.py` (new)
- `backend/webhooks/handlers/checkout.py` (new)
- `backend/webhooks/handlers/invoice.py` (new)
- `backend/webhooks/handlers/subscription.py` (new)
- `backend/webhooks/handlers/payment_method.py` (new)
- `backend/tests/test_webhook_*.py` (new per-handler tests)

### Accessibility
- `frontend/app/pipeline/page.tsx` or `components/Pipeline*.tsx` (DndContext + aria)
- `frontend/app/buscar/components/ViabilityBadge.tsx` (text alternatives)
- `frontend/app/(protected)/layout.tsx` (unify /buscar auth)
- `frontend/app/buscar/layout.tsx` (merge into protected layout)

### jest-axe (if pulled forward from Batch 5)
- `frontend/jest.setup.js` (add jest-axe matchers)
- `frontend/package.json` (add jest-axe dependency)
- `frontend/__tests__/a11y/` (new a11y test directory)

## Notas

- **DEBT-324 MUST be complete** before starting DEBT-307. The audit findings from Batch 0 determine whether idempotency logic needs to be added to each new handler.
- **jest-axe setup (TD-L01)** is officially in Batch 5 but strongly recommended to pull into Batch 3 start. Without it, a11y fixes lack automated regression protection.
- **Webhook decomposition risk:** 1192 LOC with complex billing state transitions. Use `git stash` liberally. Commit after EACH handler extraction, not at the end.
- **Pipeline DnD a11y:** `@dnd-kit` has built-in `accessibility` prop on `DndContext`. The fix is adding the prop with Portuguese strings, not reimplementing keyboard support (which already works via `KeyboardSensor`).
- **Viability badge approach:** Add text label inside the badge component. Do NOT rely solely on `aria-label` -- sighted users with color blindness need visible text too.
