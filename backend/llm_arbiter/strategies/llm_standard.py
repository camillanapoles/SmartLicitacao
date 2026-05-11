"""Standard-density LLM strategy (2-5% density) — REF-VAL-002."""

from __future__ import annotations

from typing import Optional

from llm_arbiter.strategies._base import (
    ClassificationStrategy,
    build_user_prompt,
    run_llm_classification,
)


class LLMStandardStrategy(ClassificationStrategy):
    """Standard LLM arbiter prompt for medium keyword density."""

    @property
    def name(self) -> str:
        return "standard"

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
