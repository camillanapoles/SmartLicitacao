import { Metadata } from 'next';
import { notFound } from 'next/navigation';
import ContentPageLayout from '../../components/ContentPageLayout';
import CnpjPerfilClient from './CnpjPerfilClient';
import InlineTrialCTA from '../../components/InlineTrialCTA';
import IntelReportCTA from './IntelReportCTA';
import { LeadCapture } from '@/components/LeadCapture';
import { FoundersRibbon } from '@/components/banners/FoundersRibbon';
import { fetchWithBudget } from '@/lib/safe-fetch';
import { getBackendUrl } from '@/lib/backend-url';

const BACKEND_URL = getBackendUrl();

interface EditaisAmostra {
  orgao: string;
  descricao: string;
  valor_estimado: number | null;
  data_encerramento: string | null;
  uf: string | null;
  modalidade: string | null;
}

interface PerfilB2G {
  empresa: {
    razao_social: string;
    cnpj: string;
    cnae_principal: string;
    porte: string;
    uf: string;
    situacao: string;
  };
  contratos: Array<{
    orgao: string;
    orgao_cnpj?: string | null;
    valor: number | null;
    data_inicio: string | null;
    descricao: string;
    esfera?: string | null;
    uf?: string | null;
  }>;
  score: string;
  setor_detectado: string;
  setor_nome: string;
  editais_abertos_setor: number;
  editais_amostra: EditaisAmostra[];
  total_contratos_24m: number;
  valor_total_24m: number;
  ufs_atuacao: string[];
  aviso_legal: string;
}

export const revalidate = 86400; // 24h ISR

export function generateStaticParams() {
  return []; // SSR on-demand
}

async function fetchPerfil(cnpj: string): Promise<PerfilB2G | null> {
  return fetchWithBudget<PerfilB2G>(`${BACKEND_URL}/v1/empresa/${cnpj}/perfil-b2g`, {
    timeout: 10000,
    retries: 1,
    revalidate: 86400,
    label: 'cnpj-perfil',
  });
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ cnpj: string }>;
}): Promise<Metadata> {
  const { cnpj } = await params;
  const perfil = await fetchPerfil(cnpj);

  if (!perfil) {
    return {
      title: 'CNPJ não encontrado',
      description: 'O CNPJ informado não foi encontrado na base de dados.',
    };
  }

  const { empresa, total_contratos_24m, valor_total_24m, score } = perfil;
  const valorFormatado = new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    minimumFractionDigits: 0,
  }).format(valor_total_24m);

  return {
    title: `${empresa.razao_social} — Histórico de Contratos Públicos`,
    description: `Contratos públicos, licitações e editais do CNPJ ${cnpj} (${empresa.razao_social}). ${total_contratos_24m} contratos | ${valorFormatado} captados. Monitore via SmartLic.`,
    alternates: {
      canonical: `https://smartlic.tech/cnpj/${cnpj}`,
    },
    openGraph: {
      title: `${empresa.razao_social} — Contratos Públicos`,
      description: `${total_contratos_24m} contratos | ${valorFormatado} | Score: ${score}`,
      url: `https://smartlic.tech/cnpj/${cnpj}`,
      type: 'website',
      images: [
        {
          url: `/api/og?title=${encodeURIComponent(empresa.razao_social + ' — B2G Score: ' + score)}`,
          width: 1200,
          height: 630,
        },
      ],
    },
    twitter: {
      card: 'summary_large_image',
      title: `${empresa.razao_social} — Score B2G: ${score}`,
      description: `${total_contratos_24m} contratos | ${valorFormatado}`,
    },
    robots: { index: total_contratos_24m > 0, follow: true },
  };
}

export default async function CnpjPerfilPage({
  params,
}: {
  params: Promise<{ cnpj: string }>;
}) {
  const { cnpj } = await params;
  const perfil = await fetchPerfil(cnpj);

  if (!perfil) {
    notFound();
  }

  const { empresa } = perfil;

  const orgSchema = {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: empresa.razao_social,
    taxID: empresa.cnpj,
    address: {
      '@type': 'PostalAddress',
      addressRegion: empresa.uf,
      addressCountry: 'BR',
    },
  };

  const datasetSchema = {
    '@context': 'https://schema.org',
    '@type': 'Dataset',
    name: `Contratos Públicos — ${empresa.razao_social}`,
    description: `Histórico de contratos governamentais de ${empresa.razao_social} (CNPJ ${empresa.cnpj})`,
    creator: { '@type': 'Organization', name: 'SmartLic', url: 'https://smartlic.tech' },
    license: 'https://dados.gov.br/dados/conteudo/sobre-dados-abertos',
    distribution: {
      '@type': 'DataDownload',
      contentUrl: `https://smartlic.tech/cnpj/${cnpj}`,
      encodingFormat: 'text/html',
    },
  };

  const breadcrumbSchema = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Início', item: 'https://smartlic.tech' },
      { '@type': 'ListItem', position: 2, name: 'Consulta CNPJ', item: 'https://smartlic.tech/cnpj' },
      { '@type': 'ListItem', position: 3, name: empresa.razao_social, item: `https://smartlic.tech/cnpj/${cnpj}` },
    ],
  };

  return (
    <ContentPageLayout
      breadcrumbLabel={empresa.razao_social}
      relatedPages={[
        { href: '/cnpj', title: 'Nova consulta CNPJ' },
        { href: '/orgaos', title: 'Órgãos Compradores' },
        { href: '/calculadora', title: 'Calculadora de Oportunidades' },
        { href: '/licitacoes', title: 'Licitações por Setor' },
      ]}
    >
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(orgSchema) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(datasetSchema) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbSchema) }}
      />

      <CnpjPerfilClient perfil={perfil} />

      {/* #632: Intel Report one-time purchase CTA */}
      <section className="mt-8 rounded-xl border border-blue-100 bg-gradient-to-r from-blue-50 to-indigo-50 p-6">
        <h2 className="mb-2 text-xl font-bold text-gray-900">
          Inteligência Competitiva
        </h2>
        <p className="mb-1 font-semibold text-gray-600">
          Raio-X Completo do Concorrente
        </p>
        <p className="mb-4 text-sm text-gray-500">
          8–12 páginas: histórico de contratos, órgãos compradores, evolução temporal, análise IA
        </p>
        <div className="mb-4 text-2xl font-bold text-gray-900">
          R$197{" "}
          <span className="text-sm font-normal text-gray-500">— download imediato</span>
        </div>
        <IntelReportCTA cnpj={cnpj} />
        <p className="mt-3 text-xs text-gray-400">
          ✓ PDF imediato &nbsp; ✓ 30 dias de acesso &nbsp; ✓ Dados PNCP atualizados
        </p>
      </section>

      {/* #652: Inline trial CTA after contratos section */}
      <InlineTrialCTA
        page="cnpj"
        source="cnpj-page"
        extraParam={{ name: 'orgao', value: cnpj }}
      />

      {/* A2: Contextual lead capture with detected sector + UF */}
      <div className="mt-10">
        <LeadCapture
          source="cnpj-perfil"
          setor={perfil.setor_detectado}
          uf={perfil.empresa.uf}
          heading="Receba alertas semanais do seu setor por email"
          description={`Novos editais de ${perfil.setor_nome} em ${perfil.empresa.uf}, toda semana no seu email.`}
        />
      </div>

      {/* #788: Founders plan CTA for high-intent organic visitors */}
      <FoundersRibbon
        variant="contextual"
        copy="Acesso vitalício durante a fase inicial do SmartLic — vagas limitadas."
        src="pseo_cnpj"
      />
    </ContentPageLayout>
  );
}
