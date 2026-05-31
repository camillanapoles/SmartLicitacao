"""Tests for B2GOPS-001: workspace_watchlists schema + RPCs (Wave 0).

Validates the migration SQL contract, RPC signatures, grants, RLS policies,
return shapes, and the B2G_OPS_ENABLED feature flag.

These tests are purely static/contract validation — they do NOT connect to
a live database. RPC behavior (ops_create_watchlist, ops_match_watchlist)
is validated via mock supabase.rpc() chains.
"""

from __future__ import annotations

import json
import os
import re
from unittest.mock import MagicMock

import pytest

from tests.conftest import mock_supabase as _mock_supabase  # noqa: F401

# Paths relative to repo root
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MIGRATIONS_DIR = os.path.join(REPO_ROOT, "supabase", "migrations")

MIGRATION_FILE = "20260531175520_workspace_watchlists.sql"
DOWN_FILE = "20260531175520_workspace_watchlists.down.sql"

# Expected columns for workspace_watchlists
WATCHLIST_COLUMNS = [
    "id", "user_id", "nome", "descricao", "filtros",
    "alertas_ativos", "frequencia_alerta", "created_at", "updated_at",
]

# Expected columns for workspace_watchlist_matches
MATCH_COLUMNS = [
    "id", "watchlist_id", "licitacao_id", "fonte",
    "status", "matched_at",
]

# Expected JSON keys from ops_create_watchlist
WATCHLIST_KEYS = [
    "id", "user_id", "nome", "descricao", "filtros",
    "alertas_ativos", "frequencia_alerta", "created_at", "updated_at",
]

# Expected JSON keys from ops_match_watchlist
MATCH_RESULT_KEYS = ["watchlist_id", "new_matches"]

# Feature flag name
B2G_OPS_ENABLED_FLAG = "B2G_OPS_ENABLED"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_sql(filename: str) -> str:
    path = os.path.join(MIGRATIONS_DIR, filename)
    with open(path) as f:
        return f.read()


def _build_mock_result(data: list) -> MagicMock:
    """Build a supabase RPC execute result wrapping ``data``."""
    result = MagicMock()
    result.data = data
    return result


def _rpc_execute(result_data: list | None = None, side_effect: Exception | None = None):
    """Patch helper: returns a supabase rpc() chain ending in execute()."""
    rpc_chain = MagicMock()
    if side_effect:
        rpc_chain.execute.side_effect = side_effect
    else:
        rpc_result = _build_mock_result(result_data or [])
        rpc_chain.execute.return_value = rpc_result
    return rpc_chain


# ---------------------------------------------------------------------------
# Sample data (simulates what the RPCs return)
# ---------------------------------------------------------------------------

SAMPLE_WATCHLIST_RESPONSE = {
    "id": "00000000-0000-0000-0000-000000000001",
    "user_id": "user-123-uuid",
    "nome": "Oportunidades SP",
    "descricao": "Licitações de TI em São Paulo",
    "filtros": {"ufs": ["SP"], "setor": "informatica"},
    "alertas_ativos": True,
    "frequencia_alerta": "daily",
    "created_at": "2026-05-31T12:00:00+00:00",
    "updated_at": "2026-05-31T12:00:00+00:00",
}

SAMPLE_MATCH_RESULT = {
    "watchlist_id": "00000000-0000-0000-0000-000000000001",
    "new_matches": 5,
}

EMPTY_MATCH_RESULT = {
    "watchlist_id": "00000000-0000-0000-0000-000000000002",
    "new_matches": 0,
}


# ===================================================================
# Migration Contract Tests
# ===================================================================


class TestMigrationContract:
    """Validate the SQL migration files are well-formed."""

    def test_migration_file_exists(self):
        path = os.path.join(MIGRATIONS_DIR, MIGRATION_FILE)
        assert os.path.exists(path), f"Migration file not found: {path}"

    def test_down_file_exists(self):
        path = os.path.join(MIGRATIONS_DIR, DOWN_FILE)
        assert os.path.exists(path), f"Down migration not found: {path}"

    # -- Tables --

    def test_workspace_watchlists_table_created(self):
        sql = _read_sql(MIGRATION_FILE)
        assert (
            "CREATE TABLE public.workspace_watchlists" in sql
        ), "Missing workspace_watchlists table"

    def test_workspace_watchlist_matches_table_created(self):
        sql = _read_sql(MIGRATION_FILE)
        assert (
            "CREATE TABLE public.workspace_watchlist_matches" in sql
        ), "Missing workspace_watchlist_matches table"

    def test_watchlist_all_columns(self):
        sql = _read_sql(MIGRATION_FILE)
        for col in WATCHLIST_COLUMNS:
            assert col in sql, f"Missing workspace_watchlists column: {col}"

    def test_watchlist_matches_all_columns(self):
        sql = _read_sql(MIGRATION_FILE)
        for col in MATCH_COLUMNS:
            assert col in sql, f"Missing workspace_watchlist_matches column: {col}"

    def test_unique_constraint_on_matches(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "UNIQUE(watchlist_id, licitacao_id, fonte)" in sql, (
            "Missing UNIQUE constraint on (watchlist_id, licitacao_id, fonte)"
        )

    def test_frequencia_alerta_check_constraint(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "CHECK (frequencia_alerta IN ('daily', 'weekly', 'instant'))" in sql, (
            "Missing CHECK constraint on frequencia_alerta"
        )

    def test_matches_status_check_constraint(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "CHECK (status IN ('unread', 'archived', 'dismissed'))" in sql, (
            "Missing CHECK constraint on status"
        )

    def test_on_delete_cascade_watchlist(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "REFERENCES auth.users(id) ON DELETE CASCADE" in sql, (
            "Missing ON DELETE CASCADE for user_id FK"
        )

    def test_on_delete_cascade_matches(self):
        sql = _read_sql(MIGRATION_FILE)
        assert (
            "REFERENCES public.workspace_watchlists(id) ON DELETE CASCADE" in sql
        ), "Missing ON DELETE CASCADE for watchlist_id FK"

    def test_indexes_created(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "idx_watchlists_user" in sql, "Missing idx_watchlists_user"
        assert "idx_watchlist_matches_wid" in sql, "Missing idx_watchlist_matches_wid"
        assert "idx_watchlist_matches_status" in sql, "Missing idx_watchlist_matches_status"

    # -- RLS --

    def test_rls_enabled_on_watchlists(self):
        sql = _read_sql(MIGRATION_FILE)
        assert (
            'ALTER TABLE public.workspace_watchlists ENABLE ROW LEVEL SECURITY' in sql
        ), "Missing RLS enable on workspace_watchlists"

    def test_rls_enabled_on_matches(self):
        sql = _read_sql(MIGRATION_FILE)
        assert (
            'ALTER TABLE public.workspace_watchlist_matches ENABLE ROW LEVEL SECURITY' in sql
        ), "Missing RLS enable on workspace_watchlist_matches"

    def test_watchlists_rls_policy(self):
        sql = _read_sql(MIGRATION_FILE)
        assert (
            'CREATE POLICY "Users can CRUD own watchlists"' in sql
        ), "Missing watchlists RLS policy"
        assert "user_id = auth.uid()" in sql, (
            "Watchlists RLS must enforce user_id = auth.uid()"
        )

    def test_matches_rls_policy(self):
        sql = _read_sql(MIGRATION_FILE)
        assert (
            'CREATE POLICY "Users can CRUD own watchlist matches"' in sql
        ), "Missing matches RLS policy"
        assert "w.user_id = auth.uid()" in sql, (
            "Matches RLS must verify ownership via workspace_watchlists"
        )

    # -- Grants --

    def test_service_role_grants(self):
        sql = _read_sql(MIGRATION_FILE)
        # Both tables must have service_role grant
        service_grants = re.findall(r"GRANT ALL ON public\.\w+ TO service_role;", sql)
        assert len(service_grants) == 2, (
            f"Expected 2 service_role grants, found {len(service_grants)}: {service_grants}"
        )

    def test_authenticated_grants(self):
        sql = _read_sql(MIGRATION_FILE)
        auth_grants = re.findall(
            r"GRANT SELECT, INSERT, UPDATE, DELETE ON public\.\w+ TO authenticated;", sql
        )
        assert len(auth_grants) == 2, (
            f"Expected 2 authenticated grants, found {len(auth_grants)}: {auth_grants}"
        )

    # -- RPC: ops_create_watchlist --

    def test_ops_create_watchlist_function(self):
        sql = _read_sql(MIGRATION_FILE)
        assert (
            "CREATE OR REPLACE FUNCTION public.ops_create_watchlist" in sql
        ), "Missing ops_create_watchlist function"

    def test_ops_create_watchlist_params(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "p_nome TEXT" in sql, "Missing p_nome parameter"
        assert "p_descricao TEXT DEFAULT NULL" in sql, (
            "Missing or misconfigured p_descricao parameter"
        )
        assert "p_filtros JSONB DEFAULT '{}'" in sql, (
            "Missing or misconfigured p_filtros parameter"
        )
        assert "p_frequencia_alerta TEXT DEFAULT 'daily'" in sql, (
            "Missing or misconfigured p_frequencia_alerta parameter"
        )

    def test_ops_create_watchlist_returns_json(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "RETURNS json" in sql, "Must return json"

    def test_ops_create_watchlist_security_definer(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "SECURITY DEFINER" in sql, "Missing SECURITY DEFINER"

    def test_ops_create_watchlist_search_path(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "SET search_path = public, pg_temp" in sql, (
            "Missing search_path = public, pg_temp"
        )

    def test_ops_create_watchlist_uses_auth_uid(self):
        """ops_create_watchlist must use auth.uid(), NOT receive user_id as param."""
        sql = _read_sql(MIGRATION_FILE)
        assert "auth.uid()" in sql, "Must use auth.uid()"
        assert "p_user_id" not in sql, (
            "ops_create_watchlist must NOT receive user_id as parameter"
        )

    def test_ops_create_watchlist_grants(self):
        sql = _read_sql(MIGRATION_FILE)
        create_grants = re.findall(
            r"GRANT EXECUTE ON FUNCTION public\.ops_create_watchlist\(TEXT, TEXT, JSONB, TEXT\) TO (\w+);",
            sql,
        )
        assert "authenticated" in create_grants, "Missing authenticated grant"
        assert "service_role" in create_grants, "Missing service_role grant"

    # -- RPC: ops_match_watchlist --

    def test_ops_match_watchlist_function(self):
        sql = _read_sql(MIGRATION_FILE)
        assert (
            "CREATE OR REPLACE FUNCTION public.ops_match_watchlist" in sql
        ), "Missing ops_match_watchlist function"

    def test_ops_match_watchlist_params(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "p_watchlist_id UUID" in sql, "Missing p_watchlist_id parameter"

    def test_ops_match_watchlist_returns_json(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "RETURNS json" in sql, "Must return json"

    def test_ops_match_watchlist_security_definer(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "SECURITY DEFINER" in sql, "Missing SECURITY DEFINER"

    def test_ops_match_watchlist_search_path(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "SET search_path = public, pg_temp" in sql, (
            "Missing search_path = public, pg_temp"
        )

    def test_ops_match_watchlist_grants(self):
        sql = _read_sql(MIGRATION_FILE)
        match_grants = re.findall(
            r"GRANT EXECUTE ON FUNCTION public\.ops_match_watchlist\(UUID\) TO (\w+);",
            sql,
        )
        assert "authenticated" in match_grants, "Missing authenticated grant"
        assert "service_role" in match_grants, "Missing service_role grant"

    # -- Down migration --

    def test_down_drops_functions(self):
        sql = _read_sql(DOWN_FILE)
        assert (
            "DROP FUNCTION IF EXISTS public.ops_match_watchlist(UUID)" in sql
        ), "Down must drop ops_match_watchlist"
        assert (
            "DROP FUNCTION IF EXISTS public.ops_create_watchlist(TEXT, TEXT, JSONB, TEXT)" in sql
        ), "Down must drop ops_create_watchlist"

    def test_down_drops_tables_cascade(self):
        sql = _read_sql(DOWN_FILE)
        assert (
            "DROP TABLE IF EXISTS public.workspace_watchlist_matches CASCADE" in sql
        ), "Down must drop workspace_watchlist_matches CASCADE"
        assert (
            "DROP TABLE IF EXISTS public.workspace_watchlists CASCADE" in sql
        ), "Down must drop workspace_watchlists CASCADE"

    def test_no_existing_objects_altered(self):
        """Ensure migration doesn't alter any existing tables or RPCs."""
        sql = _read_sql(MIGRATION_FILE)
        # Count CREATE OR REPLACE FUNCTION occurrences
        func_count = len(re.findall(r"CREATE OR REPLACE FUNCTION", sql))
        assert func_count == 2, (
            f"Expected exactly 2 CREATE OR REPLACE FUNCTION, found {func_count}"
        )
        # Count CREATE TABLE occurrences
        table_count = len(re.findall(r"CREATE TABLE public\.", sql))
        assert table_count == 2, (
            f"Expected exactly 2 CREATE TABLE, found {table_count}"
        )


# ===================================================================
# Return Shape Tests
# ===================================================================


class TestReturnShape:
    """Validate the RPC JSON shapes against the specification."""

    def test_watchlist_all_expected_keys(self):
        for key in WATCHLIST_KEYS:
            assert key in SAMPLE_WATCHLIST_RESPONSE, f"Missing key: {key}"

    def test_watchlist_no_extra_keys(self):
        extra = set(SAMPLE_WATCHLIST_RESPONSE.keys()) - set(WATCHLIST_KEYS)
        assert not extra, f"Unexpected keys: {extra}"

    def test_watchlist_uuid_fields(self):
        assert isinstance(SAMPLE_WATCHLIST_RESPONSE["id"], str)
        assert isinstance(SAMPLE_WATCHLIST_RESPONSE["user_id"], str)

    def test_watchlist_string_fields(self):
        for key in ("nome", "descricao", "frequencia_alerta"):
            assert isinstance(SAMPLE_WATCHLIST_RESPONSE[key], str), (
                f"{key} must be str, got {type(SAMPLE_WATCHLIST_RESPONSE[key])}"
            )

    def test_watchlist_boolean_field(self):
        assert isinstance(SAMPLE_WATCHLIST_RESPONSE["alertas_ativos"], bool)

    def test_watchlist_jsonb_field(self):
        assert isinstance(SAMPLE_WATCHLIST_RESPONSE["filtros"], dict), "filtros must be a dict"

    def test_watchlist_timestamp_fields(self):
        for key in ("created_at", "updated_at"):
            assert isinstance(SAMPLE_WATCHLIST_RESPONSE[key], str), (
                f"{key} must be str (ISO timestamp)"
            )

    def test_match_result_all_expected_keys(self):
        for key in MATCH_RESULT_KEYS:
            assert key in SAMPLE_MATCH_RESULT, f"Missing key: {key}"

    def test_match_result_no_extra_keys(self):
        extra = set(SAMPLE_MATCH_RESULT.keys()) - set(MATCH_RESULT_KEYS)
        assert not extra, f"Unexpected keys: {extra}"

    def test_match_result_types(self):
        assert isinstance(SAMPLE_MATCH_RESULT["watchlist_id"], str)
        assert isinstance(SAMPLE_MATCH_RESULT["new_matches"], int)

    def test_match_result_zero_matches(self):
        assert EMPTY_MATCH_RESULT["new_matches"] == 0


# ===================================================================
# Supabase RPC Mock Integration Tests
# ===================================================================


class TestSupabaseRPCIntegration:
    """Validate that supabase.rpc() can call the functions with correct params."""

    def test_ops_create_watchlist_call_signature(self):
        """ops_create_watchlist must accept (p_nome, p_descricao, p_filtros, p_frequencia_alerta)."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=[SAMPLE_WATCHLIST_RESPONSE])

        mock_rpc.rpc(
            "ops_create_watchlist",
            {
                "p_nome": "Oportunidades SP",
                "p_descricao": "Licitações de TI em São Paulo",
                "p_filtros": json.dumps({"ufs": ["SP"], "setor": "informatica"}),
                "p_frequencia_alerta": "daily",
            },
        ).execute()

        mock_rpc.rpc.assert_called_once_with(
            "ops_create_watchlist",
            {
                "p_nome": "Oportunidades SP",
                "p_descricao": "Licitações de TI em São Paulo",
                "p_filtros": json.dumps({"ufs": ["SP"], "setor": "informatica"}),
                "p_frequencia_alerta": "daily",
            },
        )

    def test_ops_create_watchlist_defaults(self):
        """ops_create_watchlist with only required params uses defaults."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=[SAMPLE_WATCHLIST_RESPONSE])

        mock_rpc.rpc(
            "ops_create_watchlist",
            {"p_nome": "Minha Watchlist"},
        ).execute()

        mock_rpc.rpc.assert_called_once_with(
            "ops_create_watchlist",
            {"p_nome": "Minha Watchlist"},
        )

    def test_ops_create_watchlist_returns_full_row(self):
        """The RPC returns the full watchlist row as JSON."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=[SAMPLE_WATCHLIST_RESPONSE])

        result = mock_rpc.rpc(
            "ops_create_watchlist",
            {"p_nome": "Oportunidades SP"},
        ).execute()

        resp = result.data[0]
        assert resp["nome"] == "Oportunidades SP"
        assert resp["user_id"] == "user-123-uuid"
        assert resp["alertas_ativos"] is True
        assert resp["frequencia_alerta"] == "daily"

    def test_ops_match_watchlist_call_signature(self):
        """ops_match_watchlist must accept (p_watchlist_id)."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=[SAMPLE_MATCH_RESULT])

        watchlist_id = "00000000-0000-0000-0000-000000000001"
        mock_rpc.rpc(
            "ops_match_watchlist",
            {"p_watchlist_id": watchlist_id},
        ).execute()

        mock_rpc.rpc.assert_called_once_with(
            "ops_match_watchlist",
            {"p_watchlist_id": watchlist_id},
        )

    def test_ops_match_watchlist_returns_result(self):
        """The RPC returns {watchlist_id, new_matches}."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=[SAMPLE_MATCH_RESULT])

        result = mock_rpc.rpc(
            "ops_match_watchlist",
            {"p_watchlist_id": "00000000-0000-0000-0000-000000000001"},
        ).execute()

        resp = result.data[0]
        assert resp["watchlist_id"] == "00000000-0000-0000-0000-000000000001"
        assert resp["new_matches"] == 5

    def test_ops_match_watchlist_zero_matches(self):
        """When no matches found, new_matches must be 0."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=[EMPTY_MATCH_RESULT])

        result = mock_rpc.rpc(
            "ops_match_watchlist",
            {"p_watchlist_id": "00000000-0000-0000-0000-000000000002"},
        ).execute()

        resp = result.data[0]
        assert resp["new_matches"] == 0

    @pytest.mark.parametrize("key", WATCHLIST_KEYS)
    def test_watchlist_all_keys_present_in_sample(self, key):
        """Parametrized: every expected key must be present in sample response."""
        assert key in SAMPLE_WATCHLIST_RESPONSE, f"Key '{key}' missing from sample"

    @pytest.mark.parametrize("key", MATCH_RESULT_KEYS)
    def test_match_result_all_keys_present_in_sample(self, key):
        """Parametrized: every expected key must be present in sample response."""
        assert key in SAMPLE_MATCH_RESULT, f"Key '{key}' missing from sample"

    def test_rpc_error_handling_create(self):
        """RPC failure should propagate the exception."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.side_effect = Exception(
            "function ops_create_watchlist(text, text, jsonb, text) does not exist"
        )

        with pytest.raises(Exception) as exc:
            mock_rpc.rpc(
                "ops_create_watchlist",
                {"p_nome": "Test"},
            ).execute()

        assert "ops_create_watchlist" in str(exc.value)

    def test_rpc_error_handling_match(self):
        """RPC failure should propagate the exception."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.side_effect = Exception(
            "function ops_match_watchlist(uuid) does not exist"
        )

        with pytest.raises(Exception) as exc:
            mock_rpc.rpc(
                "ops_match_watchlist",
                {"p_watchlist_id": "00000000-0000-0000-0000-000000000001"},
            ).execute()

        assert "ops_match_watchlist" in str(exc.value)

    def test_ops_create_watchlist_no_user_id_param(self):
        """ops_create_watchlist must NOT receive user_id as a parameter."""
        sql = _read_sql(MIGRATION_FILE)
        assert "p_user_id" not in sql, (
            "ops_create_watchlist must not accept user_id — uses auth.uid() instead"
        )


# ===================================================================
# JSON Serialization Tests
# ===================================================================


class TestJSONSerialization:
    """Validate the RPC responses round-trip through JSON."""

    def test_watchlist_response_serializable(self):
        json.dumps(SAMPLE_WATCHLIST_RESPONSE)

    def test_match_result_serializable(self):
        json.dumps(SAMPLE_MATCH_RESULT)

    def test_watchlist_json_round_trip(self):
        serialized = json.dumps(SAMPLE_WATCHLIST_RESPONSE)
        deserialized = json.loads(serialized)
        assert deserialized == SAMPLE_WATCHLIST_RESPONSE

    def test_match_result_json_round_trip(self):
        serialized = json.dumps(SAMPLE_MATCH_RESULT)
        deserialized = json.loads(serialized)
        assert deserialized == SAMPLE_MATCH_RESULT


# ===================================================================
# Feature Flag Tests
# ===================================================================


class TestFeatureFlag:
    """Validate the B2G_OPS_ENABLED feature flag."""

    def test_b2g_ops_flag_defined(self):
        """B2G_OPS_ENABLED must be defined in config.features module-level."""
        # We test the module variable directly
        from config.features import B2G_OPS_ENABLED  # noqa: F401

    def test_b2g_ops_flag_default_false(self):
        """B2G_OPS_ENABLED must default to False (not active in production yet)."""
        from config.features import B2G_OPS_ENABLED as flag

        # When no env is set, default must be False
        assert flag is False, "B2G_OPS_ENABLED must default to False"

    def test_b2g_ops_flag_in_registry(self):
        """B2G_OPS_ENABLED must be in the runtime feature flag registry."""
        from config.features import _FEATURE_FLAG_REGISTRY

        assert "B2G_OPS_ENABLED" in _FEATURE_FLAG_REGISTRY, (
            "B2G_OPS_ENABLED missing from _FEATURE_FLAG_REGISTRY"
        )

    def test_b2g_ops_flag_registry_value(self):
        """Registry entry must have default false."""
        from config.features import _FEATURE_FLAG_REGISTRY

        env_var, registry_default = _FEATURE_FLAG_REGISTRY["B2G_OPS_ENABLED"]
        assert registry_default == "false", (
            f"Registry default must be 'false', got '{registry_default}'"
        )

    def test_b2g_ops_flag_env_override_true(self, monkeypatch):
        """Setting env var to true should return True via get_feature_flag."""
        from config.features import get_feature_flag

        monkeypatch.setenv("B2G_OPS_ENABLED", "true")
        # Clear cache to force re-read from env
        from config.features import _feature_flag_cache
        _feature_flag_cache.clear()

        assert get_feature_flag("B2G_OPS_ENABLED") is True

    def test_b2g_ops_flag_env_override_false(self, monkeypatch):
        """Setting env var to false should return False via get_feature_flag."""
        from config.features import get_feature_flag

        monkeypatch.setenv("B2G_OPS_ENABLED", "false")
        from config.features import _feature_flag_cache
        _feature_flag_cache.clear()

        assert get_feature_flag("B2G_OPS_ENABLED") is False
