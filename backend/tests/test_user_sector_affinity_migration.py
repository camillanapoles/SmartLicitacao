"""Tests for FEEDBACK-001 — user_sector_affinity migration (Issue #1435).

Validates the migration SQL through static analysis:
  - Migration file structure (UP + DOWN)
  - Table schema (columns, PK, FK, CHECK constraint)
  - RLS policies
  - Trigger function
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MIGRATIONS_DIR = REPO_ROOT / "supabase" / "migrations"

MIGRATION_TIMESTAMP = "20260604135548"
UP_FILE = f"{MIGRATION_TIMESTAMP}_create_user_sector_affinity.sql"
DOWN_FILE = f"{MIGRATION_TIMESTAMP}_create_user_sector_affinity.down.sql"


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

    def test_down_drops_table(self):
        """DOWN migration drops the table with IF EXISTS."""
        sql = load_migration(DOWN_FILE)
        assert "DROP TABLE IF EXISTS public.user_sector_affinity CASCADE" in sql

    def test_down_drops_trigger(self):
        """DOWN migration drops the trigger with IF EXISTS."""
        sql = load_migration(DOWN_FILE)
        assert "DROP TRIGGER IF EXISTS trg_user_sector_affinity_updated_at" in sql

    def test_down_drops_policy(self):
        """DOWN migration drops the RLS policy with IF EXISTS."""
        sql = load_migration(DOWN_FILE)
        assert 'DROP POLICY IF EXISTS "usa_owner_all" ON public.user_sector_affinity' in sql


# ═══════════════════════════════════════════════════════════════════════════
# AC: Table Schema
# ═══════════════════════════════════════════════════════════════════════════


class TestTableSchema:
    """AC: Table has correct columns, types, constraints."""

    @pytest.fixture(scope="class")
    def sql(self):
        return load_migration(UP_FILE)

    def test_creates_table(self, sql):
        """Migration creates user_sector_affinity table."""
        assert "CREATE TABLE public.user_sector_affinity" in sql

    def test_has_user_id_column(self, sql):
        """Has user_id UUID NOT NULL column."""
        assert "user_id" in sql
        assert "UUID" in sql
        assert "NOT NULL" in sql

    def test_has_sector_id_column(self, sql):
        """Has sector_id VARCHAR NOT NULL column."""
        assert "sector_id" in sql
        assert "VARCHAR" in sql
        assert "NOT NULL" in sql

    def test_has_affinity_score_column(self, sql):
        """Has affinity_score NUMERIC(3,2) with DEFAULT 0.5."""
        assert "affinity_score" in sql
        assert "NUMERIC(3,2)" in sql
        assert "DEFAULT 0.5" in sql

    def test_has_updated_at_column(self, sql):
        """Has updated_at TIMESTAMPTZ with DEFAULT now()."""
        assert "updated_at" in sql
        assert "TIMESTAMPTZ" in sql
        assert "DEFAULT now()" in sql

    def test_has_primary_key(self, sql):
        """Has composite PRIMARY KEY (user_id, sector_id)."""
        assert "PRIMARY KEY (user_id, sector_id)" in sql

    def test_has_check_constraint(self, sql):
        """Has CHECK constraint for affinity_score range [0.0, 1.0]."""
        assert "CHECK" in sql
        assert "affinity_score >= 0.0" in sql
        assert "affinity_score <= 1.0" in sql

    def test_has_foreign_key_to_profiles(self, sql):
        """Has FK to profiles(id) with ON DELETE CASCADE."""
        assert "REFERENCES profiles(id)" in sql
        assert "ON DELETE CASCADE" in sql


# ═══════════════════════════════════════════════════════════════════════════
# AC: RLS
# ═══════════════════════════════════════════════════════════════════════════


class TestRLS:
    """AC: RLS is enabled with owner-only policies."""

    @pytest.fixture(scope="class")
    def sql(self):
        return load_migration(UP_FILE)

    def test_rls_enabled(self, sql):
        """RLS is enabled on the table."""
        assert "ALTER TABLE public.user_sector_affinity ENABLE ROW LEVEL SECURITY;" in sql

    def test_owner_policy_exists(self, sql):
        """FOR ALL policy checks auth.uid() = user_id."""
        assert "FOR ALL" in sql
        assert "auth.uid() = user_id" in sql

    def test_owner_policy_using_clause(self, sql):
        """Policy has USING clause for SELECT/UPDATE/DELETE."""
        assert "USING (auth.uid() = user_id)" in sql

    def test_owner_policy_with_check(self, sql):
        """Policy has WITH CHECK clause for INSERT/UPDATE."""
        assert "WITH CHECK (auth.uid() = user_id)" in sql

    def test_grant_to_authenticated(self, sql):
        """GRANT SELECT, INSERT, UPDATE, DELETE to authenticated."""
        assert "GRANT SELECT, INSERT, UPDATE, DELETE ON public.user_sector_affinity TO authenticated" in sql

    def test_grant_to_service_role(self, sql):
        """GRANT ALL to service_role."""
        assert "GRANT ALL ON public.user_sector_affinity TO service_role" in sql


# ═══════════════════════════════════════════════════════════════════════════
# AC: Trigger
# ═══════════════════════════════════════════════════════════════════════════


class TestTrigger:
    """AC: Trigger auto-updates updated_at on row modification."""

    @pytest.fixture(scope="class")
    def sql(self):
        return load_migration(UP_FILE)

    def test_creates_trigger_function(self, sql):
        """Creates trigger function set_user_sector_affinity_updated_at()."""
        assert "CREATE OR REPLACE FUNCTION public.set_user_sector_affinity_updated_at()" in sql

    def test_trigger_function_sets_updated_at(self, sql):
        """Trigger function sets NEW.updated_at = now()."""
        assert "NEW.updated_at = now()" in sql

    def test_trigger_has_security_definer(self, sql):
        """Trigger function uses SECURITY DEFINER."""
        assert "SECURITY DEFINER" in sql

    def test_trigger_has_sanitized_search_path(self, sql):
        """Trigger function sets search_path = public, pg_temp."""
        assert "SET search_path = public, pg_temp" in sql

    def test_trigger_is_before_update(self, sql):
        """Trigger fires BEFORE UPDATE FOR EACH ROW."""
        assert "BEFORE UPDATE" in sql
        assert "FOR EACH ROW" in sql
        assert "EXECUTE FUNCTION public.set_user_sector_affinity_updated_at()" in sql

    def test_comment_on_table_exists(self, sql):
        """Has COMMENT ON TABLE."""
        assert "COMMENT ON TABLE" in sql

    def test_comment_on_columns_exists(self, sql):
        """Has at least one COMMENT ON COLUMN."""
        assert sql.count("COMMENT ON COLUMN") >= 3
