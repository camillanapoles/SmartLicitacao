# REF-MON-004: Split `routes/analytics.py` (547L → conversion vs usage)

**Priority:** P2
**Effort:** M (3-4 dias)
**Squad:** @dev + @analyst
**Status:** Ready
**Epic:** [EPIC-MON-FN-2026-Q2](EPIC-MON-FN-2026-Q2.md)
**Sprint:** Sprint 3
**Dependências bloqueadoras:** Mixpanel lib instalada (PR #536, Done) · BIZ-METRIC-001 (paralelo OK)

---

## Contexto

`backend/routes/analytics.py` 547L, 6 endpoints:
- `/summary`, `/searches-over-time`, `/top-dimensions`, `/trial-value`, `/new-opportunities`, `/track-cta`

Mistura analytics-pessoal-do-user (percepção valor) com tracking-conversão (monetização). Acoplamento dificulta evolução: `track-cta` precisa enviar Mixpanel server-side (memory `project_mixpanel_lib_silent_2026_04_27` confirma 7d silenciado por lib ausente até PR #536) mas é forçado a respeitar contrato user-facing.

Memory `reference_mixpanel_backend_token_gap_2026_04_24`: token agora live em prod.

---

## Acceptance Criteria

### AC1: Split arquivos

- [ ] `backend/routes/analytics_user.py` (novo, ~300L) — user dashboard endpoints:
  - `/summary`, `/searches-over-time`, `/top-dimensions`, `/new-opportunities`
- [ ] `backend/routes/analytics_conversion.py` (novo, ~250L) — CTA tracking, funnel:
  - `/trial-value`, `/track-cta`
- [ ] `routes/analytics.py` deletado OU façade re-export se backward compat needed

### AC2: Mixpanel server-side em conversion

- [ ] `analytics_conversion.py::track-cta` adiciona `mixpanel.track(user_id, event, properties)` server-side
- [ ] Validate token via assertion startup (ou MON-FN-005 pattern)
- [ ] Privacy: log_sanitizer + sem PII in event properties

### AC3: Hours saved dependency

- [ ] `analytics_user.py::summary` consume `app_config.hours_saved_per_search` (BIZ-METRIC-001 dependency — pode rodar paralelo)
- [ ] Se BIZ-METRIC-001 não Done: hardcoded 2.5 fallback com TODO comment

### AC4: Tests

- [ ] `test_analytics_user.py` + `test_analytics_conversion.py` substituem `test_analytics.py`
- [ ] Mixpanel mock fixture compartilhado
- [ ] Cobertura ≥85%

### AC5: Frontend hooks

- [ ] `frontend/hooks/useAnalytics.ts` consome both endpoints; aliases compatíveis
- [ ] Sem breaking change UI

---

## Scope

**IN:** split 2 routers + Mixpanel server-side + tests + frontend hooks
**OUT:** Add new analytics endpoints (separate) · Cohort retention dashboard (MON-FN-012 separate)

---

## Definition of Done

- [ ] 2 routers criados
- [ ] Mixpanel events firing prod (verify dashboard)
- [ ] Tests pass
- [ ] Suite passa
- [ ] @po validation GO

---

## Dev Notes

- `routes/analytics.py:547L:6 funções`
- `startup/routes.py::_v1_routers` register both new routers
- Memory `reference_mixpanel_backend_token_gap_2026_04_24`: verify `MIXPANEL_TOKEN` em Railway bidiq-backend

---

## Risk & Rollback

| Trigger | Ação |
|---|---|
| Mixpanel rate limit em prod | Async fire-and-forget pattern + Sentry alert |
| Frontend hooks quebram | useAnalytics provides backward alias |

**Rollback:** revert split; analytics.py monolítico restaurado.

---

## Dependencies

**Entrada:** PR #536 Done · BIZ-METRIC-001 (parallel OK)
**Saída:** habilita MON-FN-006 funnel-events-backend-complete (cleaner separation)

---

## PO Validation

**Validated by:** @po (Pax)
**Date:** 2026-04-28
**Verdict:** GO
**Score:** 10/10

### 10-Point Checklist

| # | Criterion | ✓/✗ | Notes |
|---|-----------|-----|-------|
| 1 | Clear and objective title | ✓ | Split explícito 547L conversion vs usage. |
| 2 | Complete description | ✓ | Memory mixpanel silenced 7d documentado. |
| 3 | Testable acceptance criteria | ✓ | 5 ACs com Mixpanel events firing prod. |
| 4 | Well-defined scope | ✓ | OUT exclude new endpoints + cohort dashboard. |
| 5 | Dependencies mapped | ✓ | PR #536 Done + BIZ-METRIC-001 paralelo OK. |
| 6 | Complexity estimate | ✓ | M (3-4d). |
| 7 | Business value | ✓ | Funnel events + boundaries claros. |
| 8 | Risks documented | ✓ | Async fire-and-forget pattern + Sentry alert. |
| 9 | Criteria of Done | ✓ | 5 itens. |
| 10 | Alignment with PRD/Epic | ✓ | EPIC-MON-FN funnel measurement. |

Status: Draft → Ready.

---

## Change Log

| Data | Versão | Descrição | Autor |
|---|---|---|---|
| 2026-04-28 | 1.0 | Story criada via batch. Origem: `_reversa_sdd/sm-briefing-refactor.md` REF-MON-004. | @sm (River) |
| 2026-04-28 | 1.1 | PO validation: GO (10/10). Status: Draft → Ready. | @po (Pax) |
