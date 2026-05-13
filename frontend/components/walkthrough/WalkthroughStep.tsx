"use client";

import React from "react";

export interface WalkthroughStepProps {
  /** The title of the current step. */
  title: string;
  /** The rendered content for this step. */
  children: React.ReactNode;
}

/**
 * WalkthroughStep renders individual step content inside the ProductWalkthrough modal.
 * Provides consistent layout for the content area.
 */
export function WalkthroughStep({ title, children }: WalkthroughStepProps) {
  return (
    <div className="space-y-4">
      <h3 className="text-base font-semibold text-[var(--ink)]">{title}</h3>
      <div>{children}</div>
    </div>
  );
}
