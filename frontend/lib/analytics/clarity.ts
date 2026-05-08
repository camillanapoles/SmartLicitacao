/**
 * MS Clarity onboarding step tagging helpers.
 *
 * All functions are SSR-safe and LGPD-safe — they never throw even if
 * Clarity is not loaded or analytics consent has not been given.
 *
 * Import pattern:
 *   import { tagOnboardingStep } from '@/lib/analytics/clarity';
 */

import { setClarityTag } from '../../app/components/ClarityAnalytics';

// Funnel steps tracked as onboarding_step tag in Clarity.
export type OnboardingStep =
  | 'signup_form'
  | 'email_pending'
  | 'email_confirmed'
  | 'profile_setup'
  | 'first_search'
  | 'trial_activated'
  | 'churned';

/**
 * Tags the current session with an onboarding funnel step in MS Clarity.
 *
 * The tag appears as a filterable session attribute in the Clarity dashboard
 * under the key `onboarding_step`, enabling heatmap and recording filters
 * per funnel stage.
 *
 * SSR-safe: no-op when called server-side.
 * LGPD-safe: no-op when analytics consent has not been given.
 */
export function tagOnboardingStep(step: OnboardingStep): void {
  setClarityTag('onboarding_step', step);
}
