'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { fadeInUp } from '@/lib/animations';

/**
 * LoomPlaceholder — Cialdini AC5: Video preview with modal.
 * Shows a product tour CTA that opens a video modal.
 * Replace iframe src with actual Loom URL when available.
 */
export default function LoomPlaceholder() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <motion.div
        variants={fadeInUp}
        className="mt-8"
        data-testid="loom-placeholder"
      >
        <button
          onClick={() => setIsOpen(true)}
          className="group flex items-center gap-3 text-sm text-ink-muted hover:text-ink transition-colors"
          aria-label="Assista 90s — tour rápido do produto"
        >
          {/* Play button circle */}
          <span className="flex items-center justify-center w-10 h-10 rounded-full bg-brand-blue-subtle group-hover:bg-brand-blue/20 transition-colors">
            <svg className="w-4 h-4 text-brand-blue ml-0.5" fill="currentColor" viewBox="0 0 16 16">
              <path d="M6 3.5v9l6-4.5L6 3.5z" />
            </svg>
          </span>
          <span className="font-medium">
            Assista 90s — tour rápido do produto
          </span>
        </button>
      </motion.div>

      {/* Modal */}
      {isOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
          onClick={() => setIsOpen(false)}
          role="dialog"
          aria-modal="true"
          aria-label="Tour rápido do produto"
        >
          <div
            className="relative w-full max-w-3xl aspect-video bg-black rounded-xl overflow-hidden shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Placeholder — replace src with actual Loom URL */}
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-gray-900 text-white p-8 text-center">
              <svg className="w-16 h-16 mb-4 text-white/40" fill="currentColor" viewBox="0 0 24 24">
                <path d="M8 5v14l11-7L8 5z" />
              </svg>
              <p className="text-lg font-semibold mb-2">Tour rápido do SmartLic</p>
              <p className="text-sm text-white/60 max-w-md">
                Veja como o SmartLic filtra oportunidades, analisa viabilidade e prioriza os editais certos para sua empresa — em 90 segundos.
              </p>
              <p className="mt-4 text-xs text-white/40">
                URL do Loom será inserida quando disponível
              </p>
            </div>

            {/* Close button */}
            <button
              onClick={() => setIsOpen(false)}
              className="absolute top-3 right-3 w-8 h-8 flex items-center justify-center rounded-full bg-black/40 text-white hover:bg-black/60 transition-colors"
              aria-label="Fechar"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      )}
    </>
  );
}
