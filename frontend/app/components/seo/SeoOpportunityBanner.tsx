'use client';

import Link from 'next/link';
import { TrackedCTALink } from '@/app/components/seo/TrackedCTALink';

interface SeoOpportunityBannerProps {
  sector: string;
  sectorName?: string;
  uf?: string;
}

/**
 * COPY-COP-006: SEO programmatic banner for sector/UF landing pages.
 *
 * Renders a contextual CTA banner with dynamic sector name and optional UF:
 *   "Buscando editais de {sectorName} em {ufName ou 'todo Brasil'}?
 *    O SmartLic encontra automaticamente para você."
 *
 * Insert into:
 *   - /licitacoes/[setor]
 *   - /contratos/[setor]/[uf]
 */
export function SeoOpportunityBanner({
  sector,
  sectorName,
  uf,
}: SeoOpportunityBannerProps) {
  const displayName = sectorName || sector;
  const location = uf ? em(uf) : 'em todo o Brasil';
  const searchUrl = `/buscar?setor=${sector}${uf ? `&uf=${uf}` : ''}`;

  return (
    <div className="rounded-xl bg-gradient-to-br from-brand-blue/5 to-brand-blue/10 border border-brand-blue/20 p-6 sm:p-8 my-8">
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
        <div className="flex-1">
          <h3 className="text-lg font-bold text-ink mb-2">
            Buscando editais de {displayName} {location}?
          </h3>
          <p className="text-ink-secondary text-sm">
            O SmartLic encontra automaticamente oportunidades para o seu setor,
            analisa a viabilidade e prioriza os melhores editais para você.
          </p>
        </div>
        <TrackedCTALink
          href={searchUrl}
          eventName="seo_banner_click"
          eventProps={{ sector, uf: uf || null }}
          className="inline-flex items-center gap-2 px-6 py-3 bg-brand-blue text-white font-semibold rounded-lg hover:bg-blue-700 transition-colors whitespace-nowrap shrink-0"
        >
          Ver oportunidades do meu setor
          <svg
            className="w-4 h-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M17 8l4 4m0 0l-4 4m4-4H3"
            />
          </svg>
        </TrackedCTALink>
      </div>
    </div>
  );
}

/** Format UF code as "em {UF}" with state name for common UFs. */
function em(uf: string): string {
  const states: Record<string, string> = {
    AC: 'Acre', AL: 'Alagoas', AP: 'Amapá', AM: 'Amazonas',
    BA: 'Bahia', CE: 'Ceará', DF: 'Distrito Federal',
    ES: 'Espírito Santo', GO: 'Goiás', MA: 'Maranhão',
    MT: 'Mato Grosso', MS: 'Mato Grosso do Sul', MG: 'Minas Gerais',
    PA: 'Pará', PB: 'Paraíba', PR: 'Paraná', PE: 'Pernambuco',
    PI: 'Piauí', RJ: 'Rio de Janeiro', RN: 'Rio Grande do Norte',
    RS: 'Rio Grande do Sul', RO: 'Rondônia', RR: 'Roraima',
    SC: 'Santa Catarina', SP: 'São Paulo', SE: 'Sergipe', TO: 'Tocantins',
  };
  const name = states[uf.toUpperCase()];
  return name ? `em ${name}` : `no ${uf.toUpperCase()}`;
}
