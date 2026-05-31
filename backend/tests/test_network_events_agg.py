"""Tests for NETINT-001 — Schema network_events_agg + coleta anonimizada (Issue #1283).

Validates the migration SQL through static analysis:
  - Migration file structure (UP + DOWN)
  - Table schema and constraints
  - RPC function signature, security attributes, sanitization, and grants
  - RLS policies
  - Column addition to profiles
  - Output structure
  - Edge cases: sanitization, PII rejection, empty metadados, UPSERT behavior

No live DB connection needed. Follows the pattern from test_network_sector_migration.py.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MIGRATIONS_DIR = REPO_ROOT / "supabase" / "migrations"

MIGRATION_TIMESTAMP = "20260531232239"
UP_FILE = f"{MIGRATION_TIMESTAMP}_network_events_agg.sql"
DOWN_FILE = f"{MIGRATION_TIMESTAMP}_network_events_agg.down.sql"


def load_migration(filename: str) -> str:
    """Load a migration SQL file from the supabase migrations directory."""
    path = MIGRATIONS_DIR / filename
    assert path.exists(), f"Migration not found: {path}"
    return path.read_text(encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════
# AC: File Structure
# ═══════════════════════════════════════════════════════════════════════════


class TestMigrationFileStructure:
    """AC: Migration files exist and have correct structure."""

    def test_up_migration_exists(self):
        """UP migration file must exist."""
        assert (MIGRATIONS_DIR / UP_FILE).exists(), (
            f"UP migration file {UP_FILE} not found"
        )

    def test_down_migration_exists(self):
        """DOWN migration file must exist."""
        assert (MIGRATIONS_DIR / DOWN_FILE).exists(), (
            f"DOWN migration file {DOWN_FILE} not found"
        )

    def test_up_contains_begin_commit(self):
        """UP migration is wrapped in BEGIN / COMMIT."""
        sql = load_migration(UP_FILE)
        assert "BEGIN;" in sql
        assert sql.strip().endswith("COMMIT;")

    def test_down_contains_drop_table_if_exists(self):
        """DOWN migration drops the table using IF EXISTS."""
        sql = load_migration(DOWN_FILE)
        assert "DROP TABLE IF EXISTS" in sql
        assert "network_events_agg" in sql

    def test_down_contains_drop_rpc(self):
        """DOWN migration drops the RPC function."""
        sql = load_migration(DOWN_FILE)
        assert "DROP FUNCTION IF EXISTS" in sql
        assert "network_record_event" in sql

    def test_down_contains_drop_column(self):
        """DOWN migration drops the profiles column."""
        sql = load_migration(DOWN_FILE)
        assert "ALTER TABLE public.profiles" in sql
        assert "DROP COLUMN IF EXISTS" in sql
        assert "allow_network_analytics" in sql


# ═══════════════════════════════════════════════════════════════════════════
# AC: Table Schema
# ═══════════════════════════════════════════════════════════════════════════


class TestTableSchema:
    """AC: network_events_agg table has correct schema."""

    REQUIRED_COLUMNS = [
        "id UUID PRIMARY KEY DEFAULT gen_random_uuid()",
        "evento_tipo TEXT NOT NULL",
        "dimensao_tipo TEXT NOT NULL",
        "dimensao_valor TEXT NOT NULL",
        "periodo DATE NOT NULL",
        "contagem INTEGER DEFAULT 1",
        "metadados JSONB DEFAULT '{}'",
        "created_at TIMESTAMPTZ DEFAULT now()",
    ]

    @pytest.fixture(scope="class")
    def sql(self):
        return load_migration(UP_FILE)

    def test_creates_table(self, sql):
        """Creates network_events_agg table with IF NOT EXISTS."""
        assert "CREATE TABLE IF NOT EXISTS public.network_events_agg" in sql

    def test_has_all_required_columns(self, sql):
        """All required columns are present."""
        for col in self.REQUIRED_COLUMNS:
            assert col in sql, f"Required column definition not found: {col}"

    def test_has_comments(self, sql):
        """Table and columns have descriptive COMMENTs."""
        assert "COMMENT ON TABLE public.network_events_agg IS" in sql
        assert "COMMENT ON COLUMN" in sql

    def test_has_idempotent_creation(self, sql):
        """Uses IF NOT EXISTS for table creation."""
        assert "IF NOT EXISTS" in sql


# ═══════════════════════════════════════════════════════════════════════════
# AC: Indexes & Constraints
# ═══════════════════════════════════════════════════════════════════════════


class TestIndexesAndConstraints:
    """AC: Proper indexes and unique constraint for daily aggregation."""

    @pytest.fixture(scope="class")
    def sql(self):
        return load_migration(UP_FILE)

    def test_periodo_index(self, sql):
        """Creates index on (periodo, evento_tipo, dimensao_tipo)."""
        assert "CREATE INDEX IF NOT EXISTS idx_network_events_periodo" in sql
        assert "periodo, evento_tipo, dimensao_tipo" in sql

    def test_tipo_valor_index(self, sql):
        """Creates index on (evento_tipo, dimensao_valor)."""
        assert "CREATE INDEX IF NOT EXISTS idx_network_events_tipo_valor" in sql
        assert "evento_tipo, dimensao_valor" in sql

    def test_unique_daily_constraint(self, sql):
        """Creates unique constraint for daily aggregation."""
        assert "idx_network_events_unique_daily" in sql
        assert "UNIQUE USING INDEX" in sql
        assert "evento_tipo, dimensao_tipo, dimensao_valor, periodo" in sql


# ═══════════════════════════════════════════════════════════════════════════
# AC: RLS Policies
# ═══════════════════════════════════════════════════════════════════════════


class TestRLSPolicies:
    """AC: RLS policies allow SELECT for all roles (anonymized data)."""

    @pytest.fixture(scope="class")
    def sql(self):
        return load_migration(UP_FILE)

    def test_enable_rls(self, sql):
        """Enables RLS on network_events_agg."""
        assert "ALTER TABLE public.network_events_agg ENABLE ROW LEVEL SECURITY" in sql

    def test_select_policy_anon(self, sql):
        """SELECT policy for anon role."""
        assert "CREATE POLICY" in sql
        assert "network_events_agg_select_anon" in sql
        assert "TO anon" in sql
        assert "FOR SELECT" in sql

    def test_select_policy_authenticated(self, sql):
        """SELECT policy for authenticated role."""
        assert "network_events_agg_select_authenticated" in sql
        assert "TO authenticated" in sql
        assert "FOR SELECT" in sql

    def test_select_policy_service_role(self, sql):
        """SELECT policy for service_role."""
        assert "network_events_agg_select_service_role" in sql
        assert "TO service_role" in sql
        assert "FOR SELECT" in sql


# ═══════════════════════════════════════════════════════════════════════════
# AC: RPC network_record_event — Signature & Security
# ═══════════════════════════════════════════════════════════════════════════


class TestRPCSignature:
    """AC: RPC function has correct signature and security attributes."""

    FUNCTION_NAME = "public.network_record_event"

    @pytest.fixture(scope="class")
    def sql(self):
        return load_migration(UP_FILE)

    def _function_block(self, sql: str) -> str:
        """Extract the function definition block."""
        start = sql.find(f"CREATE OR REPLACE FUNCTION {self.FUNCTION_NAME}")
        assert start >= 0, "Function definition not found"
        end = sql.find("$$;", start)
        assert end >= 0, "Function body end not found"
        return sql[start:end + 3]

    def test_creates_or_replaces_function(self, sql):
        """Uses CREATE OR REPLACE FUNCTION."""
        assert f"CREATE OR REPLACE FUNCTION {self.FUNCTION_NAME}" in sql

    def test_returns_void(self, sql):
        """Returns void."""
        assert "RETURNS void" in sql

    def test_language_plpgsql(self, sql):
        """Uses LANGUAGE plpgsql."""
        assert "LANGUAGE plpgsql" in sql

    def test_security_definer(self, sql):
        """Uses SECURITY DEFINER."""
        assert "SECURITY DEFINER" in sql

    def test_search_path_sanitized(self, sql):
        """Sets search_path to public, pg_temp."""
        assert "SET search_path = public, pg_temp" in sql

    def test_has_parameters(self, sql):
        """Accepts required parameters."""
        assert "p_evento_tipo TEXT" in sql
        assert "p_dimensao_tipo TEXT" in sql
        assert "p_dimensao_valor TEXT" in sql
        assert "p_metadados JSONB DEFAULT '{}'" in sql

    def test_has_comment(self, sql):
        """Function has descriptive COMMENT."""
        assert "COMMENT ON FUNCTION public.network_record_event" in sql
        assert "NETINT-001" in sql
        assert "LGPD" in sql

    def test_input_validation(self, sql):
        """Validates all required parameters are not null/empty."""
        assert "p_evento_tipo IS NULL OR trim(p_evento_tipo) = ''" in sql
        assert "p_dimensao_tipo IS NULL OR trim(p_dimensao_tipo) = ''" in sql
        assert "p_dimensao_valor IS NULL OR trim(p_dimensao_valor) = ''" in sql
        assert "RAISE EXCEPTION" in sql

    def test_statement_timeout_set(self, sql):
        """Sets LOCAL statement_timeout for defense."""
        assert "SET LOCAL statement_timeout" in sql


# ═══════════════════════════════════════════════════════════════════════════
# AC: PII Sanitization (LGPD)
# ═══════════════════════════════════════════════════════════════════════════


class TestSanitization:
    """AC: RPC sanitizes metadados — never stores PII."""

    PROHIBITED_KEYS = [
        "user_id", "profile_id", "email", "cnpj", "cpf",
        "ip", "user_agent", "fingerprint", "telefone",
        "endereco", "nome", "token", "session_id",
        "userId", "customerId", "profileId",
    ]

    @pytest.fixture(scope="class")
    def sql(self):
        return load_migration(UP_FILE)

    def test_defines_prohibited_keys_array(self, sql):
        """Defines an array of prohibited keys."""
        assert "v_proibido" in sql
        for key in ["user_id", "profile_id", "email", "cnpj", "cpf"]:
            assert f"'{key}'" in sql, f"Prohibited key '{key}' not found in array"

    def test_removes_prohibited_keys(self, sql):
        """Removes prohibited keys via FOREACH loop."""
        assert "FOREACH v_key IN ARRAY v_proibido" in sql
        assert "v_sanitized := v_sanitized - v_key" in sql

    def test_removes_camel_case_variants(self, sql):
        """Removes camelCase variants of prohibited keys."""
        assert "replace(v_key, '_', '')" in sql
        assert "upper(v_key)" in sql
        assert "initcap(v_key)" in sql

    def test_removes_keys_ending_in_id(self, sql):
        """Removes any keys ending with 'id', 'Id', or 'ID'."""
        assert "key ~* '.*(id|Id|ID)$'" in sql

    def test_rejects_cnpj_pattern(self, sql):
        """Rejects metadados containing CNPJ (14-digit pattern)."""
        assert "CNPJ" in sql
        assert "rejeitado por seguranca LGPD" in sql

    def test_rejects_email_pattern(self, sql):
        """Rejects metadados containing email pattern."""
        assert "email" in sql
        assert "rejeitado por seguranca LGPD" in sql

    def test_rejects_uuid_pattern(self, sql):
        """Rejects metadados containing UUID pattern."""
        assert "UUID" in sql
        assert "rejeitado por seguranca LGPD" in sql

    def test_rejects_ip_pattern(self, sql):
        """Rejects metadados containing IP pattern."""
        assert "IP" in sql
        assert "rejeitado por seguranca LGPD" in sql

    def test_handles_null_metadados(self, sql):
        """Handles NULL metadados gracefully — defaults to empty JSONB."""
        assert "v_sanitized := '{}'::jsonb" in sql


# ═══════════════════════════════════════════════════════════════════════════
# AC: UPSERT Behavior
# ═══════════════════════════════════════════════════════════════════════════


class TestUpsertBehavior:
    """AC: RPC uses UPSERT — increments contagem if same combo exists."""

    @pytest.fixture(scope="class")
    def sql(self):
        return load_migration(UP_FILE)

    def test_uses_insert_on_conflict(self, sql):
        """Uses INSERT ... ON CONFLICT for UPSERT."""
        assert "ON CONFLICT ON CONSTRAINT network_events_agg_unique_daily" in sql

    def test_increments_contagem(self, sql):
        """Increments contagem on conflict."""
        assert "contagem = public.network_events_agg.contagem + 1" in sql

    def test_merges_metadados_on_conflict(self, sql):
        """Merges metadados arrays on conflict (no duplicates)."""
        assert "jsonb_agg(DISTINCT elem)" in sql
        assert "FULL OUTER JOIN" in sql

    def test_creates_current_date(self, sql):
        """Uses CURRENT_DATE for periodo."""
        assert "CURRENT_DATE" in sql


# ═══════════════════════════════════════════════════════════════════════════
# AC: Profiles Column Addition
# ═══════════════════════════════════════════════════════════════════════════


class TestProfilesColumn:
    """AC: profiles.allow_network_analytics column added."""

    @pytest.fixture(scope="class")
    def sql(self):
        return load_migration(UP_FILE)

    def test_adds_column(self, sql):
        """Adds allow_network_analytics BOOLEAN DEFAULT NULL."""
        assert "ADD COLUMN IF NOT EXISTS allow_network_analytics BOOLEAN DEFAULT NULL" in sql

    def test_column_is_nullable(self, sql):
        """Column is nullable — no NOT NULL constraint."""
        assert "DEFAULT NULL" in sql

    def test_has_comment(self, sql):
        """Column has descriptive COMMENT."""
        assert "COMMENT ON COLUMN public.profiles.allow_network_analytics IS" in sql
        assert "NETINT-001" in sql
        assert "LGPD" in sql


# ═══════════════════════════════════════════════════════════════════════════
# AC: Grants
# ═══════════════════════════════════════════════════════════════════════════


class TestGrants:
    """AC: Proper GRANT permissions."""

    @pytest.fixture(scope="class")
    def sql(self):
        return load_migration(UP_FILE)

    def test_grant_select_anon(self, sql):
        """GRANT SELECT to anon on network_events_agg."""
        assert "GRANT SELECT ON public.network_events_agg TO anon" in sql

    def test_grant_select_authenticated(self, sql):
        """GRANT SELECT to authenticated on network_events_agg."""
        assert "GRANT SELECT ON public.network_events_agg TO authenticated" in sql

    def test_grant_select_service_role(self, sql):
        """GRANT SELECT to service_role on network_events_agg."""
        assert "GRANT SELECT ON public.network_events_agg TO service_role" in sql

    def test_grant_execute_rpc_authenticated(self, sql):
        """GRANT EXECUTE on RPC to authenticated."""
        assert "GRANT EXECUTE ON FUNCTION public.network_record_event" in sql
        assert "TO authenticated" in sql

    def test_grant_execute_rpc_service_role(self, sql):
        """GRANT EXECUTE on RPC to service_role."""
        assert "GRANT EXECUTE ON FUNCTION public.network_record_event" in sql
        assert "TO service_role" in sql

    def test_no_direct_dml_for_anon(self, sql):
        """No INSERT/UPDATE/DELETE grants to anon (DML via RPC only)."""
        # Verify no DML grants to anon exist anywhere in the migration
        for dml in ["INSERT", "UPDATE", "DELETE"]:
            pattern = re.compile(rf"GRANT\s+{dml}\s+ON.*TO\s+anon", re.IGNORECASE)
            assert not pattern.search(sql), (
                f"Found {dml} grant to anon — DML must be RPC-only"
            )
        # Verify SELECT grant to anon exists
        assert re.search(
            r"GRANT\s+SELECT\s+ON\s+public\.network_events_agg\s+TO\s+anon",
            sql, re.IGNORECASE
        ), "SELECT grant to anon not found"


# ═══════════════════════════════════════════════════════════════════════════
# AC: No PII in Schema
# ═══════════════════════════════════════════════════════════════════════════


class TestNoPII:
    """AC: Schema has no columns capable of storing individual PII."""

    @pytest.fixture(scope="class")
    def sql(self):
        return load_migration(UP_FILE)

    def test_no_user_id_column(self, sql):
        """Network_events_agg table has no user_id column."""
        table_def = sql[sql.find("CREATE TABLE"):sql.find(");", sql.find("CREATE TABLE"))]
        assert "user_id" not in table_def, "Table contains user_id column"

    def test_no_cnpj_column(self, sql):
        """Network_events_agg table has no cnpj column."""
        table_def = sql[sql.find("CREATE TABLE"):sql.find(");", sql.find("CREATE TABLE"))]
        assert "cnpj" not in table_def

    def test_no_email_column(self, sql):
        """Network_events_agg table has no email column."""
        table_def = sql[sql.find("CREATE TABLE"):sql.find(");", sql.find("CREATE TABLE"))]
        assert "email" not in table_def

    def test_aggregated_data_only(self, sql):
        """Data model is aggregated (contagem INTEGER, no individual rows)."""
        assert "contagem INTEGER DEFAULT 1" in sql


# ═══════════════════════════════════════════════════════════════════════════
# AC: Edge Cases
# ═══════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """AC: Edge cases handled correctly."""

    @pytest.fixture(scope="class")
    def sql(self):
        return load_migration(UP_FILE)

    def test_empty_metadados_default(self, sql):
        """Empty metadados defaults to '{}'."""
        assert "DEFAULT '{}'::jsonb" in sql

    def test_null_metadados_handling(self, sql):
        """NULL metadados handled — defaults to empty JSONB."""
        block = sql[sql.find("IF p_metadados IS NULL"):
                    sql.find("IF p_metadados IS NULL") + 100]
        assert "v_sanitized := '{}'::jsonb" in block

    def test_trim_on_text_fields(self, sql):
        """Text fields are trimmed on insert."""
        assert "trim(p_evento_tipo)" in sql
        assert "trim(p_dimensao_tipo)" in sql
        assert "trim(p_dimensao_valor)" in sql

    def test_empty_string_rejected(self, sql):
        """Empty strings rejected via input validation."""
        assert "trim(p_evento_tipo) = ''" in sql
        assert "trim(p_dimensao_tipo) = ''" in sql
        assert "trim(p_dimensao_valor) = ''" in sql

    def test_allowed_event_types_suggested(self, sql):
        """COMMENT suggests allowed evento_tipo values."""
        assert "COMMENT ON COLUMN public.network_events_agg.evento_tipo IS" in sql
        assert "search_query" in sql
        assert "sector_view" in sql
        assert "org_view" in sql
        assert "cnpj_lookup" in sql

    def test_allowed_dimension_types_suggested(self, sql):
        """COMMENT suggests allowed dimensao_tipo values."""
        assert "COMMENT ON COLUMN public.network_events_agg.dimensao_tipo IS" in sql
        assert "setor" in sql
        assert "uf" in sql
        assert "modalidade" in sql
        assert "orgao" in sql
        assert "municipio" in sql
