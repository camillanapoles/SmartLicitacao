"use client";

import { useMemo } from "react";
import Link from "next/link";

interface TrialCountdownProps {
  daysRemaining: number;
  className?: string;
}

/**
 * Color-coded countdown badge for active trial.
 * STORY-264 AC7 + Issue #620: Badge with feature-named urgency by tier.
 * Colors: green (>=5), yellow (3-4), red (1-2)
 *
 * Loss-aversion copy (Kahneman): names features at risk instead of generic
 * "acesso completo" so users react to concrete loss, not abstract access.
 */
export function TrialCountdown({ daysRemaining, className = "" }: TrialCountdownProps) {
  const { bgColor, textColor, borderColor, dotColor } = useMemo(() => {
    if (daysRemaining >= 5) {
      return {
        bgColor: "bg-emerald-50 dark:bg-emerald-900/20",
        textColor: "text-emerald-700 dark:text-emerald-300",
        borderColor: "border-emerald-200 dark:border-emerald-800",
        dotColor: "bg-emerald-500",
      };
    }
    if (daysRemaining >= 3) {
      return {
        bgColor: "bg-amber-50 dark:bg-amber-900/20",
        textColor: "text-amber-700 dark:text-amber-300",
        borderColor: "border-amber-200 dark:border-amber-800",
        dotColor: "bg-amber-500",
      };
    }
    return {
      bgColor: "bg-red-50 dark:bg-red-900/20",
      textColor: "text-red-700 dark:text-red-300",
      borderColor: "border-red-200 dark:border-red-800",
      dotColor: "bg-red-500",
    };
  }, [daysRemaining]);

  if (daysRemaining <= 0) return null;

  // Pill text varies by tier — names the feature at risk (loss aversion)
  const pillText =
    daysRemaining >= 5
      ? `${daysRemaining} dias · Pipeline + Excel`
      : daysRemaining >= 3
        ? `${daysRemaining} dias · alertas expiram em breve`
        : daysRemaining === 1
          ? "Última 1 dia · Excel + alertas expiram"
          : `Últimas ${daysRemaining} dias · Excel + alertas expiram`;

  // Tooltip — red tier names the 3 features that disappear
  const tooltipText =
    daysRemaining > 7
      ? `Seu trial tem acesso completo por ${daysRemaining} dias`
      : daysRemaining >= 3
        ? "Acesso completo. Após Day 7, alguns recursos ficam limitados."
        : `Em ${daysRemaining} ${daysRemaining === 1 ? "dia" : "dias"} você perde: alertas por e-mail, exportação Excel e pipeline ilimitado. Assine para manter.`;

  return (
    <Link
      href="/planos"
      aria-label={pillText}
      className={`
        inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium
        border transition-all hover:opacity-80
        ${bgColor} ${textColor} ${borderColor}
        ${className}
      `}
      title={tooltipText}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${dotColor} ${daysRemaining <= 2 ? "animate-pulse" : ""}`} />
      {pillText}
    </Link>
  );
}
