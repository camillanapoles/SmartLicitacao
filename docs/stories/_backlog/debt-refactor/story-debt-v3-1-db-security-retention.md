# Story: DB Security Hardening + Retention Policies

**Story ID:** DEBT-v3-001
**Epic:** DEBT-v3
**Phase:** 1 (Quick Wins)
**Priority:** P0
**Estimated Hours:** 11h
**Agent:** @data-engineer
**Status:** PLANNED

---

## Objetivo

Eliminar vulnerabilidades de seguranca em funcoes SECURITY DEFINER que nao possuem `SET search_path`, remover indexes redundantes, e implementar retencao automatica para 5 tabelas que crescem sem limite. Estas sao correcoes de risco zero que podem ser deployadas imediatamente em uma unica migracao.

---

## Debitos Cobertos

### Batch 1: Security + Cleanup (single migration, ~3h)

| ID | Debt | Severity | Hours |
|----|------|----------|-------|
| DB-001 | `handle_new_user()` SECURITY DEFINER sem `SET search_path` — 8a redefinicao | HIGH | 1h |
| DB-022 | `get_conversations_with_unread_count()` e `get_analytics_summary()` sem `SET search_path` | LOW | 1h |
| DB-014 | Index redundante `idx_alert_preferences_user_id` | LOW | 0.5h |
| DB-015 | GIN index nao utilizado em `google_sheets_exports.search_params` | LOW | 0.5h |

### Batch 2: Retention Policies (single pg_cron migration, ~8h)

| ID | Debt | Severity | Hours |
|----|------|----------|-------|
| DB-008 | Tabelas sem retencao: search_state_transitions, classification_feedback, mfa_recovery_attempts, alert_runs | HIGH | 6h |
| DB-023 | `search_sessions` sem retencao para estados terminais | MEDIUM | 2h |

---

## Acceptance Criteria

### Batch 1: Security
- [ ] AC1: `handle_new_user()` inclui `SET search_path = public` no corpo da funcao
- [ ] AC2: `get_conversations_with_unread_count()` inclui `SET search_path = public`
- [ ] AC3: `get_analytics_summary()` inclui `SET search_path = public`
- [ ] AC4: Query de auditoria `SELECT proname FROM pg_proc WHERE prosecdef AND proconfig IS NULL` retorna 0 rows para funcoes do schema public
- [ ] AC5: `idx_alert_preferences_user_id` removido (DROP INDEX)
- [ ] AC6: GIN index de `google_sheets_exports.search_params` removido
- [ ] AC7: Tudo em uma unica migracao transacional

### Batch 2: Retention
- [ ] AC8: pg_cron job para `search_state_transitions` com retencao de 90 dias
- [ ] AC9: pg_cron job para `classification_feedback` com retencao de 12 meses
- [ ] AC10: pg_cron job para `mfa_recovery_attempts` com retencao de 30 dias
- [ ] AC11: pg_cron job para `alert_runs` com retencao de 6 meses
- [ ] AC12: pg_cron job para `search_sessions` com retencao de 6 meses (apenas estados terminais: completed, failed, cancelled)
- [ ] AC13: Cada pg_cron job usa batch DELETE (LIMIT 1000) para evitar lock contention
- [ ] AC14: Cada job loga quantidade de rows deletadas via `RAISE LOG`
- [ ] AC15: Schedule: diario as 07:00 UTC (fora de horario de pico)

---

## Technical Notes

**Batch 1 — Security migration:**
```sql
-- Fix SECURITY DEFINER functions
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$ ... $$;

-- Same pattern for get_conversations_with_unread_count and get_analytics_summary

-- Drop redundant indexes
DROP INDEX IF EXISTS idx_alert_preferences_user_id;
DROP INDEX IF EXISTS idx_google_sheets_exports_search_params;
```

**Batch 2 — Retention via pg_cron:**
- Usar `SELECT cron.schedule(...)` para cada tabela
- Batch delete pattern: `DELETE FROM table WHERE created_at < NOW() - INTERVAL 'X' LIMIT 1000`
- Repetir ate `ROW_COUNT = 0` para evitar long locks
- Agendar 30 min apos ingestion purge (que roda as 07:00 UTC)

**Pre-squash:** Estes fixes DEVEM preceder o migration squash (DEBT-v3-003) pois serao incorporados na baseline.

---

## Tests Required

- [ ] Schema audit query confirma zero SECURITY DEFINER sem search_path
- [ ] Index existence queries confirmam remocao
- [ ] pg_cron job listing confirma 5 novos jobs ativos
- [ ] Smoke test: `handle_new_user()` funciona normalmente apos alteracao
- [ ] Smoke test: conversations e analytics endpoints funcionam normalmente

---

## Definition of Done

- [ ] All ACs pass
- [ ] Migration aplicada com sucesso em staging
- [ ] Backend tests pass (zero regressions)
- [ ] Schema audit query clean
- [ ] Migration file committed
- [ ] Code reviewed
