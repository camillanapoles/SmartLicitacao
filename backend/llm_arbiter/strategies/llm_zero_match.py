"""Zero-density LLM strategy (<1% density) — single-bid zero-match (REF-VAL-002).

Wraps the single-bid zero-match arbiter call. Batch zero-match recovery
remains in ``llm_arbiter.zero_match`` (different code path: bulk YES/NO list
over many bids) and is not within the scope of this strategy.
"""

from __future__ import annotations

from typing import Optional

from llm_arbiter.strategies._base import (
    ClassificationStrategy,
    build_user_prompt,
    run_llm_classification,
)


class LLMZeroMatchStrategy(ClassificationStrategy):
    """Zero-match LLM prompt for very low keyword density (<1%)."""

    @property
    def name(self) -> str:
        return "zero_match"

    def classify(
        self,
        *,
        objeto: str,
        valor: float,
        setor_name: Optional[str] = None,
        termos_busca: Optional[list[str]] = None,
        setor_id: Optional[str] = None,
        search_id: str = "",
    ) -> dict:
        objeto_truncated = objeto[:500]
        user_prompt, mode, context = build_user_prompt(
            prompt_level=self.name,
            setor_name=setor_name,
            termos_busca=termos_busca,
            objeto_truncated=objeto_truncated,
            valor=valor,
            setor_id=setor_id,
            structured_enabled=True,
        )
        return run_llm_classification(
            user_prompt=user_prompt,
            mode=mode,
            context=context,
            objeto=objeto,
            valor=valor,
            objeto_truncated=objeto_truncated,
            prompt_level=self.name,
            setor_id=setor_id,
            search_id=search_id,
        )
