# ADR-RLS-MANDATORY-001: RLS is Mandatory on Every `public` Schema Table

| Field | Value |
|-------|-------|
| Status | Accepted (2026-05-09) |
| Issue | [#969](https://github.com/tjsasakifln/SmartLic/issues/969) — RLS-AUDIT-001 |
| Stakeholders | @dev (lead), @architect, @qa |
| Supersedes | — |
| Superseded by | — |

## Context

`CLAUDE.md` § Security Notes claims "Supabase Auth with RLS on all
tables", but `_reversa_sdd/data-master.md` § 9 Lacunas flagged the
absence of an empirical export of `pg_policies`. The 2026-05-09 review
(`_reversa_sdd/review-report.md` § 15.3) scored RBAC/Security at 94 %
with the explicit driver:

> Closure of `feedback_secdef_search_path_trap` family + audit
> `pg_policy` export → RBAC/Security +5

Supabase's `service_role` bypasses RLS unconditionally, so a table that
ships without RLS enabled looks healthy from the backend's perspective
while exposing the same data to `anon` and `authenticated` clients via
PostgREST. The 2026-05-09 SECURITY DEFINER view downgrade (PR #955)
already absorbed one such gap; without a coverage gate, the next
omission lands silently.

The repo lacks a single source of truth for the live policy state and
no CI gate exists to catch a new table that ships without policies.

## Decision

1. **RLS-mandatory.** Every table in the `public` schema must have
   `ROW LEVEL SECURITY ENABLED` and at least one policy from
   `pg_policies` attached.
2. **Exemption path.** A table that is intentionally public (e.g.
   programmatic-SEO read-only tables, plan catalog) may opt out by
   carrying a comment of the form
   `-- rls-exempt: <one-line reason>`
   on or just above the `CREATE TABLE` / `ALTER TABLE` statement
   in `supabase/migrations/`. The reason must be specific enough to be
   re-evaluated 6 months later.
3. **Empirical audit.** `backend/scripts/audit_rls_coverage.py` is the
   source of truth. It queries `pg_tables` joined with `pg_policies`
   via the Supabase Management API
   (`POST /v1/projects/{ref}/database/query`) and writes
   `_reversa_sdd/rls-coverage-<UTC date>.md`. Exit code is `0` if all
   tables are compliant or exempt, `1` otherwise.
4. **CI gate.** `.github/workflows/audit-rls-coverage.yml` runs the
   script on push to `main`, weekly (Monday 06:00 UTC), and on manual
   dispatch. Failures block via the workflow status (no advisory
   bypass — RLS is non-negotiable).

## Consequences

- New tables that ship without an explicit policy or exemption marker
  fail CI on the first push to `main`, instead of being discovered via
  incident.
- The generated report is committed monthly (or on demand) and serves
  as the audit trail referenced by `_reversa_sdd/data-master.md`
  § "RLS Coverage".
- Exemptions are auditable in `git log` because the marker lives next
  to the DDL and follows the migration's `.down.sql` pairing rule
  (STORY-6.2).
- The Management API path is resilient under Disk-IO degraded mode
  (memory `reference_supabase_management_api_query`), so the gate
  remains usable during incident response.

## Alternatives Considered

1. **`supabase db pull` + grep.** Rejected: the dump output groups
   policies by command/role and is brittle to format drift between CLI
   versions. The Management API returns structured JSON that maps
   directly to `pg_policies`.
2. **Backend-side audit endpoint.** Rejected: would require live
   backend availability, which contradicts the requirement to keep the
   audit usable during outages, and adds a new admin surface that itself
   needs RLS reasoning.
3. **Static grep over `supabase/migrations/`.** Rejected: false
   negatives whenever a policy is added in a follow-up migration and
   false positives whenever a table is dropped. The live database is
   the only honest source.
4. **Soft warning instead of hard fail.** Rejected: the
   `audit-prod-env.yml` advisory pattern fits emergency env-var changes,
   but RLS gaps cannot be "emergency-shipped" — they always need a
   policy or an exemption marker, both of which are cheap to add.
