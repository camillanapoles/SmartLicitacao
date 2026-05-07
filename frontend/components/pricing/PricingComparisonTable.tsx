'use client';

/**
 * PricingComparisonTable — feat/#789
 *
 * 3-column comparison: Plano Fundadores vs SmartLic Pro mensal vs SmartLic Pro anual.
 * Collapses to 2-col when the founding offer is expired or seats are exhausted.
 * Fetches /api/founding/availability on mount; shows founders column by default
 * until data loads (avoids layout shift on first render).
 */

import { useState, useEffect } from 'react';
import Link from 'next/link';

export interface PricingComparisonTableProps {
  /** When false the Fundadores column is hidden. Default true until fetch resolves. */
  showFounders?: boolean;
  foundersSeatsRemaining?: number;
  foundersDeadline?: string | null;
}

interface AvailabilitySnapshot {
  available: boolean;
  seats_remaining: number;
  deadline_at: string | null;
}

const CHECK = (
  <svg
    className="w-5 h-5 text-green-600 dark:text-green-400 mx-auto"
    fill="none"
    stroke="currentColor"
    viewBox="0 0 24 24"
    aria-hidden="true"
  >
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
  </svg>
);

const CROSS = (
  <svg
    className="w-5 h-5 text-[var(--ink-muted)] mx-auto"
    fill="none"
    stroke="currentColor"
    viewBox="0 0 24 24"
    aria-hidden="true"
  >
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
  </svg>
);

const TBD = (
  <span className="text-xs text-[var(--ink-muted)]">a definir</span>
);

interface Row {
  feature: string;
  founders: React.ReactNode;
  proMonthly: React.ReactNode;
  proAnnual: React.ReactNode;
}

const ROWS: Row[] = [
  {
    feature: 'Pagamento',
    founders: <span className="font-semibold text-amber-700 dark:text-amber-300">R$997 ÚNICO</span>,
    proMonthly: <span>R$397/mês</span>,
    proAnnual: <span>R$297/mês</span>,
  },
  {
    feature: 'Acesso',
    founders: <span className="font-medium">Vitalício*</span>,
    proMonthly: <span>Recorrente</span>,
    proAnnual: <span>Recorrente</span>,
  },
  {
    feature: 'Self-service buscas',
    founders: CHECK,
    proMonthly: CHECK,
    proAnnual: CHECK,
  },
  {
    feature: 'Consultoria 50% off',
    founders: CHECK,
    proMonthly: CROSS,
    proAnnual: CROSS,
  },
  {
    feature: 'Features premium futuras',
    founders: CROSS,
    proMonthly: TBD,
    proAnnual: TBD,
  },
  {
    feature: 'Suporte prioritário',
    founders: CROSS,
    proMonthly: CROSS,
    proAnnual: CROSS,
  },
];

export default function PricingComparisonTable({
  showFounders: showFoundersInitial = true,
  foundersSeatsRemaining,
  foundersDeadline,
}: PricingComparisonTableProps) {
  const [showFounders, setShowFounders] = useState(showFoundersInitial);
  const [seatsRemaining, setSeatsRemaining] = useState<number | undefined>(foundersSeatsRemaining);
  const [deadline, setDeadline] = useState<string | null>(foundersDeadline ?? null);

  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/founding/availability', { cache: 'no-store', signal: controller.signal })
      .then((res) => {
        if (!res.ok) return null;
        return res.json() as Promise<AvailabilitySnapshot>;
      })
      .then((data) => {
        if (!data) return;
        if (!data.available || data.seats_remaining === 0) {
          setShowFounders(false);
        }
        setSeatsRemaining(data.seats_remaining);
        setDeadline(data.deadline_at);
      })
      .catch((err) => {
        // Fail-open: keep showing founders column on transient errors or abort
        if (err instanceof Error && err.name === 'AbortError') return;
      });
    return () => {
      controller.abort();
    };
  }, []);

  const deadlineLabel = deadline
    ? new Date(deadline).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' })
    : '30/06';

  const colCount = showFounders ? 3 : 2;

  return (
    <div className="w-full">
      <div className="overflow-x-auto rounded-lg border border-[var(--border)] shadow-sm">
        <table className="w-full bg-[var(--surface-0)] text-sm">
          {/* Header */}
          <thead>
            <tr className="border-b border-[var(--border)]">
              <th scope="col" className="px-4 py-4 text-left font-semibold text-[var(--ink)] w-[30%] min-w-[140px]">
                Funcionalidade
              </th>

              {showFounders && (
                <th scope="col" className="px-4 py-4 text-center bg-amber-50 dark:bg-amber-950/30 border-l border-amber-200 dark:border-amber-800 min-w-[180px]">
                  <div className="flex flex-col items-center gap-2">
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-100 dark:bg-amber-900/50 border border-amber-300 dark:border-amber-700 px-2.5 py-0.5 text-[11px] font-semibold text-amber-800 dark:text-amber-200 leading-none">
                      <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
                        <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                      </svg>
                      Oferta limitada — encerra {deadlineLabel}
                    </span>
                    <span className="font-bold text-base text-[var(--ink)]">Plano Fundadores</span>
                    {seatsRemaining !== undefined && (
                      <span className="text-xs text-amber-700 dark:text-amber-300 font-medium">
                        {seatsRemaining} {seatsRemaining === 1 ? 'vaga restante' : 'vagas restantes'}
                      </span>
                    )}
                    <Link
                      href="/fundadores"
                      className="mt-1 inline-block rounded-lg bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold px-3 py-1.5 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 focus-visible:ring-offset-1"
                    >
                      Garantir vitalício por R$997
                    </Link>
                  </div>
                </th>
              )}

              <th
                scope="col"
                className={`px-4 py-4 text-center min-w-[150px] ${showFounders ? 'border-l border-[var(--border)]' : ''}`}
              >
                <div className="flex flex-col items-center gap-1">
                  <span className="font-bold text-base text-[var(--ink)]">SmartLic Pro</span>
                  <span className="text-xs text-[var(--ink-muted)]">Mensal</span>
                  <span className="text-sm font-semibold text-[var(--brand-blue)]">R$397/mês</span>
                  <Link
                    href="/planos?billing=monthly"
                    className="mt-1 inline-block rounded-lg bg-[var(--brand-blue)] hover:bg-[var(--brand-blue)]/90 text-white text-xs font-semibold px-3 py-1.5 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand-blue)] focus-visible:ring-offset-1"
                  >
                    Assinar agora
                  </Link>
                </div>
              </th>

              <th scope="col" className="px-4 py-4 text-center border-l border-[var(--border)] min-w-[150px]">
                <div className="flex flex-col items-center gap-1">
                  <span className="inline-flex items-center gap-1 rounded-full bg-green-50 dark:bg-green-900/30 border border-green-200 dark:border-green-800 px-2 py-0.5 text-[10px] font-semibold text-green-700 dark:text-green-300 leading-none mb-0.5">
                    25% off
                  </span>
                  <span className="font-bold text-base text-[var(--ink)]">SmartLic Pro</span>
                  <span className="text-xs text-[var(--ink-muted)]">Anual</span>
                  <span className="text-sm font-semibold text-[var(--brand-blue)]">R$297/mês</span>
                  <Link
                    href="/planos?billing=annual"
                    className="mt-1 inline-block rounded-lg bg-[var(--brand-blue)] hover:bg-[var(--brand-blue)]/90 text-white text-xs font-semibold px-3 py-1.5 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand-blue)] focus-visible:ring-offset-1"
                  >
                    Assinar agora
                  </Link>
                </div>
              </th>
            </tr>
          </thead>

          {/* Body */}
          <tbody className="divide-y divide-[var(--border)]">
            {ROWS.map((row) => (
              <tr key={row.feature} className="hover:bg-[var(--surface-1)] transition-colors">
                <td className="px-4 py-3 font-medium text-[var(--ink)]">{row.feature}</td>
                {showFounders && (
                  <td className="px-4 py-3 text-center bg-amber-50/50 dark:bg-amber-950/10 border-l border-amber-200/60 dark:border-amber-800/40">
                    {row.founders}
                  </td>
                )}
                <td className={`px-4 py-3 text-center text-[var(--ink-secondary)] ${showFounders ? 'border-l border-[var(--border)]' : ''}`}>
                  {row.proMonthly}
                </td>
                <td className="px-4 py-3 text-center text-[var(--ink-secondary)] border-l border-[var(--border)]">
                  {row.proAnnual}
                </td>
              </tr>
            ))}
          </tbody>

          {/* Footer row showing disclaimer */}
          <tfoot>
            <tr className="border-t border-[var(--border)] bg-[var(--surface-1)]">
              <td
                colSpan={colCount + 1}
                className="px-4 py-3 text-xs text-[var(--ink-muted)] italic"
              >
                *Acesso vitalício ao plano self-service atual. Features premium/enterprise futuras podem requerer assinatura adicional.
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}
