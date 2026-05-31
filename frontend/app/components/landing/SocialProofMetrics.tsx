'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { socialProof } from '@/lib/copy/b2gIntelCopy';
import { useLandingAnimation, fadeInUp, staggerContainer } from '@/lib/animations';

/**
 * REPO-COMMS #1289: Seção de Prova Social — métricas reais do datalake
 * 4 métricas: contratos, órgãos, setores, UFs
 *
 * Usa useLandingAnimation (scroll trigger + prefers-reduced-motion).
 */
export default function SocialProofMetrics() {
  const { ref, shouldAnimate } = useLandingAnimation();

  return (
    <section
      ref={ref}
      id={socialProof.sectionId}
      className="relative max-w-landing mx-auto px-4 sm:px-6 lg:px-8 py-20 sm:py-28"
    >
      <motion.div
        className="text-center mb-16"
        variants={staggerContainer}
        initial="hidden"
        animate={shouldAnimate ? 'visible' : 'hidden'}
      >
        <motion.h2
          className="text-3xl sm:text-4xl font-display font-bold tracking-tight text-[var(--ink)]"
          variants={fadeInUp}
        >
          {socialProof.headline}
        </motion.h2>
      </motion.div>

      <motion.div
        className="grid grid-cols-2 lg:grid-cols-4 gap-6 max-w-4xl mx-auto"
        variants={staggerContainer}
        initial="hidden"
        animate={shouldAnimate ? 'visible' : 'hidden'}
      >
        {socialProof.metrics.map((m) => (
          <motion.div
            key={m.label}
            className="text-center p-6 rounded-xl border border-[var(--border)] bg-[var(--surface-1)]"
            variants={fadeInUp}
          >
            <div className="font-data text-4xl sm:text-5xl font-bold text-[var(--brand-blue)] mb-2 tabular-nums">
              {m.value}
            </div>
            <div className="text-sm font-semibold text-[var(--ink)] mb-1">{m.label}</div>
            <div className="text-xs text-[var(--ink-muted)]">{m.detail}</div>
          </motion.div>
        ))}
      </motion.div>
    </section>
  );
}
