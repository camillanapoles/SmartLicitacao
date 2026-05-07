/**
 * STORY-SEO-029: Dataset JSON-LD warnings.
 *
 * Validates the fields reported by GSC as missing on /licitacoes/[setor].
 */

import { buildDatasetJsonLd } from '@/app/licitacoes/[setor]/_jsonld';
import type { SectorStats } from '@/lib/sectors';

jest.mock('@/lib/sectors', () => ({
  getAllSectorSlugs: jest.fn(() => ['saude']),
  getSectorBySlug: jest.fn(),
  getRelatedSectors: jest.fn(() => []),
  fetchSectorStats: jest.fn(),
  formatBRL: jest.fn((value: number) => `R$ ${value}`),
  SECTORS: [],
}));
jest.mock('@/data/sector-faqs', () => ({ getSectorFaqs: jest.fn(() => []) }));
jest.mock('@/lib/seo', () => ({ getFreshnessLabel: jest.fn(() => 'Hoje') }));
jest.mock('@/components/seo/MicroDemo', () => ({ MicroDemo: () => null }));
jest.mock('@/components/seo/MicroDemoSchema', () => ({ MicroDemoSchema: () => null }));
jest.mock('@/lib/programmatic', () => ({ UF_NAMES: { SP: 'São Paulo' } }));

const sector = {
  name: 'Saúde',
  slug: 'saude',
};

const stats: SectorStats = {
  sector_id: 'saude',
  sector_name: 'Saúde',
  sector_description: 'Medicamentos, equipamentos hospitalares, insumos médicos',
  slug: 'saude',
  total_open: 42,
  total_value: 1_500_000,
  avg_value: 35_714,
  top_ufs: [{ name: 'SP', count: 12 }],
  top_modalidades: [{ name: 'Pregão Eletrônico', count: 20 }],
  sample_items: [],
  last_updated: '2026-05-05T12:00:00Z',
};

describe('Dataset JSON-LD schema (#614)', () => {
  it('includes description, license, distribution.contentUrl, and creator', () => {
    const dataset = buildDatasetJsonLd(sector, stats) as Record<string, any>;

    expect(dataset['@type']).toBe('Dataset');
    expect(dataset.description).toContain('PNCP');
    expect(dataset.description.length).toBeGreaterThanOrEqual(50);
    expect(dataset.license).toBe('https://creativecommons.org/licenses/by/4.0/');
    expect(dataset.creator).toEqual({
      '@type': 'Organization',
      name: 'SmartLic / CONFENGE Avaliacoes e Inteligencia Artificial LTDA',
      url: 'https://smartlic.tech',
    });
    expect(dataset.distribution).toEqual([
      {
        '@type': 'DataDownload',
        encodingFormat: 'application/json',
        contentUrl: 'https://smartlic.tech/v1/sectors/saude/stats',
      },
    ]);
  });

  it('matches the expected Dataset schema snapshot', () => {
    const dataset = buildDatasetJsonLd(sector, stats);

    expect(dataset).toMatchInlineSnapshot(`
{
  "@context": "https://schema.org",
  "@type": "Dataset",
  "creator": {
    "@type": "Organization",
    "name": "SmartLic / CONFENGE Avaliacoes e Inteligencia Artificial LTDA",
    "url": "https://smartlic.tech",
  },
  "description": "Dataset ao vivo com 42 licitações públicas abertas de Saúde no Brasil, agregadas do PNCP (Portal Nacional de Contratações Públicas) e atualizadas a cada 6 horas.",
  "distribution": [
    {
      "@type": "DataDownload",
      "contentUrl": "https://smartlic.tech/v1/sectors/saude/stats",
      "encodingFormat": "application/json",
    },
  ],
  "isAccessibleForFree": true,
  "isBasedOn": {
    "@type": "Dataset",
    "name": "PNCP — Portal Nacional de Contratações Públicas",
    "publisher": {
      "@type": "GovernmentOrganization",
      "name": "Governo Federal do Brasil",
    },
    "url": "https://pncp.gov.br",
  },
  "keywords": [
    "licitações Saúde",
    "editais Saúde",
    "PNCP",
    "contratações públicas",
    "Lei 14.133",
  ],
  "license": "https://creativecommons.org/licenses/by/4.0/",
  "measurementTechnique": "Agregação automatizada via PNCP — Portal Nacional de Contratações Públicas, com deduplicação por content hash e classificação setorial via LLM (GPT-4.1-nano)",
  "name": "Licitações de Saúde — Dataset SmartLic",
  "publisher": {
    "@type": "Organization",
    "name": "SmartLic",
    "url": "https://smartlic.tech",
  },
  "size": "42 editais abertos",
  "spatialCoverage": {
    "@type": "Place",
    "geo": {
      "@type": "GeoShape",
      "addressCountry": "BR",
    },
    "name": "Brasil",
  },
  "temporalCoverage": "2024-01-01/..",
  "url": "https://smartlic.tech/licitacoes/saude",
  "variableMeasured": [
    "Total de licitações públicas abertas",
    "Valor médio por edital",
    "Órgãos contratantes",
    "Modalidades de contratação",
  ],
}
`);
  });

  it('keeps a substantive description when live stats are unavailable', () => {
    const dataset = buildDatasetJsonLd(sector, null) as Record<string, any>;

    expect(dataset.description).toContain('Dataset ao vivo de licitações públicas de Saúde');
    expect(dataset.description.length).toBeGreaterThanOrEqual(50);
    expect(dataset.size).toBeUndefined();
  });
});
