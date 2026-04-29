# STORY-DEBT-1: Quick Wins -- DB Integrity + Backend Fixes

**Epic:** EPIC-DEBT-2026
**Batch:** 1
**Prioridade:** P0
**Estimativa:** 5h
**Agente:** @dev (implementacao) + @data-engineer (migration review) + @qa (validacao)

## Descricao

Resolver 8 debitos de alto ROI / baixo esforco que eliminam o unico item CRITICAL do sistema (memory leak em quota.py), corrigem gaps de integridade no banco de dados, e limpam configuracoes incorretamente posicionadas. Cada item leva <1h e tem risco de regressao minimo.

**Debt IDs:** DEBT-323, DB-H04+DA-02, DB-M04+M05, DA-01+DB-L05, DEBT-322, DEBT-325, TD-NEW-01, DB extras (DB-L01, DB-L03+DA-03, DB-M02, DB-M03, DB-M07, DA-04)

## Acceptance Criteria

### CRITICAL Fix
- [ ] AC1 (DEBT-323): `_plan_status_cache` em `quota.py:44` convertido para `cachetools.TTLCache` ou `functools.lru_cache` com maxsize. Unit test insere 1001 entries e verifica eviction. Test de concurrency com `threading.Thread`.

### Database Integrity
- [ ] AC2 (DB-H04+DA-02): Migration adiciona NOT NULL em `classification_feedback.created_at`, `user_oauth_tokens.created_at`, `user_oauth_tokens.updated_at`. Backfill de NULLs existentes com `COALESCE(col, now())` antes do constraint. `SELECT COUNT(*) WHERE created_at IS NULL` retorna 0 apos migration.
- [ ] AC3 (DB-M04+M05): CHECK constraints adicionados em `search_sessions.response_state` (valores: live, cached, degraded, empty_failure) e `search_sessions.pipeline_stage`. INSERT com valor invalido falha com CHECK violation error.
- [ ] AC4 (DA-01+DB-L05): Cache cleanup function restaura priority-aware eviction (hot > warm > cold ordering). Limit aumentado de 5 para 10. Inserir 11 entries com mixed priorities: cold evicted primeiro, hot sobrevive.

### Backend Config Fixes
- [ ] AC5 (DEBT-322): Circuit breaker configs de PCP e ComprasGov movidos de `pncp_client.py:56-71` para seus respectivos clients (`portal_compras_client.py`, `compras_gov_client.py`). Behavior de CB inalterado (regression test).
- [ ] AC6 (DEBT-325): `USD_TO_BRL` em `llm_arbiter.py:73` lido de env var `USD_TO_BRL_RATE` com fallback para `5.0`. Config test verifica override e fallback.

### Frontend Quick Fix
- [ ] AC7 (TD-NEW-01): Apenas 1 elemento com `id="main-content"` existe no DOM em qualquer pagina. Os 3 arquivos com duplicatas corrigidos para usar IDs unicos ou remover duplicatas.

### Database Documentation
- [ ] AC8: Migration file `.bak` removido (DB-L01). COMMENTs adicionados em tabelas sem documentacao (DB-L03+DA-03). FK docs atualizados para `organization_members.user_id` (DB-L03). COMMENT adicionado em `subscription_status` enum mapping trigger (DB-M07). `partners.updated_at` column adicionado (DA-04). FK de `partner_referrals` verificada em producao + COMMENT adicionado (DB-M03).

## Tasks

- [ ] T1: Converter `_plan_status_cache` para `TTLCache(maxsize=1000, ttl=300)` em `quota.py`. Adicionar testes de eviction e concurrency. (1h)
- [ ] T2: Criar migration `supabase/migrations/YYYYMMDD100000_debt_db_integrity.sql` -- backfill NULLs, ADD NOT NULL, ADD CHECK constraints, restore priority eviction, add COMMENTs, add partners.updated_at, cleanup .bak. Migration deve ser idempotent e zero-downtime. (1.5h)
- [ ] T3: Mover CB configs de `pncp_client.py:56-71` para `portal_compras_client.py` e `compras_gov_client.py`. Verificar imports nao quebram. (1h)
- [ ] T4: Extrair `USD_TO_BRL` para env var em `llm_arbiter.py`. Atualizar `.env.example` e `config.py`. (0.5h)
- [ ] T5: Fix duplicate `id="main-content"` nos 3 arquivos frontend identificados. (0.5h)
- [ ] T6: Run full test suites (backend + frontend) para confirmar zero regressions. (0.5h)

## Testes Requeridos

- **DEBT-323:** `pytest -k test_plan_cache` -- eviction at maxsize, TTL expiry, concurrent access
- **DB migration:** `COUNT(*) WHERE created_at IS NULL = 0`, negative INSERT with invalid response_state
- **DA-01:** Insert 11 cache entries with mixed priorities, verify cold evicted first
- **DEBT-322:** `pytest -k "circuit_breaker or cb"` -- behavior unchanged
- **DEBT-325:** `pytest -k test_config` -- env var override + fallback
- **TD-NEW-01:** `page.$$eval('[id]', els => els.map(e => e.id))` -- no duplicates
- **Full suite:** `python scripts/run_tests_safe.py --parallel 4` (7656 pass), `npm test` (5733 pass)

## Definition of Done

- [ ] All ACs checked
- [ ] Migration tested locally (`supabase db push` on linked project)
- [ ] Tests pass (backend + frontend)
- [ ] No regressions
- [ ] Code reviewed
- [ ] `.env.example` updated with `USD_TO_BRL_RATE`

## File List

- `backend/quota.py` (DEBT-323: TTLCache conversion)
- `backend/pncp_client.py` (DEBT-322: remove CB configs)
- `backend/portal_compras_client.py` (DEBT-322: receive CB configs)
- `backend/compras_gov_client.py` (DEBT-322: receive CB configs)
- `backend/llm_arbiter.py` (DEBT-325: env var for USD_TO_BRL)
- `backend/config.py` (DEBT-325: new config var)
- `backend/.env.example` (DEBT-325: document new var)
- `supabase/migrations/YYYYMMDD100000_debt_db_integrity.sql` (DB items)
- `frontend/app/(protected)/layout.tsx` (TD-NEW-01: candidate for duplicate ID fix)
- `frontend/app/buscar/layout.tsx` (TD-NEW-01: candidate)
- `frontend/app/layout.tsx` (TD-NEW-01: candidate)

## Notas

- **DEBT-323 e o unico item CRITICAL** do assessment inteiro. Fix e trivial (1h) mas impacto em producao e real -- memory cresce sem limite proporcional ao numero de usuarios unicos.
- **Migration deve ser idempotent:** usar `DO $$ ... IF NOT EXISTS ... $$` para CHECK constraints e NOT NULL. Permite re-run seguro.
- **cachetools ja e dependencia?** Verificar `requirements.txt`. Se nao, `functools.lru_cache` e alternativa zero-dependency (mas sem TTL).
- **3 arquivos com duplicate id="main-content":** Identificar com `grep -r 'id="main-content"'` no frontend antes de fixar.
