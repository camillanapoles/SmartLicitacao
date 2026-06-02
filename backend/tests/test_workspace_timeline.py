"""Tests for B2GOPS-003: workspace_timeline schema + RPCs (Wave 0).

Validates the migration SQL contract, RPC signatures, grants, RLS policies,
return shapes, overdue trigger, and the B2G_OPS_ENABLED feature flag.

These tests are purely static/contract validation — they do NOT connect to
a live database. RPC behavior (ops_add_timeline_event, ops_get_timeline,
ops_upcoming_events) is validated via mock supabase.rpc() chains.
"""

from __future__ import annotations

import json
import os
import re
from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from tests.conftest import mock_supabase as _mock_supabase  # noqa: F401

# Paths relative to repo root
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MIGRATIONS_DIR = os.path.join(REPO_ROOT, "supabase", "migrations")

MIGRATION_FILE = "20260601000002_workspace_timeline.sql"
DOWN_FILE = "20260601000002_workspace_timeline.down.sql"

# Expected columns for workspace_timeline
TIMELINE_COLUMNS = [
    "id", "user_id", "licitacao_id", "licitacao_fonte",
    "evento", "data_evento", "data_prevista", "responsavel", "notas",
    "status", "created_at", "updated_at",
]

# Expected JSON keys from ops_add_timeline_event
TIMELINE_EVENT_KEYS = [
    "id", "user_id", "licitacao_id", "licitacao_fonte",
    "evento", "data_evento", "data_prevista", "responsavel", "notas",
    "status", "created_at", "updated_at",
]

# Valid event types
VALID_EVENTOS = [
    "publicacao", "impugnacao", "esclarecimento", "abertura",
    "habilitacao", "recurso", "homologacao", "adjudicacao", "contrato",
]

# Valid statuses
VALID_STATUSES = ["pendente", "concluido", "atrasado"]

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


def _make_today() -> str:
    """Return today's date as ISO string for test samples."""
    return date.today().isoformat()


def _make_future(days: int = 5) -> str:
    """Return a future date as ISO string."""
    return (date.today() + timedelta(days=days)).isoformat()


def _make_past(days: int = 3) -> str:
    """Return a past date as ISO string."""
    return (date.today() - timedelta(days=days)).isoformat()


# ---------------------------------------------------------------------------
# Sample data (simulates what the RPCs return)
# ---------------------------------------------------------------------------

SAMPLE_EVENT_RESPONSE = {
    "id": "00000000-0000-0000-0000-000000000001",
    "user_id": "user-123-uuid",
    "licitacao_id": "PNCP-2026-12345",
    "licitacao_fonte": "pncp",
    "evento": "abertura",
    "data_evento": _make_future(5),
    "data_prevista": None,
    "responsavel": "Maria Silva",
    "notas": "Sessao publica as 14h",
    "status": "pendente",
    "created_at": "2026-05-31T12:00:00+00:00",
    "updated_at": "2026-05-31T12:00:00+00:00",
}

SAMPLE_EVENT_OVERDUE_RESPONSE = {
    "id": "00000000-0000-0000-0000-000000000002",
    "user_id": "user-123-uuid",
    "licitacao_id": "PNCP-2026-67890",
    "licitacao_fonte": "pncp",
    "evento": "esclarecimento",
    "data_evento": _make_past(5),
    "data_prevista": None,
    "responsavel": None,
    "notas": "Prazo vencido",
    "status": "atrasado",
    "created_at": "2026-05-25T10:00:00+00:00",
    "updated_at": "2026-05-25T10:00:00+00:00",
}

SAMPLE_TIMELINE_RESPONSE = [
    {
        "id": "00000000-0000-0000-0000-000000000003",
        "user_id": "user-123-uuid",
        "licitacao_id": "PNCP-2026-12345",
        "licitacao_fonte": "pncp",
        "evento": "publicacao",
        "data_evento": _make_past(10),
        "data_prevista": None,
        "responsavel": None,
        "notas": "Edital publicado no DOU",
        "status": "concluido",
        "created_at": "2026-05-21T08:00:00+00:00",
        "updated_at": "2026-05-21T08:00:00+00:00",
    },
    SAMPLE_EVENT_RESPONSE,
]

SAMPLE_UPCOMING_RESPONSE = [
    SAMPLE_EVENT_RESPONSE,
]


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

    # -- Table --

    def test_workspace_timeline_table_created(self):
        sql = _read_sql(MIGRATION_FILE)
        assert (
            "CREATE TABLE public.workspace_timeline" in sql
        ), "Missing workspace_timeline table"

    def test_timeline_all_columns(self):
        sql = _read_sql(MIGRATION_FILE)
        for col in TIMELINE_COLUMNS:
            assert col in sql, f"Missing workspace_timeline column: {col}"

    def test_evento_check_constraint(self):
        sql = _read_sql(MIGRATION_FILE)
        for evento in VALID_EVENTOS:
            assert evento in sql, f"Missing valid evento: {evento}"

    def test_status_check_constraint(self):
        sql = _read_sql(MIGRATION_FILE)
        assert (
            "CHECK (status IN ('pendente', 'concluido', 'atrasado'))" in sql
        ), "Missing CHECK constraint on status"

    def test_on_delete_cascade_user(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "REFERENCES auth.users(id) ON DELETE CASCADE" in sql, (
            "Missing ON DELETE CASCADE for user_id FK"
        )

    def test_indexes_created(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "idx_timeline_user" in sql, "Missing idx_timeline_user"
        assert "idx_timeline_licitacao" in sql, "Missing idx_timeline_licitacao"
        assert "idx_timeline_upcoming" in sql, "Missing idx_timeline_upcoming"
        assert "idx_timeline_status_due" in sql, "Missing idx_timeline_status_due"

    def test_default_status_pendente(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "DEFAULT 'pendente'" in sql, (
            "Default status must be 'pendente'"
        )

    # -- Triggers --

    def test_updated_at_trigger_function(self):
        sql = _read_sql(MIGRATION_FILE)
        assert (
            "CREATE OR REPLACE FUNCTION public.set_workspace_timeline_updated_at" in sql
        ), "Missing updated_at trigger function"

    def test_updated_at_trigger(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "trg_workspace_timeline_updated_at" in sql, (
            "Missing trg_workspace_timeline_updated_at"
        )

    def test_overdue_trigger_function(self):
        sql = _read_sql(MIGRATION_FILE)
        assert (
            "CREATE OR REPLACE FUNCTION public.set_overdue_timeline_status" in sql
        ), "Missing overdue trigger function"

    def test_overdue_trigger(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "trg_workspace_timeline_overdue" in sql, (
            "Missing trg_workspace_timeline_overdue"
        )

    def test_overdue_trigger_condition(self):
        """Overdue trigger checks data_evento < CURRENT_DATE and status = 'pendente'."""
        sql = _read_sql(MIGRATION_FILE)
        assert "data_evento < CURRENT_DATE" in sql, (
            "Trigger must check data_evento < CURRENT_DATE"
        )
        assert "status = 'pendente'" in sql, (
            "Trigger must check status = 'pendente'"
        )
        assert "NEW.status := 'atrasado'" in sql, (
            "Trigger must set status to 'atrasado'"
        )

    # -- RLS --

    def test_rls_enabled_on_timeline(self):
        sql = _read_sql(MIGRATION_FILE)
        assert (
            "ALTER TABLE public.workspace_timeline ENABLE ROW LEVEL SECURITY" in sql
        ), "Missing RLS enable on workspace_timeline"

    def test_timeline_rls_policy(self):
        sql = _read_sql(MIGRATION_FILE)
        assert (
            'CREATE POLICY "Users can CRUD own timeline"' in sql
        ), "Missing timeline RLS policy"
        assert "user_id = auth.uid()" in sql, (
            "Timeline RLS must enforce user_id = auth.uid()"
        )

    # -- Grants --

    def test_service_role_grant(self):
        sql = _read_sql(MIGRATION_FILE)
        service_grants = re.findall(r"GRANT ALL ON public\.\w+ TO service_role;", sql)
        assert len(service_grants) == 1, (
            f"Expected 1 service_role grant, found {len(service_grants)}: {service_grants}"
        )

    def test_authenticated_grant(self):
        sql = _read_sql(MIGRATION_FILE)
        auth_grants = re.findall(
            r"GRANT SELECT, INSERT, UPDATE, DELETE ON public\.\w+ TO authenticated;", sql
        )
        assert len(auth_grants) == 1, (
            f"Expected 1 authenticated grant, found {len(auth_grants)}: {auth_grants}"
        )

    # -- RPC: ops_add_timeline_event --

    def test_ops_add_timeline_event_function(self):
        sql = _read_sql(MIGRATION_FILE)
        assert (
            "CREATE OR REPLACE FUNCTION public.ops_add_timeline_event" in sql
        ), "Missing ops_add_timeline_event function"

    def test_ops_add_timeline_event_params(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "p_licitacao_id TEXT" in sql, "Missing p_licitacao_id parameter"
        assert "p_licitacao_fonte TEXT" in sql, (
            "Missing p_licitacao_fonte parameter"
        )
        assert "p_evento TEXT" in sql, "Missing p_evento parameter"
        assert "p_data_evento DATE" in sql, "Missing p_data_evento parameter"
        assert "p_data_prevista DATE DEFAULT NULL" in sql, (
            "Missing or misconfigured p_data_prevista parameter"
        )
        assert "p_responsavel TEXT DEFAULT NULL" in sql, (
            "Missing or misconfigured p_responsavel parameter"
        )
        assert "p_notas TEXT DEFAULT NULL" in sql, (
            "Missing or misconfigured p_notas parameter"
        )
        assert "p_status TEXT DEFAULT 'pendente'" in sql, (
            "Missing or misconfigured p_status parameter"
        )

    def test_ops_add_timeline_event_returns_json(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "RETURNS json" in sql, "Must return json"

    def test_ops_add_timeline_event_security_definer(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "SECURITY DEFINER" in sql, "Missing SECURITY DEFINER"

    def test_ops_add_timeline_event_search_path(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "SET search_path = public, pg_temp" in sql, (
            "Missing search_path = public, pg_temp"
        )

    def test_ops_add_timeline_event_uses_auth_uid(self):
        """ops_add_timeline_event must use auth.uid(), NOT receive user_id as param."""
        sql = _read_sql(MIGRATION_FILE)
        assert "auth.uid()" in sql, "Must use auth.uid()"
        assert "p_user_id" not in sql, (
            "ops_add_timeline_event must NOT receive user_id as parameter"
        )

    def test_ops_add_timeline_event_grants(self):
        sql = _read_sql(MIGRATION_FILE)
        add_grants = re.findall(
            r"GRANT EXECUTE ON FUNCTION public\.ops_add_timeline_event\(TEXT, TEXT, TEXT, DATE, DATE, TEXT, TEXT, TEXT\) TO (\w+);",
            sql,
        )
        assert "authenticated" in add_grants, "Missing authenticated grant"
        assert "service_role" in add_grants, "Missing service_role grant"

    # -- RPC: ops_get_timeline --

    def test_ops_get_timeline_function(self):
        sql = _read_sql(MIGRATION_FILE)
        assert (
            "CREATE OR REPLACE FUNCTION public.ops_get_timeline" in sql
        ), "Missing ops_get_timeline function"

    def test_ops_get_timeline_params(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "p_licitacao_id TEXT" in sql, "Missing p_licitacao_id parameter"

    def test_ops_get_timeline_returns_json(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "RETURNS json" in sql, "Must return json"

    def test_ops_get_timeline_security_definer(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "SECURITY DEFINER" in sql, "Missing SECURITY DEFINER"

    def test_ops_get_timeline_search_path(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "SET search_path = public, pg_temp" in sql, (
            "Missing search_path = public, pg_temp"
        )

    def test_ops_get_timeline_uses_auth_uid(self):
        """ops_get_timeline must filter by auth.uid()."""
        sql = _read_sql(MIGRATION_FILE)
        assert "auth.uid()" in sql, "Must use auth.uid()"

    def test_ops_get_timeline_licitacao_filter(self):
        """ops_get_timeline must filter by p_licitacao_id."""
        sql = _read_sql(MIGRATION_FILE)
        assert "p_licitacao_id" in sql, (
            "Must filter by p_licitacao_id"
        )

    def test_ops_get_timeline_grants(self):
        sql = _read_sql(MIGRATION_FILE)
        get_grants = re.findall(
            r"GRANT EXECUTE ON FUNCTION public\.ops_get_timeline\(TEXT\) TO (\w+);",
            sql,
        )
        assert "authenticated" in get_grants, "Missing authenticated grant"
        assert "service_role" in get_grants, "Missing service_role grant"

    # -- RPC: ops_upcoming_events --

    def test_ops_upcoming_events_function(self):
        sql = _read_sql(MIGRATION_FILE)
        assert (
            "CREATE OR REPLACE FUNCTION public.ops_upcoming_events" in sql
        ), "Missing ops_upcoming_events function"

    def test_ops_upcoming_events_params(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "p_dias INT DEFAULT 7" in sql, (
            "Missing or misconfigured p_dias parameter"
        )

    def test_ops_upcoming_events_returns_json(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "RETURNS json" in sql, "Must return json"

    def test_ops_upcoming_events_security_definer(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "SECURITY DEFINER" in sql, "Missing SECURITY DEFINER"

    def test_ops_upcoming_events_search_path(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "SET search_path = public, pg_temp" in sql, (
            "Missing search_path = public, pg_temp"
        )

    def test_ops_upcoming_events_uses_auth_uid(self):
        """ops_upcoming_events must filter by auth.uid()."""
        sql = _read_sql(MIGRATION_FILE)
        assert "auth.uid()" in sql, "Must use auth.uid()"

    def test_ops_upcoming_events_grants(self):
        sql = _read_sql(MIGRATION_FILE)
        upcoming_grants = re.findall(
            r"GRANT EXECUTE ON FUNCTION public\.ops_upcoming_events\(INT\) TO (\w+);",
            sql,
        )
        assert "authenticated" in upcoming_grants, "Missing authenticated grant"
        assert "service_role" in upcoming_grants, "Missing service_role grant"

    # -- Down migration --

    def test_down_drops_functions(self):
        sql = _read_sql(DOWN_FILE)
        assert (
            "DROP FUNCTION IF EXISTS public.ops_upcoming_events(INT)" in sql
        ), "Down must drop ops_upcoming_events"
        assert (
            "DROP FUNCTION IF EXISTS public.ops_get_timeline(TEXT)" in sql
        ), "Down must drop ops_get_timeline"
        assert (
            "DROP FUNCTION IF EXISTS public.ops_add_timeline_event(TEXT, TEXT, TEXT, DATE, DATE, TEXT, TEXT, TEXT)" in sql
        ), "Down must drop ops_add_timeline_event"

    def test_down_drops_triggers(self):
        sql = _read_sql(DOWN_FILE)
        assert (
            "DROP TRIGGER IF EXISTS trg_workspace_timeline_overdue" in sql
        ), "Down must drop trg_workspace_timeline_overdue"
        assert (
            "DROP TRIGGER IF EXISTS trg_workspace_timeline_updated_at" in sql
        ), "Down must drop trg_workspace_timeline_updated_at"

    def test_down_drops_trigger_functions(self):
        sql = _read_sql(DOWN_FILE)
        assert (
            "DROP FUNCTION IF EXISTS public.set_overdue_timeline_status()" in sql
        ), "Down must drop set_overdue_timeline_status"
        assert (
            "DROP FUNCTION IF EXISTS public.set_workspace_timeline_updated_at()" in sql
        ), "Down must drop set_workspace_timeline_updated_at"

    def test_down_drops_table_cascade(self):
        sql = _read_sql(DOWN_FILE)
        assert (
            "DROP TABLE IF EXISTS public.workspace_timeline CASCADE" in sql
        ), "Down must drop workspace_timeline CASCADE"

    def test_no_existing_objects_altered(self):
        """Ensure migration doesn't alter any existing tables or RPCs."""
        sql = _read_sql(MIGRATION_FILE)
        # Count CREATE OR REPLACE FUNCTION occurrences
        func_count = len(re.findall(r"CREATE OR REPLACE FUNCTION", sql))
        assert func_count == 5, (
            f"Expected exactly 5 CREATE OR REPLACE FUNCTION, found {func_count}"
        )
        # Count CREATE TABLE occurrences
        table_count = len(re.findall(r"CREATE TABLE public\.", sql))
        assert table_count == 1, (
            f"Expected exactly 1 CREATE TABLE, found {table_count}"
        )
        # Count CREATE TRIGGER occurrences
        trigger_count = len(re.findall(r"CREATE TRIGGER", sql))
        assert trigger_count == 2, (
            f"Expected exactly 2 CREATE TRIGGER, found {trigger_count}"
        )
        # Count CREATE INDEX occurrences
        index_count = len(re.findall(r"CREATE INDEX", sql))
        assert index_count == 4, (
            f"Expected exactly 4 CREATE INDEX, found {index_count}"
        )


# ===================================================================
# Return Shape Tests
# ===================================================================


class TestReturnShape:
    """Validate the RPC JSON shapes against the specification."""

    def test_timeline_event_all_expected_keys(self):
        for key in TIMELINE_EVENT_KEYS:
            assert key in SAMPLE_EVENT_RESPONSE, f"Missing key: {key}"

    def test_timeline_event_no_extra_keys(self):
        extra = set(SAMPLE_EVENT_RESPONSE.keys()) - set(TIMELINE_EVENT_KEYS)
        assert not extra, f"Unexpected keys: {extra}"

    def test_timeline_event_uuid_fields(self):
        assert isinstance(SAMPLE_EVENT_RESPONSE["id"], str)
        assert isinstance(SAMPLE_EVENT_RESPONSE["user_id"], str)

    def test_timeline_event_string_fields(self):
        for key in ("licitacao_id", "licitacao_fonte", "evento", "status"):
            assert isinstance(SAMPLE_EVENT_RESPONSE[key], str), (
                f"{key} must be str, got {type(SAMPLE_EVENT_RESPONSE[key])}"
            )

    def test_timeline_event_date_field(self):
        assert isinstance(SAMPLE_EVENT_RESPONSE["data_evento"], str), (
            "data_evento must be str (ISO date)"
        )

    def test_timeline_event_nullable_fields(self):
        assert SAMPLE_EVENT_RESPONSE["data_prevista"] is None, (
            "data_prevista should be nullable"
        )
        assert SAMPLE_EVENT_RESPONSE["responsavel"] is not None, (
            "responsavel should have a value in sample"
        )

    def test_timeline_event_timestamp_fields(self):
        for key in ("created_at", "updated_at"):
            assert isinstance(SAMPLE_EVENT_RESPONSE[key], str), (
                f"{key} must be str (ISO timestamp)"
            )

    def test_timeline_response_is_list(self):
        assert isinstance(SAMPLE_TIMELINE_RESPONSE, list), (
            "Timeline response must be a list"
        )

    def test_timeline_response_multiple_events(self):
        assert len(SAMPLE_TIMELINE_RESPONSE) >= 2, (
            "Sample timeline should have multiple events"
        )

    def test_upcoming_response_is_list(self):
        assert isinstance(SAMPLE_UPCOMING_RESPONSE, list), (
            "Upcoming response must be a list"
        )

    def test_overdue_event_status(self):
        assert SAMPLE_EVENT_OVERDUE_RESPONSE["status"] == "atrasado", (
            "Overdue event must have status 'atrasado'"
        )


# ===================================================================
# Supabase RPC Mock Integration Tests
# ===================================================================


class TestSupabaseRPCIntegration:
    """Validate that supabase.rpc() can call the functions with correct params."""

    def test_ops_add_timeline_event_call_signature(self):
        """ops_add_timeline_event must accept all params with defaults."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=[SAMPLE_EVENT_RESPONSE])

        mock_rpc.rpc(
            "ops_add_timeline_event",
            {
                "p_licitacao_id": "PNCP-2026-12345",
                "p_licitacao_fonte": "pncp",
                "p_evento": "abertura",
                "p_data_evento": _make_future(5),
                "p_data_prevista": None,
                "p_responsavel": "Maria Silva",
                "p_notas": "Sessao publica as 14h",
                "p_status": "pendente",
            },
        ).execute()

        mock_rpc.rpc.assert_called_once_with(
            "ops_add_timeline_event",
            {
                "p_licitacao_id": "PNCP-2026-12345",
                "p_licitacao_fonte": "pncp",
                "p_evento": "abertura",
                "p_data_evento": _make_future(5),
                "p_data_prevista": None,
                "p_responsavel": "Maria Silva",
                "p_notas": "Sessao publica as 14h",
                "p_status": "pendente",
            },
        )

    def test_ops_add_timeline_event_defaults(self):
        """ops_add_timeline_event with only required params uses defaults."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=[SAMPLE_EVENT_RESPONSE])

        mock_rpc.rpc(
            "ops_add_timeline_event",
            {
                "p_licitacao_id": "PNCP-2026-12345",
                "p_licitacao_fonte": "pncp",
                "p_evento": "publicacao",
                "p_data_evento": _make_today(),
            },
        ).execute()

        mock_rpc.rpc.assert_called_once_with(
            "ops_add_timeline_event",
            {
                "p_licitacao_id": "PNCP-2026-12345",
                "p_licitacao_fonte": "pncp",
                "p_evento": "publicacao",
                "p_data_evento": _make_today(),
            },
        )

    def test_ops_add_timeline_event_returns_full_row(self):
        """The RPC returns the full timeline event row as JSON."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=[SAMPLE_EVENT_RESPONSE])

        result = mock_rpc.rpc(
            "ops_add_timeline_event",
            {
                "p_licitacao_id": "PNCP-2026-12345",
                "p_licitacao_fonte": "pncp",
                "p_evento": "abertura",
                "p_data_evento": _make_future(5),
            },
        ).execute()

        resp = result.data[0]
        assert resp["licitacao_id"] == "PNCP-2026-12345"
        assert resp["evento"] == "abertura"
        assert resp["user_id"] == "user-123-uuid"
        assert resp["status"] == "pendente"
        assert resp["responsavel"] == "Maria Silva"

    def test_ops_get_timeline_call_signature(self):
        """ops_get_timeline must accept (p_licitacao_id)."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=SAMPLE_TIMELINE_RESPONSE)

        mock_rpc.rpc(
            "ops_get_timeline",
            {"p_licitacao_id": "PNCP-2026-12345"},
        ).execute()

        mock_rpc.rpc.assert_called_once_with(
            "ops_get_timeline",
            {"p_licitacao_id": "PNCP-2026-12345"},
        )

    def test_ops_get_timeline_returns_list(self):
        """The RPC returns a list of timeline events."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=SAMPLE_TIMELINE_RESPONSE)

        result = mock_rpc.rpc(
            "ops_get_timeline",
            {"p_licitacao_id": "PNCP-2026-12345"},
        ).execute()

        resp = result.data
        assert isinstance(resp, list)
        assert len(resp) >= 2

    def test_ops_get_timeline_events_have_correct_keys(self):
        """Each event in the timeline must have the expected keys."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=SAMPLE_TIMELINE_RESPONSE)

        result = mock_rpc.rpc(
            "ops_get_timeline",
            {"p_licitacao_id": "PNCP-2026-12345"},
        ).execute()

        for event in result.data:
            for key in TIMELINE_EVENT_KEYS:
                assert key in event, f"Event missing key: {key}"

    def test_ops_get_timeline_empty(self):
        """When no events, ops_get_timeline must return empty list."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=[])

        result = mock_rpc.rpc(
            "ops_get_timeline",
            {"p_licitacao_id": "NONEXISTENT-999"},
        ).execute()

        assert result.data == [], "Expected empty list for nonexistent licitacao"

    def test_ops_upcoming_events_call_signature(self):
        """ops_upcoming_events must accept (p_dias) with default 7."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=SAMPLE_UPCOMING_RESPONSE)

        mock_rpc.rpc(
            "ops_upcoming_events",
            {"p_dias": 7},
        ).execute()

        mock_rpc.rpc.assert_called_once_with(
            "ops_upcoming_events",
            {"p_dias": 7},
        )

    def test_ops_upcoming_events_default_param(self):
        """ops_upcoming_events with no params uses default p_dias=7."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=SAMPLE_UPCOMING_RESPONSE)

        mock_rpc.rpc(
            "ops_upcoming_events",
            {},
        ).execute()

        mock_rpc.rpc.assert_called_once_with(
            "ops_upcoming_events",
            {},
        )

    def test_ops_upcoming_events_custom_days(self):
        """ops_upcoming_events should accept custom day range."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=SAMPLE_UPCOMING_RESPONSE)

        mock_rpc.rpc(
            "ops_upcoming_events",
            {"p_dias": 30},
        ).execute()

        mock_rpc.rpc.assert_called_once_with(
            "ops_upcoming_events",
            {"p_dias": 30},
        )

    def test_ops_upcoming_events_returns_list(self):
        """The RPC returns a list of upcoming events."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=SAMPLE_UPCOMING_RESPONSE)

        result = mock_rpc.rpc(
            "ops_upcoming_events",
            {"p_dias": 7},
        ).execute()

        resp = result.data
        assert isinstance(resp, list)
        assert len(resp) > 0

    def test_ops_upcoming_events_empty(self):
        """When no upcoming events, ops_upcoming_events must return empty list."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=[])

        result = mock_rpc.rpc(
            "ops_upcoming_events",
            {"p_dias": 7},
        ).execute()

        assert result.data == [], "Expected empty list when no upcoming events"

    @pytest.mark.parametrize("key", TIMELINE_EVENT_KEYS)
    def test_timeline_event_all_keys_present_in_sample(self, key):
        """Parametrized: every expected key must be present in sample response."""
        assert key in SAMPLE_EVENT_RESPONSE, f"Key '{key}' missing from sample"

    @pytest.mark.parametrize("evento", VALID_EVENTOS)
    def test_valid_evento_types(self, evento):
        """All valid evento types must be accepted by the migration."""
        sql = _read_sql(MIGRATION_FILE)
        assert evento in sql, f"Valid evento '{evento}' missing from migration SQL"

    @pytest.mark.parametrize("status", VALID_STATUSES)
    def test_valid_status_values(self, status):
        """All valid status values must be accepted by the migration."""
        sql = _read_sql(MIGRATION_FILE)
        assert status in sql, f"Valid status '{status}' missing from migration SQL"

    def test_rpc_error_handling_add_event(self):
        """RPC failure should propagate the exception."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.side_effect = Exception(
            "function ops_add_timeline_event(text, text, text, date, date, text, text, text) does not exist"
        )

        with pytest.raises(Exception) as exc:
            mock_rpc.rpc(
                "ops_add_timeline_event",
                {
                    "p_licitacao_id": "PNCP-2026-12345",
                    "p_licitacao_fonte": "pncp",
                    "p_evento": "publicacao",
                    "p_data_evento": _make_today(),
                },
            ).execute()

        assert "ops_add_timeline_event" in str(exc.value)

    def test_rpc_error_handling_get_timeline(self):
        """RPC failure should propagate the exception."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.side_effect = Exception(
            "function ops_get_timeline(text) does not exist"
        )

        with pytest.raises(Exception) as exc:
            mock_rpc.rpc(
                "ops_get_timeline",
                {"p_licitacao_id": "PNCP-2026-12345"},
            ).execute()

        assert "ops_get_timeline" in str(exc.value)

    def test_rpc_error_handling_upcoming(self):
        """RPC failure should propagate the exception."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.side_effect = Exception(
            "function ops_upcoming_events(int) does not exist"
        )

        with pytest.raises(Exception) as exc:
            mock_rpc.rpc(
                "ops_upcoming_events",
                {"p_dias": 7},
            ).execute()

        assert "ops_upcoming_events" in str(exc.value)

    def test_ops_add_timeline_event_no_user_id_param(self):
        """ops_add_timeline_event must NOT receive user_id as a parameter."""
        sql = _read_sql(MIGRATION_FILE)
        assert "p_user_id" not in sql, (
            "ops_add_timeline_event must not accept user_id - uses auth.uid() instead"
        )


# ===================================================================
# Overdue Trigger Tests
# ===================================================================


class TestOverdueTrigger:
    """Validate the overdue trigger behavior logic."""

    def test_overdue_trigger_on_insert_past_date(self):
        """Inserting a past-due event with status 'pendente' should set 'atrasado'."""
        sql = _read_sql(MIGRATION_FILE)
        assert "IF NEW.data_evento < CURRENT_DATE AND NEW.status = 'pendente' THEN" in sql, (
            "Trigger must check data_evento < CURRENT_DATE"
        )
        assert "NEW.status := 'atrasado'" in sql, (
            "Trigger must set status to 'atrasado'"
        )

    def test_overdue_trigger_not_future_date(self):
        """A future-dated event with status 'pendente' should remain 'pendente'."""
        # Future event does not trigger the overdue status
        assert SAMPLE_EVENT_RESPONSE["status"] == "pendente", (
            "Future event must remain 'pendente'"
        )

    def test_overdue_trigger_not_concluido(self):
        """A past-due event with status 'concluido' must NOT be set to 'atrasado'."""
        sql = _read_sql(MIGRATION_FILE)
        # Trigger only fires when status = 'pendente'
        assert "status = 'pendente'" in sql, (
            "Trigger must only fire on status = 'pendente'"
        )

    def test_overdue_sample_data(self):
        """Sample overdue data should have status 'atrasado'."""
        assert SAMPLE_EVENT_OVERDUE_RESPONSE["status"] == "atrasado"
        # Verify it's in the past
        today = date.today()
        past_date = date.fromisoformat(SAMPLE_EVENT_OVERDUE_RESPONSE["data_evento"])
        assert past_date < today, "Overdue sample must have past data_evento"

    def test_trg_workspace_timeline_overdue_defined(self):
        """The trigger must be defined on the table."""
        sql = _read_sql(MIGRATION_FILE)
        assert (
            "CREATE TRIGGER trg_workspace_timeline_overdue" in sql
        ), "Missing trg_workspace_timeline_overdue definition"

    def test_overdue_trigger_on_insert_and_update(self):
        """The trigger must fire on INSERT OR UPDATE."""
        sql = _read_sql(MIGRATION_FILE)
        assert "BEFORE INSERT OR UPDATE" in sql, (
            "Trigger must be BEFORE INSERT OR UPDATE"
        )


# ===================================================================
# JSON Serialization Tests
# ===================================================================


class TestJSONSerialization:
    """Validate the RPC responses round-trip through JSON."""

    def test_timeline_event_serializable(self):
        json.dumps(SAMPLE_EVENT_RESPONSE)

    def test_timeline_list_serializable(self):
        json.dumps(SAMPLE_TIMELINE_RESPONSE)

    def test_upcoming_list_serializable(self):
        json.dumps(SAMPLE_UPCOMING_RESPONSE)

    def test_timeline_event_json_round_trip(self):
        serialized = json.dumps(SAMPLE_EVENT_RESPONSE)
        deserialized = json.loads(serialized)
        assert deserialized == SAMPLE_EVENT_RESPONSE

    def test_timeline_list_json_round_trip(self):
        serialized = json.dumps(SAMPLE_TIMELINE_RESPONSE)
        deserialized = json.loads(serialized)
        assert deserialized == SAMPLE_TIMELINE_RESPONSE

    def test_upcoming_list_json_round_trip(self):
        serialized = json.dumps(SAMPLE_UPCOMING_RESPONSE)
        deserialized = json.loads(serialized)
        assert deserialized == SAMPLE_UPCOMING_RESPONSE


# ===================================================================
# Feature Flag Tests
# ===================================================================


class TestFeatureFlag:
    """Validate the B2G_OPS_ENABLED feature flag."""

    def test_b2g_ops_flag_defined(self):
        """B2G_OPS_ENABLED must be defined in config.features module-level."""
        from config.features import B2G_OPS_ENABLED  # noqa: F401

    def test_b2g_ops_flag_default_true(self):
        """B2G_OPS_ENABLED must default to True (active in production)."""
        from config.features import B2G_OPS_ENABLED as flag

        assert flag is True, "B2G_OPS_ENABLED must default to True"

    def test_b2g_ops_flag_in_registry(self):
        """B2G_OPS_ENABLED must be in the runtime feature flag registry."""
        from config.features import _FEATURE_FLAG_REGISTRY

        assert "B2G_OPS_ENABLED" in _FEATURE_FLAG_REGISTRY, (
            "B2G_OPS_ENABLED missing from _FEATURE_FLAG_REGISTRY"
        )

    def test_b2g_ops_flag_registry_value(self):
        """Registry entry must have default true."""
        from config.features import _FEATURE_FLAG_REGISTRY

        env_var, registry_default = _FEATURE_FLAG_REGISTRY["B2G_OPS_ENABLED"]
        assert registry_default == "true", (
            f"Registry default must be 'true', got '{registry_default}'"
        )

    def test_b2g_ops_flag_env_override_true(self, monkeypatch):
        """Setting env var to true should return True via get_feature_flag."""
        from config.features import get_feature_flag

        monkeypatch.setenv("B2G_OPS_ENABLED", "true")
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
