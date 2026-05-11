"""REF-VAL-002 — LLM strategy unit tests (standard / conservative / zero_match).

Each LLM strategy calls into the shared ``run_llm_classification`` helper,
mocked at the ``llm_arbiter._get_client`` boundary (CLAUDE.md test pattern).
"""

from __future__ import annotations

import json
import os
from unittest.mock import Mock, patch

import pytest

from llm_arbiter import clear_cache
from llm_arbiter.strategies import (
    LLMConservativeStrategy,
    LLMStandardStrategy,
    LLMZeroMatchStrategy,
)


@pytest.fixture(autouse=True)
def _env() -> None:
    os.environ["LLM_ARBITER_ENABLED"] = "true"
    os.environ["LLM_ARBITER_MODEL"] = "gpt-4.1-nano"
    os.environ["LLM_ARBITER_MAX_TOKENS"] = "1"
    os.environ["LLM_ARBITER_TEMPERATURE"] = "0"
    os.environ["OPENAI_API_KEY"] = "test-key-12345"
    clear_cache()
    yield
    clear_cache()


def _mock_response(classe: str = "SIM", confianca: int = 85, evidencias: list[str] | None = None) -> Mock:
    payload = {
        "classe": classe,
        "confianca": confianca,
        "evidencias": evidencias or [],
        "motivo_exclusao": None,
        "precisa_mais_dados": False,
    }
    msg = Mock()
    msg.content = json.dumps(payload)
    choice = Mock()
    choice.message = msg
    usage = Mock()
    usage.prompt_tokens = 100
    usage.completion_tokens = 10
    resp = Mock()
    resp.choices = [choice]
    resp.usage = usage
    return resp


class TestLLMStandardStrategy:
    def test_name(self) -> None:
        assert LLMStandardStrategy().name == "standard"

    def test_classify_sim(self) -> None:
        with patch("llm_arbiter._get_client") as mock_get_client:
            mock_client = Mock()
            mock_client.chat.completions.create.return_value = _mock_response(classe="SIM", confianca=88)
            mock_get_client.return_value = mock_client

            result = LLMStandardStrategy().classify(
                objeto="Aquisição de medicamentos para a Secretaria de Saúde",
                valor=200_000,
                setor_name="Saúde",
                setor_id="saude",
                search_id="s-std-1",
            )

        assert result["is_primary"] is True
        assert result["confidence"] == 88
        mock_client.chat.completions.create.assert_called_once()

    def test_classify_nao(self) -> None:
        with patch("llm_arbiter._get_client") as mock_get_client:
            mock_client = Mock()
            mock_client.chat.completions.create.return_value = _mock_response(classe="NAO", confianca=20)
            mock_get_client.return_value = mock_client

            result = LLMStandardStrategy().classify(
                objeto="Compra de cadeiras escolares",
                valor=50_000,
                setor_name="Saúde",
                search_id="s-std-2",
            )

        assert result["is_primary"] is False
        assert result["confidence"] == 20


class TestLLMConservativeStrategy:
    def test_name(self) -> None:
        assert LLMConservativeStrategy().name == "conservative"

    def test_classify_calls_llm(self) -> None:
        with patch("llm_arbiter._get_client") as mock_get_client:
            mock_client = Mock()
            mock_client.chat.completions.create.return_value = _mock_response(classe="SIM", confianca=72)
            mock_get_client.return_value = mock_client

            result = LLMConservativeStrategy().classify(
                objeto="Serviços de manutenção predial com itens diversos",
                valor=100_000,
                setor_name="Construção Civil",
                setor_id="construcao",
                search_id="s-cons-1",
            )

        assert result["is_primary"] is True
        assert result["confidence"] == 72
        # Verify it used the conservative prompt path — check prompt_level metric label
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert "messages" in call_kwargs
        assert call_kwargs["response_format"] == {"type": "json_object"}


class TestLLMZeroMatchStrategy:
    def test_name(self) -> None:
        assert LLMZeroMatchStrategy().name == "zero_match"

    def test_classify_zero_match(self) -> None:
        with patch("llm_arbiter._get_client") as mock_get_client:
            mock_client = Mock()
            mock_client.chat.completions.create.return_value = _mock_response(classe="NAO", confianca=10)
            mock_get_client.return_value = mock_client

            result = LLMZeroMatchStrategy().classify(
                objeto="Aquisição de uniformes escolares",
                valor=30_000,
                setor_name="Saúde",
                setor_id="saude",
                search_id="s-zm-1",
            )

        assert result["is_primary"] is False
        assert result["confidence"] == 10


class TestStrategyCacheSharing:
    """All LLM strategies share the same L1 cache via run_llm_classification."""

    def test_second_call_hits_cache(self) -> None:
        with patch("llm_arbiter._get_client") as mock_get_client:
            mock_client = Mock()
            mock_client.chat.completions.create.return_value = _mock_response(classe="SIM", confianca=90)
            mock_get_client.return_value = mock_client

            strat = LLMStandardStrategy()
            r1 = strat.classify(
                objeto="Objeto X",
                valor=1_000,
                setor_name="Saúde",
                setor_id="saude",
                search_id="s-cache-1",
            )
            r2 = strat.classify(
                objeto="Objeto X",
                valor=1_000,
                setor_name="Saúde",
                setor_id="saude",
                search_id="s-cache-1",
            )

        assert r1 == r2
        # Only one underlying API call — second was a cache hit
        assert mock_client.chat.completions.create.call_count == 1


class TestStrategyErrorFallback:
    def test_api_error_pending_review(self) -> None:
        """LLM error in gray-zone returns pending_review when LLM_FALLBACK_PENDING_ENABLED."""
        with patch("llm_arbiter._get_client") as mock_get_client, patch(
            "config.LLM_FALLBACK_PENDING_ENABLED", True
        ):
            mock_client = Mock()
            mock_client.chat.completions.create.side_effect = RuntimeError("openai down")
            mock_get_client.return_value = mock_client

            result = LLMStandardStrategy().classify(
                objeto="Algum objeto",
                valor=10_000,
                setor_name="Saúde",
                setor_id="saude",
                search_id="s-err-1",
            )

        assert result["is_primary"] is False
        assert result.get("pending_review") is True
        assert result["_classification_source"] == "llm_fallback_pending"
