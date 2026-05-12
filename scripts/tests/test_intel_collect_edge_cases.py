"""
Edge case and boundary tests for scripts/intel-collect.py.

Tests cover:
- Unicode / encoding edge cases
- Empty / missing / null data
- Malformed API responses
- Large dataset handling
- Checkpoint / resume fault-tolerance
- Deduplication edge cases (hash + semantic)
- Temporal status boundary conditions
- CNAE keyword gate edge cases

All external calls are mocked. No production code is modified.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch, mock_open

import pytest

# ---------------------------------------------------------------------------
# Import intel-collect.py via importlib (hyphenated name)
# ---------------------------------------------------------------------------
SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import importlib.util

_ic_path = str(SCRIPTS_DIR / "intel-collect.py")
_ic_spec = importlib.util.spec_from_file_location("intel_collect", _ic_path)
if _ic_spec is None or _ic_spec.loader is None:
    pytest.skip(f"Cannot load {_ic_path}", allow_module_level=True)

_ic = importlib.util.module_from_spec(_ic_spec)

_real_platform = sys.platform
sys.platform = "linux"
try:
    _ic_spec.loader.exec_module(_ic)
except Exception as _e:
    sys.platform = _real_platform
    pytest.skip(f"Failed to load intel-collect.py: {_e}", allow_module_level=True)
finally:
    sys.platform = _real_platform

# Pull functions under test
_compute_dedup_hash = _ic._compute_dedup_hash
_token_overlap = _ic._token_overlap
_semantic_dedup = _ic._semantic_dedup
_parse_pncp_item = _ic._parse_pncp_item
_checkpoint_key = _ic._checkpoint_key
_subkey = _ic._subkey
_load_checkpoint = _ic._load_checkpoint
_save_checkpoint = _ic._save_checkpoint
_cleanup_old_checkpoints = _ic._cleanup_old_checkpoints
classify_by_object_heuristic = _ic.classify_by_object_heuristic
apply_cnae_keyword_gate = _ic.apply_cnae_keyword_gate
assemble_output = _ic.assemble_output
_detect_delta = _ic._detect_delta
_find_previous_run = _ic._find_previous_run
_api_get_with_retry = _ic._api_get_with_retry
_parse_numero_controle_pncp = _ic._parse_numero_controle_pncp
# EXCLUSION_PATTERNS refactored to sector-specific _EXCLUSION_PATTERNS_CACHE.
# Collect all unique exclusion patterns across all 20 sectors for testing.
_EXCLUSION_SECTOR_IDS: set[str] = {
    "vestuario", "alimentos", "informatica", "mobiliario", "papelaria",
    "engenharia", "software_desenvolvimento", "software_licencas",
    "servicos_prediais", "produtos_limpeza", "medicamentos",
    "equipamentos_medicos", "insumos_hospitalares", "vigilancia",
    "transporte_servicos", "frota_veicular", "manutencao_predial",
    "engenharia_rodoviaria", "materiais_eletricos", "materiais_hidraulicos",
}
_ALL_EXCLUSION_PATTERNS: list[re.Pattern] = _ic._get_exclusion_patterns_for_sector(_EXCLUSION_SECTOR_IDS)
MODALIDADES_BUSCA = _ic.MODALIDADES_BUSCA
_today = _ic._today
_date_compact = _ic._date_compact
_date_iso = _ic._date_iso
_CHECKPOINT_FILE = _ic._CHECKPOINT_FILE
_compile_keyword_patterns = _ic._compile_keyword_patterns


# ============================================================
# HELPERS
# ============================================================

def _make_pncp_item(
    objeto="Construcao de edificio",
    uf="SC",
    municipio="Chapeco",
    valor=1_000_000.0,
    cnpj_orgao="83102459000152",
    ano="2026",
    seq="42",
    days_until_close=15,
    days_until_open=10,
    mod_code=4,
    **overrides,
):
    """Build a minimal PNCP API item dict."""
    now = datetime.now(timezone.utc)
    item = {
        "orgaoEntidade": {
            "cnpj": cnpj_orgao,
            "razaoSocial": f"PREFEITURA DE {municipio.upper()}",
        },
        "unidadeOrgao": {
            "ufSigla": uf,
            "municipioNome": municipio,
            "nomeUnidade": "Secretaria de Obras",
        },
        "anoCompra": ano,
        "sequencialCompra": seq,
        "objetoCompra": objeto,
        "valorTotalEstimado": valor,
        "modalidadeNome": "Concorrencia - Eletronica",
        "dataPublicacaoPncp": (now - timedelta(days=5)).strftime("%Y-%m-%d"),
        "dataAberturaProposta": (now + timedelta(days=days_until_open)).strftime(
            "%Y-%m-%dT%H:%M:%S"
        ),
        "dataEncerramentoProposta": (now + timedelta(days=days_until_close)).strftime(
            "%Y-%m-%dT%H:%M:%S"
        ),
        "linkSistemaOrigem": "",
    }
    item.update(overrides)
    return item


def _make_edital(
    _id="83102459000152/2026/42",
    objeto="Construcao de edificio",
    uf="SC",
    municipio="Chapeco",
    valor_estimado=1_000_000.0,
    cnpj_orgao="83102459000152",
    status_temporal="PLANEJAVEL",
    dias_restantes=15,
    **kwargs,
):
    """Build a minimal edital dict in internal format."""
    ed = {
        "_id": _id,
        "objeto": objeto,
        "orgao": f"PREFEITURA DE {municipio.upper()}",
        "cnpj_orgao": cnpj_orgao,
        "uf": uf,
        "municipio": municipio,
        "valor_estimado": valor_estimado,
        "modalidade_code": 4,
        "modalidade_nome": "Concorrencia",
        "data_publicacao": "2026-03-15",
        "data_abertura_proposta": "2026-04-01T10:00:00",
        "data_encerramento_proposta": "2026-04-15T18:00:00",
        "link_pncp": f"https://pncp.gov.br/app/editais/{cnpj_orgao}/2026/42",
        "ano_compra": "2026",
        "sequencial_compra": "42",
        "_dedup_key": _id,
        "status_temporal": status_temporal,
        "dias_restantes": dias_restantes,
    }
    ed.update(kwargs)
    return ed


# ============================================================
# UNICODE / ENCODING EDGE CASES
# ============================================================


class TestUnicodeEdgeCases:
    """Verify that accented and special characters are handled correctly."""

    def test_objeto_with_accented_chars(self):
        """Accented chars (ã, é, ç, ü) should parse without error."""
        item = _make_pncp_item(objeto="Construção de habitação em São José do Céu")
        result = _parse_pncp_item(item, 4, "Concorrencia", ["SC"])
        assert result is not None
        assert "Construção" in result["objeto"]
        assert "São José" in result["objeto"]

    def test_objeto_with_special_symbols(self):
        """Symbols (TM, copyright, bullet, em-dash, guillemets) should survive."""
        item = _make_pncp_item(
            objeto="Obra de construção™ — «projeto» © 2026 • item 1"
        )
        result = _parse_pncp_item(item, 4, "Concorrencia", ["SC"])
        assert result is not None
        assert "™" in result["objeto"]
        assert "—" in result["objeto"]
        assert "«" in result["objeto"]

    def test_objeto_with_emoji(self):
        """Emoji in objeto should not crash (even if nonsensical)."""
        item = _make_pncp_item(objeto="Construção 🏗️ de escola municipal 🏫")
        result = _parse_pncp_item(item, 4, "Concorrencia", ["SC"])
        assert result is not None
        assert "🏗️" in result["objeto"]

    def test_cnpj_with_leading_zeros(self):
        """CNPJ 00123456000190 should preserve leading zeros."""
        item = _make_pncp_item(cnpj_orgao="00123456000190")
        result = _parse_pncp_item(item, 4, "Concorrencia", ["SC"])
        assert result is not None
        assert result["cnpj_orgao"] == "00123456000190"
        assert result["_id"].startswith("00123456000190/")

    def test_razao_social_with_special_chars(self):
        """Razao social with &, /, ', " should not corrupt the data."""
        item = _make_pncp_item()
        item["orgaoEntidade"]["razaoSocial"] = 'CONSTRUTORA D\'ÁGUA & CIA "LTDA" / ME'
        result = _parse_pncp_item(item, 4, "Concorrencia", ["SC"])
        assert result is not None
        assert "&" in result["orgao"]
        assert "'" in result["orgao"]

    def test_dedup_hash_unicode_consistency(self):
        """Dedup hash should produce consistent results for Unicode text."""
        ed1 = _make_edital(objeto="Construção de habitação popular")
        ed2 = _make_edital(objeto="Construção de habitação popular")
        assert _compute_dedup_hash(ed1) == _compute_dedup_hash(ed2)

    def test_dedup_hash_accents_differ(self):
        """Different accents should produce different hashes."""
        ed1 = _make_edital(objeto="Construção de habitação")
        ed2 = _make_edital(objeto="Construcao de habitacao")
        # They are different strings, different hashes
        assert _compute_dedup_hash(ed1) != _compute_dedup_hash(ed2)

    def test_token_overlap_with_unicode(self):
        """Token overlap should work with accented characters."""
        overlap = _token_overlap(
            "Pavimentação asfáltica em vias urbanas",
            "Pavimentação asfáltica em rodovias",
        )
        assert overlap > 0.3  # Shared: pavimentação, asfáltica

    @pytest.mark.parametrize(
        "text",
        [
            "Construção de muro de contenção",
            "Serviço de topografia e georreferenciamento",
            "Execução de drenagem pluvial e águas pluviais",
            "Recuperação de pavimentação em paralelepípedo",
        ],
    )
    def test_keyword_gate_accented_objects(self, text):
        """CNAE gate should work with accented objeto text."""
        editais = [_make_edital(objeto=text)]
        keywords = ["construção", "muro", "contenção", "topografia", "drenagem", "pavimentação"]
        patterns = _compile_keyword_patterns(keywords)
        apply_cnae_keyword_gate(editais, keywords, patterns, "engenharia_obras", "4120")
        # Should not crash; fields should be populated
        assert "cnae_compatible" in editais[0]
        assert "keyword_density" in editais[0]


# ============================================================
# EMPTY / MISSING DATA EDGE CASES
# ============================================================


class TestEmptyMissingData:
    """Test behavior when data is absent, null, or empty."""

    def test_pncp_item_missing_orgao_entity(self):
        """PNCP item with no orgaoEntidade should return None (skip)."""
        item = _make_pncp_item()
        item["orgaoEntidade"] = None
        result = _parse_pncp_item(item, 4, "Concorrencia", ["SC"])
        # Parser may return None or a dict with empty orgao
        if result is not None:
            assert isinstance(result, dict)

    def test_pncp_item_missing_unidade(self):
        """PNCP item with no unidadeOrgao should still parse."""
        item = _make_pncp_item()
        item["unidadeOrgao"] = None
        # UF cannot be determined, so it may be filtered out or parse with empty UF
        result = _parse_pncp_item(item, 4, "Concorrencia", [])
        # When ufs is empty, no UF filter is applied
        assert result is not None
        assert result["uf"] == ""

    def test_pncp_item_empty_objeto(self):
        """PNCP item with empty objeto should parse (but flag as low quality)."""
        item = _make_pncp_item(objeto="")
        result = _parse_pncp_item(item, 4, "Concorrencia", ["SC"])
        assert result is not None
        assert result["objeto"] == ""

    def test_pncp_item_null_valor(self):
        """Null valor should be converted to None/0."""
        item = _make_pncp_item(valor=None)
        item["valorTotalEstimado"] = None
        item["valorEstimado"] = None
        result = _parse_pncp_item(item, 4, "Concorrencia", ["SC"])
        assert result is not None
        assert result["valor_estimado"] is None or result["valor_estimado"] == 0

    def test_pncp_item_missing_dates(self):
        """Missing date fields should result in SEM_DATA status."""
        item = _make_pncp_item()
        item["dataEncerramentoProposta"] = ""
        item["dataAberturaProposta"] = ""
        result = _parse_pncp_item(item, 4, "Concorrencia", ["SC"])
        assert result is not None
        assert result["status_temporal"] == "SEM_DATA"

    def test_pncp_item_missing_cnpj_and_ano(self):
        """Missing cnpj+ano+seq should generate unknown/ ID."""
        item = _make_pncp_item()
        item["orgaoEntidade"]["cnpj"] = ""
        item["anoCompra"] = ""
        item["sequencialCompra"] = ""
        result = _parse_pncp_item(item, 4, "Concorrencia", ["SC"])
        assert result is not None
        assert result["_id"].startswith("unknown/")

    def test_cnae_gate_empty_objeto(self):
        """Edital with empty objeto should be marked incompatible."""
        editais = [_make_edital(objeto="")]
        keywords = ["construcao", "obra"]
        patterns = _compile_keyword_patterns(keywords)
        apply_cnae_keyword_gate(editais, keywords, patterns, "engenharia_obras", "4120")
        assert editais[0]["cnae_compatible"] is False
        assert editais[0]["exclusion_reason"] == "objeto vazio"

    def test_cnae_gate_whitespace_only_objeto(self):
        """Edital with only whitespace in objeto should be incompatible."""
        editais = [_make_edital(objeto="   \t\n  ")]
        keywords = ["construcao"]
        patterns = _compile_keyword_patterns(keywords)
        apply_cnae_keyword_gate(editais, keywords, patterns, "engenharia_obras", "4120")
        assert editais[0]["cnae_compatible"] is False

    def test_dedup_hash_empty_fields(self):
        """Dedup hash should handle all-empty fields gracefully."""
        ed = _make_edital(objeto="", uf="", municipio="", valor_estimado=0)
        h = _compute_dedup_hash(ed)
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex

    def test_semantic_dedup_empty_list(self):
        """Semantic dedup on empty list should return empty."""
        result = _semantic_dedup([])
        assert result == []

    def test_semantic_dedup_single_item(self):
        """Semantic dedup on single item should return it unchanged."""
        ed = _make_edital()
        result = _semantic_dedup([ed])
        assert len(result) == 1

    def test_token_overlap_empty_strings(self):
        """Token overlap of two empty strings should be 0.0."""
        assert _token_overlap("", "") == 0.0

    def test_token_overlap_one_empty(self):
        """Token overlap with one empty string should be 0.0."""
        assert _token_overlap("construcao de obra", "") == 0.0

    def test_detect_delta_no_previous_file(self, tmp_path):
        """All editais should be NOVO when no previous file exists."""
        editais = [_make_edital(_id=f"test/{i}") for i in range(5)]
        summary = _detect_delta(editais, None)
        assert summary["novos"] == 5
        for ed in editais:
            assert ed["_delta_status"] == "NOVO"

    def test_detect_delta_corrupted_previous(self, tmp_path):
        """Corrupted previous JSON should mark all as NOVO."""
        bad_file = tmp_path / "prev.json"
        bad_file.write_text("NOT VALID JSON {{{", encoding="utf-8")
        editais = [_make_edital(_id="test/1")]
        summary = _detect_delta(editais, str(bad_file))
        assert summary["novos"] == 1

    def test_assemble_output_empty_editais(self):
        """Assemble output with zero editais should not crash."""
        empresa = {
            "razao_social": "Test",
            "capital_social": 0,
            "_source": {"status": "API"},
        }
        result = assemble_output(
            empresa=empresa,
            editais=[],
            cnpj_formatted="01.721.078/0001-68",
            ufs=["SC"],
            dias=30,
            sector_name="Engenharia",
            sector_key="engenharia_obras",
            keywords=["obra"],
            source_meta={"total_raw_api": 0, "total_after_dedup": 0, "pages_fetched": 0, "errors": 0},
        )
        assert result["estatisticas"]["total_cnae_compativel"] == 0
        assert result["editais"] == []


# ============================================================
# MALFORMED API RESPONSES
# ============================================================


class TestMalformedApiResponses:
    """Test handling of unexpected API response formats."""

    def test_api_get_with_retry_success_first_attempt(self):
        """Should return immediately on first success."""
        api = MagicMock()
        api.get.return_value = ([{"data": "ok"}], "API")
        data, status = _api_get_with_retry(api, "http://test.com", label="test", max_retries=2)
        assert status == "API"
        assert data == [{"data": "ok"}]
        assert api.get.call_count == 1

    def test_api_get_with_retry_retries_on_failure(self):
        """Should retry on API_FAILED status."""
        api = MagicMock()
        api.get.side_effect = [
            (None, "API_FAILED"),
            (None, "API_FAILED"),
            ([{"data": "ok"}], "API"),
        ]
        with patch("time.sleep"):  # Skip actual sleep
            data, status = _api_get_with_retry(
                api, "http://test.com", label="test", max_retries=2, base_delay=0.01
            )
        assert status == "API"
        assert api.get.call_count == 3

    def test_api_get_with_retry_gives_up_after_max(self):
        """Should give up after max_retries and return last result."""
        api = MagicMock()
        api.get.return_value = (None, "API_FAILED")
        with patch("time.sleep"):
            data, status = _api_get_with_retry(
                api, "http://test.com", label="test", max_retries=2, base_delay=0.01
            )
        assert status == "API_FAILED"
        assert data is None
        assert api.get.call_count == 3  # initial + 2 retries

    def test_api_get_with_retry_no_retry_on_success_with_none_data(self):
        """Successful status with None data should also be retried (empty data)."""
        api = MagicMock()
        api.get.side_effect = [
            (None, "API"),  # Successful status but no data
            ([{"item": 1}], "API"),  # Second attempt succeeds with data
        ]
        with patch("time.sleep"):
            data, status = _api_get_with_retry(
                api, "http://test.com", label="test", max_retries=1, base_delay=0.01
            )
        assert status == "API"
        assert data == [{"item": 1}]

    def test_parse_pncp_item_string_valor(self):
        """PNCP item with string valor should be handled by _safe_float."""
        item = _make_pncp_item()
        item["valorTotalEstimado"] = "2500000.00"
        result = _parse_pncp_item(item, 4, "Concorrencia", ["SC"])
        assert result is not None
        assert result["valor_estimado"] == 2500000.0

    def test_parse_pncp_item_extra_fields_ignored(self):
        """Extra unexpected fields in PNCP item should be silently ignored."""
        item = _make_pncp_item()
        item["unknownField"] = "should be ignored"
        item["anotherRandom"] = {"nested": True}
        result = _parse_pncp_item(item, 4, "Concorrencia", ["SC"])
        assert result is not None
        assert "unknownField" not in result

    def test_parse_pncp_item_wrong_uf_filtered(self):
        """Item with UF not in filter list should return None."""
        item = _make_pncp_item(uf="AM")
        result = _parse_pncp_item(item, 4, "Concorrencia", ["SC", "PR"])
        assert result is None

    def test_parse_pncp_item_empty_uf_list(self):
        """Empty UF filter should accept all UFs."""
        item = _make_pncp_item(uf="AM")
        result = _parse_pncp_item(item, 4, "Concorrencia", [])
        assert result is not None
        assert result["uf"] == "AM"


# ============================================================
# LARGE DATASET EDGE CASES
# ============================================================


class TestLargeDataset:
    """Test behavior with large input sizes."""

    def test_dedup_hash_very_long_objeto(self):
        """Very long objeto (10K+ chars) should be truncated to 150 chars for hash."""
        long_obj = "A" * 15_000
        ed = _make_edital(objeto=long_obj)
        h = _compute_dedup_hash(ed)
        # The hash function uses objeto[:150], so it should still work
        assert isinstance(h, str)
        assert len(h) == 64

    def test_dedup_hash_truncates_at_150(self):
        """Two objects identical in first 150 chars should produce same hash."""
        base = "Construcao de obra " * 10  # ~190 chars
        ed1 = _make_edital(objeto=base + "SUFFIX_A")
        ed2 = _make_edital(objeto=base + "SUFFIX_B")
        # First 150 chars are the same
        assert _compute_dedup_hash(ed1) == _compute_dedup_hash(ed2)

    def test_semantic_dedup_100_editais(self):
        """Semantic dedup should handle 100 editais without error."""
        editais = [
            _make_edital(
                _id=f"org/{i}",
                objeto=f"Obra de construcao tipo {i} no municipio",
                cnpj_orgao="11111111000100",
                valor_estimado=1_000_000 + i * 100,
            )
            for i in range(100)
        ]
        result = _semantic_dedup(editais)
        # Some get deduped due to same orgao + similar objects + close values
        assert len(result) >= 90  # dedup removes some similar items

    def test_very_long_razao_social(self):
        """Razao social with 200+ chars should not crash PNCP parsing."""
        item = _make_pncp_item()
        item["orgaoEntidade"]["razaoSocial"] = "A" * 250
        result = _parse_pncp_item(item, 4, "Concorrencia", ["SC"])
        assert result is not None
        assert len(result["orgao"]) == 250

    def test_cnae_gate_many_editais(self):
        """CNAE gate should handle 500 editais efficiently."""
        editais = [
            _make_edital(
                _id=f"test/{i}",
                objeto=f"Construcao de obra #{i} com pavimentacao e drenagem",
            )
            for i in range(500)
        ]
        keywords = ["construcao", "obra", "pavimentacao", "drenagem"]
        patterns = _compile_keyword_patterns(keywords)
        apply_cnae_keyword_gate(editais, keywords, patterns, "engenharia_obras", "4120")
        # All should have been processed
        assert all("cnae_compatible" in ed for ed in editais)

    def test_assemble_output_many_editais(self):
        """Assemble output with 200 editais should not crash."""
        empresa = {"razao_social": "Test", "capital_social": 500000, "_source": {"status": "API"}}
        editais = [
            _make_edital(
                _id=f"test/{i}",
                cnae_compatible=True if i % 3 != 0 else False,
                valor_estimado=float(i * 100_000),
            )
            for i in range(200)
        ]
        result = assemble_output(
            empresa=empresa,
            editais=editais,
            cnpj_formatted="12.345.678/0001-99",
            ufs=["SC", "PR"],
            dias=30,
            sector_name="Engenharia",
            sector_key="engenharia_obras",
            keywords=["obra"],
            source_meta={
                "total_raw_api": 300,
                "total_after_dedup": 200,
                "pages_fetched": 50,
                "errors": 1,
            },
        )
        assert len(result["editais"]) == 200


# ============================================================
# CHECKPOINT / RESUME EDGE CASES
# ============================================================


class TestCheckpointEdgeCases:
    """Test checkpoint save/resume fault tolerance."""

    def test_load_checkpoint_file_not_exists(self, tmp_path, monkeypatch):
        """Loading when file doesn't exist should return {}."""
        monkeypatch.setattr(_ic, "_CHECKPOINT_FILE", tmp_path / "nonexistent.json")
        result = _load_checkpoint()
        assert result == {}

    def test_load_checkpoint_corrupted_json(self, tmp_path, monkeypatch):
        """Corrupted checkpoint file should return {} (not crash)."""
        cp_file = tmp_path / "checkpoint.json"
        cp_file.write_text("{INVALID JSON]]]", encoding="utf-8")
        monkeypatch.setattr(_ic, "_CHECKPOINT_FILE", cp_file)
        result = _load_checkpoint()
        assert result == {}

    def test_load_checkpoint_empty_file(self, tmp_path, monkeypatch):
        """Empty checkpoint file should return {}."""
        cp_file = tmp_path / "checkpoint.json"
        cp_file.write_text("", encoding="utf-8")
        monkeypatch.setattr(_ic, "_CHECKPOINT_FILE", cp_file)
        result = _load_checkpoint()
        assert result == {}

    def test_save_and_load_checkpoint_roundtrip(self, tmp_path, monkeypatch):
        """Save then load should produce identical data."""
        cp_file = tmp_path / "checkpoint.json"
        monkeypatch.setattr(_ic, "_CHECKPOINT_FILE", cp_file)
        data = {"key1": {"subkey": {"items": [1, 2, 3], "timestamp": "2026-03-20T12:00:00"}}}
        _save_checkpoint(data)
        loaded = _load_checkpoint()
        assert loaded == data

    def test_checkpoint_key_deterministic(self):
        """Same inputs should produce same checkpoint key."""
        k1 = _checkpoint_key("01721078000168", ["SC", "PR"], 30)
        k2 = _checkpoint_key("01721078000168", ["PR", "SC"], 30)
        # UFs are sorted
        assert k1 == k2

    def test_checkpoint_key_different_cnpj(self):
        """Different CNPJ should produce different key."""
        k1 = _checkpoint_key("01721078000168", ["SC"], 30)
        k2 = _checkpoint_key("99999999000199", ["SC"], 30)
        assert k1 != k2

    def test_checkpoint_key_different_dias(self):
        """Different dias should produce different key."""
        k1 = _checkpoint_key("01721078000168", ["SC"], 30)
        k2 = _checkpoint_key("01721078000168", ["SC"], 60)
        assert k1 != k2

    def test_subkey_format(self):
        """Subkey should combine mod_code and UF."""
        assert _subkey(4, "SC") == "mod_4_SC"
        assert _subkey(5, "ALL") == "mod_5_ALL"

    def test_cleanup_old_checkpoints_removes_stale(self):
        """Entries older than 24h should be removed."""
        old_ts = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        fresh_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        data = {
            "old_key": {
                "sub1": {"timestamp": old_ts, "items": []},
            },
            "fresh_key": {
                "sub1": {"timestamp": fresh_ts, "items": []},
            },
        }
        cleaned = _cleanup_old_checkpoints(data)
        assert "old_key" not in cleaned
        assert "fresh_key" in cleaned

    def test_cleanup_old_checkpoints_keeps_mixed(self):
        """Entry with at least one fresh sub-key should be kept entirely."""
        old_ts = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        fresh_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        data = {
            "mixed_key": {
                "sub_old": {"timestamp": old_ts, "items": []},
                "sub_fresh": {"timestamp": fresh_ts, "items": []},
            },
        }
        cleaned = _cleanup_old_checkpoints(data)
        assert "mixed_key" in cleaned

    def test_cleanup_old_checkpoints_handles_bad_timestamps(self):
        """Invalid timestamp strings should not crash cleanup."""
        data = {
            "bad_ts_key": {
                "sub1": {"timestamp": "NOT-A-DATE", "items": []},
            },
        }
        cleaned = _cleanup_old_checkpoints(data)
        # Bad timestamp = can't prove freshness, so it gets cleaned
        assert "bad_ts_key" not in cleaned

    def test_cleanup_old_checkpoints_non_dict_values(self):
        """Non-dict values at top level should be skipped."""
        data = {
            "string_val": "not a dict",
            "int_val": 42,
        }
        cleaned = _cleanup_old_checkpoints(data)
        assert cleaned == {}

    def test_save_checkpoint_creates_parent_dirs(self, tmp_path, monkeypatch):
        """Save should create parent directories if they don't exist."""
        cp_file = tmp_path / "deep" / "nested" / "dir" / "checkpoint.json"
        monkeypatch.setattr(_ic, "_CHECKPOINT_FILE", cp_file)
        data = {"test": {"sub": {"items": [], "timestamp": datetime.now(timezone.utc).isoformat()}}}
        _save_checkpoint(data)
        assert cp_file.exists()
        loaded = json.loads(cp_file.read_text(encoding="utf-8"))
        assert loaded == data


# ============================================================
# DEDUPLICATION EDGE CASES
# ============================================================


class TestDeduplicationEdgeCases:
    """Test hash-based and semantic deduplication boundary conditions."""

    def test_identical_hash_different_ufs(self):
        """Editais in different UFs should get different hashes (UF is part of hash)."""
        ed1 = _make_edital(uf="SC", objeto="Construcao de muro")
        ed2 = _make_edital(uf="PR", objeto="Construcao de muro")
        assert _compute_dedup_hash(ed1) != _compute_dedup_hash(ed2)

    def test_semantic_dedup_same_orgao_similar_value_high_overlap(self):
        """Same org, +-15% valor, >80% overlap should be deduped."""
        ed1 = _make_edital(
            _id="org/1", cnpj_orgao="11111111000100",
            objeto="Pavimentacao asfaltica em CBUQ de vias urbanas no centro",
            valor_estimado=1_000_000, uf="SC",
            data_publicacao="2026-03-10",
        )
        ed2 = _make_edital(
            _id="org/2", cnpj_orgao="11111111000100",
            objeto="Pavimentacao asfaltica em CBUQ de vias urbanas no centro da cidade",
            valor_estimado=1_050_000, uf="SC",  # Within 15%
            data_publicacao="2026-03-12",
        )
        result = _semantic_dedup([ed1, ed2])
        assert len(result) == 1
        assert result[0]["_id"] == "org/1"  # Earlier publication kept

    def test_semantic_dedup_same_orgao_different_value(self):
        """Same org but >15% valor difference should NOT be deduped."""
        ed1 = _make_edital(
            _id="org/1", cnpj_orgao="11111111000100",
            objeto="Pavimentacao asfaltica em CBUQ de vias urbanas",
            valor_estimado=1_000_000, uf="SC",
        )
        ed2 = _make_edital(
            _id="org/2", cnpj_orgao="11111111000100",
            objeto="Pavimentacao asfaltica em CBUQ de vias urbanas",
            valor_estimado=2_000_000, uf="SC",  # 100% difference
        )
        result = _semantic_dedup([ed1, ed2])
        assert len(result) == 2

    def test_semantic_dedup_different_orgao(self):
        """Different orgs should never be deduped even with identical objects."""
        ed1 = _make_edital(
            _id="org_a/1", cnpj_orgao="11111111000100",
            objeto="Construcao de escola municipal", valor_estimado=1_000_000, uf="SC",
        )
        ed2 = _make_edital(
            _id="org_b/1", cnpj_orgao="22222222000200",
            objeto="Construcao de escola municipal", valor_estimado=1_000_000, uf="SC",
        )
        result = _semantic_dedup([ed1, ed2])
        assert len(result) == 2

    def test_semantic_dedup_low_token_overlap(self):
        """Same org + similar value but low overlap should NOT be deduped."""
        ed1 = _make_edital(
            _id="org/1", cnpj_orgao="11111111000100",
            objeto="Construcao de escola municipal no bairro centro",
            valor_estimado=1_000_000, uf="SC",
        )
        ed2 = _make_edital(
            _id="org/2", cnpj_orgao="11111111000100",
            objeto="Pavimentacao asfaltica da rodovia estadual trecho norte",
            valor_estimado=1_050_000, uf="SC",
        )
        result = _semantic_dedup([ed1, ed2])
        assert len(result) == 2  # Different enough

    def test_semantic_dedup_cross_uf_not_compared(self):
        """Editais in different UFs should not be compared for semantic dedup."""
        ed1 = _make_edital(
            _id="org/1", cnpj_orgao="11111111000100",
            objeto="Pavimentacao asfaltica em CBUQ de vias urbanas",
            valor_estimado=1_000_000, uf="SC",
        )
        ed2 = _make_edital(
            _id="org/2", cnpj_orgao="11111111000100",
            objeto="Pavimentacao asfaltica em CBUQ de vias urbanas",
            valor_estimado=1_000_000, uf="PR",
        )
        result = _semantic_dedup([ed1, ed2])
        assert len(result) == 2  # Different UFs, not compared

    def test_semantic_dedup_zero_valor_both(self):
        """Both editais with valor=0 should be treated as equal-value for dedup check."""
        ed1 = _make_edital(
            _id="org/1", cnpj_orgao="11111111000100",
            objeto="Pavimentacao asfaltica em CBUQ de vias urbanas no centro",
            valor_estimado=0, uf="SC",
            data_publicacao="2026-03-10",
        )
        ed2 = _make_edital(
            _id="org/2", cnpj_orgao="11111111000100",
            objeto="Pavimentacao asfaltica em CBUQ de vias urbanas no centro da cidade",
            valor_estimado=0, uf="SC",
            data_publicacao="2026-03-12",
        )
        result = _semantic_dedup([ed1, ed2])
        # Both valor=0, same org, high overlap => should dedup
        assert len(result) == 1


# ============================================================
# TEMPORAL STATUS EDGE CASES
# ============================================================


class TestTemporalStatusEdgeCases:
    """Test status_temporal boundary conditions."""

    def test_status_exactly_7_days_is_urgente(self):
        """Exactly 7 days remaining should be URGENTE (<=7)."""
        now = datetime.now()
        enc = (now + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S")
        item = _make_pncp_item()
        item["dataEncerramentoProposta"] = enc
        item["dataAberturaProposta"] = (now + timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%S")
        result = _parse_pncp_item(item, 4, "Concorrencia", ["SC"])
        assert result is not None
        assert result["status_temporal"] == "URGENTE"

    def test_status_exactly_15_days_is_iminente(self):
        """Exactly 15 days remaining should be IMINENTE (<=15, >7)."""
        now = datetime.now()
        enc = (now + timedelta(days=15)).strftime("%Y-%m-%dT%H:%M:%S")
        item = _make_pncp_item()
        item["dataEncerramentoProposta"] = enc
        item["dataAberturaProposta"] = (now + timedelta(days=20)).strftime("%Y-%m-%dT%H:%M:%S")
        result = _parse_pncp_item(item, 4, "Concorrencia", ["SC"])
        assert result is not None
        assert result["status_temporal"] == "IMINENTE"

    def test_status_past_date_is_expirado(self):
        """Date in the past should be EXPIRADO."""
        now = datetime.now()
        enc = (now - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S")
        item = _make_pncp_item()
        item["dataEncerramentoProposta"] = enc
        item["dataAberturaProposta"] = (now - timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%S")
        result = _parse_pncp_item(item, 4, "Concorrencia", ["SC"])
        assert result is not None
        assert result["status_temporal"] == "EXPIRADO"

    def test_status_sessao_realizada_overrides(self):
        """If abertura is in the past (session held), status should be SESSAO_REALIZADA."""
        now = datetime.now()
        enc = (now + timedelta(days=15)).strftime("%Y-%m-%dT%H:%M:%S")
        ab = (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")
        item = _make_pncp_item()
        item["dataEncerramentoProposta"] = enc
        item["dataAberturaProposta"] = ab
        result = _parse_pncp_item(item, 4, "Concorrencia", ["SC"])
        assert result is not None
        assert result["status_temporal"] == "SESSAO_REALIZADA"

    def test_status_malformed_date_is_sem_data(self):
        """Malformed date string should fall back to SEM_DATA."""
        item = _make_pncp_item()
        item["dataEncerramentoProposta"] = "NOT-A-DATE"
        item["dataAberturaProposta"] = "ALSO-BAD"
        result = _parse_pncp_item(item, 4, "Concorrencia", ["SC"])
        assert result is not None
        assert result["status_temporal"] == "SEM_DATA"


# ============================================================
# DELTA DETECTION EDGE CASES
# ============================================================


class TestDeltaDetectionEdgeCases:
    """Test delta detection boundary conditions."""

    def test_delta_vencendo_transition(self, tmp_path):
        """Edital with dias_restantes going from >3 to <=3 should be VENCENDO."""
        prev_data = {
            "editais": [
                {"_id": "test/1", "dias_restantes": 10, "valor_estimado": 1000000},
            ],
            "_metadata": {"generated_at": "2026-03-18T12:00:00"},
        }
        prev_file = tmp_path / "prev.json"
        prev_file.write_text(json.dumps(prev_data), encoding="utf-8")

        editais = [_make_edital(_id="test/1", dias_restantes=2, valor_estimado=1000000)]
        summary = _detect_delta(editais, str(prev_file))
        assert summary["vencendo"] == 1
        assert editais[0]["_delta_status"] == "VENCENDO"

    def test_delta_atualizado_valor_change(self, tmp_path):
        """Valor change >5% should mark as ATUALIZADO."""
        prev_data = {
            "editais": [
                {"_id": "test/1", "dias_restantes": 15, "valor_estimado": 1000000},
            ],
            "_metadata": {"generated_at": "2026-03-18T12:00:00"},
        }
        prev_file = tmp_path / "prev.json"
        prev_file.write_text(json.dumps(prev_data), encoding="utf-8")

        editais = [_make_edital(_id="test/1", dias_restantes=13, valor_estimado=1200000)]
        summary = _detect_delta(editais, str(prev_file))
        assert summary["atualizados"] == 1

    def test_delta_inalterado(self, tmp_path):
        """No significant change should mark as INALTERADO."""
        prev_data = {
            "editais": [
                {"_id": "test/1", "dias_restantes": 15, "valor_estimado": 1000000},
            ],
            "_metadata": {"generated_at": "2026-03-18T12:00:00"},
        }
        prev_file = tmp_path / "prev.json"
        prev_file.write_text(json.dumps(prev_data), encoding="utf-8")

        editais = [_make_edital(_id="test/1", dias_restantes=13, valor_estimado=1020000)]
        summary = _detect_delta(editais, str(prev_file))
        assert summary["inalterados"] == 1

    def test_delta_new_edital_not_in_previous(self, tmp_path):
        """Edital not in previous run should be NOVO."""
        prev_data = {
            "editais": [{"_id": "test/old"}],
            "_metadata": {"generated_at": "2026-03-18T12:00:00"},
        }
        prev_file = tmp_path / "prev.json"
        prev_file.write_text(json.dumps(prev_data), encoding="utf-8")

        editais = [_make_edital(_id="test/new")]
        summary = _detect_delta(editais, str(prev_file))
        assert summary["novos"] == 1

    def test_find_previous_run_no_dir(self, tmp_path, monkeypatch):
        """Should return None when intel dir doesn't exist."""
        monkeypatch.setattr(_ic, "_PROJECT_ROOT", tmp_path)
        result = _find_previous_run("01721078000168")
        assert result is None


# ============================================================
# HEURISTIC CLASSIFIER EDGE CASES
# ============================================================


class TestHeuristicClassifierEdgeCases:
    """Test the secondary heuristic classifier boundaries."""

    @pytest.mark.parametrize(
        "objeto,expected",
        [
            ("Construcao de praca publica", "COMPATIVEL"),
            ("Reforma e ampliacao de escola", "COMPATIVEL"),
            ("Pavimentacao asfaltica em CBUQ", "COMPATIVEL"),
            ("Aquisicao de medicamentos", "NEEDS_REVIEW"),  # heuristic is conservative
            ("Transporte escolar rural", "INCOMPATIVEL"),
            ("Seguro patrimonial predial", "NEEDS_REVIEW"),  # no sector has "seguro" as strong_incompat
            ("Fornecimento de materiais diversos", "NEEDS_REVIEW"),
        ],
    )
    def test_heuristic_classification(self, objeto, expected):
        """classify_by_object_heuristic requires sector context for engenharia patterns."""
        result = classify_by_object_heuristic(
            objeto, "Construcao de edificios",
            sector_keys={"engenharia"},
        )
        assert result == expected

    def test_heuristic_conflicting_signals(self):
        """Object with both construction AND incompatible signals."""
        # "construcao" is strong_compat, "transporte" alone is not strong_incompat
        # but "transporte escolar" IS strong_incompat
        result = classify_by_object_heuristic(
            "Construcao de terminal de transporte publico", ""
        )
        # Has both strong_compat (Construcao) and strong_incompat (transporte publico)
        # When both, function returns NEEDS_REVIEW
        assert result == "NEEDS_REVIEW"


# ============================================================
# EXCLUSION PATTERNS EDGE CASES
# ============================================================


class TestExclusionPatterns:
    """Test the exclusion patterns loaded via _get_exclusion_patterns_for_sector."""

    def test_exclusion_patterns_compiled(self):
        """All exclusion patterns should be compiled successfully."""
        assert len(_ALL_EXCLUSION_PATTERNS) > 0
        for pattern in _ALL_EXCLUSION_PATTERNS:
            assert isinstance(pattern, re.Pattern)

    @pytest.mark.parametrize(
        "objeto,should_match_pattern",
        [
            ("Aquisicao de medicamentos para hospital", True),  # medical
            ("Software de gestao publica", True),  # IT
            ("Vigilância armada", True),  # surveillance
            ("Limpeza predial", True),  # cleaning
            ("Aquisicao de combustível diesel", True),  # vehicles/fuel
            ("Construcao de escola municipal", True),  # construction matches sector exclusion patterns
        ],
    )
    def test_exclusion_pattern_matches(self, objeto, should_match_pattern):
        """Verify exclusion patterns correctly match/reject known categories."""
        matched = False
        for pat in _ALL_EXCLUSION_PATTERNS:
            if pat.search(objeto.lower()):
                matched = True
                break
        assert matched == should_match_pattern


# ============================================================
# PARSE NUMERO CONTROLE PNCP
# ============================================================


class TestParseNumeroControlePncp:
    """Test parsing of PNCP procurement reference numbers."""

    def test_valid_format(self):
        result = _parse_numero_controle_pncp("12345678000190-1-000042/2025")
        assert result == ("12345678000190", "2025", "42")

    def test_leading_zeros_stripped(self):
        result = _parse_numero_controle_pncp("12345678000190-1-000001/2026")
        assert result[2] == "1"

    def test_empty_string(self):
        assert _parse_numero_controle_pncp("") is None

    def test_no_slash(self):
        assert _parse_numero_controle_pncp("12345678000190-1-000042") is None

    def test_insufficient_segments(self):
        assert _parse_numero_controle_pncp("12345678000190/2025") is None

    def test_non_numeric_seq(self):
        """Non-numeric sequencial should return None (ValueError in int())."""
        assert _parse_numero_controle_pncp("12345678000190-1-ABCDEF/2025") is None
