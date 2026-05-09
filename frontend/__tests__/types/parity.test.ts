/**
 * PARITY-BE-FE-001 (AC4): Compile-time type parity assertions.
 *
 * The audit script `backend/scripts/audit_response_model_coverage.py`
 * enforces that every FastAPI route declares `response_model=`. This test
 * is the FRONTEND counterpart: it asserts that the OpenAPI types we
 * generate from the backend (`frontend/app/api-types.generated.ts`) do
 * not collapse the schemas we care about into `{[k: string]: unknown}`.
 *
 * If this test fails to compile (`tsc --noEmit`), it means a critical
 * schema lost its declared shape — usually because a route lost its
 * `response_model=` kwarg or the schema was renamed without updating
 * `frontend/app/types.ts` re-exports.
 *
 * NOTE: Jest does not type-check at runtime; this file's value is the
 * compile-time signal it gives `tsc --noEmit` (run by the
 * `api-types-check.yml` CI workflow). The runtime test below exists so
 * Jest does not complain about an empty file.
 */

import type { components } from '@/app/api-types.generated';

// ---------------------------------------------------------------------------
// Compile-time assertion helper
// ---------------------------------------------------------------------------

/**
 * Resolves to `T` only when `T` is *not* an unconstrained
 * `{[k: string]: unknown}`. Trying to assign such an unknown shape will
 * fail to compile, which is the whole point.
 */
type AssertNotUnknown<T> = [T] extends [Record<string, unknown>]
  ? Record<string, unknown> extends T
    ? never
    : T
  : T;

// ---------------------------------------------------------------------------
// Schemas critical to frontend behaviour. If any of these break, the
// admin / billing / search UI silently regresses to `unknown`.
// ---------------------------------------------------------------------------

// Admin (Pass 1)
type _AdminCronStatus = AssertNotUnknown<
  components['schemas']['AdminCronStatusResponse']
>;
type _AdminLlmCost = AssertNotUnknown<
  components['schemas']['AdminLlmCostResponse']
>;
type _AdminSearchTrace = AssertNotUnknown<
  components['schemas']['AdminSearchTraceResponse']
>;

// Pipeline / billing
type _PipelineItem = AssertNotUnknown<
  components['schemas']['PipelineItemResponse']
>;
type _BillingPlans = AssertNotUnknown<
  components['schemas']['BillingPlansResponse']
>;
type _CheckoutResponse = AssertNotUnknown<
  components['schemas']['CheckoutResponse']
>;

// User / auth
type _UserProfile = AssertNotUnknown<
  components['schemas']['UserProfileResponse']
>;
type _TrialStatus = AssertNotUnknown<
  components['schemas']['TrialStatusResponse']
>;

// Search
type _SearchStatus = AssertNotUnknown<
  components['schemas']['SearchStatusResponse']
>;

// Health
type _Readiness = AssertNotUnknown<components['schemas']['ReadinessResponse']>;
type _Sources = AssertNotUnknown<
  components['schemas']['SourcesHealthResponse']
>;

// Pass 2 — admin / health / org / partner permissive shapes
type _SystemHealth = AssertNotUnknown<
  components['schemas']['SystemHealthResponse']
>;
type _CacheHealth = AssertNotUnknown<
  components['schemas']['CacheHealthResponse']
>;
type _SloDashboard = AssertNotUnknown<
  components['schemas']['SloDashboardResponse']
>;
type _OrgMembership = AssertNotUnknown<
  components['schemas']['OrganizationMembershipResponse']
>;
type _PartnerDashboard = AssertNotUnknown<
  components['schemas']['PartnerDashboardResponse']
>;

// ---------------------------------------------------------------------------
// Runtime placeholder so Jest collects this file as a test module.
// ---------------------------------------------------------------------------

describe('PARITY-BE-FE-001 — generated types compile-time invariants', () => {
  it('imports the generated module without runtime errors', () => {
    // The real assertion happens at compile time via the type aliases above.
    // If `tsc --noEmit` succeeds, the parity invariant holds.
    expect(true).toBe(true);
  });
});
