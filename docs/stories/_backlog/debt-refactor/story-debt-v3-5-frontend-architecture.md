# Story: Frontend Architecture — Hooks + Auth + Directory Consolidation

**Story ID:** DEBT-v3-005
**Epic:** DEBT-v3
**Phase:** 2 (Foundation)
**Priority:** P1
**Estimated Hours:** 36h
**Agent:** @dev, @ux-design-expert (security review for FE-004)
**Status:** PLANNED

---

## Objetivo

Resolver os 3 debitos estruturais do frontend que afetam a manutenibilidade e seguranca: decompor o mega-hook `useSearchOrchestration` (369 LOC), unificar os 3 padroes divergentes de auth guard, e consolidar a estrutura de diretorios de componentes (51 files em `app/components/` vs 33 em `components/`).

---

## Debitos Cobertos

| ID | Debt | Severity | Hours |
|----|------|----------|-------|
| FE-002 | `useSearchOrchestration` mega-hook (369 LOC) — importa 15 hooks/modulos, orquestra trial state, modals, tours | HIGH | 16h |
| FE-004 | Auth guard patterns divergentes — `(protected)/layout.tsx` vs manual `useEffect` em `/buscar` | HIGH | 8h |
| FE-005 | Dual component directory — 51 files em `app/components/` vs 33 em `components/` | HIGH | 12h |
| CROSS-002 | Auth pattern divergence coordination (overhead) | HIGH | (included in FE-004) |

---

## Acceptance Criteria

### FE-002: useSearchOrchestration Decomposition (16h)
- [ ] AC1: `useSearchOrchestration` decomposto em sub-hooks: `useSearchModals` (~60 LOC), `useSearchTours` (~50 LOC), `useSearchBillingGuard` (~50 LOC), `usePdfGeneration` (~40 LOC)
- [ ] AC2: Compositor hook `useSearchOrchestration` reduzido a ~150 LOC (composes sub-hooks)
- [ ] AC3: API externa identica — nenhum componente consumidor precisa mudar
- [ ] AC4: `useSearchOrchestration*.test.ts` passam sem mudanca de asserts
- [ ] AC5: `search-resilience.test.tsx` passam sem mudanca

### FE-004: Auth Guard Unification (8h)
- [ ] AC6: Um unico padrao de auth enforcement para todas paginas protegidas
- [ ] AC7: `/buscar` usa o mesmo mecanismo que `(protected)/layout.tsx` (nao useEffect manual)
- [ ] AC8: Security review documentada antes da implementacao (current state audit)
- [ ] AC9: Security review documentada apos implementacao (verification)
- [ ] AC10: E2E tests com auth boundary checks (unauthenticated redirect, token expiry)
- [ ] AC11: Zero data exposure: paginas protegidas nao renderizam conteudo antes de auth check

### FE-005: Directory Consolidation (12h)
- [ ] AC12: Todos componentes compartilhados em `components/` (shared)
- [ ] AC13: Providers extraidos para `providers/` (infra)
- [ ] AC14: `app/components/` vazio e removido (ou contendo apenas page-specific components)
- [ ] AC15: jest.config.js `moduleNameMapper` atualizado se necessario
- [ ] AC16: Todos imports atualizados — `grep -r "app/components/" frontend/` retorna zero (exceto page-specific)
- [ ] AC17: TypeScript check limpo: `npx tsc --noEmit --pretty`

---

## Technical Notes

**FE-002 Decomposition strategy:**
- Extract `useSearchModals` first (isolated modal open/close state)
- Extract `useSearchTours` (Shepherd.js integration)
- Extract `useSearchBillingGuard` (trial/plan checks)
- Extract `usePdfGeneration` (PDF export logic)
- Compositor remains as orchestrator, delegating to sub-hooks
- External API (returned values) must be identical for zero-touch migration

**FE-004 Auth unification:**
- Three current enforcement points: middleware, route group layout, manual useEffect
- Target: single source of truth via middleware + route group layout
- `/buscar` has special case: allows unauthenticated access with limited features?
  - Verify current behavior before changing
  - If buscar allows anon access, guard only protected actions within the page
- CRITICAL: Security review BEFORE and AFTER changes. Document both.

**FE-005 Directory consolidation:**
- Step 1: Identify shared vs page-specific components in `app/components/`
- Step 2: Move shared to `components/`
- Step 3: Extract providers (SWRProvider, UserProvider, etc.) to `providers/`
- Step 4: Update all imports (automated find-and-replace)
- Step 5: Verify moduleNameMapper in jest.config.js (`@/` maps to `<rootDir>/`)
- CRITICAL: `@/` mapping must stay `<rootDir>/` (NOT `<rootDir>/app/`) — see MEMORY.md

---

## Tests Required

- [ ] `useSearchOrchestration*.test.ts` — all passing with identical assertions
- [ ] `search-resilience.test.tsx` — no regressions
- [ ] E2E auth boundary tests (new): unauthenticated redirect, token expiry, protected content
- [ ] Frontend full suite: `npm test` (5,733+ pass, 0 new failures)
- [ ] TypeScript check: `npx tsc --noEmit --pretty` clean
- [ ] Import audit: zero broken imports

---

## Dependencies

- **REQUIRES:** Nothing (independent of backend stories)
- **ENABLES:** DEBT-v3-007 (FE-010 mensagens decomposition benefits from clean directory structure)

---

## Definition of Done

- [ ] All ACs pass
- [ ] Frontend tests pass (zero regressions)
- [ ] TypeScript check clean
- [ ] Security review documented (before + after FE-004)
- [ ] E2E auth tests passing
- [ ] No lint errors
- [ ] Code reviewed
