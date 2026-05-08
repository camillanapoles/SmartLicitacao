"""Pydantic schemas for Intel Report one-time purchase flow.

Intel Report products:
- INTEL-REPORT-001: Company analysis by CNPJ (R$197)
- INTEL-REPORT-002: Sector/UF market report (R$147)
"""

from typing import Optional, Literal
from pydantic import BaseModel


# Valid product types for Intel Reports
VALID_PRODUCT_TYPES = ("cnpj", "sector_uf")

# Prices in BRL cents
INTEL_REPORT_PRICES: dict[str, int] = {
    "cnpj": 19700,       # R$197.00
    "sector_uf": 14700,  # R$147.00
}


class IntelReportCheckoutRequest(BaseModel):
    """Request body for POST /v1/intel-reports/checkout."""

    product_type: Literal["cnpj", "sector_uf"]
    entity_key: str  # CNPJ value (e.g. "12345678000195") or "sector:uf" (e.g. "limpeza:SP")


class IntelReportPurchase(BaseModel):
    """Represents a row in intel_report_purchases table."""

    id: str
    user_id: str
    product_type: str
    entity_key: str
    status: str  # "pending" | "generating" | "ready" | "failed"
    pdf_url: Optional[str] = None
    created_at: str
    expires_at: Optional[str] = None


class IntelReportCheckoutResponse(BaseModel):
    """Response for POST /v1/intel-reports/checkout."""

    checkout_url: str
    session_id: str


class IntelReportStatusResponse(BaseModel):
    """Response for GET /v1/intel-reports/{purchase_id}."""

    status: str  # "pending" | "generating" | "ready" | "failed"
    pdf_url: Optional[str] = None
    expires_at: Optional[str] = None
