import { Metadata } from 'next';
import Link from 'next/link';
import EmptyStateSEO from '@/components/seo/EmptyStateSEO';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { QUESTIONS, getQuestionBySlug, getAllQuestionSlugs, CATEGORY_META, getQuestionsByCategory } from '@/lib/questions';
import { GLOSSARY_TERMS } from '@/lib/glossary-terms';
import { buildCanonical } from '@/lib/seo';
import { stripMarkdown } from '@/lib/text';
import LandingNavbar from '@/app/components/landing/LandingNavbar';
import Footer from '@/app/components/Footer';
import RelatedArticles from '@/components/seo/RelatedArticles';
import AuthorByline from '@/components/seo/AuthorByline';
import { getAuthorBySlug, DEFAULT_AUTHOR_SLUG } from '@/lib/authors';
import {
  buildPersonAuthorLd,
  buildQaPageLd,
  buildArticleLd,
  buildBreadcrumbLd,
  buildFaqPageLd,
  buildHowToLd,
  isHowToEligible,
  extractHowToSteps,
} from './json-ld';

export const revalidate = 3600;

/**
 * SEO-P2-011 (Issue #997): E-E-A-T author bylines on legal/Lei 14.133 pages.
 *
 * Perguntas pages are content-heavy on Lei 14.133/jurisprudence/TCU and
 * therefore YMYL-adjacent. They previously rendered with `Organization`
 * author only — weak Trustworthiness signal in SERP. We layer an `Article`
 * JSON-LD with `author: Person` on top of the existing `QAPage` (kept for
 * AI Overviews) and bind the `acceptedAnswer.author` to the same Person.
 */
const ARTICLE_PUBLISHED_AT = '2025-09-01';
// Bumped on every meaningful answer revision; keep within last 12 months
// for the "fresh content" SERP signal.
const ARTICLE_UPDATED_AT = '2026-05-10';

export function generateStaticParams() {
  return getAllQuestionSlugs().map((slug) => ({ slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const question = getQuestionBySlug(slug);
  if (!question) return { robots: { index: false, follow: true } };

  return {
    title: `${question.title}`,
    description: question.metaDescription,
    alternates: { canonical: buildCanonical(`/perguntas/${slug}`) },
    openGraph: {
      title: `${question.title} | SmartLic`,
      description: question.metaDescription,
      url: buildCanonical(`/perguntas/${slug}`),
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

export default async function PerguntaPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const question = getQuestionBySlug(slug);
  if (!question) {
    return (
      <>
        <LandingNavbar />
        <EmptyStateSEO
          title="Pergunta não encontrada"
          description="Esta pergunta pode ter sido removida ou o endereço está incorreto. Consulte todas as perguntas sobre licitações públicas."
          ctaHref="/perguntas"
          ctaLabel="Ver todas as perguntas"
        />
        <Footer />
      </>
    );
  }

  // Related glossary terms
  const relatedTermObjects = question.relatedTerms
    .map((termSlug) => GLOSSARY_TERMS.find((t) => t.slug === termSlug))
    .filter(Boolean);

  // Related questions from same category (excluding self)
  const relatedQuestions = getQuestionsByCategory(question.category)
    .filter((q) => q.slug !== slug)
    .slice(0, 5);

  // Plain-text answer for schema.org consumers (AI Overviews, rich results).
  // Markdown markers must be stripped so `**bold**` never leaks into search.
  const plainAnswer = stripMarkdown(question.answer);

  // SEO-P2-011 (#997): E-E-A-T Person author for Article + QAPage schemas.
  const author = getAuthorBySlug(DEFAULT_AUTHOR_SLUG);
  const personAuthorLd = buildPersonAuthorLd(author);
  const qaPageLd = buildQaPageLd(question, plainAnswer, personAuthorLd);
  const articleLd = buildArticleLd(question, slug, personAuthorLd, ARTICLE_PUBLISHED_AT, ARTICLE_UPDATED_AT);
  const breadcrumbLd = buildBreadcrumbLd(question, slug);
  const faqPageLd = buildFaqPageLd(relatedQuestions);

  /*
   * #991 — HowTo JSON-LD for procedural questions.
   *
   * Google deprecated FAQ rich results in May/2026 for non-gov/health sites.
   * QAPage-only emission no longer surfaces in SERP — only AI Overviews.
   * For "como-*" and "*passo-a-passo*" slugs we extract step structure from
   * the existing answer markdown and emit a HowTo schema. Article +
   * BreadcrumbList remain the always-present primary schemas; QAPage stays
   * as secondary for AI Overviews ingestion.
   */
  const howToSteps = isHowToEligible(slug) ? extractHowToSteps(question.answer) : null;
  const howToLd = howToSteps ? buildHowToLd(question, slug, howToSteps) : null;

  return (
    <>
      <LandingNavbar />
      <main className="min-h-screen bg-surface-0">
        {/* Hero */}
        <section className="bg-surface-1 border-b border-[var(--border)] py-12">
          <div className="mx-auto max-w-4xl px-4">
            <nav className="text-sm text-ink-muted mb-4">
              <Link href="/" className="hover:text-ink-primary transition-colors">Início</Link>
              <span className="mx-2">›</span>
              <Link href="/perguntas" className="hover:text-ink-primary transition-colors">Perguntas</Link>
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
            {/* SEO-P2-011 (#997): E-E-A-T author byline above answer body */}
            <AuthorByline
              authorSlug={DEFAULT_AUTHOR_SLUG}
              publishedAt={ARTICLE_PUBLISHED_AT}
              updatedAt={ARTICLE_UPDATED_AT}
              className="mb-6"
            />
            <div className="prose prose-lg max-w-none text-ink-secondary leading-relaxed">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {question.answer}
              </ReactMarkdown>
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
                        {articleSlug.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())} →
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </article>

          {/* Sidebar */}
          <aside className="space-y-6">
            {/* Related glossary terms */}
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

            {/* Related questions */}
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

            {/* Cross-links */}
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

        {/* SEO-P2-010: Cross-link to glossary, sibling questions, articles */}
        <div className="mx-auto max-w-4xl px-4 pb-12">
          <RelatedArticles
            context={{
              type: 'question',
              value: slug,
              currentUrl: `/perguntas/${slug}`,
            }}
            heading="Continue aprendendo"
          />
        </div>

        {/* JSON-LD */}
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(qaPageLd) }} />
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(articleLd) }} />
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbLd) }} />
        {howToLd && (
          <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(howToLd) }} />
        )}
        {faqPageLd && (
          <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(faqPageLd) }} />
        )}
      </main>
      <Footer />
    </>
  );
}
