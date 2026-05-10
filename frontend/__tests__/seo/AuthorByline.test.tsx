/**
 * SEO-P2-011 (Issue #997): AuthorByline component tests.
 *
 * Validates:
 *   - Renders author name, role, and shortBio from `lib/authors.ts`
 *   - Profile link points to `/blog/author/{slug}` with descriptive aria-label
 *   - LinkedIn link present with rel="noopener noreferrer me" and aria-label
 *   - <time> elements have machine-readable `dateTime` attributes
 *   - "Atualizado em" only renders when updatedAt differs from publishedAt
 *   - Falls back to DEFAULT_AUTHOR_SLUG when authorSlug is omitted
 *   - Initials avatar fallback (no /authors/{slug}.webp asset shipped yet)
 */

import { render, screen } from '@testing-library/react';
import AuthorByline from '@/components/seo/AuthorByline';
import { AUTHORS, DEFAULT_AUTHOR_SLUG } from '@/lib/authors';

const tiago = AUTHORS.find((a) => a.slug === DEFAULT_AUTHOR_SLUG)!;

describe('AuthorByline (SEO-P2-011 #997)', () => {
  it('renders author name and role for default slug', () => {
    render(<AuthorByline publishedAt="2025-09-01" />);
    expect(screen.getByText(tiago.name)).toBeInTheDocument();
    // role appears with em-dash separator: "— CEO & CTO"
    expect(
      screen.getByText(new RegExp(`— ${tiago.role.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&')}`)),
    ).toBeInTheDocument();
  });

  it('renders shortBio so the byline carries E-E-A-T context', () => {
    render(<AuthorByline publishedAt="2025-09-01" />);
    expect(screen.getByText(tiago.shortBio)).toBeInTheDocument();
  });

  it('links to /blog/author/{slug} with descriptive aria-label', () => {
    render(<AuthorByline authorSlug={tiago.slug} publishedAt="2025-09-01" />);
    const profileLink = screen.getByLabelText(
      `Ver perfil completo de ${tiago.name}`,
    );
    expect(profileLink).toHaveAttribute('href', `/blog/author/${tiago.slug}`);
  });

  it('renders LinkedIn link with rel="noopener noreferrer me" and aria-label', () => {
    render(<AuthorByline publishedAt="2025-09-01" />);
    const liLink = screen.getByLabelText(
      `Perfil de ${tiago.name} no LinkedIn`,
    );
    expect(liLink).toHaveAttribute('href', tiago.socialLinks.linkedin);
    expect(liLink.getAttribute('rel')).toMatch(/noopener/);
    expect(liLink.getAttribute('rel')).toMatch(/noreferrer/);
    expect(liLink.getAttribute('rel')).toMatch(/\bme\b/);
    expect(liLink).toHaveAttribute('target', '_blank');
  });

  it('renders <time> with ISO dateTime for publishedAt', () => {
    render(<AuthorByline publishedAt="2025-09-01" />);
    const t = screen.getByTestId('author-byline-published');
    expect(t.tagName).toBe('TIME');
    expect(t).toHaveAttribute('dateTime', '2025-09-01');
  });

  it('renders "Atualizado em" only when updatedAt differs from publishedAt', () => {
    const { rerender } = render(
      <AuthorByline publishedAt="2025-09-01" updatedAt="2026-05-10" />,
    );
    const updated = screen.getByTestId('author-byline-updated');
    expect(updated.tagName).toBe('TIME');
    expect(updated).toHaveAttribute('dateTime', '2026-05-10');

    // Same date -> no updated row
    rerender(
      <AuthorByline publishedAt="2025-09-01" updatedAt="2025-09-01" />,
    );
    expect(screen.queryByTestId('author-byline-updated')).toBeNull();
  });

  it('does not render "Atualizado em" when updatedAt is omitted', () => {
    render(<AuthorByline publishedAt="2025-09-01" />);
    expect(screen.queryByTestId('author-byline-updated')).toBeNull();
  });

  it('falls back to DEFAULT_AUTHOR_SLUG when authorSlug is omitted', () => {
    render(<AuthorByline publishedAt="2025-09-01" />);
    expect(screen.getByText(tiago.name)).toBeInTheDocument();
  });

  it('renders initials avatar (no /authors/{slug}.webp asset shipped yet)', () => {
    render(<AuthorByline publishedAt="2025-09-01" />);
    const avatar = screen.getByTestId('author-byline-avatar');
    // Tiago Sasaki -> TS
    expect(avatar.textContent).toBe('TS');
  });

  it('emits Schema.org Person microdata (itemScope/itemType/itemProp)', () => {
    render(<AuthorByline publishedAt="2025-09-01" />);
    const root = screen.getByTestId('author-byline');
    expect(root).toHaveAttribute('itemscope');
    expect(root).toHaveAttribute(
      'itemtype',
      'https://schema.org/Person',
    );
    // itemProp="name" must wrap the displayed name for crawlers
    const nameEl = screen.getByText(tiago.name);
    const nameContainer = nameEl.closest('[itemprop="name"]') ?? nameEl;
    expect(nameContainer.getAttribute('itemprop')).toBe('name');
  });

  it('renders nothing if registry has no matching author', () => {
    const { container } = render(
      <AuthorByline authorSlug="__nonexistent__" publishedAt="2025-09-01" />,
    );
    // DEFAULT_AUTHOR_SLUG only kicks in when authorSlug is undefined/empty,
    // so an explicit unknown slug must yield null.
    expect(container.firstChild).toBeNull();
  });
});
