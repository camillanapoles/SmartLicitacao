"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useAnalytics } from "../../../hooks/useAnalytics";
import { EmailDeadEndModal } from "./EmailDeadEndModal";

interface SignupSuccessProps {
  email: string;
  isConfirmed: boolean;
  countdown: number;
  isResending: boolean;
  onResend: () => void;
  onChangeEmail: () => void;
  /** Timestamp (ms) when setSuccess(true) was called — used for timeout calculation. */
  signupStartedAt: number;
  /** Rollout branch from page.tsx state — included in email_verification_pending event. */
  rolloutBranch?: string | null;
  /** Shared ref so page.tsx polling increments and SignupSuccess reads. */
  pollingIterationsRef?: React.MutableRefObject<number>;
  /** Shared ref updated by page.tsx handleResend — used in timeout event payload. */
  lastResendAtRef?: React.MutableRefObject<number | null>;
}

const TIMEOUT_5MIN_MS = 5 * 60 * 1000;

export function SignupSuccess({
  email,
  isConfirmed,
  countdown,
  isResending,
  onResend,
  onChangeEmail,
  signupStartedAt,
  rolloutBranch,
  pollingIterationsRef,
  lastResendAtRef,
}: SignupSuccessProps) {
  const { trackEvent } = useAnalytics();
  const pendingFiredRef = useRef(false);
  const timeoutFiredRef = useRef(false);
  const [showDeadEndModal, setShowDeadEndModal] = useState(false);
  const emailDomain = email.split("@")[1] ?? "";

  // AC1: Fire email_verification_pending ONCE on mount.
  // useRef gate prevents double-fire in React StrictMode.
  // LGPD: only email_domain is logged, never full email.
  useEffect(() => {
    if (pendingFiredRef.current) return;
    pendingFiredRef.current = true;
    trackEvent("email_verification_pending", {
      email_domain: emailDomain,
      rollout_branch: rolloutBranch ?? "unknown",
      signup_method: "email", // Google OAuth goes through /auth/callback — never reaches this screen
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // AC3: After 5min without confirmation, fire timeout event + show dead-end modal.
  useEffect(() => {
    if (isConfirmed || timeoutFiredRef.current) return;

    const elapsed = Date.now() - signupStartedAt;
    const remainingMs = TIMEOUT_5MIN_MS - elapsed;
    if (remainingMs <= 0) {
      // Already past 5min (e.g. component remounted) — fire immediately
      if (!timeoutFiredRef.current) {
        timeoutFiredRef.current = true;
        const lastResendMs = lastResendAtRef?.current
          ? Date.now() - lastResendAtRef.current
          : null;
        trackEvent("email_verification_timeout", {
          email_domain: emailDomain,
          polling_iterations: pollingIterationsRef?.current ?? 0,
          last_resend_attempt_ms_ago: lastResendMs,
        });
        setShowDeadEndModal(true);
      }
      return;
    }

    const timerId = setTimeout(() => {
      if (isConfirmed || timeoutFiredRef.current) return;
      timeoutFiredRef.current = true;

      const lastResendMs = lastResendAtRef?.current
        ? Date.now() - lastResendAtRef.current
        : null;

      trackEvent("email_verification_timeout", {
        email_domain: emailDomain,
        polling_iterations: pollingIterationsRef?.current ?? 0,
        last_resend_attempt_ms_ago: lastResendMs,
      });

      setShowDeadEndModal(true);
    }, remainingMs);

    return () => clearTimeout(timerId);
  }, [isConfirmed]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="min-h-screen flex items-center justify-center bg-canvas">
      {showDeadEndModal && (
        <EmailDeadEndModal
          onClose={() => setShowDeadEndModal(false)}
          onResend={onResend}
          isResending={isResending}
          countdown={countdown}
        />
      )}

      <div className="w-full max-w-md p-8 bg-surface-0 rounded-card shadow-lg text-center">
        {/* AC10: Confirmed transition */}
        {isConfirmed ? (
          <>
            <div className="text-4xl mb-4" data-testid="confirmed-icon">&#10003;</div>
            <h2 className="text-xl font-semibold text-green-600 mb-2">
              Email confirmado!
            </h2>
            <p className="text-ink-secondary">Redirecionando...</p>
          </>
        ) : (
          <>
            {/* AC1: Mail icon */}
            <div className="text-4xl mb-4" data-testid="mail-icon">&#9993;</div>

            <h2 className="text-xl font-semibold text-ink mb-2">
              Confirme seu email
            </h2>

            <p className="text-ink-secondary mb-4">
              Enviamos um link de confirmação para:
              <br />
              <strong>{email}</strong>
            </p>

            {/* AC7: Polling indicator */}
            <p className="text-sm text-brand-blue mb-4" data-testid="polling-indicator">
              Aguardando confirmação...
            </p>

            {/* AC1/AC2: Resend button with countdown */}
            <button
              onClick={onResend}
              disabled={countdown > 0 || isResending}
              data-testid="resend-button"
              className="w-full py-3 bg-brand-blue text-white rounded-button
                         font-semibold disabled:bg-gray-300 disabled:text-gray-500
                         disabled:cursor-not-allowed hover:opacity-90 transition-colors"
            >
              {isResending
                ? "Reenviando..."
                : countdown > 0
                  ? `Reenviar em ${countdown}s`
                  : "Reenviar email"}
            </button>

            {/* AC11: Spam helper section */}
            <div className="mt-6 p-4 bg-surface-1 rounded-input text-left">
              <h3 className="font-semibold text-sm mb-2 text-ink">
                Não recebeu o email?
              </h3>
              <ul className="text-sm space-y-1 text-ink-secondary">
                <li>• Verifique sua caixa de spam/lixo eletrônico</li>
                <li>• Aguarde até 5 minutos</li>
                <li>• Confirme se o email está correto</li>
              </ul>
              {/* AC12: Change email link */}
              <button
                onClick={onChangeEmail}
                data-testid="change-email-link"
                className="text-brand-blue text-sm mt-2 underline hover:opacity-80"
              >
                Alterar email
              </button>
            </div>

            <Link
              href="/login"
              className="mt-4 inline-block text-sm text-ink-muted hover:underline"
            >
              Ir para login
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
