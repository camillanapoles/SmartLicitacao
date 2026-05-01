# DATA-CNAE-001: Migrate `utils/cnae_mapping.py` Hardcoded → DB Table

**Priority:** P2
**Effort:** M (2-3 dias)
**Squad:** @data-engineer + @dev
**Status:** Ready
**Epic:** [EPIC-TD-2026Q2](EPIC-TD-2026Q2/)
**Sprint:** Sprint 2-3
**Dependências bloqueadoras:** Nenhuma

---

## Contexto

`backend/utils/cnae_mapping.py` é hardcoded (Reversa review-report.md Gap-8). Cobertura desconhecida; updates exigem deploy. Driver onboarding wizard (US-006 Reversa user-stories.md) — Step 1 user fornece CNAE → mapeia para setor → first-analysis dispatch.

Pre-revenue: novo CNAE entrant não pode esperar deploy cycle. DB-driven permite admin update runtime.

---

## Acceptance Criteria

### AC1: `cnae_setor_mapping` table

- [ ] Migration `supabase/migrations/YYYYMMDDHHMMSS_cnae_setor_mapping.sql`:
  ```sql
  CREATE TABLE cnae_setor_mapping (
    cnae_code TEXT PRIMARY KEY,
    setor_id TEXT NOT NULL REFERENCES (sectors_data.yaml id — virtual FK),
    confidence NUMERIC(3,2) NOT NULL DEFAULT 1.00,
    fallback_setor_id TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by UUID REFERENCES auth.users(id)
  );
  CREATE INDEX idx_cnae_setor_mapping_setor ON cnae_setor_mapping(setor_id);
  ```
- [ ] Paired `.down.sql`
- [ ] RLS: read public (onboarding pré-auth pode consultar) · write `is_admin`

### AC2: Seed migration — import current `cnae_mapping.py`

- [ ] Script Python parse `utils/cnae_mapping.py` dict → INSERT batch
- [ ] Validate post-seed: count rows == count entries no dict original
- [ ] Audit log: registrar `created_by=NULL` + notes "seed initial 2026-04-28"

### AC3: Refactor `utils/cnae_mapping.py`

- [ ] `lookup_cnae_setor(cnae_code: str) -> Optional[str]`:
  - SELECT FROM cnae_setor_mapping
  - LRU cache `functools.lru_cache(maxsize=1000)` TTL 1h (similar quota_core padrão)
- [ ] Backward compat: import path preservado

### AC4: Admin endpoint CRUD

- [ ] `POST /v1/admin/cnae-mapping` — create entry
- [ ] `PATCH /v1/admin/cnae-mapping/{cnae_code}` — update
- [ ] `DELETE /v1/admin/cnae-mapping/{cnae_code}` — soft delete via `notes='deleted'` (preserve audit)
- [ ] `GET /v1/admin/cnae-mapping?setor=...` — list filtered
- [ ] Permission: `is_admin OR is_master`

### AC5: Tests regression

- [ ] Snapshot test: para cada CNAE no dict original, `lookup_cnae_setor(cnae)` retorna mesmo setor
- [ ] Edge: CNAE inexistente retorna None (não erra)
- [ ] Cache invalidation após PATCH via admin

### AC6: Documentação

- [ ] `docs/data/cnae-coverage.md`: quais CNAEs caem em "diversos" / fallback (review-report.md Gap-8)
- [ ] CHANGELOG entry

---

## Scope

**IN:** table + seed + refactor lookup + admin CRUD + tests + coverage doc
**OUT:** A/B test mapping precision · CNAE 2.x → 3.x version migration (future)

---

## Definition of Done

- [ ] Migration aplicada + paired down.sql
- [ ] Snapshot 100% match pré/pós migração
- [ ] Admin endpoint funcional
- [ ] Cache invalidate verificado
- [ ] Coverage doc criado
- [ ] Suite passa

---

## Dev Notes

- `backend/utils/cnae_mapping.py` — file referência atual
- Padrão LRU cache: `quota/quota_core.py:_plan_status_cache` (bounded 1000, TTL 5min — adjust 1h aqui)
- Pattern admin endpoint: existing `routes/admin_*.py`

---

## Risk & Rollback

| Trigger | Ação |
|---|---|
| Snapshot test falha após seed | Bug em seed script; revert migration + investigate |
| Performance lookup degrada (>10ms p95) | Verify index `idx_cnae_setor_mapping` + cache hit ratio |
| RLS read public expõe data sensível | Revisão: cnae_code não é PII; setor_id pública via /setores; OK |

**Rollback:** revert migration; lookup volta ao hardcoded.

---

## Dependencies

**Entrada:** Nenhuma
**Saída:** habilita REF-VAL-004 (onboarding refactor) — depende desta DB lookup

---

## PO Validation

**Validated by:** @po (Pax)
**Date:** 2026-04-28
**Verdict:** GO
**Score:** 10/10

### 10-Point Checklist

| # | Criterion | ✓/✗ | Notes |
|---|-----------|-----|-------|
| 1 | Clear and objective title | ✓ | Migration intent explícito (hardcoded → DB). |
| 2 | Complete description | ✓ | Driver onboarding (US-006) + admin runtime update use case. |
| 3 | Testable acceptance criteria | ✓ | 6 ACs com snapshot test 100% match pré/pós. |
| 4 | Well-defined scope | ✓ | OUT exclude CNAE 2.x→3.x version migration. |
| 5 | Dependencies mapped | ✓ | Saída habilita REF-VAL-004. |
| 6 | Complexity estimate | ✓ | M (2-3d) coerente. |
| 7 | Business value | ✓ | Dispatch deploy cycle eliminado. |
| 8 | Risks documented | ✓ | Snapshot test cobre regressão. |
| 9 | Criteria of Done | ✓ | 6 itens. |
| 10 | Alignment with PRD/Epic | ✓ | EPIC-TD-2026Q2 hardcoded→DB pattern. |

### Minor follow-up (non-blocker)

- @sm pode rename para `STORY-7.X-cnae-mapping-db.md` per TD-2026Q2 numbering convention. Não blocker para @dev pickup.

Status: Draft → Ready.

---

## Change Log

| Data | Versão | Descrição | Autor |
|---|---|---|---|
| 2026-04-28 | 1.0 | Story criada — recria fictícia state.json sm_handoff. Minor followup: rename para STORY-7.X-cnae-mapping-db.md per TD-2026Q2 convention se @po preferir. Origem: `_reversa_sdd/sm-briefing-refactor.md` + sm-briefing.md sec.2.2. | @sm (River) |
| 2026-04-28 | 1.1 | PO validation: GO (10/10). Status: Draft → Ready. Minor followup naming rename é non-blocker. | @po (Pax) |
