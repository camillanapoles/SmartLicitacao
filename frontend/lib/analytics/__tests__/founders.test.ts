/**
 * Tests for founders analytics wrappers (lib/analytics/founders.ts).
 *
 * Verifies:
 * - safeTrack swallows errors from Mixpanel (never throws)
 * - Each exported event wrapper calls mixpanel.track with the correct event
 *   name and forwards props unchanged
 */

import mixpanel from 'mixpanel-browser';

jest.mock('mixpanel-browser', () => ({
  __esModule: true,
  default: { track: jest.fn() },
}));

import {
  trackFoundersPageView,
  trackFoundersBannerView,
  trackFoundersBannerClick,
  trackFoundersBannerDismiss,
  trackFoundersRibbonView,
  trackFoundersRibbonClick,
  trackFoundersCtaClick,
  trackFoundersCheckoutStart,
  trackFoundersPseoConversion,
} from '../founders';

const mockTrack = mixpanel.track as jest.Mock;

beforeEach(() => {
  mockTrack.mockClear();
});

// ---------------------------------------------------------------------------
// safeTrack — error swallowing
// ---------------------------------------------------------------------------

describe('safeTrack error swallowing', () => {
  it('does not throw when mixpanel.track throws', () => {
    mockTrack.mockImplementationOnce(() => {
      throw new Error('Mixpanel not initialized');
    });

    expect(() =>
      trackFoundersPageView({ utm_source: null, utm_medium: null, utm_campaign: null })
    ).not.toThrow();
  });

  it('does not throw when mixpanel.track throws a non-Error value', () => {
    mockTrack.mockImplementationOnce(() => {
      // eslint-disable-next-line @typescript-eslint/no-throw-literal
      throw 'consent not given';
    });

    expect(() => trackFoundersCtaClick({ cta_location: 'hero' })).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// Individual event wrappers
// ---------------------------------------------------------------------------

describe('trackFoundersPageView', () => {
  it('calls mixpanel.track with founders_page_view and forwarded props', () => {
    const props = {
      utm_source: 'google',
      utm_medium: 'cpc',
      utm_campaign: 'founders-2026',
      src: 'banner',
      seats_remaining: 10,
      deadline_at: '2026-05-30T23:59:59-03:00',
    };
    trackFoundersPageView(props);
    expect(mockTrack).toHaveBeenCalledWith('founders_page_view', props);
  });

  it('accepts nullish optional props', () => {
    trackFoundersPageView({ utm_source: null, utm_medium: null, utm_campaign: null });
    expect(mockTrack).toHaveBeenCalledWith('founders_page_view', {
      utm_source: null,
      utm_medium: null,
      utm_campaign: null,
    });
  });
});

describe('trackFoundersBannerView', () => {
  it('calls mixpanel.track with founders_banner_view', () => {
    trackFoundersBannerView({ route: '/buscar', dismissed_count: 2 });
    expect(mockTrack).toHaveBeenCalledWith('founders_banner_view', {
      route: '/buscar',
      dismissed_count: 2,
    });
  });
});

describe('trackFoundersBannerClick', () => {
  it('calls mixpanel.track with founders_banner_click', () => {
    trackFoundersBannerClick({ route: '/planos' });
    expect(mockTrack).toHaveBeenCalledWith('founders_banner_click', { route: '/planos' });
  });
});

describe('trackFoundersBannerDismiss', () => {
  it('calls mixpanel.track with founders_banner_dismiss', () => {
    trackFoundersBannerDismiss({ route: '/dashboard' });
    expect(mockTrack).toHaveBeenCalledWith('founders_banner_dismiss', { route: '/dashboard' });
  });
});

describe('trackFoundersRibbonView', () => {
  it('calls mixpanel.track with founders_ribbon_view and variant', () => {
    trackFoundersRibbonView({ route: '/licitacoes/tecnologia', variant: 'compact' });
    expect(mockTrack).toHaveBeenCalledWith('founders_ribbon_view', {
      route: '/licitacoes/tecnologia',
      variant: 'compact',
    });
  });
});

describe('trackFoundersRibbonClick', () => {
  it('calls mixpanel.track with founders_ribbon_click and variant', () => {
    trackFoundersRibbonClick({ route: '/observatorio/setor-ti', variant: 'default' });
    expect(mockTrack).toHaveBeenCalledWith('founders_ribbon_click', {
      route: '/observatorio/setor-ti',
      variant: 'default',
    });
  });
});

describe('trackFoundersCtaClick', () => {
  it('calls mixpanel.track with founders_cta_click and cta_location', () => {
    trackFoundersCtaClick({ cta_location: 'pricing_table', src: 'email' });
    expect(mockTrack).toHaveBeenCalledWith('founders_cta_click', {
      cta_location: 'pricing_table',
      src: 'email',
    });
  });
});

describe('trackFoundersCheckoutStart', () => {
  it('calls mixpanel.track with founders_checkout_start', () => {
    trackFoundersCheckoutStart({ email_provided: true, src: 'ribbon' });
    expect(mockTrack).toHaveBeenCalledWith('founders_checkout_start', {
      email_provided: true,
      src: 'ribbon',
    });
  });
});

describe('trackFoundersPseoConversion', () => {
  it('calls mixpanel.track with founders_pseo_conversion', () => {
    trackFoundersPseoConversion({ from_route: '/contratos/tecnologia/SP', variant: 'default' });
    expect(mockTrack).toHaveBeenCalledWith('founders_pseo_conversion', {
      from_route: '/contratos/tecnologia/SP',
      variant: 'default',
    });
  });
});
