/**
 * Issue #1034: ISR-safe empty/missing-data state for SEO programmatic pages.
 *
 * Replaces `notFound()` calls in dynamic SEO routes that hit ISR
 * (revalidate ≥ hours). `notFound()` becomes a TERMINAL state under ISR — a
 * single transient backend blip turns into a 24h hard 404. This component
 * lets the route render a real, indexable-aware page (with `robots:noindex`
 * set in `generateMetadata`) so transient failures degrade gracefully and
 * recover on next revalidation.
 *
 * Stateless server-component. No data fetching, no client hooks.
 */

import Link from 'next/link';

export interface EmptyStateSEOProps {
  title: string;
  description: string;
  ctaHref?: string;
  ctaLabel?: string;
  periodLabel?: string;
}

export default function EmptyStateSEO({
  title,
  description,
  ctaHref,
  ctaLabel,
  periodLabel,
}: EmptyStateSEOProps) {
  return (
    <section
      className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-12"
      aria-labelledby="empty-state-seo-title"
      data-testid="empty-state-seo"
    >
      <div className="rounded-2xl border border-gray-200 bg-white p-8 sm:p-10 shadow-sm">
        {periodLabel && (
          <p className="text-sm font-medium uppercase tracking-wide text-gray-500 mb-3">
            {periodLabel}
          </p>
        )}
        <h1
          id="empty-state-seo-title"
          className="text-2xl sm:text-3xl font-semibold text-gray-900 mb-4"
        >
          {title}
        </h1>
        <p className="text-base text-gray-600 leading-relaxed mb-6">
          {description}
        </p>
        {ctaHref && ctaLabel && (
          <Link
            href={ctaHref}
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
          >
            {ctaLabel}
          </Link>
        )}
      </div>
    </section>
  );
}
