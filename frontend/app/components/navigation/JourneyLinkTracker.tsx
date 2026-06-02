'use client';

/**
 * CONV-017 (#1332): Client component for tracking journey_link_clicked events.
 *
 * Renders a Link with an onClick handler that fires a Mixpanel event with
 * source_template, destination_type, and position metadata.
 *
 * SSR-safe (renders anchor statically, tracking only fires on client).
 */

import Link from 'next/link';
import type { ReactNode } from 'react';
import { trackJourneyLinkClicked } from '@/lib/analytics-events';

interface JourneyLinkTrackerProps {
  href: string;
  sourceTemplate: string;
  destinationType: string;
  position: number;
  className?: string;
  children: ReactNode;
}

/**
 * Tracked link wrapper for journey steps. Fires `journey_link_clicked` on
 * click with structured metadata for Mixpanel analysis.
 */
export function JourneyLinkTracker({
  href,
  sourceTemplate,
  destinationType,
  position,
  className,
  children,
}: JourneyLinkTrackerProps) {
  const handleClick = () => {
    trackJourneyLinkClicked({
      source_template: sourceTemplate,
      destination_type: destinationType,
      position,
    });
  };

  return (
    <Link href={href} className={className} onClick={handleClick}>
      {children}
    </Link>
  );
}
