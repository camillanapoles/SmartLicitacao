"""Tests for MON-FN-005: boot-time environment variable assertions."""

import pytest
from unittest.mock import MagicMock, patch


class TestAssertRequiredEnvVars:
    def test_raises_in_production_when_token_missing(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.delenv("MIXPANEL_TOKEN", raising=False)
        monkeypatch.delenv("BYPASS_REQUIRED_ENV_ASSERTIONS", raising=False)

        # Re-import to pick up fresh env
        import importlib
        import startup.assertions as mod
        importlib.reload(mod)

        with pytest.raises(RuntimeError, match="MIXPANEL_TOKEN"):
            mod.assert_required_env_vars()

    def test_passes_in_production_when_token_present(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("MIXPANEL_TOKEN", "test_token_abc")
        monkeypatch.delenv("BYPASS_REQUIRED_ENV_ASSERTIONS", raising=False)

        import importlib
        import startup.assertions as mod
        importlib.reload(mod)

        mod.assert_required_env_vars()  # must not raise

    def test_skips_in_development(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.delenv("MIXPANEL_TOKEN", raising=False)
        monkeypatch.delenv("BYPASS_REQUIRED_ENV_ASSERTIONS", raising=False)

        import importlib
        import startup.assertions as mod
        importlib.reload(mod)

        mod.assert_required_env_vars()  # must not raise

    def test_skips_when_environment_not_set(self, monkeypatch):
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("MIXPANEL_TOKEN", raising=False)
        monkeypatch.delenv("BYPASS_REQUIRED_ENV_ASSERTIONS", raising=False)

        import importlib
        import startup.assertions as mod
        importlib.reload(mod)

        mod.assert_required_env_vars()  # defaults to 'development', must not raise

    def test_bypass_flag_prevents_raise_in_production(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.delenv("MIXPANEL_TOKEN", raising=False)
        monkeypatch.setenv("BYPASS_REQUIRED_ENV_ASSERTIONS", "true")

        import importlib
        import startup.assertions as mod
        importlib.reload(mod)

        mod.assert_required_env_vars()  # must not raise

    def test_error_message_includes_var_name_and_description(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.delenv("MIXPANEL_TOKEN", raising=False)
        monkeypatch.delenv("BYPASS_REQUIRED_ENV_ASSERTIONS", raising=False)

        import importlib
        import startup.assertions as mod
        importlib.reload(mod)

        with pytest.raises(RuntimeError) as exc_info:
            mod.assert_required_env_vars()

        assert "MIXPANEL_TOKEN" in str(exc_info.value)
        assert "railway variables" in str(exc_info.value).lower() or "railway" in str(exc_info.value)


class TestAssertMixpanelReachable:
    def test_skips_in_non_production(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "development")

        import importlib
        import startup.assertions as mod
        importlib.reload(mod)

        mod.assert_mixpanel_reachable()  # must not raise

    def test_raises_when_get_mixpanel_returns_none_in_production(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")

        import importlib
        import startup.assertions as mod
        importlib.reload(mod)

        with patch("analytics_events._get_mixpanel", return_value=None):
            with pytest.raises(RuntimeError, match="Mixpanel client failed"):
                mod.assert_mixpanel_reachable()

    def test_passes_when_get_mixpanel_returns_client_in_production(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")

        import importlib
        import startup.assertions as mod
        importlib.reload(mod)

        mock_mp = MagicMock()
        mock_mp.track = MagicMock()

        with patch("analytics_events._get_mixpanel", return_value=mock_mp):
            mod.assert_mixpanel_reachable()  # must not raise

        mock_mp.track.assert_called_once()
        call_args = mock_mp.track.call_args
        assert call_args[0][1] == "backend_boot"

    def test_smoke_event_failure_is_non_fatal(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")

        import importlib
        import startup.assertions as mod
        importlib.reload(mod)

        mock_mp = MagicMock()
        mock_mp.track.side_effect = Exception("network error")

        with patch("analytics_events._get_mixpanel", return_value=mock_mp):
            mod.assert_mixpanel_reachable()  # must not raise despite track failure
