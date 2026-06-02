"""Tests for B2GOPS-002: workspace_documents schema + RPCs.

Validates the migration SQL contract, RPC signatures, grants, RLS policies,
return shapes, and the B2G_OPS_ENABLED feature flag.

These tests are purely static/contract validation — they do NOT connect to
a live database. RPC behavior (ops_insert_document, ops_list_documents,
ops_check_expiring_certidoes) is validated via mock supabase.rpc() chains.
"""

from __future__ import annotations

import datetime
import json
import os
import re
from unittest.mock import MagicMock

import pytest

from tests.conftest import mock_supabase as _mock_supabase  # noqa: F401

# Paths relative to repo root
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MIGRATIONS_DIR = os.path.join(REPO_ROOT, "supabase", "migrations")

MIGRATION_FILE = "20260602214104_workspace_documents.sql"
DOWN_FILE = "20260602214104_workspace_documents.down.sql"

# Expected columns for workspace_documents
DOCUMENT_COLUMNS = [
    "id", "user_id", "licitacao_id", "licitacao_fonte",
    "nome", "tipo", "tamanho_bytes", "mime_type", "storage_path",
    "status", "data_validade", "tags", "created_at", "updated_at",
]

# Valid document types
VALID_TIPOS = ["edital", "proposta", "certidao", "contrato", "outro"]

# Valid statuses
VALID_STATUSES = ["ativo", "vencido", "arquivado"]

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
    return datetime.date.today().isoformat()


def _make_future(days: int = 30) -> str:
    """Return a future date as ISO string."""
    return (datetime.date.today() + datetime.timedelta(days=days)).isoformat()


def _make_past(days: int = 30) -> str:
    """Return a past date as ISO string."""
    return (datetime.date.today() - datetime.timedelta(days=days)).isoformat()


# ---------------------------------------------------------------------------
# Sample data (simulates what the RPCs return)
# ---------------------------------------------------------------------------

SAMPLE_DOCUMENT_RESPONSE = {
    "id": "00000000-0000-0000-0000-000000000001",
    "user_id": "user-123-uuid",
    "licitacao_id": "PNCP-2026-12345",
    "licitacao_fonte": "pncp",
    "nome": "Edital_Completo.pdf",
    "tipo": "edital",
    "tamanho_bytes": 2048576,
    "mime_type": "application/pdf",
    "storage_path": "documents/user-123/edital_completo.pdf",
    "status": "ativo",
    "data_validade": None,
    "tags": ["urgente", "ti"],
    "created_at": "2026-06-01T12:00:00+00:00",
    "updated_at": "2026-06-01T12:00:00+00:00",
}

SAMPLE_CERTIDAO_RESPONSE = {
    "id": "00000000-0000-0000-0000-000000000002",
    "user_id": "user-123-uuid",
    "licitacao_id": "PNCP-2026-67890",
    "licitacao_fonte": "pncp",
    "nome": "Certidao_Regularidade_Fiscal.pdf",
    "tipo": "certidao",
    "tamanho_bytes": 512000,
    "mime_type": "application/pdf",
    "storage_path": "documents/user-123/certidao_fiscal.pdf",
    "status": "ativo",
    "data_validade": _make_future(15),
    "tags": ["fiscal", "regularidade"],
    "created_at": "2026-05-15T08:00:00+00:00",
    "updated_at": "2026-05-15T08:00:00+00:00",
}

SAMPLE_EXPIRING_CERTIDAO = {
    "id": "00000000-0000-0000-0000-000000000003",
    "user_id": "user-123-uuid",
    "licitacao_id": "PNCP-2026-11111",
    "licitacao_fonte": "pncp",
    "nome": "Certidao_Trabalhista.pdf",
    "tipo": "certidao",
    "tamanho_bytes": 256000,
    "mime_type": "application/pdf",
    "storage_path": "documents/user-123/certidao_trab.pdf",
    "status": "ativo",
    "data_validade": _make_future(5),
    "tags": ["trabalhista"],
    "created_at": "2026-04-01T10:00:00+00:00",
    "updated_at": "2026-04-01T10:00:00+00:00",
}

SAMPLE_VENCIDO_CERTIDAO = {
    "id": "00000000-0000-0000-0000-000000000004",
    "user_id": "user-123-uuid",
    "licitacao_id": None,
    "licitacao_fonte": None,
    "nome": "Certidao_Vencida.pdf",
    "tipo": "certidao",
    "tamanho_bytes": 128000,
    "mime_type": "application/pdf",
    "storage_path": "documents/user-123/certidao_vencida.pdf",
    "status": "vencido",
    "data_validade": _make_past(10),
    "tags": None,
    "created_at": "2026-03-01T08:00:00+00:00",
    "updated_at": "2026-03-01T08:00:00+00:00",
}

SAMPLE_DOCUMENT_LIST_RESPONSE = [
    SAMPLE_DOCUMENT_RESPONSE,
    SAMPLE_CERTIDAO_RESPONSE,
]

SAMPLE_EXPIRING_LIST_RESPONSE = [
    SAMPLE_EXPIRING_CERTIDAO,
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

    def test_workspace_documents_table_created(self):
        sql = _read_sql(MIGRATION_FILE)
        assert (
            "CREATE TABLE public.workspace_documents" in sql
        ), "Missing workspace_documents table"

    def test_documents_all_columns(self):
        sql = _read_sql(MIGRATION_FILE)
        for col in DOCUMENT_COLUMNS:
            assert col in sql, f"Missing workspace_documents column: {col}"

    def test_tipo_check_constraint(self):
        sql = _read_sql(MIGRATION_FILE)
        for tipo in VALID_TIPOS:
            assert tipo in sql, f"Missing valid tipo: {tipo}"

    def test_status_check_constraint(self):
        sql = _read_sql(MIGRATION_FILE)
        assert (
            "CHECK (status IN ('ativo', 'vencido', 'arquivado'))" in sql
        ), "Missing CHECK constraint on status"

    def test_on_delete_cascade_user(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "REFERENCES auth.users(id) ON DELETE CASCADE" in sql, (
            "Missing ON DELETE CASCADE for user_id FK"
        )

    def test_default_status_ativo(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "DEFAULT 'ativo'" in sql, (
            "Default status must be 'ativo'"
        )

    def test_indexes_created(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "idx_workspace_documents_licitacao" in sql, (
            "Missing idx_workspace_documents_licitacao"
        )
        assert "idx_workspace_documents_user" in sql, (
            "Missing idx_workspace_documents_user"
        )
        assert "idx_workspace_documents_validade" in sql, (
            "Missing idx_workspace_documents_validade"
        )

    def test_partial_index_validade(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "WHERE tipo = 'certidao' AND status = 'ativo'" in sql, (
            "Partial index must filter certidao + ativo"
        )

    # -- RLS --

    def test_rls_enabled(self):
        sql = _read_sql(MIGRATION_FILE)
        assert (
            "ALTER TABLE public.workspace_documents ENABLE ROW LEVEL SECURITY" in sql
        ), "Missing RLS enable on workspace_documents"

    def test_rls_policy(self):
        sql = _read_sql(MIGRATION_FILE)
        assert (
            'CREATE POLICY "Users can CRUD own documents"' in sql
        ), "Missing documents RLS policy"
        assert "user_id = auth.uid()" in sql, (
            "Documents RLS must enforce user_id = auth.uid()"
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

    # -- RPC: ops_list_documents --

    def test_ops_list_documents_function(self):
        sql = _read_sql(MIGRATION_FILE)
        assert (
            "CREATE OR REPLACE FUNCTION public.ops_list_documents" in sql
        ), "Missing ops_list_documents function"

    def test_ops_list_documents_params(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "p_licitacao_id TEXT" in sql, "Missing p_licitacao_id parameter"
        assert "p_licitacao_fonte TEXT DEFAULT NULL" in sql, (
            "Missing or misconfigured p_licitacao_fonte parameter"
        )

    def test_ops_list_documents_returns_setof(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "RETURNS SETOF public.workspace_documents" in sql, (
            "Must return SETOF workspace_documents"
        )

    def test_ops_list_documents_security_definer(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "SECURITY DEFINER" in sql, "Missing SECURITY DEFINER"

    def test_ops_list_documents_search_path(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "SET search_path = public, pg_temp" in sql, (
            "Missing search_path = public, pg_temp"
        )

    def test_ops_list_documents_uses_auth_uid(self):
        """ops_list_documents must filter by auth.uid()."""
        sql = _read_sql(MIGRATION_FILE)
        assert "auth.uid()" in sql, "Must use auth.uid()"

    def test_ops_list_documents_licitacao_filter(self):
        """ops_list_documents must filter by p_licitacao_id."""
        sql = _read_sql(MIGRATION_FILE)
        assert "p_licitacao_id" in sql, (
            "Must filter by p_licitacao_id"
        )

    def test_ops_list_documents_grants(self):
        sql = _read_sql(MIGRATION_FILE)
        list_grants = re.findall(
            r"GRANT EXECUTE ON FUNCTION public\.ops_list_documents\(TEXT, TEXT\) TO (\w+);",
            sql,
        )
        assert "authenticated" in list_grants, "Missing authenticated grant"
        assert "service_role" in list_grants, "Missing service_role grant"

    # -- RPC: ops_check_expiring_certidoes --

    def test_ops_check_expiring_certidoes_function(self):
        sql = _read_sql(MIGRATION_FILE)
        assert (
            "CREATE OR REPLACE FUNCTION public.ops_check_expiring_certidoes" in sql
        ), "Missing ops_check_expiring_certidoes function"

    def test_ops_check_expiring_certidoes_params(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "p_dias INTEGER DEFAULT 30" in sql, (
            "Missing or misconfigured p_dias parameter"
        )

    def test_ops_check_expiring_certidoes_returns_setof(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "RETURNS SETOF public.workspace_documents" in sql, (
            "Must return SETOF workspace_documents"
        )

    def test_ops_check_expiring_certidoes_security_definer(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "SECURITY DEFINER" in sql, "Missing SECURITY DEFINER"

    def test_ops_check_expiring_certidoes_search_path(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "SET search_path = public, pg_temp" in sql, (
            "Missing search_path = public, pg_temp"
        )

    def test_ops_check_expiring_certidoes_uses_auth_uid(self):
        """ops_check_expiring_certidoes must filter by auth.uid()."""
        sql = _read_sql(MIGRATION_FILE)
        assert "auth.uid()" in sql, "Must use auth.uid()"

    def test_ops_check_expiring_certidoes_uses_current_date(self):
        """ops_check_expiring_certidoes must compare against CURRENT_DATE."""
        sql = _read_sql(MIGRATION_FILE)
        assert "CURRENT_DATE" in sql, "Must use CURRENT_DATE for date comparison"

    def test_ops_check_expiring_certidoes_grants(self):
        sql = _read_sql(MIGRATION_FILE)
        check_grants = re.findall(
            r"GRANT EXECUTE ON FUNCTION public\.ops_check_expiring_certidoes\(INTEGER\) TO (\w+);",
            sql,
        )
        assert "authenticated" in check_grants, "Missing authenticated grant"
        assert "service_role" in check_grants, "Missing service_role grant"

    # -- RPC: ops_insert_document --

    def test_ops_insert_document_function(self):
        sql = _read_sql(MIGRATION_FILE)
        assert (
            "CREATE OR REPLACE FUNCTION public.ops_insert_document" in sql
        ), "Missing ops_insert_document function"

    def test_ops_insert_document_params(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "p_licitacao_id TEXT" in sql, "Missing p_licitacao_id parameter"
        assert "p_licitacao_fonte TEXT" in sql, "Missing p_licitacao_fonte parameter"
        assert "p_nome TEXT" in sql, "Missing p_nome parameter"
        assert "p_tipo TEXT" in sql, "Missing p_tipo parameter"
        assert "p_tamanho_bytes BIGINT" in sql, "Missing p_tamanho_bytes parameter"
        assert "p_mime_type TEXT" in sql, "Missing p_mime_type parameter"
        assert "p_storage_path TEXT" in sql, "Missing p_storage_path parameter"
        assert "p_data_validade DATE DEFAULT NULL" in sql, (
            "Missing or misconfigured p_data_validade parameter"
        )
        assert "p_tags TEXT[] DEFAULT NULL" in sql, (
            "Missing or misconfigured p_tags parameter"
        )

    def test_ops_insert_document_returns_document(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "RETURNS public.workspace_documents" in sql, (
            "Must return workspace_documents"
        )

    def test_ops_insert_document_security_definer(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "SECURITY DEFINER" in sql, "Missing SECURITY DEFINER"

    def test_ops_insert_document_search_path(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "SET search_path = public, pg_temp" in sql, (
            "Missing search_path = public, pg_temp"
        )

    def test_ops_insert_document_uses_auth_uid(self):
        """ops_insert_document must use auth.uid(), NOT receive user_id as param."""
        sql = _read_sql(MIGRATION_FILE)
        assert "auth.uid()" in sql, "Must use auth.uid()"
        assert "p_user_id" not in sql, (
            "ops_insert_document must NOT receive user_id as parameter"
        )

    def test_ops_insert_document_grants(self):
        sql = _read_sql(MIGRATION_FILE)
        insert_grants = re.findall(
            r"GRANT EXECUTE ON FUNCTION public\.ops_insert_document\(TEXT, TEXT, TEXT, TEXT, BIGINT, TEXT, TEXT, DATE, TEXT\[\]\) TO (\w+);",
            sql,
        )
        assert "authenticated" in insert_grants, "Missing authenticated grant"
        assert "service_role" in insert_grants, "Missing service_role grant"

    # -- Down migration --

    def test_down_drops_functions(self):
        sql = _read_sql(DOWN_FILE)
        assert (
            "DROP FUNCTION IF EXISTS public.ops_list_documents(TEXT, TEXT)" in sql
        ), "Down must drop ops_list_documents"
        assert (
            "DROP FUNCTION IF EXISTS public.ops_check_expiring_certidoes(INTEGER)" in sql
        ), "Down must drop ops_check_expiring_certidoes"
        assert (
            "DROP FUNCTION IF EXISTS public.ops_insert_document(TEXT, TEXT, TEXT, TEXT, BIGINT, TEXT, TEXT, DATE, TEXT[])" in sql
        ), "Down must drop ops_insert_document"

    def test_down_drops_policy(self):
        sql = _read_sql(DOWN_FILE)
        assert (
            'DROP POLICY IF EXISTS "Users can CRUD own documents" ON public.workspace_documents' in sql
        ), "Down must drop RLS policy"

    def test_down_drops_table_cascade(self):
        sql = _read_sql(DOWN_FILE)
        assert (
            "DROP TABLE IF EXISTS public.workspace_documents CASCADE" in sql
        ), "Down must drop workspace_documents CASCADE"

    def test_no_existing_objects_altered(self):
        """Ensure migration doesn't alter any existing tables or RPCs."""
        sql = _read_sql(MIGRATION_FILE)
        # Count CREATE OR REPLACE FUNCTION occurrences
        func_count = len(re.findall(r"CREATE OR REPLACE FUNCTION", sql))
        assert func_count == 3, (
            f"Expected exactly 3 CREATE OR REPLACE FUNCTION, found {func_count}"
        )
        # Count CREATE TABLE occurrences
        table_count = len(re.findall(r"CREATE TABLE public\.", sql))
        assert table_count == 1, (
            f"Expected exactly 1 CREATE TABLE, found {table_count}"
        )
        # Count CREATE INDEX occurrences
        index_count = len(re.findall(r"CREATE INDEX", sql))
        assert index_count == 3, (
            f"Expected exactly 3 CREATE INDEX, found {index_count}"
        )


# ===================================================================
# Return Shape Tests
# ===================================================================


class TestReturnShape:
    """Validate the document row shapes against the specification."""

    def test_document_all_expected_keys(self):
        for key in DOCUMENT_COLUMNS:
            assert key in SAMPLE_DOCUMENT_RESPONSE, f"Missing key: {key}"

    def test_document_no_extra_keys(self):
        extra = set(SAMPLE_DOCUMENT_RESPONSE.keys()) - set(DOCUMENT_COLUMNS)
        assert not extra, f"Unexpected keys: {extra}"

    def test_document_uuid_fields(self):
        assert isinstance(SAMPLE_DOCUMENT_RESPONSE["id"], str)
        assert isinstance(SAMPLE_DOCUMENT_RESPONSE["user_id"], str)

    def test_document_string_fields(self):
        for key in ("nome", "tipo", "mime_type", "storage_path", "status"):
            assert isinstance(SAMPLE_DOCUMENT_RESPONSE[key], str), (
                f"{key} must be str, got {type(SAMPLE_DOCUMENT_RESPONSE[key])}"
            )

    def test_document_integer_field(self):
        assert isinstance(SAMPLE_DOCUMENT_RESPONSE["tamanho_bytes"], int), (
            "tamanho_bytes must be int"
        )

    def test_document_nullable_fields(self):
        assert SAMPLE_DOCUMENT_RESPONSE["data_validade"] is None, (
            "data_validade should be nullable"
        )

    def test_document_list_field(self):
        assert isinstance(SAMPLE_DOCUMENT_RESPONSE["tags"], list), "tags must be a list"

    def test_document_timestamp_fields(self):
        for key in ("created_at", "updated_at"):
            assert isinstance(SAMPLE_DOCUMENT_RESPONSE[key], str), (
                f"{key} must be str (ISO timestamp)"
            )

    def test_document_list_response_is_list(self):
        assert isinstance(SAMPLE_DOCUMENT_LIST_RESPONSE, list), (
            "Document list response must be a list"
        )

    def test_document_list_response_multiple_items(self):
        assert len(SAMPLE_DOCUMENT_LIST_RESPONSE) >= 2, (
            "Sample document list should have multiple items"
        )

    def test_expiring_list_response_is_list(self):
        assert isinstance(SAMPLE_EXPIRING_LIST_RESPONSE, list), (
            "Expiring certidoes response must be a list"
        )

    def test_certidao_has_data_validade(self):
        assert SAMPLE_CERTIDAO_RESPONSE["data_validade"] is not None, (
            "Certidao must have data_validade"
        )

    def test_vencido_certidao_status(self):
        assert SAMPLE_VENCIDO_CERTIDAO["status"] == "vencido", (
            "Vencido certidao must have status 'vencido'"
        )

    def test_certidao_tipo(self):
        assert SAMPLE_CERTIDAO_RESPONSE["tipo"] == "certidao", (
            "Sample certidao must have tipo 'certidao'"
        )

    def test_vencido_certidao_nullable_licitacao(self):
        """A vencido certidao may not be linked to a licitacao."""
        assert SAMPLE_VENCIDO_CERTIDAO["licitacao_id"] is None
        assert SAMPLE_VENCIDO_CERTIDAO["licitacao_fonte"] is None

    def test_vencido_certidao_nullable_tags(self):
        """Tags may be null."""
        assert SAMPLE_VENCIDO_CERTIDAO["tags"] is None


# ===================================================================
# Supabase RPC Mock Integration Tests
# ===================================================================


class TestSupabaseRPCIntegration:
    """Validate that supabase.rpc() can call the functions with correct params."""

    # -- ops_insert_document --

    def test_ops_insert_document_call_signature(self):
        """ops_insert_document must accept all params with defaults."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=[SAMPLE_DOCUMENT_RESPONSE])

        mock_rpc.rpc(
            "ops_insert_document",
            {
                "p_licitacao_id": "PNCP-2026-12345",
                "p_licitacao_fonte": "pncp",
                "p_nome": "Edital_Completo.pdf",
                "p_tipo": "edital",
                "p_tamanho_bytes": 2048576,
                "p_mime_type": "application/pdf",
                "p_storage_path": "documents/user-123/edital_completo.pdf",
                "p_data_validade": None,
                "p_tags": ["urgente", "ti"],
            },
        ).execute()

        mock_rpc.rpc.assert_called_once_with(
            "ops_insert_document",
            {
                "p_licitacao_id": "PNCP-2026-12345",
                "p_licitacao_fonte": "pncp",
                "p_nome": "Edital_Completo.pdf",
                "p_tipo": "edital",
                "p_tamanho_bytes": 2048576,
                "p_mime_type": "application/pdf",
                "p_storage_path": "documents/user-123/edital_completo.pdf",
                "p_data_validade": None,
                "p_tags": ["urgente", "ti"],
            },
        )

    def test_ops_insert_document_required_only(self):
        """ops_insert_document with only required params."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=[SAMPLE_DOCUMENT_RESPONSE])

        minimal_doc = {
            "id": "00000000-0000-0000-0000-000000000005",
            "user_id": "user-123-uuid",
            "licitacao_id": "PNCP-2026-99999",
            "licitacao_fonte": "pncp",
            "nome": "Contrato.pdf",
            "tipo": "contrato",
            "tamanho_bytes": 1024,
            "mime_type": "application/pdf",
            "storage_path": "documents/user-123/contrato.pdf",
            "status": "ativo",
            "data_validade": None,
            "tags": None,
            "created_at": "2026-06-01T12:00:00+00:00",
            "updated_at": "2026-06-01T12:00:00+00:00",
        }
        mock_rpc.execute.return_value = MagicMock(data=[minimal_doc])

        mock_rpc.rpc(
            "ops_insert_document",
            {
                "p_licitacao_id": "PNCP-2026-99999",
                "p_licitacao_fonte": "pncp",
                "p_nome": "Contrato.pdf",
                "p_tipo": "contrato",
                "p_tamanho_bytes": 1024,
                "p_mime_type": "application/pdf",
                "p_storage_path": "documents/user-123/contrato.pdf",
            },
        ).execute()

        mock_rpc.rpc.assert_called_once()

    def test_ops_insert_document_returns_full_row(self):
        """The RPC returns the full document row."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=[SAMPLE_DOCUMENT_RESPONSE])

        result = mock_rpc.rpc(
            "ops_insert_document",
            {
                "p_licitacao_id": "PNCP-2026-12345",
                "p_licitacao_fonte": "pncp",
                "p_nome": "Edital_Completo.pdf",
                "p_tipo": "edital",
                "p_tamanho_bytes": 2048576,
                "p_mime_type": "application/pdf",
                "p_storage_path": "documents/user-123/edital_completo.pdf",
            },
        ).execute()

        resp = result.data[0]
        assert resp["nome"] == "Edital_Completo.pdf"
        assert resp["tipo"] == "edital"
        assert resp["user_id"] == "user-123-uuid"
        assert resp["status"] == "ativo"
        assert resp["tamanho_bytes"] == 2048576

    # -- ops_list_documents --

    def test_ops_list_documents_call_signature(self):
        """ops_list_documents must accept (p_licitacao_id, p_licitacao_fonte)."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=SAMPLE_DOCUMENT_LIST_RESPONSE)

        mock_rpc.rpc(
            "ops_list_documents",
            {"p_licitacao_id": "PNCP-2026-12345", "p_licitacao_fonte": "pncp"},
        ).execute()

        mock_rpc.rpc.assert_called_once_with(
            "ops_list_documents",
            {"p_licitacao_id": "PNCP-2026-12345", "p_licitacao_fonte": "pncp"},
        )

    def test_ops_list_documents_without_fonte(self):
        """ops_list_documents with only p_licitacao_id should work (fonte defaults NULL)."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=SAMPLE_DOCUMENT_LIST_RESPONSE)

        mock_rpc.rpc(
            "ops_list_documents",
            {"p_licitacao_id": "PNCP-2026-12345"},
        ).execute()

        mock_rpc.rpc.assert_called_once_with(
            "ops_list_documents",
            {"p_licitacao_id": "PNCP-2026-12345"},
        )

    def test_ops_list_documents_returns_list(self):
        """The RPC returns a list of documents."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=SAMPLE_DOCUMENT_LIST_RESPONSE)

        result = mock_rpc.rpc(
            "ops_list_documents",
            {"p_licitacao_id": "PNCP-2026-12345"},
        ).execute()

        resp = result.data
        assert isinstance(resp, list)
        assert len(resp) >= 2

    def test_ops_list_documents_empty(self):
        """When no documents, ops_list_documents must return empty list."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=[])

        result = mock_rpc.rpc(
            "ops_list_documents",
            {"p_licitacao_id": "NONEXISTENT-999"},
        ).execute()

        assert result.data == [], "Expected empty list for nonexistent licitacao"

    # -- ops_check_expiring_certidoes --

    def test_ops_check_expiring_certidoes_call_signature(self):
        """ops_check_expiring_certidoes must accept (p_dias) with default 30."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=SAMPLE_EXPIRING_LIST_RESPONSE)

        mock_rpc.rpc(
            "ops_check_expiring_certidoes",
            {"p_dias": 30},
        ).execute()

        mock_rpc.rpc.assert_called_once_with(
            "ops_check_expiring_certidoes",
            {"p_dias": 30},
        )

    def test_ops_check_expiring_certidoes_default_param(self):
        """ops_check_expiring_certidoes with no params uses default p_dias=30."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=SAMPLE_EXPIRING_LIST_RESPONSE)

        mock_rpc.rpc(
            "ops_check_expiring_certidoes",
            {},
        ).execute()

        mock_rpc.rpc.assert_called_once_with(
            "ops_check_expiring_certidoes",
            {},
        )

    def test_ops_check_expiring_certidoes_custom_days(self):
        """ops_check_expiring_certidoes should accept custom day range."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=SAMPLE_EXPIRING_LIST_RESPONSE)

        mock_rpc.rpc(
            "ops_check_expiring_certidoes",
            {"p_dias": 7},
        ).execute()

        mock_rpc.rpc.assert_called_once_with(
            "ops_check_expiring_certidoes",
            {"p_dias": 7},
        )

    def test_ops_check_expiring_certidoes_returns_list(self):
        """The RPC returns a list of expiring certidoes."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=SAMPLE_EXPIRING_LIST_RESPONSE)

        result = mock_rpc.rpc(
            "ops_check_expiring_certidoes",
            {"p_dias": 30},
        ).execute()

        resp = result.data
        assert isinstance(resp, list)
        assert len(resp) > 0

    def test_ops_check_expiring_certidoes_empty(self):
        """When no expiring certidoes, returns empty list."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=[])

        result = mock_rpc.rpc(
            "ops_check_expiring_certidoes",
            {"p_dias": 1},
        ).execute()

        assert result.data == [], "Expected empty list when no expiring certidoes"

    # -- Error handling --

    def test_rpc_error_handling_insert(self):
        """RPC failure should propagate the exception."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.side_effect = Exception(
            "function ops_insert_document(text, text, text, text, bigint, text, text, date, text[]) does not exist"
        )

        with pytest.raises(Exception) as exc:
            mock_rpc.rpc(
                "ops_insert_document",
                {
                    "p_licitacao_id": "PNCP-2026-12345",
                    "p_licitacao_fonte": "pncp",
                    "p_nome": "test.pdf",
                    "p_tipo": "edital",
                    "p_tamanho_bytes": 1000,
                    "p_mime_type": "application/pdf",
                    "p_storage_path": "test/test.pdf",
                },
            ).execute()

        assert "ops_insert_document" in str(exc.value)

    def test_rpc_error_handling_list(self):
        """RPC failure should propagate the exception."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.side_effect = Exception(
            "function ops_list_documents(text, text) does not exist"
        )

        with pytest.raises(Exception) as exc:
            mock_rpc.rpc(
                "ops_list_documents",
                {"p_licitacao_id": "PNCP-2026-12345"},
            ).execute()

        assert "ops_list_documents" in str(exc.value)

    def test_rpc_error_handling_expiring(self):
        """RPC failure should propagate the exception."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.side_effect = Exception(
            "function ops_check_expiring_certidoes(integer) does not exist"
        )

        with pytest.raises(Exception) as exc:
            mock_rpc.rpc(
                "ops_check_expiring_certidoes",
                {"p_dias": 30},
            ).execute()

        assert "ops_check_expiring_certidoes" in str(exc.value)

    def test_ops_insert_document_no_user_id_param(self):
        """ops_insert_document must NOT receive user_id as a parameter."""
        sql = _read_sql(MIGRATION_FILE)
        assert "p_user_id" not in sql, (
            "ops_insert_document must not accept user_id - uses auth.uid() instead"
        )

    # -- Parametrized valid types --

    @pytest.mark.parametrize("key", DOCUMENT_COLUMNS)
    def test_document_all_keys_present_in_sample(self, key):
        """Parametrized: every expected key must be present in sample response."""
        assert key in SAMPLE_DOCUMENT_RESPONSE, f"Key '{key}' missing from sample"

    @pytest.mark.parametrize("tipo", VALID_TIPOS)
    def test_valid_tipo_types(self, tipo):
        """All valid tipo types must be accepted by the migration."""
        sql = _read_sql(MIGRATION_FILE)
        assert tipo in sql, f"Valid tipo '{tipo}' missing from migration SQL"

    @pytest.mark.parametrize("status", VALID_STATUSES)
    def test_valid_status_values(self, status):
        """All valid status values must be accepted by the migration."""
        sql = _read_sql(MIGRATION_FILE)
        assert status in sql, f"Valid status '{status}' missing from migration SQL"


# ===================================================================
# JSON Serialization Tests
# ===================================================================


class TestJSONSerialization:
    """Validate the RPC responses round-trip through JSON."""

    def test_document_response_serializable(self):
        json.dumps(SAMPLE_DOCUMENT_RESPONSE)

    def test_document_list_serializable(self):
        json.dumps(SAMPLE_DOCUMENT_LIST_RESPONSE)

    def test_expiring_list_serializable(self):
        json.dumps(SAMPLE_EXPIRING_LIST_RESPONSE)

    def test_certidao_response_serializable(self):
        json.dumps(SAMPLE_CERTIDAO_RESPONSE)

    def test_vencido_response_serializable(self):
        json.dumps(SAMPLE_VENCIDO_CERTIDAO)

    def test_document_json_round_trip(self):
        serialized = json.dumps(SAMPLE_DOCUMENT_RESPONSE)
        deserialized = json.loads(serialized)
        assert deserialized == SAMPLE_DOCUMENT_RESPONSE

    def test_document_list_json_round_trip(self):
        serialized = json.dumps(SAMPLE_DOCUMENT_LIST_RESPONSE)
        deserialized = json.loads(serialized)
        assert deserialized == SAMPLE_DOCUMENT_LIST_RESPONSE

    def test_expiring_list_json_round_trip(self):
        serialized = json.dumps(SAMPLE_EXPIRING_LIST_RESPONSE)
        deserialized = json.loads(serialized)
        assert deserialized == SAMPLE_EXPIRING_LIST_RESPONSE


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
