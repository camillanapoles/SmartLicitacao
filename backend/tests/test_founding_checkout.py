"""STORY-BIZ-001: tests for founding customer checkout route + webhook handlers."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Enable Stripe key + founding price ID before importing the route.
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_fake")
os.environ.setdefault("FOUNDING_ONE_TIME_PRICE_ID", "price_test_founding_lifetime")

import routes.founding as founding_module  # noqa: E402

from routes.founding import (  # noqa: E402
    FoundingCheckoutRequest,
    _is_valid_cnpj_check_digits,
    _client_ip,
    router as founding_router,
)
from webhooks.handlers.founding import (  # noqa: E402
    mark_founding_lead_abandoned,
    mark_founding_lead_completed,
)


# ---------------------------------------------------------------------------
# CNPJ validator
# ---------------------------------------------------------------------------


def test_cnpj_validator_accepts_known_valid():
    # Well-known public CNPJ of the Brazilian Federal Treasury (valid check digits)
    assert _is_valid_cnpj_check_digits("00394460000141")


def test_cnpj_validator_rejects_wrong_check_digit():
    assert not _is_valid_cnpj_check_digits("00394460000199")


def test_cnpj_validator_rejects_all_equal_digits():
    assert not _is_valid_cnpj_check_digits("00000000000000")
    assert not _is_valid_cnpj_check_digits("11111111111111")


def test_cnpj_validator_rejects_non_numeric():
    assert not _is_valid_cnpj_check_digits("abc39446000141")


def test_cnpj_validator_rejects_wrong_length():
    assert not _is_valid_cnpj_check_digits("003944600001")


# ---------------------------------------------------------------------------
# Pydantic payload validation
# ---------------------------------------------------------------------------


def _valid_payload_args(**overrides):
    base = {
        "email": "founder@empresa.com.br",
        "nome": "Maria Silva",
        "cnpj": "00.394.460/0001-41",
        "razao_social": "Tesouro Nacional Brasil",
        "motivo": (
            "Nossa empresa atua ha 5 anos em licitacoes B2G no setor de engenharia "
            "rodoviaria e vemos no SmartLic um diferencial competitivo para ganhar "
            "escala em monitoramento de editais e qualificacao rapida de oportunidades."
        ),
    }
    base.update(overrides)
    return base


def test_payload_accepts_masked_cnpj():
    req = FoundingCheckoutRequest(**_valid_payload_args())
    assert req.cnpj == "00394460000141"


def test_payload_rejects_short_motivo():
    with pytest.raises(Exception):
        FoundingCheckoutRequest(**_valid_payload_args(motivo="muito curto"))


def test_payload_rejects_invalid_cnpj():
    with pytest.raises(Exception):
        FoundingCheckoutRequest(**_valid_payload_args(cnpj="11.111.111/1111-11"))


def test_payload_rejects_bad_email():
    with pytest.raises(Exception):
        FoundingCheckoutRequest(**_valid_payload_args(email="not-an-email"))


def test_payload_lowercases_email():
    req = FoundingCheckoutRequest(**_valid_payload_args(email="Mixed.CASE@EXAMPLE.COM"))
    assert req.email == "mixed.case@example.com"


# ---------------------------------------------------------------------------
# _client_ip helper
# ---------------------------------------------------------------------------


def test_client_ip_prefers_xff_header():
    req = MagicMock()
    req.headers = {"x-forwarded-for": "203.0.113.1, 10.0.0.2"}
    req.client = MagicMock(host="10.0.0.3")
    assert _client_ip(req) == "203.0.113.1"


def test_client_ip_falls_back_to_client_host():
    req = MagicMock()
    req.headers = {}
    req.client = MagicMock(host="10.0.0.3")
    assert _client_ip(req) == "10.0.0.3"


def test_client_ip_returns_unknown_when_missing():
    req = MagicMock()
    req.headers = {}
    req.client = None
    assert _client_ip(req) == "unknown"


# ---------------------------------------------------------------------------
# Webhook handlers
# ---------------------------------------------------------------------------


def _mk_table_mock(data):
    tbl = MagicMock()
    tbl.table.return_value = tbl
    tbl.update.return_value = tbl
    tbl.eq.return_value = tbl
    tbl.execute.return_value = MagicMock(data=data)
    return tbl


def test_mark_founding_lead_completed_skips_non_founding_session():
    sb = _mk_table_mock(data=[])
    session = {"id": "cs_test_123", "metadata": {"source": "regular"}, "customer": "cus_1"}
    mark_founding_lead_completed(sb, session)
    # Handler exits early — no table access
    assert not sb.update.called


def test_mark_founding_lead_completed_updates_row():
    sb = _mk_table_mock(data=[{"id": "lead-1"}])
    session = {
        "id": "cs_test_123",
        "metadata": {"source": "founding"},
        "customer": "cus_42",
    }
    mark_founding_lead_completed(sb, session)
    sb.table.assert_called_with("founding_leads")
    sb.update.assert_called_once()
    update_payload = sb.update.call_args.args[0]
    assert update_payload["checkout_status"] == "completed"
    assert update_payload["stripe_customer_id"] == "cus_42"
    assert "completed_at" in update_payload


def test_mark_founding_lead_abandoned_updates_only_pending_rows():
    sb = _mk_table_mock(data=[{"id": "lead-1"}])
    session = {"id": "cs_test_987", "metadata": {"source": "founding"}}
    mark_founding_lead_abandoned(sb, session)
    # Second .eq narrows by pending status — confirm it was called
    assert sb.eq.call_count == 2
    calls = [c.args for c in sb.eq.call_args_list]
    assert ("checkout_session_id", "cs_test_987") in calls
    assert ("checkout_status", "pending") in calls


def test_mark_founding_lead_abandoned_skips_non_founding():
    sb = _mk_table_mock(data=[])
    mark_founding_lead_abandoned(sb, {"id": "cs", "metadata": {"source": "x"}})
    assert not sb.update.called


def test_mark_founding_lead_completed_survives_db_error():
    sb = MagicMock()
    sb.table.side_effect = Exception("db unreachable")
    # Should not raise
    mark_founding_lead_completed(
        sb,
        {"id": "cs_test", "metadata": {"source": "founding"}, "customer": "cus"},
    )


# ---------------------------------------------------------------------------
# Route integration (rate-limit + validation errors without hitting Stripe)
# ---------------------------------------------------------------------------


@pytest.fixture
def app_with_founding():
    app = FastAPI()
    app.include_router(founding_router, prefix="/v1")
    return app


def test_founding_route_rejects_short_motivo(app_with_founding):
    client = TestClient(app_with_founding)
    payload = _valid_payload_args(motivo="curto")
    r = client.post("/v1/founding/checkout", json=payload)
    assert r.status_code == 422


def test_founding_route_rejects_invalid_cnpj(app_with_founding):
    client = TestClient(app_with_founding)
    payload = _valid_payload_args(cnpj="11.111.111/1111-11")
    r = client.post("/v1/founding/checkout", json=payload)
    assert r.status_code == 422


@patch("routes.founding.get_supabase")
def test_founding_route_returns_409_when_email_already_has_profile(
    mock_get_supabase, app_with_founding
):
    fake_sb = MagicMock()
    fake_sb.table.return_value = fake_sb
    fake_sb.select.return_value = fake_sb
    fake_sb.eq.return_value = fake_sb
    fake_sb.limit.return_value = fake_sb
    fake_sb.execute.return_value = MagicMock(data=[{"id": "existing-user"}])

    # BIZ-FOUND-002: route now gates on check_founding_availability() RPC
    # before the profile lookup. Wire RPC -> available=true so this test
    # still hits the 409 path it cares about.
    fake_sb.rpc.return_value = MagicMock(execute=MagicMock(return_value=MagicMock(data=[
        {
            "available": True,
            "seats_remaining": 49,
            "seats_total": 50,
            "deadline_at": "2026-05-30T23:59:59-03:00",
            "paused": False,
            "reason": "available",
        }
    ])))

    mock_get_supabase.return_value = fake_sb

    client = TestClient(app_with_founding)
    r = client.post("/v1/founding/checkout", json=_valid_payload_args())
    assert r.status_code == 409
    assert "já possui conta" in r.json()["detail"].lower() or "ja possui" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# #783 — v2 lifetime one-time payment tests
# ---------------------------------------------------------------------------


class _TableChain:
    """Differentiates DB calls by table + operation to avoid mock collision."""

    def __init__(self):
        self._table = None
        self._op = None
        self._rpc_result = {
            "available": True,
            "seats_remaining": 48,
            "seats_total": 50,
            "deadline_at": "2026-05-30T23:59:59-03:00",
            "paused": False,
            "reason": "available",
            "offer_mode": "lifetime",
            "price_brl_cents": 99700,
        }

    def table(self, name):
        self._table = name
        return self

    def select(self, *a, **kw):
        self._op = "select"
        return self

    def insert(self, *a, **kw):
        self._op = "insert"
        return self

    def update(self, *a, **kw):
        self._op = "update"
        return self

    def eq(self, *a, **kw):
        return self

    def limit(self, *a, **kw):
        return self

    def rpc(self, name):
        return self

    def execute(self):
        if self._table == "profiles" and self._op == "select":
            return MagicMock(data=[])  # no existing profile
        if self._table == "founding_leads" and self._op == "insert":
            return MagicMock(data=[{"id": "lead-uuid-v2-001"}])
        if self._table == "founding_leads" and self._op == "update":
            return MagicMock(data=[])
        # RPC call (table is None)
        return MagicMock(data=[self._rpc_result])


def _make_stripe_session_mock(**extra_metadata):
    session = MagicMock()
    session.id = "cs_test_v2_lifetime"
    session.url = "https://checkout.stripe.com/pay/cs_test_v2_lifetime"
    return session


def _v2_checkout_setup(app_with_founding, monkeypatch, price_id="price_test_founding_lifetime"):
    """Returns (client, stripe_create_mock)."""
    chain = _TableChain()

    with patch("routes.founding.get_supabase", return_value=chain):
        if price_id:
            monkeypatch.setenv("FOUNDING_ONE_TIME_PRICE_ID", price_id)
        else:
            monkeypatch.delenv("FOUNDING_ONE_TIME_PRICE_ID", raising=False)

        import stripe as stripe_lib
        stripe_create_mock = MagicMock(return_value=_make_stripe_session_mock())
        monkeypatch.setattr(stripe_lib.checkout.Session, "create", stripe_create_mock)

        client = TestClient(app_with_founding, raise_server_exceptions=False)
        r = client.post("/v1/founding/checkout", json=_valid_payload_args())
        return r, stripe_create_mock


@patch("routes.founding.get_supabase")
def test_checkout_v2_uses_mode_payment(mock_get_supabase, app_with_founding, monkeypatch):
    chain = _TableChain()
    mock_get_supabase.return_value = chain

    import stripe as stripe_lib

    stripe_create_mock = MagicMock(return_value=_make_stripe_session_mock())
    monkeypatch.setattr(stripe_lib.checkout.Session, "create", stripe_create_mock)

    client = TestClient(app_with_founding)
    r = client.post("/v1/founding/checkout", json=_valid_payload_args())

    assert r.status_code == 200
    call_kwargs = stripe_create_mock.call_args.kwargs
    assert call_kwargs["mode"] == "payment"


@patch("routes.founding.get_supabase")
def test_checkout_v2_uses_card_and_boleto(mock_get_supabase, app_with_founding, monkeypatch):
    chain = _TableChain()
    mock_get_supabase.return_value = chain

    import stripe as stripe_lib

    stripe_create_mock = MagicMock(return_value=_make_stripe_session_mock())
    monkeypatch.setattr(stripe_lib.checkout.Session, "create", stripe_create_mock)

    client = TestClient(app_with_founding)
    client.post("/v1/founding/checkout", json=_valid_payload_args())

    call_kwargs = stripe_create_mock.call_args.kwargs
    assert set(call_kwargs["payment_method_types"]) == {"card", "boleto"}


@patch("routes.founding.get_supabase")
def test_checkout_v2_metadata_contains_offer_fields(mock_get_supabase, app_with_founding, monkeypatch):
    chain = _TableChain()
    mock_get_supabase.return_value = chain

    import stripe as stripe_lib

    stripe_create_mock = MagicMock(return_value=_make_stripe_session_mock())
    monkeypatch.setattr(stripe_lib.checkout.Session, "create", stripe_create_mock)

    client = TestClient(app_with_founding)
    client.post("/v1/founding/checkout", json=_valid_payload_args())

    call_kwargs = stripe_create_mock.call_args.kwargs
    meta = call_kwargs["metadata"]
    assert meta["offer_version"] == "v2_lifetime"
    assert meta["offer_mode"] == "lifetime"
    assert meta["price_brl_cents"] == "99700"
    assert "checkout_source" in meta
    assert "founding_lead_id" in meta


@patch("routes.founding.get_supabase")
def test_checkout_v2_no_discounts_in_session(mock_get_supabase, app_with_founding, monkeypatch):
    chain = _TableChain()
    mock_get_supabase.return_value = chain

    import stripe as stripe_lib

    stripe_create_mock = MagicMock(return_value=_make_stripe_session_mock())
    monkeypatch.setattr(stripe_lib.checkout.Session, "create", stripe_create_mock)

    client = TestClient(app_with_founding)
    client.post("/v1/founding/checkout", json=_valid_payload_args())

    call_kwargs = stripe_create_mock.call_args.kwargs
    assert "discounts" not in call_kwargs


@patch("routes.founding.get_supabase")
def test_checkout_v2_returns_500_when_price_id_not_configured(
    mock_get_supabase, app_with_founding, monkeypatch
):
    chain = _TableChain()
    mock_get_supabase.return_value = chain

    monkeypatch.delenv("FOUNDING_ONE_TIME_PRICE_ID", raising=False)
    client = TestClient(app_with_founding, raise_server_exceptions=False)
    r = client.post("/v1/founding/checkout", json=_valid_payload_args())

    assert r.status_code == 500


@patch("routes.founding.get_supabase")
def test_checkout_v2_returns_410_when_cap_reached(mock_get_supabase, app_with_founding):
    chain = _TableChain()
    chain._rpc_result = {
        "available": False,
        "seats_remaining": 0,
        "seats_total": 50,
        "deadline_at": None,
        "paused": False,
        "reason": "founding_cap_reached",
        "offer_mode": "lifetime",
        "price_brl_cents": 99700,
    }
    mock_get_supabase.return_value = chain

    client = TestClient(app_with_founding)
    r = client.post("/v1/founding/checkout", json=_valid_payload_args())

    assert r.status_code == 410
    assert r.json()["detail"]["error_code"] == "founding_cap_reached"


@patch("routes.founding.get_supabase")
def test_checkout_v2_response_includes_payment_mode_lifetime(
    mock_get_supabase, app_with_founding, monkeypatch
):
    chain = _TableChain()
    mock_get_supabase.return_value = chain

    import stripe as stripe_lib

    monkeypatch.setattr(
        stripe_lib.checkout.Session, "create", MagicMock(return_value=_make_stripe_session_mock())
    )

    client = TestClient(app_with_founding)
    r = client.post("/v1/founding/checkout", json=_valid_payload_args())

    assert r.status_code == 200
    body = r.json()
    assert body["payment_mode"] == "lifetime"
    assert "checkout_url" in body
    assert "lead_id" in body


@patch("routes.founding.get_supabase")
def test_checkout_v2_checkout_source_from_query_param(
    mock_get_supabase, app_with_founding, monkeypatch
):
    chain = _TableChain()
    mock_get_supabase.return_value = chain

    import stripe as stripe_lib

    stripe_create_mock = MagicMock(return_value=_make_stripe_session_mock())
    monkeypatch.setattr(stripe_lib.checkout.Session, "create", stripe_create_mock)

    client = TestClient(app_with_founding)
    client.post(
        "/v1/founding/checkout?src=email_campaign",
        json=_valid_payload_args(),
    )

    call_kwargs = stripe_create_mock.call_args.kwargs
    assert call_kwargs["metadata"]["checkout_source"] == "email_campaign"
