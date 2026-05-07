/**
 * ViabilityVerdict — reusable component for displaying algorithmic recommendation.
 *
 * REPO-012 (#764): Auto-maps score (0-10) → PARTICIPAR / AVALIAR / NÃO RECOMENDADO
 * with optional bullet reasons and embedded legal disclaimer.
 *
 * Used downstream by REPO-013, REPO-020.
 */

import React from "react";

export interface ViabilityVerdictProps {
  /** Score 0-10. Drives auto-mapping when `label` is omitted. */
  score: number;
  /** Explicit label override. Auto-derived from score when not provided. */
  label?: "PARTICIPAR" | "AVALIAR" | "NÃO RECOMENDADO";
  /** Supporting bullet points (max 3 rendered). */
  reasons?: string[];
  /** Compact mode: renders badge only (no reasons, no disclaimer). Defaults to false. */
  compact?: boolean;
}

// ─── Helpers ────────────────────────────────────────────────────────────────

const DISCLAIMER_TEXT =
  "Recomendação algorítmica baseada em dados públicos. Não substitui análise jurídica, técnica ou comercial final.";

type VerdictLabel = "PARTICIPAR" | "AVALIAR" | "NÃO RECOMENDADO";

function scoreToLabel(score: number): VerdictLabel {
  if (score >= 7) return "PARTICIPAR";
  if (score >= 4) return "AVALIAR";
  return "NÃO RECOMENDADO";
}

const LABEL_CONFIG: Record<
  VerdictLabel,
  { badgeCls: string; icon: React.ReactNode }
> = {
  PARTICIPAR: {
    badgeCls:
      "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300",
    icon: (
      <svg
        className="w-3.5 h-3.5"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        aria-hidden="true"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M5 13l4 4L19 7"
        />
      </svg>
    ),
  },
  AVALIAR: {
    badgeCls:
      "bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300",
    icon: (
      <svg
        className="w-3.5 h-3.5"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        aria-hidden="true"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M12 9v2m0 4h.01M12 3l9.66 16.59A1 1 0 0120.66 21H3.34a1 1 0 01-.86-1.41L12 3z"
        />
      </svg>
    ),
  },
  "NÃO RECOMENDADO": {
    badgeCls: "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300",
    icon: (
      <svg
        className="w-3.5 h-3.5"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        aria-hidden="true"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M6 18L18 6M6 6l12 12"
        />
      </svg>
    ),
  },
};

// ─── Component ───────────────────────────────────────────────────────────────

/**
 * Renders an algorithmic viability recommendation badge with optional
 * bullet reasons and legal disclaimer.
 *
 * @example
 * // Full (default)
 * <ViabilityVerdict score={7.5} reasons={["Modalidade favorável", "Valor compatível"]} />
 *
 * @example
 * // Compact — inline badge only
 * <ViabilityVerdict score={3.2} compact />
 */
export function ViabilityVerdict({
  score,
  label,
  reasons,
  compact = false,
}: ViabilityVerdictProps): React.ReactElement {
  const resolvedLabel: VerdictLabel = label ?? scoreToLabel(score);
  const { badgeCls, icon } = LABEL_CONFIG[resolvedLabel];

  const displayScore = Number.isFinite(score)
    ? `${Math.round(score * 10) / 10}/10`
    : "–/10";

  // Badge element shared between compact and full modes
  const badge = (
    <span
      data-testid="viability-verdict-badge"
      data-verdict={resolvedLabel}
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-semibold ${badgeCls}`}
    >
      {icon}
      <span>{resolvedLabel}</span>
      <span aria-label={`Pontuação ${displayScore}`} className="font-normal opacity-75">
        {displayScore}
      </span>
    </span>
  );

  if (compact) {
    return <div data-testid="viability-verdict">{badge}</div>;
  }

  // Clamp to max 3 reasons
  const displayedReasons = reasons ? reasons.slice(0, 3) : [];

  return (
    <div data-testid="viability-verdict" className="space-y-1.5">
      {badge}

      {displayedReasons.length > 0 && (
        <ul
          data-testid="viability-verdict-reasons"
          className="mt-1 space-y-0.5 pl-1"
        >
          {displayedReasons.map((reason, idx) => (
            <li
              key={idx}
              className="flex items-start gap-1.5 text-xs text-zinc-600 dark:text-zinc-400"
            >
              <span aria-hidden="true" className="mt-0.5 shrink-0 text-zinc-400">
                •
              </span>
              {reason}
            </li>
          ))}
        </ul>
      )}

      <p
        data-testid="viability-verdict-disclaimer"
        className="text-xs text-zinc-500 dark:text-zinc-500 leading-snug"
      >
        {DISCLAIMER_TEXT}
      </p>
    </div>
  );
}

export default ViabilityVerdict;
