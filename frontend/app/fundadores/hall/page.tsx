/**
 * /fundadores/hall — Hall of Founders (issue #1008 COPY-HALL-009).
 *
 * Server component (no auth gate). Lists founders that opted in via
 * `profiles.founder_public_listing_consent = TRUE`. Data freshness:
 *   - Next.js ISR: `revalidate = 300` (5 minutes)
 *   - Backend Cache-Control: s-maxage=300 (aligned)
 *   - Fetch tag: `next: { revalidate: 300 }` (avoid cache:'no-store',
 *     SEN-FE-001 lesson — that flag breaks SSG output).
 *
 * Hall na home (homepage Hall section) é DEFERRED: PR-mate #1017 está
 * unmerged e mexer em `app/page.tsx` causaria collision.
 */
import type { Metadata } from 'next';
import Link from 'next/link';
import { getBackendUrl } from '@/lib/backend-url';

export const revalidate = 300; // 5 minutes ISR — see header

export const metadata: Metadata = {
  title: 'Hall dos Fundadores | SmartLic',
  description:
    'Empresas fundadoras que escolheram o SmartLic para automatizar a inteligência em licitações públicas.',
  robots: { index: true, follow: true },
};

interface FounderEntry {
  display_name: string;
  uf: string | null;
  setor: string | null;
  logo_url: string | null;
  founder_since: string | null;
}

// Escape JSON for safe inline embedding in <script type="application/ld+json">.
// Even though Next.js puts content inside the tag, an unescaped `</script>` or
// HTML-special chars in user-controlled fields (display_name, logo_url) could
// break out of the script context. Belt-and-suspenders against XSS.
function escapeJsonLd(obj: unknown): string {
  return JSON.stringify(obj)
    .replace(/</g, '\\u003c')
    .replace(/>/g, '\\u003e')
    .replace(/&/g, '\\u0026')
    .replace(/'/g, '\\u0027');
}

interface HallResponse {
  founders: (FounderEntry & { id?: string | null })[];
  count: number;
  fallback: boolean;
}

async function fetchHall(): Promise<HallResponse> {
  const backend = getBackendUrl();
  try {
    const r = await fetch(`${backend}/api/founders/hall`, {
      next: { revalidate: 300 },
      // Defensive timeout — SSG should never hang the build (memory:
      // feedback_build_hammers_backend_cascade).
      signal: AbortSignal.timeout(8_000),
    });
    if (!r.ok) {
      return { founders: [], count: 0, fallback: true };
    }
    const data = (await r.json()) as HallResponse;
    return data;
  } catch {
    return { founders: [], count: 0, fallback: true };
  }
}

function formatDate(iso: string | null): string {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return '';
    return d.toLocaleDateString('pt-BR', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    });
  } catch {
    return '';
  }
}

function FounderCard({ f }: { f: FounderEntry }) {
  const initials = f.display_name
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w.charAt(0).toUpperCase())
    .join('');

  // Schema.org Organization for E-E-A-T (issue #1008 AC).
  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: f.display_name,
    ...(f.logo_url ? { logo: f.logo_url } : {}),
    ...(f.uf ? { address: { '@type': 'PostalAddress', addressRegion: f.uf } } : {}),
  };

  return (
    <li className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-card)] p-5 shadow-sm">
      <script
        type="application/ld+json"
        // display_name / logo_url come from user-controlled DB fields; escape
        // HTML-significant chars to prevent <script>-tag breakout XSS.
        dangerouslySetInnerHTML={{ __html: escapeJsonLd(jsonLd) }}
      />
      <div className="flex items-start gap-4">
        <div className="flex-shrink-0">
          {f.logo_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={f.logo_url}
              alt={`Logo de ${f.display_name}`}
              className="h-14 w-14 rounded-md object-contain bg-white"
              loading="lazy"
              referrerPolicy="no-referrer"
            />
          ) : (
            <div
              aria-hidden
              className="flex h-14 w-14 items-center justify-center rounded-md bg-[var(--surface-muted)] text-base font-semibold text-[var(--ink-secondary)]"
            >
              {initials || '★'}
            </div>
          )}
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="text-base font-semibold text-[var(--ink-primary)]">{f.display_name}</h3>
          <div className="mt-1 flex flex-wrap gap-2 text-xs text-[var(--ink-secondary)]">
            {f.uf ? (
              <span className="rounded-full bg-[var(--surface-muted)] px-2 py-0.5">{f.uf}</span>
            ) : null}
            {f.setor ? (
              <span className="rounded-full bg-[var(--surface-muted)] px-2 py-0.5">{f.setor}</span>
            ) : null}
            {f.founder_since ? (
              <span className="rounded-full bg-[var(--surface-muted)] px-2 py-0.5">
                Fundador desde {formatDate(f.founder_since)}
              </span>
            ) : null}
          </div>
        </div>
      </div>
    </li>
  );
}

export default async function FundadoresHallPage() {
  const data = await fetchHall();

  return (
    <main className="mx-auto max-w-5xl px-4 py-12">
      <header className="mb-10">
        <p className="text-sm font-medium uppercase tracking-wider text-[var(--brand-accent)]">
          Plano Fundadores
        </p>
        <h1 className="mt-2 text-3xl font-bold text-[var(--ink-primary)] md:text-4xl">
          Hall dos Fundadores
        </h1>
        <p className="mt-3 max-w-2xl text-[var(--ink-secondary)]">
          Empresas que adotaram cedo o SmartLic e optaram por aparecer publicamente.
          A listagem é opcional (LGPD) — cada fundador escolhe estar aqui via opt-in
          em sua conta.
        </p>
        {!data.fallback ? (
          <p className="mt-4 text-sm text-[var(--ink-secondary)]">
            <strong>{data.count}</strong> {data.count === 1 ? 'fundador listado' : 'fundadores listados'}
          </p>
        ) : null}
      </header>

      {data.fallback ? (
        <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-card)] p-8 text-center text-[var(--ink-secondary)]">
          Lista temporariamente indisponível. Tente novamente em alguns instantes.
        </div>
      ) : data.founders.length === 0 ? (
        <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-card)] p-8 text-center text-[var(--ink-secondary)]">
          <p>Nenhum fundador optou por listagem pública ainda.</p>
          <p className="mt-2 text-sm">
            Se você é fundador e quer aparecer aqui, ative o opt-in em{' '}
            <Link href="/conta/perfil" className="underline hover:no-underline">
              /conta/perfil
            </Link>
            .
          </p>
        </div>
      ) : (
        <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.founders.map((f) => (
            <FounderCard
              // Stable composite key: founder_since is the per-user opt-in
              // timestamp from the DB, unique enough to avoid React key
              // collisions even with duplicate display_names.
              key={`${f.founder_since ?? ''}|${f.display_name}|${f.uf ?? ''}`}
              f={f}
            />
          ))}
        </ul>
      )}

      <footer className="mt-12 border-t border-[var(--border-subtle)] pt-6 text-sm text-[var(--ink-secondary)]">
        <p>
          Quer entrar para o Plano Fundadores?{' '}
          <Link
            href="/fundadores"
            className="font-medium text-[var(--brand-accent)] underline hover:no-underline"
          >
            Saiba mais
          </Link>
          .
        </p>
      </footer>
    </main>
  );
}
