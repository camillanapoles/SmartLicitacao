"""Tests for Datalake API Self-Service (#1372)."""

from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from routes.datalake_api import (
    _check_feature_flag,
    _generate_api_key,
    _now_iso,
    API_KEY_PREFIX,
)
from schemas.datalake_api import (
    ApiKeyCreateRequest,
    ApiKeyCreateResponse,
    ApiKeyListItem,
    ApiKeyListResponse,
    ApiKeyRevokeResponse,
    ApiSearchParams,
)


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestApiKeyCreateRequest:
    def test_default_name_empty(self):
        req = ApiKeyCreateRequest()
        assert req.name == ""

    def test_with_name(self):
        req = ApiKeyCreateRequest(name="minha-key")
        assert req.name == "minha-key"

    def test_name_max_length(self):
        req = ApiKeyCreateRequest(name="a" * 100)
        assert len(req.name) == 100


class TestApiSearchParams:
    def test_minimal_valid(self):
        params = ApiSearchParams(q="material escritorio")
        assert params.q == "material escritorio"
        assert params.pagina == 1
        assert params.tamanho == 20

    def test_with_all_fields(self):
        params = ApiSearchParams(
            q="obras engenharia",
            uf="SC",
            data_inicial="2026-01-01",
            data_final="2026-06-03",
            modalidade="5,6",
            valor_min=10000.0,
            valor_max=500000.0,
            pagina=2,
            tamanho=50,
        )
        assert params.uf == "SC"
        assert params.modalidade == "5,6"
        assert params.valor_min == 10000.0
        assert params.pagina == 2
        assert params.tamanho == 50

    def test_q_too_short(self):
        with pytest.raises(ValueError):
            ApiSearchParams(q="a")

    def test_pagina_out_of_range(self):
        with pytest.raises(ValueError):
            ApiSearchParams(q="test query", pagina=0)

        with pytest.raises(ValueError):
            ApiSearchParams(q="test query", pagina=101)


# ---------------------------------------------------------------------------
# Key generation
# ---------------------------------------------------------------------------


class TestGenerateApiKey:
    def test_format(self):
        plaintext, key_hash = _generate_api_key()
        assert plaintext.startswith(API_KEY_PREFIX)
        assert len(plaintext) == len(API_KEY_PREFIX) + 64  # sk_ + 64 hex

    def test_hash_matches(self):
        plaintext, key_hash = _generate_api_key()
        expected = hashlib.sha256(plaintext.encode()).hexdigest()
        assert key_hash == expected

    def test_uniqueness(self):
        keys = [_generate_api_key()[0] for _ in range(10)]
        assert len(set(keys)) == 10


# ---------------------------------------------------------------------------
# Feature flag
# ---------------------------------------------------------------------------


class TestFeatureFlag:
    def test_flag_off_raises_503(self):
        with patch("routes.datalake_api.API_SELF_SERVICE_ENABLED", False):
            with pytest.raises(Exception) as exc_info:
                _check_feature_flag()
            assert exc_info.value.status_code == 503

    def test_flag_on_passes(self):
        with patch("routes.datalake_api.API_SELF_SERVICE_ENABLED", True):
            _check_feature_flag()  # should not raise


# ---------------------------------------------------------------------------
# Response schema validation
# ---------------------------------------------------------------------------


class TestApiKeyCreateResponse:
    def test_serialization(self):
        resp = ApiKeyCreateResponse(
            id="uuid-1",
            key="sk_abc123",
            name="test-key",
            created_at="2026-06-03T00:00:00Z",
        )
        data = resp.model_dump()
        assert data["key"] == "sk_abc123"
        assert data["name"] == "test-key"


class TestApiKeyListItem:
    def test_no_plaintext_exposed(self):
        item = ApiKeyListItem(
            id="uuid-1",
            name="test-key",
            created_at="2026-06-03T00:00:00Z",
        )
        data = item.model_dump()
        assert "key" not in data
        assert "key_hash" not in data


class TestApiKeyRevokeResponse:
    def test_revoked_true(self):
        resp = ApiKeyRevokeResponse(id="uuid-1", revoked=True, message="OK")
        assert resp.revoked is True
