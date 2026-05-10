/**
 * SEO-P2-011 (Issue #997): E-E-A-T author byline for legal/Lei 14.133 pages.
 *
 * Reusable, server-component-safe byline that renders author name, role,
 * profile link, and publication/update dates above article-style content.
 * Reads from the canonical author registry in `lib/authors.ts` to avoid
 * data duplication.
 *
 * Usage:
 *   <AuthorByline
 *     authorSlug="tiago-sasaki"
 *     publishedAt="2025-09-01"
 *     updatedAt="2026-05-10"
 *   />
 *
 * Renders:
 *   - Avatar (initials fallback if image asset missing — `/authors/{slug}.webp`)
 *   - Name + role
 *   - "Ver perfil" link to /blog/author/{slug}
 *   - LinkedIn link with aria-label
 *   - <time> elements for datePublished + dateModified
 *
 * Schema.org markup is emitted by the parent page (Article + Person JSON-LD)
 * — see `app/perguntas/[slug]/page.tsx`. This component is the visible UI.
 */

import Link from 'next/link';
import { Linkedin } from 'lucide-react';
import { getAuthorBySlug, DEFAULT_AUTHOR_SLUG } from '@/lib/authors';

export interface AuthorBylineProps {
  /** Slug from `lib/authors.ts`. Falls back to DEFAULT_AUTHOR_SLUG when omitted. */
  authorSlug?: string;
  /** ISO date (YYYY-MM-DD) for datePublished. */
  publishedAt: string;
  /** ISO date (YYYY-MM-DD) for dateModified. Optional. */
  updatedAt?: string;
  /** Optional className passthrough for layout-specific spacing. */
  className?: string;
}

function formatDateBR(dateStr: string): string {
  // Normalize to noon BRT to dodge timezone-shift edge cases.
  const date = new Date(`${dateStr}T12:00:00`);
  if (Number.isNaN(date.getTime())) return dateStr;
  return date.toLocaleDateString('pt-BR', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
}

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
}

export default function AuthorByline({
  authorSlug,
  publishedAt,
  updatedAt,
  className = '',
}: AuthorBylineProps) {
  const author = getAuthorBySlug(authorSlug || DEFAULT_AUTHOR_SLUG);

  if (!author) {
    // Defensive fallback — should never hit in practice because DEFAULT_AUTHOR_SLUG
    // resolves. If the registry is empty, render nothing rather than break the page.
    return null;
  }

  const profileUrl = `/blog/author/${author.slug}`;
  const showUpdated = updatedAt && updatedAt !== publishedAt;

  return (
    <div
      className={`flex items-start gap-3 py-4 border-y border-[var(--border)] ${className}`.trim()}
      data-testid="author-byline"
      itemScope
      itemType="https://schema.org/Person"
    >
      {/* Avatar — initials fallback because /authors/{slug}.webp not yet shipped. */}
      <div
        className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-brand-blue text-white font-semibold text-sm"
        aria-hidden="true"
        data-testid="author-byline-avatar"
      >
        {getInitials(author.name)}
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
          <Link
            href={profileUrl}
            className="text-sm font-semibold text-ink hover:text-brand-blue transition-colors"
            aria-label={`Ver perfil completo de ${author.name}`}
            itemProp="url"
          >
            <span itemProp="name">{author.name}</span>
          </Link>
          <span className="text-xs text-ink-secondary" itemProp="jobTitle">
            — {author.role}
          </span>
          {author.socialLinks.linkedin && (
            <a
              href={author.socialLinks.linkedin}
              target="_blank"
              rel="noopener noreferrer me"
              className="text-ink-secondary hover:text-brand-blue transition-colors"
              aria-label={`Perfil de ${author.name} no LinkedIn`}
              data-testid="author-byline-linkedin"
            >
              <Linkedin className="h-4 w-4" aria-hidden="true" />
            </a>
          )}
        </div>

        <p className="mt-1 text-xs text-ink-secondary">{author.shortBio}</p>

        <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-ink-muted">
          <span>
            Publicado em{' '}
            <time dateTime={publishedAt} data-testid="author-byline-published">
              {formatDateBR(publishedAt)}
            </time>
          </span>
          {showUpdated && (
            <span>
              Atualizado em{' '}
              <time dateTime={updatedAt} data-testid="author-byline-updated">
                {formatDateBR(updatedAt as string)}
              </time>
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
