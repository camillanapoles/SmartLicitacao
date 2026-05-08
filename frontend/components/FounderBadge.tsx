'use client';

interface FounderBadgeProps {
  className?: string;
}

export function FounderBadge({ className }: FounderBadgeProps) {
  return (
    <span
      title="Plano Fundadores SmartLic — acesso vitalício"
      className={`inline-flex items-center gap-1 px-2 py-0.5 bg-gradient-to-r from-amber-500 to-orange-500 text-white text-xs font-semibold rounded-full ${className ?? ''}`}
    >
      &#11088; Fundador
    </span>
  );
}
