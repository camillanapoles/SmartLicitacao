import { Metadata } from 'next';
import Link from 'next/link';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { getQuestionBySlug, CATEGORY_META, getQuestionsByCategory } from '@/lib/questions';
import { GLOSSARY_TERMS } from '@/lib/glossary-terms';
import { buildCanonical, SITE_URL } from '@/lib/seo';
import { stripMarkdown } from '@/lib/text';
import LandingNavbar from '@/app/components/landing/LandingNavbar';
import Footer from '@/app/components/Footer';
import { LeadCapture } from '@/components/LeadCapture';
import ReajusteCalculator from './ReajusteCalculator';

export const revalidate = 3600;

const SLUG = 'indice-reajuste-contrato-publico';

export async function generateMetadata(): Promise<Metadata> {
  const question = getQuestionBySlug(SLUG);
  if (!question) return {};

  return {
    title: question.title,
    description: question.metaDescription,
    alternates: { canonical: buildCanonical(`/perguntas/${SLUG}`) },
    openGraph: {
      title: `${question.title} | SmartLic`,
      description: question.metaDescription,
      url: buildCanonical(`/perguntas/${SLUG}`),
      type: 'article',
      siteName: 'SmartLic',
    },
    twitter: {
      card: 'summary_large_image',
      title: `${question.title} | SmartLic`,
      description: question.metaDescription,
    },
  };
}

export default function ReajustePage() {
  const question = getQuestionBySlug(SLUG)!;

  const relatedTermObjects = question.relatedTerms
    .map((termSlug) => GLOSSARY_TERMS.find((t) => t.slug === termSlug))
    .filter(Boolean);

  const relatedQuestions = getQuestionsByCategory(question.category)
    .filter((q) => q.slug !== SLUG)
    .slice(0, 5);

  const plainAnswer = stripMarkdown(question.answer);

  /* QAPage JSON-LD */
  const qaPageLd = {
    '@context': 'https://schema.org',
    '@type': 'QAPage',
    mainEntity: {
      '@type': 'Question',
      name: question.title,
      text: question.title,
      answerCount: 1,
      acceptedAnswer: {
        '@type': 'Answer',
        text: plainAnswer,
        author: {
          '@type': 'Organization',
          name: 'SmartLic',
          url: SITE_URL,
        },
      },
    },
  };

  const breadcrumbLd = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Home', item: SITE_URL },
      { '@type': 'ListItem', position: 2, name: 'Perguntas', item: buildCanonical('/perguntas') },
      {
        '@type': 'ListItem',
        position: 3,
        name: question.title.slice(0, 60),
        item: buildCanonical(`/perguntas/${SLUG}`),
      },
    ],
  };

  /* HowTo JSON-LD — specific to the calculator tool */
  const howToLd = {
    '@context': 'https://schema.org',
    '@type': 'HowTo',
    name: 'Como calcular o reajuste de um contrato público',
    description:
      'Use a calculadora para obter o valor reajustado do seu contrato com base nos índices oficiais IPCA, INPC ou IGP-M.',
    tool: [
      { '@type': 'HowToTool', name: 'IPCA (IBGE)' },
      { '@type': 'HowToTool', name: 'INPC (IBGE)' },
      { '@type': 'HowToTool', name: 'IGP-M (FGV)' },
    ],
    step: [
      {
        '@type': 'HowToStep',
        position: 1,
        name: 'Informe o valor base do contrato',
        text: 'Digite o valor original do contrato em reais no campo "Valor base do contrato".',
      },
      {
        '@type': 'HowToStep',
        position: 2,
        name: 'Selecione o índice de reajuste',
        text: 'Escolha o índice previsto no edital: IPCA para bens e serviços gerais, INPC para contratos com mão de obra, ou IGP-M para aluguéis e fornecimentos de longo prazo.',
      },
      {
        '@type': 'HowToStep',
        position: 3,
        name: 'Informe as datas de vigência e aniversário',
        text: 'Selecione o mês/ano de início da vigência do contrato e a data de aniversário (quando o reajuste deve ser aplicado).',
      },
      {
        '@type': 'HowToStep',
        position: 4,
        name: 'Escolha a periodicidade e calcule',
        text: 'Selecione a periodicidade (anual, semestral ou trimestral) conforme previsto no contrato e clique em "Calcular reajuste" para ver o valor atualizado.',
      },
    ],
  };

  const faqPageLd =
    relatedQuestions.length > 0
      ? {
          '@context': 'https://schema.org',
          '@type': 'FAQPage',
          mainEntity: relatedQuestions.map((q) => ({
            '@type': 'Question',
            name: q.title,
            acceptedAnswer: {
              '@type': 'Answer',
              text: stripMarkdown(q.answer).slice(0, 500),
            },
          })),
        }
      : null;

  return (
    <>
      <LandingNavbar />
      <main className="min-h-screen bg-surface-0">
        {/* Hero */}
        <section className="bg-surface-1 border-b border-[var(--border)] py-12">
          <div className="mx-auto max-w-4xl px-4">
            <nav className="text-sm text-ink-muted mb-4">
              <Link href="/" className="hover:text-ink-primary transition-colors">
                Início
              </Link>
              <span className="mx-2">›</span>
              <Link href="/perguntas" className="hover:text-ink-primary transition-colors">
                Perguntas
              </Link>
              <span className="mx-2">›</span>
              <span className="text-ink-primary">{CATEGORY_META[question.category].label}</span>
            </nav>
            <h1 className="text-3xl font-bold text-ink-primary">{question.h1 ?? question.title}</h1>
            <div className="flex flex-wrap gap-2 mt-4">
              <span className="px-3 py-1 rounded-full text-xs font-medium bg-brand-blue/10 text-brand-blue">
                {CATEGORY_META[question.category].label}
              </span>
              {question.legalBasis && (
                <span className="px-3 py-1 rounded-full text-xs font-medium bg-amber-50 text-amber-700">
                  {question.legalBasis}
                </span>
              )}
            </div>
          </div>
        </section>

        {/* Content grid */}
        <div className="mx-auto max-w-4xl px-4 py-12 grid grid-cols-1 lg:grid-cols-3 gap-12">
          {/* Main content */}
          <article className="lg:col-span-2">
            {/* Calculator — above the explanatory text */}
            <ReajusteCalculator />

            {/* Lead capture — after calculator, before explanatory text */}
            <div className="mb-8">
              <LeadCapture
                source="reajuste-calculadora"
                heading="Quer receber alertas quando novos contratos do seu setor forem abertos?"
                description="Monitoramos o PNCP e fontes oficiais diariamente. Sem spam — cancele quando quiser."
              />
            </div>

            {/* Explanatory content */}
            <div className="prose prose-lg max-w-none text-ink-secondary leading-relaxed">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{question.answer}</ReactMarkdown>
            </div>

            {/* Related articles */}
            {question.relatedArticles.length > 0 && (
              <div className="mt-8 p-4 rounded-xl bg-surface-1 border border-[var(--border)]">
                <h3 className="font-semibold text-ink-primary mb-3">Artigos relacionados</h3>
                <ul className="space-y-2">
                  {question.relatedArticles.map((articleSlug) => (
                    <li key={articleSlug}>
                      <Link
                        href={`/blog/${articleSlug}`}
                        className="text-sm text-brand-blue hover:underline"
                      >
                        {articleSlug
                          .replace(/-/g, ' ')
                          .replace(/\b\w/g, (c) => c.toUpperCase())}{' '}
                        →
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </article>

          {/* Sidebar */}
          <aside className="space-y-6">
            {relatedTermObjects.length > 0 && (
              <div className="p-4 rounded-xl border border-[var(--border)]">
                <h3 className="font-semibold text-ink-primary mb-3">Termos do Glossário</h3>
                <ul className="space-y-2">
                  {relatedTermObjects.map((term) => (
                    <li key={term!.slug}>
                      <Link
                        href={`/glossario/${term!.slug}`}
                        className="text-sm text-brand-blue hover:underline"
                      >
                        {term!.term}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {relatedQuestions.length > 0 && (
              <div className="p-4 rounded-xl border border-[var(--border)]">
                <h3 className="font-semibold text-ink-primary mb-3">Perguntas relacionadas</h3>
                <ul className="space-y-2">
                  {relatedQuestions.map((q) => (
                    <li key={q.slug}>
                      <Link
                        href={`/perguntas/${q.slug}`}
                        className="text-sm text-brand-blue hover:underline"
                      >
                        {q.title}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="p-4 rounded-xl border border-[var(--border)]">
              <h3 className="font-semibold text-ink-primary mb-3">Ferramentas</h3>
              <ul className="space-y-2">
                <li>
                  <Link href="/calculadora" className="text-sm text-brand-blue hover:underline">
                    Calculadora de Oportunidades →
                  </Link>
                </li>
                <li>
                  <Link href="/glossario" className="text-sm text-brand-blue hover:underline">
                    Glossário de Licitações →
                  </Link>
                </li>
                <li>
                  <Link href="/perguntas" className="text-sm text-brand-blue hover:underline">
                    ← Todas as perguntas
                  </Link>
                </li>
              </ul>
            </div>
          </aside>
        </div>

        {/* JSON-LD */}
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(qaPageLd) }}
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbLd) }}
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(howToLd) }}
        />
        {faqPageLd && (
          <script
            type="application/ld+json"
            dangerouslySetInnerHTML={{ __html: JSON.stringify(faqPageLd) }}
          />
        )}
      </main>
      <Footer />
    </>
  );
}
