// ---------------------------------------------------------------------------
// Pure date-math helpers shared between server and client components.
// Extracted from components/pseo/UrgencyBadge.tsx to fix CONV-016 regression:
// "Attempted to call daysSince() from the server but daysSince is on the client"
// — caused by importing a function from a 'use client' module in a Server Component.
// ---------------------------------------------------------------------------

export type UrgencyLevel = 'green' | 'yellow' | 'neutral' | 'gray';

export const URGENCY_COLOR_MAP: Record<UrgencyLevel, string> = {
  green: 'bg-green-100 text-green-800 border-green-200',
  yellow: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  neutral: 'bg-blue-50 text-blue-700 border-blue-100',
  gray: 'bg-gray-100 text-gray-500 border-gray-200',
};

export const URGENCY_LEVEL_LABELS: Record<UrgencyLevel, { text: string; title: string }> = {
  green: { text: 'Ativo esta semana', title: 'Atividade registrada nos últimos 7 dias' },
  yellow: { text: 'Ativo este mês', title: 'Atividade registrada nos últimos 30 dias' },
  neutral: { text: 'Ativo recentemente', title: 'Atividade registrada nos últimos 90 dias' },
  gray: { text: 'Sem atividade recente', title: 'Nenhuma atividade registrada nos últimos 90 dias' },
};

export function getUrgencyLevel(days: number): UrgencyLevel {
  if (days < 0) return 'gray';
  if (days <= 7) return 'green';
  if (days <= 30) return 'yellow';
  if (days <= 90) return 'neutral';
  return 'gray';
}

export function getDaysSince(dateStr: string | null | undefined): number {
  if (!dateStr) return -1;
  try {
    const eventDate = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - eventDate.getTime();
    return Math.floor(diffMs / (1000 * 60 * 60 * 24));
  } catch {
    return -1;
  }
}

/**
 * Convenience function to compute days-since from a date string.
 * Safe to call from both Server and Client Components.
 */
export function daysSince(dateStr: string | null | undefined): number {
  return getDaysSince(dateStr);
}

/**
 * Helper to get the appropriate label text for a date string.
 * Safe to call from both Server and Client Components.
 */
export function urgencyLabel(dateStr: string | null | undefined): string {
  const days = getDaysSince(dateStr);
  const level = getUrgencyLevel(days);
  return URGENCY_LEVEL_LABELS[level].text;
}
