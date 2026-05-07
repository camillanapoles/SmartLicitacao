/**
 * REPO-018: Tests for lib/analytics-events.ts
 *
 * Verifies that each tracking function:
 * 1. Calls mixpanel.track with the correct event name and payload.
 * 2. Is SSR-safe (no-op when NEXT_PUBLIC_MIXPANEL_TOKEN is missing).
 * 3. Is safe when called without analytics consent.
 */

import {
  trackCTAClick,
  trackFormStarted,
  trackFormSubmitted,
  trackLeadCaptured,
  type CTAClickEvent,
  type FormStartedEvent,
  type FormSubmittedEvent,
  type LeadCapturedEvent,
} from '../../lib/analytics-events';

// ---- Mocks ---------------------------------------------------------------

jest.mock('mixpanel-browser', () => ({
  track: jest.fn(),
}));

jest.mock('@/app/components/CookieConsentBanner', () => ({
  getCookieConsent: jest.fn(() => ({ analytics: true })),
}));

import mixpanel from 'mixpanel-browser';
import { getCookieConsent } from '@/app/components/CookieConsentBanner';

const mockGetCookieConsent = getCookieConsent as jest.Mock;

// ---- Fixtures ------------------------------------------------------------

const ctaEvent: CTAClickEvent = {
  label: 'Começar agora',
  source: 'landing_hero',
  destination: '/planos',
  cta_type: 'self-service',
};

const formStartedEvent: FormStartedEvent = {
  form_name: 'lead_capture_modal',
  source: 'observatorio_raio_x',
};

const formSubmittedEvent: FormSubmittedEvent = {
  form_name: 'lead_capture_modal',
  source: 'observatorio_raio_x',
  modalidade: 'radar',
};

const leadCapturedEvent: LeadCapturedEvent = {
  source: 'observatorio_raio_x',
  modalidade: 'radar',
  form_name: 'lead_capture_modal',
};

// ---- Helpers -------------------------------------------------------------

const originalEnv = process.env;

function clearMocks() {
  jest.clearAllMocks();
  // Restore env snapshot and set the token so tracking is enabled by default.
  process.env = { ...originalEnv };
  process.env.NEXT_PUBLIC_MIXPANEL_TOKEN = 'test-token';
  process.env.NODE_ENV = 'test';
  mockGetCookieConsent.mockReturnValue({ analytics: true });
}

// ---- Tests ---------------------------------------------------------------

describe('analytics-events — trackCTAClick', () => {
  beforeEach(clearMocks);

  it('calls mixpanel.track with event name "cta_click" and full payload', () => {
    trackCTAClick(ctaEvent);

    expect(mixpanel.track).toHaveBeenCalledTimes(1);
    expect(mixpanel.track).toHaveBeenCalledWith('cta_click', {
      label: 'Começar agora',
      source: 'landing_hero',
      destination: '/planos',
      cta_type: 'self-service',
      timestamp: expect.any(String),
      environment: expect.any(String),
    });
  });

  it('is no-op when NEXT_PUBLIC_MIXPANEL_TOKEN is missing (SSR-safe)', () => {
    const original = process.env.NEXT_PUBLIC_MIXPANEL_TOKEN;
    delete process.env.NEXT_PUBLIC_MIXPANEL_TOKEN;

    trackCTAClick(ctaEvent);

    expect(mixpanel.track).not.toHaveBeenCalled();
    process.env.NEXT_PUBLIC_MIXPANEL_TOKEN = original;
  });

  it('is no-op when analytics consent is not granted', () => {
    mockGetCookieConsent.mockReturnValue({ analytics: false });

    trackCTAClick(ctaEvent);

    expect(mixpanel.track).not.toHaveBeenCalled();
  });

  it('is no-op when consent object is null', () => {
    mockGetCookieConsent.mockReturnValue(null);

    trackCTAClick(ctaEvent);

    expect(mixpanel.track).not.toHaveBeenCalled();
  });
});

describe('analytics-events — trackFormStarted', () => {
  beforeEach(clearMocks);

  it('calls mixpanel.track with event name "form_started" and full payload', () => {
    trackFormStarted(formStartedEvent);

    expect(mixpanel.track).toHaveBeenCalledTimes(1);
    expect(mixpanel.track).toHaveBeenCalledWith('form_started', {
      form_name: 'lead_capture_modal',
      source: 'observatorio_raio_x',
      timestamp: expect.any(String),
      environment: expect.any(String),
    });
  });

  it('is no-op when NEXT_PUBLIC_MIXPANEL_TOKEN is missing', () => {
    const original = process.env.NEXT_PUBLIC_MIXPANEL_TOKEN;
    delete process.env.NEXT_PUBLIC_MIXPANEL_TOKEN;

    trackFormStarted(formStartedEvent);

    expect(mixpanel.track).not.toHaveBeenCalled();
    process.env.NEXT_PUBLIC_MIXPANEL_TOKEN = original;
  });

  it('is no-op when analytics consent is not granted', () => {
    mockGetCookieConsent.mockReturnValue({ analytics: false });

    trackFormStarted(formStartedEvent);

    expect(mixpanel.track).not.toHaveBeenCalled();
  });
});

describe('analytics-events — trackFormSubmitted', () => {
  beforeEach(clearMocks);

  it('calls mixpanel.track with event name "form_submitted" and full payload including modalidade', () => {
    trackFormSubmitted(formSubmittedEvent);

    expect(mixpanel.track).toHaveBeenCalledTimes(1);
    expect(mixpanel.track).toHaveBeenCalledWith('form_submitted', {
      form_name: 'lead_capture_modal',
      source: 'observatorio_raio_x',
      modalidade: 'radar',
      timestamp: expect.any(String),
      environment: expect.any(String),
    });
  });

  it('tracks without optional modalidade field', () => {
    const eventWithoutModalidade: FormSubmittedEvent = {
      form_name: 'contact',
      source: 'footer',
    };
    trackFormSubmitted(eventWithoutModalidade);

    expect(mixpanel.track).toHaveBeenCalledWith('form_submitted', {
      form_name: 'contact',
      source: 'footer',
      timestamp: expect.any(String),
      environment: expect.any(String),
    });
  });

  it('is no-op when NEXT_PUBLIC_MIXPANEL_TOKEN is missing', () => {
    const original = process.env.NEXT_PUBLIC_MIXPANEL_TOKEN;
    delete process.env.NEXT_PUBLIC_MIXPANEL_TOKEN;

    trackFormSubmitted(formSubmittedEvent);

    expect(mixpanel.track).not.toHaveBeenCalled();
    process.env.NEXT_PUBLIC_MIXPANEL_TOKEN = original;
  });

  it('is no-op when analytics consent is not granted', () => {
    mockGetCookieConsent.mockReturnValue({ analytics: false });

    trackFormSubmitted(formSubmittedEvent);

    expect(mixpanel.track).not.toHaveBeenCalled();
  });
});

describe('analytics-events — trackLeadCaptured', () => {
  beforeEach(clearMocks);

  it('calls mixpanel.track with event name "lead_captured" and full payload', () => {
    trackLeadCaptured(leadCapturedEvent);

    expect(mixpanel.track).toHaveBeenCalledTimes(1);
    expect(mixpanel.track).toHaveBeenCalledWith('lead_captured', {
      source: 'observatorio_raio_x',
      modalidade: 'radar',
      form_name: 'lead_capture_modal',
      timestamp: expect.any(String),
      environment: expect.any(String),
    });
  });

  it('tracks with only required source field', () => {
    const minimalEvent: LeadCapturedEvent = { source: 'pricing_page' };
    trackLeadCaptured(minimalEvent);

    expect(mixpanel.track).toHaveBeenCalledWith('lead_captured', {
      source: 'pricing_page',
      timestamp: expect.any(String),
      environment: expect.any(String),
    });
  });

  it('is no-op when NEXT_PUBLIC_MIXPANEL_TOKEN is missing', () => {
    const original = process.env.NEXT_PUBLIC_MIXPANEL_TOKEN;
    delete process.env.NEXT_PUBLIC_MIXPANEL_TOKEN;

    trackLeadCaptured(leadCapturedEvent);

    expect(mixpanel.track).not.toHaveBeenCalled();
    process.env.NEXT_PUBLIC_MIXPANEL_TOKEN = original;
  });

  it('is no-op when analytics consent is not granted', () => {
    mockGetCookieConsent.mockReturnValue({ analytics: false });

    trackLeadCaptured(leadCapturedEvent);

    expect(mixpanel.track).not.toHaveBeenCalled();
  });
});

describe('analytics-events — error resilience', () => {
  beforeEach(clearMocks);

  it('does not throw when mixpanel.track throws', () => {
    const consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation();
    (mixpanel.track as jest.Mock).mockImplementationOnce(() => {
      throw new Error('Mixpanel error');
    });

    expect(() => trackCTAClick(ctaEvent)).not.toThrow();
    expect(consoleWarnSpy).toHaveBeenCalledWith(
      'Analytics tracking failed:',
      expect.any(Error)
    );

    consoleWarnSpy.mockRestore();
  });
});
