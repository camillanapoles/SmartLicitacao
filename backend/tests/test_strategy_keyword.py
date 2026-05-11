"""REF-VAL-002 — KeywordStrategy unit tests.

High-density keyword tier short-circuits: no LLM call, returns is_primary=True
with confidence=95.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from llm_arbiter.strategies import KeywordStrategy, get_strategy, select_strategy_by_density


class TestKeywordStrategyNoLLM:
    def test_name(self) -> None:
        assert KeywordStrategy().name == "keyword"

    def test_classify_does_not_call_llm(self) -> None:
        """KeywordStrategy must never invoke the OpenAI client."""
        with patch("llm_arbiter._get_client") as mock_client:
            result = KeywordStrategy().classify(
                objeto="Construção de escola pública municipal",
                valor=1_500_000,
                setor_name="Construção Civil",
                setor_id="construcao",
                search_id="search-abc",
            )
            mock_client.assert_not_called()

        assert result["is_primary"] is True
        assert result["confidence"] == 95
        assert result["evidence"] == []
        assert result["rejection_reason"] is None
        assert result["needs_more_data"] is False
        assert result["_classification_source"] == "keyword"

    def test_classify_with_termos_busca(self) -> None:
        result = KeywordStrategy().classify(
            objeto="Fornecimento de equipamentos médicos",
            valor=500_000,
            termos_busca=["equipamentos médicos", "hospitalar"],
            search_id="search-xyz",
        )
        assert result["is_primary"] is True
        assert result["confidence"] == 95


class TestStrategyRegistry:
    def test_get_strategy_by_name(self) -> None:
        assert get_strategy("keyword").name == "keyword"
        assert get_strategy("standard").name == "standard"
        assert get_strategy("conservative").name == "conservative"
        assert get_strategy("zero_match").name == "zero_match"

    def test_get_strategy_unknown_falls_back_to_standard(self) -> None:
        """Legacy default to standard for unknown prompt_level."""
        assert get_strategy("nonexistent").name == "standard"

    @pytest.mark.parametrize(
        "density,expected",
        [
            (0.10, "keyword"),       # >5%
            (0.06, "keyword"),       # >5%
            (0.05, "standard"),      # not > 5%, but > 2%
            (0.03, "standard"),      # 2-5%
            (0.02, "conservative"),  # not > 2%, but > 1%
            (0.015, "conservative"), # 1-2%
            (0.01, "zero_match"),    # not > 1%
            (0.005, "zero_match"),   # <1%
            (0.0, "zero_match"),
        ],
    )
    def test_select_strategy_by_density(self, density: float, expected: str) -> None:
        assert select_strategy_by_density(density).name == expected
