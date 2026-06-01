/**
 * CONV-013: Typed Mixpanel analytics wrappers for WhatsApp CTA events.
 *
 * Two events:
 *  - whatsapp_cta_viewed  — fired when the CTA enters the viewport
 *  - whatsapp_cta_clicked — fired when the user clicks the CTA
 *
 * Each carries the source template, entity_id, setor, uf, and device type
 * for downstream conversion funnel analysis.
 *
 * All functions are SSR-safe: they return early when window is unavailable.
 * All functions never throw — errors are swallowed silently.
 */

import mixpanel from 'mixpanel-browser';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface WhatsAppCTAEventProperties {
  /** Source template identifier (e.g. 'fornecedor_page', 'orgao_page') */
  source_template: string;
  /** Entity identifier (CNPJ, slug, sector, etc.) */
  entity_id?: string;
  /** Sector slug (e.g. 'pavimentacao-asfaltica') */
  setor?: string;
  /** Two-letter UF code (e.g. 'SC') */
  uf?: string;
  /** Device type: 'mobile' or 'desktop' */
  device?: string;
  /** Allow extra properties */
  [key: string]: unknown;
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function isTrackingEnabled(): boolean {
  if (typeof window === 'undefined') return false;
  if (!process.env.NEXT_PUBLIC_MIXPANEL_TOKEN) return false;
  return true;
}

function safeTrack(eventName: string, properties: Record<string, unknown>): void {
  if (!isTrackingEnabled()) return;
  try {
    mixpanel.track(eventName, {
      ...properties,
      timestamp: new Date().toISOString(),
      environment: process.env.NODE_ENV || 'development',
    });
  } catch {
    // Mixpanel not initialized — swallow silently
  }
}

function detectDevice(): string {
  if (typeof window === 'undefined') return 'unknown';
  return /Mobi|Android|iPhone|iPad|iPod/i.test(navigator.userAgent) ? 'mobile' : 'desktop';
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Track when the WhatsApp CTA becomes visible in the viewport.
 *
 * @param props - Event properties (source_template, entity_id, setor, uf)
 */
export function trackWhatsAppCTAViewed(props: WhatsAppCTAEventProperties): void {
  safeTrack('whatsapp_cta_viewed', {
    ...props,
    device: detectDevice(),
  });
}

/**
 * Track when the user clicks the WhatsApp CTA.
 *
 * @param props - Event properties (source_template, entity_id, setor, uf)
 */
export function trackWhatsAppCTAClicked(props: WhatsAppCTAEventProperties): void {
  safeTrack('whatsapp_cta_clicked', {
    ...props,
    device: detectDevice(),
  });
}
