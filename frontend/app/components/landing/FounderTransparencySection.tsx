'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { fadeInUp, staggerContainer } from '@/lib/animations';

/**
 * COPY-COP-004 (#1125): FounderTransparencySection — real founder content
 * replaces fabricated TestimonialSection (CDC art. 37 compliance).
 *
 * Shows founder photo (plain img tag to avoid next/image build dependency),
 * beta disclaimer, and direct email contact.
 */
export default function FounderTransparencySection() {
  const [imgError, setImgError] = React.useState(false);

  return (
    <section
      className="py-16 sm:py-20 bg-[var(--surface-1)]"
      data-testid="founder-transparency-section"
    >
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <motion.div
          variants={staggerContainer}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-50px' }}
        >
          <h2 className="text-2xl sm:text-3xl font-bold text-[var(--ink)] mb-8">
            Quem faz o SmartLic
          </h2>

          <motion.div className="flex flex-col items-center gap-6" variants={fadeInUp}>
            <div className="w-24 h-24 rounded-full overflow-hidden ring-4 ring-[var(--brand-blue-subtle)] flex items-center justify-center bg-[var(--brand-blue-subtle)]">
              {!imgError ? (
                <img
                  src="/tiago.jpg"
                  alt="Tiago Sasaki — Founder do SmartLic"
                  className="w-full h-full object-cover"
                  onError={() => setImgError(true)}
                />
              ) : (
                <span className="text-[var(--brand-blue)] font-bold text-xl">TS</span>
              )}
            </div>

            <blockquote className="max-w-2xl text-lg sm:text-xl text-[var(--ink-secondary)] leading-relaxed italic">
              &ldquo;O SmartLic est&aacute; em beta. Constru&iacute; cada parte com
              obsess&atilde;o pelo sucesso das empresas em licita&ccedil;&otilde;es. Seus primeiros 14 dias
              s&atilde;o gr&aacute;tis. Se gostar, fica. Se n&atilde;o, boa sorte!&rdquo;
            </blockquote>

            <div className="text-sm text-[var(--ink-muted)]">
              <p className="font-semibold text-[var(--ink)]">Tiago Sasaki</p>
              <p>Founder, SmartLic</p>
              <a
                href="mailto:tiago@smartlic.tech"
                className="text-[var(--brand-blue)] hover:underline mt-1 inline-block"
                data-testid="founder-email"
              >
                tiago@smartlic.tech
              </a>
            </div>
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
}
