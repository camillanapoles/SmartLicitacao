"use client";

/**
 * Issue #1008 (COPY-HALL-009) — opt-in toggle for /fundadores/hall.
 *
 * Renders a checkbox + optional display name + optional logo URL fields. On
 * change, calls POST /api/founders-hall/consent (Next.js proxy) with the
 * user's session token. LGPD: default is opt-OUT; toggle is the only way
 * to opt in or out.
 *
 * Self-contained (no parent prop wiring) so it can be dropped into the
 * perfil page without restructuring the surrounding form.
 */

import { useState, useRef, useEffect, useCallback } from "react";
import { toast } from "sonner";
import Link from "next/link";
import { useUser } from "../../../contexts/UserContext";

const PERSIST_DEBOUNCE_MS = 500;

interface ConsentResponse {
  consent: boolean;
  display_name?: string | null;
  logo_url?: string | null;
  is_founder?: boolean;
}

interface Props {
  /** Initial consent state (FALSE for users who haven't toggled). */
  initialConsent?: boolean;
  /** Initial display name. */
  initialDisplayName?: string | null;
  /** Initial logo URL. */
  initialLogoUrl?: string | null;
  /**
   * If FALSE the toggle is rendered disabled with copy explaining the user
   * needs to be a founder. Defaults to TRUE so users still see the section
   * (graceful UX).
   */
  isFounder?: boolean;
}

export default function HallOfFoundersConsent({
  initialConsent = false,
  initialDisplayName = "",
  initialLogoUrl = "",
  isFounder = true,
}: Props) {
  const { session } = useUser();
  const [consent, setConsent] = useState<boolean>(initialConsent);
  const [displayName, setDisplayName] = useState<string>(initialDisplayName ?? "");
  const [logoUrl, setLogoUrl] = useState<string>(initialLogoUrl ?? "");
  const [saving, setSaving] = useState(false);

  // Debounced opt-in field persistence — prevents flooding the backend when
  // the user blurs both fields in quick succession. Toggle clicks bypass the
  // debounce so consent flips remain instantaneous.
  const blurTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  async function persist(nextConsent: boolean) {
    if (!session?.access_token) {
      toast.error("Sessão expirada. Faça login novamente.");
      return;
    }
    setSaving(true);
    try {
      const body: Record<string, unknown> = { consent: nextConsent };
      if (nextConsent) {
        if (displayName.trim()) body.display_name = displayName.trim();
        if (logoUrl.trim()) body.logo_url = logoUrl.trim();
      }
      const r = await fetch("/api/founders-hall/consent", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.access_token}`,
        },
        body: JSON.stringify(body),
      });
      if (!r.ok) {
        toast.error("Não foi possível atualizar a preferência. Tente novamente.");
        // Revert local state
        setConsent(!nextConsent);
        return;
      }
      const data = (await r.json()) as ConsentResponse;
      setConsent(Boolean(data.consent));
      if (typeof data.display_name === "string") setDisplayName(data.display_name);
      if (typeof data.logo_url === "string") setLogoUrl(data.logo_url);
      toast.success(
        nextConsent
          ? "Você está listado no Hall dos Fundadores."
          : "Sua listagem pública foi removida.",
      );
    } catch {
      toast.error("Erro de rede. Tente novamente.");
      setConsent(!nextConsent);
    } finally {
      setSaving(false);
    }
  }

  function onToggle(e: React.ChangeEvent<HTMLInputElement>) {
    const next = e.target.checked;
    setConsent(next);
    // Cancel any pending field-blur flush; the toggle takes precedence.
    if (blurTimerRef.current) {
      clearTimeout(blurTimerRef.current);
      blurTimerRef.current = null;
    }
    void persist(next);
  }

  const scheduleBlurPersist = useCallback(() => {
    if (!consent) return;
    if (blurTimerRef.current) clearTimeout(blurTimerRef.current);
    blurTimerRef.current = setTimeout(() => {
      blurTimerRef.current = null;
      void persist(true);
    }, PERSIST_DEBOUNCE_MS);
    // persist closes over current state via setState getters — intentional.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [consent]);

  // Flush any pending debounce on unmount so we don't drop the user's edits.
  useEffect(() => {
    return () => {
      if (blurTimerRef.current) {
        clearTimeout(blurTimerRef.current);
        blurTimerRef.current = null;
        void persist(true);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <section
      aria-labelledby="hall-consent-heading"
      className="p-6 bg-[var(--surface-0)] border border-[var(--border)] rounded-card"
    >
      <h2
        id="hall-consent-heading"
        className="text-lg font-semibold text-[var(--ink-primary)]"
      >
        Hall dos Fundadores
      </h2>
      <p className="mt-2 text-sm text-[var(--ink-secondary)]">
        Aparecer no{" "}
        <Link href="/fundadores/hall" className="underline hover:no-underline">
          /fundadores/hall
        </Link>{" "}
        é opcional (LGPD). Se você ativar, sua empresa será listada publicamente.
        Você pode desativar a qualquer momento.
      </p>

      {!isFounder ? (
        <p className="mt-4 text-sm text-[var(--ink-secondary)] italic">
          Disponível apenas para Fundadores. Saiba mais em{" "}
          <Link href="/fundadores" className="underline hover:no-underline">
            /fundadores
          </Link>
          .
        </p>
      ) : null}

      <label className="mt-4 flex items-start gap-3">
        <input
          type="checkbox"
          className="mt-1 h-4 w-4"
          checked={consent}
          onChange={onToggle}
          disabled={saving || !isFounder}
          aria-describedby="hall-consent-help"
        />
        <span className="text-sm text-[var(--ink-primary)]">
          Sim, quero aparecer publicamente no Hall dos Fundadores.
        </span>
      </label>
      <p id="hall-consent-help" className="ml-7 mt-1 text-xs text-[var(--ink-secondary)]">
        Você pode desmarcar a qualquer momento. Remoção em até 5 minutos.
      </p>

      {consent && isFounder ? (
        <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
          <label className="block text-sm">
            <span className="text-[var(--ink-secondary)]">Nome de exibição (opcional)</span>
            <input
              type="text"
              maxLength={120}
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              onBlur={scheduleBlurPersist}
              disabled={saving}
              placeholder="Sua empresa, LTDA"
              className="mt-1 w-full rounded-md border border-[var(--border)] bg-[var(--surface-0)] px-3 py-2 text-sm"
            />
          </label>
          <label className="block text-sm">
            <span className="text-[var(--ink-secondary)]">URL do logo (opcional)</span>
            <input
              type="url"
              maxLength={500}
              value={logoUrl}
              onChange={(e) => setLogoUrl(e.target.value)}
              onBlur={scheduleBlurPersist}
              disabled={saving}
              placeholder="https://exemplo.com/logo.png"
              className="mt-1 w-full rounded-md border border-[var(--border)] bg-[var(--surface-0)] px-3 py-2 text-sm"
            />
          </label>
        </div>
      ) : null}
    </section>
  );
}
