'use client';

import React from 'react';
import {
  type UrgencyLevel,
  URGENCY_COLOR_MAP,
  URGENCY_LEVEL_LABELS,
  getUrgencyLevel,
  getDaysSince,
  daysSince,
  urgencyLabel,
} from '@/lib/urgency-utils';

// ---------------------------------------------------------------------------
// CONV-016: Visual badge with time-based color coding for pSEO urgency signals
// ---------------------------------------------------------------------------

interface UrgencyBadgeProps {
  /** Days since the last event */
  daysSinceLastEvent: number;
  /** Optional custom text override */
  label?: string;
  /** Additional CSS classes */
  className?: string;
}

/**
 * UrgencyBadge — small badge showing recency of activity for an entity.
 * Color-coded: green (< 7d), yellow (7-30d), neutral (31-90d), gray (> 90d).
 */
export function UrgencyBadge({
  daysSinceLastEvent,
  label,
  className = '',
}: UrgencyBadgeProps) {
  const level = getUrgencyLevel(daysSinceLastEvent);
  const defaults = URGENCY_LEVEL_LABELS[level];
  const displayText = label ?? defaults.text;

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${URGENCY_COLOR_MAP[level]} ${className}`}
      title={defaults.title}
    >
      <span
        className={`inline-block h-1.5 w-1.5 rounded-full ${
          level === 'green'
            ? 'bg-green-500'
            : level === 'yellow'
            ? 'bg-yellow-500'
            : level === 'neutral'
            ? 'bg-blue-500'
            : 'bg-gray-400'
        }`}
      />
      {displayText}
    </span>
  );
}

// Re-export pure helpers for backward compatibility.
// NEW: prefer importing from '@/lib/urgency-utils' in Server Components.
export { daysSince, urgencyLabel, getDaysSince, getUrgencyLevel, URGENCY_COLOR_MAP, URGENCY_LEVEL_LABELS };
export type { UrgencyLevel };
