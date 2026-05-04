"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "../../lib/supabase";
import { useAuth } from "../../app/components/AuthProvider";

interface MfaEnforcementBannerProps {
  className?: string;
}

type EnforceReason = "admin" | "consultoria" | "bruteforce" | null;

interface MfaStatus {
  mfa_enabled: boolean;
  enforce_reason: EnforceReason;
  force_mfa_enrollment_until: string | null;
  grace_days_remaining: number | null;
}

/**
 * STORY-317 AC16-17 + MFA-EXT-001 AC8/AC9.
 *
 * Persistent, non-dismissible red banner shown when MFA enrollment is
 * mandatory and the user has not yet enrolled. Variants:
 *
 *   - admin/master  -> "MFA obrigatorio..."  (existing STORY-317 text)
 *   - consultoria   -> "Plano Consultoria requer MFA — configure em N dias"
 *   - bruteforce    -> "Detectamos atividade suspeita..."
 *
 * Reads `/v1/mfa/status` (single source of truth), falling back to a
 * direct Supabase listFactors() probe if the proxy fails — this keeps
 * the existing admin/master variant working even if the backend is
 * temporarily unreachable.
 */
export function MfaEnforcementBanner({ className = "" }: MfaEnforcementBannerProps) {
  const router = useRouter();
  const { isAdmin, session } = useAuth();
  const [status, setStatus] = useState<MfaStatus | null>(null);
  const [fallbackAdmin, setFallbackAdmin] = useState<boolean>(false);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    if (!session) {
      setChecking(false);
      return;
    }

    let cancelled = false;

    (async () => {
      try {
        // Primary: ask the backend so we get the enforce_reason + countdown.
        const accessToken =
          (session as unknown as { access_token?: string })?.access_token ?? "";
        const resp = await fetch("/api/mfa?endpoint=status", {
          method: "GET",
          headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined,
          cache: "no-store",
        });
        if (resp.ok) {
          const data = (await resp.json()) as MfaStatus;
          if (!cancelled) setStatus(data);
          return;
        }
      } catch {
        // fall through to legacy Supabase-direct check
      }

      // Fallback: legacy STORY-317 path (admin-only banner).
      try {
        const { data } = await supabase.auth.mfa.listFactors();
        const hasVerifiedTotp = data?.totp?.some(
          (f: { status: string }) => f.status === "verified"
        );
        if (!cancelled && isAdmin && !hasVerifiedTotp) {
          setFallbackAdmin(true);
        }
      } catch {
        /* best-effort */
      } finally {
        if (!cancelled) setChecking(false);
      }
    })().finally(() => {
      if (!cancelled) setChecking(false);
    });

    return () => {
      cancelled = true;
    };
  }, [session, isAdmin]);

  if (checking) return null;

  // Decide whether to render. Banner is suppressed once MFA is enrolled.
  const enforceReason: EnforceReason = status?.enforce_reason ?? null;
  const mfaEnabled = status?.mfa_enabled ?? false;
  const shouldRender =
    !mfaEnabled && (enforceReason !== null || (fallbackAdmin && status === null));

  if (!shouldRender) return null;

  const grace = status?.grace_days_remaining ?? null;
  const reasonForVariant: EnforceReason = enforceReason ?? "admin";

  let message = "MFA obrigatório para sua conta. Configure a autenticação em dois fatores para continuar.";
  let testReason = "admin";

  if (reasonForVariant === "consultoria") {
    testReason = "consultoria";
    message =
      grace !== null && grace > 0
        ? `Plano Consultoria requer MFA — configure em ${grace} ${grace === 1 ? "dia" : "dias"}.`
        : "Plano Consultoria requer MFA. Configure a autenticação em dois fatores agora.";
  } else if (reasonForVariant === "bruteforce") {
    testReason = "bruteforce";
    message =
      grace !== null && grace > 0
        ? `Detectamos tentativas suspeitas. MFA é obrigatório por ${grace} ${grace === 1 ? "dia" : "dias"}.`
        : "Detectamos tentativas suspeitas. MFA é obrigatório. Configure agora.";
  }

  return (
    <div
      className={`w-full bg-[var(--error)] text-white px-4 py-3 ${className}`}
      role="alert"
      data-testid="mfa-enforcement-banner"
      data-mfa-reason={testReason}
    >
      <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <svg className="w-5 h-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
          <p className="text-sm font-medium">{message}</p>
        </div>
        <button
          onClick={() => router.push("/conta/seguranca")}
          className="flex-shrink-0 px-4 py-1.5 bg-white text-[var(--error)] rounded-button text-sm font-semibold hover:bg-white/90 transition-colors"
        >
          Configurar agora
        </button>
      </div>
    </div>
  );
}
