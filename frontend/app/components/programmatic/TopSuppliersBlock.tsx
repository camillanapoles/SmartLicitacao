"use client";
/**
 * TopSuppliersBlock — Issue #1007 (PSEODataBlock)
 *
 * Social proof block: "Quem ganha contratos de {setorLabel} em {ufLabel}"
 * DataLake source: pncp_supplier_contracts aggregated by CNPJ.
 * LGPD: CNPJ not shown as plain text — only as an href in "Ver perfil →".
 */

import { useEffect, useState } from "react";
import Link from "next/link";

export interface TopSuppliersBlockProps {
  setor: string;       // URL slug, e.g. "construcao-civil"
  uf?: string;         // UF code, e.g. "SP"
  setorLabel: string;  // Human label, e.g. "Construção Civil"
  ufLabel: string;     // Human label, e.g. "São Paulo"
}

interface SupplierItem {
  razao_social: string;
  cnpj: string;
  contratos_count: number;
  valor_total: number;
}

interface TopSuppliersResponse {
  items: SupplierItem[];
  total_contracts_in_scope: number;
  last_updated: string;
}

function formatBRL(value: number): string {
  if (value >= 1_000_000) {
    return `R$ ${(value / 1_000_000).toFixed(1)} M`;
  }
  if (value >= 1_000) {
    return `R$ ${(value / 1_000).toFixed(0)} mil`;
  }
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
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

export function TopSuppliersBlock({
  setor,
  uf,
  setorLabel,
  ufLabel,
}: TopSuppliersBlockProps) {
  const [data, setData] = useState<TopSuppliersResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const params = new URLSearchParams({ setor });
    if (uf) params.set("uf", uf);

    const promise = fetch(`/api/pseo/top-suppliers?${params.toString()}`);
    if (!promise) { setLoading(false); return; }
    promise
      .then((res) => (res.ok ? res.json() : null))
      .then((json) => setData(json))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [setor, uf]);

  // Empty state: hide section entirely (no weak social proof)
  if (!loading && (!data || data.items.length === 0)) {
    return null;
  }

  return (
    <section
      className="max-w-5xl mx-auto py-10 px-4"
      aria-label={`Top fornecedores de ${setorLabel} em ${ufLabel}`}
    >
      <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">
        Quem ganha contratos de {setorLabel} em {ufLabel}
      </h2>

      <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-700">
        <table className="w-full text-sm text-left">
          <thead className="text-xs text-gray-500 uppercase bg-gray-50 dark:bg-gray-800 dark:text-gray-400">
            <tr>
              <th className="px-4 py-3">Fornecedor</th>
              <th className="px-4 py-3 text-center">Contratos (12m)</th>
              <th className="px-4 py-3 text-right">Valor Total</th>
              <th className="px-4 py-3 text-center">Perfil</th>
            </tr>
          </thead>
          <tbody>
            {loading
              ? Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} />)
              : data?.items.map((item) => (
                  <tr
                    key={item.cnpj}
                    className="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
                  >
                    <td className="px-4 py-3 font-medium text-gray-900 dark:text-white max-w-xs truncate">
                      {item.razao_social}
                    </td>
                    <td className="px-4 py-3 text-center text-gray-600 dark:text-gray-400">
                      {item.contratos_count.toLocaleString("pt-BR")}
                    </td>
                    <td className="px-4 py-3 text-right text-gray-600 dark:text-gray-400">
                      {formatBRL(item.valor_total)}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {/* LGPD: CNPJ only as href — never rendered as visible text */}
                      <Link
                        href={`/cnpj/${item.cnpj}`}
                        className="text-brand-blue hover:underline text-xs whitespace-nowrap"
                        title={`Ver perfil do fornecedor`}
                      >
                        Ver perfil →
                      </Link>
                    </td>
                  </tr>
                ))}
          </tbody>
        </table>
      </div>

      <p className="mt-3 text-sm text-gray-500 dark:text-gray-400">
        <Link
          href={`/buscar?setor=${setor}${uf ? `&uf=${uf}` : ""}`}
          className="text-brand-blue hover:underline"
        >
          Ver histórico completo de qualquer CNPJ concorrente →
        </Link>
      </p>
    </section>
  );
}
