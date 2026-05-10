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

/* ------------------------------------------------------------------ */
/*  HowTo (#991) — replaces deprecated FAQ rich result for "como-*"   */
/*                 and "*passo-a-passo*" question slugs.              */
/* ------------------------------------------------------------------ */

/**
 * Heuristic eligibility: only emit HowTo for procedural questions where
 * Google's HowTo rich result still pays off (gov/public-procurement).
 * Avoids fabricating steps for definitional questions.
 */
export function isHowToEligible(slug: string): boolean {
  return slug.startsWith('como-') || slug.includes('passo-a-passo');
}

/**
 * Extract ordered procedure steps from question.answer.
 *
 * Recognises two markdown patterns used in `lib/questions.ts`:
 *  - `**N. Title:**\nDescription`         (bold-numbered headings)
 *  - `N. Title — description`             (plain numbered list)
 *
 * Steps are returned in source order. Each step is plain text (markdown
 * stripped) so schema.org consumers (Google rich results, AI overviews)
 * never see `**bold**` markers.
 *
 * Returns `null` when fewer than 3 steps can be extracted — below that,
 * the heuristic is unreliable and we'd fabricate structure that doesn't
 * exist in the source content. Caller should skip HowTo emission in that
 * case (Article + BreadcrumbList alone suffice).
 */
export function extractHowToSteps(answer: string): Array<{ name: string; text: string }> | null {
  const steps: Array<{ name: string; text: string }> = [];

  // Pattern 1: **N. Title:** followed by body text until next `**N+1.` or end.
  const boldNumbered = /\*\*(\d+)\.\s+([^*]+?):\*\*\s*\n([^]*?)(?=\n\*\*\d+\.|$)/g;
  let match: RegExpExecArray | null;
  while ((match = boldNumbered.exec(answer)) !== null) {
    const name = match[2].trim();
    const text = stripMarkdown(match[3]).trim().replace(/\s+/g, ' ');
    if (name && text) steps.push({ name, text });
  }

  // Pattern 2 (fallback): `N. Title` numbered list lines.
  // We can't use stripMarkdown here because it strips leading `N. `; instead
  // we only remove inline bold/italic decorations and keep block structure.
  //
  // To avoid mixing two independent numbered lists (e.g. cost categories +
  // procedure steps), we scope extraction in priority order:
  //  a) Lines AFTER a "Passo a passo" section heading, if one exists.
  //  b) Otherwise, the LAST contiguous numbered sequence in the answer.
  if (steps.length === 0) {
    const inlineStrip = (s: string) =>
      s
        .replace(/\*\*([^*]+)\*\*/g, '$1')
        .replace(/__([^_]+)__/g, '$1')
        .replace(/`([^`]+)`/g, '$1')
        .trim();

    const lines = answer.split('\n').map((l) => l.trim());

    // Locate "Passo a passo" anchor (e.g. "**Passo a passo:**" or "Passo a passo:").
    const anchorIdx = lines.findIndex((l) => /passo\s+a\s+passo/i.test(l));

    // Determine the slice of lines to collect numbered items from.
    const candidateLines = anchorIdx >= 0 ? lines.slice(anchorIdx + 1) : lines;

    if (anchorIdx >= 0) {
      // Anchor found: collect all numbered lines in the post-anchor section.
      for (const line of candidateLines) {
        if (!line) continue;
        const m = /^(\d+)\.\s+(.+)$/.exec(line);
        if (m) {
          const fullText = inlineStrip(m[2]);
          const colonIdx = fullText.indexOf(':');
          const name =
            colonIdx > 0 && colonIdx < 80
              ? fullText.slice(0, colonIdx).trim()
              : fullText.length > 80
                ? fullText.slice(0, 80) + '…'
                : fullText;
          steps.push({ name, text: fullText });
        }
      }
    } else {
      // No anchor: collect the LAST contiguous numbered sequence only,
      // to avoid mixing two independent lists.
      const groups: Array<Array<{ name: string; text: string }>> = [];
      let current: Array<{ name: string; text: string }> = [];
      for (const line of candidateLines) {
        const m = /^(\d+)\.\s+(.+)$/.exec(line);
        if (m) {
          const fullText = inlineStrip(m[2]);
          const colonIdx = fullText.indexOf(':');
          const name =
            colonIdx > 0 && colonIdx < 80
              ? fullText.slice(0, colonIdx).trim()
              : fullText.length > 80
                ? fullText.slice(0, 80) + '…'
                : fullText;
          current.push({ name, text: fullText });
        } else if (line && current.length > 0) {
          // Non-blank, non-numbered line breaks the sequence.
          groups.push(current);
          current = [];
        }
      }
      if (current.length > 0) groups.push(current);
      // Use the last group (most likely the procedure steps).
      if (groups.length > 0) {
        steps.push(...groups[groups.length - 1]);
      }
    }
  }

  if (steps.length < 3) return null;
  return steps;
}

export function buildHowToLd(
  question: Question,
  slug: string,
  steps: Array<{ name: string; text: string }>,
) {
  return {
    '@context': 'https://schema.org',
    '@type': 'HowTo',
    name: question.title,
    description: question.metaDescription,
    inLanguage: 'pt-BR',
    mainEntityOfPage: {
      '@type': 'WebPage',
      '@id': buildCanonical(`/perguntas/${slug}`),
    },
    step: steps.map((s, i) => ({
      '@type': 'HowToStep',
      position: i + 1,
      name: s.name,
      text: s.text,
    })),
  };
}
