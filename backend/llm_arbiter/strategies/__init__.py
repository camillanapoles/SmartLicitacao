"""Classification strategies package (REF-VAL-002).

Strategy pattern for LLM arbiter classification. Each strategy encapsulates
one density tier:

  - KeywordStrategy        — high keyword density (>5%), no LLM call
  - LLMStandardStrategy    — medium density (2-5%), standard LLM prompt
  - LLMConservativeStrategy — low density (1-2%), conservative LLM prompt
  - LLMZeroMatchStrategy   — zero density (<1%), zero-match LLM prompt

Prompts remain centralized in ``llm_arbiter.prompt_builder``. Strategies
only orchestrate prompt selection, LLM call, cache, and parsing.

Public entry points live in ``llm_arbiter.classification`` (back-compat).
"""

from llm_arbiter.strategies._base import ClassificationStrategy
from llm_arbiter.strategies.keyword import KeywordStrategy
from llm_arbiter.strategies.llm_standard import LLMStandardStrategy
from llm_arbiter.strategies.llm_conservative import LLMConservativeStrategy
from llm_arbiter.strategies.llm_zero_match import LLMZeroMatchStrategy


# Registry by canonical name. Mirrors the ``prompt_level`` string used by
# upstream callers in ``filter/pipeline.py`` and ``jobs/queue/jobs.py``.
STRATEGY_REGISTRY: dict[str, type[ClassificationStrategy]] = {
    "keyword": KeywordStrategy,
    "standard": LLMStandardStrategy,
    "conservative": LLMConservativeStrategy,
    "zero_match": LLMZeroMatchStrategy,
}


def get_strategy(name: str) -> ClassificationStrategy:
    """Look up and instantiate a strategy by name.

    Falls back to LLMStandardStrategy on unknown name to preserve the
    legacy "default to standard" behaviour of ``classify_contract_primary_match``.
    """
    cls = STRATEGY_REGISTRY.get(name, LLMStandardStrategy)
    return cls()


def select_strategy_by_density(density: float) -> ClassificationStrategy:
    """Pick a strategy from a keyword-density score.

    Tiers mirror the upstream logic in ``filter/pipeline.py`` so callers that
    have not yet adopted ``prompt_level`` can still use this helper.

      - density > 0.05 → KeywordStrategy
      - 0.02 < density ≤ 0.05 → LLMStandardStrategy
      - 0.01 < density ≤ 0.02 → LLMConservativeStrategy
      - density ≤ 0.01 → LLMZeroMatchStrategy
    """
    if density > 0.05:
        return KeywordStrategy()
    if density > 0.02:
        return LLMStandardStrategy()
    if density > 0.01:
        return LLMConservativeStrategy()
    return LLMZeroMatchStrategy()


__all__ = [
    "ClassificationStrategy",
    "KeywordStrategy",
    "LLMStandardStrategy",
    "LLMConservativeStrategy",
    "LLMZeroMatchStrategy",
    "STRATEGY_REGISTRY",
    "get_strategy",
    "select_strategy_by_density",
]
