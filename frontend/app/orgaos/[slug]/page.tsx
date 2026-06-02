import { Metadata } from 'next';
import Link from 'next/link';
import ContentPageLayout from '../../components/ContentPageLayout';
import OrgaoPerfilClient from './OrgaoPerfilClient';
import EmptyStateSEO from '@/components/seo/EmptyStateSEO';
import { LeadCapture } from '@/components/LeadCapture';
import AlertEntityCta from '@/components/seo/AlertEntityCta';
import { FoundersRibbon } from '@/components/banners/FoundersRibbon';
import { fetchWithBudget } from '@/lib/safe-fetch';
import { getBackendUrl } from '@/lib/backend-url';
import { AdvisoryDisclaimer } from '@/components/legal/AdvisoryDisclaimer';
import WhatsAppCTA from '@/app/components/whatsapp/WhatsAppCTA';
import PreviewCTA from '@/app/components/programmatic/PreviewCTA';
import { resolveJourney } from '@/lib/seo/relatedResolver';

const BACKEND_URL = getBackendUrl();

interface LicitacaoRecente {
  objeto_compra: string;
  modalidade_nome: string;
  valor_total_estimado: number | null;
  data_publicacao: string;
  uf: string;
}

interface ModalidadeCount {
  nome: string;
  count: number;
}

interface OrgaoStats {
  nome: string;
  cnpj: string;
  esfera: string;
  uf: string;
  municipio: string;
  total_licitacoes: number;
  licitacoes_30d: number;
  licitacoes_90d: number;
  licitacoes_365d: number;
  valor_medio_estimado: number;
  valor_total_estimado: number;
  top_modalidades: ModalidadeCount[];
  top_setores: string[];
  ultimas_licitacoes: LicitacaoRecente[];
  total_contratos_24m?: number;
  valor_total_contratos_24m?: number;
  aviso_legal: string;
}

export const revalidate = 3600; // 24h ISR

export function generateStaticParams() {
  return []; // SSR on-demand
}

async function fetchOrgaoStats(slug: string): Promise<OrgaoStats | null> {
  return fetchWithBudget<OrgaoStats>(`${BACKEND_URL}/v1/orgao/${slug}/stats`, {
    timeout: 15000,
    retries: 1,
    revalidate: 3600,
    throwOn5xx: true, // ISR stale-preservation: 5xx re-throws to keep last-good cache
    label: 'orgao-stats',
  });
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const stats = await fetchOrgaoStats(slug);

  if (!stats) {
    return {
      title: 'Órgão não encontrado',
      description: 'O órgão informado não foi encontrado na base de dados.',
      robots: { index: false, follow: false },
    };
  }

  // STORY-439 AC1: noindex órgãos com volume insuficiente de licitações (thin content gate)
  const minBids = parseInt(process.env.MIN_ACTIVE_BIDS_FOR_INDEX ?? '5', 10);
  if (stats.total_licitacoes < minBids) {
    return {
      title: `${stats.nome} — Licitações Públicas`,
      robots: { index: false, follow: true },
    };
  }

  const valorMedioFormatado = new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    minimumFractionDigits: 0,
  }).format(stats.valor_medio_estimado);

  const contratosDesc = stats.total_contratos_24m
    ? ` ${stats.total_contratos_24m} contratos firmados (24 meses).`
    : '';

  return {
    title: `Como ${stats.nome} compra e quais oportunidades publica? | SmartLic`,
    description: `${stats.nome} publicou ${stats.total_licitacoes} licitações. ${stats.licitacoes_30d} nos últimos 30 dias. Valor médio: ${valorMedioFormatado}.${contratosDesc}`,
    alternates: {
      canonical: `https://smartlic.tech/orgaos/${slug}`,
    },
    openGraph: {
      title: `${stats.nome} — Licitações e Editais`,
      description: `${stats.total_licitacoes} licitações publicadas | ${stats.licitacoes_30d} nos últimos 30 dias`,
      url: `https://smartlic.tech/orgaos/${slug}`,
      type: 'website',
      images: [
        {
          url: `/api/og?title=${encodeURIComponent(stats.nome + ' — Licitações Públicas')}`,
          width: 1200,
          height: 630,
        },
      ],
    },
    twitter: {
      card: 'summary_large_image',
      title: `${stats.nome} — Licitações Públicas`,
      description: `${stats.total_licitacoes} licitações | ${stats.licitacoes_30d} nos últimos 30 dias`,
    },
  };
}

export default async function OrgaoPerfilPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const stats = await fetchOrgaoStats(slug);

  // ADR-SEO-001: data absence → EmptyStateSEO (not notFound) to prevent ISR-cached 404s
  if (!stats) {
    return (
      <EmptyStateSEO
        title="Órgão público sem licitações registradas ainda"
        description="Este órgão não possui licitações públicas registradas nas fontes oficiais no momento. Os dados são indexados diariamente — volte em breve."
        ctaHref="/orgaos"
        ctaLabel="Ver outros órgãos"
      />
    );
  }

  const orgSchema = {
    '@context': 'https://schema.org',
    '@type': 'GovernmentOrganization',
    name: stats.nome,
    taxID: stats.cnpj,
    address: {
      '@type': 'PostalAddress',
      addressRegion: stats.uf,
      addressLocality: stats.municipio,
      addressCountry: 'BR',
    },
  };

  const datasetSchema = {
    '@context': 'https://schema.org',
    '@type': 'Dataset',
    name: `Licitações Públicas — ${stats.nome}`,
    description: `Histórico de licitações e editais publicados por ${stats.nome} (CNPJ ${stats.cnpj})`,
    creator: { '@type': 'Organization', name: 'SmartLic', url: 'https://smartlic.tech' },
    license: 'https://dados.gov.br/dados/conteudo/sobre-dados-abertos',
    distribution: {
      '@type': 'DataDownload',
      contentUrl: `https://smartlic.tech/orgaos/${slug}`,
      encodingFormat: 'text/html',
    },
  };

  // CONV-002b: preview items for PreviewCTA — 3 últimas licitações + 3 blurred
  const previewItems = stats.ultimas_licitacoes.slice(0, 6).map((l) => ({
    orgao: stats.nome,
    objeto: l.objeto_compra,
    valor_estimado: l.valor_total_estimado,
    data_limite: null as string | null,
    data_publicacao: l.data_publicacao,
    link_interno: `/orgaos/${slug}`,
  }));

  // SEO-P1-007 (#993): Visual breadcrumb derived from same trail as JSON-LD.
  // ContentPageLayout's BreadcrumbNav emits the BreadcrumbList JSON-LD when
  // breadcrumbItems is provided (suppressSchema=false), so we no longer need
  // an inline breadcrumbSchema script — single source of truth.
  const breadcrumbItems = [
    { label: 'Início', href: '/' },
    { label: 'Órgãos Compradores', href: '/orgaos' },
    { label: stats.nome },
  ];

  // CONV-017 (#1332): Build intent-progressive journey for this órgão.
  const journey = resolveJourney({
    type: 'orgao',
    value: stats.cnpj,
    currentUrl: `/orgaos/${slug}`,
    name: stats.nome,
    uf: stats.uf,
    sectorSlug: stats.top_setores?.[0],
    sectorName: stats.top_setores?.[0]
      ? undefined
      : undefined,
  });

  return (
    <>
    {/* CONV-002b: Sticky bottom mobile CTA — contextual */}
    <div
      className="fixed bottom-0 left-0 right-0 z-40 sm:hidden bg-brand-navy text-white px-4 py-3 shadow-lg"
      data-testid="pseo-sticky-cta"
    >
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-medium">
          {stats.licitacoes_30d} editais · {stats.nome}
        </span>
        <Link
          href={`/signup?ref=orgao-${slug}-sticky`}
          className="px-4 py-2 bg-brand-blue rounded-lg text-sm font-semibold whitespace-nowrap"
        >
          Receber alertas →
        </Link>
      </div>
    </div>
    <ContentPageLayout
      breadcrumbLabel={stats.nome}
      breadcrumbItems={breadcrumbItems}
      relatedPages={[]}
      journeyLinks={journey}
      journeySourceTemplate="orgao"
    >
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(orgSchema) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(datasetSchema) }}
      />

      <OrgaoPerfilClient stats={stats} />

      {/* CONV-002b: PreviewCTA — 3 últimas licitações + 3 blurred (degustação) */}
      {stats.ultimas_licitacoes.length >= 3 && (
        <div className="mt-8">
          <PreviewCTA
            setor="orgao-licitacoes"
            setorLabel={stats.nome}
            ufLabel={stats.uf}
            totalOpen={stats.licitacoes_30d}
            items={previewItems}
          />
        </div>
      )}

      {/* CONV-002b: Contextual CTA — trial + "Só quero ver os dados" */}
      <section className="max-w-5xl mx-auto px-4 py-8">
        <div className="rounded-2xl border border-brand-blue/30 bg-brand-blue/5 dark:bg-brand-blue/10 p-6 sm:p-8">
          <p className="text-lg text-gray-900 dark:text-white mb-4">
            Quer receber os próximos editais de <strong>{stats.nome}</strong>?
          </p>
          <div className="flex flex-col sm:flex-row gap-3">
            <Link
              href={`/signup?ref=orgao-${slug}`}
              className="inline-block px-6 py-3 bg-brand-blue text-white font-semibold rounded-lg hover:bg-blue-700 transition-colors text-center"
            >
              Receber alertas grátis 14 dias →
            </Link>
            <Link
              href="/observatorio"
              className="inline-block px-6 py-3 bg-white dark:bg-gray-900 text-brand-navy dark:text-white font-medium rounded-lg border border-gray-300 dark:border-gray-700 hover:border-brand-blue transition-colors text-center"
            >
              Só quero ver os dados
            </Link>
          </div>
        </div>
      </section>

      <div className="mt-10">
        <LeadCapture
          source="orgao-perfil"
          uf={stats.uf}
          heading="Receba alertas de editais deste órgão"
          description={`Novos editais de ${stats.nome}, toda semana no seu email.`}
        />
      </div>

      {/* CONV-014: Alert CTA — monitorar editais deste órgão */}
      <div className="mt-6">
        <AlertEntityCta
          entityType="orgao"
          entityId={slug}
          entityLabel={stats.nome}
        />
      </div>

      {/* REPO-015: Consultoria-b2g CTA with orgao slug pre-fill */}
      <section className="mt-12 rounded-xl border border-blue-200 bg-blue-50 dark:bg-blue-950/30 dark:border-blue-800 p-6">
        <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-1">
          Quer monitorar os editais deste órgão?
        </h3>
        <p className="text-sm text-slate-600 dark:text-slate-400 mb-4">
          Diagnóstico gratuito. Sem compromisso.
        </p>
        <Link
          href={`/consultoria-b2g?modalidade=report&orgao=${slug}`}
          className="inline-block rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 transition-colors"
          data-cta-source="pseo-orgao"
        >
          Solicitar análise de edital
        </Link>
      </section>

      {/* CONV-013: WhatsApp CTA — falar com founder */}
      <div className="mt-8">
        <WhatsAppCTA
          source="orgao_page"
          entity={stats.nome}
          entityId={slug}
          uf={stats.uf}
        />
      </div>

      {/* #788: Founders plan CTA for high-intent organic visitors */}
      <FoundersRibbon
        variant="contextual"
        copy="Transforme dados oficiais em decisão. Vitalício por R$997."
        src="pseo_orgao"
      />

      {/* REPO-020 (#772): Advisory disclaimer for algorithmic data aggregations */}
      <AdvisoryDisclaimer variant="full" />
    </ContentPageLayout>
    </>
  );
}
