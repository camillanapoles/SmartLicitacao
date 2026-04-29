# BIZ-METRIC-001: Empirical Validation `estimated_hours_saved` (atualmente N×2.5h hardcoded)

**Priority:** P2
**Effort:** M (3-4 dias) + soak window n≥30
**Squad:** @analyst + @dev + @data-engineer
**Status:** Ready
**Epic:** [EPIC-MON-FN-2026-Q2](EPIC-MON-FN-2026-Q2.md)
**Sprint:** Sprint 2-3 (após n≥30 sessions)
**Dependências bloqueadoras:** Mixpanel backend lib instalada (PR #536, Done) · n≥30 active users (memory `feedback_n2_below_noise_eng_theater` — pre-revenue gate)

---

## Contexto

`backend/routes/analytics.py::summary` retorna `estimated_hours_saved = total_searches * 2.5` (review-report.md Gap-6). Constante hardcoded sem base empírica documentada. Aparece em dashboard pessoal (US-007 Reversa user-stories.md) — drive percepção valor critical.

Memory `feedback_n2_below_noise_eng_theater` (2026-04-26): n=2 abaixo noise floor; instrumentation prematura = eng theater. Esta story instrumenta + coleta + recalibra pós n≥30.

`utils/cnae_mapping.py` é hardcoded também (DATA-CNAE-001 separate); analytics constants seguem padrão antipattern.

---

## Acceptance Criteria

### AC1: Instrumentation Mixpanel time-on-task

- [ ] `frontend/app/buscar/page.tsx` emite Mixpanel events:
  - `search_started` (timestamp `t0`)
  - `search_results_viewed` (timestamp `t1`)
  - `search_export_clicked` (timestamp `t2`)
- [ ] `track-cta` endpoint backend (`routes/analytics.py`) recebe + persiste duration (`t2-t0`) por `user_id`
- [ ] Privacy: log_sanitizer.py aplicado; sem PII

### AC2: `app_config` table — runtime-toggle constant

- [ ] Migration `supabase/migrations/YYYYMMDDHHMMSS_app_config.sql`:
  ```sql
  CREATE TABLE app_config (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by UUID REFERENCES auth.users(id)
  );
  INSERT INTO app_config (key, value) VALUES ('hours_saved_per_search', '2.5');
  ```
- [ ] Paired `.down.sql`
- [ ] RLS: read public, write `is_admin`

### AC3: Refactor `analytics.py::summary`

- [ ] Substituir `total_searches * 2.5` por:
  ```python
  hours_per_search = await app_config_service.get('hours_saved_per_search', default=2.5)
  estimated_hours_saved = total_searches * hours_per_search
  ```
- [ ] LRU cache 1h (similar `quota_core.py:_plan_status_cache`)

### AC4: Admin endpoint config

- [ ] `PATCH /v1/admin/config/{key}` — atualiza `app_config.value` + invalidate cache
- [ ] `GET /v1/admin/config` — lista all configs
- [ ] Permission: `is_admin OR is_master`

### AC5: Empirical analysis (após n≥30)

- [ ] `docs/methodology/hours-saved-calibration.md` documenta:
  - Sample size n
  - Distribuição duration (median, p75, p95)
  - Compared to manual baseline (consultoria estimou X horas para mesma busca)
  - Recalibrated value (ex: 1.8h ou 3.5h)
- [ ] PATCH config via admin endpoint

### AC6: Tests

- [ ] `test_analytics_summary_hours_saved_dynamic.py`: config 2.5 → expect; PATCH para 1.8 + invalidate → expect 1.8
- [ ] Race-free PATCH: 2 simultaneous → consistent state
- [ ] Mixpanel event schema test (validate no PII)

---

## Scope

**IN:** Mixpanel instrumentation · app_config table · refactor analytics.py · admin endpoint · methodology doc · tests
**OUT:** Migrate other constants (`SUBSCRIPTION_GRACE_DAYS=3`, etc.) — separate stories · A/B test hours_saved display copy

---

## Definition of Done

- [ ] Mixpanel events firing in prod (verify dashboard)
- [ ] app_config table + migration applied
- [ ] Admin endpoint functional + RBAC
- [ ] Methodology doc com n≥30 samples
- [ ] Suite passa
- [ ] @po validation GO

---

## Dev Notes

- `backend/routes/analytics.py:547L` — endpoint `/summary`
- Mixpanel lib instalada: confirme `import mixpanel` em `requirements.txt` (PR #536)
- Memory `reference_mixpanel_backend_token_gap_2026_04_24` + `project_mixpanel_lib_silent_2026_04_27` — verify token + lib in prod

---

## Risk & Rollback

| Trigger | Ação |
|---|---|
| n não atinge 30 em 60d | Defer recalibration; manter 2.5 default |
| Mixpanel events com PII | log_sanitizer + revisão |
| Cache stale após PATCH | Invalidate via Redis pub/sub (futuro) ou TTL curto 1h |

**Rollback:** revert migration; analytics.py volta hardcoded 2.5.

---

## Dependencies

**Entrada:** Mixpanel lib (PR #536 Done) · token MIXPANEL_TOKEN setado prod
**Saída:** habilita futuro: outros constants migram para app_config (precedente)

---

## PO Validation

**Validated by:** @po (Pax)
**Date:** 2026-04-28
**Verdict:** GO
**Score:** 10/10

### 10-Point Checklist

| # | Criterion | ✓/✗ | Notes |
|---|-----------|-----|-------|
| 1 | Clear and objective title | ✓ | Empirical validation magic constant explícito (N×2.5h hardcoded). |
| 2 | Complete description | ✓ | Memory `feedback_n2_below_noise_eng_theater` referenciada; n≥30 gate documentado. |
| 3 | Testable acceptance criteria | ✓ | 6 ACs com Mixpanel events + app_config table + admin endpoint + methodology doc. |
| 4 | Well-defined scope | ✓ | OUT excludes A/B test display copy. |
| 5 | Dependencies mapped | ✓ | Mixpanel lib PR #536 Done + token verify. |
| 6 | Complexity estimate | ✓ | M (3-4d) + soak window n≥30. |
| 7 | Business value | ✓ | Drive percepção valor crítica (US-007 Reversa). |
| 8 | Risks documented | ✓ | n não atinge 30 in 60d → defer recalibration. |
| 9 | Criteria of Done | ✓ | 6 itens DoD com methodology doc. |
| 10 | Alignment with PRD/Epic | ✓ | EPIC-MON-FN funnel measurement. |

Status: Draft → Ready.

---

## Change Log

| Data | Versão | Descrição | Autor |
|---|---|---|---|
| 2026-04-28 | 1.0 | Story criada — recria fictícia state.json sm_handoff. Origem: `_reversa_sdd/sm-briefing-refactor.md` Eixo 1 + sm-briefing.md sec.2.1. | @sm (River) |
| 2026-04-28 | 1.1 | PO validation: GO (10/10). Status: Draft → Ready. | @po (Pax) |
