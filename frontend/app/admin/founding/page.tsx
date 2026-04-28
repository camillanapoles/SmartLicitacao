"use client";

/**
 * BIZ-FOUND-002: admin dashboard for the canonical founding policy.
 *
 * Surfaces:
 * - Progress bar (X/50 + completion %).
 * - Policy snapshot (deadline, coupon, paused state).
 * - Founding leads list with status filter.
 * - Pause / resume toggle.
 *
 * All API calls go through /api/admin/founding/* which is fronted by the
 * catch-all admin proxy and the backend require_admin guard.
 */

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "../../components/AuthProvider";
import { useAdminSWR } from "../../../hooks/useAdminSWR";

interface FoundingPolicySnapshot {
  seat_limit: number;
  deadline_at: string;
  discount_pct: number;
  coupon_code: string;
  active: boolean;
  paused: boolean;
  paused_at: string | null;
  paused_by: string | null;
  paused_reason: string | null;
  seats_taken: number;
  seats_remaining: number;
  completion_pct: number;
}

interface FoundingLead {
  id: string;
  email: string;
  nome: string;
  cnpj: string;
  razao_social: string | null;
  checkout_status: string;
  created_at: string;
  completed_at: string | null;
  stripe_customer_id: string | null;
}

interface FoundingLeadsList {
  count: number;
  completed_count: number;
  pending_count: number;
  leads: FoundingLead[];
}

const STATUS_LABEL: Record<string, string> = {
  pending: "Pendente",
  completed: "Pago",
  abandoned: "Abandonado",
  failed: "Falhou",
  cap_violated: "Reembolsado (race)",
};

const STATUS_COLOR: Record<string, string> = {
  completed: "bg-green-100 text-green-800",
  pending: "bg-amber-100 text-amber-800",
  abandoned: "bg-slate-100 text-slate-700",
  failed: "bg-red-100 text-red-800",
  cap_violated: "bg-orange-100 text-orange-800",
};

function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function maskCnpj(cnpj: string): string {
  if (!cnpj || cnpj.length !== 14) return cnpj;
  return `${cnpj.slice(0, 2)}.${cnpj.slice(2, 5)}.${cnpj.slice(5, 8)}/${cnpj.slice(8, 12)}-${cnpj.slice(12)}`;
}

export default function AdminFoundingPage() {
  const { session, isAdmin, loading } = useAuth();
  const isAuthenticated = !!session;
  const shouldFetch = isAuthenticated && isAdmin;

  const [statusFilter, setStatusFilter] = useState<string>("");
  const [pauseReason, setPauseReason] = useState<string>("");
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [mutationOk, setMutationOk] = useState<string | null>(null);

  const {
    data: policy,
    error: policyError,
    isLoading: policyLoading,
    mutate: mutatePolicy,
  } = useAdminSWR<FoundingPolicySnapshot>(
    shouldFetch ? "/api/admin/founding/policy" : null,
    { refreshInterval: 30_000 },
  );

  const leadsKey = shouldFetch
    ? `/api/admin/founding/leads?limit=100${statusFilter ? `&status=${statusFilter}` : ""}`
    : null;
  const {
    data: leadsData,
    error: leadsError,
    isLoading: leadsLoading,
    mutate: mutateLeads,
  } = useAdminSWR<FoundingLeadsList>(leadsKey, { refreshInterval: 60_000 });

  async function callAdmin(path: string, body?: unknown): Promise<boolean> {
    if (!session?.access_token) return false;
    setMutationError(null);
    setMutationOk(null);
    try {
      const res = await fetch(path, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.access_token}`,
        },
        body: body ? JSON.stringify(body) : undefined,
      });
      if (!res.ok) {
        const txt = await res.text();
        setMutationError(`Erro ${res.status}: ${txt.slice(0, 200)}`);
        return false;
      }
      return true;
    } catch (e) {
      setMutationError(e instanceof Error ? e.message : "Erro de rede");
      return false;
    }
  }

  async function handlePause() {
    const ok = await callAdmin("/api/admin/founding/pause", { reason: pauseReason || null });
    if (ok) {
      setMutationOk("Programa pausado. Frontend exibirá mensagem de pausa.");
      setPauseReason("");
      mutatePolicy();
    }
  }

  async function handleResume() {
    const ok = await callAdmin("/api/admin/founding/resume");
    if (ok) {
      setMutationOk("Programa retomado. Inscrições liberadas.");
      mutatePolicy();
    }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-3xl p-8">
        <p className="text-sm text-slate-500">Carregando...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="mx-auto max-w-3xl p-8">
        <p className="text-sm text-slate-700">
          Você precisa estar autenticado.{" "}
          <Link href="/login" className="text-blue-600 underline">
            Entrar
          </Link>
        </p>
      </div>
    );
  }

  if (!isAdmin) {
    return (
      <div className="mx-auto max-w-3xl p-8">
        <p className="text-sm text-red-700">Acesso restrito a administradores.</p>
      </div>
    );
  }

  return (
    <main className="mx-auto max-w-5xl p-6 space-y-6">
      <header className="border-b pb-4">
        <h1 className="text-2xl font-bold text-slate-900">Founding Partners — Painel Admin</h1>
        <p className="text-sm text-slate-600 mt-1">
          BIZ-FOUND-002 · cap canonical = 50 vagas, prazo 30/05/2026, 50% off vitalício.
        </p>
      </header>

      {(mutationError || mutationOk) && (
        <div
          role="status"
          className={`rounded border px-3 py-2 text-sm ${
            mutationError
              ? "bg-red-50 border-red-200 text-red-800"
              : "bg-green-50 border-green-200 text-green-800"
          }`}
        >
          {mutationError || mutationOk}
        </div>
      )}

      {/* Progress card */}
      <section className="rounded-lg border border-slate-200 p-4 bg-white">
        <h2 className="text-lg font-semibold text-slate-900 mb-3">Progresso do programa</h2>
        {policyLoading && <p className="text-sm text-slate-500">Carregando policy...</p>}
        {policyError && (
          <p className="text-sm text-red-700">Erro ao carregar policy: {String(policyError)}</p>
        )}
        {policy && (
          <>
            <div className="flex items-baseline justify-between mb-2">
              <span className="text-sm text-slate-700">
                <strong>{policy.seats_taken}</strong>/{policy.seat_limit} vagas preenchidas
              </span>
              <span className="text-sm text-slate-500">{policy.completion_pct.toFixed(1)}%</span>
            </div>
            <div className="h-3 w-full bg-slate-100 rounded overflow-hidden" aria-label="Progresso founding">
              <div
                className="h-full bg-blue-600 transition-all"
                style={{ width: `${Math.min(100, policy.completion_pct)}%` }}
                data-testid="founding-progress-bar-fill"
              />
            </div>

            <dl className="mt-4 grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm">
              <div>
                <dt className="text-slate-500">Deadline</dt>
                <dd className="text-slate-900 font-medium">{formatDateTime(policy.deadline_at)}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Cupom</dt>
                <dd className="text-slate-900 font-mono">{policy.coupon_code}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Desconto</dt>
                <dd className="text-slate-900 font-medium">{policy.discount_pct}% vitalício</dd>
              </div>
              <div>
                <dt className="text-slate-500">Status</dt>
                <dd className="text-slate-900 font-medium">
                  {policy.paused ? (
                    <span className="text-amber-700">Pausado</span>
                  ) : policy.active ? (
                    <span className="text-green-700">Ativo</span>
                  ) : (
                    <span className="text-red-700">Desativado</span>
                  )}
                </dd>
              </div>
              {policy.paused && policy.paused_reason && (
                <div className="col-span-full">
                  <dt className="text-slate-500">Motivo da pausa</dt>
                  <dd className="text-slate-900">{policy.paused_reason}</dd>
                </div>
              )}
            </dl>
          </>
        )}
      </section>

      {/* Pause / resume toggle */}
      <section className="rounded-lg border border-slate-200 p-4 bg-white">
        <h2 className="text-lg font-semibold text-slate-900 mb-3">Controle operacional</h2>
        {policy?.paused ? (
          <button
            type="button"
            onClick={handleResume}
            data-testid="founding-resume-btn"
            className="rounded bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700"
          >
            Retomar inscrições
          </button>
        ) : (
          <div className="flex flex-col sm:flex-row gap-2">
            <input
              type="text"
              value={pauseReason}
              onChange={(e) => setPauseReason(e.target.value)}
              placeholder="Motivo (opcional, ex: 'manual review backlog')"
              maxLength={500}
              data-testid="founding-pause-reason"
              className="flex-1 rounded border border-slate-300 px-3 py-2 text-sm"
            />
            <button
              type="button"
              onClick={handlePause}
              data-testid="founding-pause-btn"
              className="rounded bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700"
            >
              Pausar inscrições
            </button>
          </div>
        )}
      </section>

      {/* Leads list */}
      <section className="rounded-lg border border-slate-200 p-4 bg-white">
        <div className="flex items-baseline justify-between mb-3">
          <h2 className="text-lg font-semibold text-slate-900">Founding leads</h2>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded border border-slate-300 px-2 py-1 text-sm"
            data-testid="founding-status-filter"
          >
            <option value="">Todos</option>
            <option value="completed">Pago</option>
            <option value="pending">Pendente</option>
            <option value="abandoned">Abandonado</option>
            <option value="failed">Falhou</option>
            <option value="cap_violated">Reembolsado (race)</option>
          </select>
        </div>

        {leadsLoading && <p className="text-sm text-slate-500">Carregando...</p>}
        {leadsError && (
          <p className="text-sm text-red-700">Erro ao carregar leads: {String(leadsError)}</p>
        )}
        {leadsData && (
          <>
            <p className="text-xs text-slate-500 mb-2">
              {leadsData.count} leads · {leadsData.completed_count} pagos ·{" "}
              {leadsData.pending_count} pendentes
            </p>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-slate-500">
                    <th className="py-2 pr-3">Status</th>
                    <th className="py-2 pr-3">Email</th>
                    <th className="py-2 pr-3">Nome</th>
                    <th className="py-2 pr-3">CNPJ</th>
                    <th className="py-2 pr-3">Criado em</th>
                    <th className="py-2 pr-3">Pago em</th>
                  </tr>
                </thead>
                <tbody data-testid="founding-leads-tbody">
                  {leadsData.leads.map((lead) => (
                    <tr key={lead.id} className="border-b hover:bg-slate-50">
                      <td className="py-2 pr-3">
                        <span
                          className={`inline-block rounded px-2 py-0.5 text-xs ${
                            STATUS_COLOR[lead.checkout_status] || "bg-slate-100 text-slate-700"
                          }`}
                        >
                          {STATUS_LABEL[lead.checkout_status] || lead.checkout_status}
                        </span>
                      </td>
                      <td className="py-2 pr-3 font-mono text-xs">{lead.email}</td>
                      <td className="py-2 pr-3">{lead.nome}</td>
                      <td className="py-2 pr-3 font-mono text-xs">{maskCnpj(lead.cnpj)}</td>
                      <td className="py-2 pr-3 text-xs text-slate-600">
                        {formatDateTime(lead.created_at)}
                      </td>
                      <td className="py-2 pr-3 text-xs text-slate-600">
                        {formatDateTime(lead.completed_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-3">
              <button
                type="button"
                onClick={() => mutateLeads()}
                className="text-sm text-blue-600 hover:underline"
              >
                Atualizar lista
              </button>
            </div>
          </>
        )}
      </section>
    </main>
  );
}
