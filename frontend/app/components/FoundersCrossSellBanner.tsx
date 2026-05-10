"use client";

/**
 * Issue #1006 (COPY-CROSS-007): Cross-sell Founders banner — shared component.
 *
 * Variants:
 *  - 'planos'    : top of /planos pricing table; non-dismissable when seats ≤ 10 (real scarcity)
 *  - 'dashboard' : trial Day 3–11 dashboard cross-sell; session-scoped dismiss + 24h click anti-fatigue
 *  - 'pseo'      : programmatic SEO footer (referenced by COPY-PSEO-005)
 *
 * Hide rules (all variants):
 *  - User is already a founder (`isFounder`)
 *  - Offer sold out (seats_remaining = 0) or unavailable
 *  - Deadline passed
 *
 * Variant-specific hides:
 *  - 'planos'    : dismissed via localStorage UNLESS seats ≤ 10
 *  - 'dashboard' : trial_day < 3 OR trial_day >= 12 (Day 12+ has urgent TrialProgressBar);
 *                  session-dismissed; 24h-anti-fatigue after CTA click
 *
 * Animation: Framer Motion fade, respects prefers-reduced-motion.
 */

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { motion, useReducedMotion } from "framer-motion";
import { useFoundersAvailability } from "../../hooks/useFoundersAvailability";
import {
  trackFoundersBannerView,
  trackFoundersBannerClick,
  trackFoundersBannerDismiss,
} from "../../lib/analytics/founders";

const PLANOS_DISMISS_KEY = "founders_cross_sell_planos_dismissed";
const PLANOS_DISMISS_TTL_MS = 7 * 24 * 60 * 60 * 1000; // 7 days
const DASHBOARD_SESSION_DISMISS_KEY = "founders_cross_sell_dashboard_dismissed_session";
const DASHBOARD_CLICK_KEY = "founders_cross_sell_dashboard_clicked_at";
const DASHBOARD_CLICK_TTL_MS = 24 * 60 * 60 * 1000; // 24h
const SCARCITY_THRESHOLD = 10;

export interface FoundersCrossSellBannerProps {
  variant: "planos" | "dashboard" | "pseo";
  dismissable?: boolean;
  position?: "top" | "bottom" | "sticky";
  /** Required for 'dashboard' variant — pulled from useTrialPhase().day */
  trialDay?: number;
  /** Hide entirely if user is already a Founder */
  isFounder?: boolean;
  className?: string;
}

function isPlanosDismissed(): boolean {
  if (typeof window === "undefined") return false;
  try {
    const raw = localStorage.getItem(PLANOS_DISMISS_KEY);
    if (!raw) return false;
    const ts = parseInt(raw, 10);
    if (Number.isNaN(ts)) return false;
    return Date.now() - ts < PLANOS_DISMISS_TTL_MS;
  } catch {
    return false;
  }
}

function isDashboardSessionDismissed(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return sessionStorage.getItem(DASHBOARD_SESSION_DISMISS_KEY) === "1";
  } catch {
    return false;
  }
}

function isDashboardClickAntiFatigueActive(): boolean {
  if (typeof window === "undefined") return false;
  try {
    const raw = localStorage.getItem(DASHBOARD_CLICK_KEY);
    if (!raw) return false;
    const ts = parseInt(raw, 10);
    if (Number.isNaN(ts)) return false;
    return Date.now() - ts < DASHBOARD_CLICK_TTL_MS;
  } catch {
    return false;
  }
}

export function FoundersCrossSellBanner({
  variant,
  dismissable = true,
  position = "top",
  trialDay,
  isFounder = false,
  className = "",
}: FoundersCrossSellBannerProps) {
  const { data: availability, isLoading, error } = useFoundersAvailability();
  const reducedMotion = useReducedMotion();

  // Client-side dismiss state hydration
  const [dismissed, setDismissed] = useState(true);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    if (variant === "planos") {
      setDismissed(isPlanosDismissed());
    } else if (variant === "dashboard") {
      setDismissed(isDashboardSessionDismissed() || isDashboardClickAntiFatigueActive());
    } else {
      // pseo: never dismissable in storage — always render if eligible
      setDismissed(false);
    }
    setHydrated(true);
  }, [variant]);

  const seatsRemaining = availability?.seats_remaining ?? null;
  const deadlinePassed = useMemo(() => {
    if (!availability?.deadline_at) return false;
    try {
      return new Date(availability.deadline_at) < new Date();
    } catch {
      return false;
    }
  }, [availability?.deadline_at]);

  // Variant-specific eligibility (computed before render to gate analytics)
  const variantEligible = useMemo(() => {
    if (variant === "dashboard") {
      if (typeof trialDay !== "number") return false;
      if (trialDay < 3) return false;
      if (trialDay >= 12) return false;
    }
    return true;
  }, [variant, trialDay]);

  // Effective dismissable: planos becomes non-dismissable under scarcity
  const effectiveDismissable = useMemo(() => {
    if (!dismissable) return false;
    if (variant === "planos" && seatsRemaining !== null && seatsRemaining <= SCARCITY_THRESHOLD) {
      return false;
    }
    return true;
  }, [dismissable, variant, seatsRemaining]);

  // Fire view analytics once when eligible
  const visibilityKey = `${hydrated}-${dismissed}-${variantEligible}-${isFounder}-${availability?.available}-${seatsRemaining}-${deadlinePassed}`;
  useEffect(() => {
    if (!hydrated || dismissed || !variantEligible || isFounder) return;
    if (!availability || !availability.available) return;
    if (seatsRemaining === 0 || deadlinePassed) return;
    trackFoundersBannerView({
      route: variant,
      dismissed_count: undefined,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visibilityKey]);

  const handleDismiss = () => {
    try {
      if (variant === "planos") {
        localStorage.setItem(PLANOS_DISMISS_KEY, String(Date.now()));
      } else if (variant === "dashboard") {
        sessionStorage.setItem(DASHBOARD_SESSION_DISMISS_KEY, "1");
      }
    } catch {
      // storage unavailable — dismiss in-memory only
    }
    setDismissed(true);
    trackFoundersBannerDismiss({ route: variant });
  };

  const handleCtaClick = () => {
    try {
      if (variant === "dashboard") {
        localStorage.setItem(DASHBOARD_CLICK_KEY, String(Date.now()));
      }
    } catch {
      // no-op
    }
    trackFoundersBannerClick({ route: variant });
  };

  // Render gates
  if (!hydrated) return null;
  if (dismissed) return null;
  if (isFounder) return null;
  if (!variantEligible) return null;

  // Loading: render nothing rather than "..." (per AC: "Loading state graceful")
  if (isLoading && !availability) return null;

  // Hard hides from API state
  if (availability) {
    if (!availability.available) return null;
    if (availability.seats_remaining === 0) return null;
    if (deadlinePassed) return null;
  } else if (error) {
    // Fallback path: API failed — render conservative copy without number
  } else {
    return null;
  }

  // Resolve copy by variant (with API fallback)
  const seats = seatsRemaining;
  const hasSeats = typeof seats === "number" && seats > 0;
  const fallback = !availability && !!error;

  let bodyText: React.ReactNode;
  let ctaLabel: string;
  if (variant === "planos") {
    bodyText = fallback ? (
      <>
        <strong>Antes de escolher um plano mensal:</strong> existem vagas vitalícias por R$997. Pague uma vez, use pra sempre. Encerra 30/06.
      </>
    ) : (
      <>
        <strong>Antes de escolher um plano mensal: existem {seats} vagas vitalícias por R$997.</strong>{" "}
        Pague uma vez, use pra sempre. Encerra 30/06.
      </>
    );
    ctaLabel = "Ver Plano Fundadores →";
  } else if (variant === "dashboard") {
    bodyText = fallback || !hasSeats ? (
      <>Já está vendo valor? Pague R$997 uma vez e nunca mais veja boleto do SmartLic.</>
    ) : (
      <>
        Já está vendo valor? Pague R$997 uma vez e nunca mais veja boleto do SmartLic. {seats} vagas restantes.
      </>
    );
    ctaLabel = "Pegar minha vaga R$997 →";
  } else {
    // pseo
    bodyText = fallback || !hasSeats ? (
      <>Plano Fundadores: acesso vitalício por R$997. Vagas limitadas, encerra 30/06.</>
    ) : (
      <>Plano Fundadores: {seats} vagas vitalícias por R$997. Encerra 30/06.</>
    );
    ctaLabel = "Saiba mais →";
  }

  const positionClass =
    position === "sticky"
      ? "sticky top-0 z-30"
      : position === "bottom"
        ? ""
        : "";

  const animProps = reducedMotion
    ? { initial: false, animate: { opacity: 1 } }
    : { initial: { opacity: 0, y: -4 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.25 } };

  return (
    <motion.div
      role="status"
      aria-live="polite"
      data-testid={`founders-cross-sell-banner-${variant}`}
      data-variant={variant}
      className={`w-full bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-lg px-4 py-3 ${positionClass} ${className}`}
      {...animProps}
    >
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <p className="text-sm text-amber-900 dark:text-amber-100 leading-relaxed">{bodyText}</p>
        <div className="flex items-center gap-2 flex-shrink-0 self-stretch sm:self-auto">
          <Link
            href="/fundadores"
            onClick={handleCtaClick}
            data-testid={`founders-cross-sell-cta-${variant}`}
            className="inline-flex items-center justify-center min-h-[44px] px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white text-sm font-medium rounded-md transition-colors whitespace-nowrap focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 focus-visible:ring-offset-2"
          >
            {ctaLabel}
          </Link>
          {effectiveDismissable && (
            <button
              type="button"
              onClick={handleDismiss}
              aria-label="Fechar banner Plano Fundadores"
              data-testid={`founders-cross-sell-dismiss-${variant}`}
              className="inline-flex items-center justify-center min-w-[44px] min-h-[44px] p-2 text-amber-700 hover:text-amber-900 dark:text-amber-300 dark:hover:text-amber-100 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 focus-visible:ring-offset-2 rounded-md"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-4 w-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
                aria-hidden="true"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      </div>
    </motion.div>
  );
}

export default FoundersCrossSellBanner;
