# Story DEBT-100: DB Quick Wins — Integrity, Retention & Indexes

## Metadata
- **Story ID:** DEBT-100
- **Epic:** EPIC-DEBT
- **Batch:** A (Quick Wins)
- **Sprint:** 1 (Semanas 1-2)
- **Estimativa:** 7h
- **Prioridade:** P0-P2 (mix of verification + integrity fixes)
- **Agent:** @data-engineer

## Descricao

Como engenheiro de plataforma, quero resolver 12 items de banco de dados de baixo esforco (<2h cada), para que a integridade referencial, retention automatica e performance de escrita estejam garantidas antes de atacar os debitos estruturais maiores.

## Debt Items Cobertos

| ID | Debito | Severidade | Horas |
|----|--------|:---:|:---:|
| DB-NEW-01 | `search_results_store` FK NOT VALID — verificar se esta validada em producao | HIGH | 0.5h |
| DB-NEW-04 | `search_results_cache` FK estado incerto — multiplas migracoes tocaram esta FK | MEDIUM | 0.5h |
| DB-NEW-03 | `search_results_store` sem retention — `expires_at` existe mas nenhum pg_cron limpa | HIGH | 0.5h |
| DB-021 | `organizations.plan_type` sem CHECK constraint — aceita qualquer texto | MEDIUM | 0.5h |
| DB-018 | `partner_referrals.partner_id` missing ON DELETE CASCADE | MEDIUM | 0.5h |
| DB-015 | `monthly_quota.user_id` references `auth.users` not `profiles` | MEDIUM | 1h |
| DB-NEW-02 | `search_results_store` index duplicado: `idx_search_results_user` e `idx_search_results_store_user_id` | MEDIUM | 0.5h |
| DB-026 | `search_sessions` accumulating without retention (12 meses recomendado) | LOW | 0.5h |
| DB-016 | Missing `updated_at` on `incidents` e `partners` + trigger | MEDIUM | 1h |
| DB-011 | Redundant indexes em 3 tabelas (search_results_store, search_sessions, partners) | MEDIUM | 1h |
| FE-A11Y-02 | SearchErrorBoundary crash UI nao anunciado a assistive technology — add `role="alert"` | MEDIUM | 0.5h |
| FE-019 | `@types/uuid` in dependencies (should be devDependencies) | LOW | 0.5h |

## Acceptance Criteria

- [x] AC1: Query de verificacao FK executada em producao para DB-NEW-01 — resultado documentado (validada ou action item)
- [x] AC2: Query de verificacao FK executada em producao para DB-NEW-04 — resultado documentado
- [x] AC3: pg_cron job criado: `DELETE FROM search_results_store WHERE expires_at < now()` (daily schedule)
- [x] AC4: pg_cron job criado para search_sessions (registros > 12 meses)
- [x] AC5: `organizations.plan_type` tem CHECK constraint (`free_trial`, `pro`, `consultoria`, ou valores validos)
- [x] AC6: `partner_referrals.partner_id` tem ON DELETE CASCADE
- [x] AC7: `monthly_quota.user_id` aponta para `profiles(id)` com ON DELETE CASCADE
- [x] AC8: Index duplicado `idx_search_results_store_user_id` removido
- [x] AC9: `incidents` e `partners` tem coluna `updated_at` com trigger automatico
- [x] AC10: Indexes redundantes em search_sessions e partners removidos (apos verificar idx_scan=0)
- [x] AC11: SearchErrorBoundary fallback tem `role="alert"` e `aria-live="assertive"`
- [x] AC12: `@types/uuid` movido para devDependencies no `package.json`
- [x] AC13: Todos items implementados em uma unica migration SQL (exceto FE items)

## Testes Requeridos

- Executar 5 SQL diagnostics do QA Gate Condicao 1 ANTES de iniciar
- Verificar `SELECT jobname, schedule FROM cron.job` apos criacao dos pg_cron jobs
- Verificar FK state com query: `SELECT tc.table_name, ccu.table_name AS references_table FROM information_schema.table_constraints...`
- `npm run build` para confirmar que mover @types/uuid nao quebra build
- `npm test` para confirmar SearchErrorBoundary test passa com role="alert"

## Notas Tecnicas

- Todos os DB items podem ser consolidados em uma unica migration: `supabase/migrations/YYYYMMDDHHMMSS_debt100_db_quick_wins.sql`
- Para DB-NEW-01/DB-NEW-04: executar apenas queries de verificacao, NAO alterar se ja validado
- Para DB-011: verificar `pg_stat_user_indexes.idx_scan` antes de dropar — so remover indexes com 0 scans
- Para DB-015: usar pattern NOT VALID + VALIDATE em separado para evitar lock longo
- FE-A11Y-02: arquivo `frontend/app/buscar/components/SearchErrorBoundary.tsx` (ou similar)
- FE-019: arquivo `frontend/package.json`

## Dependencias

- **Depende de:** Nenhuma (pode iniciar imediatamente)
- **Bloqueia:** DEBT-104 (DB-NEW-01/DB-NEW-04 results inform scope of DB-001 FK standardization)

## Definition of Done

- [x] Codigo implementado (migration SQL + 2 FE fixes)
- [ ] Migration aplicada em producao via `supabase db push`
- [ ] pg_cron jobs ativos verificados
- [x] Testes passando (backend + frontend)
- [x] Resultados das queries de verificacao documentados
