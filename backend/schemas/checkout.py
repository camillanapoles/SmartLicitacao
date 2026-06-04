"""CONV-005b-2: Pydantic schemas for checkout endpoint."""

from __future__ import annotations

from pydantic import BaseModel


class CheckoutRequest(BaseModel):
    """Request body for POST /api/checkout/one-time."""

    sku: str
    context: dict = {}


class CheckoutResponse(BaseModel):
    """Response for a successful checkout session creation."""

    checkout_url: str
