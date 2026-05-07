/**
 * AdvisoryDisclaimer — legal disclaimer for algorithmic recommendations.
 *
 * REPO-020 (#772): Standalone component extracted so multiple surfaces
 * (alertas-publicos, cnpj profiles, etc.) can render the same approved
 * disclaimer text without inline duplication.
 *
 * Note: ViabilityVerdict.tsx retains its own inline disclaimer for now —
 * that component renders it only in full (non-compact) mode and does not
 * need the AdvisoryDisclaimer wrapper.
 */

import React from "react";

const DISCLAIMER_TEXT =
  "Recomendação algorítmica baseada em dados públicos. Não substitui análise jurídica, técnica ou comercial final.";

export interface AdvisoryDisclaimerProps {
  /**
   * 'compact' — single line, inline, text-xs text-zinc-500.
   * 'full'    — two lines, padded card, bg-zinc-50 / dark:bg-zinc-900 rounded.
   * Defaults to 'compact'.
   */
  variant?: "compact" | "full";
}

/**
 * Renders the approved algorithmic-recommendation disclaimer.
 *
 * @example
 * // Compact (default) — drop anywhere inline
 * <AdvisoryDisclaimer />
 *
 * @example
 * // Full — padded block at the bottom of a section
 * <AdvisoryDisclaimer variant="full" />
 */
export function AdvisoryDisclaimer({
  variant = "compact",
}: AdvisoryDisclaimerProps): React.ReactElement {
  if (variant === "full") {
    return (
      <p
        data-testid="advisory-disclaimer"
        className="text-xs text-zinc-500 dark:text-zinc-500 leading-snug p-3 bg-zinc-50 dark:bg-zinc-900 rounded"
      >
        {DISCLAIMER_TEXT}
      </p>
    );
  }

  // compact (default)
  return (
    <p
      data-testid="advisory-disclaimer"
      className="text-xs text-zinc-500"
    >
      {DISCLAIMER_TEXT}
    </p>
  );
}

export default AdvisoryDisclaimer;
