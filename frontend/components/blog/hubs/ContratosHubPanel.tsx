/**
 * ContratosHubPanel — painel acima da dobra para o Hub de Contratos Públicos.
 *
 * PSEO-HUB-002: Async server component com ISR 3600s.
 * Busca dados reais de contratos por setor/UF via backend e exibe
 * ContractsPanoramaBlock com dados de engenharia/SP como âncora principal.
 * Retorna null silenciosamente se BACKEND_URL não estiver configurado.
 */

import Link from 'next/link';
import ContractsPanoramaBlock from '@/components/blog/ContractsPanoramaBlock';
import { SECTOR_SLUG_TO_BACKEND_ID } from '@/lib/programmatic';
import type { ContratosSetorUfStats } from '@/lib/contracts-fallback';

const SECTOR_LINKS = [
  { slug: 'engenharia', label: 'Contratos de Engenharia', ufs: ['SP', 'MG', 'RJ'] },
  { slug: 'saude', label: 'Contratos de Saúde', ufs: ['SP', 'MG', 'DF'] },
  { slug: 'informatica', label: 'Contratos de TI', ufs: ['SP', 'DF', 'PR'] },
  { slug: 'alimentos', label: 'Contratos de Alimentos', ufs: ['SP', 'BA', 'MG'] },
  { slug: 'facilities', label: 'Contratos de Facilities', ufs: ['SP', 'RJ', 'DF'] },
];

// Fetcher local com ISR 3600s (lib/contracts-fallback usa 86400 — aqui precisamos 3600 por AC)
async function fetchContratosHubStats(
  sectorSlug: string,
  uf: string,
): Promise<ContratosSetorUfStats | null> {
  const backendUrl = process.env.BACKEND_URL;
  if (!backendUrl) return null;
  try {
    const sectorId = SECTOR_SLUG_TO_BACKEND_ID[sectorSlug] ?? sectorSlug.replace(/-/g, '_');
    const res = await fetch(
      `${backendUrl}/v1/blog/stats/contratos/${sectorId}/uf/${uf.toUpperCase()}`,
      { next: { revalidate: 3600 }, signal: AbortSignal.timeout(10000) },
    );
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export default async function ContratosHubPanel() {
  // Âncora: engenharia/SP — setor de maior volume de contratos
  const engenhSpData = await fetchContratosHubStats('engenharia', 'SP');

  return (
    <div className="not-prose mb-10">
      {/* CTA principal — above the fold */}
      <div className="bg-gradient-to-r from-brand-navy to-brand-blue rounded-xl p-6 sm:p-8 text-white mb-6">
        <h2 className="text-xl sm:text-2xl font-bold mb-2">
          Descubra quem compra do seu setor no governo
        </h2>
        <p className="text-white/80 text-sm sm:text-base mb-4 max-w-xl">
          2 milhões de contratos do PNCP indexados por fornecedor, órgão, valor
          e setor. Atualização diária.
        </p>
        <div className="flex flex-col sm:flex-row gap-3">
          <Link
            href="/contratos?source=blog-contratos"
            className="inline-block bg-white text-brand-navy font-semibold px-6 py-3 rounded-button text-sm transition-all hover:scale-[1.02] active:scale-[0.98] text-center"
          >
            Consultar contratos agora
          </Link>
          <Link
            href="/contratos/fornecedores"
            className="inline-block bg-white/10 hover:bg-white/20 border border-white/30 text-white font-medium px-6 py-3 rounded-button text-sm transition-all text-center"
          >
            Ver maiores fornecedores →
          </Link>
        </div>
      </div>

      {/* Panorama real — Engenharia/SP como âncora de dados */}
      {engenhSpData && (
        <div className="mb-6">
          <ContractsPanoramaBlock
            variant="setor-uf"
            data={engenhSpData}
            sectorName="Engenharia"
            ufName="São Paulo"
            uf="SP"
          />
        </div>
      )}

      {/* Busca por tipo */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
        {/* Busca por CNPJ */}
        <div className="p-4 rounded-lg border border-[var(--border)] bg-[var(--surface-1)]">
          <h3 className="text-sm font-semibold text-[var(--ink)] mb-2">
            Por CNPJ do fornecedor
          </h3>
          <p className="text-xs text-[var(--ink-secondary)] mb-3 leading-relaxed">
            Veja todos os contratos de uma empresa com o governo — histórico completo, valores e órgãos.
          </p>
          <Link
            href="/fornecedores"
            className="text-sm font-medium text-[var(--brand-blue)] hover:underline"
          >
            Buscar por CNPJ →
          </Link>
        </div>

        {/* Busca por órgão */}
        <div className="p-4 rounded-lg border border-[var(--border)] bg-[var(--surface-1)]">
          <h3 className="text-sm font-semibold text-[var(--ink)] mb-2">
            Por órgão público
          </h3>
          <p className="text-xs text-[var(--ink-secondary)] mb-3 leading-relaxed">
            Identifique os maiores compradores de cada setor — órgãos com maior volume de contratações.
          </p>
          <Link
            href="/orgaos"
            className="text-sm font-medium text-[var(--brand-blue)] hover:underline"
          >
            Ver órgãos compradores →
          </Link>
        </div>
      </div>

      {/* Contratos por setor */}
      <div className="mb-6">
        <h3 className="text-sm font-semibold text-[var(--ink)] mb-3">
          Contratos por setor e estado
        </h3>
        <div className="space-y-2">
          {SECTOR_LINKS.map((sector) => (
            <div
              key={sector.slug}
              className="flex flex-col sm:flex-row sm:items-center gap-2 p-3 rounded-lg border border-[var(--border)] bg-[var(--surface-1)]"
            >
              <span className="text-sm font-medium text-[var(--ink)] sm:w-40 shrink-0">
                {sector.label}
              </span>
              <div className="flex flex-wrap gap-2">
                {sector.ufs.map((uf) => (
                  <Link
                    key={uf}
                    href={`/contratos/${sector.slug}/${uf}`}
                    className="px-2.5 py-1 text-xs font-medium text-[var(--brand-blue)] bg-[var(--brand-blue-subtle)] border border-[var(--brand-blue)]/20 rounded-full hover:bg-[var(--brand-blue)]/10 transition-colors"
                  >
                    {uf}
                  </Link>
                ))}
                <Link
                  href={`/contratos/${sector.slug}/SP`}
                  className="px-2.5 py-1 text-xs font-medium text-[var(--ink-secondary)] hover:text-[var(--brand-blue)] transition-colors"
                >
                  ver todos →
                </Link>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Links diretos para contratos por órgão */}
      <div className="bg-[var(--surface-1)] rounded-lg border border-[var(--border)] p-4">
        <h3 className="text-sm font-semibold text-[var(--ink)] mb-3">
          Acesso direto por vínculo
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          <Link href="/contratos/orgao" className="text-sm text-[var(--brand-blue)] hover:underline flex items-center gap-1">
            <span aria-hidden="true">→</span> Contratos por órgão contratante
          </Link>
          <Link href="/fornecedores" className="text-sm text-[var(--brand-blue)] hover:underline flex items-center gap-1">
            <span aria-hidden="true">→</span> Fornecedores mais contratados
          </Link>
          <Link href="/contratos/engenharia/SP" className="text-sm text-[var(--brand-blue)] hover:underline flex items-center gap-1">
            <span aria-hidden="true">→</span> Contratos de obras em SP
          </Link>
          <Link href="/contratos/saude/DF" className="text-sm text-[var(--brand-blue)] hover:underline flex items-center gap-1">
            <span aria-hidden="true">→</span> Contratos de saúde no DF
          </Link>
        </div>
      </div>
    </div>
  );
}
