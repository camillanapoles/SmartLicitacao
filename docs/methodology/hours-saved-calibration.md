# `hours_saved_per_search` Calibration Methodology

**Story:** [BIZ-METRIC-001](../../docs/stories/2026-04/BIZ-METRIC-001-empirical-hours-saved-survey.story.md)
**Origin:** Reversa Audit 2026-04-27 (`_reversa_sdd/review-report.md` Gap-6)
**Status:** Implementation merged 2026-04-28 — collection in progress (target n>=30).

---

## What is this?

The personal dashboard surfaces an `estimated_hours_saved` figure per
user (e.g. *"você economizou 24h usando o SmartLic"*). It is computed
in `backend/routes/analytics.py::summary` as:

```
estimated_hours_saved = total_searches * hours_saved_per_search
```

where `hours_saved_per_search` is read from
`app_config.hours_saved_per_search` via a TTL-cached helper
(`backend/utils/app_config.py`).

Until this story shipped, the constant was hardcoded as `2.0` —
arbitrary, not based on user data. This document explains how the new
empirical calibration replaces that arbitrary value.

---

## Why a survey, not Mixpanel time-on-task?

The CTO decision (2026-04-27) explicitly rejected Mixpanel-based
instrumentation:

| Approach | What it measures | Problem |
|----------|------------------|---------|
| Mixpanel `time_on_search_page` | Time the user spent inside SmartLic | NOT the time saved — the metric we want is *time saved vs. doing this manually* (PNCP web + spreadsheets), which Mixpanel cannot observe. |
| **Post-export survey** (chosen) | The user's own estimate of the manual-equivalent time | Direct contrafactual — exactly what marketing copy and dashboard surfaces claim. Trade-off: relies on self-report. |

The survey asks: *"Sem o SmartLic, quanto tempo isso teria levado
fazendo manualmente?"* (Slider 0.5h → 20h, optional free-text "Como
você teria feito antes?"). Captured via
`POST /v1/survey/export-time-saved`, persisted to
`export_time_saved_survey`.

---

## Why median, not mean?

We expect a heavily right-skewed distribution: most users will report
2-5 hours, but some will report 20+ hours (long, manual research
projects). The mean of such a distribution is dragged up by the tail
and *overstates* typical savings, fueling the over-promise risk
documented in the story (R3).

The **median** is robust to outliers and answers a more honest
question: *"What does the typical user save?"* This matches the way
the figure is consumed in product copy ("você economizou X horas")
which a user mentally compares to *their own* expected savings — not
to the cohort mean.

---

## Why IQR (Tukey) outlier removal?

Self-reported survey data is noisy. Some respondents will:

- Misread the slider (e.g. report 50h for a 2h export).
- Anchor on the wrong reference task (estimating an entire research
  pipeline, not just the export).
- Click through to dismiss the modal and accidentally submit at the
  default value.

The Tukey IQR rule (drop values outside `[Q1 - 1.5*IQR, Q3 + 1.5*IQR]`)
is a textbook, defensible filter. It removes pathological extremes
without the parametric assumptions of z-score (which assumes
normality — survey data is not normal).

The implementation lives in
`backend/routes/admin_calibration.py::filter_outliers_iqr` and is
shared with `scripts/recalibrate_hours_saved.py` so the admin
endpoint, the CLI, and the dashboard report all use **the same
algorithm with the same inputs** — no drift.

---

## Why n>=30?

Below n=30 the median is too volatile: a single outlier-survivor row
can shift the value by >20%, producing an unstable dashboard
constant. Above n=30 the standard error of the median is small enough
that the figure is reproducible across re-calibrations weeks apart.

This is the *post-IQR* sample size, not the raw count: if 35 surveys
are collected and 4 are dropped as outliers, eligibility is `31 >= 30`
=> recalibration proceeds. If only 28 survive IQR, recalibration is
blocked with `reason: insufficient_sample`.

The threshold is encoded in
`backend/routes/admin_calibration.py::MIN_SAMPLE_SIZE` and surfaced in
the API response (`eligible: false`, `reason: ...`) so the admin
dashboard can render an explicit "not enough data yet" state.

---

## How often should we recalibrate?

| Cadence | Trigger | Action |
|---------|---------|--------|
| Quarterly (suggested) | Calendar | `python scripts/recalibrate_hours_saved.py --range-days 90` |
| Ad-hoc | Product team observes constant feels off | Same — and document the rationale in PR description |
| Annually | Long-term trend review | Compute the median per quarter for the trailing year, flag drift |

Each recalibration writes a markdown report to `docs/reports/` with
the exact distribution, IQR bounds, and the new vs. old value. The
report is the durable audit trail.

---

## Response bias — known limitation

Survey response bias is unavoidable: satisfied users are over-represented
among respondents, dissatisfied users dismiss the modal. We mitigate by:

- **Frequency throttling** (story AC8): modal appears every 3rd export
  per user, max 5 per user lifetime. Reduces fatigue-driven low-quality
  responses without forcing every export to surface the modal.
- **Eligibility gate** (story AC10): only users with >=3 completed
  searches see the modal — filters new users without baseline.
- **Documentation** (this file): we explicitly disclose the bias so
  dashboard consumers (internal + external comms) understand the
  figure is *self-reported* not *observed*.

A future iteration may incentivise responses ("respond to 3 surveys =
1 month free") to reduce bias, but that is out of scope here.

---

## Implementation map

| Concern | Location |
|---------|----------|
| Survey table | `supabase/migrations/20260428100600_export_time_saved_survey.sql` |
| App config table | `supabase/migrations/20260428100700_app_config_table.sql` |
| TTL-cached read helper | `backend/utils/app_config.py` |
| Survey submit endpoint | `backend/routes/survey.py` (`POST /v1/survey/export-time-saved`) |
| Admin aggregate / patch / recalibrate | `backend/routes/admin_calibration.py` |
| Recalibration CLI | `scripts/recalibrate_hours_saved.py` |
| Calibration dashboard UI | `frontend/app/admin/calibration/page.tsx` |
| Modal component | `frontend/components/survey/ExportTimeSavedModal.tsx` |
| Backend tests | `backend/tests/test_survey.py`, `test_admin_calibration.py`, `test_analytics_app_config.py` |
| Frontend tests | `frontend/__tests__/components/SurveyModal.test.tsx`, `frontend/__tests__/components/calibration-page.test.tsx` |

---

## Operator runbook

### View current calibration state
```
GET /v1/admin/survey/export-time-saved?range_days=90
```
Returns sample size, IQR bounds, median, histogram, and current
constant.

### Recalibrate (dry-run)
```
POST /v1/admin/calibration/recalibrate
{ "range_days": 90, "apply": false }
```
Returns the proposed new value plus `eligible` flag.

### Recalibrate (apply)
```
POST /v1/admin/calibration/recalibrate
{ "range_days": 90, "apply": true }
```
Writes the new value to `app_config`, drops the in-process TTL cache
in this worker. Other workers see the new value after their TTL
expires (default 5 min — bounded staleness).

### Manual override
```
PATCH /v1/admin/config/hours_saved_per_search
{ "value": 3.2, "description": "manual override 2026-Q3" }
```
Use sparingly; prefer the survey-driven path.

### CLI report
```
python scripts/recalibrate_hours_saved.py --range-days 90 --output-dir docs/reports
```
Generates a markdown report plus optionally `--apply` writes through.
