# Story: DB Foundation — Pre-Squash Fixes + Migration Squash

**Story ID:** DEBT-v3-003
**Epic:** DEBT-v3
**Phase:** 2 (Foundation)
**Priority:** P1
**Estimated Hours:** 29h
**Agent:** @data-engineer
**Status:** PLANNED

---

## Objetivo

Preparar o banco de dados para o migration squash executando todos os pre-requisitos (VACUUM schedule, trigger renaming, composite indexes, FK fixes), e entao executar o squash de 106 migrations para ~5-10 baseline files. O squash tambem resolve organicamente DB-005 (Stripe IDs hardcoded) e DB-020 (timestamp naming).

---

## Debitos Cobertos

### Pre-Squash Fixes (~5h)

| ID | Debt | Severity | Hours |
|----|------|----------|-------|
| DB-010 | Sem VACUUM ANALYZE para tabelas de alto churn — auto-vacuum pode nao trigger apos purge diario | MEDIUM | 2h |
| DB-011 | 4 triggers com prefixo antigo (`tr_`, `trigger_`) — renomear para `trg_` | LOW | 1h |
| DB-019 | Indexes compostos faltantes: `search_state_transitions(search_id, to_state)`, `classification_feedback(setor_id, created_at DESC)` | LOW | 2h |

### Migration Squash (~24h)

| ID | Debt | Severity | Hours |
|----|------|----------|-------|
| DB-002 | 106 migration files — schema archaeology risk, DR de replay nao testado | HIGH | 24h |
| DB-005 | Stripe price IDs hardcoded em migrations (resolvido no squash via env-aware seed) | MEDIUM | (included) |
| DB-020 | Timestamp naming inconsistente: `last_updated_at`, `checked_at` outliers (resolvido na baseline) | LOW | (included) |
| CROSS-004 | Migration volume + schema archaeology — 106 migrations impactam deploy time e DR (resolvido pelo squash) | HIGH | 0h (coord) |

---

## Acceptance Criteria

### Pre-Squash
- [ ] AC1: pg_cron job para VACUUM ANALYZE em `pncp_raw_bids` agendado as 07:30 UTC (30 min apos purge)
- [ ] AC2: pg_cron job semanal para `check_pncp_raw_bids_bloat()` (domingo 04:00 UTC)
- [ ] AC3: 4 triggers renomeados para prefixo `trg_` em migracao dedicada
- [ ] AC4: Index composto `idx_search_state_transitions_search_id_to_state` criado
- [ ] AC5: Index composto `idx_classification_feedback_setor_created` criado
- [ ] AC6: Todos pre-squash fixes deployados e verificados antes de iniciar squash

### Migration Squash
- [ ] AC7: 106 migrations consolidadas em ~5-10 baseline files seguindo `MIGRATION-SQUASH-PLAN.md`
- [ ] AC8: `pg_dump --schema-only` da baseline squashed == `pg_dump --schema-only` de producao (diff vazio)
- [ ] AC9: Clean DB creation a partir da baseline squashed funciona sem erros
- [ ] AC10: Stripe price IDs substituidos por env-aware seed (nao hardcoded na baseline)
- [ ] AC11: Timestamps normalizados: todos usam `updated_at` e `created_at` (sem `last_updated_at`, `checked_at`)
- [ ] AC12: CI migration-gate.yml atualizado para reconhecer nova estrutura
- [ ] AC13: `supabase db push` funciona com nova baseline
- [ ] AC14: Backup pg_dump antes do squash armazenado e documentado

---

## Technical Notes

**Pre-squash order matters:**
1. DEBT-v3-001 (security fixes) MUST be deployed first — included in squashed baseline
2. DB-010 (VACUUM) — deploy and verify
3. DB-011 (triggers) — cosmetic rename, zero risk
4. DB-019 (indexes) — CREATE INDEX CONCURRENTLY to avoid locks
5. Only then start squash

**Squash approach (from MIGRATION-SQUASH-PLAN.md):**
1. `pg_dump --schema-only` of production as reference
2. Create new baseline migration(s) organized by domain
3. Keep recent migrations (last 2-3 sprints) as individual files
4. Test clean DB creation matches pg_dump reference
5. Update Supabase project to use new baseline

**Risk mitigation:**
- Keep original migrations in `supabase/migrations/_archived/` (not deleted)
- Test on staging with real data before production
- Schedule during low-traffic window
- Each week adds 1-3 new migrations — execute promptly to minimize drift (R-013)

---

## Tests Required

- [ ] Schema diff test: squashed baseline vs pg_dump = empty diff
- [ ] Clean DB creation test from squashed baseline
- [ ] `supabase db push` success on fresh project
- [ ] CI pipeline green with new structure
- [ ] Backend full suite passes (no migration-dependent failures)

---

## Dependencies

- **REQUIRES:** DEBT-v3-001 (DB security fixes must be in baseline)
- **BLOCKS:** Nothing directly (but clean migration baseline benefits all future work)

---

## Definition of Done

- [ ] All ACs pass
- [ ] Pre-squash fixes deployed and verified
- [ ] Squashed baseline creates identical schema to production
- [ ] CI green
- [ ] Original migrations archived (not deleted)
- [ ] Code reviewed by @data-engineer
