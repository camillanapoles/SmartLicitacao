"""
ENTITY-004: Tests for tracked entity limits per plan tier.

Tests cover:
- PlanCapabilities includes max_tracked_entities
- Each plan has the correct limit (trial=1, pro=5, consulting=20, master=unlimited)
- Entity limit validation logic in alerts routes
"""

import sys
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel, Field

from quota.quota_core import (
    PLAN_CAPABILITIES,
    PlanCapabilities,
)


# ---------------------------------------------------------------------------
# Mock the module-level dependencies of routes.alerts so we can import
# the Pydantic models and helper functions without pulling in FastAPI/auth.
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _mock_alerts_deps():
    """Mock dependencies of routes.alerts module before any test imports from it.

    IMPORTANT: Save original modules BEFORE mocking and restore them in cleanup.
    Removing real modules from sys.modules corrupts imports for the entire test suite
    (CRIT-091: caused 191 cascading 401 failures across unrelated test files).
    """
    _MOCK_MODULES = ["auth", "log_sanitizer", "schemas.common", "supabase_client"]

    # Save original modules so we can restore them without corrupting the suite
    _saved: dict[str, object] = {}
    for mod_name in _MOCK_MODULES:
        _saved[mod_name] = sys.modules.get(mod_name)

    mock_auth = MagicMock()
    mock_auth.require_auth = MagicMock()
    sys.modules["auth"] = mock_auth

    mock_log_sanitizer = MagicMock()
    mock_log_sanitizer.mask_user_id = lambda x: x[:8] + "..." if len(x or "") > 8 else x
    sys.modules["log_sanitizer"] = mock_log_sanitizer

    # schemas.common may not have SuccessMessageResponse — create minimal stub
    mock_schemas_common = MagicMock()

    class MockSuccessMessageResponse(BaseModel):
        success: bool = True
        message: str = ""

    mock_schemas_common.SuccessMessageResponse = MockSuccessMessageResponse
    sys.modules["schemas.common"] = mock_schemas_common

    # Also mock supabase_client since routes.alerts imports it at function level
    mock_supabase = MagicMock()
    sys.modules["supabase_client"] = mock_supabase

    yield

    # Restore original modules — never leave holes in sys.modules
    for mod_name in _MOCK_MODULES:
        original = _saved.get(mod_name)
        if original is None:
            sys.modules.pop(mod_name, None)
        else:
            sys.modules[mod_name] = original


# ===========================================================================
# PlanCapabilities Tests
# ===========================================================================


class TestEntityPlanLimits:
    """ENTITY-004 AC1: PlanCapabilities max_tracked_entries per tier."""

    def test_plan_capabilities_has_max_tracked_entities_field(self):
        """max_tracked_entities is present in the PlanCapabilities TypedDict."""
        caps = PlanCapabilities(
            max_history_days=30,
            allow_excel=False,
            allow_pipeline=False,
            allow_subcontract_intel=False,
            allow_predictive_intel=False,
            allow_competitive_intel=False,
            allow_workspace_basic=False,
            max_requests_per_month=10,
            max_requests_per_min=2,
            max_summary_tokens=200,
            max_tracked_entities=1,
            priority="normal",
        )
        assert caps["max_tracked_entities"] == 1

    def test_trial_has_limit_1(self):
        """free_trial plan allows 1 tracked entity."""
        assert PLAN_CAPABILITIES["free_trial"]["max_tracked_entities"] == 1

    def test_smartlic_pro_has_limit_5(self):
        """smartlic_pro plan allows 5 tracked entities."""
        assert PLAN_CAPABILITIES["smartlic_pro"]["max_tracked_entities"] == 5

    def test_consultoria_has_limit_20(self):
        """consultoria plan allows 20 tracked entities."""
        assert PLAN_CAPABILITIES["consultoria"]["max_tracked_entities"] == 20

    def test_master_has_unlimited(self):
        """master plan allows unlimited tracked entities."""
        assert PLAN_CAPABILITIES["master"]["max_tracked_entities"] >= 99999

    def test_free_plan_has_no_tracking(self):
        """free plan allows 0 tracked entities."""
        assert PLAN_CAPABILITIES["free"]["max_tracked_entities"] == 0

    def test_founding_member_same_as_pro(self):
        """founding_member has same limit as smartlic_pro (5)."""
        assert PLAN_CAPABILITIES["founding_member"]["max_tracked_entities"] == 5

    def test_all_plans_have_max_tracked_entities(self):
        """Every plan definition includes max_tracked_entities."""
        for plan_id, caps in PLAN_CAPABILITIES.items():
            assert "max_tracked_entities" in caps, f"Plan {plan_id} missing max_tracked_entities"
            assert isinstance(caps["max_tracked_entities"], int)

    def test_unknown_plan_default(self):
        """Unknown plan defaults to conservative limit of 1 (same as trial)."""
        from quota.quota_core import _UNKNOWN_PLAN_DEFAULTS
        assert _UNKNOWN_PLAN_DEFAULTS["max_tracked_entities"] == 1


# ===========================================================================
# _check_entity_limit Unit Tests
# ===========================================================================


class TestCheckEntityLimit:
    """ENTITY-004: Unit tests for _check_entity_limit."""

    @pytest.mark.asyncio
    @patch("routes.alerts._get_entity_tracked_limit", new_callable=AsyncMock)
    @patch("routes.alerts._count_user_tracked_entities", new_callable=AsyncMock)
    async def test_passes_when_under_limit(
        self,
        mock_count: AsyncMock,
        mock_limit: AsyncMock,
    ):
        """User with room can add entities."""
        mock_limit.return_value = 5
        mock_count.return_value = 2

        from routes.alerts import _check_entity_limit

        # Should not raise
        await _check_entity_limit("user-1", "tracked_orgaos", ["cnpj-new"])

    @pytest.mark.asyncio
    @patch("routes.alerts._get_entity_tracked_limit", new_callable=AsyncMock)
    async def test_skipped_for_unlimited_plan(self, mock_limit: AsyncMock):
        """Master/unlimited plans skip the check."""
        mock_limit.return_value = 99999

        from routes.alerts import _check_entity_limit

        # Should not raise — unlimited
        await _check_entity_limit("user-master", "tracked_orgaos", ["cnpj-1"])


# ===========================================================================
# _PLAN_TRACKED_ENTITY_LIMITS Dict Tests
# ===========================================================================


class TestPlanTrackedEntityLimits:
    """ENTITY-004: _PLAN_TRACKED_ENTITY_LIMITS hardcoded fallback."""

    def test_limits_defined_for_all_tiers(self):
        """All major plan tiers have entity limits defined."""
        from routes.alerts import _PLAN_TRACKED_ENTITY_LIMITS

        assert _PLAN_TRACKED_ENTITY_LIMITS["free"] == 0
        assert _PLAN_TRACKED_ENTITY_LIMITS["free_trial"] == 1
        assert _PLAN_TRACKED_ENTITY_LIMITS["smartlic_pro"] == 5
        assert _PLAN_TRACKED_ENTITY_LIMITS["consultoria"] == 20
        assert _PLAN_TRACKED_ENTITY_LIMITS["master"] >= 99999


# ===========================================================================
# Pydantic Model Tests
# ===========================================================================


class TestAlertResponseHasTrackedEntities:
    """ENTITY-004: AlertResponse model includes tracked entity fields."""

    def test_alert_response_includes_tracked_orgaos(self):
        """AlertResponse has tracked_orgaos field defaulting to empty list."""
        from routes.alerts import AlertResponse

        resp = AlertResponse(
            id="test-id",
            user_id="user-1",
            name="Test Alert",
            filters={},
            active=True,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        assert resp.tracked_orgaos == []

    def test_alert_response_includes_tracked_fornecedores(self):
        """AlertResponse has tracked_fornecedores field defaulting to empty list."""
        from routes.alerts import AlertResponse

        resp = AlertResponse(
            id="test-id",
            user_id="user-1",
            name="Test Alert",
            filters={},
            active=True,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        assert resp.tracked_fornecedores == []


class TestCreateAlertRequestIncludesTrackedEntities:
    """ENTITY-004: CreateAlertRequest model includes tracked entity fields."""

    def test_create_alert_request_has_tracked_orgaos(self):
        """CreateAlertRequest accepts tracked_orgaos."""
        from routes.alerts import CreateAlertRequest, AlertFilters

        req = CreateAlertRequest(
            name="Test",
            filters=AlertFilters(),
            tracked_orgaos=["cnpj-1", "cnpj-2"],
        )
        assert req.tracked_orgaos == ["cnpj-1", "cnpj-2"]

    def test_create_alert_request_has_tracked_fornecedores(self):
        """CreateAlertRequest accepts tracked_fornecedores."""
        from routes.alerts import CreateAlertRequest, AlertFilters

        req = CreateAlertRequest(
            name="Test",
            filters=AlertFilters(),
            tracked_fornecedores=["cnpj-3"],
        )
        assert req.tracked_fornecedores == ["cnpj-3"]


class TestUpdateAlertRequestIncludesTrackedEntities:
    """ENTITY-004: UpdateAlertRequest model includes tracked entity fields."""

    def test_update_alert_request_has_tracked_orgaos(self):
        """UpdateAlertRequest accepts tracked_orgaos."""
        from routes.alerts import UpdateAlertRequest

        req = UpdateAlertRequest(tracked_orgaos=["cnpj-1"])
        assert req.tracked_orgaos == ["cnpj-1"]

    def test_update_alert_request_tracked_fornecedores_none_by_default(self):
        """UpdateAlertRequest has tracked_fornecedores as None by default."""
        from routes.alerts import UpdateAlertRequest

        req = UpdateAlertRequest()
        assert req.tracked_fornecedores is None
