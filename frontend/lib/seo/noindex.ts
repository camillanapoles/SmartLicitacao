/**
 * SEO-P0-003 (#989) — Single source of truth for noindex decisions across
 * route families flagged by `scripts/seo/uniqueness_audit.py`.
 *
 * The audit script writes `noindex-slugs.ts` (auto-generated). This module
 * exposes pure helpers used by:
 *   - `generateMetadata` of each programmatic route family (gates `robots.index`)
 *   - `frontend/app/sitemap.ts` (filters URLs out of the sitemap entirely —
 *     not just noindex; see #989 AC "Sitemap exclusion")
 *
 * Memory note (SEN-FE-001 recidiva): if you change anything that touches
 * fetch options downstream, grep all call sites — never reintroduce
 * `cache: 'no-store'` on revalidate-enabled routes.
 */
import { NOINDEX_SLUGS } from './noindex-slugs';

/**
 * Family ids must mirror those produced by `classify_family` in
 * `scripts/seo/uniqueness_audit.py`. Keep in sync — single string contract.
 */
export type RouteFamily =
  | 'cnpj'
  | 'fornecedores-cnpj'
  | 'contratos-orgao'
  | 'orgaos'
  | 'blog-licitacoes-setor-uf'
  | 'fornecedores-setor-uf'
  | 'contratos-setor-uf'
  | 'alertas-publicos'
  | 'municipios'
  | 'itens';

/**
 * Builds the lookup key. Script-side analogue: `slug_from_url(url, family)`.
 *
 * Path is normalized: trailing slash stripped, leading slash kept. Callers
 * must pass the *path* (not full URL).
 */
export function noindexKey(family: RouteFamily, path: string): string {
  let normalized = path.startsWith('/') ? path : `/${path}`;
  if (normalized.length > 1 && normalized.endsWith('/')) {
    normalized = normalized.slice(0, -1);
  }
  return `${family}:${normalized}`;
}

/**
 * Returns true iff this family+path pair has been flagged as duplicate
 * content by the latest uniqueness audit and should be excluded from search
 * indexing AND from the sitemap.
 */
export function isNoindexed(family: RouteFamily, path: string): boolean {
  return NOINDEX_SLUGS.has(noindexKey(family, path));
}

/**
 * Sitemap helper — filters a list of `{url, ...}` Sitemap entries to drop
 * everything where the path matches a noindexed slug for `family`.
 *
 * Use this in `frontend/app/sitemap.ts` *after* building each entity route
 * list, before returning. Cheap O(n) lookup per entry.
 */
export function filterNoindexedSitemap<T extends { url: string }>(
  entries: T[],
  family: RouteFamily,
): T[] {
  if (NOINDEX_SLUGS.size === 0) return entries; // Fast path: empty list.
  return entries.filter((entry) => {
    try {
      const path = new URL(entry.url).pathname;
      return !isNoindexed(family, path);
    } catch {
      return true; // Malformed URL — leave it in, sitemap renderer will skip.
    }
  });
}
