"""Tests for the Subcontracting Intelligence gate (SUBINTEL-030, EPIC-SUBINTEL #1224).

Covers:
  - Non-regression: every existing plan defaults allow_subcontract_intel=False
  - Stage 1 gate: feature flag OFF ⇒ HTTP 404 (vertical inert)
  - Stage 2 gate: capability False ⇒ HTTP 403 upsell
  - capability True ⇒ access granted
  - master/admin bypass
  - fail-closed on Supabase circuit-breaker open (premium gate must not open)
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from quota import PLAN_CAPABILITIES, requires_subcontract_intel
from supabase_client import CircuitBreakerOpenError

USER = {"id": "user-123"}

# Every plan_id shipped today — gate must be invisible to all of them by default.
EXISTING_PLANS = [
    "free_trial",
    "consultor_agil",
    "maquina",
    "sala_guerra",
    "smartlic_pro",
    "founding_member",
    "consultoria",
    "free",
    "master",
]


class TestNonRegression:
    """Adding the capability must not change any existing plan's behaviour."""

    @pytest.mark.parametrize("plan_id", EXISTING_PLANS)
    def test_existing_plan_defaults_subcontract_intel_false(self, plan_id):
        assert plan_id in PLAN_CAPABILITIES
        assert PLAN_CAPABILITIES[plan_id]["allow_subcontract_intel"] is False

    @pytest.mark.parametrize("plan_id", EXISTING_PLANS)
    def test_existing_plan_keeps_legacy_capabilities(self, plan_id):
        """The new key is purely additive — legacy keys remain present."""
        caps = PLAN_CAPABILITIES[plan_id]
        for legacy_key in (
            "max_history_days",
            "allow_excel",
            "allow_pipeline",
            "max_requests_per_month",
            "priority",
        ):
            assert legacy_key in caps


def _mock_quota(allow: bool, plan_id: str = "free_trial"):
    return SimpleNamespace(
        capabilities={"allow_subcontract_intel": allow},
        plan_id=plan_id,
        allowed=True,
    )


@pytest.mark.asyncio
class TestSubcontractIntelGate:
    async def test_flag_off_returns_404(self):
        """Stage 1: kill-switch off ⇒ route behaves as if it does not exist."""
        with patch("config.features.get_feature_flag", return_value=False):
            with pytest.raises(HTTPException) as exc:
                await requires_subcontract_intel(USER)
        assert exc.value.status_code == 404

    async def test_flag_on_capability_false_returns_403(self):
        """Stage 2: enabled but plan lacks capability ⇒ upsell 403."""
        with patch("config.features.get_feature_flag", return_value=True), \
             patch("authorization.has_master_access", new=AsyncMock(return_value=False)), \
             patch("quota.plan_enforcement.check_quota", MagicMock(return_value=_mock_quota(False))), \
             patch("quota.plan_auth.track_funnel_event"):
            with pytest.raises(HTTPException) as exc:
                await requires_subcontract_intel(USER)
        assert exc.value.status_code == 403
        assert exc.value.detail["error_code"] == "subcontract_intel_not_available"

    async def test_flag_on_capability_true_passes(self):
        """Plan with the capability is granted access (returns the user)."""
        with patch("config.features.get_feature_flag", return_value=True), \
             patch("authorization.has_master_access", new=AsyncMock(return_value=False)), \
             patch("quota.plan_enforcement.check_quota",
                   MagicMock(return_value=_mock_quota(True, "smartlic_insight"))):
            result = await requires_subcontract_intel(USER)
        assert result == USER

    async def test_master_bypasses_capability_gate(self):
        """Master/admin always passes even when the plan capability is False."""
        with patch("config.features.get_feature_flag", return_value=True), \
             patch("authorization.has_master_access", new=AsyncMock(return_value=True)):
            result = await requires_subcontract_intel(USER)
        assert result == USER

    async def test_circuit_breaker_open_fails_closed(self):
        """Premium gate must NOT open when Supabase circuit breaker is open."""
        with patch("config.features.get_feature_flag", return_value=True), \
             patch("authorization.has_master_access", new=AsyncMock(return_value=False)), \
             patch("quota.plan_enforcement.check_quota",
                   MagicMock(side_effect=CircuitBreakerOpenError("cb open"))):
            with pytest.raises(HTTPException) as exc:
                await requires_subcontract_intel(USER)
        assert exc.value.status_code == 403
        assert exc.value.detail["error_code"] == "subcontract_intel_not_available"
