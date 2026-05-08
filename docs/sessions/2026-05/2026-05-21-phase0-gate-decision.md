# Phase 0 Gate Decision — 2026-05-21

**Deploy date:** 2026-05-07  
**Evaluation window:** 14 days (2026-05-07 → 2026-05-21)  
**Author:** @pm (to be populated at evaluation)  
**Status:** PENDING — populate at evaluation date

---

## Gate Criteria

```yaml
gate:
  evaluation_date: "2026-05-21"
  deploy_date: "2026-05-07"
  window_days: 14

  # PASS: all 3 conditions met
  pass_conditions:
    form_submitted_distinct: ">=10"         # distinct user sessions
    modalidade_non_null:
      allowed: [intel, radar, report, consultoria]
      disallowed: [nao_sei]                 # at least 1 non-ambiguous
    lead_with_cnpj_valid: ">=1"             # CNPJ format + setor preenchido

  # FAIL: any condition below
  fail_conditions:
    form_submitted_distinct: "<10"
    only_modalidade_nao_sei: true           # all submissions = "nao_sei"

  breakdown_required:
    - field: modalidade
      values: [intel, radar, report, consultoria, nao_sei]
    - field: setor
      values: top_5
    - field: utm_source
      values: top_5
```

---

## Metrics to Collect (populate at evaluation)

| Metric | Value | Source |
|--------|-------|--------|
| `form_submitted` total | — | Mixpanel |
| `form_submitted` distinct sessions | — | Mixpanel |
| Modalidade breakdown | — | Mixpanel / Supabase `lead_capture` |
| Leads with valid CNPJ + setor | — | Supabase `lead_capture` |
| Top traffic sources | — | Mixpanel `utm_source` |
| Conversion: pSEO → form | — | Mixpanel funnel |

---

## Verdict Options

### PASS
**Trigger:** ≥10 distinct `form_submitted` + ≥1 modalidade ≠ `nao_sei` + ≥1 lead with valid CNPJ + setor.

**Action:** Spawn Phase 1 issues:
- `/radar-b2g` real page + Stripe OTP (3 issues)
- `/report-b2g` page + Stripe OTP R$497 (4 issues)
- `/intel-b2g` page + Stripe OTP R$997 (4 issues)
- `/exemplos/*` demo pages (3 issues)
- Stripe products setup (1 issue)
- Backend generation pipelines (4 issues)

### FAIL
**Trigger:** <10 distinct `form_submitted` OR all modalidade = `nao_sei`.

**Action options (choose via `/conselho`):**
1. **Re-tese:** Change messaging angle, rerun Phase 0 for another 14d window
2. **Pivot → Intel Reports T0:** Monetize DataLake directly (2M contracts) without consultoria — PMF blind spot identified 2026-05-04

---

## Evaluation Notes (populate at evaluation)

```
Date evaluated: 
Evaluator: 
Verdict: [ ] PASS  [ ] FAIL
Notes:
```

---

## References

- Phase 0 issue plan: `docs/sessions/2026-05/2026-05-07-reposicionamento-b2g-issues-plan.md`
- PMF blind spots: `memory/project_pmf_blind_spots_2026_05_04.md`
- Intel Reports T0: `project_smartlic_onpage_pivot_2026_04_26.md`
