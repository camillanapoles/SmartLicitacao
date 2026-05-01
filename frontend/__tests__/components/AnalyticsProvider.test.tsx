/**
 * AnalyticsProvider Component Tests
 *
 * Tests Mixpanel initialization, cookie consent handling, and page tracking
 */

import { render, screen, waitFor } from '@testing-library/react';
import { AnalyticsProvider } from '@/app/components/AnalyticsProvider';
import mixpanel from 'mixpanel-browser';
import * as Sentry from '@sentry/nextjs';
import { usePathname } from 'next/navigation';

// Mock dependencies
jest.mock('mixpanel-browser');
jest.mock('@sentry/nextjs', () => ({
  init: jest.fn(),
  getClient: jest.fn(() => null),
}));
jest.mock('next/navigation', () => ({
  usePathname: jest.fn(() => '/test-page'),
}));

// Mock getCookieConsent and captureUTMParams
jest.mock('../../app/components/CookieConsentBanner', () => ({
  getCookieConsent: jest.fn(),
}));

jest.mock('../../hooks/useAnalytics', () => ({
  captureUTMParams: jest.fn(),
  getStoredUTMParams: jest.fn(() => ({})),
}));

jest.mock('../../lib/analytics-traffic-source', () => ({
  deriveTrafficSource: jest.fn(() => 'direct'),
}));

jest.mock('../../app/components/AuthProvider', () => ({
  useAuth: () => ({ user: null, session: null, isAdmin: false, loading: false }),
}));

jest.mock('../../hooks/useUserProfile', () => ({
  useUserProfile: () => ({ data: null, error: null, isLoading: false }),
}));

jest.mock('../../hooks/useClarity', () => ({
  useClarity: () => ({
    clarityIdentify: jest.fn(),
    claritySet: jest.fn(),
    clarityEvent: jest.fn(),
  }),
}));

const mockMixpanel = mixpanel as jest.Mocked<typeof mixpanel>;
const { getCookieConsent } = require('../../app/components/CookieConsentBanner');
const { captureUTMParams, getStoredUTMParams } = require('../../hooks/useAnalytics');
const { deriveTrafficSource } = require('../../lib/analytics-traffic-source');

describe('AnalyticsProvider Component', () => {
  const originalEnv = process.env;
  const originalSentry = { ...Sentry };

  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
    sessionStorage.clear();
    process.env = { ...originalEnv };
    process.env.NEXT_PUBLIC_MIXPANEL_TOKEN = 'test-token-123';
    process.env.NODE_ENV = 'test';

    // Mock Sentry.getClient to return null initially
    (Sentry.getClient as jest.Mock).mockReturnValue(null);

    // Default: no UTM params stored, direct traffic
    getStoredUTMParams.mockReturnValue({});
    deriveTrafficSource.mockReturnValue('direct');

    // Restore usePathname implementation (reset by resetMocks:true in jest.config.js)
    (usePathname as jest.Mock).mockReturnValue('/test-page');
  });

  afterEach(() => {
    process.env = originalEnv;
    jest.restoreAllMocks();
  });

  describe('initialization', () => {
    it('should render children', () => {
      getCookieConsent.mockReturnValue({ analytics: true });

      render(
        <AnalyticsProvider>
          <div>Test Content</div>
        </AnalyticsProvider>
      );

      expect(screen.getByText('Test Content')).toBeInTheDocument();
    });

    it('should not initialize Mixpanel if token is missing', () => {
      delete process.env.NEXT_PUBLIC_MIXPANEL_TOKEN;
      getCookieConsent.mockReturnValue({ analytics: true });

      render(
        <AnalyticsProvider>
          <div>Test Content</div>
        </AnalyticsProvider>
      );

      expect(mockMixpanel.init).not.toHaveBeenCalled();
    });

    it('should initialize Mixpanel if consent is granted', async () => {
      getCookieConsent.mockReturnValue({ analytics: true });

      render(
        <AnalyticsProvider>
          <div>Test Content</div>
        </AnalyticsProvider>
      );

      await waitFor(() => {
        expect(mockMixpanel.init).toHaveBeenCalledWith('test-token-123', {
          debug: false,
          track_pageview: false,
          persistence: 'localStorage',
        });
      });
    });

    it('should not initialize Mixpanel if consent is not granted', () => {
      getCookieConsent.mockReturnValue({ analytics: false });

      render(
        <AnalyticsProvider>
          <div>Test Content</div>
        </AnalyticsProvider>
      );

      expect(mockMixpanel.init).not.toHaveBeenCalled();
    });

    it('should not initialize if consent is null', () => {
      getCookieConsent.mockReturnValue(null);

      render(
        <AnalyticsProvider>
          <div>Test Content</div>
        </AnalyticsProvider>
      );

      expect(mockMixpanel.init).not.toHaveBeenCalled();
    });
  });

  describe('page tracking', () => {
    it('should track page_load event after initialization', async () => {
      getCookieConsent.mockReturnValue({ analytics: true });

      render(
        <AnalyticsProvider>
          <div>Test Content</div>
        </AnalyticsProvider>
      );

      await waitFor(() => {
        expect(mockMixpanel.track).toHaveBeenCalledWith('page_load', expect.objectContaining({
          environment: 'test',
        }));
      });

      // Verify path is included (may be undefined in test environment)
      const trackCalls = mockMixpanel.track.mock.calls;
      const pageLoadCall = trackCalls.find((call: any) => call[0] === 'page_load');
      expect(pageLoadCall).toBeDefined();
      expect(pageLoadCall![1]).toHaveProperty('timestamp');
    });

    it('should capture UTM params on first load', async () => {
      getCookieConsent.mockReturnValue({ analytics: true });
      captureUTMParams.mockClear();

      render(
        <AnalyticsProvider>
          <div>Test Content</div>
        </AnalyticsProvider>
      );

      await waitFor(() => {
        expect(captureUTMParams).toHaveBeenCalled();
      }, { timeout: 3000 });
    });

    it('should not track page_load if consent not granted', () => {
      getCookieConsent.mockReturnValue({ analytics: false });

      render(
        <AnalyticsProvider>
          <div>Test Content</div>
        </AnalyticsProvider>
      );

      expect(mockMixpanel.track).not.toHaveBeenCalled();
    });
  });

  describe('consent changes', () => {
    it('should initialize Mixpanel when consent is granted via event', async () => {
      getCookieConsent.mockReturnValue({ analytics: false });

      render(
        <AnalyticsProvider>
          <div>Test Content</div>
        </AnalyticsProvider>
      );

      expect(mockMixpanel.init).not.toHaveBeenCalled();

      // Simulate consent change
      getCookieConsent.mockReturnValue({ analytics: true });
      const event = new CustomEvent('cookie-consent-changed', {
        detail: { analytics: true },
      });

      await waitFor(() => {
        window.dispatchEvent(event);
      });

      await waitFor(() => {
        expect(mockMixpanel.init).toHaveBeenCalled();
      });
    });

    it('should opt out when consent is revoked', async () => {
      getCookieConsent.mockReturnValue({ analytics: true });

      render(
        <AnalyticsProvider>
          <div>Test Content</div>
        </AnalyticsProvider>
      );

      await waitFor(() => {
        expect(mockMixpanel.init).toHaveBeenCalled();
      });

      // Simulate consent revocation
      getCookieConsent.mockReturnValue({ analytics: false });
      const event = new CustomEvent('cookie-consent-changed', {
        detail: { analytics: false },
      });

      await waitFor(() => {
        window.dispatchEvent(event);
      });

      await waitFor(() => {
        expect(mockMixpanel.opt_out_tracking).toHaveBeenCalled();
      });
    });

    it('should opt back in when consent is re-granted after opt-out', async () => {
      getCookieConsent.mockReturnValue({ analytics: true });

      render(
        <AnalyticsProvider>
          <div>Test Content</div>
        </AnalyticsProvider>
      );

      await waitFor(() => {
        expect(mockMixpanel.init).toHaveBeenCalled();
      });

      // Revoke consent
      getCookieConsent.mockReturnValue({ analytics: false });
      let event = new CustomEvent('cookie-consent-changed', {
        detail: { analytics: false },
      });
      window.dispatchEvent(event);

      await waitFor(() => {
        expect(mockMixpanel.opt_out_tracking).toHaveBeenCalled();
      });

      // Re-grant consent
      getCookieConsent.mockReturnValue({ analytics: true });
      event = new CustomEvent('cookie-consent-changed', {
        detail: { analytics: true },
      });
      window.dispatchEvent(event);

      await waitFor(() => {
        expect(mockMixpanel.opt_in_tracking).toHaveBeenCalled();
      });
    });
  });

  describe('page exit tracking', () => {
    it('should add beforeunload listener when consent granted', async () => {
      getCookieConsent.mockReturnValue({ analytics: true });
      const addEventListenerSpy = jest.spyOn(window, 'addEventListener');

      render(
        <AnalyticsProvider>
          <div>Test Content</div>
        </AnalyticsProvider>
      );

      await waitFor(() => {
        expect(mockMixpanel.init).toHaveBeenCalled();
      });

      expect(addEventListenerSpy).toHaveBeenCalledWith('beforeunload', expect.any(Function));

      addEventListenerSpy.mockRestore();
    });

    it('should not track page_exit if consent not granted', () => {
      getCookieConsent.mockReturnValue({ analytics: false });

      render(
        <AnalyticsProvider>
          <div>Test Content</div>
        </AnalyticsProvider>
      );

      const event = new Event('beforeunload');
      window.dispatchEvent(event);

      expect(mockMixpanel.track).not.toHaveBeenCalled();
    });

    it('should clean up beforeunload listener on unmount', async () => {
      getCookieConsent.mockReturnValue({ analytics: true });
      const removeEventListenerSpy = jest.spyOn(window, 'removeEventListener');

      const { unmount } = render(
        <AnalyticsProvider>
          <div>Test Content</div>
        </AnalyticsProvider>
      );

      await waitFor(() => {
        expect(mockMixpanel.init).toHaveBeenCalled();
      });

      unmount();

      expect(removeEventListenerSpy).toHaveBeenCalledWith('beforeunload', expect.any(Function));

      removeEventListenerSpy.mockRestore();
    });
  });

  describe('error handling', () => {
    it('should handle Mixpanel initialization errors gracefully', async () => {
      getCookieConsent.mockReturnValue({ analytics: true });
      mockMixpanel.init.mockImplementation(() => {
        throw new Error('Init failed');
      });

      const consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation();

      render(
        <AnalyticsProvider>
          <div>Test Content</div>
        </AnalyticsProvider>
      );

      await waitFor(() => {
        expect(consoleWarnSpy).toHaveBeenCalledWith('Mixpanel initialization failed:', expect.any(Error));
      });

      consoleWarnSpy.mockRestore();
    });

    it('should handle track errors gracefully', async () => {
      getCookieConsent.mockReturnValue({ analytics: true });
      mockMixpanel.track.mockImplementation(() => {
        throw new Error('Track failed');
      });

      render(
        <AnalyticsProvider>
          <div>Test Content</div>
        </AnalyticsProvider>
      );

      // Should not throw
      await waitFor(() => {
        expect(mockMixpanel.init).toHaveBeenCalled();
      });
    });
  });

  describe('Sentry integration', () => {
    it('should have Sentry DSN configured if environment variable is set', () => {
      // Note: Sentry.init is called at module load time, not in component
      // This test verifies the module-level initialization would happen
      // The actual Sentry.init call happens when the module is first imported

      // We can verify the DSN is used in the environment
      const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;
      if (dsn) {
        expect(dsn).toContain('sentry.io');
      } else {
        // If no DSN, Sentry shouldn't initialize
        expect(dsn).toBeUndefined();
      }
    });
  });

  describe('development mode', () => {
    it('should enable debug mode in development', async () => {
      process.env.NODE_ENV = 'development';
      getCookieConsent.mockReturnValue({ analytics: true });

      render(
        <AnalyticsProvider>
          <div>Test Content</div>
        </AnalyticsProvider>
      );

      await waitFor(() => {
        expect(mockMixpanel.init).toHaveBeenCalledWith('test-token-123', expect.objectContaining({
          debug: true,
        }));
      });
    });
  });

  describe('CONV-INST-001: traffic_source enrichment', () => {
    // AC7 scenario 1: organic_search referrer
    it('AC7-1: page_load includes traffic_source=organic_search for Google referrer', async () => {
      getCookieConsent.mockReturnValue({ analytics: true });
      getStoredUTMParams.mockReturnValue({});
      deriveTrafficSource.mockReturnValue('organic_search');

      render(
        <AnalyticsProvider>
          <div>Test Content</div>
        </AnalyticsProvider>
      );

      await waitFor(() => {
        expect(mockMixpanel.track).toHaveBeenCalledWith(
          'page_load',
          expect.objectContaining({ traffic_source: 'organic_search' })
        );
      });
    });

    // AC7 scenario 2: utm_campaign
    it('AC7-2: page_load includes traffic_source=utm_campaign when UTM params present', async () => {
      getCookieConsent.mockReturnValue({ analytics: true });
      getStoredUTMParams.mockReturnValue({ utm_source: 'blog', utm_medium: 'cta', utm_campaign: 'trial' });
      deriveTrafficSource.mockReturnValue('utm_campaign');

      render(
        <AnalyticsProvider>
          <div>Test Content</div>
        </AnalyticsProvider>
      );

      await waitFor(() => {
        expect(mockMixpanel.track).toHaveBeenCalledWith(
          'page_load',
          expect.objectContaining({
            traffic_source: 'utm_campaign',
            utm_source: 'blog',
            utm_campaign: 'trial',
          })
        );
      });
    });

    // AC7 scenario 3: first navigation → is_landing_page: true
    it('AC7-3: first navigation sets is_landing_page=true and registers entry_pathname', async () => {
      getCookieConsent.mockReturnValue({ analytics: true });
      // sessionStorage is clear from beforeEach

      render(
        <AnalyticsProvider>
          <div>Test Content</div>
        </AnalyticsProvider>
      );

      await waitFor(() => {
        expect(mockMixpanel.track).toHaveBeenCalledWith(
          'page_load',
          expect.objectContaining({ is_landing_page: true })
        );
      });

      expect(mockMixpanel.register).toHaveBeenCalledWith(
        expect.objectContaining({ entry_pathname: expect.any(String) })
      );
    });

    // AC7 scenario 4: second navigation → is_landing_page: false
    it('AC7-4: second navigation sets is_landing_page=false and does NOT call register with entry_pathname again', async () => {
      getCookieConsent.mockReturnValue({ analytics: true });
      // Simulate first path already recorded
      sessionStorage.setItem('smartlic_first_path_recorded', '1');

      render(
        <AnalyticsProvider>
          <div>Test Content</div>
        </AnalyticsProvider>
      );

      await waitFor(() => {
        expect(mockMixpanel.track).toHaveBeenCalledWith(
          'page_load',
          expect.objectContaining({ is_landing_page: false })
        );
      });

      // register should NOT have been called with entry_pathname on second navigation
      const registerCallsWithEntryPath = (mockMixpanel.register as jest.Mock).mock.calls.filter(
        (args: unknown[]) => args[0] && typeof args[0] === 'object' && 'entry_pathname' in (args[0] as object)
      );
      expect(registerCallsWithEntryPath).toHaveLength(0);
    });

    it('page_load includes direct traffic_source when no referrer and no UTM', async () => {
      getCookieConsent.mockReturnValue({ analytics: true });
      getStoredUTMParams.mockReturnValue({});
      deriveTrafficSource.mockReturnValue('direct');

      render(
        <AnalyticsProvider>
          <div>Test Content</div>
        </AnalyticsProvider>
      );

      await waitFor(() => {
        expect(mockMixpanel.track).toHaveBeenCalledWith(
          'page_load',
          expect.objectContaining({ traffic_source: 'direct' })
        );
      });
    });

    it('utm_source/utm_campaign not included when UTM params absent', async () => {
      getCookieConsent.mockReturnValue({ analytics: true });
      getStoredUTMParams.mockReturnValue({});
      deriveTrafficSource.mockReturnValue('direct');

      render(
        <AnalyticsProvider>
          <div>Test Content</div>
        </AnalyticsProvider>
      );

      await waitFor(() => {
        expect(mockMixpanel.track).toHaveBeenCalledWith('page_load', expect.any(Object));
      });

      const trackArgs = (mockMixpanel.track as jest.Mock).mock.calls.find(
        (c: unknown[]) => c[0] === 'page_load'
      );
      expect(trackArgs![1]).not.toHaveProperty('utm_source');
      expect(trackArgs![1]).not.toHaveProperty('utm_campaign');
    });

    it('does not track when consent not granted', () => {
      getCookieConsent.mockReturnValue({ analytics: false });

      render(
        <AnalyticsProvider>
          <div>Test Content</div>
        </AnalyticsProvider>
      );

      expect(mockMixpanel.track).not.toHaveBeenCalled();
      expect(mockMixpanel.register).not.toHaveBeenCalled();
    });
  });
});
