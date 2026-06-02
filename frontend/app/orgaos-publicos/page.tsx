/**
 * #1374 — /orgaos-publicos landing page
 *
 * Server Component. Handles metadata + JSON-LD structured data.
 * OrgaosPublicosForm is wrapped in a thin 'use client' island.
 */

import type { Metadata } from 'next';
import Link from 'next/link';
import Footer from '@/app/components/Footer';
import LandingNavbar from '@/app/components/landing/LandingNavbar';
import OrgaosPublicosForm from './OrgaosPublicosForm';

// ---------------------------------------------------------------------------
// Metadata
// ---------------------------------------------------------------------------

export const metadata: Metadata = {
  title: 'SmartLic para Órgãos Públicos — Contratação por Inexigibilidade | SmartLic',
  description:
    'Solução white-label de inteligência em licitações para órgãos públicos. Busca multi-fonte, classificação por IA e análise de viabilidade. Contratação via inexigibilidade (Art. 74, I, Lei 14.133).',
  alternates: {
    canonical: '/orgaos-publicos',
  },
  openGraph: {
    title: 'SmartLic para Órgãos Públicos',
    description:
      'Plataforma white-label de inteligência em licitações. Contratação direta por inexigibilidade.',
    url: '/orgaos-publicos',
  },
};

// ---------------------------------------------------------------------------
// Structured data
// ---------------------------------------------------------------------------

const faqItems = [
  {
    question: 'Como funciona a contratação por inexigibilidade?',
    answer:
      'A plataforma SmartLic se enquadra no Art. 74, I, §3º da Lei 14.133/2021 por sua singularidade técnica — sistema proprietário de classificação setorial por IA que não possui similar no mercado brasileiro. Fornecemos modelo completo de justificativa para instrução do processo.',
  },
  {
    question: 'O SmartLic substitui uma equipe de licitação?',
    answer:
      'Não. O SmartLic é uma ferramenta de apoio à tomada de decisão. Ele automatiza a busca, classificação e análise de viabilidade, liberando sua equipe para o que realmente importa: a participação estratégica nos certames.',
  },
  {
    question: 'Quais fontes de dados são cobertas?',
    answer:
      'PNCP (Portal Nacional de Contratações Públicas), PCP v2 (Portal de Compras Públicas) e ComprasGov v3 (Dados Abertos) — consolidadas em um único resultado com deduplicação automática.',
  },
  {
    question: 'É possível customizar os setores e filtros?',
    answer:
      'Sim. A plataforma cobre 20 setores econômicos e é parametrizável conforme as necessidades específicas do órgão, incluindo filtros por UF, modalidade, valor estimado e período.',
  },
  {
    question: 'O órgão precisa de estrutura técnica para usar?',
    answer:
      'Não. A plataforma é web-based, não requer instalação. Oferecemos treinamento inicial e suporte contínuo. A implantação completa é feita em até 20 dias.',
  },
  {
    question: 'Qual o prazo mínimo de contrato?',
    answer:
      'O licenciamento é anual, prorrogável por iguais períodos, nos termos do Art. 106 da Lei 14.133/2021.',
  },
];

const faqSchema = {
  '@context': 'https://schema.org',
  '@type': 'FAQPage',
  mainEntity: faqItems.map((item) => ({
    '@type': 'Question',
    name: item.question,
    acceptedAnswer: {
      '@type': 'Answer',
      text: item.answer,
    },
  })),
};

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function OrgaosPublicosPage() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqSchema) }}
      />

      <LandingNavbar />

      <main className="bg-white dark:bg-slate-950 text-slate-900 dark:text-slate-100">
        {/* ------------------------------------------------------------------ */}
        {/* Hero */}
        {/* ------------------------------------------------------------------ */}
        <section className="relative bg-gradient-to-br from-slate-900 to-blue-950 text-white py-20 px-4">
          <div className="max-w-4xl mx-auto text-center">
            <p className="text-blue-300 text-sm font-semibold uppercase tracking-widest mb-4">
              Solução White-Label · SmartLic
            </p>
            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold leading-tight mb-6">
              Inteligência em licitações para órgãos públicos
            </h1>
            <p className="text-lg sm:text-xl text-slate-300 max-w-3xl mx-auto mb-8">
              Busca multi-fonte, classificação por IA e análise de viabilidade
              em uma única plataforma white-label. Contratação simplificada via
              inexigibilidade — Art. 74, I, Lei 14.133.
            </p>
            <div className="flex flex-col sm:flex-row justify-center gap-4">
              <a
                href="#contato"
                className="inline-block bg-blue-500 hover:bg-blue-400 text-white font-semibold px-8 py-4 rounded-lg transition-colors"
              >
                Solicitar contato →
              </a>
              <a
                href="#material"
                className="inline-block bg-white/10 hover:bg-white/20 text-white font-semibold px-8 py-4 rounded-lg border border-white/30 transition-colors"
              >
                Modelo de inexigibilidade ↓
              </a>
            </div>
            <p className="text-sm text-slate-400 mt-6">
              Atenda ao Art. 74, I, §3º da Lei 14.133· Implantação em 20 dias ·
              Suporte contínuo
            </p>
          </div>
        </section>

        {/* ------------------------------------------------------------------ */}
        {/* 3 funcionalidades principais */}
        {/* ------------------------------------------------------------------ */}
        <section className="py-20 px-4">
          <div className="max-w-5xl mx-auto">
            <h2 className="text-2xl sm:text-3xl font-bold text-center mb-4">
              Três funcionalidades em uma plataforma white-label
            </h2>
            <p className="text-slate-500 dark:text-slate-400 text-center mb-12 max-w-2xl mx-auto">
              Tudo que o seu órgão precisa para centralizar a inteligência de
              licitações em um único sistema, com a identidade visual do órgão.
            </p>

            <div className="grid md:grid-cols-3 gap-8">
              {/* Busca multi-fonte */}
              <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6">
                <div className="w-12 h-12 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center mb-4">
                  <svg
                    className="w-6 h-6 text-blue-600 dark:text-blue-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                    />
                  </svg>
                </div>
                <h3 className="text-lg font-bold mb-2">Busca multi-fonte</h3>
                <p className="text-slate-600 dark:text-slate-400 text-sm">
                  Agrega PNCP, PCP v2 e ComprasGov v3 em uma busca consolidada
                  com deduplicação automática. Cobertura de 27 UFs e mais de 1,5
                  milhão de registros com resposta em menos de 100ms.
                </p>
              </div>

              {/* Classificação IA */}
              <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6">
                <div className="w-12 h-12 rounded-lg bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center mb-4">
                  <svg
                    className="w-6 h-6 text-emerald-600 dark:text-emerald-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
                    />
                  </svg>
                </div>
                <h3 className="text-lg font-bold mb-2">
                  Classificação por IA
                </h3>
                <p className="text-slate-600 dark:text-slate-400 text-sm">
                  Classificação setorial automatizada em 20 setores econômicos
                  com três camadas de decisão (keyword → LLM standard → LLM
                  zero-match). Precisão ≥85% validada em benchmark contínuo.
                </p>
              </div>

              {/* Análise de viabilidade */}
              <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6">
                <div className="w-12 h-12 rounded-lg bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center mb-4">
                  <svg
                    className="w-6 h-6 text-amber-600 dark:text-amber-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                    />
                  </svg>
                </div>
                <h3 className="text-lg font-bold mb-2">
                  Análise de viabilidade
                </h3>
                <p className="text-slate-600 dark:text-slate-400 text-sm">
                  Scoring em 4 fatores (modalidade 30%, prazo 25%, valor
                  estimado 25%, geografia 20%) com pesos validados contra série
                  histórica. Relatórios executivos exportáveis em Excel.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* ------------------------------------------------------------------ */}
        {/* Por que inexigibilidade? */}
        {/* ------------------------------------------------------------------ */}
        <section className="py-16 px-4 bg-slate-50 dark:bg-slate-900">
          <div className="max-w-4xl mx-auto">
            <h2 className="text-2xl sm:text-3xl font-bold text-center mb-4">
              Por que contratação por inexigibilidade?
            </h2>
            <p className="text-slate-500 dark:text-slate-400 text-center mb-10 max-w-2xl mx-auto">
              O SmartLic se enquadra no Art. 74, I, §3º da Lei 14.133 por sua
              singularidade técnica — e você não precisa de licitação para
              contratar.
            </p>

            <div className="grid sm:grid-cols-2 gap-6">
              <div className="bg-white dark:bg-slate-800 rounded-xl p-6 border border-slate-200 dark:border-slate-700">
                <h3 className="font-bold text-lg mb-3 flex items-center gap-2">
                  <span className="text-blue-500" aria-hidden="true">📋</span>
                  Art. 74, I — Inexigibilidade
                </h3>
                <p className="text-slate-600 dark:text-slate-400 text-sm">
                  Inviabilidade de competição por singularidade técnica do
                  serviço. O SmartLic é um sistema proprietário de classificação
                  setorial por IA sem similar no mercado brasileiro.
                </p>
              </div>

              <div className="bg-white dark:bg-slate-800 rounded-xl p-6 border border-slate-200 dark:border-slate-700">
                <h3 className="font-bold text-lg mb-3 flex items-center gap-2">
                  <span className="text-blue-500" aria-hidden="true">⚖️</span>
                  Segurança jurídica
                </h3>
                <p className="text-slate-600 dark:text-slate-400 text-sm">
                  Fornecemos modelo completo de justificativa de singularidade,
                  minuta de contrato e cronograma de implantação — tudo em
                  conformidade com a Lei 14.133/2021.
                </p>
              </div>

              <div className="bg-white dark:bg-slate-800 rounded-xl p-6 border border-slate-200 dark:border-slate-700">
                <h3 className="font-bold text-lg mb-3 flex items-center gap-2">
                  <span className="text-blue-500" aria-hidden="true">💰</span>
                  Economicidade
                </h3>
                <p className="text-slate-600 dark:text-slate-400 text-sm">
                  Custo muito inferior ao de uma equipe interna dedicada. Uma
                  ferramenta que reduz em mais de 70% o tempo de triagem e
                  análise de editais.
                </p>
              </div>

              <div className="bg-white dark:bg-slate-800 rounded-xl p-6 border border-slate-200 dark:border-slate-700">
                <h3 className="font-bold text-lg mb-3 flex items-center gap-2">
                  <span className="text-blue-500" aria-hidden="true">🏛️</span>
                  White-label
                </h3>
                <p className="text-slate-600 dark:text-slate-400 text-sm">
                  A plataforma pode ser personalizada com a identidade visual do
                  órgão. Seus servidores utilizam um sistema que parece ter sido
                  desenvolvido internamente.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* ------------------------------------------------------------------ */}
        {/* Casos de uso (placeholder) */}
        {/* ------------------------------------------------------------------ */}
        <section className="py-20 px-4">
          <div className="max-w-4xl mx-auto">
            <h2 className="text-2xl sm:text-3xl font-bold text-center mb-4">
              Casos de uso reais
            </h2>
            <p className="text-slate-500 dark:text-slate-400 text-center mb-10">
              Como órgãos públicos estão usando o SmartLic para transformar sua
              área de licitações.
            </p>

            <div className="grid sm:grid-cols-2 gap-6">
              {/* Caso 1 */}
              <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center text-blue-600 dark:text-blue-400 font-bold">
                    P
                  </div>
                  <div>
                    <p className="font-semibold text-sm">
                      Prefeitura de médio porte
                    </p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      Setor de Compras e Licitações
                    </p>
                  </div>
                </div>
                <p className="text-slate-600 dark:text-slate-400 text-sm mb-3">
                  Redução de 70% no tempo de triagem de editais. A equipe de 5
                  servidores passou a analisar 3x mais oportunidades no mesmo
                  período.
                </p>
                <p className="text-xs text-slate-400 dark:text-slate-500 italic">
                  *Estudo de caso em desenvolvimento. Resultados estimados com
                  base em uso da plataforma por clientes corporativos.
                </p>
              </div>

              {/* Caso 2 */}
              <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-full bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center text-emerald-600 dark:text-emerald-400 font-bold">
                    S
                  </div>
                  <div>
                    <p className="font-semibold text-sm">
                      Secretaria Estadual
                    </p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      Departamento de Licitações
                    </p>
                  </div>
                </div>
                <p className="text-slate-600 dark:text-slate-400 text-sm mb-3">
                  Centralização da busca de oportunidades em 27 UFs. Economia
                  estimada de R$ 240 mil/ano em horas de servidor.
                </p>
                <p className="text-xs text-slate-400 dark:text-slate-500 italic">
                  *Estudo de caso em desenvolvimento. Resultados estimados com
                  base em uso da plataforma por clientes corporativos.
                </p>
              </div>
            </div>

            <p className="text-center text-sm text-slate-400 mt-8">
              Seu órgão pode ser o próximo caso de sucesso.{' '}
              <a
                href="#contato"
                className="text-blue-600 dark:text-blue-400 underline font-medium"
              >
                Agende uma apresentação personalizada →
              </a>
            </p>
          </div>
        </section>

        {/* ------------------------------------------------------------------ */}
        {/* Planos para governo */}
        {/* ------------------------------------------------------------------ */}
        <section className="py-20 px-4 bg-slate-50 dark:bg-slate-900">
          <div className="max-w-5xl mx-auto">
            <h2 className="text-2xl sm:text-3xl font-bold text-center mb-4">
              Planos para órgãos públicos
            </h2>
            <p className="text-slate-500 dark:text-slate-400 text-center mb-12 max-w-2xl mx-auto">
              Contratação anual por inexigibilidade. Planos adaptados ao porte
              e necessidade do seu órgão.
            </p>

            <div className="grid md:grid-cols-3 gap-6">
              {/* Plano Básico */}
              <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6 flex flex-col">
                <h3 className="text-xl font-bold mb-1">Básico</h3>
                <p className="text-blue-600 dark:text-blue-400 text-sm font-semibold mb-4">
                  Para secretarias e departamentos
                </p>
                <p className="text-3xl font-bold mb-6">
                  Sob consulta
                  <span className="text-sm font-normal text-slate-400">
                    /ano
                  </span>
                </p>
                <ul className="space-y-2 mb-6 flex-1">
                  <li className="flex items-start gap-2 text-sm">
                    <span className="text-green-500 flex-shrink-0 mt-0.5" aria-hidden="true">✓</span>
                    Busca multi-fonte (até 3 UFs)
                  </li>
                  <li className="flex items-start gap-2 text-sm">
                    <span className="text-green-500 flex-shrink-0 mt-0.5" aria-hidden="true">✓</span>
                    Classificação IA em 20 setores
                  </li>
                  <li className="flex items-start gap-2 text-sm">
                    <span className="text-green-500 flex-shrink-0 mt-0.5" aria-hidden="true">✓</span>
                    Análise de viabilidade 4 fatores
                  </li>
                  <li className="flex items-start gap-2 text-sm">
                    <span className="text-green-500 flex-shrink-0 mt-0.5" aria-hidden="true">✓</span>
                    Até 5 usuários simultâneos
                  </li>
                  <li className="flex items-start gap-2 text-sm">
                    <span className="text-green-500 flex-shrink-0 mt-0.5" aria-hidden="true">✓</span>
                    Suporte por e-mail
                  </li>
                </ul>
                <a
                  href="#contato"
                  className="block text-center font-semibold py-3 px-4 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-700 dark:hover:bg-slate-600 text-slate-900 dark:text-slate-100 transition-colors"
                >
                  Consultar valor →
                </a>
              </div>

              {/* Plano Profissional (destaque) */}
              <div className="rounded-xl border border-blue-500 ring-2 ring-blue-500 bg-blue-50 dark:bg-blue-950/30 p-6 flex flex-col">
                <span className="self-start mb-3 text-xs font-bold uppercase tracking-wider bg-blue-500 text-white px-2 py-1 rounded">
                  Mais popular
                </span>
                <h3 className="text-xl font-bold mb-1">Profissional</h3>
                <p className="text-blue-600 dark:text-blue-400 text-sm font-semibold mb-4">
                  Para prefeituras e autarquias
                </p>
                <p className="text-3xl font-bold mb-6">
                  Sob consulta
                  <span className="text-sm font-normal text-slate-400">
                    /ano
                  </span>
                </p>
                <ul className="space-y-2 mb-6 flex-1">
                  <li className="flex items-start gap-2 text-sm">
                    <span className="text-green-500 flex-shrink-0 mt-0.5" aria-hidden="true">✓</span>
                    Busca multi-fonte (até 15 UFs)
                  </li>
                  <li className="flex items-start gap-2 text-sm">
                    <span className="text-green-500 flex-shrink-0 mt-0.5" aria-hidden="true">✓</span>
                    Classificação IA em 20 setores
                  </li>
                  <li className="flex items-start gap-2 text-sm">
                    <span className="text-green-500 flex-shrink-0 mt-0.5" aria-hidden="true">✓</span>
                    Análise de viabilidade 4 fatores
                  </li>
                  <li className="flex items-start gap-2 text-sm">
                    <span className="text-green-500 flex-shrink-0 mt-0.5" aria-hidden="true">✓</span>
                    Até 20 usuários simultâneos
                  </li>
                  <li className="flex items-start gap-2 text-sm">
                    <span className="text-green-500 flex-shrink-0 mt-0.5" aria-hidden="true">✓</span>
                    Suporte prioritário + treinamento
                  </li>
                  <li className="flex items-start gap-2 text-sm">
                    <span className="text-green-500 flex-shrink-0 mt-0.5" aria-hidden="true">✓</span>
                    Relatórios executivos exportáveis
                  </li>
                </ul>
                <a
                  href="#contato"
                  className="block text-center font-semibold py-3 px-4 rounded-lg bg-blue-600 hover:bg-blue-700 text-white transition-colors"
                >
                  Consultar valor →
                </a>
              </div>

              {/* Plano Enterprise */}
              <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6 flex flex-col">
                <h3 className="text-xl font-bold mb-1">Enterprise</h3>
                <p className="text-blue-600 dark:text-blue-400 text-sm font-semibold mb-4">
                  Para governos estaduais
                </p>
                <p className="text-3xl font-bold mb-6">
                  Sob consulta
                  <span className="text-sm font-normal text-slate-400">
                    /ano
                  </span>
                </p>
                <ul className="space-y-2 mb-6 flex-1">
                  <li className="flex items-start gap-2 text-sm">
                    <span className="text-green-500 flex-shrink-0 mt-0.5" aria-hidden="true">✓</span>
                    Busca multi-fonte (27 UFs)
                  </li>
                  <li className="flex items-start gap-2 text-sm">
                    <span className="text-green-500 flex-shrink-0 mt-0.5" aria-hidden="true">✓</span>
                    Classificação IA em 20 setores
                  </li>
                  <li className="flex items-start gap-2 text-sm">
                    <span className="text-green-500 flex-shrink-0 mt-0.5" aria-hidden="true">✓</span>
                    Análise de viabilidade 4 fatores
                  </li>
                  <li className="flex items-start gap-2 text-sm">
                    <span className="text-green-500 flex-shrink-0 mt-0.5" aria-hidden="true">✓</span>
                    Usuários ilimitados
                  </li>
                  <li className="flex items-start gap-2 text-sm">
                    <span className="text-green-500 flex-shrink-0 mt-0.5" aria-hidden="true">✓</span>
                    Suporte dedicado 24/7
                  </li>
                  <li className="flex items-start gap-2 text-sm">
                    <span className="text-green-500 flex-shrink-0 mt-0.5" aria-hidden="true">✓</span>
                    White-label + customizações
                  </li>
                  <li className="flex items-start gap-2 text-sm">
                    <span className="text-green-500 flex-shrink-0 mt-0.5" aria-hidden="true">✓</span>
                    Integração com sistemas existentes
                  </li>
                </ul>
                <a
                  href="#contato"
                  className="block text-center font-semibold py-3 px-4 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-700 dark:hover:bg-slate-600 text-slate-900 dark:text-slate-100 transition-colors"
                >
                  Consultar valor →
                </a>
              </div>
            </div>
          </div>
        </section>

        {/* ------------------------------------------------------------------ */}
        {/* Tecnologia */}
        {/* ------------------------------------------------------------------ */}
        <section className="py-16 px-4">
          <div className="max-w-3xl mx-auto text-center">
            <h2 className="text-2xl sm:text-3xl font-bold mb-4">
              Tecnologia proprietária, resultados validados
            </h2>
            <p className="text-slate-600 dark:text-slate-400 mb-6">
              Toda inteligência da plataforma é produzida por sistemas próprios
              — desde a ingestão de dados das fontes oficiais até a
              classificação setorial por GPT-4.1-nano e a análise de
              viabilidade em 4 fatores. A mesma tecnologia já está disponível
              para empresas no SmartLic.tech.
            </p>
            <Link
              href="/buscar"
              className="inline-block bg-blue-600 hover:bg-blue-700 text-white font-semibold px-6 py-3 rounded-lg transition-colors"
            >
              Explorar a plataforma →
            </Link>
          </div>
        </section>

        {/* ------------------------------------------------------------------ */}
        {/* FAQ */}
        {/* ------------------------------------------------------------------ */}
        <section className="py-16 px-4 bg-slate-50 dark:bg-slate-900">
          <div className="max-w-3xl mx-auto">
            <h2 className="text-2xl sm:text-3xl font-bold text-center mb-12">
              Perguntas frequentes
            </h2>
            <dl className="space-y-6">
              {faqItems.map((item, i) => (
                <div
                  key={i}
                  className="border-b border-slate-200 dark:border-slate-700 pb-6 last:border-0"
                >
                  <dt className="font-semibold text-lg mb-2">
                    {item.question}
                  </dt>
                  <dd className="text-slate-600 dark:text-slate-400">
                    {item.answer}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        </section>

        {/* ------------------------------------------------------------------ */}
        {/* One-pager note (AC-3) */}
        {/* ------------------------------------------------------------------ */}
        {/* ------------------------------------------------------------------ */}
        {/* Material institucional — AC-3: One-pager placeholder */}
        {/* ------------------------------------------------------------------ */}
        <section id="material" className="py-12 px-4 bg-blue-600 text-white">
          <div className="max-w-3xl mx-auto text-center">
            <h2 className="text-2xl font-bold mb-3">
              Material institucional
            </h2>
            <p className="text-blue-100 mb-6">
              Baixe nosso one-pager institucional com visão geral da plataforma,
              funcionalidades e benefícios para órgãos públicos.
            </p>
            <p className="text-blue-200 text-sm">
              O one-pager em PDF estará disponível em breve. Por enquanto,{' '}
              <a href="#contato" className="underline font-semibold text-white">
                solicite contato comercial
              </a>{' '}
              para receber o material diretamente por e-mail.
            </p>
          </div>
        </section>

        {/* ------------------------------------------------------------------ */}
        {/* Contato — OrgaosPublicosForm */}
        {/* ------------------------------------------------------------------ */}
        <section id="contato" className="py-20 px-4">
          <div className="max-w-2xl mx-auto">
            <h2 className="text-2xl sm:text-3xl font-bold text-center mb-3">
              Solicite contato comercial
            </h2>
            <p className="text-slate-600 dark:text-slate-400 text-center mb-8">
              Preencha o formulário e retornaremos em até 48 horas com uma
              proposta personalizada para o seu órgão.
            </p>
            <OrgaosPublicosForm />
          </div>
        </section>
      </main>

      <Footer />
    </>
  );
}
