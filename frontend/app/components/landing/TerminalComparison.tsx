'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { terminalComparison } from '@/lib/copy/b2gIntelCopy';
import { useScrollAnimation, fadeInUp } from '@/lib/animations';

/**
 * REPO-COMMS #1289: Seção "Não é um alerta de edital. É um terminal de inteligência."
 * Comparação visual antes/depois — planilha+Trello+WhatsApp → SmartLic
 */
export default function TerminalComparison() {
  const { ref, isVisible } = useScrollAnimation(0.15);

  return (
    <section
      ref={ref}
      id={terminalComparison.sectionId}
      className="relative max-w-landing mx-auto px-4 sm:px-6 lg:px-8 py-20 sm:py-28"
    >
      {/* Kicker */}
      <motion.div
        className="text-center mb-4"
        initial={{ opacity: 0, y: 20 }}
        animate={isVisible ? { opacity: 1, y: 0 } : {}}
        transition={{ duration: 0.5 }}
      >
        <span className="inline-flex items-center gap-2 rounded-full border border-[var(--warning)]/30 bg-[var(--warning-subtle)] px-4 py-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-[var(--warning)]" />
          <span className="text-sm font-semibold text-[var(--warning)] tracking-wide uppercase">
            {terminalComparison.kicker}
          </span>
        </span>
      </motion.div>

      <motion.h2
        className="text-3xl sm:text-4xl font-display font-bold tracking-tight text-center text-[var(--ink)] mb-16"
        initial={{ opacity: 0, y: 20 }}
        animate={isVisible ? { opacity: 1, y: 0 } : {}}
        transition={{ duration: 0.5, delay: 0.1 }}
      >
        {terminalComparison.headline}
      </motion.h2>

      {/* Two-column comparison */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 max-w-4xl mx-auto">
        {/* Before */}
        <motion.div
          className="rounded-xl border border-[var(--border)] bg-[var(--surface-1)] p-8"
          initial={{ opacity: 0, x: -20 }}
          animate={isVisible ? { opacity: 1, x: 0 } : {}}
          transition={{ duration: 0.5, delay: 0.2 }}
        >
          <h3 className="text-lg font-semibold text-[var(--error)] mb-6">
            {terminalComparison.before.title}
          </h3>
          <ul className="space-y-4">
            {terminalComparison.before.items.map((item, i) => (
              <li key={i} className="flex items-start gap-3 text-sm text-[var(--ink-secondary)]">
                <span className="mt-0.5 flex-shrink-0 w-5 h-5 rounded-full bg-[var(--error-subtle)] flex items-center justify-center">
                  <span className="text-[var(--error)] text-xs font-bold">✕</span>
                </span>
                {item}
              </li>
            ))}
          </ul>
        </motion.div>

        {/* After */}
        <motion.div
          className="rounded-xl border border-[var(--success)]/20 bg-[var(--surface-1)] p-8 ring-1 ring-[var(--success)]/10"
          initial={{ opacity: 0, x: 20 }}
          animate={isVisible ? { opacity: 1, x: 0 } : {}}
          transition={{ duration: 0.5, delay: 0.2 }}
        >
          <h3 className="text-lg font-semibold text-[var(--success)] mb-6">
            {terminalComparison.after.title}
          </h3>
          <ul className="space-y-4">
            {terminalComparison.after.items.map((item, i) => (
              <li key={i} className="flex items-start gap-3 text-sm text-[var(--ink-secondary)]">
                <span className="mt-0.5 flex-shrink-0 w-5 h-5 rounded-full bg-[var(--success-subtle)] flex items-center justify-center">
                  <span className="text-[var(--success)] text-xs font-bold">✓</span>
                </span>
                {item}
              </li>
            ))}
          </ul>
        </motion.div>
      </div>
    </section>
  );
}
