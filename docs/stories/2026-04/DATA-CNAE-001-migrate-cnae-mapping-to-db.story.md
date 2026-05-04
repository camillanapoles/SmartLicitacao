# DATA-CNAE-001: Migrate hardcoded `cnae_mapping.py` → DB table `cnae_setor_mapping` + admin full CRUD

**Status:** InReview
**Origem:** Reversa Audit 2026-04-27 (`_reversa_sdd/review-report.md` Gap-8) + decisão CTO 2026-04-27 (full CRUD admin)
**Prioridade:** P2 — data governance / operational agility
**Complexidade:** M (2-3 dias)
**Owner:** @data-engineer + @dev
**Tipo:** Data / Refactor
**Epic:** EPIC-TD-2026Q2 (technical debt)

---

## Contexto

`backend/utils/cnae_mapping.py` contém mapping CNAE → setor hardcoded em código. Implicações:

1. Updates exigem deploy backend
2. Cobertura desconhecida (quais CNAEs caem em "diversos"?)
3. Sem audit trail (quem alterou quando?)
4. Onboarding usa esse mapping em first-analysis (US-006); errors silenciosos enviam usuário para setor errado → first impression ruim

Reversa Audit Gap-8: *"existe spreadsheet de cobertura CNAE? Atualização frequência?"*.

**Decisão CTO 2026-04-27:** Full CRUD admin (não só read+update) — operações de governance precisam delete entries obsoletos quando IBGE retira CNAEs.

---

## Decisão

1. Migration: tabela `cnae_setor_mapping` (versionável + audit)
2. Seed: importar conteúdo atual `cnae_mapping.py`
3. Refactor `cnae_mapping.py` → query DB com cache LRU 1h
4. Admin endpoints CRUD com audit log
5. Tests regression: snapshot mapping atual = 100% match pós-migração

---

## Critérios de Aceite

### Backend — Schema + Seed

- [x] **AC1:** Migration `supabase/migrations/20260427215000_create_cnae_setor_mapping.sql`:
  ```sql
  CREATE TABLE cnae_setor_mapping (
    cnae_code TEXT PRIMARY KEY,         -- "8531-7/00" formato IBGE
    setor_id TEXT NOT NULL REFERENCES sectors(id),  -- ou enum, checar sectors_data.yaml
    confidence NUMERIC(3,2) DEFAULT 1.0 CHECK (confidence BETWEEN 0 AND 1),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    updated_by UUID REFERENCES auth.users(id),
    is_active BOOLEAN DEFAULT true
  );
  CREATE INDEX idx_cnae_active ON cnae_setor_mapping(is_active) WHERE is_active = true;
  ```
- [x] **AC2:** Migration paired `.down.sql` (`DROP TABLE cnae_setor_mapping;`)
- [x] **AC3:** Migration `supabase/migrations/20260427215100_cnae_audit_log.sql`:
  ```sql
  CREATE TABLE cnae_mapping_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cnae_code TEXT,
    action TEXT CHECK (action IN ('create','update','delete','restore')),
    old_value JSONB,
    new_value JSONB,
    actor_user_id UUID,
    created_at TIMESTAMPTZ DEFAULT now()
  );
  ```
- [x] **AC4:** Seed migration `supabase/migrations/20260427215200_seed_cnae_mapping.sql` importa 100% de `backend/utils/cnae_mapping.py` atual (script gerador idempotente em `scripts/generate_cnae_seed.py`)

### Backend — Refactor + Cache

- [x] **AC5:** `backend/utils/cnae_mapping.py` refatorado:
  - Function `get_setor_for_cnae(cnae_code: str) -> str | None` query DB
  - LRU cache `@lru_cache(maxsize=2048)` com TTL 1h via `cachetools.TTLCache` (não vanilla lru_cache)
  - Cache invalidation via Redis pubsub channel `cnae_mapping:invalidate` (admin updates publica)
  - Fallback: se DB indisponível, usa snapshot in-memory (loaded em startup)
- [x] **AC6:** `backend/routes/onboarding.py` continua funcionando idêntico (apenas trocou source); zero regression em first-analysis flow

### Backend — Admin CRUD

- [x] **AC7:** Endpoints admin (`backend/routes/admin_cnae.py`):
  - `GET /v1/admin/cnae-mapping` — list paginado + search
  - `GET /v1/admin/cnae-mapping/{cnae_code}` — detail + audit log
  - `POST /v1/admin/cnae-mapping` — create (body: cnae_code, setor_id, confidence, notes)
  - `PATCH /v1/admin/cnae-mapping/{cnae_code}` — update (campos modificáveis: setor_id, confidence, notes, is_active)
  - `DELETE /v1/admin/cnae-mapping/{cnae_code}` — soft-delete (is_active=false; preservado para audit)
  - `POST /v1/admin/cnae-mapping/{cnae_code}/restore` — undo soft-delete
  - `POST /v1/admin/cnae-mapping/bulk-import` — CSV upload (validation + preview before commit)
- [x] **AC8:** Cada mutation registra row em `cnae_mapping_audit_log` com `actor_user_id`
- [x] **AC9:** Cada mutation publica em Redis `cnae_mapping:invalidate` para invalidar cache de todos workers

### Frontend — Admin UI

- [x] **AC10:** `frontend/app/admin/cnae/page.tsx`:
  - Tabela paginada com search por código/setor
  - Filtros: setor, is_active, confidence range
  - Botões inline: edit, delete, view-audit
  - Botão "Bulk import CSV" → modal upload
  - Botão "Export CSV" (current state)
- [x] **AC11:** Modal edit/create com validação (cnae_code formato `XXXX-X/XX`, setor_id from dropdown)
- [x] **AC12:** Audit log view: timeline visual com diffs

### Coverage Report

- [x] **AC13:** Script `scripts/cnae_coverage_report.py`:
  - Cross-reference IBGE official CNAE list vs `cnae_setor_mapping` ativo
  - Output: `docs/reports/cnae-coverage-{YYYY-MM-DD}.md`
  - Métricas: % cobertura, CNAEs sem mapping (caem em fallback "diversos"), CNAEs IBGE removidos ainda no DB
- [x] **AC14:** Cron mensal (dia 1, 06 UTC) regenera report automatically

### Tests — Regression

- [x] **AC15:** Tests `backend/tests/test_cnae_mapping_db.py`:
  - Snapshot test: `cnae_mapping.py` antigo + novo retornam idêntico para 100% dos CNAEs (via fixture pre/post)
  - Cache invalidation funciona (Redis pubsub)
  - Soft-delete preserva audit
  - Bulk-import valida CSV antes de commit
- [x] **AC16:** Test `backend/tests/test_onboarding_cnae_integration.py`: first-analysis end-to-end com novo source = idêntico comportamento
- [x] **AC17:** Frontend `frontend/__tests__/admin/cnae.test.tsx`: CRUD operations + audit log render

---

## Arquivos Impactados

**Novos:**
- `supabase/migrations/20260427215000_create_cnae_setor_mapping.sql` + `.down.sql`
- `supabase/migrations/20260427215100_cnae_audit_log.sql` + `.down.sql`
- `supabase/migrations/20260427215200_seed_cnae_mapping.sql` + `.down.sql`
- `scripts/generate_cnae_seed.py`
- `scripts/cnae_coverage_report.py`
- `backend/routes/admin_cnae.py`
- `backend/tests/test_cnae_mapping_db.py`
- `backend/tests/test_onboarding_cnae_integration.py`
- `frontend/app/admin/cnae/page.tsx`
- `frontend/__tests__/admin/cnae.test.tsx`
- `docs/reports/cnae-coverage-baseline.md` (initial run)

**Modificados:**
- `backend/utils/cnae_mapping.py` — refator query DB + cache + Redis invalidation
- `backend/routes/onboarding.py` — zero changes esperadas (transparente)
- `backend/jobs/cron/scheduler.py` — adicionar coverage report cron

**Removidos (após validation):**
- conteúdo hardcoded em `backend/utils/cnae_mapping.py` (mantém só function signature + cache layer)

---

## Riscos

- **R1 (Alto):** Regression silenciosa em onboarding first-analysis (CNAE→setor errado afeta UX 100% dos novos signups). **Mitigação:** AC15 snapshot test obrigatório + canary deploy 5% trafic primeiro
- **R2 (Médio):** Cache invalidation race condition (worker A serve stale enquanto B atualizou). **Mitigação:** AC5 Redis pubsub + TTL 1h cap (worst case 1h stale)
- **R3 (Médio):** Bulk-import CSV pode introduzir erros em massa. **Mitigação:** AC7 preview obrigatório + dry-run mode + audit log per-row
- **R4 (Baixo):** DB query em hot path (every signup) adiciona latência. **Mitigação:** LRU cache + fallback in-memory snapshot

---

## Dependências

- Tabela `sectors` (existente) ou enum `setor_id` confirmado pelo @data-engineer
- @analyst review CSV import schema antes do AC11

---

## Change Log

| Data | Agente | Ação |
|------|--------|------|
| 2026-04-27 | @sm | Story criada via Reversa Audit Gap-8 + CTO decision (full CRUD admin). Snapshot regression mandatória. Status=Draft → @po validation |
| 2026-04-27 | @po | Validation 9/10 → **GO**. Naming convention TD-2026Q2 epic usa `STORY-X.X-name.md` (próximo: STORY-7.1); este file pode ser renomeado quando @sm consolidar. AC15 snapshot test bem-pensado contra R1 (HIGH). Status Draft → Ready. |
| 2026-04-28 | @dev | Implementation complete. Migrations, refactor com TTL cache + Redis pubsub + legacy fallback, admin CRUD, frontend page, coverage script + cron, snapshot regression test. Pre-allocated timestamps used (`20260428100800/100900/101000` overrides story-suggested `20260427215000/215100/215200`). All 68 backend + 10 frontend tests passing. Branch: `feat/data-cnae-001`. Status Ready → InReview. |

## File List

### Created

- `supabase/migrations/20260428100800_create_cnae_setor_mapping.sql` + `.down.sql`
- `supabase/migrations/20260428100900_cnae_audit_log.sql` + `.down.sql`
- `supabase/migrations/20260428101000_seed_cnae_mapping.sql` + `.down.sql`
- `scripts/generate_cnae_seed.py` (with `--check` for CI drift detection)
- `scripts/cnae_coverage_report.py`
- `backend/routes/admin_cnae.py` (full CRUD + bulk-import)
- `backend/jobs/cron/cnae_coverage.py` (monthly coverage cron)
- `backend/tests/test_cnae_mapping_db.py` (12 tests — snapshot regression, TTL cache, fallback, kill switch)
- `backend/tests/test_admin_cnae.py` (17 tests — CRUD + bulk-import + auth gate)
- `backend/tests/test_onboarding_cnae_integration.py` (13 tests — high-traffic CNAE coverage)
- `frontend/app/admin/cnae/page.tsx` (admin UI)
- `frontend/__tests__/admin/cnae.test.tsx` (10 tests)
- `docs/reports/cnae-coverage-baseline.md` (initial coverage report)

### Modified

- `backend/utils/cnae_mapping.py` — refactored to DB-first lookup with `_TTLCache` (1h, 2048 entries), Redis pubsub listener, legacy snapshot fallback. `_LEGACY_CNAE_TO_SETOR` retained as the source of truth for the seed migration AND the AC15 regression baseline. Added `invalidate_cnae_cache()` and `CNAE_INVALIDATION_CHANNEL` constants. `CNAE_TO_SETOR` exposed as a backward-compat read-only proxy.
- `backend/startup/routes.py` — registered new `admin_cnae_router` as self-prefixed.
- `backend/jobs/cron/scheduler.py` — wired up `start_cnae_coverage_task`.
- `backend/tests/test_cnae_mapping.py` — added autouse fixture forcing `CNAE_DB_LOOKUP_ENABLED=false` so the legacy unit tests stay pinned to the in-memory snapshot (avoids hitting prod Supabase from a unit test).

### Notes for QA

- Migration timestamps are `20260428100800/100900/101000` (per task instructions — pre-allocated to avoid collisions). Story body still references the original `20260427215000` timestamps because they remain in `Critérios de Aceite` for traceability; the actual files use the agreed timestamps.
- AC9 implementation: admin mutations call `invalidate_cnae_cache()` synchronously (writer worker) AND publish on Redis (other workers). The subscriber thread is lazily started on first lookup (gated by `CNAE_LISTENER_DISABLED` for tests).
- The `sectors` table mentioned in AC1 does NOT exist in production — there is only `backend/sectors_data.yaml`. The migration uses a CHECK constraint listing the 20 yaml-canonical ids plus 4 legacy aliases (`saude`, `equipamentos`, `transporte`, `geral`) used by the production hardcoded mapping. This preserves AC15 byte-equivalence; a future story can migrate sectors into a real table.
- The IBGE master CNAE list is not on disk. The coverage report runs against the legacy snapshot baseline by default; when `data/ibge_cnae_master.csv` is present it cross-references and reports uncovered/retired codes.
