"use client";

import Link from "next/link";
import type { BuscaResult } from "../../../types";
import { OrdenacaoSelect, type OrdenacaoOption } from "../../../components/OrdenacaoSelect";
import GoogleSheetsExportButton from "../GoogleSheetsExportButton";

interface ResultsToolbarProps {
  result: BuscaResult;
  ordenacao: OrdenacaoOption;
  onOrdenacaoChange: (ord: OrdenacaoOption) => void;
  loading: boolean;
  // Excel
  onDownload: () => void;
  downloadLoading: boolean;
  onRegenerateExcel?: () => void;
  excelFailCount?: number;
  excelTimedOut: boolean;
  // Auth/plan
  planInfo: {
    capabilities: { allow_excel: boolean };
  } | null;
  session: { access_token: string } | null;
  isTrialExpired?: boolean;
  paywallApplied?: boolean;
  totalBeforePaywall?: number | null;
  // Sectors/UFs for export label
  sectorName: string;
  ufsSelecionadas: Set<string>;
  // PDF
  onGeneratePdf?: (options: { clientName: string; maxItems: number }) => void;
  pdfLoading?: boolean;
  // Search
  onSearch: () => void;
  // BIZ-METRIC-001: optional pass-through to GoogleSheetsExportButton
  onSheetsExportSucceeded?: (input: { exportType: "sheets"; bidCount: number }) => void;
}

/**
 * TD-007 AC3: ResultsToolbar — sort controls, view mode toggle, items per page, export buttons.
 * Renders the sticky action bar with sort select, Excel/Sheets/PDF buttons, and opportunity count.
 */
export function ResultsToolbar({
  result,
  ordenacao,
  onOrdenacaoChange,
  loading,
  onDownload,
  downloadLoading,
  onRegenerateExcel,
  excelFailCount = 0,
  excelTimedOut,
  planInfo,
  session,
  isTrialExpired,
  paywallApplied,
  totalBeforePaywall,
  sectorName,
  ufsSelecionadas,
  onGeneratePdf,
  pdfLoading,
  onSearch,
  onSheetsExportSucceeded,
}: ResultsToolbarProps) {
  return (
    <div
      className="sticky top-0 z-30 bg-[var(--canvas)] border-b border-[var(--border)] -mx-1 px-1 py-3"
      data-testid="sticky-action-bar"
      id="results-top"
    >
      <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3">
        {/* Row 1: Sort + action buttons */}
        <div className="flex items-center gap-2 flex-wrap">
          <OrdenacaoSelect
            value={ordenacao}
            onChange={onOrdenacaoChange}
            disabled={loading}
          />

          {/* Excel button (compact) */}
          {planInfo?.capabilities.allow_excel && !isTrialExpired && !(paywallApplied && totalBeforePaywall) && (
            <ExcelButton
              result={result}
              onDownload={onDownload}
              downloadLoading={downloadLoading}
              onRegenerateExcel={onRegenerateExcel}
              excelFailCount={excelFailCount}
              excelTimedOut={excelTimedOut}
              loading={loading}
              onSearch={onSearch}
            />
          )}

          {/* Google Sheets button (compact) — AC18 */}
          {planInfo?.capabilities.allow_excel && !isTrialExpired && (
            <GoogleSheetsExportButton
              licitacoes={result.licitacoes}
              searchLabel={`${sectorName} - ${Array.from(ufsSelecionadas).join(', ')}`}
              disabled={downloadLoading}
              session={session}
              onExportSucceeded={onSheetsExportSucceeded}
            />
          )}

          {/* PDF button (compact) */}
          {session?.access_token && result && !isTrialExpired && onGeneratePdf && (
            <button
              onClick={() => onGeneratePdf({ clientName: "", maxItems: 20 })}
              disabled={pdfLoading}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium
                         border border-[var(--brand-navy)] text-[var(--brand-navy)]
                         dark:border-[var(--brand-blue)] dark:text-[var(--brand-blue)]
                         rounded-button hover:bg-[var(--brand-blue-subtle)] transition-colors
                         disabled:opacity-50 disabled:cursor-not-allowed"
              data-testid="pdf-report-button"
            >
              {pdfLoading ? (
                <>
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" aria-label="Gerando PDF" role="img">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Gerando PDF...
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                  </svg>
                  Relatório PDF ({result.resumo.total_oportunidades} {result.resumo.total_oportunidades === 1 ? 'oportunidade' : 'oportunidades'})
                </>
              )}
            </button>
          )}
        </div>

        {/* Opportunity count — right side */}
        <span className="text-sm text-[var(--ink-secondary)] sm:ml-auto whitespace-nowrap" data-testid="sticky-count">
          {result.resumo.total_oportunidades} {result.resumo.total_oportunidades === 1 ? 'oportunidade' : 'oportunidades'}
        </span>
      </div>

      {/* AC13: Skeleton state during loading */}
      {loading && (
        <div className="flex items-center gap-3 mt-2 animate-pulse">
          <div className="h-8 w-28 bg-[var(--surface-1)] rounded" />
          <div className="h-8 w-24 bg-[var(--surface-1)] rounded" />
          <div className="h-8 w-20 bg-[var(--surface-1)] rounded" />
          <div className="h-4 w-32 bg-[var(--surface-1)] rounded ml-auto" />
        </div>
      )}
    </div>
  );
}

// --- Internal sub-component for Excel button states ---
function ExcelButton({
  result,
  onDownload,
  downloadLoading,
  onRegenerateExcel,
  excelFailCount,
  excelTimedOut,
  loading,
  onSearch,
}: {
  result: BuscaResult;
  onDownload: () => void;
  downloadLoading: boolean;
  onRegenerateExcel?: () => void;
  excelFailCount: number;
  excelTimedOut: boolean;
  loading: boolean;
  onSearch: () => void;
}) {
  const hasDownload = !!(result.download_url || result.download_id);
  const isFailed = (result.excel_status === 'failed' || excelTimedOut) && !hasDownload;
  const isProcessing = result.excel_status === 'processing' && !hasDownload && !isFailed;

  if (isProcessing) {
    return (
      <button
        disabled
        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium
                   bg-[var(--brand-navy)]/70 text-white rounded-button cursor-wait"
        data-testid="excel-processing-button"
      >
        <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" aria-label="Gerando Excel" role="img">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        Gerando Excel...
      </button>
    );
  }

  if (isFailed) {
    const isMaxRetries = excelFailCount >= 2;
    return isMaxRetries ? (
      <span
        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm text-ink-muted"
        data-testid="excel-unavailable-message"
      >
        Excel temporariamente indisponível —{" "}
        <a href="/ajuda" className="underline hover:text-ink">
          suporte
        </a>
      </span>
    ) : (
      <button
        onClick={onRegenerateExcel || onSearch}
        disabled={loading}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium
                   bg-amber-600 hover:bg-amber-700 text-white rounded-button
                   disabled:opacity-50 disabled:cursor-not-allowed"
        data-testid="excel-retry-button"
        title="A geração automática falhou. Clique para tentar novamente."
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
        Gerar novamente
      </button>
    );
  }

  return (
    <button
      onClick={onDownload}
      disabled={downloadLoading}
      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium
                 bg-[var(--brand-navy)] text-white rounded-button
                 hover:bg-[var(--brand-blue-hover)]
                 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      data-testid="excel-download-button"
      aria-label={`Baixar Excel com ${result.resumo.total_oportunidades} licitações`}
    >
      {downloadLoading ? (
        <>
          <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" aria-label="Preparando" role="img">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Preparando download...
        </>
      ) : (
        <>
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          Baixar Excel ({result.resumo.total_oportunidades} {result.resumo.total_oportunidades === 1 ? 'licitação' : 'licitações'})
        </>
      )}
    </button>
  );
}
