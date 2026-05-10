import { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { buildCanonical, getFreshnessLabel } from '@/lib/seo';
import LandingNavbar from '@/app/components/landing/LandingNavbar';
import Footer from '@/app/components/Footer';
import FornecedorPseoCTA from './FornecedorPseoCTA';
import { isNoindexed } from '@/lib/seo/noindex';

// Sprint 3 Parte 13: paginas de perfil de fornecedor por CNPJ
// ISR 24h — dados do PNCP atualizados diariamente
export const revalidate = 86400;

// Limite de CNPJs pre-renderizados no build (resto e on-demand ISR)
const _MAX_STATIC_CNPJS = 1000;

type Props = { params: Promise<{ cnpj: string }> };

interface RecentContract {
  objeto: string;
  orgao: string;
  orgao_cnpj?: string | null; // PSEO-TMPL-001 (#882): interlinking contrato → órgão
  valor: number | null;
  data_assinatura: string;
  uf: string;
}

interface TopComprador {
  nome: string;
  cnpj: string;
  total_contratos: number;
  valor_total: number;
}

interface FaqItem {
  question: string;
  answer: string;
}

interface FornecedorProfile {
  cnpj: string;
  razao_social: string;
  cnae_descricao: string;
  municipio: string;
  uf_sede: string;
  simples_nacional: boolean;
  mei: boolean;
  total_contratos: number;
  valor_total: number;
  ufs_atuantes: string[];
  anos_atividade: number[];
  top_compradores: TopComprador[];
  contratos_recentes: RecentContract[];
  faq_items: FaqItem[];
  last_updated: string;
  aviso_legal: string;
}

async function fetchProfile(cnpj: string): Promise<FornecedorProfile | null> {
  const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';
  try {
    const res = await fetch(`${backendUrl}/v1/fornecedores/${cnpj}/profile`, {
      next: { revalidate: 86400 },
      signal: AbortSignal.timeout(10000),
    });
    if (res.status === 404) return null;
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function generateStaticParams() {
  const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';
  try {
    const res = await fetch(`${backendUrl}/v1/sitemap/fornecedores-cnpj`, {
      cache: 'no-store',
      signal: AbortSignal.timeout(15000),
    });
    if (!res.ok) return [];
    const data = await res.json();
    const cnpjs: string[] = (data.cnpjs || []).slice(0, _MAX_STATIC_CNPJS);
    return cnpjs.map((cnpj) => ({ cnpj }));
  } catch {
    return [];
  }
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { cnpj } = await params;
  const profile = await fetchProfile(cnpj);

  if (!profile) {
    return {
      title: `Fornecedor ${cnpj} — SmartLic`,
      robots: { index: false, follow: false },
    };
  }

  const valorFmt = profile.valor_total >= 1_000_000
    ? `R$ ${(profile.valor_total / 1_000_000).toFixed(1)} mi`
    : `R$ ${(profile.valor_total / 1_000).toFixed(0)} mil`;

  return {
    title: `Contratos públicos de ${profile.razao_social} — CNPJ ${cnpj} | SmartLic`,
    description: `${profile.razao_social} (CNPJ ${cnpj}) acumula ${profile.total_contratos} contratos públicos em fontes oficiais, totalizando ${valorFmt}, atuando em ${profile.ufs_atuantes.length} estado(s). Dados atualizados diariamente.`,
    alternates: { canonical: buildCanonical(`/fornecedores/${cnpj}`) },
    openGraph: {
      title: `${profile.razao_social} — Contratos com o Governo`,
      description: `${profile.total_contratos} contratos | ${valorFmt} | fontes oficiais`,
      type: 'website',
      locale: 'pt_BR',
    },
    // SEO-P0-003 (#989): gate on uniqueness audit (see lib/seo/noindex.ts).
    robots: {
      index: !isNoindexed('fornecedores-cnpj', `/fornecedores/${cnpj}`),
      follow: true,
    },
  };
}

export default async function FornecedorCnpjPage({ params }: Props) {
  const { cnpj } = await params;

  // Validacao basica de formato antes de chamar o backend
  if (!/^\d{14}$/.test(cnpj)) notFound();

  const profile = await fetchProfile(cnpj);
  if (!profile) notFound();

  const breadcrumbs = [
    { name: 'SmartLic', url: '/' },
    { name: 'Fornecedores do Governo', url: '/fornecedores' },
    { name: profile.razao_social, url: `/fornecedores/${cnpj}` },
  ];

  const localizacao = [profile.municipio, profile.uf_sede].filter(Boolean).join(' — ') || 'Nao informado';

  // SEO-Sprint2 P6.6: filter FAQ answers shorter than 300 chars
  const eligibleFaqs = (profile.faq_items ?? []).filter(
    (f) => f.answer.replace(/<[^>]*>/g, '').length >= 300
  );

  // PSEO-MOBILE-001 #886: valorFmt for Dataset JSON-LD description
  const valorFmtLd = profile.valor_total >= 1_000_000
    ? `R$ ${(profile.valor_total / 1_000_000).toFixed(1)} mi`
    : `R$ ${(profile.valor_total / 1_000).toFixed(0)} mil`;

  const jsonLd = [
    {
      '@context': 'https://schema.org',
      '@type': 'Organization',
      name: profile.razao_social,
      legalName: profile.razao_social,
      identifier: { '@type': 'PropertyValue', name: 'CNPJ', value: cnpj },
      ...(profile.municipio && profile.uf_sede
        ? {
            address: {
              '@type': 'PostalAddress',
              addressLocality: profile.municipio,
              addressRegion: profile.uf_sede,
              addressCountry: 'BR',
            },
          }
        : {}),
      url: `https://smartlic.tech/fornecedores/${cnpj}`,
      // SEO-Sprint2 P6.3: enrich with offer catalog and area served
      ...(profile.cnae_descricao
        ? {
            hasOfferCatalog: {
              '@type': 'OfferCatalog',
              name: `Serviços de ${profile.razao_social}`,
              description: profile.cnae_descricao,
            },
          }
        : {}),
      ...((profile.ufs_atuantes ?? []).length > 0
        ? {
            areaServed: profile.ufs_atuantes.map((uf: string) => ({
              '@type': 'AdministrativeArea',
              name: uf,
            })),
          }
        : {}),
    },
    // PSEO-MOBILE-001 #886: Dataset schema for Google Dataset Search rich results
    {
      '@context': 'https://schema.org',
      '@type': 'Dataset',
      name: `Contratos públicos — ${profile.razao_social}`,
      description: `Histórico de contratos públicos de ${profile.razao_social} (CNPJ ${cnpj}) no Portal Nacional de Contratações Públicas. ${profile.total_contratos} contratos, totalizando ${valorFmtLd}, em ${profile.ufs_atuantes.length} estado(s).`,
      publisher: {
        '@type': 'Organization',
        name: 'SmartLic',
        url: 'https://smartlic.tech',
      },
      creator: { '@type': 'Organization', name: 'SmartLic', url: 'https://smartlic.tech' },
      license: 'https://dados.gov.br/dados/conteudo/sobre-dados-abertos',
      distribution: {
        '@type': 'DataDownload',
        contentUrl: `https://smartlic.tech/fornecedores/${cnpj}`,
        encodingFormat: 'text/html',
      },
    },
    {
      '@context': 'https://schema.org',
      '@type': 'BreadcrumbList',
      itemListElement: breadcrumbs.map((b, i) => ({
        '@type': 'ListItem',
        position: i + 1,
        name: b.name,
        item: `https://smartlic.tech${b.url}`,
      })),
    },
    ...(eligibleFaqs.length > 0
      ? [
          {
            '@context': 'https://schema.org',
            '@type': 'FAQPage',
            mainEntity: eligibleFaqs.map((f) => ({
              '@type': 'Question',
              name: f.question,
              acceptedAnswer: { '@type': 'Answer', text: f.answer },
            })),
          },
        ]
      : []),
  ];

  return (
    <>
      <LandingNavbar />
      <main className="min-h-screen bg-gray-50 pt-20 pb-16">
        {jsonLd.map((ld, i) => (
          <script
            key={i}
            type="application/ld+json"
            dangerouslySetInnerHTML={{ __html: JSON.stringify(ld) }}
          />
        ))}

        {/* Breadcrumb */}
        <nav className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 text-sm text-gray-500">
          {breadcrumbs.map((b, i) => (
            <span key={b.url + i}>
              {i > 0 && <span className="mx-1">/</span>}
              {i < breadcrumbs.length - 1 ? (
                <Link href={b.url} className="hover:text-blue-600">{b.name}</Link>
              ) : (
                <span className="text-gray-900 font-medium">{b.name}</span>
              )}
            </span>
          ))}
        </nav>

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-1">
            {profile.razao_social}
          </h1>
          <p className="text-sm text-gray-500 mb-1">
            CNPJ {cnpj.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, '$1.$2.$3/$4-$5')}
            {profile.cnae_descricao && <> &middot; {profile.cnae_descricao}</>}
          </p>
          <p className="text-sm text-gray-400 mb-4">
            {profile.last_updated ? getFreshnessLabel(profile.last_updated) : 'Dados das fontes oficiais'}
            {' · Fonte: Portal Nacional de Contratacoes Publicas'}
          </p>

          {/* PSEO-MOBILE-001 #886: Primary CTA above the fold — visible on mobile 375px without scroll */}
          <div className="mb-6 rounded-lg bg-blue-600 px-4 py-4 text-center sm:text-left sm:flex sm:items-center sm:justify-between sm:gap-4">
            <p className="text-sm text-blue-100 mb-3 sm:mb-0">
              Monitore editais do setor de <span className="font-semibold text-white">{profile.razao_social}</span> e receba alertas automáticos.
            </p>
            <Link
              href={`/signup?ref=fornecedor&cnpj=${cnpj}`}
              data-testid="pseo-cta-primary"
              className="inline-block whitespace-nowrap rounded-lg bg-white px-5 py-2.5 text-sm font-semibold text-blue-700 hover:bg-blue-50 transition-colors min-h-[44px] leading-[44px] sm:leading-normal sm:py-2.5"
            >
              Testar 14 dias grátis →
            </Link>
          </div>

          {/* KPI Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
            <div className="bg-white rounded-lg shadow-sm border p-4">
              <p className="text-xs text-gray-500 mb-1">Total de Contratos</p>
              <p className="text-2xl font-bold text-gray-900">
                {profile.total_contratos.toLocaleString('pt-BR')}
              </p>
            </div>
            <div className="bg-white rounded-lg shadow-sm border p-4">
              <p className="text-xs text-gray-500 mb-1">Valor Total</p>
              <p className="text-2xl font-bold text-green-700">
                {formatBRL(profile.valor_total)}
              </p>
            </div>
            <div className="bg-white rounded-lg shadow-sm border p-4">
              <p className="text-xs text-gray-500 mb-1">Estados Atuantes</p>
              <p className="text-2xl font-bold text-gray-900">
                {profile.ufs_atuantes.length}
              </p>
              <p className="text-xs text-gray-400 mt-1">
                {profile.ufs_atuantes.slice(0, 5).join(', ')}
                {profile.ufs_atuantes.length > 5 && '...'}
              </p>
            </div>
            <div className="bg-white rounded-lg shadow-sm border p-4">
              <p className="text-xs text-gray-500 mb-1">Sede</p>
              <p className="text-sm font-semibold text-gray-900">{localizacao}</p>
              <div className="flex gap-1 mt-1 flex-wrap">
                {profile.simples_nacional && (
                  <span className="text-xs bg-green-100 text-green-700 rounded px-1">Simples</span>
                )}
                {profile.mei && (
                  <span className="text-xs bg-blue-100 text-blue-700 rounded px-1">MEI</span>
                )}
              </div>
            </div>
          </div>

          {/* Contratos Recentes */}
          <section className="mb-8">
            <h2 className="text-xl font-semibold text-gray-900 mb-3">
              Contratos Recentes
            </h2>
            <div className="bg-white rounded-lg shadow-sm border overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-gray-600">
                  <tr>
                    <th className="text-left px-4 py-3">Objeto</th>
                    <th className="text-left px-4 py-3">Orgao Comprador</th>
                    <th className="text-right px-4 py-3">Valor</th>
                    <th className="text-right px-4 py-3">Data</th>
                    <th className="text-center px-4 py-3">UF</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {profile.contratos_recentes.map((c, i) => (
                    <tr key={i} className="hover:bg-gray-50">
                      <td className="px-4 py-2 max-w-xs">
                        <span className="line-clamp-2">{c.objeto}</span>
                      </td>
                      <td className="px-4 py-2">
                        {/* PSEO-TMPL-001 (#882): link bidirecional contrato → órgão */}
                        {c.orgao_cnpj ? (
                          <Link
                            href={`/orgaos/${c.orgao_cnpj}`}
                            className="text-blue-600 hover:underline text-sm"
                          >
                            {c.orgao}
                          </Link>
                        ) : (
                          <span className="text-gray-600 text-sm">{c.orgao}</span>
                        )}
                      </td>
                      <td className="text-right px-4 py-2 text-green-700 whitespace-nowrap">
                        {c.valor != null ? formatBRL(c.valor) : '—'}
                      </td>
                      <td className="text-right px-4 py-2 text-gray-500 whitespace-nowrap">
                        {c.data_assinatura || '—'}
                      </td>
                      <td className="text-center px-4 py-2 text-gray-500">{c.uf || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* Top Compradores */}
          {profile.top_compradores.length > 0 && (
            <section className="mb-8">
              <h2 className="text-xl font-semibold text-gray-900 mb-3">
                Principais Orgaos Compradores
              </h2>
              <div className="bg-white rounded-lg shadow-sm border overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 text-gray-600">
                    <tr>
                      <th className="text-left px-4 py-3">Orgao</th>
                      <th className="text-right px-4 py-3">Contratos</th>
                      <th className="text-right px-4 py-3">Valor Total</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {profile.top_compradores.map((o) => (
                      <tr key={o.cnpj} className="hover:bg-gray-50">
                        <td className="px-4 py-2">
                          {/* PSEO-TMPL-001 (#882): interlinking bidirecional fornecedor ↔ órgão */}
                          <Link href={`/orgaos/${o.cnpj}`} className="text-blue-600 hover:underline font-medium">
                            {o.nome}
                          </Link>
                          <Link
                            href={`/contratos/orgao/${o.cnpj}`}
                            className="block text-xs text-gray-400 hover:text-blue-500 hover:underline mt-0.5"
                          >
                            Ver contratos deste órgão →
                          </Link>
                        </td>
                        <td className="text-right px-4 py-2">{o.total_contratos}</td>
                        <td className="text-right px-4 py-2 text-green-700">{formatBRL(o.valor_total)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {/* FAQ */}
          <section className="mb-8">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Perguntas Frequentes</h2>
            <div className="space-y-4">
              {profile.faq_items.map((f, i) => (
                <details key={i} className="bg-white rounded-lg shadow-sm border p-4">
                  <summary className="font-medium text-gray-900 cursor-pointer">{f.question}</summary>
                  <p className="mt-2 text-sm text-gray-600">{f.answer}</p>
                </details>
              ))}
            </div>
          </section>

          {/* Páginas Relacionadas — PSEO-TMPL-001 (#882): interlinking bidirecional completo */}
          <section className="border-t border-gray-200 pt-8 mb-8">
            <h2 className="text-lg font-semibold text-gray-900 mb-3">Páginas Relacionadas</h2>
            <div className="flex flex-wrap gap-3 text-sm">
              <Link href={`/cnpj/${cnpj}`} className="text-blue-600 hover:underline">
                Consulta CNPJ — {cnpj.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, '$1.$2.$3/$4-$5')}
              </Link>
              <Link href="/fornecedores" className="text-blue-600 hover:underline">
                Todos os Fornecedores
              </Link>
              {profile.top_compradores.slice(0, 2).map((o) => (
                <Link
                  key={o.cnpj}
                  href={`/contratos/orgao/${o.cnpj}`}
                  className="text-blue-600 hover:underline"
                >
                  Contratos de {o.nome.split(' ').slice(0, 3).join(' ')}
                </Link>
              ))}
              {profile.ufs_atuantes.slice(0, 2).map((uf) => (
                <Link
                  key={uf}
                  href={`/contratos/${uf.toLowerCase()}`}
                  className="text-blue-600 hover:underline"
                >
                  Contratos em {uf}
                </Link>
              ))}
            </div>
          </section>

          {/* Lead Capture — client component fires pseo_supplier_viewed + pseo_checkout_click */}
          <FornecedorPseoCTA cnpj={cnpj} razaoSocial={profile.razao_social} />

          <p className="text-xs text-gray-400 mt-8">{profile.aviso_legal}</p>
        </div>
      </main>
      <Footer />
    </>
  );
}

function formatBRL(value: number): string {
  if (value >= 1_000_000_000) {
    return `R$ ${(value / 1_000_000_000).toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} bi`;
  }
  if (value >= 1_000_000) {
    return `R$ ${(value / 1_000_000).toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} mi`;
  }
  if (value >= 1_000) {
    return `R$ ${(value / 1_000).toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 0 })} mil`;
  }
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}
