'use client';

/**
 * Plano Fundadores: deadline countdown + seat counter for the /fundadores landing.
 *
 * Receives an availability snapshot from the parent (single fetch on mount)
 * and ticks an internal clock every 1s for the countdown. Re-fetch of the
 * snapshot itself is the parent's responsibility (currently every 60s).
 */

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

interface Countdown {
  days: number;
  hours: number;
  minutes: number;
  seconds: number;
  total_ms: number;
}

function computeCountdown(deadlineIso: string | null, nowMs: number): Countdown {
  if (!deadlineIso) {
    return { days: 0, hours: 0, minutes: 0, seconds: 0, total_ms: 0 };
  }
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

  const countdown = useMemo(
    () => computeCountdown(snapshot?.deadline_at ?? null, now),
    [snapshot?.deadline_at, now]
  );

  if (!snapshot) {
    return (
      <div
        data-testid="fundadores-availability-loading"
        className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-500"
      >
        Carregando disponibilidade...
      </div>
    );
  }

  const seatsRemaining = snapshot.seats_remaining;
  const seatsTotal = snapshot.seats_total;
  const urgency = seatsRemaining > 0 && seatsRemaining <= 5;
  const full = !snapshot.available;

  const counterColor = full
    ? 'text-red-700 bg-red-50 border-red-200'
    : urgency
      ? 'text-amber-800 bg-amber-50 border-amber-200'
      : 'text-blue-800 bg-blue-50 border-blue-200';

  return (
    <div
      data-testid="fundadores-availability"
      className={`rounded-lg border p-4 ${counterColor}`}
      aria-live="polite"
    >
      <div className="flex items-baseline justify-between gap-2">
        <p className="text-sm font-medium" data-testid="fundadores-seat-counter">
          {full ? (
            <span>
              <strong>0/{seatsTotal}</strong> vagas restantes — programa fechado.
            </span>
          ) : (
            <span>
              <strong data-testid="fundadores-seats-remaining">{seatsRemaining}</strong>
              /{seatsTotal} vagas restantes
              {urgency && ' — corra!'}
            </span>
          )}
        </p>
        <p className="text-xs uppercase tracking-wide opacity-80" data-testid="fundadores-price-label">
          Acesso vitalício
        </p>
      </div>

      {snapshot.deadline_at && countdown.total_ms > 0 && (
        <div
          className="mt-3 flex flex-wrap items-center gap-3 text-sm"
          data-testid="fundadores-countdown"
        >
          <span className="opacity-70">Encerra em:</span>
          <div className="flex items-center gap-2 font-mono tabular-nums">
            <span data-testid="fundadores-countdown-days">
              <strong>{countdown.days}</strong>d
            </span>
            <span data-testid="fundadores-countdown-hours">
              <strong>{pad2(countdown.hours)}</strong>h
            </span>
            <span data-testid="fundadores-countdown-minutes">
              <strong>{pad2(countdown.minutes)}</strong>m
            </span>
            <span data-testid="fundadores-countdown-seconds">
              <strong>{pad2(countdown.seconds)}</strong>s
            </span>
          </div>
        </div>
      )}

      {snapshot.deadline_at && countdown.total_ms === 0 && (
        <p className="mt-2 text-sm" data-testid="fundadores-countdown-expired">
          O prazo de inscrição fundadores encerrou.
        </p>
      )}

      {snapshot.paused && (
        <p className="mt-2 text-sm" data-testid="fundadores-paused-notice">
          Inscrições temporariamente pausadas. Tente novamente em algumas horas.
        </p>
      )}
    </div>
  );
}
