# REF-SCALE-005: `datalake_query.py` Query Builder Pattern (536L)

**Priority:** P3
**Effort:** M (3 dias)
**Squad:** @data-engineer + @dev
**Status:** Ready
**Epic:** [EPIC-TD-2026Q2](EPIC-TD-2026Q2/)
**Sprint:** Sprint 5
**Dependências bloqueadoras:** Nenhuma

---

## Contexto

`backend/datalake_query.py` 536L é builder SQL complexo sem padrão Builder. Funcionalmente OK (`search_datalake` RPC <100ms p95 confirma), mas evolução (adicionar filtro novo) requer modificar arquivo central. Pattern Builder tornaria extensível sem dor.

DataLake é fonte primária Layer 2 search (CLAUDE.md): `pncp_raw_bids` 1.5M rows + RPC `search_datalake`. Usado por `search_pipeline.py` quando `DATALAKE_QUERY_ENABLED=true` (default).

---

## Acceptance Criteria

### AC1: `datalake/query_builder.py`

- [ ] Criar package `backend/datalake/`:
  ```
  backend/datalake/
  ├── __init__.py
  ├── query_builder.py     # DatalakeQueryBuilder fluent API (~250L)
  ├── rpc_executor.py      # search_datalake RPC invocation (~150L)
  └── _types.py            # tipos shared (~80L)
  ```
- [ ] Fluent API:
  ```python
  query = (DatalakeQueryBuilder()
           .set_uf(["SP", "RJ"])
           .set_value_range(min=10000, max=500000)
           .set_keywords(["limpeza", "manutenção"])
           .set_modalidades([4, 5, 6])
           .set_date_window(days=10)
           .build())
  results = await execute_search_datalake(query)
  ```

### AC2: Backward compat

- [ ] `datalake_query.py` deleted; `from datalake_query import query_datalake` continua via shim (ou updated callsites)
- [ ] `search_pipeline.py::query_datalake()` consume new builder

### AC3: Tests

- [ ] `test_datalake_query_builder.py` — combinações filter
- [ ] `test_datalake_rpc_executor.py` — RPC mock
- [ ] Existing `test_datalake*.py` redistribuído
- [ ] Cobertura ≥85%

### AC4: Performance preserved

- [ ] Latency p95 <100ms (CLAUDE.md SLA)
- [ ] Baseline em `docs/perf/datalake-query-baseline-2026-04-28.md`
- [ ] Zero regression

---

## Scope

**IN:** Builder pattern + executor split + tests + benchmark
**OUT:** RPC schema changes · New filter types (separate stories) · search_datalake RPC modification

---

## Definition of Done

- [ ] Builder + executor + types split
- [ ] Tests pass cobertura ≥85%
- [ ] Performance preserved
- [ ] Suite passa
- [ ] @po validation GO

---

## Dev Notes

- `backend/datalake_query.py:536L`
- RPC `search_datalake` documentada `data-master.md`
- Padrão referência: builder fluent similar `pydantic.BaseModel.model_construct()` chains

---

## Risk & Rollback

| Trigger | Ação |
|---|---|
| Latency regride >5% | Profile lazy imports, optimize SQL build |
| Edge case filter combinação não cobre | Add to test suite + fix |

**Rollback:** revert PR; datalake_query.py monolítico.

---

## Dependencies

**Entrada:** Nenhuma
**Saída:** facilita stories futuras adicionar filtros sem tocar core

---

## PO Validation

**Validated by:** @po (Pax)
**Date:** 2026-04-28
**Verdict:** GO
**Score:** 10/10

### 10-Point Checklist

| # | Criterion | ✓/✗ | Notes |
|---|-----------|-----|-------|
| 1 | Clear and objective title | ✓ | Builder pattern + LOC explícito 536L. |
| 2 | Complete description | ✓ | <100ms p95 SLA referenciado. |
| 3 | Testable acceptance criteria | ✓ | 4 ACs com performance preserved. |
| 4 | Well-defined scope | ✓ | OUT exclude RPC schema changes. |
| 5 | Dependencies mapped | ✓ | Nenhuma. |
| 6 | Complexity estimate | ✓ | M (3d). |
| 7 | Business value | ✓ | Future filters sem dor. |
| 8 | Risks documented | ✓ | Profile + lazy imports se latency >5%. |
| 9 | Criteria of Done | ✓ | 5 itens. |
| 10 | Alignment with PRD/Epic | ✓ | EPIC-TD-2026Q2. |

P3 priority — defer aceitável; não blocker para sprint atual.

Status: Draft → Ready.

---

## Change Log

| Data | Versão | Descrição | Autor |
|---|---|---|---|
| 2026-04-28 | 1.0 | Story criada via batch. Origem: `_reversa_sdd/sm-briefing-refactor.md` REF-SCALE-005. | @sm (River) |
| 2026-04-28 | 1.1 | PO validation: GO (10/10). Status: Draft → Ready. P3 priority — defer aceitável. | @po (Pax) |
