"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useUser } from "../../contexts/UserContext";

/**
 * BIZ-FOUND-002 / Issue #787: Global founders top banner.
 *
 * Shown to non-founders / non-paying customers when the founding offer is
 * still available (seats_remaining > 0, deadline not passed).
 *
 * Hidden when:
 * - seats_remaining === 0 or available === false
 * - deadline passed
 * - user has an active (non-trial) subscription
 * - localStorage 'founders_banner_dismissed' is set with TTL < 7 days
 *
 * No countdown timer (per spec).
 * Fires Mixpanel events: founders_banner_view (mount), founders_banner_click (CTA).
 */

const DISMISS_KEY = "founders_banner_dismissed";
const DISMISS_TTL_MS = 7 * 24 * 60 * 60 * 1000; // 7 days

interface FoundingAvailability {
  available: boolean;
  seats_remaining: number;
  deadline_at: string | null;
}

function isDismissed(): boolean {
  if (typeof window === "undefined") return true;
  try {
    const raw = localStorage.getItem(DISMISS_KEY);
    if (!raw) return false;
    const ts = parseInt(raw, 10);
    if (isNaN(ts)) return false;
    return Date.now() - ts < DISMISS_TTL_MS;
  } catch {
    return false;
  }
}

export function FoundersTopBanner() {
  const { planInfo, planLoading } = useUser();
  const [availability, setAvailability] = useState<FoundingAvailability | null>(null);
  const [dismissed, setDismissed] = useState(true); // default hidden until checked
  const [loaded, setLoaded] = useState(false);

  // Check localStorage on mount (client-side only)
  useEffect(() => {
    setDismissed(isDismissed());
    setLoaded(true);
  }, []);

  // Fetch availability only when we know the user is a candidate
  useEffect(() => {
    if (!loaded) return;
    if (dismissed) return;
    if (planLoading) return;

    // Active (non-trial) subscribers should never see this banner
    const isActivePaying =
      planInfo?.subscription_status === "active" && !planInfo?.trial_expires_at;
    if (isActivePaying) return;

    let cancelled = false;
    fetch("/api/founding/availability")
      .then((res) => (res.ok ? res.json() : null))
      .then((data: FoundingAvailability | null) => {
        if (!cancelled && data) setAvailability(data);
      })
      .catch(() => {
        // Fail silently — banner simply won't show
      });

    return () => {
      cancelled = true;
    };
  }, [loaded, dismissed, planLoading, planInfo?.subscription_status, planInfo?.trial_expires_at]);

  // Fire view event once after banner becomes visible
  useEffect(() => {
    if (!availability || !loaded || dismissed) return;
    if (!availability.available || availability.seats_remaining <= 0) return;
    if (planInfo?.subscription_status === "active" && !planInfo?.trial_expires_at) return;

    try {
      if (
        typeof window !== "undefined" &&
        window.mixpanel &&
        typeof window.mixpanel.track === "function"
      ) {
        window.mixpanel.track("founders_banner_view", {
          seats_remaining: availability.seats_remaining,
        });
      }
    } catch {
      // Mixpanel not loaded — no-op
    }
  }, [availability, loaded, dismissed, planInfo?.subscription_status, planInfo?.trial_expires_at]);

  const handleDismiss = () => {
    try {
      localStorage.setItem(DISMISS_KEY, String(Date.now()));
    } catch {
      // localStorage unavailable — dismiss in-memory only
    }
    setDismissed(true);
  };

  const handleCTAClick = () => {
    try {
      if (
        typeof window !== "undefined" &&
        window.mixpanel &&
        typeof window.mixpanel.track === "function"
      ) {
        window.mixpanel.track("founders_banner_click", {
          seats_remaining: availability?.seats_remaining,
        });
      }
    } catch {
      // no-op
    }
  };

  // Guard: don't render until client-side checks are done
  if (!loaded) return null;
  if (dismissed) return null;
  if (planLoading) return null;

  // Hide for active paying subscribers
  const isActivePaying =
    planInfo?.subscription_status === "active" && !planInfo?.trial_expires_at;
  if (isActivePaying) return null;

  // Hide if availability data not loaded yet or offer unavailable
  if (!availability) return null;
  if (!availability.available) return null;
  if (availability.seats_remaining <= 0) return null;

  // Hide if deadline has passed
  if (availability.deadline_at) {
    const deadline = new Date(availability.deadline_at);
    if (deadline < new Date()) return null;
  }

  return (
    <div
      role="status"
      aria-live="polite"
      data-testid="founders-top-banner"
      className="w-full bg-amber-50 border-b border-amber-200 dark:bg-amber-950/30 dark:border-amber-800 px-4 py-2.5"
    >
      <div className="max-w-5xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2">
        <p className="text-sm font-medium text-amber-900 dark:text-amber-100 text-center sm:text-left">
          Plano Fundadores: acesso vitalício por R$997 — vagas limitadas até 30/06
        </p>
        <div className="flex items-center gap-3 flex-shrink-0">
          <Link
            href="/fundadores"
            onClick={handleCTAClick}
            className="inline-flex items-center px-4 py-1.5 bg-amber-600 hover:bg-amber-700 text-white text-sm font-medium rounded-md transition-colors whitespace-nowrap"
          >
            Saiba mais
          </Link>
          <button
            type="button"
            aria-label="Fechar banner Fundadores"
            onClick={handleDismiss}
            className="p-1 text-amber-700 hover:text-amber-900 dark:text-amber-300 dark:hover:text-amber-100 transition-colors"
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
        </div>
      </div>
    </div>
  );
}
