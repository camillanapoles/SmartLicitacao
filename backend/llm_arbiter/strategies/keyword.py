"""High-density keyword strategy (>5% density) — no LLM call (REF-VAL-002).

When keyword density is high enough, the upstream filter pipeline has already
established sector match deterministically. We short-circuit without invoking
the LLM and return the legacy "keyword accept" payload (confidence=95, matching
the documented benchmark behaviour in ``test_llm_arbiter.py`` and the D-02
comment: "keyword=95, LLM=varies, zero_match<=70").
"""

from __future__ import annotations

import logging
from typing import Optional

from llm_arbiter.strategies._base import ClassificationStrategy

logger = logging.getLogger(__name__)


class KeywordStrategy(ClassificationStrategy):
    """High keyword density: accept without an LLM call."""

    @property
    def name(self) -> str:
        return "keyword"

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
        logger.debug(
            "REF-VAL-002 KeywordStrategy ACCEPT (no LLM) | "
            f"setor={setor_name} valor=R${valor:,.2f}"
        )
        return {
            "is_primary": True,
            "confidence": 95,
            "evidence": [],
            "rejection_reason": None,
            "needs_more_data": False,
            "_classification_source": "keyword",
        }
