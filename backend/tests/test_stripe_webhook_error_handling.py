"""Focused tests for Stripe webhook defensive error handling."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
import stripe
from fastapi import HTTPException


@pytest.fixture
def mock_request():
    request = AsyncMock()
    request.body = AsyncMock(return_value=b'{"id":"evt_test_123"}')
    request.headers = {"stripe-signature": "t=1234567890,v1=sensitive_sig"}
    return request


_DEFAULT_DATA_OBJECT = object()


def _event(
    *,
    event_id="evt_test_123",
    event_type="checkout.session.completed",
    data_object=_DEFAULT_DATA_OBJECT,
):
    event = Mock()
    event.id = event_id
    event.type = event_type
    event.data = Mock()
    event.data.object = (
        {"id": "cs_test_123"} if data_object is _DEFAULT_DATA_OBJECT else data_object
    )
    return event


@pytest.mark.asyncio
@patch("webhooks.stripe.STRIPE_WEBHOOK_SECRET", "whsec_test")
@patch("webhooks.stripe.get_supabase")
@patch("webhooks.stripe.logger")
@patch("webhooks.stripe.stripe.Webhook.construct_event")
async def test_signature_verification_error_logs_safely_before_db(
    mock_construct, mock_logger, mock_get_supabase, mock_request
):
    from webhooks.stripe import stripe_webhook

    mock_construct.side_effect = stripe.error.SignatureVerificationError(
        "No signatures found matching expected signature for payload secret_payload",
        "t=1234567890,v1=sensitive_sig",
    )

    with pytest.raises(HTTPException) as exc_info:
        await stripe_webhook(mock_request)

    assert exc_info.value.status_code == 400
    mock_get_supabase.assert_not_called()

    log_text = " ".join(str(call) for call in mock_logger.warning.call_args_list)
    assert "SignatureVerificationError" in log_text
    assert "sensitive_sig" not in log_text
    assert "secret_payload" not in log_text


@pytest.mark.asyncio
@patch("webhooks.stripe.STRIPE_WEBHOOK_SECRET", "whsec_test")
@patch("webhooks.stripe.get_supabase")
@patch("webhooks.stripe.stripe.Webhook.construct_event")
async def test_invalid_payload_returns_400_before_db(
    mock_construct, mock_get_supabase, mock_request
):
    from webhooks.stripe import stripe_webhook

    mock_construct.side_effect = ValueError("raw payload contains bad json")

    with pytest.raises(HTTPException) as exc_info:
        await stripe_webhook(mock_request)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Dados de webhook inválidos"
    mock_get_supabase.assert_not_called()


@pytest.mark.asyncio
@patch("webhooks.stripe.STRIPE_WEBHOOK_SECRET", "whsec_test")
@patch("webhooks.stripe.get_supabase")
@patch("webhooks.stripe.stripe.Webhook.construct_event")
async def test_malformed_event_data_object_rejected_before_db(
    mock_construct, mock_get_supabase, mock_request
):
    from webhooks.stripe import stripe_webhook

    mock_construct.return_value = _event(data_object=None)

    with pytest.raises(HTTPException) as exc_info:
        await stripe_webhook(mock_request)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Dados de webhook inválidos"
    mock_get_supabase.assert_not_called()


@pytest.mark.asyncio
@patch("webhooks.stripe.STRIPE_WEBHOOK_SECRET", "whsec_test")
@patch("webhooks.stripe.get_supabase")
@patch("webhooks.stripe.stripe.Webhook.construct_event")
async def test_invalid_event_id_rejected_before_db(
    mock_construct, mock_get_supabase, mock_request
):
    from webhooks.stripe import stripe_webhook

    mock_construct.return_value = _event(event_id="not_stripe_event")

    with pytest.raises(HTTPException) as exc_info:
        await stripe_webhook(mock_request)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Dados de webhook inválidos"
    mock_get_supabase.assert_not_called()
