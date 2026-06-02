"use client";

/**
 * CONV-018: 3-question user segmentation form for journey personalization.
 *
 * Asks the user:
 *   1. "O que sua empresa vende?" (segmento_principal — sector autocomplete)
 *   2. "Onde sua empresa atua?" (ufs_atuacao — multi-select)
 *   3. "Qual seu objetivo principal?" (objetivo_tipo — radio group)
 *
 * The component is self-contained with its own step navigation and submits
 * to POST /api/segment/save.
 */

import { useState, useMemo, useCallback } from "react";
import { SETORES_FALLBACK } from "@/app/buscar/hooks/filters/sectorData";
import { UFS, UF_NAMES } from "@/lib/constants/uf-names";
import type { Setor } from "@/app/types";
import { useAuth } from "@/app/components/AuthProvider";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ObjetivoTipo = "vencer_licitacao" | "subcontratar" | "monitorar";

interface SegmentFormProps {
  /** Called after successful submission. */
  onComplete?: () => void;
  /** Pre-filled UF list from profile context. */
  prefillUfs?: string[];
  /** Pre-filled sector ID. */
  prefillSetor?: number;
  /** Custom submit button text for the last step. */
  submitLabel?: string;
}

const OBJETIVO_OPTIONS: { value: ObjetivoTipo; label: string; descricao: string }[] = [
  {
    value: "vencer_licitacao",
    label: "Vencer Licitações",
    descricao: "Encontrar e ganhar contratos públicos para minha empresa",
  },
  {
    value: "subcontratar",
    label: "Subcontratar",
    descricao: "Atuar como fornecedor terceirizado em contratos públicos",
  },
  {
    value: "monitorar",
    label: "Monitorar o Mercado",
    descricao: "Acompanhar editais e tendências sem necessariamente concorrer",
  },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SegmentForm({
  onComplete,
  prefillUfs,
  prefillSetor,
  submitLabel = "Salvar",
}: SegmentFormProps) {
  const { session } = useAuth();

  // Step state
  const [step, setStep] = useState(0);
  const totalSteps = 3;

  // Form data
  const [segmentoPrincipal, setSegmentoPrincipal] = useState<number | null>(
    prefillSetor ?? null,
  );
  const [ufsSelecionadas, setUfsSelecionadas] = useState<string[]>(
    prefillUfs ?? [],
  );
  const [objetivoTipo, setObjetivoTipo] = useState<ObjetivoTipo | null>(null);

  // Sector autocomplete
  const [sectorSearch, setSectorSearch] = useState("");
  const [sectorOpen, setSectorOpen] = useState(false);

  // Submission state
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Filterable sector list (id is a string, we assign numeric IDs by index+1)
  const sectorList = useMemo(
    () =>
      SETORES_FALLBACK.map((s: Setor, i: number) => ({
        ...s,
        numericId: i + 1,
      })),
    [],
  );

  const filteredSectors = useMemo(
    () =>
      sectorSearch.trim()
        ? sectorList.filter(
            (s) =>
              s.name.toLowerCase().includes(sectorSearch.toLowerCase()) ||
              s.description.toLowerCase().includes(sectorSearch.toLowerCase()),
          )
        : sectorList,
    [sectorList, sectorSearch],
  );

  const selectedSector = useMemo(
    () => sectorList.find((s) => s.numericId === segmentoPrincipal),
    [sectorList, segmentoPrincipal],
  );

  // UF toggle
  const toggleUf = useCallback((uf: string) => {
    setUfsSelecionadas((prev) =>
      prev.includes(uf) ? prev.filter((u) => u !== uf) : [...prev, uf],
    );
  }, []);

  // Select all / clear UFs
  const selectAllUfs = useCallback(() => setUfsSelecionadas([...UFS]), []);
  const clearUfs = useCallback(() => setUfsSelecionadas([]), []);

  // Navigation
  const canProceed = (): boolean => {
    if (step === 0) return segmentoPrincipal !== null;
    if (step === 1) return ufsSelecionadas.length > 0;
    if (step === 2) return objetivoTipo !== null;
    return true;
  };

  const handleNext = () => {
    if (!canProceed()) return;
    if (step < totalSteps - 1) {
      setStep((s) => s + 1);
    } else {
      handleSubmit();
    }
  };

  const handleBack = () => {
    if (step > 0) setStep((s) => s - 1);
  };

  // Submit
  const handleSubmit = async () => {
    if (!session?.access_token) return;
    setSubmitting(true);
    setError(null);

    try {
      const res = await fetch("/api/segment/save", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          segmento_principal: segmentoPrincipal,
          objetivo_tipo: objetivoTipo,
        }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || body.message || "Erro ao salvar");
      }

      setSuccess(true);
      onComplete?.();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Erro ao salvar segmentação",
      );
    } finally {
      setSubmitting(false);
    }
  };

  // Success state
  if (success) {
    return (
      <div className="rounded-xl bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 p-6 text-center">
        <p className="text-green-800 dark:text-green-200 font-medium text-base">
          Segmentação salva com sucesso!
        </p>
      </div>
    );
  }

  return (
    <div className="w-full">
      {/* Step indicator */}
      <div className="flex items-center gap-2 mb-6">
        {Array.from({ length: totalSteps }).map((_, i) => (
          <div key={i} className="flex items-center gap-2 flex-1">
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-colors ${
                i === step
                  ? "bg-[var(--brand-blue)] text-white"
                  : i < step
                    ? "bg-green-500 text-white"
                    : "bg-[var(--surface-1)] text-[var(--ink-secondary)]"
              }`}
            >
              {i < step ? (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
              ) : (
                i + 1
              )}
            </div>
            {i < totalSteps - 1 && (
              <div
                className={`flex-1 h-0.5 rounded transition-colors ${
                  i < step ? "bg-green-500" : "bg-[var(--border)]"
                }`}
              />
            )}
          </div>
        ))}
      </div>

      {/* Step 1: Sector autocomplete */}
      {step === 0 && (
        <div className="space-y-4">
          <div>
            <h3 className="text-lg font-semibold text-[var(--ink)]">
              O que sua empresa vende?
            </h3>
            <p className="text-sm text-[var(--ink-secondary)] mt-1">
              Selecione o setor mais próximo do seu ramo de atuação.
            </p>
          </div>

          {/* Sector combobox */}
          <div className="relative">
            <input
              type="text"
              value={selectedSector ? selectedSector.name : sectorSearch}
              onChange={(e) => {
                setSectorSearch(e.target.value);
                setSegmentoPrincipal(null);
                setSectorOpen(true);
              }}
              onFocus={() => setSectorOpen(true)}
              onBlur={() => {
                // Delay closing to allow click on option
                setTimeout(() => setSectorOpen(false), 200);
              }}
              placeholder="Digite para buscar um setor..."
              className="w-full px-4 py-3 rounded-lg border border-[var(--border)] bg-[var(--surface-0)] text-[var(--ink)] placeholder:text-[var(--ink-secondary)] focus:outline-none focus:ring-2 focus:ring-[var(--brand-blue)] focus:border-transparent transition-all"
              aria-label="Buscar setor"
              data-testid="segment-sector-input"
            />

            {sectorOpen && (
              <div
                className="absolute z-10 mt-1 w-full max-h-60 overflow-y-auto rounded-lg border border-[var(--border)] bg-[var(--surface-0)] shadow-lg"
                data-testid="segment-sector-dropdown"
              >
                {filteredSectors.length === 0 ? (
                  <div className="px-4 py-3 text-sm text-[var(--ink-secondary)]">
                    Nenhum setor encontrado
                  </div>
                ) : (
                  filteredSectors.map((s) => (
                    <button
                      key={s.numericId}
                      type="button"
                      onMouseDown={(e) => {
                        e.preventDefault();
                        setSegmentoPrincipal(s.numericId);
                        setSectorSearch(s.name);
                        setSectorOpen(false);
                      }}
                      className={`w-full text-left px-4 py-3 text-sm hover:bg-[var(--surface-1)] transition-colors ${
                        segmentoPrincipal === s.numericId
                          ? "bg-[var(--surface-1)] font-medium text-[var(--brand-blue)]"
                          : "text-[var(--ink)]"
                      }`}
                      data-testid={`segment-sector-option-${s.id}`}
                    >
                      <span className="block font-medium">{s.name}</span>
                      <span className="block text-xs text-[var(--ink-secondary)] mt-0.5 line-clamp-1">
                        {s.description}
                      </span>
                    </button>
                  ))
                )}
              </div>
            )}
          </div>

          {selectedSector && (
            <p className="text-sm text-green-600 dark:text-green-400 font-medium">
              Setor selecionado: {selectedSector.name}
            </p>
          )}
        </div>
      )}

      {/* Step 2: UF multi-select */}
      {step === 1 && (
        <div className="space-y-4">
          <div>
            <h3 className="text-lg font-semibold text-[var(--ink)]">
              Onde sua empresa atua?
            </h3>
            <p className="text-sm text-[var(--ink-secondary)] mt-1">
              Selecione os estados onde você quer encontrar oportunidades.
            </p>
          </div>

          {/* Quick actions */}
          <div className="flex items-center gap-3 text-sm">
            <button
              type="button"
              onClick={selectAllUfs}
              className="text-[var(--brand-blue)] hover:underline font-medium"
              data-testid="segment-select-all-ufs"
            >
              Selecionar todos
            </button>
            <button
              type="button"
              onClick={clearUfs}
              className="text-[var(--ink-secondary)] hover:underline"
              data-testid="segment-clear-ufs"
            >
              Limpar
            </button>
            <span className="text-[var(--ink-secondary)] ml-auto">
              {ufsSelecionadas.length}/{UFS.length} selecionados
            </span>
          </div>

          {/* UF grid */}
          <div className="grid grid-cols-3 sm:grid-cols-5 gap-2">
            {UFS.map((uf) => {
              const selected = ufsSelecionadas.includes(uf);
              return (
                <button
                  key={uf}
                  type="button"
                  onClick={() => toggleUf(uf)}
                  className={`flex items-center gap-1.5 px-3 py-2.5 rounded-lg border text-sm transition-all ${
                    selected
                      ? "border-[var(--brand-blue)] bg-[var(--brand-blue)]/10 text-[var(--brand-blue)] font-medium"
                      : "border-[var(--border)] bg-[var(--surface-0)] text-[var(--ink)] hover:border-[var(--brand-blue)]/40"
                  }`}
                  data-testid={`segment-uf-${uf}`}
                  aria-pressed={selected}
                >
                  <span className="font-semibold w-6">{uf}</span>
                  <span className="hidden sm:inline text-xs truncate">
                    {UF_NAMES[uf]}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Step 3: Objective radio group */}
      {step === 2 && (
        <div className="space-y-4">
          <div>
            <h3 className="text-lg font-semibold text-[var(--ink)]">
              Qual seu objetivo principal?
            </h3>
            <p className="text-sm text-[var(--ink-secondary)] mt-1">
              Isso nos ajuda a personalizar sua experiência.
            </p>
          </div>

          <div className="space-y-3">
            {OBJETIVO_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setObjetivoTipo(opt.value)}
                className={`w-full text-left p-4 rounded-lg border transition-all ${
                  objetivoTipo === opt.value
                    ? "border-[var(--brand-blue)] bg-[var(--brand-blue)]/10 ring-2 ring-[var(--brand-blue)]/20"
                    : "border-[var(--border)] bg-[var(--surface-0)] hover:border-[var(--brand-blue)]/40"
                }`}
                data-testid={`segment-objetivo-${opt.value}`}
                aria-pressed={objetivoTipo === opt.value}
              >
                <div className="flex items-start gap-3">
                  <div
                    className={`mt-0.5 w-5 h-5 rounded-full border-2 flex items-center justify-center flex-shrink-0 ${
                      objetivoTipo === opt.value
                        ? "border-[var(--brand-blue)]"
                        : "border-[var(--ink-secondary)]"
                    }`}
                  >
                    {objetivoTipo === opt.value && (
                      <div className="w-2.5 h-2.5 rounded-full bg-[var(--brand-blue)]" />
                    )}
                  </div>
                  <div>
                    <span className="block font-medium text-[var(--ink)]">
                      {opt.label}
                    </span>
                    <span className="block text-sm text-[var(--ink-secondary)] mt-0.5">
                      {opt.descricao}
                    </span>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="mt-4 p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-sm text-red-700 dark:text-red-300">
          {error}
        </div>
      )}

      {/* Navigation */}
      <div className="flex items-center justify-between mt-8 pt-4 border-t border-[var(--border)]">
        <div>
          {step > 0 && (
            <button
              type="button"
              onClick={handleBack}
              disabled={submitting}
              className="min-h-[44px] px-4 py-2 text-sm text-[var(--ink-secondary)] hover:text-[var(--ink)] transition-colors disabled:opacity-40"
              data-testid="segment-btn-back"
            >
              Voltar
            </button>
          )}
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleNext}
            disabled={!canProceed() || submitting}
            className="min-h-[44px] px-6 py-2.5 rounded-lg bg-[var(--brand-blue)] text-white text-sm font-medium disabled:opacity-40 hover:bg-[var(--brand-blue-hover)] transition-colors"
            data-testid="segment-btn-continue"
          >
            {step === totalSteps - 1
              ? submitting
                ? "Salvando..."
                : submitLabel
              : "Continuar"}
          </button>
        </div>
      </div>
    </div>
  );
}
