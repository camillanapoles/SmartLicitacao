/**
 * REPO-018: Typed Mixpanel analytics events for reposicionamento tracking.
 *
 * Provides TypeScript event types and standalone tracking functions for the
 * 4 standardised Phase 0 funnel events (cta_click, form_started,
 * form_submitted, lead_captured). Required by REPO-019 and REPO-022.
 *
 * All functions respect LGPD cookie consent (same gate as useAnalytics.ts).
 * All functions are SSR-safe: they return early when window is unavailable.
 */

import mixpanel from 'mixpanel-browser';
import { getCookieConsent } from '../app/components/CookieConsentBanner';

// ---------------------------------------------------------------------------
// Event payload types
// ---------------------------------------------------------------------------

export type CTAClickEvent = {
  label: string;
  source: string;
  destination: string;
  cta_type: 'self-service' | 'consultive';
};

export type FormStartedEvent = {
  form_name: string;
  source: string;
};

export type FormSubmittedEvent = {
  form_name: string;
  source: string;
  modalidade?: 'radar' | 'report' | 'intel' | 'nao_sei';
};

export type LeadCapturedEvent = {
  source: string;
  modalidade?: string;
  form_name?: string;
};

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function isTrackingEnabled(): boolean {
  if (typeof window === 'undefined') return false;
  if (!process.env.NEXT_PUBLIC_MIXPANEL_TOKEN) return false;
  const consent = getCookieConsent();
  return consent?.analytics === true;
}

function safeTrack(eventName: string, properties: Record<string, unknown>): void {
  if (!isTrackingEnabled()) return;
  try {
    mixpanel.track(eventName, {
      ...properties,
      timestamp: new Date().toISOString(),
      environment: process.env.NODE_ENV || 'development',
    });
  } catch (error) {
    console.warn('Analytics tracking failed:', error);
  }
}

// ---------------------------------------------------------------------------
// Standalone tracking functions
// ---------------------------------------------------------------------------

/**
 * Track a CTA button click.
 * Event name: 'cta_click'
 */
export function trackCTAClick(event: CTAClickEvent): void {
  safeTrack('cta_click', event as unknown as Record<string, unknown>);
}

/**
 * Track when a user starts interacting with a form (first field focus / open).
 * Event name: 'form_started'
 */
export function trackFormStarted(event: FormStartedEvent): void {
  safeTrack('form_started', event as unknown as Record<string, unknown>);
}

/**
 * Track a successful form submission.
 * Event name: 'form_submitted'
 */
export function trackFormSubmitted(event: FormSubmittedEvent): void {
  safeTrack('form_submitted', event as unknown as Record<string, unknown>);
}

/**
 * Track when a lead is captured (e.g., after form submission confirms an
 * email address or intent signal).
 * Event name: 'lead_captured'
 */
export function trackLeadCaptured(event: LeadCapturedEvent): void {
  safeTrack('lead_captured', event as unknown as Record<string, unknown>);
}
