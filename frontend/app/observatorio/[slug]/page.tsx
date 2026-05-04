/**
 * STORY-431 AC1+AC3+AC4+AC5+AC7+AC13+AC14: Observatory monthly report page.
 *
 * Slug format: raio-x-abril-2026 → mes=4, ano=2026
 * Renders charts (BarChart, PieChart, LineChart), CSV download, embed button.
 *
 * AC13: notFound() on fetch failure or malformed slug; generateMetadata returns
 * robots:noindex when data is missing.
 * AC14: Sentry.captureMessage when relatorio is empty (warning level + tags).
 */

import { Metadata } from 'next';
import { notFound } from 'next/navigation';
import * as Sentry from '@sentry/nextjs';
import ObservatorioRelatorioClient from './ObservatorioRelatorioClient';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

const MONTH_NAMES_PT: Record<string, number> = {
  janeiro: 1, fevereiro: 2, marco: 3, abril: 4, maio: 5, junho: 6,
  julho: 7, agosto: 8, setembro: 9, outubro: 10, novembro: 11, dezembro: 12,
};

const MONTH_NAMES_DISPLAY: Record<number, string> = {
  1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho',
  7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro',
};

function parseSlug(slug: string): { mes: number; ano: number } | null {
  // Expected: "raio-x-{mes_nome}-{ano}" e.g. "raio-x-marco-2026"
  const parts = slug.split('-');
  if (parts.length < 4) return null;
  const mesNome = parts[parts.length - 2];
  const anoStr = parts[parts.length - 1];
  const mes = MONTH_NAMES_PT[mesNome.toLowerCase()];
  const ano = parseInt(anoStr, 10);
  if (!mes || isNaN(ano) || ano < 2024) return null;
  return { mes, ano };
}

async function fetchRelatorio(mes: number, ano: number) {
  try {
    const resp = await fetch(`${BACKEND_URL}/v1/observatorio/relatorio/${mes}/${ano}`, {
      next: { revalidate: 86400 }, // 24h ISR
      signal: AbortSignal.timeout(10000),
    });
    if (!resp.ok) return null;
    return await resp.json();
  } catch {
    return null;
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const parsed = parseSlug(slug);
  // STORY-431 AC13: malformed slug → noindex metadata (page itself returns 404).
  if (!parsed) {
    return {
      title: 'Relatório não encontrado',
      robots: { index: false, follow: false },
    };
  }

  const { mes, ano } = parsed;
  const mesDisplay = MONTH_NAMES_DISPLAY[mes] ?? String(mes);
  const relatorio = await fetchRelatorio(mes, ano);

  // STORY-431 AC13: missing or empty payload → noindex metadata so an
  // accidentally-cached blank page never lands in Google's index.
  if (!relatorio || !relatorio.total_editais) {
    return {
      title: `Raio-X das Licitações — ${mesDisplay} ${ano}`,
      description: `Análise mensal das licitações públicas brasileiras em ${mesDisplay.toLowerCase()} de ${ano}.`,
      robots: { index: false, follow: false },
    };
  }

  const totalDisplay = new Intl.NumberFormat('pt-BR').format(relatorio.total_editais);
  const title = `${totalDisplay} editais em ${mesDisplay} de ${ano} — Raio-X das Licitações`;
  const description = `O Brasil publicou ${totalDisplay} editais no PNCP em ${mesDisplay.toLowerCase()} de ${ano}. Análise completa por UF, modalidade e setor com dados reais. Licença Creative Commons BY 4.0.`;

  return {
    title,
    description,
    alternates: { canonical: `https://smartlic.tech/observatorio/${slug}` },
    openGraph: {
      title,
      description,
      url: `https://smartlic.tech/observatorio/${slug}`,
      type: 'article',
      locale: 'pt_BR',
      images: [
        {
          url: `/api/og?title=${encodeURIComponent(`Raio-X ${mesDisplay} ${ano}`)}&subtitle=${encodeURIComponent(`${totalDisplay} editais publicados no PNCP`)}`,
          width: 1200,
          height: 630,
          alt: `Raio-X das Licitações — ${mesDisplay} ${ano} | SmartLic`,
        },
      ],
    },
    robots: { index: true },
  };
}

export default async function RelatorioPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  // STORY-431 AC13: malformed slug → 404 (page itself, plus noindex metadata).
  const parsed = parseSlug(slug);
  if (!parsed) notFound();

  const { mes, ano } = parsed;
  const relatorio = await fetchRelatorio(mes, ano);
  // STORY-431 AC13: backend null/throw → 404 instead of rendering a blank page.
  if (!relatorio) notFound();

  const mesDisplay = MONTH_NAMES_DISPLAY[mes] ?? String(mes);
  const totalEditais = Number(relatorio.total_editais ?? 0);
  const periodoNonEmpty = typeof relatorio.periodo === 'string' && relatorio.periodo.trim().length > 0;

  // STORY-431 AC14: empty period → Sentry warning so we know how often this
  // surface degrades to the EmptyStatePeriod CTA.
  if (totalEditais === 0) {
    Sentry.captureMessage('observatorio_empty_period', {
      level: 'warning',
      tags: { mes: String(mes), ano: String(ano), slug },
    });
  }

  // STORY-431 AC12: only emit the Dataset JSON-LD when the period is real
  // (non-empty + has a periodo string). Avoids polluting Google with an
  // "empty Dataset" structured-data entry.
  const shouldEmitJsonLd = periodoNonEmpty && totalEditais > 0;
  const datasetSchema = shouldEmitJsonLd
    ? {
        '@context': 'https://schema.org',
        '@type': 'Dataset',
        name: `Raio-X das Licitações — ${mesDisplay} ${ano}`,
        description: relatorio.periodo,
        url: `https://smartlic.tech/observatorio/${slug}`,
        license: 'https://creativecommons.org/licenses/by/4.0/',
        creator: {
          '@type': 'Organization',
          name: 'SmartLic',
          url: 'https://smartlic.tech',
        },
        temporalCoverage: `${ano}-${String(mes).padStart(2, '0')}`,
        spatialCoverage: 'Brasil',
        distribution: [
          {
            '@type': 'DataDownload',
            encodingFormat: 'text/csv',
            contentUrl: `https://smartlic.tech/v1/observatorio/relatorio/${mes}/${ano}/csv`,
          },
          {
            '@type': 'DataDownload',
            encodingFormat: 'application/json',
            contentUrl: `https://smartlic.tech/v1/observatorio/relatorio/${mes}/${ano}`,
          },
        ],
      }
    : null;

  return (
    <>
      {datasetSchema && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(datasetSchema) }}
        />
      )}
      <ObservatorioRelatorioClient
        relatorio={relatorio}
        slug={slug}
        mesDisplay={mesDisplay}
        ano={ano}
        mes={mes}
      />
    </>
  );
}
