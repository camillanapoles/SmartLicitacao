"""Datalake API Self-Service schemas (#1372)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# API Key Management
# ---------------------------------------------------------------------------


class ApiKeyCreateRequest(BaseModel):
    """Request to create a new API key."""
    name: str = Field(default="", max_length=100, description="Label for the API key")


class ApiKeyCreateResponse(BaseModel):
    """Response after creating an API key. The plaintext key is returned ONCE."""
    id: str
    key: str = Field(description="Plaintext API key — shown only once")
    name: str
    created_at: datetime


class ApiKeyListItem(BaseModel):
    """Public representation of an API key (no plaintext)."""
    id: str
    name: str
    last_used_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    created_at: datetime


class ApiKeyListResponse(BaseModel):
    """List of user's API keys."""
    keys: list[ApiKeyListItem]


class ApiKeyRevokeResponse(BaseModel):
    """Response after revoking an API key."""
    id: str
    revoked: bool
    message: str


# ---------------------------------------------------------------------------
# API Search
# ---------------------------------------------------------------------------


class ApiSearchParams(BaseModel):
    """Query parameters for the public API search endpoint.

    Mirrors the internal /buscar request structure but exposes
    only the fields appropriate for API (programmatic) access.
    """
    q: str = Field(..., min_length=2, max_length=200, description="Search query (keywords)")
    uf: Optional[str] = Field(default=None, min_length=2, max_length=2, description="State (UF) filter")
    data_inicial: Optional[str] = Field(default=None, description="Start date (ISO format)")
    data_final: Optional[str] = Field(default=None, description="End date (ISO format)")
    modalidade: Optional[str] = Field(default=None, description="Comma-separated modality codes")
    valor_min: Optional[float] = Field(default=None, ge=0, description="Minimum estimated value")
    valor_max: Optional[float] = Field(default=None, ge=0, description="Maximum estimated value")
    pagina: int = Field(default=1, ge=1, le=100, description="Page number (1-based)")
    tamanho: int = Field(default=20, ge=1, le=100, description="Items per page (max 100)")


class ApiSearchResponse(BaseModel):
    """Paginated search response for the API search endpoint."""
    pagina: int
    tamanho: int
    total: int
    resultados: list[dict] = []
