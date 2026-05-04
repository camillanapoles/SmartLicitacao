"use client";

/**
 * BILL-SYNC-001 (AC10): Admin UI for bidirectional Stripe <-> DB sync.
 *
 * Pairs with backend/routes/admin_billing_sync.py (/v1/admin/plans/...).
 * Renders:
 *  - Plans table with drift indicator (in_sync | drift_recent | drift_stale).
 *  - "Push DB to Stripe" button per row (reverse sync, with confirmation).
 *  - "Reconcile now" trigger for ad-hoc cron run.
 *  - Last 30 reconciliation runs panel.
 */

import { useCallback, useState } from "react";
import { toast } from "sonner";

import { useAuth } from "../../../components/AuthProvider";
import { useAdminSWR } from "../../../../hooks/useAdminSWR";

interface BillingSyncRow {
  id: string;
  plan_id: string;
  billing_period: string;
  price_cents: number;
  discount_percent: number;
  stripe_price_id: string | null;
  stripe_product_id: string | null;
  last_forward_synced_at: string | null;
  last_reverse_synced_at: string | null;
  is_archived: boolean;
  drift_status: "in_sync" | "drift_recent" | "drift_stale" | "unknown";
}

interface BillingSyncListResponse {
  items: BillingSyncRow[];
}

interface ReconciliationRun {
  id: string;
  started_at: string;
  finished_at: string | null;
  status: string;
  dry_run: boolean;
  rows_checked: number;
  drifts_detected: number;
  drifts_fixed: number;
  drifts_manual: number;
  error_message: string | null;
}

interface ReconciliationRunsResponse {
  items: ReconciliationRun[];
}

const DRIFT_LABELS: Record<BillingSyncRow["drift_status"], string> = {
  in_sync: "Em sincronia",
  drift_recent: "Drift recente",
  drift_stale: "Drift antigo",
  unknown: "Sem dados",
};

const DRIFT_DOT_COLOR: Record<BillingSyncRow["drift_status"], string> = {
  in_sync: "bg-green-500",
  drift_recent: "bg-yellow-500",
  drift_stale: "bg-red-500",
  unknown: "bg-gray-400",
};

function formatTimestamp(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("pt-BR");
  } catch {
    return iso;
  }
}

function formatPriceBRL(cents: number): string {
  return (cents / 100).toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
  });
}

export default function AdminBillingSyncPage() {
  const { session } = useAuth();
  const token = session?.access_token;

  const {
    data: rowsData,
    error: rowsError,
    isLoading: rowsLoading,
    mutate: refetchRows,
  } = useAdminSWR<BillingSyncListResponse>("/api/admin/plans/billing-sync");
  const {
    data: runsData,
    isLoading: runsLoading,
    mutate: refetchRuns,
  } = useAdminSWR<ReconciliationRunsResponse>(
    "/api/admin/plans/reconciliation-runs?limit=30",
  );

  const [busyRowId, setBusyRowId] = useState<string | null>(null);
  const [reconcilingNow, setReconcilingNow] = useState(false);
  const [confirmRow, setConfirmRow] = useState<BillingSyncRow | null>(null);
  const [confirmNote, setConfirmNote] = useState("");

  const reverseSync = useCallback(
    async (row: BillingSyncRow, note: string) => {
      if (!token) return;
      setBusyRowId(row.id);
      try {
        const res = await fetch(`/api/admin/plans/${row.id}/sync-to-stripe`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            i_understand_this_modifies_stripe: true,
            note: note || null,
          }),
        });
        if (!res.ok) {
          const body = await res.text();
          throw new Error(body || `HTTP ${res.status}`);
        }
        const data: {
          status: string;
          new_stripe_price_id: string | null;
          skipped_reason: string | null;
        } = await res.json();
        if (data.status === "skipped") {
          toast.warning(
            `Reverse sync ignorada: ${data.skipped_reason ?? "race guard"}`,
          );
        } else {
          toast.success(
            `Stripe atualizada — novo price ${data.new_stripe_price_id ?? "?"}`,
          );
        }
        await refetchRows();
        await refetchRuns();
      } catch (e) {
        toast.error(`Falha no reverse sync: ${(e as Error).message}`);
      } finally {
        setBusyRowId(null);
        setConfirmRow(null);
        setConfirmNote("");
      }
    },
    [token, refetchRows, refetchRuns],
  );

  const reconcileNow = useCallback(
    async (dryRun: boolean) => {
      if (!token) return;
      setReconcilingNow(true);
      try {
        const res = await fetch(
          `/api/admin/plans/reconcile-now?dry_run=${dryRun}`,
          {
            method: "POST",
            headers: { Authorization: `Bearer ${token}` },
          },
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: { drifts_detected: number; drifts_fixed: number } =
          await res.json();
        toast.success(
          `Reconciliação OK: ${data.drifts_detected} drifts detectados, ${data.drifts_fixed} auto-corrigidos`,
        );
        await refetchRows();
        await refetchRuns();
      } catch (e) {
        toast.error(`Falha na reconciliação: ${(e as Error).message}`);
      } finally {
        setReconcilingNow(false);
      }
    },
    [token, refetchRows, refetchRuns],
  );

  if (rowsError) {
    return (
      <div className="p-6">
        <h1 className="text-2xl font-bold mb-4">Sync Stripe ↔ DB</h1>
        <div className="bg-red-50 border border-red-200 text-red-800 p-4 rounded">
          {(rowsError as Error).message}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto" data-testid="admin-billing-sync">
      <header className="mb-6">
        <h1 className="text-2xl font-bold">Sync Stripe ↔ DB</h1>
        <p className="text-sm text-gray-600 mt-1">
          BILL-SYNC-001 — sincronização bidirecional de preços entre Stripe e
          plan_billing_periods.
        </p>
      </header>

      <section className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Planos</h2>
          <div className="flex gap-2">
            <button
              type="button"
              className="px-4 py-2 text-sm bg-gray-200 hover:bg-gray-300 rounded disabled:opacity-50"
              onClick={() => reconcileNow(true)}
              disabled={reconcilingNow}
              data-testid="reconcile-dry-run"
            >
              {reconcilingNow ? "Executando..." : "Reconcile (dry-run)"}
            </button>
            <button
              type="button"
              className="px-4 py-2 text-sm bg-blue-600 text-white hover:bg-blue-700 rounded disabled:opacity-50"
              onClick={() => reconcileNow(false)}
              disabled={reconcilingNow}
              data-testid="reconcile-live"
            >
              {reconcilingNow ? "Executando..." : "Reconcile agora"}
            </button>
          </div>
        </div>

        {rowsLoading && <p className="text-sm text-gray-500">Carregando…</p>}

        {!rowsLoading && rowsData && (
          <div className="overflow-x-auto bg-white rounded shadow">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Plan
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Período
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Preço DB
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Stripe price id
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Drift
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Last forward
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Last reverse
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Ações
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {rowsData.items.map((row) => (
                  <tr
                    key={row.id}
                    data-testid={`bps-row-${row.id}`}
                    className={row.is_archived ? "bg-gray-50 text-gray-400" : ""}
                  >
                    <td className="px-4 py-3 text-sm">{row.plan_id}</td>
                    <td className="px-4 py-3 text-sm">{row.billing_period}</td>
                    <td className="px-4 py-3 text-sm text-right">
                      {formatPriceBRL(row.price_cents)}
                    </td>
                    <td className="px-4 py-3 text-sm font-mono text-xs">
                      {row.stripe_price_id ?? "—"}
                    </td>
                    <td
                      className="px-4 py-3 text-sm"
                      data-testid={`drift-${row.id}`}
                    >
                      <span className="inline-flex items-center gap-2">
                        <span
                          className={`inline-block w-2 h-2 rounded-full ${DRIFT_DOT_COLOR[row.drift_status]}`}
                          aria-hidden="true"
                        />
                        {DRIFT_LABELS[row.drift_status]}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {formatTimestamp(row.last_forward_synced_at)}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {formatTimestamp(row.last_reverse_synced_at)}
                    </td>
                    <td className="px-4 py-3 text-sm text-right">
                      <button
                        type="button"
                        className="px-3 py-1 text-xs bg-orange-100 text-orange-800 hover:bg-orange-200 rounded disabled:opacity-50"
                        onClick={() => setConfirmRow(row)}
                        disabled={busyRowId === row.id || row.is_archived}
                        data-testid={`push-${row.id}`}
                      >
                        Push DB → Stripe
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section>
        <h2 className="text-lg font-semibold mb-4">
          Últimas execuções de reconciliação
        </h2>
        {runsLoading && <p className="text-sm text-gray-500">Carregando…</p>}
        {!runsLoading && runsData && (
          <div className="overflow-x-auto bg-white rounded shadow">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Início
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Status
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Modo
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Linhas
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Drifts
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Auto-fix
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Manual
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {runsData.items.map((r) => (
                  <tr key={r.id} data-testid={`run-${r.id}`}>
                    <td className="px-4 py-3 text-sm">
                      {formatTimestamp(r.started_at)}
                    </td>
                    <td className="px-4 py-3 text-sm">{r.status}</td>
                    <td className="px-4 py-3 text-sm">
                      {r.dry_run ? "dry-run" : "live"}
                    </td>
                    <td className="px-4 py-3 text-sm text-right">
                      {r.rows_checked}
                    </td>
                    <td className="px-4 py-3 text-sm text-right">
                      {r.drifts_detected}
                    </td>
                    <td className="px-4 py-3 text-sm text-right">
                      {r.drifts_fixed}
                    </td>
                    <td className="px-4 py-3 text-sm text-right">
                      {r.drifts_manual}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {confirmRow && (
        <div
          className="fixed inset-0 bg-black bg-opacity-40 flex items-center justify-center z-50"
          role="dialog"
          aria-modal="true"
          data-testid="confirm-modal"
        >
          <div className="bg-white rounded p-6 max-w-md w-full">
            <h3 className="text-lg font-semibold mb-2">
              Confirmar reverse sync?
            </h3>
            <p className="text-sm text-gray-600 mb-4">
              Isso criará uma nova Stripe Price (
              <code className="font-mono text-xs">
                {formatPriceBRL(confirmRow.price_cents)}
              </code>
              ) e arquivará a antiga{" "}
              <code className="font-mono text-xs">
                {confirmRow.stripe_price_id ?? "?"}
              </code>
              . Operação irreversível.
            </p>
            <label className="block mb-3 text-sm">
              Nota (opcional):
              <textarea
                value={confirmNote}
                onChange={(e) => setConfirmNote(e.target.value)}
                className="mt-1 w-full border rounded px-2 py-1 text-sm"
                rows={2}
                data-testid="confirm-note"
              />
            </label>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setConfirmRow(null);
                  setConfirmNote("");
                }}
                className="px-4 py-2 text-sm bg-gray-200 rounded hover:bg-gray-300"
                data-testid="confirm-cancel"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={() => reverseSync(confirmRow, confirmNote)}
                disabled={busyRowId === confirmRow.id}
                className="px-4 py-2 text-sm bg-orange-600 text-white rounded hover:bg-orange-700 disabled:opacity-50"
                data-testid="confirm-submit"
              >
                {busyRowId === confirmRow.id
                  ? "Enviando..."
                  : "Confirmar Push"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
