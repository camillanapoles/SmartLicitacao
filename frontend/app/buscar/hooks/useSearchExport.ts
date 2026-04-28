"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import type { BuscaResult } from "../../types";
import { getUserFriendlyError } from "../../../lib/error-messages";
import { getCorrelationId, logCorrelatedRequest } from "../../../lib/utils/correlationId";
import { useAnalytics } from "../../../hooks/useAnalytics";
import { APP_NAME } from "../../../lib/config";
import { toast } from "sonner";

interface UseSearchExportParams {
  result: BuscaResult | null;
  setResult: (updater: (prev: BuscaResult | null) => BuscaResult | null) => void;
  searchId: string | null;
  asyncSearchIdRef: React.MutableRefObject<string | null>;
  sseDisconnected: boolean;
  sseAvailable: boolean;
  loading: boolean;
  session: { access_token?: string | null } | null;
  sectorName: string;
  dataInicial: string;
  dataFinal: string;
  // Shared refs from orchestrator (also used by execution hook for reset)
  excelFailCountRef: React.MutableRefObject<number>;
  excelToastFiredRef: React.MutableRefObject<boolean>;
  // BIZ-METRIC-001: optional callback fired after a successful Excel
  // download. The orchestrator wires this to
  // ``useExportTimeSavedSurvey`` so the post-export modal can be shown.
  onExportSucceeded?: (input: { exportType: "excel" | "pdf" | "sheets"; bidCount: number | null }) => void;
}

export interface UseSearchExportReturn {
  downloadLoading: boolean;
  downloadError: string | null;
  excelFailCountRef: React.MutableRefObject<number>;
  excelToastFiredRef: React.MutableRefObject<boolean>;
  excelPollingRef: React.MutableRefObject<ReturnType<typeof setInterval> | null>;
  excelPollingCountRef: React.MutableRefObject<number>;
  handleDownload: () => Promise<void>;
  handleRegenerateExcel: () => Promise<void>;
  handleExcelFailure: (isRegenerateAttempt: boolean) => void;
  setDownloadError: (e: string | null) => void;
}

export function useSearchExport(params: UseSearchExportParams): UseSearchExportReturn {
  const {
    result, setResult, searchId, asyncSearchIdRef,
    sseDisconnected, sseAvailable, loading, session,
    sectorName, dataInicial, dataFinal,
    excelFailCountRef, excelToastFiredRef,
    onExportSucceeded,
  } = params;

  const { trackEvent } = useAnalytics();

  // Download
  const [downloadLoading, setDownloadLoading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  // =========================================================================
  // STORY-364 AC4-AC6: Excel polling fallback when SSE disconnects
  // =========================================================================
  const excelPollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const excelPollingCountRef = useRef(0);

  useEffect(() => {
    const shouldPoll = !!(
      result
      && result.excel_status === 'processing'
      && !result.download_url
      && !result.download_id
      && (sseDisconnected || !sseAvailable)
      && !loading
    );

    if (!shouldPoll) {
      if (excelPollingRef.current) {
        clearInterval(excelPollingRef.current);
        excelPollingRef.current = null;
      }
      // Reset counter when Excel is resolved
      if (result?.excel_status !== 'processing') {
        excelPollingCountRef.current = 0;
      }
      return;
    }

    const pollExcelStatus = async () => {
      // AC6: Max 12 attempts (60s total)
      if (excelPollingCountRef.current >= 12) {
        if (excelPollingRef.current) {
          clearInterval(excelPollingRef.current);
          excelPollingRef.current = null;
        }
        return;
      }

      excelPollingCountRef.current++;

      try {
        const headers: Record<string, string> = {};
        if (session?.access_token) headers['Authorization'] = `Bearer ${session.access_token}`;

        const sid = asyncSearchIdRef.current || searchId;
        if (!sid) return;

        const res = await fetch(
          `/api/search-status?search_id=${encodeURIComponent(sid)}`,
          { headers },
        );
        if (!res.ok) return;

        const data = await res.json();
        // AC5: When polling returns excel_url, update result
        if (data.excel_url) {
          setResult(prev => prev ? {
            ...prev,
            download_url: data.excel_url,
            excel_status: 'ready' as const,
          } : prev);
          if (excelPollingRef.current) {
            clearInterval(excelPollingRef.current);
            excelPollingRef.current = null;
          }
          excelPollingCountRef.current = 0;
        }
      } catch (e) {
        console.warn('[STORY-364] Excel polling failed:', e);
      }
    };

    // Start polling: immediate first check + every 5s
    pollExcelStatus();
    excelPollingRef.current = setInterval(pollExcelStatus, 5000);

    return () => {
      if (excelPollingRef.current) {
        clearInterval(excelPollingRef.current);
        excelPollingRef.current = null;
      }
    };
  }, [result?.excel_status, result?.download_url, result?.download_id, sseDisconnected, sseAvailable, loading, searchId, session?.access_token, asyncSearchIdRef, setResult]);

  // UX-405: Centralized Excel failure handler — toast, Mixpanel, retry tracking
  const handleExcelFailure = useCallback((isRegenerateAttempt: boolean) => {
    excelFailCountRef.current += 1;
    const attempt = excelFailCountRef.current;

    // AC4: Mixpanel event
    const sid = asyncSearchIdRef.current || searchId;
    trackEvent('excel_generation_failed', { search_id: sid, attempt_number: attempt });

    // AC1 + AC3: Toast (deduplicated per search via ref)
    if (!excelToastFiredRef.current) {
      excelToastFiredRef.current = true;
      toast.error("Não foi possível gerar o Excel. Você pode tentar novamente.");
    } else if (isRegenerateAttempt && attempt >= 2) {
      // AC3: More detailed toast on repeated regeneration failure
      toast.error("Excel indisponível. Tente novamente em alguns instantes ou faça uma nova busca.");
    } else if (isRegenerateAttempt) {
      toast.error("Não foi possível gerar o Excel. Você pode tentar novamente.");
    }

    setResult(prev => prev ? { ...prev, excel_status: 'failed' as const } : prev);
  }, [asyncSearchIdRef, searchId, trackEvent, setResult]);

  const handleDownload = useCallback(async () => {
    // STORY-202 CROSS-C02: Support both download_url (object storage) and download_id (filesystem)
    // UX-349 AC1: Show error instead of silently returning when no download available
    if (!result?.download_id && !result?.download_url) {
      setDownloadError("Excel ainda não disponível. Faça uma nova análise para gerar a planilha.");
      return;
    }
    setDownloadError(null);
    setDownloadLoading(true);

    const downloadIdentifier = result.download_url ? 'url' : result.download_id;
    trackEvent('download_started', { download_id: result.download_id, has_url: !!result.download_url });

    try {
      // STORY-226 AC24: Attach session correlation ID for distributed tracing
      const dlCorrelationId = getCorrelationId();
      const downloadHeaders: Record<string, string> = {
        "X-Correlation-ID": dlCorrelationId,
      };
      if (session?.access_token) downloadHeaders["Authorization"] = `Bearer ${session.access_token}`;

      // Priority 1: Use signed URL from object storage (pass as query param for redirect)
      // Priority 2: Use legacy download_id (filesystem)
      const downloadEndpoint = result.download_url
        ? `/api/download?url=${encodeURIComponent(result.download_url)}`
        : `/api/download?id=${result.download_id}`;

      logCorrelatedRequest("GET", downloadEndpoint, dlCorrelationId);
      const response = await fetch(downloadEndpoint, { headers: downloadHeaders });

      if (!response.ok) {
        if (response.status === 401) { window.location.href = "/login"; throw new Error('Faça login para continuar'); }
        if (response.status === 404) throw new Error('Arquivo expirado. Faça uma nova análise para gerar o Excel.');
        throw new Error('Não foi possível baixar o arquivo. Tente novamente.');
      }

      const blob = await response.blob();
      const setorLabel = sectorName.replace(/\s+/g, '_');
      const appNameSlug = APP_NAME.replace(/\s+/g, '_');
      const filename = `${appNameSlug}_${setorLabel}_${dataInicial}_a_${dataFinal}.xlsx`;

      const anchor = document.createElement('a');
      if ('download' in anchor) {
        const url = URL.createObjectURL(blob);
        anchor.href = url;
        anchor.download = filename;
        anchor.style.display = 'none';
        document.body.appendChild(anchor);
        anchor.click();
        document.body.removeChild(anchor);
        setTimeout(() => URL.revokeObjectURL(url), 100);
      } else {
        const url = URL.createObjectURL(blob);
        const newWindow = window.open(url, '_blank');
        if (!newWindow) window.location.href = url;
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      }

      trackEvent('download_completed', {
        download_id: result.download_id,
        file_size_bytes: blob.size,
        source: result.download_url ? 'object_storage' : 'filesystem'
      });
      // Zero-churn P1 §7.1: Feature usage tracking
      trackEvent('feature_used', { feature_name: 'excel_export' });

      // BIZ-METRIC-001: notify the orchestrator so the post-export
      // survey modal can fire (subject to frequency throttling and
      // eligibility checks owned by useExportTimeSavedSurvey).
      try {
        onExportSucceeded?.({
          exportType: "excel",
          bidCount: result?.resumo?.total_oportunidades ?? null,
        });
      } catch {
        // never let survey-trigger errors fail the download flow
      }
    } catch (e) {
      setDownloadError(getUserFriendlyError(e instanceof Error ? e : 'Não foi possível baixar o arquivo.'));
    } finally {
      setDownloadLoading(false);
    }
  }, [result, session, sectorName, dataInicial, dataFinal, trackEvent]);

  // STORY-364 AC7: Regenerate Excel without re-running search
  const handleRegenerateExcel = useCallback(async () => {
    const sid = asyncSearchIdRef.current || searchId;
    if (!sid) {
      setDownloadError("Sem ID de análise para regenerar Excel.");
      return;
    }

    // AC5: Block if already at max retries
    if (excelFailCountRef.current >= 2) return;

    // Set processing state
    setResult(prev => prev ? { ...prev, excel_status: 'processing' as const, download_url: null } : prev);
    excelPollingCountRef.current = 0;

    try {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (session?.access_token) headers['Authorization'] = `Bearer ${session.access_token}`;

      const res = await fetch(`/api/regenerate-excel/${encodeURIComponent(sid)}`, {
        method: 'POST',
        headers,
      });

      if (res.status === 404) {
        setDownloadError("Resultados expirados. Faça uma nova análise.");
        handleExcelFailure(true);
        return;
      }

      if (!res.ok) {
        setDownloadError("Erro ao regenerar Excel. Tente novamente.");
        handleExcelFailure(true);
        return;
      }

      const data = await res.json();

      // If inline generation returned ready result
      if (data.excel_status === 'ready' && data.download_url) {
        // Reset failure tracking on success
        excelFailCountRef.current = 0;
        excelToastFiredRef.current = false;
        setResult(prev => prev ? {
          ...prev,
          download_url: data.download_url,
          excel_status: 'ready' as const,
        } : prev);
        return;
      }

      // 202 — job queued, polling will pick it up via the effect above
      // excel_status is already 'processing'
    } catch (e) {
      console.error('[STORY-364] Regenerate Excel failed:', e);
      setDownloadError("Erro de rede ao regenerar Excel.");
      handleExcelFailure(true);
    }
  }, [asyncSearchIdRef, searchId, session, setResult, handleExcelFailure]);

  return {
    downloadLoading,
    downloadError,
    excelFailCountRef,
    excelToastFiredRef,
    excelPollingRef,
    excelPollingCountRef,
    handleDownload,
    handleRegenerateExcel,
    handleExcelFailure,
    setDownloadError,
  };
}
