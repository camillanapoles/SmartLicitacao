'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { antecipeDecidaExecute } from '@/lib/copy/b2gIntelCopy';
import { useLandingAnimation, fadeInUp, staggerContainer } from '@/lib/animations';

/**
 * REPO-COMMS #1289: Seção "O que o SmartLic realmente faz"
 * 3 colunas: Antecipe, Decida, Execute — com métricas visíveis
 *
 * Usa useLandingAnimation (scroll trigger + prefers-reduced-motion).
 */
export default function AntecipeDecidaExecute() {
  const { ref, shouldAnimate } = useLandingAnimation();

  return (
    <section
      ref={ref}
      id={antecipeDecidaExecute.sectionId}
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
          {antecipeDecidaExecute.headline}
        </motion.h2>
      </motion.div>

      <motion.div
        className="grid grid-cols-1 md:grid-cols-3 gap-8"
        variants={staggerContainer}
        initial="hidden"
        animate={shouldAnimate ? 'visible' : 'hidden'}
      >
        {antecipeDecidaExecute.columns.map((col) => (
          <motion.div
            key={col.title}
            className="relative rounded-xl border border-[var(--border)] bg-[var(--surface-1)] p-8 hover:border-[var(--border-accent)] transition-colors"
            variants={fadeInUp}
          >
            {/* Metric */}
            <div className="font-data text-4xl font-bold text-[var(--brand-blue)] mb-3 tabular-nums">
              {col.metric}
            </div>
            <div className="text-xs text-[var(--ink-muted)] uppercase tracking-wider mb-6 font-medium">
              {col.metricLabel}
            </div>

            <h3 className="text-xl font-bold text-[var(--ink)] mb-3">{col.title}</h3>
            <p className="text-sm text-[var(--ink-secondary)] leading-relaxed">{col.description}</p>
          </motion.div>
        ))}
      </motion.div>
    </section>
  );
}
