"""Tests for CNAE to sector mapping (GTM-004 AC6)."""

import logging

import pytest
from utils.cnae_mapping import map_cnae_to_setor, get_setor_name


class TestMapCnaeToSetor:
    """Test CNAE code to sector mapping."""

    @pytest.mark.parametrize("cnae,expected", [
        # Engenharia / Construção
        ("4120", "engenharia"),
        ("4211", "engenharia"),
        ("4399", "engenharia"),
        ("7112", "engenharia"),
        # Vestuário
        ("4781", "vestuario"),
        ("1412", "vestuario"),
        # Facilities / Prediais
        ("8121", "servicos_prediais"),
        # Vigilância
        ("8011", "vigilancia"),
        # Saúde
        ("3250", "saude"),
        # Equipamentos
        ("2710", "equipamentos"),
        # Alimentos
        ("1011", "alimentos"),
        ("1091", "alimentos"),
        # TI
        ("6201", "informatica"),
        ("6202", "informatica"),
        # Transporte
        ("4924", "transporte"),
    ])
    def test_cnae_mappings(self, cnae: str, expected: str):
        """AC6: All top 10 CNAEs map to correct sector."""
        assert map_cnae_to_setor(cnae) == expected

    @pytest.mark.parametrize("cnae,expected", [
        ("4781-4/00", "vestuario"),
        ("8121-4/00", "servicos_prediais"),
        ("6201-5/01", "informatica"),
    ])
    def test_formatted_cnae(self, cnae: str, expected: str):
        """Handles CNAE in full format (e.g., 4781-4/00)."""
        assert map_cnae_to_setor(cnae) == expected

    @pytest.mark.parametrize("cnae,expected", [
        ("47814", "vestuario"),
        ("81214", "servicos_prediais"),
    ])
    def test_five_digit_cnae(self, cnae: str, expected: str):
        """Handles 5-digit CNAE prefix format."""
        assert map_cnae_to_setor(cnae) == expected

    def test_unknown_cnae_falls_back_to_geral(self):
        """Unknown CNAE falls back to geral (not vestuario)."""
        assert map_cnae_to_setor("9999") == "geral"
        assert map_cnae_to_setor("0000") == "geral"

    def test_unknown_cnae_emits_warning(self, caplog):
        """Unknown CNAE emits a warning log so gaps can be tracked (#599)."""
        with caplog.at_level(logging.WARNING, logger="utils.cnae_mapping"):
            result = map_cnae_to_setor("9999")
        assert result == "geral"
        assert any("cnae_not_mapped" in record.message for record in caplog.records)

    def test_unparseable_cnae_emits_warning(self, caplog):
        """Unparseable CNAE (too short / no digits) emits a warning log."""
        with caplog.at_level(logging.WARNING, logger="utils.cnae_mapping"):
            result = map_cnae_to_setor("abc")
        assert result == "geral"
        assert any("cnae_not_mapped" in record.message for record in caplog.records)

    def test_empty_input(self):
        """Empty or very short input falls back to geral."""
        assert map_cnae_to_setor("") == "geral"
        assert map_cnae_to_setor("12") == "geral"
        assert map_cnae_to_setor("abc") == "geral"

    def test_whitespace_handling(self):
        """Handles leading/trailing whitespace."""
        assert map_cnae_to_setor("  4781  ") == "vestuario"
        assert map_cnae_to_setor(" 8121-4/00 ") == "servicos_prediais"

    def test_text_with_cnae(self):
        """Handles CNAE embedded in description text."""
        # The function extracts first 4 digits
        assert map_cnae_to_setor("4781-4/00 — Comércio varejista") == "vestuario"


class TestGetSetorName:
    """Test sector name lookup."""

    def test_known_sectors(self):
        """Returns correct names for known sectors."""
        assert get_setor_name("engenharia") == "Engenharia, Projetos e Obras"
        assert get_setor_name("vestuario") == "Vestuário e Uniformes"
        assert get_setor_name("servicos_prediais") == "Serviços Prediais e Facilities"
        assert get_setor_name("equipamentos") == "Equipamentos"
        assert get_setor_name("alimentos") == "Alimentos e Merenda"
        assert get_setor_name("informatica") == "TI e Sistemas"
        assert get_setor_name("saude") == "Saúde e Hospitalar"
        assert get_setor_name("transporte") == "Transporte e Logística"

    def test_unknown_sector(self):
        """Falls back to title-cased ID for unknown sectors."""
        assert get_setor_name("unknown_sector") == "Unknown Sector"
