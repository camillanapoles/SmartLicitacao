"use client";

/**
 * CONV-013: WhatsApp CTA component for pSEO pages.
 *
 * Renders a WhatsApp button that opens a direct conversation with the founder
 * (+55 48 98834-4559) with a pre-filled contextual message.
 *
 * Two variants:
 *  - 'floating' : Fixed button at bottom-right corner (mobile-first)
 *  - 'inline'   : Banner-style CTA below the first data block (desktop)
 *
 * Tracking (Mixpanel):
 *  - whatsapp_cta_viewed  — fires when the CTA enters the viewport
 *  - whatsapp_cta_clicked — fires on click
 *
 * Usage:
 *   <WhatsAppCTA
 *     source="fornecedor_page"
 *     entity="Empresa XYZ Ltda"
 *     entityId="12345678000199"
 *     setor="pavimentacao-asfaltica"
 *     uf="SC"
 *   />
 */

import { useEffect, useRef, useCallback } from "react";
import Image from "next/image";
import { motion } from "framer-motion";
import { buildWhatsAppUrl, getWhatsAppCtaLabel, WhatsAppSourceTemplate, WhatsAppContext } from "@/lib/whatsapp-messages";
import { trackWhatsAppCTAViewed, trackWhatsAppCTAClicked } from "@/lib/analytics/whatsapp";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type CTAVariant = "floating" | "inline";

export interface WhatsAppCTAProps {
  /** Source template identifier (e.g. 'fornecedor_page', 'orgao_page') */
  source: WhatsAppSourceTemplate;
  /** Entity display name (e.g. company name, orgao name) */
  entity?: string;
  /** Entity identifier (CNPJ, slug, etc.) */
  entityId?: string;
  /** Sector slug */
  setor?: string;
  /** Two-letter UF code */
  uf?: string;
  /** Visual variant — 'floating' (mobile bottom-right) or 'inline' (desktop contextual) */
  variant?: CTAVariant;
  /** Additional classes for the wrapper (inline only) */
  className?: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Device detection — mobile below this breakpoint. Tailwind `md:` = 768px */
const MOBILE_BREAKPOINT_PX = 768;

// ---------------------------------------------------------------------------
// Inline variant
// ---------------------------------------------------------------------------

function InlineWhatsAppCTA({
  source,
  entity,
  entityId,
  setor,
  uf,
  className = "",
}: WhatsAppCTAProps) {
  const sectionRef = useRef<HTMLElement>(null);
  const viewTracked = useRef(false);

  const whatsappContext: WhatsAppContext = { entity, setor, uf };
  const whatsappUrl = buildWhatsAppUrl(source, whatsappContext);

  // Track view on mount (once)
  useEffect(() => {
    if (viewTracked.current) return;
    viewTracked.current = true;
    trackWhatsAppCTAViewed({
      source_template: source,
      entity_id: entityId,
      setor,
      uf,
    });
  }, [source, entityId, setor, uf]);

  const handleClick = useCallback(() => {
    trackWhatsAppCTAClicked({
      source_template: source,
      entity_id: entityId,
      setor,
      uf,
    });
  }, [source, entityId, setor, uf]);

  return (
    <section
      ref={sectionRef}
      aria-label="Falar com especialista no WhatsApp"
      data-testid={`whatsapp-cta-inline`}
      className={`rounded-xl border border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-950/30 p-5 sm:p-6 ${className}`}
    >
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex items-start gap-3 flex-1">
          <div className="shrink-0 w-10 h-10 rounded-full bg-green-500 flex items-center justify-center mt-0.5">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="white"
              className="w-5 h-5"
              aria-hidden="true"
            >
              <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.095 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
            </svg>
          </div>
          <div>
            <p className="text-sm font-semibold text-gray-900 dark:text-white">
              {getWhatsAppCtaLabel()}
            </p>
            <p className="text-xs text-gray-600 dark:text-gray-400 mt-0.5">
              Tire dúvidas diretamente com o founder. Resposta em até 1h em horário comercial.
            </p>
          </div>
        </div>
        <a
          href={whatsappUrl}
          target="_blank"
          rel="noopener noreferrer"
          onClick={handleClick}
          data-testid="whatsapp-cta-inline-link"
          className="
            inline-flex items-center justify-center gap-2
            min-h-[44px] px-5 py-2.5
            bg-green-600 hover:bg-green-700
            text-white text-sm font-semibold
            rounded-lg transition-colors
            focus:outline-none focus-visible:ring-2 focus-visible:ring-green-500 focus-visible:ring-offset-2
            whitespace-nowrap shrink-0
          "
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="currentColor"
            className="w-4 h-4"
            aria-hidden="true"
          >
            <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.095 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
          </svg>
          Falar agora
        </a>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Floating variant (mobile bottom-right)
// ---------------------------------------------------------------------------

function FloatingWhatsAppCTA({
  source,
  entity,
  entityId,
  setor,
  uf,
}: WhatsAppCTAProps) {
  const buttonRef = useRef<HTMLAnchorElement>(null);
  const viewTracked = useRef(false);

  const whatsappContext: WhatsAppContext = { entity, setor, uf };
  const whatsappUrl = buildWhatsAppUrl(source, whatsappContext);

  // Track view on mount (once)
  useEffect(() => {
    if (viewTracked.current) return;
    viewTracked.current = true;
    trackWhatsAppCTAViewed({
      source_template: source,
      entity_id: entityId,
      setor,
      uf,
    });
  }, [source, entityId, setor, uf]);

  const handleClick = useCallback(() => {
    trackWhatsAppCTAClicked({
      source_template: source,
      entity_id: entityId,
      setor,
      uf,
    });
  }, [source, entityId, setor, uf]);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay: 0.5, duration: 0.3 }}
      className="fixed bottom-6 right-4 z-50 md:hidden"
    >
      <a
        ref={buttonRef}
        href={whatsappUrl}
        target="_blank"
        rel="noopener noreferrer"
        onClick={handleClick}
        data-testid="whatsapp-cta-floating"
        aria-label="Falar com especialista no WhatsApp"
        className="
          flex items-center gap-2
          min-h-[48px] px-4 py-2.5
          bg-green-600 hover:bg-green-700
          text-white text-sm font-semibold
          rounded-full shadow-lg
          transition-all duration-200
          hover:shadow-xl hover:scale-105
          focus:outline-none focus-visible:ring-2 focus-visible:ring-green-500 focus-visible:ring-offset-2
        "
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="currentColor"
          className="w-5 h-5 shrink-0"
          aria-hidden="true"
        >
          <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.095 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
        </svg>
        <span className="whitespace-nowrap">{getWhatsAppCtaLabel()}</span>
      </a>
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

/**
 * WhatsApp CTA component with two variants:
 * - `floating`: Fixed button at bottom-right (mobile only, hidden on md+)
 * - `inline`: Contextual banner (shown on desktop, or always depending on usage)
 *
 * Default behavior (no variant specified):
 * - Floating on mobile (< 768px)
 * - Inline on desktop (>= 768px)
 *
 * When explicitly set:
 * - `variant="floating"`: renders ONLY the floating button (hidden on md+)
 * - `variant="inline"`: renders ONLY the inline banner
 *
 * For pages that want both: render with default (no variant) or render both explicitly.
 */
export default function WhatsAppCTA(props: WhatsAppCTAProps) {
  const { variant } = props;

  // If variant explicitly set, render just that one
  if (variant === "floating") {
    return <FloatingWhatsAppCTA {...props} />;
  }
  if (variant === "inline") {
    return <InlineWhatsAppCTA {...props} />;
  }

  // Default: both — floating on mobile, inline on desktop
  return (
    <>
      <FloatingWhatsAppCTA {...props} />
      <div className="hidden md:block">
        <InlineWhatsAppCTA {...props} />
      </div>
    </>
  );
}
