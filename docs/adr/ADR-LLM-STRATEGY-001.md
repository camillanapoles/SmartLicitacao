---
id: ADR-LLM-STRATEGY-001
title: LLM Classification Strategy Pattern (REF-VAL-002)
status: Accepted
authors: [@architect, @dev]
date: 2026-05-12
deciders: [Tiago Sasaki]
---

# ADR-LLM-STRATEGY-001: LLM Classification Strategy Pattern (REF-VAL-002)

## Context

SmartLic's core differentiator is AI-driven sector classification of public bids. Each incoming bid must be classified as relevant or irrelevant to one of 20 defined sectors (defined in `backend/sectors_data.yaml`). Classification accuracy determines both user trust (precision >= 85%) and coverage (recall >= 70%).

Before the Strategy pattern refactor, all classification logic lived in a monolithic `classify_contract_primary_match` function in `backend/llm.py` (~800 LOC). This function contained:

- Keyword density scoring interleaved with LLM dispatch logic
- Three distinct prompt levels (standard, conservative, zero_match) handled via inline `if/elif/else`
- Cache management, token logging, and error fallback mixed with business logic
- No clean extension point for adding new classification tiers

The Reversa Architect analysis (2026-04-27, `_reversa_sdd/review-report.md`) flagged this as a godmodule candidate (REF-VAL-002) with a recommendation to adopt the **Strategy pattern**.

Three tiers drive the classification pipeline:

| Tier | Keyword Density | Method | Latency | Coverage Contribution |
|------|----------------|--------|---------|----------------------|
| Keyword | >5% density | Regex keyword match in `filter/keywords.py` | ~50ms | ~60% of classified bids |
| Standard | 2-5% density | GPT-4.1-nano sector prompt | ~2s | ~25% (cumulative ~85%) |
| Conservative | 1-2% density | GPT-4.1-nano conservative prompt | ~2s | ~5% (cumulative ~90%) |
| Zero-match | <1% density | GPT-4.1-nano deep analysis prompt | ~5s | ~5% (cumulative ~95%) |

The remaining ~5% of bids fall through to PENDING_REVIEW (manual classification) or REJECT (when `LLM_FALLBACK_PENDING_ENABLED=false`).

## Decision

1. **ClassificationStrategy ABC** (`backend/llm_arbiter/strategies/_base.py`): a plain ABC with a single abstract method `classify(objeto, valor, setor_name, termos_busca, setor_id, search_id) -> dict`. Each strategy encapsulates exactly one classification tier. The return dict mirrors the legacy `classify_contract_primary_match` shape so callers require zero changes.

2. **Four concrete strategies** in `backend/llm_arbiter/strategies/`:

   | Class | File | Tier | No LLM call? | Prompt builder |
   |-------|------|------|-------------|----------------|
   | `KeywordStrategy` | `keyword.py` | >5% density | Yes (pure regex) | N/A |
   | `LLMStandardStrategy` | `llm_standard.py` | 2-5% | No | `_build_standard_sector_prompt` |
   | `LLMConservativeStrategy` | `llm_conservative.py` | 1-2% | No | `_build_conservative_prompt` |
   | `LLMZeroMatchStrategy` | `llm_zero_match.py` | <1% | No | `_build_zero_match_prompt` |

3. **Strategy Registry** (`backend/llm_arbiter/strategies/__init__.py`):

   ```python
   STRATEGY_REGISTRY = {
       "keyword": KeywordStrategy,
       "standard": LLMStandardStrategy,
       "conservative": LLMConservativeStrategy,
       "zero_match": LLMZeroMatchStrategy,
   }
   ```

   Selection is driven by `select_strategy_by_density(density)` which maps keyword density scores to tiers. Callers can also use `get_strategy(name)` for explicit strategy selection.

4. **Shared LLM helper** (`run_llm_classification` in `_base.py`): factors out the cross-cutting machinery that all LLM-using strategies share:

   - L1 in-memory cache + L2 Redis cache (same cache key shape as pre-refactor)
   - Monthly budget cap short-circuit (`is_budget_exceeded_sync`)
   - OpenAI `chat.completions.create` call with structured JSON or binary SIM/NAO mode
   - Token logging and metrics (`LLM_DURATION`, `LLM_CALLS`, `ARBITER_CACHE_HITS`)
   - Error fallback: PENDING_REVIEW when `LLM_FALLBACK_PENDING_ENABLED=true`, hard REJECT otherwise

5. **Pipeline integration** (`backend/pipeline/stages/post_filter_llm.py`): the post-filter pipeline stage selects the strategy via density threshold, calls `classify()`, and routes the result. This decouples classification strategy selection from stage orchestration.

6. **Prompts remain centralized** in `backend/llm_arbiter/prompt_builder.py`. Strategies call `build_user_prompt()` which dispatches to the appropriate builder based on prompt_level. This separation ensures prompt changes don't require strategy changes and vice versa.

### Class hierarchy

```text
ClassificationStrategy (ABC)          # _base.py
├── KeywordStrategy                    # keyword.py — no LLM, pure keyword match
├── LLMStandardStrategy               # llm_standard.py — standard GPT-4.1-nano prompt
├── LLMConservativeStrategy           # llm_conservative.py — conservative prompt
└── LLMZeroMatchStrategy              # llm_zero_match.py — zero-match deep analysis
```

## Consequences

### Positive

- Each strategy is independently unit-testable without mocking LLM calls (KeywordStrategy needs no mocking at all).
- New classification tiers can be added by implementing a single new class and registering it — no changes to pipeline orchestration.
- The `run_llm_classification` helper ensures all LLM strategies share the same cache, budget, metrics, and error behavior. No divergence risk.
- Prompt engineering changes are isolated to `prompt_builder.py`; strategy code stays stable.
- The density-based selector (`select_strategy_by_density`) mirrors the upstream logic in `filter/pipeline.py`, keeping the tier boundaries consistent across the stack.
- Legacy callers via `llm_arbiter.classification` facade work unchanged — the Strategy pattern is an internal refactor with no API change.

### Negative / Risks

- **R1 (Low)**: Adding a strategy requires creating a new file, a new class, and registering it in `STRATEGY_REGISTRY` and `select_strategy_by_density`. Mitigation: documented in `__init__.py` module docstring; the pattern is simple enough that a future developer can follow it by example.
- **R2 (Low)**: The shared `run_llm_classification` helper is in `_base.py` but is not a method of `ClassificationStrategy` — it's a module-level function. This means a strategy could theoretically bypass it. Mitigation: all four concrete strategies use it; code review enforces this for new strategies.
- **R3 (Low)**: The `select_strategy_by_density` density thresholds (0.05, 0.02, 0.01) are hardcoded. If they drift from `filter/pipeline.py`, tiers become inconsistent. Mitigation: both files reference the same constants via a shared config import path.

### Neutral

- The legacy `classify_contract_primary_match` function in `llm_arbiter.classification` is preserved as a facade for backward compatibility. It creates the appropriate strategy internally and delegates. This allows gradual migration of callers.

## Alternatives Considered

| Alternative | Why rejected |
|-------------|--------------|
| **Template Method pattern** | Strategies are independent algorithms, not lifecycle stages. Forcing them into a template (preprocess -> classify -> postprocess) adds indirection without benefit. |
| **Single classification function with config flags** | This was the pre-refactor state and caused the godmodule problem. Adding a new tier required modifying an 800-LOC function. |
| **File per density tier without ABC** | Without the ABC, nothing enforces that each tier returns the same dict shape. A divergence between tiers would silently break callers. |
| **External ML model for keyword tier** | Over-engineered for the keyword tier — regex matching achieves >95% precision at near-zero cost. The LLM is reserved for ambiguous cases. |
| **RFC-based prompt routing** | Evaluating every bid through all tiers and picking the best match would cost 4x LLM calls. Sequential gating (keyword -> standard -> conservative -> zero_match) minimizes LLM cost. |

## References

- ADR-ARCH-001 §3.1 — Strategy pattern canonical reference
- `backend/llm_arbiter/strategies/_base.py` — ClassificationStrategy ABC
- `backend/llm_arbiter/strategies/__init__.py` — STRATEGY_REGISTRY
- `backend/llm_arbiter/strategies/keyword.py` — KeywordStrategy
- `backend/llm_arbiter/strategies/llm_standard.py` — LLMStandardStrategy
- `backend/llm_arbiter/strategies/llm_conservative.py` — LLMConservativeStrategy
- `backend/llm_arbiter/strategies/llm_zero_match.py` — LLMZeroMatchStrategy
- `backend/pipeline/stages/post_filter_llm.py` — Pipeline integration
- `backend/llm_arbiter/prompt_builder.py` — Centralized prompt builders
- `backend/sectors_data.yaml` — 20 sector definitions
- Issue REF-VAL-002 — Godmodule split for keywords + LLM arbiter
