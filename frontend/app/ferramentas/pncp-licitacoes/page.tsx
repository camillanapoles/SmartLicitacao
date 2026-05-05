/**
 * Issue #653: SEO landing dedicada para queries B2B tool-search
 * "pncp licitações", "pncp contratos", "consultar contratos pncp" — pos 11-17 sem clique.
 *
 * Server Component, ISR 24h. Pura static content (sem fetch backend).
 * Target: empresas que pesquisam ferramenta para automatizar busca PNCP.
 */

import type { Metadata } from "next";
import Link from "next/link";

// ISR — conteúdo é estático, revalidação diária basta para qualquer ajuste de copy
// sem deploy. Sem fetch, sem alignment de cache (memory: feedback_isr_fetch_cache_alignment_next16).
export const revalidate = 86400;

const CANONICAL_URL = "https://smartlic.tech/ferramentas/pncp-licitacoes";
const TITLE = "PNCP Licitações 2026 — Busca Automatizada para Empresas | SmartLic";
const DESCRIPTION =
  "Automatize a busca de licitações no PNCP: filtre por setor, valor e UF, receba alertas e analise viabilidade com IA. Compare a busca manual no portal PNCP com a automação SmartLic. 14 dias grátis.";

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  alternates: {
    canonical: CANONICAL_URL,
  },
  robots: { index: true, follow: true },
  openGraph: {
    title: TITLE,
    description: DESCRIPTION,
    url: CANONICAL_URL,
    type: "website",
    locale: "pt_BR",
    siteName: "SmartLic",
  },
  twitter: {
    card: "summary_large_image",
    title: "PNCP Licitações 2026 — Busca Automatizada para Empresas",
    description:
      "Filtre licitações no PNCP por setor, valor e UF. Alertas + análise de viabilidade com IA. Teste 14 dias grátis.",
  },
};

const articleJsonLd = {
  "@context": "https://schema.org",
  "@type": "Article",
  headline: "PNCP Licitações 2026 — Busca Automatizada para Empresas",
  description: DESCRIPTION,
  inLanguage: "pt-BR",
  url: CANONICAL_URL,
  about: [
    { "@type": "Thing", name: "PNCP — Portal Nacional de Contratações Públicas" },
    { "@type": "Thing", name: "Licitações públicas Brasil" },
    { "@type": "Thing", name: "Lei 14.133/2021" },
  ],
  publisher: {
    "@type": "Organization",
    name: "SmartLic",
    url: "https://smartlic.tech",
    logo: {
      "@type": "ImageObject",
      url: "https://smartlic.tech/logo.png",
    },
  },
  author: {
    "@type": "Organization",
    name: "SmartLic",
    url: "https://smartlic.tech",
  },
  datePublished: "2026-05-05",
  dateModified: "2026-05-05",
  mainEntityOfPage: {
    "@type": "WebPage",
    "@id": CANONICAL_URL,
  },
};

const breadcrumbJsonLd = {
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  itemListElement: [
    { "@type": "ListItem", position: 1, name: "Início", item: "https://smartlic.tech" },
    { "@type": "ListItem", position: 2, name: "Ferramentas", item: "https://smartlic.tech/ferramentas" },
    {
      "@type": "ListItem",
      position: 3,
      name: "PNCP Licitações",
      item: CANONICAL_URL,
    },
  ],
};

export default function PncpLicitacoesPage() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(articleJsonLd) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbJsonLd) }}
      />

      <main id="main-content" className="min-h-screen bg-white dark:bg-gray-950">
        {/* Hero */}
        <section className="bg-gradient-to-br from-brand-blue to-blue-700 text-white py-16 px-4">
          <div className="max-w-4xl mx-auto">
            <nav aria-label="Breadcrumb" className="text-sm text-white/70 mb-4">
              <ol className="flex flex-wrap items-center gap-x-1">
                <li>
                  <Link href="/" className="hover:text-white">Início</Link>
                </li>
                <li aria-hidden="true"> › </li>
                <li aria-current="page" className="text-white/90">PNCP Licitações</li>
              </ol>
            </nav>
            <h1 className="text-3xl md:text-5xl font-bold mb-4">
              PNCP Licitações 2026 — Busca Automatizada
            </h1>
            <p className="text-lg md:text-xl text-blue-100 max-w-2xl">
              Encontre, filtre e analise licitações públicas no PNCP sem perder horas
              navegando pelo portal manualmente. Alertas por setor, score de viabilidade
              com IA e exportação direta para Excel.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                href="/signup?source=ferramentas-pncp-licitacoes"
                className="inline-block px-7 py-3 bg-white text-brand-navy font-semibold rounded-lg
                           hover:bg-gray-100 transition-colors text-base shadow-md"
              >
                Buscar editais agora — 14 dias grátis
              </Link>
              <Link
                href="/licitacoes"
                className="inline-block px-7 py-3 border border-white/40 text-white font-medium
                           rounded-lg hover:bg-white/10 transition-colors text-base"
              >
                Ver licitações por setor
              </Link>
            </div>
            <p className="mt-3 text-sm text-blue-100/80">
              Sem cartão de crédito. Resultado em 3 minutos.
            </p>
          </div>
        </section>

        {/* Lead — explica PNCP + dor */}
        <section className="max-w-3xl mx-auto py-14 px-4">
          <h2 className="text-2xl md:text-3xl font-bold text-gray-900 dark:text-white mb-4">
            O que é o PNCP e por que buscar manualmente é caro
          </h2>
          <div className="space-y-4 text-base text-gray-700 dark:text-gray-300 leading-relaxed">
            <p>
              O <strong>PNCP (Portal Nacional de Contratações Públicas)</strong> é o sistema
              oficial do governo federal que centraliza editais e contratos públicos
              celebrados sob a Lei 14.133/2021. Hoje ele agrega dezenas de milhares de
              licitações abertas e contratos já firmados em todo o Brasil — uma
              oportunidade enorme para empresas B2G, mas pesquisar lá direto é trabalhoso.
            </p>
            <p>
              Para encontrar uma licitação relevante no PNCP, a empresa precisa abrir
              filtros UF a UF, escolher modalidade, ler descrições genéricas, comparar
              valores e refazer a busca todos os dias. É o tipo de tarefa que come 3-5
              horas semanais de um analista comercial e ainda assim deixa oportunidades
              passarem.
            </p>
            <p>
              O SmartLic resolve isso lendo o PNCP automaticamente, classificando cada
              edital por setor com IA (GPT-4.1-nano), filtrando por região e valor, e
              entregando só o que importa — com score de viabilidade e alertas por email.
            </p>
          </div>
        </section>

        {/* Tabela comparativa Manual × SmartLic */}
        <section className="bg-gray-50 dark:bg-gray-900 py-14 px-4">
          <div className="max-w-4xl mx-auto">
            <h2 className="text-2xl md:text-3xl font-bold text-gray-900 dark:text-white mb-2">
              Busca manual no PNCP × SmartLic
            </h2>
            <p className="text-gray-600 dark:text-gray-400 mb-8">
              Comparativo direto do que muda entre consultar contratos PNCP no portal
              oficial e usar a automação SmartLic.
            </p>

            <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950">
              <table className="w-full text-sm text-left">
                <thead className="text-xs uppercase text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-800">
                  <tr>
                    <th scope="col" className="px-4 py-3">Recurso</th>
                    <th scope="col" className="px-4 py-3">Manual (PNCP web)</th>
                    <th scope="col" className="px-4 py-3">SmartLic</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 dark:divide-gray-800">
                  <ComparativeRow
                    feature="Filtro por setor"
                    manual="Apenas modalidade e UF — sem categoria de produto/serviço"
                    smartlic="20 setores pré-mapeados com keywords e exclusões"
                  />
                  <ComparativeRow
                    feature="Filtro por valor estimado"
                    manual="Não disponível na busca padrão"
                    smartlic="Faixa mínima e máxima por edital"
                  />
                  <ComparativeRow
                    feature="Filtro por UF"
                    manual="Sim, mas é preciso refazer a busca por UF"
                    smartlic="Múltiplas UFs simultâneas + agregação"
                  />
                  <ComparativeRow
                    feature="Alertas de novos editais"
                    manual="Inexistente — usuário precisa voltar ao site"
                    smartlic="Email automático conforme critérios salvos"
                  />
                  <ComparativeRow
                    feature="Análise de viabilidade"
                    manual="Não — empresa lê edital por edital"
                    smartlic="Score 4 fatores (modalidade, prazo, valor, geografia)"
                  />
                  <ComparativeRow
                    feature="Classificação automática"
                    manual="Manual, baseada em palavras-chave do título"
                    smartlic="IA classifica relevância (precisão ≥85%)"
                  />
                  <ComparativeRow
                    feature="Exportação"
                    manual="Cópia manual ou print"
                    smartlic="Excel estilizado + resumo executivo IA"
                  />
                  <ComparativeRow
                    feature="Cobertura de fontes"
                    manual="Apenas PNCP"
                    smartlic="PNCP + PCP v2 + ComprasGov v3 (deduplicado)"
                  />
                  <ComparativeRow
                    feature="Tempo médio de triagem semanal"
                    manual="3-5 horas por analista"
                    smartlic="3 minutos para a primeira lista"
                  />
                </tbody>
              </table>
            </div>

            <p className="mt-6 text-sm text-gray-500 dark:text-gray-400">
              Fonte do dataset: PNCP — Portal Nacional de Contratações Públicas, processado
              pelo SmartLic com classificação setorial via IA. Atualização periódica.
            </p>
          </div>
        </section>

        {/* Como usar — passo a passo */}
        <section className="max-w-4xl mx-auto py-14 px-4">
          <h2 className="text-2xl md:text-3xl font-bold text-gray-900 dark:text-white mb-8">
            Como buscar licitações do PNCP no SmartLic
          </h2>
          <ol className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <HowToStep
              step={1}
              title="Crie sua conta em 30 segundos"
              description="Cadastre-se com email — sem cartão de crédito. Trial de 14 dias com acesso completo à busca, classificação por IA e exportação."
            />
            <HowToStep
              step={2}
              title="Selecione setor, UFs e faixa de valor"
              description="Escolha entre 20 setores (limpeza, TI, engenharia, saúde, etc.), as UFs onde sua empresa atua e a faixa de valor estimado dos editais."
            />
            <HowToStep
              step={3}
              title="Receba a lista priorizada por viabilidade"
              description="O SmartLic consulta o PNCP, classifica cada edital com IA e retorna a lista priorizada por score de viabilidade — modalidade, prazo, valor e geografia."
            />
            <HowToStep
              step={4}
              title="Configure alertas e exporte"
              description="Salve filtros como alerta para receber novos editais por email. Exporte resultados para Excel ou PDF com resumo executivo gerado por IA."
            />
          </ol>
        </section>

        {/* CTA final */}
        <section className="bg-brand-blue/5 dark:bg-brand-blue/10 py-14 px-4">
          <div className="max-w-3xl mx-auto text-center">
            <h2 className="text-2xl md:text-3xl font-bold text-gray-900 dark:text-white mb-3">
              Pronto para parar de garimpar o PNCP manualmente?
            </h2>
            <p className="text-base text-gray-600 dark:text-gray-400 mb-6">
              Teste a busca automatizada por 14 dias grátis. Sem cartão de crédito,
              sem renovação automática. Cancele quando quiser.
            </p>
            <Link
              href="/signup?source=ferramentas-pncp-licitacoes"
              className="inline-block px-8 py-4 bg-brand-blue text-white font-bold rounded-xl
                         hover:bg-blue-700 transition-colors text-lg shadow-lg"
            >
              Buscar editais agora — 14 dias grátis
            </Link>
            <p className="mt-3 text-sm text-gray-500 dark:text-gray-400">
              Resultado em 3 minutos. Cobertura nacional. Suporte por email.
            </p>
          </div>
        </section>

        {/* Links internos para distribuir PageRank dentro do site */}
        <section className="max-w-4xl mx-auto py-12 px-4 border-t border-gray-200 dark:border-gray-800">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Continuar explorando
          </h2>
          <ul className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
            <li>
              <Link href="/licitacoes" className="text-brand-blue hover:underline">
                Licitações por setor — todos os 20 setores
              </Link>
            </li>
            <li>
              <Link href="/observatorio" className="text-brand-blue hover:underline">
                Observatório de Licitações — relatórios mensais
              </Link>
            </li>
            <li>
              <Link href="/guia/pncp" className="text-brand-blue hover:underline">
                Guia completo do PNCP
              </Link>
            </li>
            <li>
              <Link href="/guia/lei-14133" className="text-brand-blue hover:underline">
                Lei 14.133/2021 — visão geral
              </Link>
            </li>
          </ul>
        </section>
      </main>
    </>
  );
}

// ----- Sub-components -----

function ComparativeRow({
  feature,
  manual,
  smartlic,
}: {
  feature: string;
  manual: string;
  smartlic: string;
}) {
  return (
    <tr>
      <td className="px-4 py-3 font-medium text-gray-900 dark:text-white align-top">
        {feature}
      </td>
      <td className="px-4 py-3 text-gray-600 dark:text-gray-400 align-top">{manual}</td>
      <td className="px-4 py-3 text-brand-navy dark:text-blue-200 align-top">
        {smartlic}
      </td>
    </tr>
  );
}

function HowToStep({
  step,
  title,
  description,
}: {
  step: number;
  title: string;
  description: string;
}) {
  return (
    <li className="flex gap-4">
      <div
        aria-hidden="true"
        className="shrink-0 w-10 h-10 rounded-full bg-brand-blue/10 text-brand-blue
                   flex items-center justify-center font-bold"
      >
        {step}
      </div>
      <div>
        <h3 className="font-semibold text-gray-900 dark:text-white mb-1">{title}</h3>
        <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">
          {description}
        </p>
      </div>
    </li>
  );
}
