/**
 * SectorHubPanel — painel de dados reais acima da dobra para hubs setoriais.
 *
 * PSEO-HUB-002: Async server component usado em TI, Saúde, Engenharia e Contratos.
 * Busca dados do backend com ISR 3600s e exibe:
 * - CTA principal com contexto do setor
 * - Sub-categorias com links para UFs
 * - Links internos cruzados
 *
 * Todos os fetches usam next:{revalidate:3600} conforme padrão SEN-FE-001.
 */

import Link from 'next/link';
import { SECTOR_SLUG_TO_BACKEND_ID, formatBRL } from '@/lib/programmatic';
import type { PanoramaStats } from '@/lib/programmatic';

export interface SectorHubConfig {
  /** Slug do setor (ex: 'informatica', 'saude', 'engenharia') */
  sectorSlug: string;
  /** Nome do setor para exibição */
  sectorName: string;
  /** Título principal do hub */
  title: string;
  /** Subtítulo descritivo */
  subtitle: string;
  /** Texto do CTA principal */
  ctaText: string;
  /** href do CTA principal (signup) */
  ctaHref: string;
  /** Sub-categorias do setor */
  subcategories: Array<{ label: string; href: string }>;
  /** UFs prioritárias para links de editais */
  priorityUfs: Array<{ uf: string; name: string }>;
  /** Links internos adicionais */
  internalLinks: Array<{ href: string; label: string }>;
}

// UFs prioritárias comuns
const TOP_UFS = [
  { uf: 'SP', name: 'São Paulo' },
  { uf: 'RJ', name: 'Rio de Janeiro' },
  { uf: 'MG', name: 'Minas Gerais' },
  { uf: 'DF', name: 'Distrito Federal' },
  { uf: 'PR', name: 'Paraná' },
  { uf: 'RS', name: 'Rio Grande do Sul' },
];

/**
 * Fetch panorama stats com ISR 3600s (1h) — padrão hub utilitário.
 * Nota: fetchPanoramaStats da lib usa 86400 (24h). Para hubs, usamos 3600.
 */
async function fetchHubPanoramaStats(sectorSlug: string): Promise<PanoramaStats | null> {
  const backendUrl = process.env.BACKEND_URL;
  if (!backendUrl) return null;
  try {
    const sectorId = SECTOR_SLUG_TO_BACKEND_ID[sectorSlug] ?? sectorSlug.replace(/-/g, '_');
    const res = await fetch(`${backendUrl}/v1/blog/stats/panorama/${sectorId}`, {
      next: { revalidate: 3600 },
      signal: AbortSignal.timeout(10000),
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export default async function SectorHubPanel({ config }: { config: SectorHubConfig }) {
  // Busca panorama nacional com ISR 3600s (1h) — requisito PSEO-HUB-002
  let panorama: PanoramaStats | null = null;
  try {
    panorama = await fetchHubPanoramaStats(config.sectorSlug);
  } catch {
    // Falha silenciosa — exibe panel sem KPIs
  }

  const ufs = config.priorityUfs.length > 0 ? config.priorityUfs : TOP_UFS;

  return (
    <div className="not-prose mb-10">
      {/* CTA principal — above the fold */}
      <div className="bg-gradient-to-r from-brand-navy to-brand-blue rounded-xl p-6 sm:p-8 text-white mb-6">
        <h2 className="text-xl sm:text-2xl font-bold mb-2">
          {config.title}
        </h2>
        <p className="text-white/80 text-sm sm:text-base mb-4 max-w-xl">
          {config.subtitle}
        </p>

        {/* KPIs se disponíveis */}
        {panorama && panorama.total_nacional > 0 && (
          <div className="flex flex-wrap gap-4 mb-4 text-sm">
            <div className="bg-white/10 rounded-lg px-3 py-2">
              <span className="block font-bold text-white">{panorama.total_nacional.toLocaleString('pt-BR')}</span>
              <span className="text-white/70 text-xs">editais publicados</span>
            </div>
            {panorama.total_value > 0 && (
              <div className="bg-white/10 rounded-lg px-3 py-2">
                <span className="block font-bold text-white">{formatBRL(panorama.total_value)}</span>
                <span className="text-white/70 text-xs">volume total</span>
              </div>
            )}
            {panorama.avg_value > 0 && (
              <div className="bg-white/10 rounded-lg px-3 py-2">
                <span className="block font-bold text-white">{formatBRL(panorama.avg_value)}</span>
                <span className="text-white/70 text-xs">valor médio</span>
              </div>
            )}
          </div>
        )}

        <div className="flex flex-col sm:flex-row gap-3">
          <Link
            href={config.ctaHref}
            className="inline-block bg-white text-brand-navy font-semibold px-6 py-3 rounded-button text-sm transition-all hover:scale-[1.02] active:scale-[0.98] text-center"
          >
            {config.ctaText}
          </Link>
          <Link
            href={`/blog/licitacoes/${config.sectorSlug}/SP`}
            className="inline-block bg-white/10 hover:bg-white/20 border border-white/30 text-white font-medium px-6 py-3 rounded-button text-sm transition-all text-center"
          >
            Ver editais em SP →
          </Link>
        </div>
      </div>

      {/* Sub-categorias */}
      {config.subcategories.length > 0 && (
        <div className="mb-6">
          <h3 className="text-sm font-semibold text-[var(--ink)] mb-3">
            Sub-categorias — acesse diretamente
          </h3>
          <div className="flex flex-wrap gap-2">
            {config.subcategories.map((sub) => (
              <Link
                key={sub.href}
                href={sub.href}
                className="px-3 py-1.5 text-sm font-medium text-[var(--brand-blue)] bg-[var(--brand-blue-subtle)] border border-[var(--brand-blue)]/20 rounded-full hover:bg-[var(--brand-blue)]/10 transition-colors"
              >
                {sub.label}
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Editais por UF */}
      <div className="mb-6">
        <h3 className="text-sm font-semibold text-[var(--ink)] mb-3">
          Editais abertos de {config.sectorName} por estado
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {ufs.map(({ uf, name }) => (
            <Link
              key={uf}
              href={`/blog/licitacoes/${config.sectorSlug}/${uf}`}
              className="flex items-center justify-between px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--surface-1)] hover:border-[var(--brand-blue)] hover:shadow-sm transition-all text-sm group"
            >
              <span className="text-[var(--ink-secondary)] group-hover:text-[var(--brand-blue)] transition-colors truncate">
                {name}
              </span>
              <span className="text-[var(--brand-blue)] font-bold text-xs ml-2 shrink-0">{uf}</span>
            </Link>
          ))}
        </div>
        <p className="text-xs text-[var(--ink-secondary)] mt-2">
          Dados atualizados via PNCP. ISR 1h.
        </p>
      </div>

      {/* Links internos adicionais */}
      {config.internalLinks.length > 0 && (
        <div className="bg-[var(--surface-1)] rounded-lg border border-[var(--border)] p-4">
          <h3 className="text-sm font-semibold text-[var(--ink)] mb-3">
            Dados relacionados — navegue diretamente
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {config.internalLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="text-sm text-[var(--brand-blue)] hover:underline flex items-center gap-1"
              >
                <span aria-hidden="true">→</span>
                {link.label}
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
