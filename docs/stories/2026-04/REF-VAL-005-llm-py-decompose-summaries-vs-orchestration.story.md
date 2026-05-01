# REF-VAL-005: Decompose `llm.py` (638L → client/summaries/prompts)

**Priority:** P2
**Effort:** M (3 dias)
**Squad:** @architect + @dev
**Status:** Ready
**Epic:** [EPIC-TD-2026Q2](EPIC-TD-2026Q2/)
**Sprint:** Sprint 4
**Dependências bloqueadoras:** Mixpanel lib instalada (PR #536) — confirma observability

---

## Contexto

`backend/llm.py` 638L, 6 funções — wrapper LLM monolítico para exec summaries (`gerar_resumo`, `gerar_resumo_fallback`). Memory `project_mixpanel_lib_silent_2026_04_27` mostra: ARQ summary jobs depende de fallback path correto. Mistura: client init + fallback constants + prompt + schema (`ResumoLicitacoes`) + retry.

Distinto de `llm_arbiter/` (1926L, classification — REF-VAL-002 separate).

---

## Acceptance Criteria

### AC1: Estrutura alvo `backend/llm/`

- [ ] Criar package `backend/llm/`:
  ```
  backend/llm/
  ├── __init__.py        # façade re-export
  ├── client.py          # init/retry/cost tracking (~150L)
  ├── summaries.py       # gerar_resumo + fallback (~250L)
  ├── prompts/
  │   └── resumo.py      # template + variants (~150L)
  └── _types.py          # tipos shared (~60L)
  ```
- [ ] `llm.py` deletado (foi virou package)

### AC2: Schema preservation

- [ ] `ResumoLicitacoes` Pydantic schema permanece em `schemas/search.py` (já lá)
- [ ] Imports não mudam

### AC3: Façade

- [ ] `llm/__init__.py` re-export `gerar_resumo`, `gerar_resumo_fallback`
- [ ] Importadores externos não mudam

### AC4: Cost tracking

- [ ] `client.py` registra cost via `metrics.LLM_COST_TOTAL` (existing or new) per call
- [ ] Stack para LLM cost dashboard (US-021 Reversa user-stories.md)

### AC5: Tests

- [ ] `test_llm_client.py` (init/retry)
- [ ] `test_llm_summaries.py` (gerar_resumo + fallback paths)
- [ ] `test_llm_prompts_resumo.py` (template render)
- [ ] Cobertura ≥85%

---

## Scope

**IN:** package decomposition + cost tracking + tests
**OUT:** Migrate llm_arbiter/ (REF-VAL-002 separate) · Add new prompt variants

---

## Definition of Done

- [ ] Package criado, façade preserve API
- [ ] Cost tracking registered
- [ ] Tests pass cobertura ≥85%
- [ ] Suite passa
- [ ] @po validation GO

---

## Dev Notes

- `backend/llm.py:638L:6 funções`
- Pattern referência: `quota/` decomposition (TD-007), `cache/` decomposition
- LLM model: GPT-4.1-nano (CLAUDE.md)

---

## Risk & Rollback

| Trigger | Ação |
|---|---|
| Fallback path subtle break | Tests AC5 cobrem; rollback per-function |
| Imports circulares (client → summaries → prompts) | _types.py neutral module |

**Rollback:** revert PR; `llm.py` monolítico.

---

## Dependencies

**Entrada:** Nenhuma
**Saída:** habilita US-021 LLM cost dashboard refinement

---

## PO Validation

**Validated by:** @po (Pax)
**Date:** 2026-04-28
**Verdict:** GO
**Score:** 10/10

### 10-Point Checklist

| # | Criterion | ✓/✗ | Notes |
|---|-----------|-----|-------|
| 1 | Clear and objective title | ✓ | Decompose 638L explícito. |
| 2 | Complete description | ✓ | Distinção llm_arbiter (REF-VAL-002) clarificada. |
| 3 | Testable acceptance criteria | ✓ | 5 ACs com cobertura ≥85%. |
| 4 | Well-defined scope | ✓ | OUT exclude llm_arbiter migration. |
| 5 | Dependencies mapped | ✓ | Mixpanel lib PR #536. |
| 6 | Complexity estimate | ✓ | M (3d). |
| 7 | Business value | ✓ | Habilita US-021 LLM cost dashboard refinement. |
| 8 | Risks documented | ✓ | _types.py neutral module evita circular. |
| 9 | Criteria of Done | ✓ | 5 itens. |
| 10 | Alignment with PRD/Epic | ✓ | EPIC-TD-2026Q2 decomposition. |

Status: Draft → Ready.

---

## Change Log

| Data | Versão | Descrição | Autor |
|---|---|---|---|
| 2026-04-28 | 1.0 | Story criada via batch. Origem: `_reversa_sdd/sm-briefing-refactor.md` REF-VAL-005. | @sm (River) |
| 2026-04-28 | 1.1 | PO validation: GO (10/10). Status: Draft → Ready. | @po (Pax) |
