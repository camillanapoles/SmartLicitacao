import type { SectorStats } from "@/lib/sectors";

// Always emitted — describes the conceptual dataset (PNCP bids for this sector).
// Live `total_open` is enriched opportunistically when available.
export function buildDatasetJsonLd(
  sector: { name: string; slug: string },
  stats: SectorStats | null,
) {
  const totalOpen = stats?.total_open ?? 0;
  const hasLiveCount = totalOpen > 0;
  const description = hasLiveCount
    ? `Dataset ao vivo com ${totalOpen} licitações públicas abertas de ${sector.name} no Brasil, agregadas do PNCP (Portal Nacional de Contratações Públicas) e atualizadas a cada 6 horas.`
    : `Dataset ao vivo de licitações públicas de ${sector.name} no Brasil, agregadas do PNCP (Portal Nacional de Contratações Públicas) e atualizadas a cada 6 horas.`;

  const dataset: Record<string, unknown> = {
    "@context": "https://schema.org",
    "@type": "Dataset",
    name: `Licitações de ${sector.name} — Dataset SmartLic`,
    description,
    keywords: [
      `licitações ${sector.name}`,
      `editais ${sector.name}`,
      "PNCP",
      "contratações públicas",
      "Lei 14.133",
    ],
    variableMeasured: [
      "Total de licitações públicas abertas",
      "Valor médio por edital",
      "Órgãos contratantes",
      "Modalidades de contratação",
    ],
    measurementTechnique:
      "Agregação automatizada via PNCP — Portal Nacional de Contratações Públicas, com deduplicação por content hash e classificação setorial via LLM (GPT-4.1-nano)",
    temporalCoverage: "2024-01-01/..",
    spatialCoverage: {
      "@type": "Place",
      name: "Brasil",
      geo: {
        "@type": "GeoShape",
        addressCountry: "BR",
      },
    },
    isAccessibleForFree: true,
    license: "https://creativecommons.org/licenses/by/4.0/",
    creator: {
      "@type": "Organization",
      name: "SmartLic / CONFENGE Avaliacoes e Inteligencia Artificial LTDA",
      url: "https://smartlic.tech",
    },
    publisher: {
      "@type": "Organization",
      name: "SmartLic",
      url: "https://smartlic.tech",
    },
    isBasedOn: {
      "@type": "Dataset",
      name: "PNCP — Portal Nacional de Contratações Públicas",
      url: "https://pncp.gov.br",
      publisher: {
        "@type": "GovernmentOrganization",
        name: "Governo Federal do Brasil",
      },
    },
    distribution: [
      {
        "@type": "DataDownload",
        encodingFormat: "application/json",
        contentUrl: `https://smartlic.tech/v1/sectors/${sector.slug}/stats`,
      },
    ],
    url: `https://smartlic.tech/licitacoes/${sector.slug}`,
  };

  if (hasLiveCount) {
    (dataset as Record<string, unknown>).size = `${totalOpen} editais abertos`;
  }

  return dataset;
}
