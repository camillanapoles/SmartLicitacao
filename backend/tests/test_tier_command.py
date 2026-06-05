"""Tests for TIER-COMMAND-001: Command tier PlanCapabilities and TierConfig.

Verifies:
  - TIER_COMMAND has all 7 exclusive capabilities (default False)
  - TIER_COMMAND inherits INSIGHT_CAPABILITIES (#1235 placeholder)
  - TIER_COMMAND quotas: searches=-1, intel_reports=10
  - Existing tiers (Free, Pro) not affected by Command tier addition
  - TierConfig model validates fields correctly
"""

from quota.quota_core import (
    TierConfig,
    INSIGHT_CAPABILITIES,
    COMMAND_CAPABILITIES,
    TIER_COMMAND,
    PLAN_CAPABILITIES,
)


class TestTierConfigModel:
    """Test TierConfig Pydantic model creation and validation."""

    def test_tier_config_creation(self):
        """TierConfig should be created with all required fields."""
        config = TierConfig(
            tier_id="test_tier",
            name="Test Tier",
            price_monthly=1000_00,
            price_yearly=10000_00,
            capabilities={"allow_test": True, "allow_other": False},
            quotas={"searches": 100, "reports": 5},
        )

        assert config.tier_id == "test_tier"
        assert config.name == "Test Tier"
        assert config.price_monthly == 1000_00
        assert config.price_yearly == 10000_00
        assert config.capabilities["allow_test"] is True
        assert config.capabilities["allow_other"] is False
        assert config.quotas["searches"] == 100
        assert config.quotas["reports"] == 5

    def test_tier_config_empty_capabilities(self):
        """TierConfig should accept empty capabilities dict."""
        config = TierConfig(
            tier_id="empty",
            name="Empty",
            price_monthly=0,
            price_yearly=0,
            capabilities={},
            quotas={},
        )

        assert config.capabilities == {}
        assert config.quotas == {}


class TestInsightCapabilities:
    """Test INSIGHT_CAPABILITIES placeholder (TIER-COMMAND-001 AC #1235)."""

    def test_insight_capabilities_is_empty_dict(self):
        """INSIGHT_CAPABILITIES should be empty until #1235 is merged."""
        assert isinstance(INSIGHT_CAPABILITIES, dict)
        assert len(INSIGHT_CAPABILITIES) == 0


class TestCommandCapabilities:
    """Test COMMAND_CAPABILITIES definitions (TIER-COMMAND-001)."""

    COMMAND_CAP_KEYS = {
        "allow_multi_user",
        "allow_api_access",
        "allow_executive_reports",
        "allow_regional_intel",
        "allow_workspace_advanced",
        "allow_data_export",
        "allow_custom_alerts",
    }

    def test_all_command_capabilities_defined(self):
        """COMMAND_CAPABILITIES must have all 7 exclusive capabilities."""
        assert isinstance(COMMAND_CAPABILITIES, dict)
        assert set(COMMAND_CAPABILITIES.keys()) == self.COMMAND_CAP_KEYS

    def test_command_capabilities_count(self):
        """COMMAND_CAPABILITIES must have exactly 7 capabilities."""
        assert len(COMMAND_CAPABILITIES) == 7

    def test_all_command_capabilities_default_false(self):
        """All COMMAND_CAPABILITIES must default to False."""
        for cap_name, cap_value in COMMAND_CAPABILITIES.items():
            assert cap_value is False, (
                f"Command capability '{cap_name}' must default to False, "
                f"got {cap_value}"
            )


class TestTierCommand:
    """Test TIER_COMMAND TierConfig instance (TIER-COMMAND-001)."""

    def test_tier_command_is_tier_config(self):
        """TIER_COMMAND must be a TierConfig instance."""
        assert isinstance(TIER_COMMAND, TierConfig)

    def test_tier_command_tier_id(self):
        """TIER_COMMAND tier_id must be 'command'."""
        assert TIER_COMMAND.tier_id == "command"

    def test_tier_command_name(self):
        """TIER_COMMAND display name must be 'SmartLic Command'."""
        assert TIER_COMMAND.name == "SmartLic Command"

    def test_tier_command_price_monthly(self):
        """TIER_COMMAND monthly price must be R$ 4.970,00 (4970_00 cents)."""
        assert TIER_COMMAND.price_monthly == 4970_00

    def test_tier_command_price_yearly(self):
        """TIER_COMMAND yearly price must be R$ 49.700,00 (49700_00 cents)."""
        assert TIER_COMMAND.price_yearly == 49700_00

    def test_tier_command_has_all_command_capabilities(self):
        """TIER_COMMAND must have all 7 Command exclusive capabilities."""
        for cap_key in COMMAND_CAPABILITIES:
            assert cap_key in TIER_COMMAND.capabilities, (
                f"TIER_COMMAND missing capability: {cap_key}"
            )

    def test_tier_command_inherits_insight_capabilities(self):
        """TIER_COMMAND must inherit all INSIGHT_CAPABILITIES."""
        for cap_key in INSIGHT_CAPABILITIES:
            assert cap_key in TIER_COMMAND.capabilities, (
                f"TIER_COMMAND missing inherited Insight capability: {cap_key}"
            )

    def test_tier_command_quotas_searches_unlimited(self):
        """TIER_COMMAND searches quota must be -1 (ilimitado)."""
        assert TIER_COMMAND.quotas["searches"] == -1

    def test_tier_command_quotas_intel_reports(self):
        """TIER_COMMAND intel_reports quota must be 10/mês."""
        assert TIER_COMMAND.quotas["intel_reports"] == 10

    def test_tier_command_has_exactly_2_quotas(self):
        """TIER_COMMAND must have exactly 2 quota entries."""
        assert len(TIER_COMMAND.quotas) == 2


class TestExistingTiersNotModified:
    """Verify Command tier addition does NOT affect existing tiers.

    TIER-COMMAND-001 AC: Zero alteration in existing Free and Pro tiers.
    """

    def test_free_plan_still_exists(self):
        """'free' plan must still exist in PLAN_CAPABILITIES."""
        assert "free" in PLAN_CAPABILITIES

    def test_free_plan_capabilities_unchanged(self):
        """'free' plan capabilities must remain unchanged."""
        free_caps = PLAN_CAPABILITIES["free"]
        assert free_caps["max_history_days"] == 7
        assert free_caps["allow_excel"] is False
        assert free_caps["allow_pipeline"] is False
        assert free_caps["max_requests_per_month"] == 10
        assert free_caps["max_requests_per_min"] == 2
        assert free_caps["max_summary_tokens"] == 200
        assert free_caps["priority"] == "low"

    def test_smartlic_pro_plan_still_exists(self):
        """'smartlic_pro' plan must still exist in PLAN_CAPABILITIES."""
        assert "smartlic_pro" in PLAN_CAPABILITIES

    def test_smartlic_pro_capabilities_unchanged(self):
        """'smartlic_pro' plan capabilities must remain unchanged."""
        pro_caps = PLAN_CAPABILITIES["smartlic_pro"]
        assert pro_caps["max_history_days"] == 1825
        assert pro_caps["allow_excel"] is True
        assert pro_caps["allow_pipeline"] is True
        assert pro_caps["max_requests_per_month"] == 1000
        assert pro_caps["max_requests_per_min"] == 60
        assert pro_caps["max_summary_tokens"] == 10000
        assert pro_caps["priority"] == "normal"

    def test_free_trial_plan_unchanged(self):
        """'free_trial' plan capabilities must remain unchanged."""
        trial_caps = PLAN_CAPABILITIES["free_trial"]
        assert trial_caps["max_history_days"] == 365
        assert trial_caps["allow_excel"] is True
        assert trial_caps["allow_pipeline"] is True
        assert trial_caps["max_requests_per_month"] == 1000
        assert trial_caps["max_requests_per_min"] == 2
        assert trial_caps["max_summary_tokens"] == 10000
        assert trial_caps["priority"] == "normal"

    def test_all_original_plans_still_present(self):
        """All original plan IDs must still be in PLAN_CAPABILITIES."""
        original_plans = {
            "free_trial",
            "consultor_agil",
            "maquina",
            "sala_guerra",
            "smartlic_pro",
            "founding_member",
            "consultoria",
            "free",
            "master",
        }
        assert original_plans.issubset(set(PLAN_CAPABILITIES.keys()))

    def test_no_extra_plans_added(self):
        """No new plans should be added to PLAN_CAPABILITIES."""
        expected_plans = {
            "free_trial",
            "consultor_agil",
            "maquina",
            "sala_guerra",
            "smartlic_pro",
            "founding_member",
            "consultoria",
            "smartlic_command",
            "free",
            "master",
        }
        assert set(PLAN_CAPABILITIES.keys()) == expected_plans
