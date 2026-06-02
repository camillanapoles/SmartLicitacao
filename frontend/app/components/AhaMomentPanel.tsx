'use client';

/**
 * CONV-004 (#1313): AhaMomentPanel — Progressive blur + email/WhatsApp gate.
 *
 * Shows real data insights from entity pages (fornecedor, orgao, etc.)
 * with progressive blur on premium cards. The blurred cards have an
 * overlay gate that collects email OR WhatsApp (NOT full signup).
 *
 * Events (Mixpanel):
 *   aha_panel_view      — panel rendered on the page
 *   aha_unlock_start    — user clicked "Desbloquear insight"
 *   aha_unlock_complete — user submitted email/WhatsApp
 *   value_prop_view     — shared with CONV-001
 *   value_cta_click     — shared with CONV-001
 */

import { useState, useEffect, useRef, type FormEvent } from 'react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import { trackPseoEvent, type PseoSourceTemplate } from '@/lib/analytics/pseo';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** A single insight card with a real data point from the page. */
export interface InsightCard {
  /** Unique identifier within the card list. */
  id: string;
  /** Emoji or short icon text (e.g. "📊", "🏢"). */
  icon: string;
  /** Short title (e.g. "Estados Atuantes"). */
  title: string;
  /** The key metric value (e.g. "5 estados"). */
  value: string;
  /** Supporting description (1 sentence). */
  description: string;
}

export interface AhaMomentPanelProps {
  /** Analytics source template identifier. */
  sourceTemplate: PseoSourceTemplate;
  /** Entity identifier (CNPJ, slug, etc.). */
  entityId?: string;
  /** Entity display name for personalisation. */
  entityName?: string;
  /** Sector slug for analytics. */
  setor?: string;
  /** Two-letter UF code for analytics. */
  uf?: string;
  /** Real insight cards derived from page data. */
  insightCards: InsightCard[];
  /**
   * Number of cards visible without blur.
   * Cards before this index are fully visible; from this index onward are blurred.
   * @default 2
   */
  blurThreshold?: number;
  /** Optional CTA config shown after all insights are revealed. */
  postUnlockCta?: {
    label: string;
    href: string;
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function validateEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

function validatePhone(value: string): boolean {
  // Accepts +55 (XX) XXXXX-XXXX, (XX) XXXXX-XXXX, XXXXXXXXXXX, etc.
  const digits = value.replace(/\D/g, '');
  return digits.length >= 10 && digits.length <= 13;
}

/** Obfuscate sensitive data for pre-unlock blurred cards (CR security gate). */
function obfuscateCard(card: InsightCard): InsightCard {
  return {
    ...card,
    value: '●●●●',
    description: 'Insight exclusivo — desbloqueie para ver os dados reais.',
  };
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function InsightCardView({
  card,
  index,
  isBlurred,
}: {
  card: InsightCard;
  index: number;
  isBlurred: boolean;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: index * 0.08 }}
      className={`rounded-xl border p-4 sm:p-5 transition-colors ${
        isBlurred
          ? 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800'
          : 'border-brand-blue/20 dark:border-brand-blue/30 bg-white dark:bg-gray-800'
      }`}
      aria-hidden={isBlurred ? 'true' : undefined}
    >
      {/* Icon */}
      <div
        className={`text-2xl mb-2 ${isBlurred ? 'blur-[3px] select-none' : ''}`}
        aria-hidden="true"
      >
        {card.icon}
      </div>

      {/* Value */}
      <p
        className={`text-xl sm:text-2xl font-bold text-gray-900 dark:text-white mb-1 ${
          isBlurred ? 'blur-[4px] select-none' : ''
        }`}
      >
        {card.value}
      </p>

      {/* Title */}
      <h4
        className={`text-sm font-semibold text-gray-900 dark:text-white mb-1 ${
          isBlurred ? 'blur-[2px] select-none' : ''
        }`}
      >
        {card.title}
      </h4>

      {/* Description */}
      <p
        className={`text-xs text-gray-500 dark:text-gray-400 leading-relaxed ${
          isBlurred ? 'blur-[2px] select-none' : ''
        }`}
      >
        {card.description}
      </p>
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function AhaMomentPanel({
  sourceTemplate,
  entityId,
  entityName,
  setor,
  uf,
  insightCards,
  blurThreshold = 2,
  postUnlockCta,
}: AhaMomentPanelProps) {
  const [unlocked, setUnlocked] = useState(false);
  const [showGate, setShowGate] = useState(false);
  const [contact, setContact] = useState('');
  const [error, setError] = useState(false);
  const [persisting, setPersisting] = useState(false);
  const viewFiredRef = useRef(false);

  // Total cards = all insight cards
  const visibleCards = insightCards.slice(0, blurThreshold);
  const blurredCards = insightCards.slice(blurThreshold);
  const hasBlurred = blurredCards.length > 0;

  // Fire aha_panel_view + value_prop_view on mount
  useEffect(() => {
    if (!viewFiredRef.current) {
      viewFiredRef.current = true;
      const baseProps = {
        source_template: sourceTemplate,
        entity_id: entityId,
        setor,
        uf,
        page_url: typeof window !== 'undefined' ? window.location.href : undefined,
      };

      trackPseoEvent('aha_panel_view', {
        ...baseProps,
        total_cards: insightCards.length,
        blur_threshold: blurThreshold,
      });

      trackPseoEvent('value_prop_view', {
        ...baseProps,
        component: 'aha_moment_panel',
        template: sourceTemplate,
      });
    }
  }, [sourceTemplate, entityId, setor, uf, insightCards.length, blurThreshold]);

  const handleUnlockStart = () => {
    setShowGate(true);
    trackPseoEvent('aha_unlock_start', {
      source_template: sourceTemplate,
      entity_id: entityId,
      setor,
      uf,
    });
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const isEmail = validateEmail(contact);
    const isPhone = validatePhone(contact);

    if (!isEmail && !isPhone) {
      setError(true);
      return;
    }

    setError(false);
    setPersisting(true);

    // Persist lead via /api/lead-capture (CONV-004 lead gate)
    const contactType = isEmail ? 'email' : 'whatsapp';
    const payload: Record<string, string> = {
      source: 'seo_banner',
      setor: setor || '',
      uf: uf || '',
    };

    if (isEmail) {
      payload.email = contact;
    } else {
      // Phone-only: send placeholder email + real phone in telefone field
      const digits = contact.replace(/\D/g, '');
      payload.email = `whatsapp-${digits.slice(-4)}@lead.smartlic.tech`;
      payload.telefone = contact;
    }

    try {
      await fetch('/api/lead-capture', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    } catch {
      // Fail-open: unlock even if persistence fails
      console.warn('AhaMomentPanel: lead-capture POST failed (fail-open)');
    }

    setPersisting(false);
    setUnlocked(true);
    setShowGate(false);

    trackPseoEvent('aha_unlock_complete', {
      source_template: sourceTemplate,
      entity_id: entityId,
      setor,
      uf,
      contact_type: contactType,
    });
  };

  // Show nothing if no cards
  if (insightCards.length === 0) return null;

  return (
    <section
      aria-label="Insights intelligence"
      className="max-w-5xl mx-auto px-4 py-6 sm:py-8"
      data-testid="aha-moment-panel"
    >
      {/* Section header */}
      <div className="mb-5">
        <h2 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-white">
          {entityName
            ? `Insights sobre ${entityName}`
            : 'Insights inteligentes'}
        </h2>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Dados reais das fontes oficiais — análise inteligente.
        </p>
      </div>

      {/* Card grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* Visible cards */}
        {visibleCards.map((card, idx) => (
          <InsightCardView
            key={card.id}
            card={card}
            index={idx}
            isBlurred={false}
          />
        ))}

        {/* Blurred cards section — obfuscated data (CR security: no real data in DOM) */}
        {hasBlurred && !unlocked && (
          <div className="relative col-span-1 sm:col-span-2 lg:col-span-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {blurredCards.map((card, idx) => (
                <InsightCardView
                  key={card.id}
                  card={obfuscateCard(card)}
                  index={blurThreshold + idx}
                  isBlurred={true}
                />
              ))}
            </div>

            {/* Overlay */}
            <AnimatePresence mode="wait">
              {!showGate && (
                <motion.div
                  key="overlay"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="absolute inset-0 z-10 flex flex-col items-center justify-center rounded-xl bg-gradient-to-b from-white/60 via-white/80 to-white/95 dark:from-gray-900/60 dark:via-gray-900/80 dark:to-gray-900/95 backdrop-blur-[1px] p-6"
                >
                  <p className="text-base sm:text-lg font-semibold text-gray-900 dark:text-white text-center mb-2">
                    Desbloqueie insights exclusivos
                  </p>
                  <p className="text-xs sm:text-sm text-gray-500 dark:text-gray-400 text-center mb-4 max-w-xs">
                    Coloque seu email ou WhatsApp para ver os insights
                    completos — sem cadastro.
                  </p>
                  <button
                    type="button"
                    onClick={handleUnlockStart}
                    className="inline-flex items-center justify-center px-6 py-2.5 bg-brand-blue text-white font-semibold text-sm rounded-lg hover:bg-blue-700 transition-all duration-200 shadow-sm hover:shadow-md"
                    data-testid="aha-unlock-button"
                  >
                    Desbloquear insight
                  </button>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Gate form */}
            <AnimatePresence mode="wait">
              {showGate && (
                <motion.div
                  key="gate"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="absolute inset-0 z-10 flex flex-col items-center justify-center rounded-xl bg-gradient-to-b from-white/80 via-white/90 to-white dark:from-gray-900/80 dark:via-gray-900/90 dark:to-gray-900 backdrop-blur-[2px] p-6"
                >
                  <p className="text-base sm:text-lg font-semibold text-gray-900 dark:text-white text-center mb-1">
                    Veja todos os insights
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 text-center mb-4">
                    Coloque seu email ou WhatsApp para continuar — sem
                    compromisso.
                  </p>
                  <form
                    onSubmit={handleSubmit}
                    className="w-full max-w-sm flex flex-col gap-3"
                  >
                    <label htmlFor="aha-gate-contact" className="sr-only">
                      Email ou WhatsApp
                    </label>
                    <input
                      id="aha-gate-contact"
                      type="text"
                      value={contact}
                      onChange={(e) => {
                        setContact(e.target.value);
                        setError(false);
                      }}
                      placeholder="Seu email ou WhatsApp"
                      className="w-full px-4 py-2.5 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm text-gray-900 dark:text-white placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-brand-blue/40"
                      autoFocus
                      required
                      aria-label="Email ou WhatsApp"
                    />
                    {error && (
                      <p className="text-xs text-red-600" role="alert">
                        Informe um email ou telefone válido.
                      </p>
                    )}
                    <button
                      type="submit"
                      disabled={persisting}
                      className="w-full px-5 py-2.5 bg-brand-blue text-white font-semibold text-sm rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-wait"
                      data-testid="aha-gate-submit"
                    >
                      {persisting ? 'Enviando…' : 'Ver insights completos'}
                    </button>
                  </form>
                  <button
                    type="button"
                    onClick={() => setShowGate(false)}
                    className="mt-3 text-xs text-gray-600 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
                  >
                    Voltar
                  </button>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}

        {/* Revealed blurred cards (after unlock) */}
        {hasBlurred && unlocked && (
          <div className="col-span-1 sm:col-span-2 lg:col-span-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {blurredCards.map((card, idx) => (
                <InsightCardView
                  key={card.id}
                  card={card}
                  index={blurThreshold + idx}
                  isBlurred={false}
                />
              ))}
            </div>

            {/* Post-unlock CTA */}
            <AnimatePresence>
              {postUnlockCta && (
                <motion.div
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.4, delay: 0.3 }}
                  className="mt-6 rounded-xl border border-brand-blue/30 bg-gradient-to-r from-brand-blue/5 to-blue-50 dark:from-brand-blue/10 dark:to-blue-950/20 p-5 sm:p-6 text-center"
                  data-testid="aha-post-unlock-cta"
                >
                  <p className="text-base font-semibold text-gray-900 dark:text-white mb-2">
                    Quer analisar seus próprios editais?
                  </p>
                  <p className="text-xs sm:text-sm text-gray-500 dark:text-gray-400 mb-4 max-w-md mx-auto">
                    Receba alertas automáticos de oportunidades, análise de
                    viabilidade com IA e muito mais.
                  </p>
                  <Link
                    href={postUnlockCta.href}
                    onClick={() =>
                      trackPseoEvent('value_cta_click', {
                        source_template: sourceTemplate,
                        entity_id: entityId,
                        setor,
                        uf,
                        component: 'aha_moment_panel',
                        destination: postUnlockCta.href,
                      })
                    }
                    className="inline-block px-6 py-2.5 bg-brand-blue text-white font-semibold text-sm rounded-lg hover:bg-blue-700 transition-colors shadow-sm"
                  >
                    {postUnlockCta.label} →
                  </Link>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}
      </div>
    </section>
  );
}
