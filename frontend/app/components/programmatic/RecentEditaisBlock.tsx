"use client";
/**
 * RecentEditaisBlock — Issue #1007 (PSEODataBlock)
 *
 * Social proof block: "Últimos editais publicados de {setorLabel} em {ufLabel}"
 * DataLake source: pncp_raw_bids, ordered by data_publicacao desc.
 */

import { useEffect, useState } from "react";
import Link from "next/link";

export interface RecentEditaisBlockProps {
  setor: string;        // URL slug, e.g. "construcao-civil"
  uf?: string;          // UF code, e.g. "SP"
  setorLabel: string;   // Human label, e.g. "Construção Civil"
  ufLabel: string;      // Human label, e.g. "São Paulo"
  totalOpen?: number;   // Total open editais for the footer link label
}

interface EditalItem {
  orgao: string;
  objeto: string;
  valor_estimado: number | null;
  data_limite: string | null;
  data_publicacao: string | null;
  link_interno: string;
}

interface RecentEditaisResponse {
  items: EditalItem[];
  total: number;
}

function formatBRL(value: number | null): string {
  if (value === null || value === undefined) return "N/I";
  if (value >= 1_000_000) {
    return `R$ ${(value / 1_000_000).toFixed(1)} M`;
  }
  if (value >= 1_000) {
    return `R$ ${(value / 1_000).toFixed(0)} mil`;
  }
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "—";
  try {
    return new Date(dateStr).toLocaleDateString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

/** Skeleton row shown while loading */
function SkeletonRow() {
  return (
    <tr className="border-b border-gray-100 dark:border-gray-800">
      {[1, 2, 3, 4].map((i) => (
        <td key={i} className="px-4 py-3">
          <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
        </td>
      ))}
    </tr>
  );
}

export function RecentEditaisBlock({
  setor,
  uf,
  setorLabel,
  ufLabel,
  totalOpen,
}: RecentEditaisBlockProps) {
  const [data, setData] = useState<RecentEditaisResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const params = new URLSearchParams({ setor });
    if (uf) params.set("uf", uf);

    const promise = fetch(`/api/pseo/recent-editais?${params.toString()}`);
    if (!promise) { setLoading(false); return; }
    promise
      .then((res) => (res.ok ? res.json() : null))
      .then((json) => setData(json))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [setor, uf]);

  // Empty state: hide section if no data
  if (!loading && (!data || data.items.length === 0)) {
    return null;
  }

  const verTodosHref = `/licitacoes/${setor}${uf ? `?uf=${uf}` : ""}`;
  const verTodosLabel =
    totalOpen && totalOpen > 0
      ? `Ver todos os ${totalOpen} editais →`
      : "Ver todos os editais →";

  return (
    <section
      className="max-w-5xl mx-auto py-10 px-4"
      aria-label={`Últimos editais de ${setorLabel} em ${ufLabel}`}
    >
      <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">
        Últimos editais publicados de {setorLabel} em {ufLabel}
      </h2>

      <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-700">
        <table className="w-full text-sm text-left">
          <thead className="text-xs text-gray-500 uppercase bg-gray-50 dark:bg-gray-800 dark:text-gray-400">
            <tr>
              <th className="px-4 py-3">Órgão</th>
              <th className="px-4 py-3">Objeto</th>
              <th className="px-4 py-3 text-right">Valor Est.</th>
              <th className="px-4 py-3 text-center">Data Limite</th>
            </tr>
          </thead>
          <tbody>
            {loading
              ? Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} />)
              : data?.items.map((item, idx) => (
                  <tr
                    key={idx}
                    className="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
                  >
                    <td className="px-4 py-3 text-gray-700 dark:text-gray-300 max-w-[180px] truncate">
                      {item.orgao}
                    </td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400 max-w-xs">
                      <Link
                        href={item.link_interno}
                        className="hover:text-brand-blue hover:underline"
                        title={item.objeto}
                      >
                        {item.objeto}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-right text-gray-600 dark:text-gray-400 whitespace-nowrap">
                      {formatBRL(item.valor_estimado)}
                    </td>
                    <td className="px-4 py-3 text-center text-gray-600 dark:text-gray-400 whitespace-nowrap">
                      {formatDate(item.data_limite)}
                    </td>
                  </tr>
                ))}
          </tbody>
        </table>
      </div>

      <p className="mt-3 text-sm">
        <Link
          href={verTodosHref}
          className="text-brand-blue hover:underline"
        >
          {verTodosLabel}
        </Link>
      </p>
    </section>
  );
}
