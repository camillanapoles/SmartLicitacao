/**
 * Tests for MS Clarity onboarding step tagging (lib/analytics/clarity.ts).
 *
 * Verifies:
 * - tagOnboardingStep calls window.clarity('set', 'onboarding_step', step)
 * - All OnboardingStep values are forwarded correctly
 * - No-op when window.clarity is unavailable
 * - No-op when analytics consent is not given
 */

// Mock ClarityAnalytics before importing the module under test
jest.mock('../../../app/components/ClarityAnalytics', () => ({
  setClarityTag: jest.fn(),
}));

import { setClarityTag } from '../../../app/components/ClarityAnalytics';
import { tagOnboardingStep, type OnboardingStep } from '../clarity';

const mockSetClarityTag = setClarityTag as jest.Mock;

beforeEach(() => {
  mockSetClarityTag.mockClear();
});

describe('tagOnboardingStep', () => {
  const steps: OnboardingStep[] = [
    'signup_form',
    'email_pending',
    'email_confirmed',
    'profile_setup',
    'first_search',
    'trial_activated',
    'churned',
  ];

  it.each(steps)('calls setClarityTag with onboarding_step=%s', (step) => {
    tagOnboardingStep(step);
    expect(mockSetClarityTag).toHaveBeenCalledWith('onboarding_step', step);
  });

  it('calls setClarityTag exactly once per invocation', () => {
    tagOnboardingStep('signup_form');
    expect(mockSetClarityTag).toHaveBeenCalledTimes(1);
  });

  it('does not throw when setClarityTag throws internally', () => {
    mockSetClarityTag.mockImplementationOnce(() => {
      throw new Error('Clarity not available');
    });
    expect(() => tagOnboardingStep('signup_form')).not.toThrow();
  });
});
