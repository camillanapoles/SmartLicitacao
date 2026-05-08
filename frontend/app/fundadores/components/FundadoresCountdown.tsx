'use client';

import { useEffect, useMemo, useState } from 'react';

export interface FoundingAvailabilitySnapshot {
  available: boolean;
  seats_total: number;
  seats_remaining: number;
  seats_taken: number;
  deadline_at: string | null;
  paused: boolean;
  reason: string;
  coupon_code: string;
  discount_pct: number;
  price_brl_cents?: number;
}

interface Props {
  snapshot: FoundingAvailabilitySnapshot | null;
}

// Fallback hardcoded — 2026-06-30 23:59:59 BRT (UTC-3)
const DEADLINE_FALLBACK = '2026-06-30T23:59:59-03:00';

interface Countdown {
  days: number;
  hours: number;
  minutes: number;
  seconds: number;
  total_ms: number;
}

function computeCountdown(deadlineIso: string, nowMs: number): Countdown {
  const deadlineMs = Date.parse(deadlineIso);
  const total = Math.max(0, deadlineMs - nowMs);
  const seconds = Math.floor(total / 1000) % 60;
  const minutes = Math.floor(total / 1000 / 60) % 60;
  const hours = Math.floor(total / 1000 / 60 / 60) % 24;
  const days = Math.floor(total / 1000 / 60 / 60 / 24);
  return { days, hours, minutes, seconds, total_ms: total };
}

function pad2(n: number): string {
  return n.toString().padStart(2, '0');
}

export default function FundadoresCountdown({ snapshot }: Props) {
  const [now, setNow] = useState<number>(() => Date.now());

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  const deadlineIso = snapshot?.deadline_at ?? DEADLINE_FALLBACK;

  const countdown = useMemo(
    () => computeCountdown(deadlineIso, now),
    [deadlineIso, now]
  );

  const expired = countdown.total_ms === 0;
  const paused = snapshot?.paused ?? false;

  return (
    <div
      data-testid="fundadores-availability"
      className="rounded-lg border border-blue-500/30 bg-blue-950/20 p-4"
      aria-live="polite"
    >
      {expired ? (
        <p className="text-sm text-slate-300" data-testid="fundadores-countdown-expired">
          O prazo de inscrição fundadores encerrou.
        </p>
      ) : (
        <div
          className="flex flex-wrap items-center gap-3 text-sm text-slate-200"
          data-testid="fundadores-countdown"
        >
          <span className="opacity-70">Encerra em:</span>
          <div className="flex items-center gap-3 font-mono tabular-nums text-white">
            <span data-testid="fundadores-countdown-days">
              <strong className="text-xl">{countdown.days}</strong>
              <span className="text-xs ml-1 opacity-70">dias</span>
            </span>
            <span data-testid="fundadores-countdown-hours">
              <strong className="text-xl">{pad2(countdown.hours)}</strong>
              <span className="text-xs ml-1 opacity-70">h</span>
            </span>
            <span data-testid="fundadores-countdown-minutes">
              <strong className="text-xl">{pad2(countdown.minutes)}</strong>
              <span className="text-xs ml-1 opacity-70">min</span>
            </span>
            <span data-testid="fundadores-countdown-seconds">
              <strong className="text-xl">{pad2(countdown.seconds)}</strong>
              <span className="text-xs ml-1 opacity-70">s</span>
            </span>
          </div>
        </div>
      )}

      {paused && (
        <p className="mt-2 text-sm text-amber-300" data-testid="fundadores-paused-notice">
          Inscrições temporariamente pausadas. Tente novamente em algumas horas.
        </p>
      )}
    </div>
  );
}
