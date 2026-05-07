/**
 * Typed Mixpanel analytics wrappers for all founders-related events.
 *
 * All functions are safe to call unconditionally — they never throw even if
 * Mixpanel is not initialized (SSR, consent not given, token missing).
 *
 * Import pattern:
 *   import { trackFoundersPageView } from '@/lib/analytics/founders';
 */

import mixpanel from 'mixpanel-browser';

// Safe wrapper — never throws even if Mixpanel not initialized
function safeTrack(event: string, props?: Record<string, unknown>): void {
  try {
    mixpanel.track(event, props);
  } catch {
    // Mixpanel not initialized (SSR or consent not given)
  }
}

// ============================================================
// Page & Banner Events
// ============================================================

export function trackFoundersPageView(props: {
  utm_source?: string | null;
  utm_medium?: string | null;
  utm_campaign?: string | null;
  src?: string | null;
  seats_remaining?: number;
  deadline_at?: string | null;
}): void {
  safeTrack('founders_page_view', props);
}

export function trackFoundersBannerView(props: {
  route: string;
  dismissed_count?: number;
}): void {
  safeTrack('founders_banner_view', props);
}

export function trackFoundersBannerClick(props: { route: string }): void {
  safeTrack('founders_banner_click', props);
}

export function trackFoundersBannerDismiss(props: { route: string }): void {
  safeTrack('founders_banner_dismiss', props);
}

// ============================================================
// pSEO Ribbon Events
// ============================================================

export function trackFoundersRibbonView(props: {
  route: string;
  variant: string;
}): void {
  safeTrack('founders_ribbon_view', props);
}

export function trackFoundersRibbonClick(props: {
  route: string;
  variant: string;
}): void {
  safeTrack('founders_ribbon_click', props);
}

// ============================================================
// Checkout Events
// ============================================================

export function trackFoundersCtaClick(props: {
  cta_location: string;
  src?: string | null;
}): void {
  safeTrack('founders_cta_click', props);
}

export function trackFoundersCheckoutStart(props: {
  email_provided: boolean;
  src?: string | null;
}): void {
  safeTrack('founders_checkout_start', props);
}

export function trackFoundersPseoConversion(props: {
  from_route: string;
  variant: string;
}): void {
  safeTrack('founders_pseo_conversion', props);
}
