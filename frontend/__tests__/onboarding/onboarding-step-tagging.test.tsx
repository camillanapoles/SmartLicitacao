/**
 * CONV-INST-005: Clarity onboarding step tagging (AC1)
 *
 * Tests:
 * 1. claritySet('onboarding_step', '1/3') fires when step 0→1 transitions
 * 2. claritySet('onboarding_step', '2/3') fires when step 1→2 transitions
 * 3. claritySet('onboarding_step', '3/3') fires when step 2→submit
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';

// ── Mocks ──────────────────────────────────────────────────────────────────

const mockClaritySet = jest.fn();
const mockClarityEvent = jest.fn();
const mockTrackEvent = jest.fn();
const mockRouterPush = jest.fn();
const mockRouterReplace = jest.fn();

jest.mock('../../hooks/useClarity', () => ({
  useClarity: () => ({
    clarityEvent: mockClarityEvent,
    claritySet: mockClaritySet,
    clarityIdentify: jest.fn(),
  }),
}));

jest.mock('../../hooks/useAnalytics', () => ({
  useAnalytics: () => ({
    trackEvent: mockTrackEvent,
  }),
  getDaysInTrial: jest.fn().mockReturnValue(14),
}));

jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockRouterPush,
    replace: mockRouterReplace,
  }),
}));

jest.mock('../../app/components/AuthProvider', () => ({
  useAuth: () => ({
    user: { id: 'user-test', created_at: '2026-04-01T00:00:00Z' },
    session: { access_token: 'test-token' },
    loading: false,
  }),
}));

// Suppress react-hook-form zod resolver dep warning in tests
jest.mock('@hookform/resolvers/zod', () => ({
  zodResolver: () => async () => ({ values: {}, errors: {} }),
}));

jest.mock('sonner', () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

jest.mock('../../lib/storage', () => ({
  safeSetItem: jest.fn(),
}));

jest.mock('../../lib/analytics-helpers', () => ({
  getDaysInTrial: jest.fn().mockReturnValue(14),
}));

// Mock child step components to avoid complex rendering
jest.mock('../../app/onboarding/components/OnboardingProgress', () => ({
  OnboardingProgress: () => <div data-testid="progress" />,
}));

jest.mock('../../app/onboarding/components/OnboardingStep1', () => ({
  OnboardingStep1: ({ onChange }: { onChange: (d: Record<string, unknown>) => void }) => (
    <div data-testid="step1">
      <button
        onClick={() => onChange({ cnae: '4120400', objetivo_principal: 'Construção civil' })}
        data-testid="fill-step1"
      >
        Fill Step 1
      </button>
    </div>
  ),
}));

jest.mock('../../app/onboarding/components/OnboardingStep2', () => ({
  OnboardingStep2: ({ onChange }: { onChange: (d: Record<string, unknown>) => void }) => (
    <div data-testid="step2">
      <button
        onClick={() => onChange({ ufs_atuacao: ['SP'], faixa_valor_min: 100000, faixa_valor_max: 500000 })}
        data-testid="fill-step2"
      >
        Fill Step 2
      </button>
    </div>
  ),
}));

jest.mock('../../app/onboarding/components/OnboardingStep3', () => ({
  OnboardingStep3: () => <div data-testid="step3" />,
}));

// ── Tests ───────────────────────────────────────────────────────────────────

describe('CONV-INST-005: onboarding step Clarity tagging', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // resetMocks:true in jest.config resets implementations — re-set per test
    global.fetch = jest.fn().mockImplementation((url: string) => {
      if (url === '/api/profile-context') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ context_data: {} }) });
      }
      return Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) });
    });
  });

  it('claritySet onboarding_step=1/3 fires on step 0→1 transition', async () => {
    const OnboardingPage = require('../../app/onboarding/page').default;
    render(<OnboardingPage />);

    // Fill step 1 data so canProceed() = true
    await act(async () => {
      fireEvent.click(screen.getByTestId('fill-step1'));
    });

    // Click Continuar
    await act(async () => {
      fireEvent.click(screen.getByTestId('btn-continuar'));
    });

    await waitFor(() => {
      expect(mockClaritySet).toHaveBeenCalledWith('onboarding_step', '1/3');
    });
  });

  it('claritySet onboarding_step=2/3 fires on step 1→2 transition', async () => {
    const OnboardingPage = require('../../app/onboarding/page').default;
    render(<OnboardingPage />);

    // Advance to step 1
    await act(async () => {
      fireEvent.click(screen.getByTestId('fill-step1'));
    });
    await act(async () => {
      fireEvent.click(screen.getByTestId('btn-continuar'));
    });

    // Fill step 2
    await act(async () => {
      fireEvent.click(screen.getByTestId('fill-step2'));
    });
    await act(async () => {
      fireEvent.click(screen.getByTestId('btn-continuar'));
    });

    await waitFor(() => {
      expect(mockClaritySet).toHaveBeenCalledWith('onboarding_step', '2/3');
    });
  });

  it('claritySet onboarding_step=3/3 fires on step 2→submit', async () => {
    const OnboardingPage = require('../../app/onboarding/page').default;
    render(<OnboardingPage />);

    // Advance to step 1
    await act(async () => {
      fireEvent.click(screen.getByTestId('fill-step1'));
    });
    await act(async () => {
      fireEvent.click(screen.getByTestId('btn-continuar'));
    });

    // Advance to step 2
    await act(async () => {
      fireEvent.click(screen.getByTestId('fill-step2'));
    });
    await act(async () => {
      fireEvent.click(screen.getByTestId('btn-continuar'));
    });

    // On step 3, click submit — mocked fetch will return 500, but claritySet should still fire
    await act(async () => {
      fireEvent.click(screen.getByTestId('btn-continuar'));
    });

    await waitFor(() => {
      expect(mockClaritySet).toHaveBeenCalledWith('onboarding_step', '3/3');
    });
  });
});
