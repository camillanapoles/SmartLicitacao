/**
 * ContratosHubPanel — painel acima da dobra para o Hub de Contratos Públicos.
 *
 * PSEO-HUB-002: Server component com links de busca de contratos por fornecedor/órgão.
 * Não faz fetch de dados dinâmicos (hub de navegação estrutural).
 */

import Link from 'next/link';

const SECTOR_LINKS = [
  { slug: 'engenharia', label: 'Contratos de Engenharia', ufs: ['SP', 'MG', 'RJ'] },
  { slug: 'saude', label: 'Contratos de Saúde', ufs: ['SP', 'MG', 'DF'] },
  { slug: 'informatica', label: 'Contratos de TI', ufs: ['SP', 'DF', 'PR'] },
  { slug: 'alimentos', label: 'Contratos de Alimentos', ufs: ['SP', 'BA', 'MG'] },
  { slug: 'facilities', label: 'Contratos de Facilities', ufs: ['SP', 'RJ', 'DF'] },
];

export default function ContratosHubPanel() {
  return (
    <div className="not-prose mb-10">
      {/* CTA principal — above the fold */}
      <div className="bg-gradient-to-r from-brand-navy to-brand-blue rounded-xl p-6 sm:p-8 text-white mb-6">
        <h2 className="text-xl sm:text-2xl font-bold mb-2">
          Consulte contratos públicos por fornecedor ou órgão
        </h2>
        <p className="text-white/80 text-sm sm:text-base mb-4 max-w-xl">
          Mais de 2 milhões de contratos extraídos do PNCP. Veja histórico de
          fornecedores, órgãos compradores e valores reais de contratação.
        </p>
        <div className="flex flex-col sm:flex-row gap-3">
          <Link
            href="/signup?source=contratos-hub&utm_source=blog&utm_medium=hub&utm_content=contratos-pncp"
            className="inline-block bg-white text-brand-navy font-semibold px-6 py-3 rounded-button text-sm transition-all hover:scale-[1.02] active:scale-[0.98] text-center"
          >
            Buscar contratos agora
          </Link>
          <Link
            href="/fornecedores"
            className="inline-block bg-white/10 hover:bg-white/20 border border-white/30 text-white font-medium px-6 py-3 rounded-button text-sm transition-all text-center"
          >
            Ver fornecedores →
          </Link>
        </div>
      </div>

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
