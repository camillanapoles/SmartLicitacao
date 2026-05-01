# STORY-DEBT-5: Polish, Cleanup + DX Improvements

**Epic:** EPIC-DEBT-2026
**Batch:** 5
**Prioridade:** P3
**Estimativa:** 73h (46h continued improvement + 27h backlog polish)
**Agente:** @dev (implementacao) + @qa (validacao)

## Descricao

Batch final que consolida melhorias de medio e baixo impacto: decomposicao de modulos backend restantes (quota, search_cache, pncp_client), limpeza de dead code (ComprasGov, feature flags, compat shims), standardizacao de API proxies e Tailwind tokens no frontend, conversao RSC de paginas protegidas, e polish geral (skeletons, error boundaries, docs).

Items deste batch podem ser priorizados oportunisticamente -- nao precisam ser executados em bloco. Recomendacao: agrupar com feature work relacionado.

**Debt IDs (Continued Improvement):** DEBT-309, DEBT-306, TD-H01, TD-M01, TD-M05, DEBT-303, DEBT-315, DEBT-316, DEBT-317, DEBT-313, DEBT-314, DEBT-310
**Debt IDs (Backlog/Polish):** TD-L01, TD-L02, TD-L04, TD-L06, TD-L07, TD-H03, TD-NEW-03, DEBT-308, DEBT-319, DEBT-320, TD-L03, TD-L05, TD-M02, TD-M03, TD-M04, TD-M06, TD-M08

## Acceptance Criteria

### Backend Module Decomposition (14h)
- [ ] AC1 (DEBT-309): `quota.py` (1622 LOC) decomposto em `quota/plans.py`, `quota/rate_limiting.py`, `quota/trial.py`. Re-exports via `__init__.py`. Todos os testes de quota passam.
- [ ] AC2 (DEBT-306): `search_cache.py` (2512 LOC) decomposto em `cache/l1_memory.py`, `cache/l2_supabase.py`, `cache/swr.py`, `cache/key_generation.py`. Patch path `supabase_client.get_supabase` continua funcional para testes.
- [ ] AC3 (DEBT-303): `pncp_client.py` -- `import requests` removido, fallback sync eliminado. Client opera 100% via `httpx` async. `asyncio.to_thread()` wrapper removido.
- [ ] AC4 (DEBT-310): Backward-compat re-exports em `main.py` (linhas 82-102, ~75 linhas de proxy classes) removidos. Imports atualizados nos testes que dependiam deles.

### Dead Code + Config Cleanup (4h)
- [ ] AC5 (DEBT-313): ComprasGov v3 desabilitado no pipeline. Timeout budget nao desperdicado em source fora do ar. Config flag `COMPRASGOV_ENABLED=False` adicionada (ou source removida do pipeline).
- [ ] AC6 (DEBT-314): Inventario das 16 feature flags completo -- cada flag categorizada como: active (in use), candidate_removal (unused), deferred. Flags unused removidas.
- [ ] AC7 (DEBT-320): `track_legacy_routes()` compat shim em `main.py:82-102` removido (ou justificado se ainda necessario).

### Client Standardization (8h)
- [ ] AC8 (DEBT-317): 5 clients em `clients/` seguem estrutura consistente baseada em `base.py`. Todos usam `BaseClient` (ou pattern documentado para excecoes).
- [ ] AC9 (DEBT-315): API proxies que nao usam `create-proxy-route.ts` migrados para usar factory. Security header forwarding auditado e padronizado.

### Frontend Improvements (24h)
- [ ] AC10 (TD-H01): Protected pages que se beneficiam de RSC data fetching identificadas e migradas (pelo menos as 5 mais impactantes: dashboard, pipeline, historico, conta, planos).
- [ ] AC11 (TD-M01): Zero `any` types em `SavedSearchesDropdown`, `OrgaoFilter`, `MunicipioFilter`, `AnalyticsProvider`, `LoginForm`, `ErrorDetail`. `npx tsc --noEmit` passa limpo.
- [ ] AC12 (TD-M05): Raw CSS var usage (`bg-[var(--surface-0)]`) substituido por Tailwind tokens (`bg-surface-0`) -- zero instancias restantes.
- [ ] AC13 (DEBT-316): Onboarding (783 LOC) e signup (703 LOC) decompostos em subcomponentes (<300 LOC cada).

### Frontend Polish (27h -- backlog, oportunistico)
- [ ] AC14 (TD-L01): jest-axe instalado e configurado. Pelo menos 5 testes a11y nos componentes core (se nao feito no Batch 3).
- [ ] AC15 (TD-L02): Skeleton loading states adicionados em admin sub-pages, alertas, mensagens.
- [ ] AC16 (TD-L04): `error.tsx` criado para onboarding, signup, login (3 paginas).
- [ ] AC17 (TD-H03): aria-live announcements granulares para progresso SSE (ex: "UF Sao Paulo concluida, 5 de 27").
- [ ] AC18 (TD-NEW-03): Shepherd.js carregado via `next/dynamic` com `ssr: false`. Nao importado em paginas apos tour completo.
- [ ] AC19 (TD-M02): `ValorFilter.tsx` (478 LOC) decomposto: currency formatting separado, slider separado, presets separado.
- [ ] AC20 (TD-M03): `EnhancedLoadingProgress` (391 LOC) decomposto: multi-phase logic, UF grid, fallback em componentes separados.
- [ ] AC21 (TD-M04): `useFeatureFlags` refatorado para usar SWR ao inves de cache custom.
- [ ] AC22 (TD-M06): localStorage keys centralizados em `lib/storage-keys.ts` (ou similar). Zero magic strings.
- [ ] AC23 (TD-M08): `ProfileCompletionPrompt` (638 LOC) decomposto em subcomponentes.
- [ ] AC24 (TD-L06): Blog TODO placeholders resolvidos (60+ internal linking TODOs em 30 artigos).
- [ ] AC25 (TD-L07): Dependency graph dos 9 search hooks (3287 LOC) documentado.
- [ ] AC26 (DEBT-308): `api-types.generated.ts` (5177 LOC) verificado para tree-shaking. Unused types removidas se nao tree-shaken.
- [ ] AC27 (DEBT-319): Smoke tests adicionados no CI para `run_tests_safe.py` e `sync-setores-fallback.js`.
- [ ] AC28 (TD-L03): `useOnboarding.tsx` renomeado para `useOnboarding.ts` (hook sem JSX).
- [ ] AC29 (TD-L05): `TourInviteBanner` extraido de `SearchResults.tsx` para arquivo proprio.

## Tasks

### Backend Decomposition (14h)
- [ ] T1: Decompor `quota.py` em package `quota/` (4h)
- [ ] T2: Decompor `search_cache.py` em package `cache/` (4h)
- [ ] T3: Remover sync fallback de `pncp_client.py`, manter apenas httpx async (4h)
- [ ] T4: Remover backward-compat re-exports de `main.py` (2h)

### Cleanup (4h)
- [ ] T5: Desabilitar ComprasGov v3 no pipeline (1h)
- [ ] T6: Feature flag audit -- grep all 16 flags em FE + BE, categorizar, remove unused (2h)
- [ ] T7: Remover `track_legacy_routes()` (1h)

### Client Standardization (8h)
- [ ] T8: Standardizar 5 clients em `clients/` (4h)
- [ ] T9: Migrar API proxies para `create-proxy-route.ts` factory (4h)

### Frontend Core (24h)
- [ ] T10: Protected pages RSC migration (top 5) (10h)
- [ ] T11: Eliminar `any` types nos 6 arquivos listados (4h)
- [ ] T12: Tailwind token standardization -- replace raw CSS vars (3h)
- [ ] T13: Decompose onboarding + signup pages (4h)
- [ ] T14: Decompose ValorFilter, EnhancedLoadingProgress, ProfileCompletionPrompt (3h)

### Frontend Polish (27h -- oportunistico)
- [ ] T15: jest-axe setup + 5 a11y tests (4h)
- [ ] T16: Skeleton loading states (4h)
- [ ] T17: error.tsx for 3 pages (2h)
- [ ] T18: SSE aria-live granular announcements (2h)
- [ ] T19: Shepherd.js lazy load (2h)
- [ ] T20: useFeatureFlags -> SWR (2h)
- [ ] T21: localStorage registry (2h)
- [ ] T22: Blog TODO cleanup (4h)
- [ ] T23: Search hooks dependency docs (4h)
- [ ] T24: Minor fixes: api-types tree-shaking, CI smoke tests, useOnboarding rename, TourInviteBanner extract (5h)

## Testes Requeridos

- **Per-decomposition:** Full test suite apos cada module move
- **DEBT-309:** `pytest -k quota` -- all pass, re-exports work
- **DEBT-306:** `pytest -k cache` -- patch path `supabase_client.get_supabase` still works
- **DEBT-303:** `pytest -k pncp` -- async-only client works, no `import requests` in codebase
- **TD-H01:** `npm run build` -- RSC pages build successfully
- **TD-M01:** `npx tsc --noEmit` -- zero `any` in target files
- **TD-M05:** `grep -r "var(--" frontend/app/` -- zero raw CSS var usage
- **Full suite:** `python scripts/run_tests_safe.py --parallel 4` (7656), `npm test` (5733)

## Definition of Done

- [ ] All core ACs checked (AC1-AC13 mandatory, AC14-AC29 oportunistic)
- [ ] Tests pass (backend + frontend)
- [ ] No regressions
- [ ] Code reviewed
- [ ] TypeScript strict mode clean (`npx tsc --noEmit`)

## File List

### Backend
- `backend/quota.py` -> `backend/quota/` package
- `backend/search_cache.py` -> `backend/cache/` package
- `backend/pncp_client.py` (remove sync fallback)
- `backend/main.py` (remove compat shims)
- `backend/compras_gov_client.py` (disable or feature-flag)
- `backend/config.py` or `backend/config/features.py` (flag cleanup)
- `backend/clients/*.py` (standardization)

### Frontend
- `frontend/app/(protected)/*.tsx` (RSC migration)
- `frontend/app/buscar/components/ValorFilter.tsx` (decompose)
- `frontend/app/buscar/components/EnhancedLoadingProgress.tsx` (decompose)
- `frontend/components/ProfileCompletionPrompt.tsx` (decompose)
- `frontend/app/(marketing)/onboarding/page.tsx` (decompose)
- `frontend/app/(marketing)/signup/page.tsx` (decompose)
- `frontend/app/api/*.ts` (proxy standardization)
- `frontend/lib/storage-keys.ts` (new)

## Notas

- **Oportunistic execution:** Items neste batch nao precisam ser executados em sequencia. Agrupar com feature work: ex, ao trabalhar em feature de pipeline, resolver TD-L02 (skeletons) junto.
- **DEBT-303 (pncp_client sync removal)** e de medio risco: o fallback sync via `asyncio.to_thread()` existe como safety net. Remover apenas apos confirmar que httpx async e 100% estavel em producao por pelo menos 2 semanas.
- **DEBT-306 (search_cache decomp)** requer cuidado com patch paths em testes. A regra do CLAUDE.md (`supabase_client.get_supabase`, nao `search_cache.get_supabase`) DEVE ser preservada nos novos submodulos.
- **TD-H01 (protected RSC)** e independente de TD-M07 (landing RSC, Batch 2). Podem ser feitos em qualquer ordem.
- **Blog TODOs (TD-L06):** 60+ TODO placeholders em 30 artigos de blog. Pode ser feito por content writer, nao necessariamente dev.
- **Feature flag audit (DEBT-314):** Cross-reference FE e BE antes de remover. Uma flag pode parecer unused no BE mas ser lida no FE (ou vice-versa).
