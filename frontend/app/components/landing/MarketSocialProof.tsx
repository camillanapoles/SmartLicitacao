'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { marketSocial } from '@/lib/copy/b2gIntelCopy';
import { useLandingAnimation, fadeInUp, staggerContainer } from '@/lib/animations';

/**
 * REPO-COMMS #1289: Seção "O que o mercado diz"
 * Citações de usuários reais — placeholder até coleta de depoimentos
 *
 * Usa useLandingAnimation (scroll trigger + prefers-reduced-motion).
 */
export default function MarketSocialProof() {
  const { ref, shouldAnimate } = useLandingAnimation();

  return (
    <section
      ref={ref}
      id={marketSocial.sectionId}
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
          {marketSocial.headline}
        </motion.h2>
      </motion.div>

      <motion.div
        className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl mx-auto"
        variants={staggerContainer}
        initial="hidden"
        animate={shouldAnimate ? 'visible' : 'hidden'}
      >
        {marketSocial.quotes.map((q) => (
          <motion.blockquote
            key={q.author}
            className="rounded-xl border border-[var(--border)] bg-[var(--surface-1)] p-8"
            variants={fadeInUp}
          >
            <p className="text-sm text-[var(--ink-secondary)] leading-relaxed italic mb-6">
              &ldquo;{q.text}&rdquo;
            </p>
            <footer>
              <div className="text-sm font-semibold text-[var(--ink)]">{q.author}</div>
              <div className="text-xs text-[var(--ink-muted)]">{q.role}</div>
            </footer>
          </motion.blockquote>
        ))}
      </motion.div>
    </section>
  );
}
