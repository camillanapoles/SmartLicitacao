/**
 * Typed Mixpanel analytics wrappers for pSEO micro-conversion events.
 * PSEO-CONV-001 (#884) / CONV-009 (#1318).
 *
 * All functions respect LGPD cookie consent (same gate as analytics-events.ts).
 * All functions are SSR-safe: they return early when window is unavailable.
 * All functions never throw — errors are swallowed silently.
 *
 * CONV-009 alignment: Added pseo_contrato_viewed event (9th event) and
 * standardized ConversionContext params (entity_id, setor, uf).
 */

import mixpanel from 'mixpanel-browser';
import { getCookieConsent } from '@/app/components/CookieConsentBanner';
import type { ConversionContext } from './conversion-tracker';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type PseoEventName =
  | 'pseo_search_performed'
  | 'pseo_edital_viewed'
  | 'pseo_contrato_viewed'
  | 'pseo_alert_signup'
  | 'pseo_supplier_viewed'
  | 'pseo_organ_viewed'
  | 'pseo_calculator_result'
  | 'pseo_lead_captured'
  | 'pseo_checkout_click'
  // CONV-009b (#1325): Scroll depth and time-on-page tracking
  | 'pseo_scroll_depth'
  | 'pseo_engagement'
  | 'pseo_preview_cta_click'
  // CONV-014: Alert system tracking events
  | 'alert_created'
  | 'alert_matched'
  | 'alert_upgrade_cta_click'
  // CONV-004 (#1313): Aha moment panel events
  | 'aha_panel_view'
  | 'aha_unlock_start'
  | 'aha_unlock_complete'
  // CONV-001/CONV-004 (#1310/#1313): Shared value prop events
  | 'value_prop_view'
  | 'value_cta_click';

export type PseoSourceTemplate =
  | 'fornecedor_page'
  | 'orgao_page'
  | 'contrato_page'
  | 'cnpj_page'
  | 'blog_hub'
  | 'perguntas'
  | 'licitacoes_hub'
  | 'calculadora_reajuste'
  | 'alerta_fornecedor_page'
  | 'alerta_orgao_page'
  | 'alerta_setor_page'
  | 'alerta_municipio_page';

export type PseoEventProperties = ConversionContext & {
  source_template: PseoSourceTemplate;
  page_url?: string;
  [key: string]: unknown;
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

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Track a pSEO micro-conversion event.
 *
 * Requires LGPD consent and Mixpanel token. SSR-safe.
 * Carries standardized ConversionContext params (entity_id, setor, uf)
 * for downstream attribution in dashboards.
 */
export function trackPseoEvent(
  event: PseoEventName,
  properties: PseoEventProperties,
): void {
  if (!isTrackingEnabled()) return;
  try {
    mixpanel.track(event, {
      ...properties,
      timestamp: new Date().toISOString(),
      environment: process.env.NODE_ENV || 'development',
    });
  } catch {
    // Mixpanel not initialized or consent not given
  }
}
