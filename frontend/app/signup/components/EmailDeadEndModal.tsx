"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";

interface EmailDeadEndModalProps {
  onClose: () => void;
  onResend: () => void;
  isResending: boolean;
  countdown: number;
}

/**
 * CONV-INST-003 AC3: Dead-end modal shown after 5min without email confirmation.
 *
 * Accessibility: role="dialog", aria-modal, aria-labelledby, ESC key, focus trap.
 * LGPD: no full email logged or displayed in tracking events.
 */
export function EmailDeadEndModal({
  onClose,
  onResend,
  isResending,
  countdown,
}: EmailDeadEndModalProps) {
  const headingId = "email-dead-end-title";
  const firstFocusRef = useRef<HTMLButtonElement>(null);
  const lastFocusRef = useRef<HTMLAnchorElement>(null);

  // Focus first element on mount
  useEffect(() => {
    firstFocusRef.current?.focus();
  }, []);

  // ESC key closes modal
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  // Focus trap: Tab cycles within modal
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key !== "Tab") return;
    const focusable = [firstFocusRef.current, lastFocusRef.current].filter(Boolean);
    if (focusable.length < 2) return;
    if (e.shiftKey) {
      if (document.activeElement === focusable[0]) {
        e.preventDefault();
        focusable[focusable.length - 1]?.focus();
      }
    } else {
      if (document.activeElement === focusable[focusable.length - 1]) {
        e.preventDefault();
        focusable[0]?.focus();
      }
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      aria-hidden="false"
      data-testid="email-dead-end-overlay"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={headingId}
        className="relative w-full max-w-sm mx-4 bg-surface-0 rounded-card shadow-xl p-6"
        onKeyDown={handleKeyDown}
        data-testid="email-dead-end-modal"
      >
        {/* Close button */}
        <button
          onClick={onClose}
          aria-label="Fechar"
          className="absolute top-3 right-3 text-ink-muted hover:text-ink text-xl leading-none"
        >
          &times;
        </button>

        {/* Icon */}
        <div className="text-3xl text-center mb-3" aria-hidden="true">
          &#9993;
        </div>

        {/* Headline */}
        <h2
          id={headingId}
          className="text-lg font-semibold text-ink text-center mb-2"
        >
          Email não chegou?
        </h2>

        <p className="text-sm text-ink-secondary text-center mb-5">
          Já se passaram 5 minutos. Tente uma das opções abaixo:
        </p>

        {/* Action (a): Check spam */}
        <button
          ref={firstFocusRef}
          data-testid="dead-end-check-spam"
          className="w-full py-2.5 mb-2 border border-divider rounded-button text-sm
                     text-ink hover:bg-surface-1 transition-colors"
          onClick={onClose}
        >
          Verificar SPAM
        </button>

        {/* Action (b): Resend email */}
        <button
          data-testid="dead-end-resend"
          disabled={countdown > 0 || isResending}
          onClick={() => {
            onResend();
            onClose();
          }}
          className="w-full py-2.5 mb-2 bg-brand-blue text-white rounded-button text-sm
                     font-semibold disabled:bg-gray-300 disabled:text-gray-500
                     disabled:cursor-not-allowed hover:opacity-90 transition-colors"
        >
          {isResending
            ? "Reenviando..."
            : countdown > 0
              ? `Reenviar em ${countdown}s`
              : "Reenviar email"}
        </button>

        {/* Action (c): Support */}
        <Link
          ref={lastFocusRef}
          href="/ajuda"
          data-testid="dead-end-support"
          className="block w-full py-2.5 border border-divider rounded-button text-sm
                     text-ink-secondary text-center hover:bg-surface-1 transition-colors"
        >
          Falar com suporte
        </Link>
      </div>
    </div>
  );
}
