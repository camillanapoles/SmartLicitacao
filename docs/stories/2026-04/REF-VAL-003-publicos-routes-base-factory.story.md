# REF-VAL-003: Backend `routes/*_publicos.py` Base Factory (2581L → ~1500L)

**Priority:** P1
**Effort:** L (5-7 dias)
**Squad:** @architect + @dev
**Status:** Ready
**Epic:** [EPIC-SEO-PROG-2026-Q2](EPIC-SEO-PROG-2026-Q2.md) ou [EPIC-RES-BE-2026-Q2](EPIC-RES-BE-2026-Q2.md)
**Sprint:** Sprint 3-4
**Dependências bloqueadoras:** [RES-BE-001](RES-BE-001-audit-execute-without-budget.md) (CI gate ativo) · [RES-BE-002](RES-BE-002-budget-top5-routes.md) (top-5 cobertos)

---

## Contexto

6 routers `routes/*_publicos.py`:

| Arquivo | LOC |
|---------|-----|
| `contratos_publicos.py` | 801 (god-route, 11 funções) |
| `municipios_publicos.py` | 538 |
| `itens_publicos.py` | 522 |
| `compliance_publicos.py` | 289 |
| `dados_publicos.py` | 282 |
| `alertas_publicos.py` | 149 |
| **Total** | **2581** |

Pattern idêntico: fetch DB → filter → serialize JSON. 5 menores podem instanciar factory; `contratos_publicos.py` precisa split adicional.

Drive SEO orgânico inbound (10k+ programmatic pages). Memory `project_sitemap_endpoints_wedge_2026_04_27`: TODA classe de endpoints DB-bound tinha mesmo antipattern (sync `.execute()` em handler async sem budget+negative cache). PR #535 fixou 6 sitemap routers — *_publicos próximo target.

Distinção vs EPIC-SEO-PROG (frontend SSR→ISR) : esta story refatora **backend routers**; SEO-PROG-001..005 cobrem **frontend page.tsx**. Complementam.

---

## Acceptance Criteria

### AC1: `_publicos_base.py` factory

- [ ] `backend/routes/_publicos_base.py` (novo, ~250L):
  ```python
  from typing import Callable, Awaitable
  
  def create_publicos_router(
      *,
      entity_type: str,          # "municipios", "itens", etc.
      fetcher: Callable[..., Awaitable],
      filter_schema: BaseModel,
      serializer: Callable,
      budget_s: float = 10.0,
      negative_ttl_s: int = 60,
  ) -> APIRouter:
      router = APIRouter()
      @router.get(f"/v1/{entity_type}/{{slug}}")
      @with_budget_and_negative_cache(budget_s, negative_ttl_s)
      async def get_entity(slug: str, filters: filter_schema = Depends()):
          data = await fetcher(slug, filters)
          return serializer(data)
      return router
  ```
- [ ] Decorator `@with_budget_and_negative_cache` reusa pattern de RES-BE-002 + RES-BE-003

### AC2: Migrate 5 routers menores

- [ ] `municipios_publicos.py` → `municipios_router = create_publicos_router(entity_type="municipios", ...)` ~50L
- [ ] `itens_publicos.py` → similar
- [ ] `compliance_publicos.py` → similar
- [ ] `dados_publicos.py` → similar
- [ ] `alertas_publicos.py` → similar
- [ ] Cada arquivo reduz para ~50-100L (config + factory invocation)

### AC3: `contratos_publicos.py` split adicional

- [ ] Split em sub-routers por endpoint cluster:
  - `contratos_publicos/by_cnpj.py` (~200L)
  - `contratos_publicos/by_setor.py` (~200L)
  - `contratos_publicos/agg.py` (aggregations) (~250L)
  - `contratos_publicos/__init__.py` (façade re-export ~30L)
- [ ] Cada sub-router pode usar factory ou custom (depende complexity)

### AC4: Apply async + budget + negative cache pattern

- [ ] Todos endpoints com `await asyncio.to_thread(...)` em `.execute()`
- [ ] Budget temporal aplicado via decorator
- [ ] Negative cache aplicado em failure path (cobre RES-BE-003 part of 41 routes)

### AC5: Tests

- [ ] `test_publicos_base.py` (novo) — factory tests
- [ ] `test_<entity>_publicos.py` — per-entity tests preserved
- [ ] Cobertura ≥85%
- [ ] E2E Playwright SEO bot smoke (similar pattern em CLAUDE.md Spec Impact Matrix)

### AC6: Performance benchmark

- [ ] Pre-split baseline registrado em `docs/perf/publicos-routes-baseline-2026-04-28.md`
- [ ] Pós-split: latency p95 mantida (factory deve ter zero-overhead vs inline router)

---

## Scope

**IN:** factory + migrate 5 routers + split contratos_publicos + apply pattern + tests + benchmark
**OUT:** Frontend SSR→ISR migration (EPIC-SEO-PROG-001..005 separate) · New entity types

---

## Definition of Done

- [ ] Factory + 5 migrations + contratos_publicos split
- [ ] async pattern + budget + negative cache aplicados todos endpoints
- [ ] Tests pass + cobertura ≥85%
- [ ] Performance benchmark pass
- [ ] Suite passa
- [ ] @po validation GO

---

## Dev Notes

- `routes/contratos_publicos.py:801L:11 funções`
- Padrão referência: `pipeline/budget.py:_run_with_budget` + `cache/negative_cache.py` (criado em RES-BE-003)
- Memory `feedback_supabase_disk_io_root_cause_pattern`: 3 sintomas convergentes — esta story resolve 6 endpoints da classe
- Memory `project_backend_outage_2026_04_27` Stage 2: cascade prevention via budget + negative cache

---

## Risk & Rollback

| Trigger | Ação |
|---|---|
| Factory abstract demais para edge case | Per-entity custom router (não usa factory) — preserve flexibility |
| Performance degrada via decorator overhead | Profile + lazy import; rollback decorator if >5% latency |
| SEO crawler cache stale após pattern change | revalidate=3600 ISR alignment (memory `project_sitemap_serialize_isr_pattern`) |

**Rollback:** revert PR; routers monolíticos restaurados.

---

## Dependencies

**Entrada:** RES-BE-001+002+003 (CI gate, budget, negative cache foundation)
**Saída:** habilita SEO-PROG-001..005 frontend ISR migration (backend protegido) · habilita REF-SCALE-004 sitemap factory (similar pattern reuso)

---

## PO Validation

**Validated by:** @po (Pax)
**Date:** 2026-04-28
**Verdict:** GO
**Score:** 10/10

### 10-Point Checklist

| # | Criterion | ✓/✗ | Notes |
|---|-----------|-----|-------|
| 1 | Clear and objective title | ✓ | Backend factory + LOC explícito 2581L→1500L. |
| 2 | Complete description | ✓ | 6 routers tabulados + distinção EPIC-SEO-PROG (frontend) clarificada. |
| 3 | Testable acceptance criteria | ✓ | 6 ACs com factory test + benchmark + E2E SEO smoke. |
| 4 | Well-defined scope | ✓ | OUT exclude frontend SSR→ISR (SEO-PROG separate). |
| 5 | Dependencies mapped | ✓ | RES-BE-001 + RES-BE-002 foundation. |
| 6 | Complexity estimate | ✓ | L (5-7d) coerente vs LOC scope. |
| 7 | Business value | ✓ | LOC saving + drive SEO inbound resilience. |
| 8 | Risks documented | ✓ | Per-entity custom override se factory abstract demais. |
| 9 | Criteria of Done | ✓ | 6 itens com performance benchmark. |
| 10 | Alignment with PRD/Epic | ✓ | EPIC-SEO-PROG ou EPIC-RES-BE — @sm decide placement. |

Status: Draft → Ready.

---

## Change Log

| Data | Versão | Descrição | Autor |
|---|---|---|---|
| 2026-04-28 | 1.0 | Story criada via batch. Origem: `_reversa_sdd/sm-briefing-refactor.md` REF-VAL-003. | @sm (River) |
| 2026-04-28 | 1.1 | PO validation: GO (10/10). Status: Draft → Ready. | @po (Pax) |
