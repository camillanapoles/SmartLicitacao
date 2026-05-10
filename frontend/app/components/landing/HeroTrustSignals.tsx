'use client';

import React from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { fadeInUp } from '@/lib/animations';

/**
 * COPY-LANDING-004 (#1003): Trust signals 2026 — substitui microcopy negativa
 * "Sem dados fabricados" por 4 sinais positivos verificáveis: Changelog público,
 * Roadmap aberto, 60d garantia + devolução incondicional, Fontes oficiais.
 *
 * Extraído de HeroSection.tsx em refactor estrutural (LOC gate, #1017).
 */
export default function HeroTrustSignals() {
  return (
    <motion.div
      className="mt-6 flex flex-wrap items-center justify-center lg:justify-start gap-x-5 gap-y-2 text-xs text-ink-muted"
      variants={fadeInUp}
      data-testid="hero-trust-signals"
    >
      <Link
        href="/changelog"
        className="flex items-center gap-1.5 hover:text-ink-secondary transition-colors"
        data-testid="hero-trust-changelog"
      >
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
        Changelog público
      </Link>
      <Link
        href="/roadmap"
        className="flex items-center gap-1.5 hover:text-ink-secondary transition-colors"
        data-testid="hero-trust-roadmap"
      >
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
        Roadmap aberto
      </Link>
      <span
        className="flex items-center gap-1.5"
        data-testid="hero-trust-guarantee"
      >
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
        60 dias de garantia · devolução incondicional
      </span>
      <span
        className="flex items-center gap-1.5"
        data-testid="hero-trust-sources"
      >
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
        Fontes oficiais verificadas (PNCP, ComprasGov, PCP)
      </span>
    </motion.div>
  );
}
