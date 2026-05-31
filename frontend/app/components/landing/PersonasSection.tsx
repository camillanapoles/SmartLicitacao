'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { personas } from '@/lib/copy/b2gIntelCopy';
import { useLandingAnimation, fadeInUp, staggerContainer } from '@/lib/animations';

/**
 * REPO-COMMS #1289: Seção "Para quem é o SmartLic"
 * 4 personas em grid 2x2
 *
 * Usa useLandingAnimation (scroll trigger + prefers-reduced-motion).
 */
export default function PersonasSection() {
  const { ref, shouldAnimate } = useLandingAnimation();

  return (
    <section
      ref={ref}
      id={personas.sectionId}
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
          {personas.headline}
        </motion.h2>
      </motion.div>

      <motion.div
        className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl mx-auto"
        variants={staggerContainer}
        initial="hidden"
        animate={shouldAnimate ? 'visible' : 'hidden'}
      >
        {personas.groups.map((p) => (
          <motion.div
            key={p.title}
            className="rounded-xl border border-[var(--border)] bg-[var(--surface-1)] p-6 hover:border-[var(--border-accent)] transition-colors"
            variants={fadeInUp}
          >
            <h3 className="text-lg font-bold text-[var(--ink)] mb-2">{p.title}</h3>
            <p className="text-sm text-[var(--ink-secondary)] leading-relaxed">{p.description}</p>
          </motion.div>
        ))}
      </motion.div>
    </section>
  );
}
