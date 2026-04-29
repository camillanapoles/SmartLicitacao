# Story: Polish Backlog (Opportunistic)

**Story ID:** DEBT-v3-008
**Epic:** DEBT-v3
**Phase:** 4 (Polish)
**Priority:** P3
**Estimated Hours:** 77h
**Agent:** @dev (backend + frontend), @data-engineer (DB items)
**Status:** PLANNED

---

## Objetivo

Resolver debitos de baixa severidade de forma oportunistica durante feature work relacionado. Nenhuma destes itens requer sprint dedicado — devem ser feitos quando o desenvolvedor ja esta trabalhando na area afetada. Todos sao LOW severity sem urgencia user-facing.

---

## Debitos Cobertos

### Backend Cleanup (~17h)

| ID | Debt | Severity | Hours |
|----|------|----------|-------|
| SYS-015 | Monorepo sem workspace tooling | MEDIUM | 8h |
| SYS-016 | Backward-compat shims em `main.py` | LOW | 2h |
| SYS-017 | Experimental clients sem uso ativo (portal_transparencia, querido_diario, licitaja, sanctions) | LOW | 4h |
| SYS-018 | Dual-hash transition em `auth.py` | LOW | 2h |
| SYS-019 | `search_cache.py` na root e 118 LOC re-export (remover apos DEBT-v3-004 SYS-005) | LOW | 1h |

### Database Polish (~12h)

| ID | Debt | Severity | Hours |
|----|------|----------|-------|
| DB-007 | `search_state_transitions.search_id` sem FK (CASCADE destruiria audit trail — usar retencao independente) | LOW | 1h |
| DB-012 | 8 dead plan catalog entries com `is_active=false` | LOW | 1h |
| DB-013 | `profiles.context_data` schema nao enforced no DB — adicionar CHECK `jsonb_typeof(context_data) = 'object'` | MEDIUM | 4h |
| DB-017 | Admin RLS subquery — PG faz cache dentro de statement, concern em 10K+ users (atualmente ~200) | LOW | 8h |
| DB-018 | `user_subscriptions.annual_benefits` coluna vestigial | LOW | 1h |

### Frontend Polish (~48h)

| ID | Debt | Severity | Hours |
|----|------|----------|-------|
| FE-011 | Potential `any` types em API proxy routes | LOW | 4h |
| FE-013 | Landmarks inconsistentes — minor `id` inconsistency | LOW | 2h |
| FE-015 | `prefers-reduced-motion` parcialmente nao resolvido — Framer Motion JS-driven animations na landing | LOW | 2h |
| FE-017 | Frontend feature gates hardcoded — `useFeatureFlags` hook existe mas DX concern | LOW | 3h |
| FE-019 | 60+ API proxy routes — consolidacao DX/maintenance | LOW | 6h |
| FE-021 | Inline SVGs vs lucide-react | LOW | 3h |
| FE-022 | Raw hex values vs semantic tokens | LOW | 4h |
| FE-023 | `/conta` redirect flash | LOW | 2h |
| FE-024 | Duplicate footers | LOW | 2h |
| FE-025 | RootLayout async para CSP nonce | LOW | 2h |
| FE-026 | SEO pages thin/duplicate content risk | LOW | 4h |
| FE-027 | SearchResults.tsx backward-compat re-exports | LOW | 1h |
| FE-029 | Focus order em BuscarModals + BottomNav overlay | LOW | 3h |
| FE-031 | Dashboard chart sparse para low-usage users | LOW | 3h |
| FE-032 | Pipeline empty state wordy | LOW | 1h |
| FE-035 | Chart colors nao colorblind-safe — paleta de 10 cores depende de matiz | LOW | 4h |
| FE-036 | Shepherd.js loaded eagerly em todas protected pages (~15KB) — wrap em `next/dynamic` | LOW | 2h |

---

## Acceptance Criteria

### Opportunistic Rules
- [ ] AC1: Cada item so e implementado quando o dev ja esta trabalhando na area afetada (nao como sprint dedicado)
- [ ] AC2: Items podem ser feitos em qualquer ordem
- [ ] AC3: Cada item committed individualmente com referencia ao debt ID no commit message

### Backend
- [ ] AC4: (SYS-015) Se implementado: monorepo workspace config (npm/pnpm workspaces ou similar)
- [ ] AC5: (SYS-016) Se implementado: backward-compat shims removidos de `main.py`
- [ ] AC6: (SYS-017) Se implementado: experimental clients movidos para `clients/experimental/` ou removidos com TODO
- [ ] AC7: (SYS-018) Se implementado: dual-hash removed, single hash function em `auth.py`
- [ ] AC8: (SYS-019) Se implementado: `search_cache.py` root file removido, imports diretos para `cache/`

### Database
- [ ] AC9: (DB-013) Se implementado: CHECK constraint `jsonb_typeof(context_data) = 'object'` adicionado
- [ ] AC10: (DB-018) Se implementado: `annual_benefits` column dropped (apos remover do backend model)
- [ ] AC11: (DB-012) Se implementado: dead plan entries documentados (nao necessariamente removidos — sem impacto de query)

### Frontend — Key Items
- [ ] AC12: (FE-015) Se implementado: `useReducedMotion()` do framer-motion aplicado nas landing page animations
- [ ] AC13: (FE-035) Se implementado: chart palette usa pattern + color (nao apenas hue) para colorblind safety
- [ ] AC14: (FE-036) Se implementado: Shepherd.js wrapped em `next/dynamic({ ssr: false })` com loading fallback
- [ ] AC15: (FE-019) Se implementado: API proxy routes consolidadas por dominio (buscar, admin, billing, user)

---

## Technical Notes

**SYS-017 (experimental clients):**
- `portal_transparencia_client.py` — token configurado e testado, mas limitado (requer `codigoOrgao`)
- `querido_diario_client.py`, `licitaja_client.py`, `sanctions_client.py` — no active usage
- Move to `clients/experimental/` with clear README explaining status

**FE-035 (colorblind-safe charts):**
- Current 10-color palette relies on hue differentiation
- Fix: add patterns (dashed, dotted, solid) + shape markers alongside colors
- Test with colorblind simulation (Chrome DevTools > Rendering > Emulate vision deficiency)

**FE-036 (Shepherd.js lazy load):**
```tsx
const ShepherdTour = dynamic(() => import('./ShepherdTour'), {
  ssr: false,
  loading: () => null // No loading skeleton needed for tour
});
```

**DB-017 (Admin RLS subquery):**
- Currently: subquery `auth.uid() IN (SELECT id FROM profiles WHERE is_admin OR is_master)` on every admin query
- Optimization: materialized view refreshed on role change, or session variable
- NOT urgent: PostgreSQL caches result within single statement; concern at 10K+ users
- Estimated 2-3 years away from threshold at current growth

---

## Tests Required

Per-item tests as implemented:
- [ ] Each item: component/unit test covering the change
- [ ] No regression in full suite
- [ ] TypeScript check clean for frontend items
- [ ] Schema audit for DB items

---

## Dependencies

- **REQUIRES:** DEBT-v3-004 (SYS-005 cache decomposition enables SYS-019)
- **NO hard dependencies** for most items — truly opportunistic

---

## Definition of Done

- [ ] Each implemented item passes its specific tests
- [ ] Full suite remains green
- [ ] Implemented items tracked with checkbox in this story
- [ ] Remaining items stay in backlog for future sprints
- [ ] Code reviewed per item
