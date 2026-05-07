# Story CONV-INST-005: Clarity trial/onboarding tagging and first-analysis events

## Status
Ready for Review

## Epic
[EPIC-CONV-DIAG-2026-04-30](EPIC-CONV-DIAG-2026-04-30.md)

## Story

**As a** product analyst trying to segment Clarity heatmaps by funnel state,  
**I want** Clarity and Mixpanel to receive onboarding, trial-start, and first-analysis lifecycle events at the right moments,  
**so that** heatmaps and session recordings can answer how users behave after completing onboarding when first-analysis is successful, empty, or failed.

## Context

Clarity currently receives broad tags such as `plan_type`, `is_trial`, and `user_segment`, plus a small set of events. It does not have enough session-level state to segment trial onboarding recordings by exact step, trial start, first-analysis dispatch, or first-analysis resolution.

## Objective

Instrument the existing onboarding and `/buscar` first-analysis flow using the existing `useClarity` and `useAnalytics` hooks, preserving LGPD analytics consent gates already implemented by those hooks.

## Scope

- `frontend/app/onboarding/page.tsx`
- `frontend/app/components/AnalyticsProvider.tsx`
- `frontend/app/buscar/hooks/useSearchOrchestration.ts`
- `frontend/app/buscar/hooks/useSearch.ts`
- `frontend/app/buscar/hooks/useSearchSSEHandler.ts`
- Focused Jest tests under `frontend/__tests__/onboarding/` and `frontend/__tests__/buscar/`

## Technical Approach

Reuse `useClarity()` for Clarity events/tags and `useAnalytics().trackEvent()` for Mixpanel. Add the onboarding step and first-analysis dispatch markers at existing transition points in `onboarding/page.tsx`. Pass the `auto=true` first-analysis context into the search SSE handler and emit terminal Mixpanel events once per first-analysis search with a `useRef` guard.

## Estimate

4 hours. Atomic: one instrumentation slice, limited to onboarding, analytics provider, `/buscar` search lifecycle, tests, and this story file.

## Acceptance Criteria

1. [x] **AC1 - Clarity `onboarding_step` tag by step:** `frontend/app/onboarding/page.tsx::nextStep` calls `claritySet('onboarding_step', '1/3'|'2/3'|'3/3')` on each step transition.
2. [x] **AC2 - Clarity event `trial_started`:** After `/api/first-analysis` returns 2xx, onboarding fires `clarityEvent('trial_started')` and `claritySet('trial_started_at', new Date().toISOString())`.
3. [x] **AC3 - Clarity event `first_analysis_dispatched`:** After `/api/first-analysis` returns 2xx, onboarding fires `clarityEvent('first_analysis_dispatched')` and `claritySet('first_analysis_search_id', search_id)`.
4. [x] **AC4 - Mixpanel `first_analysis_completed` vs `first_analysis_failed`:** `/buscar` auto first-analysis SSE resolution emits `first_analysis_completed`, `first_analysis_empty`, or `first_analysis_failed` once with search metadata.
5. [x] **AC5 - Mixpanel `onboarding_error_*`:** Onboarding first-analysis denial, timeout, and generic failures emit dedicated Mixpanel events; trial-expired also emits Clarity `first_analysis_trial_expired`.
6. [x] **AC6 - Clarity `trial_days_remaining` tag:** `AnalyticsProvider.tsx` sets `trial_days_remaining` when trial expiration exists and skips gracefully otherwise.
7. [x] **AC7 - REUSE strict:** No new Clarity hook was created; existing `useClarity()` is reused.
8. [x] **AC8 - LGPD:** Instrumentation uses existing `useClarity` and `useAnalytics` hooks, which gate calls through `getCookieConsent().analytics === true`.
9. [x] **AC9 - Tests:** Focused Jest tests cover onboarding step tagging and first-analysis completed/empty/failed events.

## Tasks / Subtasks

- [x] Task 1 - `onboarding_step` tag (AC1)
  - [x] Add `claritySet('onboarding_step', ...)` in each `nextStep()` branch.
- [x] Task 2 - `trial_started` event + tag (AC2)
  - [x] Add `clarityEvent('trial_started')` and `claritySet('trial_started_at', ...)` after first-analysis 2xx.
- [x] Task 3 - `first_analysis_dispatched` (AC3)
  - [x] Add `clarityEvent('first_analysis_dispatched')` and `claritySet('first_analysis_search_id', search_id)`.
- [x] Task 4 - `first_analysis_completed/failed/empty` (AC4)
  - [x] Use `/buscar` auto flag and SSE terminal events.
  - [x] Guard event emission with `useRef` to prevent duplicates.
- [x] Task 5 - `onboarding_error_*` (AC5)
  - [x] Track denied, timeout, and generic error paths.
- [x] Task 6 - `trial_days_remaining` tag (AC6)
  - [x] Calculate from `trial_expires_at` when present.
- [x] Task 7 - Tests (AC9)
  - [x] Add onboarding step-tagging tests.
  - [x] Add first-analysis SSE lifecycle tests.

## Dev Notes

- The GitHub issue referenced this story path, but the file was missing in this worktree. Recreated it from issue #608 and added the explicit estimate required by the execution protocol.
- `useClarity` and `useAnalytics` already enforce LGPD analytics consent gates.
- `search_id`, CNAE, and UF are non-email/non-name operational identifiers for funnel diagnostics.

## Dev Agent Record

### Agent Model Used
GPT-5 Codex

### Debug Log References
- `node .aiox-core/development/scripts/generate-greeting.js dev` failed because `js-yaml` was not available from the repo-root runtime path.

### Completion Notes
- Implemented feasible ACs in the existing frontend instrumentation flow.
- Added URL context (`cnae`, `ufs`) to the first-analysis redirect so `/buscar` can populate the `first_analysis_empty` event payload.
- Kept all analytics calls behind existing hooks instead of introducing new consent logic.

### File List
- `docs/stories/2026-04/CONV-INST-005-clarity-trial-onboarding-tagging.story.md`
- `frontend/app/onboarding/page.tsx`
- `frontend/app/components/AnalyticsProvider.tsx`
- `frontend/app/buscar/hooks/useSearchOrchestration.ts`
- `frontend/app/buscar/hooks/useSearch.ts`
- `frontend/app/buscar/hooks/useSearchSSEHandler.ts`
- `frontend/__tests__/onboarding/onboarding-step-tagging.test.tsx`
- `frontend/__tests__/buscar/first-analysis-completed.test.tsx`

## Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2026-04-30 | 0.1 | Story drafted from EPIC-CONV-DIAG-2026-04-30 W1 | @sm |
| 2026-04-30 | 0.2 | PO validation GO 9/10; Ready for implementation | @po |
| 2026-05-06 | 1.0 | Implemented Clarity trial/onboarding tags, first-analysis Mixpanel terminal events, focused tests, and story execution records | Codex |
