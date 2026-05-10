"use client";

/**
 * #1011 UPGRADE-PATH-013: Pro mensal -> Lifetime founder upgrade modal.
 *
 * Two-step UX:
 *   1. Preview — fetches /api/subscriptions/upgrade-to-lifetime/preview, shows
 *      pro-rata math (paid credit, lifetime price R$997, net charge).
 *   2. Confirm — POSTs /api/subscriptions/upgrade-to-lifetime which cancels
 *      the active subscription with proration and returns a Stripe checkout URL.
 *
 * The backend is the source of truth for cap availability + idempotency. The
 * estimated_credit shown here is best-effort; Stripe applies the exact credit
 * automatically when the customer completes checkout.
 */

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Modal } from "../Modal";

interface UpgradePreview {
  eligible: boolean;
  reason: string;
  lifetime_price_brl_cents: number;
  seats_remaining: number;
  seats_total: number;
  estimated_credit_brl_cents: number;
  net_charge_brl_cents: number;
  has_active_subscription: boolean;
  is_already_founder: boolean;
}

interface Props {
  isOpen: boolean;
  onClose: () => void;
  accessToken: string;
}

const REASON_COPY: Record<string, string> = {
  already_founder: "Você já é fundador SmartLic.",
  no_active_subscription: "Não encontramos uma assinatura ativa para upgrade.",
  founding_cap_reached: "As 50 vagas Fundadores já foram preenchidas.",
  founding_deadline_passed: "O período de inscrição Fundadores terminou.",
  founding_paused: "Inscrições Fundadores estão temporariamente pausadas.",
  founders_offer_disabled: "A oferta Fundadores não está disponível agora.",
  unavailable: "Não foi possível validar disponibilidade. Tente novamente em instantes.",
};

function formatBRL(cents: number): string {
  return (cents / 100).toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
    minimumFractionDigits: 2,
  });
}

export function UpgradeToLifetimeModal({ isOpen, onClose, accessToken }: Props) {
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [preview, setPreview] = useState<UpgradePreview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) {
      setPreview(null);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetch("/api/subscriptions/upgrade-to-lifetime/preview", {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
      .then(async (res) => {
        if (!res.ok) {
          throw new Error("preview_http_" + res.status);
        }
        return (await res.json()) as UpgradePreview;
      })
      .then((data) => {
        if (cancelled) return;
        setPreview(data);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "preview_error");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [isOpen, accessToken]);

  const handleConfirm = async () => {
    if (!preview?.eligible) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch("/api/subscriptions/upgrade-to-lifetime", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ confirmed: true }),
      });
      if (!res.ok) {
        const data = (await res.json().catch(() => ({}))) as {
          detail?: string | { message?: string; error_code?: string };
        };
        const detailMsg =
          typeof data.detail === "string"
            ? data.detail
            : data.detail?.message || "Erro ao iniciar upgrade.";
        throw new Error(detailMsg);
      }
      const data = (await res.json()) as { checkout_url: string };
      toast.success("Redirecionando para o checkout...");
      window.location.href = data.checkout_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao iniciar upgrade.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Virar Fundador Vitalício"
      description="Aproveite seu acesso atual e converta para o plano vitalício R$997 (uma única vez)"
      size="md"
    >
      {loading && (
        <div className="py-8 text-center text-[var(--ink-secondary)]" data-testid="upgrade-loading">
          Calculando proporcional...
        </div>
      )}

      {!loading && error && (
        <div className="py-4 text-sm text-[var(--error)]" role="alert" data-testid="upgrade-error">
          {error}
        </div>
      )}

      {!loading && preview && !preview.eligible && (
        <div className="py-4 text-sm text-[var(--ink-secondary)]" data-testid="upgrade-not-eligible">
          {REASON_COPY[preview.reason] ||
            "Você não está elegível para este upgrade no momento."}
        </div>
      )}

      {!loading && preview && preview.eligible && (
        <div className="space-y-4" data-testid="upgrade-preview">
          <div className="rounded-input border border-[var(--border)] bg-[var(--surface-1)] p-4 space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-[var(--ink-secondary)]">Plano vitalício</span>
              <span className="font-medium text-[var(--ink)]" data-testid="preview-lifetime-price">
                {formatBRL(preview.lifetime_price_brl_cents)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--ink-secondary)]">Crédito estimado da sua assinatura atual</span>
              <span className="font-medium text-emerald-700 dark:text-emerald-400" data-testid="preview-credit">
                -{formatBRL(preview.estimated_credit_brl_cents)}
              </span>
            </div>
            <div className="border-t border-[var(--border)] pt-2 flex justify-between">
              <span className="text-[var(--ink)] font-medium">Você paga agora</span>
              <span className="font-semibold text-[var(--ink)]" data-testid="preview-net-charge">
                {formatBRL(preview.net_charge_brl_cents)}
              </span>
            </div>
          </div>

          <p className="text-xs text-[var(--ink-muted)]">
            Sua assinatura atual será cancelada e o crédito proporcional aplicado
            automaticamente pelo Stripe no checkout. Vagas restantes:{" "}
            <strong>{preview.seats_remaining} de {preview.seats_total}</strong>.
          </p>

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="flex-1 py-2.5 px-4 rounded-button border border-[var(--border)] text-[var(--ink)] hover:bg-[var(--surface-1)] transition-colors text-sm font-medium disabled:opacity-50"
              data-testid="upgrade-cancel-btn"
            >
              Agora não
            </button>
            <button
              type="button"
              onClick={handleConfirm}
              disabled={submitting}
              className="flex-1 py-2.5 px-4 rounded-button bg-[var(--brand-navy)] text-white hover:bg-[var(--brand-blue)] transition-colors text-sm font-medium disabled:opacity-50"
              data-testid="upgrade-confirm-btn"
            >
              {submitting ? "Processando..." : "Confirmar upgrade"}
            </button>
          </div>
        </div>
      )}
    </Modal>
  );
}
