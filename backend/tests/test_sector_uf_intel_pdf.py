"""tests/test_sector_uf_intel_pdf.py — INTEL-REPORT-002: Panorama Setorial × UF PDF tests.

Tests:
  1. Helper functions (_sanitize, _fmt_currency, _fmt_int, _fmt_pct, _format_date, _trunc)
  2. Section builders with representative mock data
  3. generate_sector_uf_report — valid entity_key → %PDF BytesIO
  4. generate_sector_uf_report — invalid entity_key formats → ValueError
  5. generate_sector_uf_report — RPC returns no data → ValueError
  6. generate_sector_uf_report — empty sections (no fornecedores/orgaos) → PDF still generated
"""

from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

MINIMAL_RPC_PAYLOAD = {
    "sector": "limpeza",
    "uf": "SP",
    "window_months": 24,
    "window_start": "2024-05-08",
    "total_contracts": 42,
    "total_value": 5_800_000.0,
    "avg_ticket": 138_095.0,
    "median_ticket": 95_000.0,
    "p90_ticket": 320_000.0,
    "data_primeiro_contrato": "2024-06-01",
    "data_ultimo_contrato": "2026-05-01",
    "top_fornecedores": [
        {
            "ni_fornecedor": "12.345.678/0001-99",
            "nome_fornecedor": "Limpeza Geral LTDA",
            "count": 10,
            "valor_total": 1_500_000.0,
            "avg_ticket": 150_000.0,
        },
        {
            "ni_fornecedor": "98.765.432/0001-11",
            "nome_fornecedor": "Higienização SP ME",
            "count": 5,
            "valor_total": 800_000.0,
            "avg_ticket": 160_000.0,
        },
    ],
    "distribuicao_esfera": [
        {"esfera": "M", "count": 30, "valor_total": 3_500_000.0},
        {"esfera": "E", "count": 12, "valor_total": 2_300_000.0},
    ],
    "serie_temporal": [
        {"mes": "2024-05", "count": 3, "valor_total": 450_000.0},
        {"mes": "2024-06", "count": 4, "valor_total": 600_000.0},
        {"mes": "2024-07", "count": 2, "valor_total": 300_000.0},
    ],
    "top_orgaos": [
        {
            "orgao_cnpj": "01.000.001/0001-01",
            "orgao_nome": "Prefeitura de SP",
            "count": 15,
            "valor_total": 2_000_000.0,
        },
    ],
    "top_objetos": [
        {
            "objeto_resumo": "Contratação de serviços de limpeza e conservação predial",
            "count": 20,
            "valor_total": 3_000_000.0,
        },
        {
            "objeto_resumo": "Higienização de ambientes",
            "count": 10,
            "valor_total": 1_500_000.0,
        },
    ],
    "generated_at": "2026-05-08T20:00:00+00:00",
}

EMPTY_SECTIONS_PAYLOAD = {
    **MINIMAL_RPC_PAYLOAD,
    "top_fornecedores": [],
    "distribuicao_esfera": [],
    "serie_temporal": [],
    "top_orgaos": [],
    "top_objetos": [],
    "total_contracts": 0,
    "total_value": 0.0,
}


def _make_mock_sector():
    sector = SimpleNamespace()
    sector.name = "Limpeza e Conservação"
    sector.keywords = {"limpeza", "higienização", "conservação"}
    return sector


def _make_mock_db(payload=None):
    if payload is None:
        payload = MINIMAL_RPC_PAYLOAD
    mock_db = MagicMock()
    mock_result = MagicMock()
    mock_result.data = [{"sector_uf_intel": payload}]
    mock_db.rpc.return_value.execute.return_value = mock_result
    return mock_db


# ---------------------------------------------------------------------------
# Tests: helper functions
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_sanitize_none_returns_empty(self):
        from pdf_generator_sector_uf_report import _sanitize
        assert _sanitize(None) == ""

    def test_sanitize_strips_control_chars(self):
        from pdf_generator_sector_uf_report import _sanitize
        result = _sanitize("hello\x00world\x08!")
        assert "\x00" not in result
        assert "\x08" not in result
        assert "hello" in result

    def test_sanitize_escapes_html(self):
        from pdf_generator_sector_uf_report import _sanitize
        result = _sanitize("<script>alert(1)</script>")
        assert "<script>" not in result
        assert "&lt;" in result

    def test_fmt_currency_none(self):
        from pdf_generator_sector_uf_report import _fmt_currency
        assert _fmt_currency(None) == "—"

    def test_fmt_currency_zero(self):
        from pdf_generator_sector_uf_report import _fmt_currency
        assert _fmt_currency(0) == "R$ 0,00"

    def test_fmt_currency_positive(self):
        from pdf_generator_sector_uf_report import _fmt_currency
        result = _fmt_currency(1_500_000.0)
        assert "1.500.000" in result
        assert "R$" in result

    def test_fmt_currency_invalid(self):
        from pdf_generator_sector_uf_report import _fmt_currency
        assert _fmt_currency("not_a_number") == "—"

    def test_fmt_int_valid(self):
        from pdf_generator_sector_uf_report import _fmt_int
        assert _fmt_int(1234) == "1.234"

    def test_fmt_int_invalid(self):
        from pdf_generator_sector_uf_report import _fmt_int
        assert _fmt_int(None) == "—"

    def test_fmt_pct_valid(self):
        from pdf_generator_sector_uf_report import _fmt_pct
        assert _fmt_pct(42.5) == "42.5%"

    def test_fmt_pct_none(self):
        from pdf_generator_sector_uf_report import _fmt_pct
        assert _fmt_pct(None) == "—"

    def test_trunc_short_string_unchanged(self):
        from pdf_generator_sector_uf_report import _trunc
        s = "hello"
        assert _trunc(s) == s

    def test_trunc_long_string_truncated(self):
        from pdf_generator_sector_uf_report import _trunc
        s = "a" * 200
        result = _trunc(s, max_chars=80)
        assert len(result) <= 80
        assert result.endswith("…")

    def test_format_date_valid_iso(self):
        from pdf_generator_sector_uf_report import _format_date
        assert _format_date("2026-05-08") == "08/05/2026"

    def test_format_date_none(self):
        from pdf_generator_sector_uf_report import _format_date
        assert _format_date(None) == "—"

    def test_format_date_with_time_component(self):
        from pdf_generator_sector_uf_report import _format_date
        result = _format_date("2026-05-08T10:30:00")
        assert result == "08/05/2026"


# ---------------------------------------------------------------------------
# Tests: section builders (pure — no db needed)
# ---------------------------------------------------------------------------

class TestSectionBuilders:
    def setup_method(self):
        from pdf_generator_sector_uf_report import _build_styles
        self.data = {**MINIMAL_RPC_PAYLOAD, "sector_label": "Limpeza e Conservação"}
        self.styles = _build_styles()

    def test_build_cover_returns_non_empty_list(self):
        from pdf_generator_sector_uf_report import _build_cover
        story = _build_cover(self.data, self.styles)
        assert isinstance(story, list)
        assert len(story) > 0

    def test_build_cover_includes_page_break(self):
        from pdf_generator_sector_uf_report import _build_cover
        from reportlab.platypus import PageBreak
        story = _build_cover(self.data, self.styles)
        assert any(isinstance(el, PageBreak) for el in story)

    def test_build_executive_summary_returns_list(self):
        from pdf_generator_sector_uf_report import _build_executive_summary
        story = _build_executive_summary(self.data, self.styles)
        assert isinstance(story, list)
        assert len(story) > 0

    def test_build_top_fornecedores_with_data(self):
        from pdf_generator_sector_uf_report import _build_top_fornecedores
        story = _build_top_fornecedores(self.data, self.styles)
        assert isinstance(story, list)
        assert len(story) > 0

    def test_build_top_fornecedores_empty_list(self):
        from pdf_generator_sector_uf_report import _build_top_fornecedores
        data = {**self.data, "top_fornecedores": []}
        story = _build_top_fornecedores(data, self.styles)
        assert isinstance(story, list)

    def test_build_top_fornecedores_none(self):
        from pdf_generator_sector_uf_report import _build_top_fornecedores
        data = {**self.data, "top_fornecedores": None}
        story = _build_top_fornecedores(data, self.styles)
        assert isinstance(story, list)

    def test_build_cover_without_uf(self):
        from pdf_generator_sector_uf_report import _build_cover
        data = {**self.data, "uf": ""}
        story = _build_cover(data, self.styles)
        assert isinstance(story, list)
        assert len(story) > 0


# ---------------------------------------------------------------------------
# Tests: generate_sector_uf_report — integration (mocked db + sectors)
# ---------------------------------------------------------------------------

class TestGenerateSectorUfReport:
    def test_valid_entity_key_returns_pdf_bytes(self):
        from pdf_generator_sector_uf_report import generate_sector_uf_report

        mock_db = _make_mock_db()
        with patch("sectors.get_sector", return_value=_make_mock_sector()):
            result = generate_sector_uf_report(mock_db, "limpeza:SP")

        assert isinstance(result, BytesIO)
        content = result.getvalue()
        assert content[:4] == b"%PDF", f"Expected PDF magic bytes, got {content[:4]!r}"
        assert len(content) > 1000

    def test_returned_bytesio_seeked_to_start(self):
        from pdf_generator_sector_uf_report import generate_sector_uf_report

        mock_db = _make_mock_db()
        with patch("sectors.get_sector", return_value=_make_mock_sector()):
            result = generate_sector_uf_report(mock_db, "limpeza:SP")

        assert result.tell() == 0

    def test_empty_sections_still_generates_pdf(self):
        from pdf_generator_sector_uf_report import generate_sector_uf_report

        mock_db = _make_mock_db(EMPTY_SECTIONS_PAYLOAD)
        with patch("sectors.get_sector", return_value=_make_mock_sector()):
            result = generate_sector_uf_report(mock_db, "limpeza:RJ")

        content = result.getvalue()
        assert content[:4] == b"%PDF"

    def test_entity_key_without_colon_raises(self):
        from pdf_generator_sector_uf_report import generate_sector_uf_report

        with pytest.raises(ValueError, match="Invalid entity_key"):
            generate_sector_uf_report(MagicMock(), "limpeza_SP")

    def test_entity_key_empty_sector_raises(self):
        from pdf_generator_sector_uf_report import generate_sector_uf_report

        with pytest.raises(ValueError, match="Invalid entity_key"):
            generate_sector_uf_report(MagicMock(), ":SP")

    def test_entity_key_invalid_uf_length_raises(self):
        from pdf_generator_sector_uf_report import generate_sector_uf_report

        with pytest.raises(ValueError, match="Invalid entity_key"):
            generate_sector_uf_report(MagicMock(), "limpeza:SPA")

    def test_rpc_returns_empty_list_raises(self):
        from pdf_generator_sector_uf_report import generate_sector_uf_report

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.data = []
        mock_db.rpc.return_value.execute.return_value = mock_result

        with patch("sectors.get_sector", return_value=_make_mock_sector()):
            with pytest.raises(ValueError, match="no data"):
                generate_sector_uf_report(mock_db, "limpeza:SP")

    def test_rpc_returns_none_raises(self):
        from pdf_generator_sector_uf_report import generate_sector_uf_report

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.data = None
        mock_db.rpc.return_value.execute.return_value = mock_result

        with patch("sectors.get_sector", return_value=_make_mock_sector()):
            with pytest.raises(ValueError):
                generate_sector_uf_report(mock_db, "limpeza:SP")

    def test_sector_not_found_raises(self):
        from pdf_generator_sector_uf_report import generate_sector_uf_report

        with patch(
            "sectors.get_sector",
            side_effect=KeyError("setor_inexistente"),
        ):
            with pytest.raises(ValueError, match="Cannot resolve keywords"):
                generate_sector_uf_report(MagicMock(), "setor_inexistente:SP")

    def test_rpc_called_with_correct_params(self):
        from pdf_generator_sector_uf_report import generate_sector_uf_report

        mock_db = _make_mock_db()
        with patch("sectors.get_sector", return_value=_make_mock_sector()):
            generate_sector_uf_report(mock_db, "limpeza:sp")  # lowercase uf normalized

        mock_db.rpc.assert_called_once_with(
            "sector_uf_intel",
            {
                "p_sector": "limpeza",
                "p_keywords": list(_make_mock_sector().keywords),
                "p_uf": "SP",  # normalized to upper
                "p_window_months": 24,
            },
        )

    def test_rpc_dict_payload_direct(self):
        """PostgREST can return raw dict instead of list-wrapped JSONB."""
        from pdf_generator_sector_uf_report import generate_sector_uf_report

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.data = MINIMAL_RPC_PAYLOAD  # dict directly
        mock_db.rpc.return_value.execute.return_value = mock_result

        with patch("sectors.get_sector", return_value=_make_mock_sector()):
            result = generate_sector_uf_report(mock_db, "limpeza:SP")

        assert result.getvalue()[:4] == b"%PDF"
