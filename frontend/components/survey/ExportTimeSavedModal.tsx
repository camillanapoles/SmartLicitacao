"use client";

/**
 * BIZ-METRIC-001 (AC7-AC10): Post-export survey modal.
 *
 * Asks the user how long the export would have taken manually. Used
 * to empirically calibrate the dashboard ``hours_saved_per_search``
 * constant (story BIZ-METRIC-001).
 *
 * Usage:
 *   const survey = useExportTimeSavedSurvey({ totalSearches });
 *   ...
 *   await handleDownload();
 *   survey.maybeOpen({ exportType: "excel", searchId, bidCount, exportId });
 *   ...
 *   <ExportTimeSavedModal {...survey.modalProps} />
 *
 * The hook owns frequency throttling (every 3rd export), the lifetime
 * cap (5 surveys per user), and the eligibility gate (>=3 completed
 * searches). The component is intentionally pure presentational.
 */

import React, { useCallback, useEffect, useId, useRef, useState } from "react";

const STORAGE_KEY_COUNT = "smartlic.export_survey.count";
const STORAGE_KEY_EXPORT_TICKS = "smartlic.export_survey.tick";
const STORAGE_KEY_LAST_SUBMITTED_AT = "smartlic.export_survey.last_submitted_at";
const STORAGE_KEY_SESSION_SHOWN = "smartlic.export_survey.shown_in_session";

const FREQUENCY_DIVISOR = 3; // AC8: every Nth export
const LIFETIME_SUBMISSIONS_CAP = 5; // AC8: max submissions per user/lifetime
const MIN_SEARCHES_REQUIRED = 3; // AC10: only after 3+ completed searches

export type ExportType = "excel" | "pdf" | "sheets";

export interface MaybeOpenInput {
  exportType: ExportType;
  searchId?: string | null;
  exportId?: string | null;
  bidCount?: number | null;
}

export interface ExportTimeSavedModalProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: {
    estimatedManualHours: number;
    freeText: string | null;
  }) => Promise<void> | void;
  initialHours?: number;
  isSubmitting?: boolean;
  lastSubmitError?: string | null;
}

export interface UseExportTimeSavedSurveyOptions {
  totalSearches?: number | null;
  fetchImpl?: typeof fetch;
  /** Override session-storage check (testing only). */
  sessionStorageImpl?: Storage;
  /** Override local-storage check (testing only). */
  localStorageImpl?: Storage;
}

interface PendingPayload {
  exportType: ExportType;
  searchId?: string | null;
  exportId?: string | null;
  bidCount?: number | null;
}

interface UseExportTimeSavedSurveyReturn {
  modalProps: ExportTimeSavedModalProps;
  maybeOpen: (input: MaybeOpenInput) => void;
}

function getStorage(impl: Storage | undefined, fallback: () => Storage | null): Storage | null {
  if (impl) return impl;
  try {
    return fallback();
  } catch {
    return null;
  }
}

function getLocal(impl?: Storage): Storage | null {
  return getStorage(impl, () => (typeof window !== "undefined" ? window.localStorage : null));
}

function getSession(impl?: Storage): Storage | null {
  return getStorage(impl, () => (typeof window !== "undefined" ? window.sessionStorage : null));
}

function readInt(storage: Storage | null, key: string, fallback: number): number {
  if (!storage) return fallback;
  const raw = storage.getItem(key);
  if (raw === null) return fallback;
  const n = Number.parseInt(raw, 10);
  return Number.isFinite(n) ? n : fallback;
}

function writeInt(storage: Storage | null, key: string, value: number): void {
  if (!storage) return;
  try {
    storage.setItem(key, String(value));
  } catch {
    // ignore quota / disabled-storage errors
  }
}

export function useExportTimeSavedSurvey(
  opts: UseExportTimeSavedSurveyOptions = {},
): UseExportTimeSavedSurveyReturn {
  const { totalSearches, fetchImpl, sessionStorageImpl, localStorageImpl } = opts;
  const [isOpen, setIsOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [lastSubmitError, setLastSubmitError] = useState<string | null>(null);
  const pendingRef = useRef<PendingPayload | null>(null);

  const fetcher = fetchImpl ?? (typeof window !== "undefined" && typeof window.fetch === "function"
    ? window.fetch.bind(window)
    : null);

  const maybeOpen = useCallback(
    (input: MaybeOpenInput) => {
      const local = getLocal(localStorageImpl);
      const session = getSession(sessionStorageImpl);

      // AC10: minimum search history required.
      if (typeof totalSearches === "number" && totalSearches < MIN_SEARCHES_REQUIRED) {
        return;
      }

      // AC8: lifetime cap on submissions.
      const submissions = readInt(local, STORAGE_KEY_COUNT, 0);
      if (submissions >= LIFETIME_SUBMISSIONS_CAP) return;

      // AC: max once per browser session (prevents back-to-back modal noise).
      if (session?.getItem(STORAGE_KEY_SESSION_SHOWN) === "1") return;

      // AC8: every 3rd export.
      const ticks = readInt(local, STORAGE_KEY_EXPORT_TICKS, 0) + 1;
      writeInt(local, STORAGE_KEY_EXPORT_TICKS, ticks);
      if (ticks % FREQUENCY_DIVISOR !== 0) return;

      pendingRef.current = {
        exportType: input.exportType,
        searchId: input.searchId ?? null,
        exportId: input.exportId ?? null,
        bidCount: input.bidCount ?? null,
      };
      setLastSubmitError(null);
      setIsOpen(true);
      try {
        session?.setItem(STORAGE_KEY_SESSION_SHOWN, "1");
      } catch {
        // ignore
      }
    },
    [totalSearches, sessionStorageImpl, localStorageImpl],
  );

  const onClose = useCallback(() => {
    setIsOpen(false);
    setIsSubmitting(false);
    pendingRef.current = null;
  }, []);

  const onSubmit = useCallback<ExportTimeSavedModalProps["onSubmit"]>(
    async ({ estimatedManualHours, freeText }) => {
      if (!pendingRef.current) return;
      if (!fetcher) {
        setLastSubmitError("Modo offline — não foi possível enviar.");
        return;
      }
      const payload = {
        export_type: pendingRef.current.exportType,
        estimated_manual_hours: estimatedManualHours,
        search_id: pendingRef.current.searchId,
        export_id: pendingRef.current.exportId,
        bid_count: pendingRef.current.bidCount,
        free_text: freeText,
      };
      setIsSubmitting(true);
      setLastSubmitError(null);
      try {
        const res = await fetcher("/api/survey/export-time-saved", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        const local = getLocal(localStorageImpl);
        const submissions = readInt(local, STORAGE_KEY_COUNT, 0) + 1;
        writeInt(local, STORAGE_KEY_COUNT, submissions);
        try {
          local?.setItem(STORAGE_KEY_LAST_SUBMITTED_AT, new Date().toISOString());
        } catch {
          // ignore
        }
        setIsOpen(false);
        pendingRef.current = null;
      } catch (e) {
        setLastSubmitError(
          e instanceof Error ? e.message : "Falha ao enviar — tente novamente.",
        );
      } finally {
        setIsSubmitting(false);
      }
    },
    [fetcher, localStorageImpl],
  );

  return {
    modalProps: {
      open: isOpen,
      onClose,
      onSubmit,
      isSubmitting,
      lastSubmitError,
    },
    maybeOpen,
  };
}

export default function ExportTimeSavedModal(props: ExportTimeSavedModalProps): React.JSX.Element | null {
  const {
    open,
    onClose,
    onSubmit,
    initialHours = 2,
    isSubmitting = false,
    lastSubmitError = null,
  } = props;
  const headingId = useId();
  const sliderId = useId();
  const [hours, setHours] = useState<number>(initialHours);
  const [freeText, setFreeText] = useState<string>("");

  useEffect(() => {
    if (open) {
      setHours(initialHours);
      setFreeText("");
    }
  }, [open, initialHours]);

  useEffect(() => {
    if (!open) return;
    const onKey = (ev: KeyboardEvent) => {
      if (ev.key === "Escape") {
        ev.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (isSubmitting) return;
    if (!Number.isFinite(hours) || hours < 0.5 || hours > 20) return;
    const trimmed = freeText.trim();
    await onSubmit({
      estimatedManualHours: hours,
      freeText: trimmed.length > 0 ? trimmed : null,
    });
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={headingId}
      data-testid="export-time-saved-modal"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
    >
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-md rounded-lg bg-white shadow-lg p-6 space-y-4"
      >
        <h2 id={headingId} className="text-lg font-semibold">
          Sem o SmartLic, quanto tempo isso teria levado?
        </h2>
        <p className="text-sm text-slate-600">
          Sua estimativa nos ajuda a calibrar a métrica de horas economizadas no painel.
          Considere uma busca + análise + planilha equivalente, feitas manualmente.
        </p>

        <div className="space-y-2">
          <label htmlFor={sliderId} className="flex items-center justify-between text-sm font-medium">
            <span>Tempo estimado</span>
            <span data-testid="hours-display" className="text-base font-semibold">
              {hours.toFixed(1)}h
            </span>
          </label>
          <input
            id={sliderId}
            type="range"
            min={0.5}
            max={20}
            step={0.5}
            value={hours}
            onChange={(e) => setHours(Number(e.target.value))}
            disabled={isSubmitting}
            data-testid="hours-slider"
            aria-valuemin={0.5}
            aria-valuemax={20}
            aria-valuenow={hours}
            className="w-full"
          />
          <div className="flex justify-between text-xs text-slate-500">
            <span>0,5h</span>
            <span>20h</span>
          </div>
        </div>

        <div className="space-y-1">
          <label htmlFor="export-survey-freetext" className="text-sm font-medium">
            Como você teria feito antes? (opcional)
          </label>
          <textarea
            id="export-survey-freetext"
            value={freeText}
            onChange={(e) => setFreeText(e.target.value)}
            disabled={isSubmitting}
            maxLength={2000}
            rows={3}
            data-testid="freetext-input"
            className="w-full rounded-md border border-slate-300 p-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {lastSubmitError ? (
          <p className="text-sm text-red-600" data-testid="submit-error">
            {lastSubmitError}
          </p>
        ) : null}

        <div className="flex items-center justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            className="px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 rounded-md disabled:opacity-50"
            data-testid="dismiss-button"
          >
            Pular
          </button>
          <button
            type="submit"
            disabled={isSubmitting}
            className="px-3 py-1.5 text-sm font-medium bg-[var(--brand-navy,#0b2447)] text-white rounded-md hover:bg-[var(--brand-blue-hover,#19376d)] disabled:opacity-50"
            data-testid="submit-button"
          >
            {isSubmitting ? "Enviando…" : "Enviar"}
          </button>
        </div>
      </form>
    </div>
  );
}
