import { buildCanonical, SITE_URL } from '@/lib/seo';
import { stripMarkdown } from '@/lib/text';
import type { Author } from '@/lib/authors';
import type { Question } from '@/lib/questions';

/**
 * SEO-P2-011 (#997) — JSON-LD builders for /perguntas/[slug].
 *
 * Extracted from page.tsx to keep that route under the godmodule LOC gate
 * (audit-godmodule-loc.yml: ≤20% growth on existing files). Pure functions,
 * no behavior change — output is byte-equivalent to the inline forms.
 */

export function buildPersonAuthorLd(author: Author | undefined) {
  return author
    ? {
        '@type': 'Person',
        name: author.name,
        url: `${SITE_URL}/blog/author/${author.slug}`,
        jobTitle: author.role,
        image: author.image,
        sameAs: author.sameAs,
        knowsAbout: author.knowsAbout,
      }
    : {
        '@type': 'Organization',
        name: 'SmartLic',
        url: SITE_URL,
      };
}

export function buildQaPageLd(question: Question, plainAnswer: string, personAuthorLd: ReturnType<typeof buildPersonAuthorLd>) {
  return {
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
        author: personAuthorLd,
      },
    },
  };
}

export function buildArticleLd(
  question: Question,
  slug: string,
  personAuthorLd: ReturnType<typeof buildPersonAuthorLd>,
  publishedAt: string,
  updatedAt: string,
) {
  return {
    '@context': 'https://schema.org',
    '@type': 'Article',
    headline: question.title,
    description: question.metaDescription,
    author: personAuthorLd,
    publisher: {
      '@type': 'Organization',
      name: 'SmartLic',
      logo: {
        '@type': 'ImageObject',
        url: `${SITE_URL}/logo.svg`,
      },
    },
    datePublished: publishedAt,
    dateModified: updatedAt,
    mainEntityOfPage: {
      '@type': 'WebPage',
      '@id': buildCanonical(`/perguntas/${slug}`),
    },
    inLanguage: 'pt-BR',
    ...(question.legalBasis ? { citation: [{ '@type': 'CreativeWork', name: question.legalBasis }] } : {}),
  };
}

export function buildBreadcrumbLd(question: Question, slug: string) {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Home', item: SITE_URL },
      { '@type': 'ListItem', position: 2, name: 'Perguntas', item: buildCanonical('/perguntas') },
      { '@type': 'ListItem', position: 3, name: question.title.slice(0, 60), item: buildCanonical(`/perguntas/${slug}`) },
    ],
  };
}

export function buildFaqPageLd(relatedQuestions: Question[]) {
  if (relatedQuestions.length === 0) return null;
  return {
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
  };
}
