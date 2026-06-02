/**
 * CONV-017 (#1332): JourneyLinks — intent-progressive journey component.
 *
 * Renders a structured, ordered set of up to 5 links that guide the user
 * through a progression of commercial intent (most transactional first,
 * most exploratory last). Replaces the flat "Páginas Relacionadas" section
 * on entity pages.
 *
 * Features:
 * - Numbered steps with emoji icons and descriptive text
 * - Schema.org ItemList JSON-LD for rich search results
 * - Mixpanel tracking via JourneyLinkTracker client wrapper
 * - Ordered by intent (never shuffled)
 */

import type { JourneyStep } from '@/lib/seo/relatedResolver';
import { JourneyLinkTracker } from './JourneyLinkTracker';

interface JourneyLinksProps {
  /** Ordered journey steps (max 5). */
  journey: JourneyStep[];
  /** Template identifier for analytics (e.g. 'fornecedor', 'orgao'). */
  sourceTemplate: string;
  /** Optional heading override. Default: "Próximos passos" */
  heading?: string;
}

export function JourneyLinks({
  journey,
  sourceTemplate,
  heading = 'Próximos passos',
}: JourneyLinksProps) {
  if (journey.length === 0) return null;

  const itemListJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'ItemList',
    name: heading,
    description: 'Jornada de navegação progressiva para explorar dados públicos.',
    numberOfItems: journey.length,
    itemListElement: journey.map((step) => ({
      '@type': 'ListItem',
      position: step.position,
      name: step.title,
      description: step.description,
      url: `https://smartlic.tech${step.href}`,
    })),
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(itemListJsonLd) }}
      />

      <section className="border-t border-gray-200 pt-8 mb-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-1">{heading}</h2>
        <p className="text-sm text-gray-500 mb-4">
          Explore dados relacionados em ordem recomendada.
        </p>

        <div className="space-y-3">
          {journey.map((step) => (
            <JourneyLinkTracker
              key={step.position}
              href={step.href}
              sourceTemplate={sourceTemplate}
              destinationType={step.destinationType}
              position={step.position}
              className="block group"
            >
              <div className="flex items-start gap-3 rounded-lg border border-gray-200 bg-white p-3 transition-colors hover:border-blue-300 hover:bg-blue-50/50">
                {/* Position badge */}
                <span
                  className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue-100 text-sm font-bold text-blue-700 group-hover:bg-blue-200 transition-colors"
                  aria-hidden="true"
                >
                  {step.position}
                </span>

                {/* Content */}
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-base" aria-hidden="true">{step.icon}</span>
                    <span className="text-sm font-medium text-gray-900 group-hover:text-blue-700 transition-colors">
                      {step.title}
                    </span>
                  </div>
                  <p className="mt-0.5 text-xs text-gray-500 line-clamp-2">
                    {step.description}
                  </p>
                </div>

                {/* Arrow */}
                <svg
                  className="mt-1 h-4 w-4 shrink-0 text-gray-400 group-hover:text-blue-600 transition-colors"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M9 5l7 7-7 7"
                  />
                </svg>
              </div>
            </JourneyLinkTracker>
          ))}
        </div>
      </section>
    </>
  );
}
