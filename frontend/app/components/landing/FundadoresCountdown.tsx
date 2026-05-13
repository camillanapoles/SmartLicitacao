'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { fadeInUp } from '@/lib/animations';

/**
 * Cialdini AC3 — Scarcity: Countdown to Fundadores Plan deadline (30/06/2026).
 * Shows days remaining until plan closes. Red urgency when <14 days.
 */
export default function FundadoresCountdown() {
  const [timeLeft, setTimeLeft] = useState({ days: 0, hours: 0, minutes: 0 });
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const target = new Date('2026-06-30T23:59:59-03:00').getTime();

    const tick = () => {
      const now = Date.now();
      const diff = target - now;
      if (diff <= 0) return;
      setTimeLeft({
        days: Math.floor(diff / 86400000),
        hours: Math.floor((diff % 86400000) / 3600000),
        minutes: Math.floor((diff % 3600000) / 60000),
      });
    };

    tick();
    const interval = setInterval(tick, 60000);
    return () => clearInterval(interval);
  }, []);

  if (!mounted) return null;
  if (timeLeft.days <= 0 && timeLeft.hours <= 0) return null;

  const urgent = timeLeft.days < 14;

  return (
    <motion.div
      variants={fadeInUp}
      className={`
        inline-flex items-center gap-2 rounded-full border px-4 py-1.5 mb-4
        ${urgent
          ? 'border-red-300/50 bg-red-50 dark:bg-red-900/20'
          : 'border-amber-300/50 bg-amber-50 dark:bg-amber-900/20'
        }
      `}
      data-testid="fundadores-countdown"
    >
      <span className={`w-2 h-2 rounded-full ${urgent ? 'bg-red-500 animate-pulse' : 'bg-amber-400'}`} />
      <span className={`text-xs font-semibold tracking-wide uppercase ${urgent ? 'text-red-700 dark:text-red-300' : 'text-amber-700 dark:text-amber-300'}`}>
        {urgent ? 'Últimas vagas' : 'Vagas Fundadores'}:{' '}
        {timeLeft.days > 0 && <>{timeLeft.days}d </>}
        {timeLeft.hours}h {timeLeft.minutes}min
      </span>
    </motion.div>
  );
}
