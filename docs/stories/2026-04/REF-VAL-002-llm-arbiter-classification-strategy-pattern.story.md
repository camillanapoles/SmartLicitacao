# REF-VAL-002: Strategy Pattern em `llm_arbiter/classification.py` (648L)

**Priority:** P2
**Effort:** M (3-5 dias)
**Squad:** @architect + @dev
**Status:** Ready
**Epic:** [EPIC-TD-2026Q2](EPIC-TD-2026Q2/)
**Sprint:** Sprint 4
**Dependências bloqueadoras:** Benchmark precision/recall ≥85%/≥70% test suite estável

---

## Contexto

`backend/llm_arbiter/classification.py` 648L concentra arbiter logic. Branching por keyword density tier:

- >5% density → "keyword" (no LLM call)
- 2-5% → "llm_standard"
- 1-2% → "llm_conservative"
- <1% → "llm_zero_match" (GPT-4.1-nano YES/NO)

Adicionar novo tier exige modificar arquivo central. Strategy pattern desacopla; permite A/B test prompts (memory hint: experimentação ativa).

`llm_arbiter/` 1926L total: classification.py 648, prompt_builder.py 378, batch_api.py 276, zero_match.py 289.

---

## Acceptance Criteria

### AC1: ABC `ClassificationStrategy`

- [ ] `backend/llm_arbiter/strategies/_base.py`:
  ```python
  from abc import ABC, abstractmethod
  
  class ClassificationStrategy(ABC):
      @abstractmethod
      async def classify(self, bid: BidPayload, ctx: SearchContext) -> ClassificationResult: ...
      
      @property
      @abstractmethod
      def name(self) -> str: ...
  ```

### AC2: 4 strategies

- [ ] `llm_arbiter/strategies/keyword.py` — high-density (>5%) — sem LLM call
- [ ] `llm_arbiter/strategies/llm_standard.py` — 2-5% density
- [ ] `llm_arbiter/strategies/llm_conservative.py` — 1-2% density
- [ ] `llm_arbiter/strategies/llm_zero_match.py` — 0-1% (zero-match) — current `zero_match.py:289L` migra ou re-exporta

### AC3: Dispatcher refactor `classification.py`

- [ ] Reduzir para ~200L: density tier → strategy lookup
- [ ] `classification.py::classify_bid()` torna router minimalista:
  ```python
  density = compute_density(bid, ctx.keywords)
  strategy = _select_strategy(density)
  return await strategy.classify(bid, ctx)
  ```

### AC4: Prompts ficam em `prompt_builder.py`

- [ ] Cada strategy LLM consome prompts via `prompt_builder.py:_build_*_prompt`
- [ ] `prompt_builder.py` permanece centralizado (não duplicar)

### AC5: Benchmark precision/recall PRESERVADO

- [ ] `backend/tests/test_llm_arbiter_benchmark.py` 15 samples/sector continua passando
- [ ] Precision ≥85%, recall ≥70% (CLAUDE.md SLA)
- [ ] Compare pré/pós split: zero diff em verdict per bid

### AC6: Tests

- [ ] `test_strategy_<name>.py` for each strategy
- [ ] Mock LLM client patched at `_get_client` level (CLAUDE.md test pattern)
- [ ] Cobertura ≥85%

---

## Scope

**IN:** ABC + 4 strategies + dispatcher refactor + tests + benchmark preservation
**OUT:** Add new strategies (separate stories) · A/B test framework (separate)

---

## Definition of Done

- [ ] 4 strategies + ABC criados
- [ ] Benchmark precision/recall preserved
- [ ] Tests pass + cobertura ≥85%
- [ ] Suite passa
- [ ] @po validation GO

---

## Dev Notes

- `llm_arbiter/classification.py:648L`, `prompt_builder.py:378L`, `batch_api.py:276L`, `zero_match.py:289L`
- Pattern referência: REF-MON-002 webhook ABC (mesma estrutura)
- LLM model: GPT-4.1-nano (CLAUDE.md)

---

## Risk & Rollback

| Trigger | Ação |
|---|---|
| Precision/recall regride pós-split | Per-strategy benchmark; identificar prompt pequenas mudanças |
| LLM client init duplicado em strategies | _base.py compartilha `_get_client` lazy |

**Rollback:** revert PR; classification.py monolítico restaurado.

---

## Dependencies

**Entrada:** Nenhuma
**Saída:** facilita stories futuras adicionar tiers/prompts sem tocar core

---

## PO Validation

**Validated by:** @po (Pax)
**Date:** 2026-04-28
**Verdict:** GO
**Score:** 10/10

### 10-Point Checklist

| # | Criterion | ✓/✗ | Notes |
|---|-----------|-----|-------|
| 1 | Clear and objective title | ✓ | Strategy pattern + LOC explícito 648L. |
| 2 | Complete description | ✓ | 4 tiers documentados + benchmark SLA referenciado. |
| 3 | Testable acceptance criteria | ✓ | 6 ACs com benchmark precision ≥85% recall ≥70% preserve. |
| 4 | Well-defined scope | ✓ | OUT exclude A/B test framework. |
| 5 | Dependencies mapped | ✓ | Benchmark suite estável. |
| 6 | Complexity estimate | ✓ | M (3-5d). |
| 7 | Business value | ✓ | Future tier additions sem touch core. |
| 8 | Risks documented | ✓ | Per-strategy benchmark identifica regression. |
| 9 | Criteria of Done | ✓ | 5 itens com benchmark preservation. |
| 10 | Alignment with PRD/Epic | ✓ | EPIC-TD-2026Q2 strategy pattern. |

Status: Draft → Ready.

---

## Change Log

| Data | Versão | Descrição | Autor |
|---|---|---|---|
| 2026-04-28 | 1.0 | Story criada via batch. Origem: `_reversa_sdd/sm-briefing-refactor.md` REF-VAL-002. | @sm (River) |
| 2026-04-28 | 1.1 | PO validation: GO (10/10). Status: Draft → Ready. | @po (Pax) |
