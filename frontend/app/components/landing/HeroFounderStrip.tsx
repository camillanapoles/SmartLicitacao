'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { fadeInUp } from '@/lib/animations';
import { hero } from '@/lib/copy/valueProps';

/**
 * COPY-LANDING-004 (#1003): Founder-led visível — nome + cargo + LinkedIn.
 * Schema.org Person já vive em StructuredData.tsx (E-E-A-T).
 * Asset foto profissional fica como dependência separada; o strip exibe
 * iniciais "TS" como placeholder até o asset ser disponibilizado.
 *
 * Extraído de HeroSection.tsx em refactor estrutural (LOC gate, #1017).
 */
export default function HeroFounderStrip() {
  return (
    <motion.div
      className="mt-6 flex items-center justify-center lg:justify-start gap-3 text-sm"
      variants={fadeInUp}
      data-testid="hero-founder-strip"
    >
      <div
        className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-blue-subtle text-brand-blue font-semibold"
        aria-hidden="true"
      >
        TS
      </div>
      <p className="text-ink-secondary text-left leading-snug">
        Criado por{' '}
        <a
          href={hero.founder.linkedinUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="font-semibold text-ink underline-offset-2 hover:underline"
          data-testid="hero-founder-linkedin"
        >
          {hero.founder.name}
        </a>
        , {hero.founder.role}.
      </p>
    </motion.div>
  );
}
