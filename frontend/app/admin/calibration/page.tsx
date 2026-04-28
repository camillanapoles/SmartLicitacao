"use client";

/**
 * BIZ-METRIC-001 (AC11): Admin calibration dashboard.
 *
 * Shows histogram + summary statistics for the post-export survey
 * (`export_time_saved_survey`), plus a button to recalibrate
 * `app_config.hours_saved_per_search` from the median of the IQR-filtered
 * distribution.
 *
 * Admin-only — gated by the backend `require_admin` on every endpoint
 * called from this page. Non-admin users will see a 403 banner.
 */

import React, { useCallback, useEffect, useMemo, useState } from "react";

interface HistogramBucket {
  range_label: string;
  count: number;
}

interface SurveyAggregate {
  range_days: number;
  sample_size: number;
  after_outlier_removal: number;
  median_hours: number | null;
  mean_hours: number | null;
  iqr_q1: number | null;
  iqr_q3: number | null;
  iqr_lower_bound: number | null;
  iqr_upper_bound: number | null;
  median_per_bid: number | null;
  median_bid_count: number | null;
  histogram: HistogramBucket[];
  current_constant: number;
}

interface RecalibrateResponse {
  range_days: number;
  sample_size: number;
  after_outlier_removal: number;
  eligible: boolean;
  reason: string | null;
  old_value: number;
  new_value: number | null;
  diff_pct: number | null;
  applied: boolean;
  median_per_bid: number | null;
  median_bid_count: number | null;
}

const fmtNumber = (v: number | null | undefined, digits = 2): string =>
  typeof v === "number" && Number.isFinite(v) ? v.toFixed(digits) : "—";

export default function CalibrationDashboardPage(): React.JSX.Element {
  const [rangeDays, setRangeDays] = useState<number>(90);
  const [aggregate, setAggregate] = useState<SurveyAggregate | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [recalibrating, setRecalibrating] = useState<boolean>(false);
  const [recalibrateResult, setRecalibrateResult] = useState<RecalibrateResponse | null>(null);

  const loadAggregate = useCallback(
    async (range: number) => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`/api/admin/survey/export-time-saved?range_days=${range}`, {
          method: "GET",
          credentials: "include",
        });
        if (!res.ok) {
          if (res.status === 403) throw new Error("Acesso restrito a administradores.");
          throw new Error(`Falha ao carregar dados (HTTP ${res.status}).`);
        }
        const data: SurveyAggregate = await res.json();
        setAggregate(data);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
        setAggregate(null);
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    void loadAggregate(rangeDays);
  }, [loadAggregate, rangeDays]);

  const onRecalibrate = useCallback(
    async (apply: boolean) => {
      setRecalibrating(true);
      setRecalibrateResult(null);
      try {
        const res = await fetch(`/api/admin/calibration/recalibrate`, {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ range_days: rangeDays, apply }),
        });
        if (!res.ok) {
          if (res.status === 403) throw new Error("Acesso restrito a administradores.");
          throw new Error(`Falha ao recalibrar (HTTP ${res.status}).`);
        }
        const data: RecalibrateResponse = await res.json();
        setRecalibrateResult(data);
        if (apply && data.applied) {
          // Refresh aggregate so current_constant updates.
          await loadAggregate(rangeDays);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setRecalibrating(false);
      }
    },
    [rangeDays, loadAggregate],
  );

  const maxCount = useMemo(() => {
    if (!aggregate) return 0;
    return aggregate.histogram.reduce((a, b) => Math.max(a, b.count), 0);
  }, [aggregate]);

  return (
    <main className="max-w-4xl mx-auto px-4 py-8 space-y-8" data-testid="calibration-page">
      <header>
        <h1 className="text-2xl font-bold">Calibração — Horas economizadas</h1>
        <p className="text-sm text-slate-600 mt-1">
          BIZ-METRIC-001 — calibração empírica de{" "}
          <code>app_config.hours_saved_per_search</code> a partir das respostas da pesquisa
          pós-exportação. Veja{" "}
          <a className="underline" href="/docs/methodology/hours-saved-calibration.md">
            metodologia
          </a>.
        </p>
      </header>

      <section className="flex flex-wrap items-center gap-3">
        <label htmlFor="range-days" className="text-sm font-medium">
          Janela (dias):
        </label>
        <select
          id="range-days"
          value={rangeDays}
          onChange={(e) => setRangeDays(Number(e.target.value))}
          className="rounded-md border border-slate-300 px-2 py-1 text-sm"
          data-testid="range-select"
        >
          <option value={30}>30 dias</option>
          <option value={60}>60 dias</option>
          <option value={90}>90 dias</option>
          <option value={180}>180 dias</option>
          <option value={365}>365 dias</option>
        </select>
        <button
          type="button"
          onClick={() => loadAggregate(rangeDays)}
          disabled={loading}
          className="ml-auto px-3 py-1 text-sm font-medium rounded-md bg-slate-100 hover:bg-slate-200 disabled:opacity-50"
        >
          Atualizar
        </button>
      </section>

      {error ? (
        <div className="rounded-md bg-red-50 border border-red-200 p-3 text-sm text-red-700" data-testid="error-banner">
          {error}
        </div>
      ) : null}

      {aggregate ? (
        <>
          <section className="grid grid-cols-1 sm:grid-cols-3 gap-4" data-testid="summary-cards">
            <div className="rounded-lg border border-slate-200 p-4">
              <div className="text-xs text-slate-500 uppercase">Constante atual</div>
              <div className="text-2xl font-semibold" data-testid="current-constant">
                {fmtNumber(aggregate.current_constant)} h
              </div>
              <div className="text-xs text-slate-500 mt-1">
                <code>hours_saved_per_search</code>
              </div>
            </div>
            <div className="rounded-lg border border-slate-200 p-4">
              <div className="text-xs text-slate-500 uppercase">Mediana (proposta)</div>
              <div className="text-2xl font-semibold" data-testid="median-hours">
                {fmtNumber(aggregate.median_hours)} h
              </div>
              <div className="text-xs text-slate-500 mt-1">
                IQR: {fmtNumber(aggregate.iqr_q1)} – {fmtNumber(aggregate.iqr_q3)} h
              </div>
            </div>
            <div className="rounded-lg border border-slate-200 p-4">
              <div className="text-xs text-slate-500 uppercase">Tamanho da amostra</div>
              <div className="text-2xl font-semibold" data-testid="sample-size">
                {aggregate.after_outlier_removal} / {aggregate.sample_size}
              </div>
              <div className="text-xs text-slate-500 mt-1">
                após filtro IQR / total bruto
              </div>
            </div>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-3">Distribuição</h2>
            <div className="space-y-1" data-testid="histogram">
              {aggregate.histogram.map((bucket) => {
                const pct = maxCount > 0 ? (bucket.count / maxCount) * 100 : 0;
                return (
                  <div key={bucket.range_label} className="flex items-center gap-2 text-sm">
                    <span className="w-20 text-right text-slate-600">{bucket.range_label}</span>
                    <div className="flex-1 h-4 bg-slate-100 rounded overflow-hidden">
                      <div
                        className="h-full bg-blue-500"
                        style={{ width: `${pct}%` }}
                        aria-label={`${bucket.count} respostas`}
                      />
                    </div>
                    <span className="w-10 text-right">{bucket.count}</span>
                  </div>
                );
              })}
            </div>
          </section>

          <section className="space-y-2">
            <h2 className="text-lg font-semibold">Recalibrar</h2>
            <p className="text-sm text-slate-600">
              Computa a nova mediana e (opcional) persiste em <code>app_config</code>.
              Requer n ≥ 30 após filtro IQR.
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => onRecalibrate(false)}
                disabled={recalibrating}
                className="px-3 py-1.5 text-sm font-medium rounded-md bg-slate-100 hover:bg-slate-200 disabled:opacity-50"
                data-testid="recalibrate-dryrun"
              >
                Simular
              </button>
              <button
                type="button"
                onClick={() => onRecalibrate(true)}
                disabled={recalibrating}
                className="px-3 py-1.5 text-sm font-medium rounded-md bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50"
                data-testid="recalibrate-apply"
              >
                Aplicar
              </button>
            </div>
            {recalibrateResult ? (
              <div
                className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm"
                data-testid="recalibrate-result"
              >
                <div>
                  <strong>Antigo:</strong> {fmtNumber(recalibrateResult.old_value)} h →{" "}
                  <strong>Novo:</strong> {fmtNumber(recalibrateResult.new_value)} h
                  {recalibrateResult.diff_pct !== null
                    ? ` (Δ ${recalibrateResult.diff_pct.toFixed(1)}%)`
                    : null}
                </div>
                <div>
                  <strong>Elegível:</strong> {recalibrateResult.eligible ? "sim" : "não"}
                  {recalibrateResult.reason ? ` (${recalibrateResult.reason})` : null}
                </div>
                <div>
                  <strong>Aplicado:</strong> {recalibrateResult.applied ? "sim" : "não"}
                </div>
              </div>
            ) : null}
          </section>
        </>
      ) : loading ? (
        <p className="text-sm text-slate-500">Carregando…</p>
      ) : null}
    </main>
  );
}
