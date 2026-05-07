"""Tests for POST /v1/lead-capture — REPO-004 (#756) schema extension.

Covers:
- All 8 valid sources return 200
- Invalid source returns 422 (Pydantic Literal validation)
- mensagem > 500 chars returns 422 (Field max_length)
- modalidade_interesse invalid value returns 422
- Backward compat: 3 legacy sources + old field-only payloads still work
- New optional fields are accepted and passed through
- Invalid email format returns 400
"""

import pytest
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from startup.app_factory import create_app
    app = create_app()
    return TestClient(app)


@pytest.fixture
def mock_supabase():
    """Mock Supabase client — patches supabase_client.get_supabase."""
    mock = Mock()
    mock.table.return_value = mock
    mock.upsert.return_value = mock
    mock.execute.return_value = Mock(data=[{"id": "test-uuid"}])
    return mock


def _post(client, payload):
    """Helper: POST to /v1/lead-capture with payload."""
    return client.post("/v1/lead-capture", json=payload)


# ---------------------------------------------------------------------------
# Valid sources — all 8 must return 200
# ---------------------------------------------------------------------------

ALL_SOURCES = [
    "calculadora",
    "cnpj",
    "alertas",
    "consultoria",
    "radar",
    "report",
    "intel",
    "diagnostico",
]


class TestAllSourcesAccepted:
    @pytest.mark.parametrize("source", ALL_SOURCES)
    def test_valid_source_returns_200(self, client, mock_supabase, source):
        with patch("supabase_client.get_supabase", return_value=mock_supabase):
            resp = _post(client, {"email": "test@example.com", "source": source})
        assert resp.status_code == 200
        assert resp.json() == {"success": True}


# ---------------------------------------------------------------------------
# Validation — bad source → 422
# ---------------------------------------------------------------------------

class TestSourceValidation:
    def test_invalid_source_returns_422(self, client):
        resp = _post(client, {"email": "test@example.com", "source": "unknown_source"})
        assert resp.status_code == 422

    def test_empty_source_returns_422(self, client):
        resp = _post(client, {"email": "test@example.com", "source": ""})
        assert resp.status_code == 422

    def test_missing_source_returns_422(self, client):
        resp = _post(client, {"email": "test@example.com"})
        assert resp.status_code == 422

    def test_missing_email_returns_422(self, client):
        resp = _post(client, {"source": "calculadora"})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# mensagem max_length = 500
# ---------------------------------------------------------------------------

class TestMensagemValidation:
    def test_mensagem_at_max_length_accepted(self, client, mock_supabase):
        with patch("supabase_client.get_supabase", return_value=mock_supabase):
            resp = _post(client, {
                "email": "test@example.com",
                "source": "diagnostico",
                "mensagem": "a" * 500,
            })
        assert resp.status_code == 200

    def test_mensagem_over_max_length_returns_422(self, client):
        resp = _post(client, {
            "email": "test@example.com",
            "source": "diagnostico",
            "mensagem": "a" * 501,
        })
        assert resp.status_code == 422

    def test_mensagem_none_accepted(self, client, mock_supabase):
        with patch("supabase_client.get_supabase", return_value=mock_supabase):
            resp = _post(client, {
                "email": "test@example.com",
                "source": "diagnostico",
                "mensagem": None,
            })
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# modalidade_interesse validation
# ---------------------------------------------------------------------------

class TestModalidadeInteresse:
    @pytest.mark.parametrize("value", ["radar", "report", "intel", "nao_sei"])
    def test_valid_modalidade_accepted(self, client, mock_supabase, value):
        with patch("supabase_client.get_supabase", return_value=mock_supabase):
            resp = _post(client, {
                "email": "test@example.com",
                "source": "diagnostico",
                "modalidade_interesse": value,
            })
        assert resp.status_code == 200

    def test_invalid_modalidade_returns_422(self, client):
        resp = _post(client, {
            "email": "test@example.com",
            "source": "diagnostico",
            "modalidade_interesse": "outro",
        })
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Backward compatibility — legacy sources + legacy-only fields
# ---------------------------------------------------------------------------

class TestBackwardCompat:
    def test_calculadora_legacy_payload(self, client, mock_supabase):
        """Original calculadora payload still works unchanged."""
        with patch("supabase_client.get_supabase", return_value=mock_supabase):
            resp = _post(client, {
                "email": "legado@example.com",
                "source": "calculadora",
                "setor": "saude",
                "uf": "SP",
                "captured_at": "2026-05-07T12:00:00Z",
            })
        assert resp.status_code == 200

    def test_cnpj_legacy_payload(self, client, mock_supabase):
        """Original cnpj source payload still works."""
        with patch("supabase_client.get_supabase", return_value=mock_supabase):
            resp = _post(client, {
                "email": "legado@example.com",
                "source": "cnpj",
                "setor": "construcao",
            })
        assert resp.status_code == 200

    def test_alertas_legacy_payload(self, client, mock_supabase):
        """Original alertas source payload still works."""
        with patch("supabase_client.get_supabase", return_value=mock_supabase):
            resp = _post(client, {
                "email": "legado@example.com",
                "source": "alertas",
                "uf": "RJ",
            })
        assert resp.status_code == 200

    def test_minimal_payload_only_email_and_source(self, client, mock_supabase):
        """Minimal required fields work with any source."""
        with patch("supabase_client.get_supabase", return_value=mock_supabase):
            resp = _post(client, {"email": "min@example.com", "source": "radar"})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# New optional fields accepted (REPO-004)
# ---------------------------------------------------------------------------

class TestNewOptionalFields:
    def test_full_diagnostico_payload_accepted(self, client, mock_supabase):
        """Full diagnostico form payload with all new fields."""
        with patch("supabase_client.get_supabase", return_value=mock_supabase):
            resp = _post(client, {
                "email": "empresa@example.com",
                "source": "diagnostico",
                "nome": "João Silva",
                "empresa": "Acme Ltda",
                "cnpj": "12.345.678/0001-90",
                "telefone": "11999990000",
                "modalidade_interesse": "report",
                "mensagem": "Quero saber mais sobre relatórios de inteligência.",
                "utm_source": "google",
                "utm_campaign": "b2g-q2-2026",
                "referer_path": "/observatorio/licitacoes-ti",
                "setor": "tecnologia",
                "uf": "SP",
            })
        assert resp.status_code == 200

    def test_utm_fields_only(self, client, mock_supabase):
        """UTM fields alone work without other new fields."""
        with patch("supabase_client.get_supabase", return_value=mock_supabase):
            resp = _post(client, {
                "email": "utm@example.com",
                "source": "consultoria",
                "utm_source": "linkedin",
                "utm_campaign": "founders",
            })
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Invalid email → 400 (existing behavior, must remain)
# ---------------------------------------------------------------------------

class TestEmailValidation:
    def test_invalid_email_returns_400(self, client):
        with patch("supabase_client.get_supabase", return_value=Mock()):
            resp = _post(client, {"email": "not-an-email", "source": "calculadora"})
        assert resp.status_code == 400

    def test_empty_email_returns_400(self, client):
        with patch("supabase_client.get_supabase", return_value=Mock()):
            resp = _post(client, {"email": "", "source": "calculadora"})
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# DB failure — fail-open behavior preserved
# ---------------------------------------------------------------------------

class TestFailOpen:
    def test_db_failure_still_returns_success(self, client):
        """Route fails-open: DB errors logged but 200 returned."""
        mock_sb = Mock()
        mock_sb.table.side_effect = Exception("DB connection failed")
        with patch("supabase_client.get_supabase", return_value=mock_sb):
            resp = _post(client, {"email": "test@example.com", "source": "calculadora"})
        assert resp.status_code == 200
        assert resp.json() == {"success": True}
