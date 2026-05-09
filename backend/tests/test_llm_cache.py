"""Tests for LLM Redis cache layer (Issue #160).

Tests the get_or_generate_resumo_cached() async wrapper in llm.py, covering:
1. Cache hit — returns without calling OpenAI
2. Cache miss — calls gerar_resumo and stores result
3. Redis unavailable — transparent fallback to direct OpenAI call
4. Empty input — bypasses cache, returns fast fallback
5. Cache key stability — same inputs produce same key
6. Cache key uniqueness — different inputs produce different keys
"""

import hashlib
import json
import os
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from schemas import ResumoLicitacoes


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_LICITACOES = [
    {
        "objetoCompra": "Aquisição de uniformes escolares",
        "nomeOrgao": "Prefeitura de São Paulo",
        "uf": "SP",
        "municipio": "São Paulo",
        "valorTotalEstimado": 150_000.0,
        "dataAberturaProposta": "2026-06-01T10:00:00",
        "numeroControlePNCP": "12345678000195-1-000001/2026",
    },
    {
        "objetoCompra": "Serviços de limpeza",
        "nomeOrgao": "Câmara Municipal do Rio de Janeiro",
        "uf": "RJ",
        "municipio": "Rio de Janeiro",
        "valorTotalEstimado": 80_000.0,
        "dataAberturaProposta": "2026-06-15T14:00:00",
        "numeroControlePNCP": "99887766000144-1-000002/2026",
    },
]

MOCK_RESUMO = ResumoLicitacoes(
    resumo_executivo="Duas licitações encontradas em SP e RJ.",
    total_oportunidades=2,
    valor_total=230_000.0,
    destaques=["Prefeitura SP: R$ 150.000,00"],
    alerta_urgencia=None,
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Cache key helpers
# ─────────────────────────────────────────────────────────────────────────────


def test_build_resumo_cache_key_stable():
    """Same inputs must always produce the same key."""
    from llm import _build_resumo_cache_key

    key1 = _build_resumo_cache_key(SAMPLE_LICITACOES, "Limpeza", None, "limpeza")
    key2 = _build_resumo_cache_key(SAMPLE_LICITACOES, "Limpeza", None, "limpeza")
    assert key1 == key2
    assert key1.startswith("llm:summary:")


def test_build_resumo_cache_key_different_inputs():
    """Different sector_name must produce different keys."""
    from llm import _build_resumo_cache_key

    key_limpeza = _build_resumo_cache_key(SAMPLE_LICITACOES, "Limpeza", None, "limpeza")
    key_ti = _build_resumo_cache_key(SAMPLE_LICITACOES, "TI", None, "ti")
    assert key_limpeza != key_ti


def test_build_resumo_cache_key_different_bids():
    """Different bid lists must produce different keys."""
    from llm import _build_resumo_cache_key

    bids_a = [SAMPLE_LICITACOES[0]]
    bids_b = [SAMPLE_LICITACOES[1]]
    key_a = _build_resumo_cache_key(bids_a, "Limpeza", None, None)
    key_b = _build_resumo_cache_key(bids_b, "Limpeza", None, None)
    assert key_a != key_b


def test_build_resumo_cache_key_order_independent():
    """Key must be order-independent (sorted bid IDs)."""
    from llm import _build_resumo_cache_key

    key_normal = _build_resumo_cache_key(SAMPLE_LICITACOES, "X", None, None)
    reversed_lics = list(reversed(SAMPLE_LICITACOES))
    key_reversed = _build_resumo_cache_key(reversed_lics, "X", None, None)
    assert key_normal == key_reversed


def test_build_resumo_cache_key_no_stable_id():
    """Bids without any stable ID are skipped from key gracefully."""
    from llm import _build_resumo_cache_key

    bids_no_id = [
        {"objetoCompra": "Test", "uf": "SP"},
    ]
    key = _build_resumo_cache_key(bids_no_id, "Test", None, None)
    assert key.startswith("llm:summary:")


# ─────────────────────────────────────────────────────────────────────────────
# 2. Cache hit — returns without calling OpenAI
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-12345"})
async def test_cache_hit_skips_openai():
    """Cache hit must return cached resumo without calling OpenAI."""
    cached_json = MOCK_RESUMO.model_dump_json()

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=cached_json)

    with patch("llm.gerar_resumo") as mock_gerar:
        with patch("cache_module.redis_cache", mock_redis):
            from llm import get_or_generate_resumo_cached

            result = await get_or_generate_resumo_cached(
                SAMPLE_LICITACOES,
                sector_name="Limpeza",
                termos_busca=None,
                setor_id="limpeza",
            )

    mock_gerar.assert_not_called()
    assert isinstance(result, ResumoLicitacoes)
    assert result.resumo_executivo == MOCK_RESUMO.resumo_executivo


@pytest.mark.asyncio
@patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-12345"})
async def test_cache_hit_does_not_call_gerar_resumo_second_time():
    """Calling twice with same inputs — second call must hit cache and skip gerar_resumo."""
    cached_json = MOCK_RESUMO.model_dump_json()

    mock_redis = AsyncMock()
    # First call: miss; second call: hit
    mock_redis.get = AsyncMock(side_effect=[None, cached_json])
    mock_redis.setex = AsyncMock(return_value=True)

    with patch("llm.gerar_resumo", return_value=MOCK_RESUMO) as mock_gerar:
        with patch("cache_module.redis_cache", mock_redis):
            from llm import get_or_generate_resumo_cached

            await get_or_generate_resumo_cached(SAMPLE_LICITACOES, sector_name="Limpeza")
            await get_or_generate_resumo_cached(SAMPLE_LICITACOES, sector_name="Limpeza")

    # gerar_resumo should only be called once (first miss), not twice
    assert mock_gerar.call_count == 1


# ─────────────────────────────────────────────────────────────────────────────
# 3. Cache miss — calls OpenAI and stores result
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-12345"})
async def test_cache_miss_calls_openai_and_stores():
    """Cache miss must call gerar_resumo and store the result in Redis."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)  # Cache miss
    mock_redis.setex = AsyncMock(return_value=True)

    with patch("llm.gerar_resumo", return_value=MOCK_RESUMO) as mock_gerar:
        with patch("cache_module.redis_cache", mock_redis):
            from llm import get_or_generate_resumo_cached

            result = await get_or_generate_resumo_cached(
                SAMPLE_LICITACOES,
                sector_name="Limpeza",
                termos_busca=None,
                setor_id="limpeza",
            )

    mock_gerar.assert_called_once()
    mock_redis.setex.assert_called_once()
    # Verify TTL is 7 days
    _key, _ttl, _value = mock_redis.setex.call_args[0]
    assert _ttl == 7 * 24 * 3600
    assert _key.startswith("llm:summary:")
    assert isinstance(result, ResumoLicitacoes)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Redis unavailable — transparent fallback
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-12345"})
async def test_redis_unavailable_falls_back_to_openai():
    """When Redis raises, gerar_resumo is still called (no exception propagated)."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(side_effect=ConnectionError("Redis connection refused"))
    mock_redis.setex = AsyncMock(side_effect=ConnectionError("Redis connection refused"))

    with patch("llm.gerar_resumo", return_value=MOCK_RESUMO) as mock_gerar:
        with patch("cache_module.redis_cache", mock_redis):
            from llm import get_or_generate_resumo_cached

            result = await get_or_generate_resumo_cached(
                SAMPLE_LICITACOES,
                sector_name="Limpeza",
            )

    # OpenAI must be called even when Redis is down
    mock_gerar.assert_called_once()
    assert isinstance(result, ResumoLicitacoes)


@pytest.mark.asyncio
@patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-12345"})
async def test_redis_write_failure_does_not_raise():
    """A Redis write failure after successful OpenAI call must not propagate."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)  # Cache miss
    mock_redis.setex = AsyncMock(side_effect=TimeoutError("Redis timeout on SETEX"))

    with patch("llm.gerar_resumo", return_value=MOCK_RESUMO):
        with patch("cache_module.redis_cache", mock_redis):
            from llm import get_or_generate_resumo_cached

            # Must NOT raise even though Redis write fails
            result = await get_or_generate_resumo_cached(
                SAMPLE_LICITACOES,
                sector_name="Limpeza",
            )

    assert isinstance(result, ResumoLicitacoes)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Empty input — bypasses cache
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_empty_input_bypasses_cache():
    """Empty licitacoes list bypasses Redis entirely (fast path in gerar_resumo)."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)

    with patch("cache_module.redis_cache", mock_redis):
        from llm import get_or_generate_resumo_cached

        result = await get_or_generate_resumo_cached(
            [],
            sector_name="Limpeza",
        )

    # Redis should not be queried for empty input
    mock_redis.get.assert_not_called()
    assert isinstance(result, ResumoLicitacoes)
    assert result.total_oportunidades == 0


# ─────────────────────────────────────────────────────────────────────────────
# 6. Import module path uses cache_module.redis_cache singleton
# ─────────────────────────────────────────────────────────────────────────────


def test_cache_module_redis_cache_is_importable():
    """Ensure cache_module.redis_cache can be imported (basic smoke test)."""
    from cache_module import redis_cache  # noqa: F401

    assert redis_cache is not None
