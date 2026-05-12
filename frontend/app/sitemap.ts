import { MetadataRoute } from 'next';
import * as Sentry from '@sentry/nextjs';
import { getAllSlugs, getArticleBySlug } from '@/lib/blog';
import { SECTORS } from '@/lib/sectors';
import { generateSectorParams, generateLicitacoesParams, generateSectorUfParams, backendIdToFrontendSlug } from '@/lib/programmatic';
import { getAllCaseSlugs } from '@/lib/cases';
import { CITIES } from '@/lib/cities';
import { GLOSSARY_TERMS } from '@/lib/glossary-terms';
import { getAllAuthorSlugs } from '@/lib/authors';
import { getAllQuestionSlugs } from '@/lib/questions';
import { getAllMasterclassTemas } from '@/lib/masterclasses';
import { getBackendUrl } from '@/lib/backend-url';
import { ssgLimitedFetch } from '@/lib/concurrency';
// SEO-P0-003 (#989): drop URLs flagged as duplicate by the uniqueness audit
// from the sitemap entirely. Auto-generated allowlist in lib/seo/noindex-slugs.ts.
import { filterNoindexedSitemap } from '@/lib/seo/noindex';

// STORY-SEO-001 AC3: Observable fetch wrapper. Replaces the silent `catch { return []; }`
// pattern that hid ECONNREFUSED / DNS / 5xx errors at build time — which is exactly how
// `sitemap/4.xml` went empty in production for weeks without Sentry or Prometheus alerting.
//
// SEO-SITEMAP-CASCADE-001: wrapper now returns a discriminated result so callers can
// distinguish 503 (retriable — backend DB timeout) from 200+[] (legitimate empty) from
// other errors. This prevents ISR from caching a backend-timeout-induced empty sitemap.
//
// SEN-BE-007 AC11: structured Sentry breadcrumb on every fetch (success and failure)
// with sitemap_outcome ∈ {success, http_error, timeout, empty_data, service_unavailable},
// latency_ms, and url_count.
type FetchSitemapResult<T> =
  | { kind: 'success'; data: T }
  | { kind: 'empty_data'; data: T }
  | { kind: 'service_unavailable' }   // backend 503 — retriable
  | { kind: 'http_error'; status: number }
  | { kind: 'timeout' };

async function fetchSitemapJson<T>(
  endpoint: string,
  extract: (data: unknown) => T,
  label: string,
): Promise<FetchSitemapResult<T>> {
  const backendUrl = getBackendUrl();
  const url = `${backendUrl}${endpoint}`;
  const startedAt = Date.now();
  let outcome: 'success' | 'http_error' | 'timeout' | 'empty_data' | 'service_unavailable' = 'success';
  let statusCode = 0;
  let urlCount = 0;
  let fetchResult: FetchSitemapResult<T> = { kind: 'http_error', status: 0 };
  try {
    const resp = await ssgLimitedFetch(url, {
      next: { revalidate: 3600 },
      signal: AbortSignal.timeout(5000),
    });
    statusCode = resp.status;
    if (resp.status === 503) {
      // SEO-SITEMAP-CASCADE-001: backend returned 503 (DB timeout) — do NOT cache this.
      outcome = 'service_unavailable';
      console.warn(`[sitemap] ${label} returned 503 (backend timeout) url=${url}`);
      fetchResult = { kind: 'service_unavailable' };
    } else if (!resp.ok) {
      outcome = 'http_error';
      const err = new Error(`Sitemap fetch ${label} returned HTTP ${resp.status}`);
      console.error(`[sitemap] ${err.message} url=${url}`);
      Sentry.captureException(err, {
        tags: { sitemap_endpoint: label, sitemap_outcome: 'http_error' },
        contexts: { sitemap: { endpoint, url, status: resp.status } },
      });
      fetchResult = { kind: 'http_error', status: resp.status };
    } else {
      const data = (await resp.json()) as unknown;
      const extracted = extract(data);
      // Count URLs in extracted payload — defensive shape check.
      if (Array.isArray(extracted)) {
        urlCount = extracted.length;
      } else if (extracted && typeof extracted === 'object') {
        // Shape varies per endpoint (combos/cnpjs/orgaos/slugs/catmats). Sum any array values.
        for (const v of Object.values(extracted as Record<string, unknown>)) {
          if (Array.isArray(v)) urlCount += v.length;
        }
      }
      if (urlCount === 0) {
        outcome = 'empty_data';
        fetchResult = { kind: 'empty_data', data: extracted };
      } else {
        outcome = 'success';
        fetchResult = { kind: 'success', data: extracted };
      }
    }
  } catch (err) {
    const errName = (err as Error)?.name || '';
    if (errName === 'TimeoutError' || errName === 'AbortError') {
      outcome = 'timeout';
      fetchResult = { kind: 'timeout' };
    } else {
      outcome = 'http_error';
      fetchResult = { kind: 'http_error', status: 0 };
    }
    console.error(`[sitemap] fetch ${label} failed (${outcome})`, err);
    Sentry.captureException(err, {
      tags: { sitemap_endpoint: label, sitemap_outcome: outcome },
      contexts: { sitemap: { endpoint, url } },
    });
  } finally {
    Sentry.addBreadcrumb({
      category: 'sitemap',
      message: `fetch ${label}`,
      level: outcome === 'success' ? 'info' : 'warning',
      data: {
        sitemap_outcome: outcome,
        status_code: statusCode,
        latency_ms: Date.now() - startedAt,
        url_count: urlCount,
        endpoint,
      },
    });
  }
  return fetchResult;
}

// SEO-SITEMAP-MV-001: Backend queries agora são < 50ms via Materialized Views.
// Retry removido — a fonte de latência era o live aggregate (30-45s), não
// um problema de rede. 5s timeout via AbortSignal na função base é suficiente.
async function fetchSitemapJsonWithRetry<T>(
  endpoint: string,
  extract: (data: unknown) => T,
  label: string,
  _maxRetries = 3,
): Promise<T | null> {
  const res = await fetchSitemapJson<T>(endpoint, extract, label);
  if (res.kind === 'success' || res.kind === 'empty_data') {
    return res.data;
  }
  Sentry.captureMessage(`sitemap_fetch_failed_${label}`, {
    level: 'warning',
    tags: { sitemap_endpoint: label, sitemap_outcome: 'fetch_failed' },
  });
  return null;

}

/**
 * GTM-COPY-006 AC10: Dynamic sitemap with all public pages
 * STORY-261 AC10: Includes /blog and /blog/{slug} routes
 * STORY-324 AC12: Includes /licitacoes and /licitacoes/{setor} routes
 * SEO-PLAYBOOK P0: Includes programmatic, licitacoes setor×UF, and panorama routes
 * SEO-PLAYBOOK Onda 1: Includes /cnpj/{cnpj} pages from datalake (≥1 bid, ~4k-5k URLs)
 * SEO-PLAYBOOK Onda 2: Includes /orgaos/{cnpj} pages from datalake (≥1 bid, top 2000 by volume)
 * SEO-INDEX-001: Sitemap Index com sub-sitemaps segmentados por prioridade de crawl.
 *
 * Next.js generates sitemap.xml automatically as sitemap index from this file.
 * Sub-sitemaps: /sitemap/0.xml (core) → /sitemap/4.xml (entities)
 *
 * SEO-CAC-ZERO: lastmod uses actual content dates instead of build time.
 * Google ignores lastmod when all URLs share the same timestamp.
 */

// STORY-430 AC4: Cache for indexable licitacoes setor×UF combos
let _licitacoesIndexableCache: { setor: string; uf: string }[] | null = null;
let _licitacoesIndexableFetched = false;

async function fetchLicitacoesIndexable(): Promise<{ setor: string; uf: string }[]> {
  if (_licitacoesIndexableFetched && _licitacoesIndexableCache !== null) {
    return _licitacoesIndexableCache;
  }
  const result = await fetchSitemapJsonWithRetry<{ setor: string; uf: string }[]>(
    '/v1/sitemap/licitacoes-indexable',
    (d) => ((d as { combos?: { setor: string; uf: string }[] }).combos ?? []),
    'licitacoes-indexable',
  );
  // SEO-440: empty fallback — without confirmed backend data, we cannot indicate
  // which combos are indexable. Returning generateLicitacoesParams() (all 405 combos)
  // would place noindex pages in sitemap → GSC "Excluded by noindex" mass error.
  // 2026-04-28 elegant-dream: distinguir fetch-failed de fetched-empty.
  // Antes: result ?? [] colapsava null+[] em "fetched=true,cache=[]" stuck 1h ISR.
  // Agora: null (timeout/erro) NAO marca fetched → proximo ISR retry o backend.
  if (result === null) return [];
  _licitacoesIndexableCache = result;
  _licitacoesIndexableFetched = true;
  return _licitacoesIndexableCache;
}

// SEO-460: Cache para órgãos com contratos reais em pncp_supplier_contracts
let _contratosOrgaoCache: string[] = [];
let _contratosOrgaoFetched = false;

async function fetchContratosOrgaoIndexable(): Promise<string[]> {
  if (_contratosOrgaoFetched) return _contratosOrgaoCache;
  const result = await fetchSitemapJsonWithRetry<string[]>(
    '/v1/sitemap/contratos-orgao-indexable',
    (d) => ((d as { orgaos?: string[] }).orgaos ?? []),
    'contratos-orgao-indexable',
  );
  if (result === null) return [];
  _contratosOrgaoCache = result;
  _contratosOrgaoFetched = true;
  return _contratosOrgaoCache;
}

// SEO-COVERAGE-MANIFEST-001 (#1039): Coverage manifest cache
// Used to gate out slugs with coverage_status='empty' from the sitemap.
// historical_empty slugs are kept but rendered with priority=0.3.
// Fail-open: if the manifest fetch fails, all slugs are included.
interface CoverageEntry {
  coverage_status: 'full' | 'partial' | 'empty' | 'historical_empty';
  bid_count: number;
  last_updated: string;
}
type CoverageManifest = Record<string, CoverageEntry>;
let _coverageManifest: CoverageManifest | null = null;
let _coverageManifestFetched = false;

async function fetchCoverageManifest(): Promise<CoverageManifest> {
  if (_coverageManifestFetched && _coverageManifest !== null) return _coverageManifest;
  const result = await fetchSitemapJson<CoverageManifest>(
    '/v1/seo/coverage-manifest',
    (d) => {
      const data = d as { manifest?: CoverageManifest };
      return data.manifest ?? {};
    },
    'coverage-manifest',
  );
  // Fail-open: null/error → return empty object (no filtering applied)
  if (result.kind !== 'success') return {};
  _coverageManifest = result.data;
  _coverageManifestFetched = true;
  return _coverageManifest;
}

/**
 * AC5: Filter slugs based on coverage manifest.
 * - coverage_status='empty': excluded from sitemap
 * - coverage_status='historical_empty': included with priority override to 0.3
 * - anything else (full/partial/not in manifest): included as-is (fail-open)
 *
 * AC7: historical_empty slugs stay accessible (/observatorio/raio-x-marco-2026
 *      pattern — was indexed, now has 0 bids but page still exists).
 */
function applyCoverageFilter(
  urls: MetadataRoute.Sitemap,
  entityType: string,
  manifest: CoverageManifest,
): MetadataRoute.Sitemap {
  // If manifest is empty (fetch failed), return unmodified (fail-open)
  if (Object.keys(manifest).length === 0) return urls;

  return urls
    .filter((entry) => {
      // Extract slug from the URL (last path segment)
      const slug = entry.url.split('/').pop() ?? '';
      const key = `${entityType}/${slug}`;
      const coverage = manifest[key];
      // Only exclude explicitly empty slugs; everything else passes through
      return !coverage || coverage.coverage_status !== 'empty';
    })
    .map((entry) => {
      const slug = entry.url.split('/').pop() ?? '';
      const key = `${entityType}/${slug}`;
      const coverage = manifest[key];
      if (coverage?.coverage_status === 'historical_empty') {
        return { ...entry, priority: 0.3 };
      }
      return entry;
    });
}

// Cache for CNPJ list fetched from backend (build-time)
let _cnpjCache: string[] = [];
let _cnpjFetched = false;

async function fetchSitemapCnpjs(): Promise<string[]> {
  if (_cnpjFetched) return _cnpjCache;
  const result = await fetchSitemapJsonWithRetry<string[]>(
    '/v1/sitemap/cnpjs',
    (d) => ((d as { cnpjs?: string[] }).cnpjs ?? []),
    'cnpjs',
  );
  if (result === null) return [];
  _cnpjCache = result;
  _cnpjFetched = true;
  return _cnpjCache;
}

// SEO-PLAYBOOK Onda 2: Cache for órgãos compradores list
let _orgaoCache: string[] = [];
let _orgaoFetched = false;

// Parte 13 Sprint 3: Cache for fornecedores por CNPJ
let _fornecedoresCnpjCache: string[] = [];
let _fornecedoresCnpjFetched = false;

async function fetchSitemapFornecedoresCnpj(): Promise<string[]> {
  if (_fornecedoresCnpjFetched) return _fornecedoresCnpjCache;
  const result = await fetchSitemapJsonWithRetry<string[]>(
    '/v1/sitemap/fornecedores-cnpj',
    (d) => ((d as { cnpjs?: string[] }).cnpjs ?? []),
    'fornecedores-cnpj',
  );
  if (result === null) return [];
  _fornecedoresCnpjCache = result;
  _fornecedoresCnpjFetched = true;
  return _fornecedoresCnpjCache;
}

// Parte 13 Sprint 4: Cache for municípios slugs
let _municipiosCache: string[] = [];
let _municipiosFetched = false;

async function fetchSitemapMunicipios(): Promise<string[]> {
  if (_municipiosFetched) return _municipiosCache;
  const result = await fetchSitemapJsonWithRetry<string[]>(
    '/v1/sitemap/municipios',
    (d) => ((d as { slugs?: string[] }).slugs ?? []),
    'municipios',
  );
  if (result === null) return [];
  _municipiosCache = result;
  _municipiosFetched = true;
  return _municipiosCache;
}

// Parte 13 Sprint 6: Cache for CATMAT codes
let _itensCache: string[] = [];
let _itensFetched = false;

async function fetchSitemapItens(): Promise<string[]> {
  if (_itensFetched) return _itensCache;
  const result = await fetchSitemapJsonWithRetry<string[]>(
    '/v1/sitemap/itens',
    (d) => ((d as { catmats?: string[] }).catmats ?? []),
    'itens',
  );
  if (result === null) return [];
  _itensCache = result;
  _itensFetched = true;
  return _itensCache;
}

async function fetchSitemapOrgaos(): Promise<string[]> {
  if (_orgaoFetched) return _orgaoCache;
  const result = await fetchSitemapJsonWithRetry<string[]>(
    '/v1/sitemap/orgaos',
    (d) => ((d as { orgaos?: string[] }).orgaos ?? []),
    'orgaos',
  );
  if (result === null) return [];
  _orgaoCache = result;
  _orgaoFetched = true;
  return _orgaoCache;
}

/**
 * SEO-INDEX-001: Sitemap Index — 5 sub-sitemaps segmentados por prioridade de crawl.
 * Google processa na ordem: 0 (core) → 1 (setores) → 2 (combos) → 3 (blog) → 4 (entities).
 * Benefício: crawl budget focado nas páginas mais importantes primeiro.
 *
 * id:0 — Core static (~35 URLs, sem backend) — prioridade máxima
 * id:1 — Sector landing pages (~60 URLs, sem backend)
 * id:2 — Sector×UF combos (~1620 URLs, backend: licitacoes-indexable)
 * id:3 — Content/blog pages (~500 URLs, sem backend)
 * id:4 — Entity pages (~10k+ URLs, backend: cnpjs, orgaos, fornecedores)
 */
/**
 * ISR 1h — uma regeneração por hora cobre N crawler requests (Google + Bing + Yandex).
 * Sem isso, cada hit em sitemap/4.xml disparava 6 fetches sequenciais ao backend
 * (~30-45s) — sob carga de múltiplos crawlers simultâneos, o backend saturaria
 * novamente mesmo com a serialização deste PR. ISR move o custo para 1 request/h
 * por shard em vez de 1 request por crawler-hit.
 */
export const revalidate = 3600;

export async function generateSitemaps() {
  return [
    { id: 0 }, // Core static pages
    { id: 1 }, // Sector landing pages
    { id: 2 }, // Sector×UF programmatic combos
    { id: 3 }, // Content/blog pages
    { id: 4 }, // Entity pages (CNPJs, órgãos, fornecedores)
  ];
}

// SEO-476: Next.js 16 breaking change — id is now Promise<string>, not number.
// Must receive as props object and await the promise before using.
// See: https://nextjs.org/docs/app/api-reference/functions/generate-sitemaps (v16.0.0)
export default async function sitemap(props: { id: Promise<string> }): Promise<MetadataRoute.Sitemap> {
  const baseUrl = process.env.NEXT_PUBLIC_CANONICAL_URL || 'https://smartlic.tech';
  const STATIC_LAST_EDIT = new Date('2026-04-06');
  const today = new Date();
  // Await the Promise<string> and convert to number for switch comparison.
  const numericId = parseInt(await props.id, 10);

  switch (numericId) {
    // -----------------------------------------------------------------------
    // id:0 — Core Static Pages (no backend, ~35 URLs)
    // Highest priority — Google indexes these first via sitemap index ordering.
    // -----------------------------------------------------------------------
    case 0:
      return [
        {
          url: baseUrl,
          lastModified: STATIC_LAST_EDIT,
          changeFrequency: 'weekly',
          priority: 1.0,
        },
        {
          url: `${baseUrl}/planos`,
          lastModified: STATIC_LAST_EDIT,
          changeFrequency: 'weekly',
          priority: 0.9,
        },
        {
          url: `${baseUrl}/features`,
          lastModified: STATIC_LAST_EDIT,
          changeFrequency: 'monthly',
          priority: 0.8,
        },
        {
          url: `${baseUrl}/ajuda`,
          lastModified: STATIC_LAST_EDIT,
          changeFrequency: 'monthly',
          priority: 0.7,
        },
        // /pricing removed: 301 redirect to /planos (ISSUE-SEO-005). Only /planos in sitemap.
        {
          url: `${baseUrl}/signup`,
          lastModified: STATIC_LAST_EDIT,
          changeFrequency: 'monthly',
          priority: 0.6,
        },
        // /login removed: page is noindex, wastes crawl budget
        {
          url: `${baseUrl}/termos`,
          lastModified: new Date('2026-02-01'),
          changeFrequency: 'yearly',
          priority: 0.2,
        },
        {
          url: `${baseUrl}/privacidade`,
          lastModified: new Date('2026-02-01'),
          changeFrequency: 'yearly',
          priority: 0.2,
        },
        {
          url: `${baseUrl}/sobre`,
          lastModified: STATIC_LAST_EDIT,
          changeFrequency: 'monthly',
          priority: 0.6,
        },
        // SEO-PLAYBOOK 6.3: Panorama Licitações Brasil 2026 T1 (gated digital PR asset)
        {
          url: `${baseUrl}/relatorio-2026-t1`,
          lastModified: STATIC_LAST_EDIT,
          changeFrequency: 'weekly' as const,
          priority: 0.8,
        },
        // Issue #653: Landing dedicada B2B tool-search (queries "pncp licitações", "pncp contratos")
        {
          url: `${baseUrl}/ferramentas/pncp-licitacoes`,
          lastModified: STATIC_LAST_EDIT,
          changeFrequency: 'monthly' as const,
          priority: 0.8,
        },
        // SEO-PLAYBOOK P2: Calculadora B2G
        {
          url: `${baseUrl}/calculadora`,
          lastModified: STATIC_LAST_EDIT,
          changeFrequency: 'weekly',
          priority: 0.9,
        },
        // Hub pages (landing, no backend content)
        {
          url: `${baseUrl}/blog`,
          lastModified: today,
          changeFrequency: 'weekly',
          priority: 0.9,
        },
        {
          url: `${baseUrl}/licitacoes`,
          lastModified: today,
          changeFrequency: 'daily' as const,
          priority: 0.9,
        },
        {
          url: `${baseUrl}/alertas-publicos`,
          lastModified: today,
          changeFrequency: 'daily' as const,
          priority: 0.9,
        },
        {
          url: `${baseUrl}/contratos`,
          lastModified: today,
          changeFrequency: 'daily' as const,
          priority: 0.8,
        },
        {
          url: `${baseUrl}/fornecedores`,
          lastModified: today,
          changeFrequency: 'daily' as const,
          priority: 0.8,
        },
        {
          url: `${baseUrl}/dados`,
          lastModified: today,
          changeFrequency: 'daily' as const,
          priority: 0.9,
        },
        {
          url: `${baseUrl}/estatisticas`,
          lastModified: today,
          changeFrequency: 'daily' as const,
          priority: 0.8,
        },
        {
          url: `${baseUrl}/cnpj`,
          lastModified: STATIC_LAST_EDIT,
          changeFrequency: 'weekly',
          priority: 0.8,
        },
        {
          url: `${baseUrl}/orgaos`,
          lastModified: STATIC_LAST_EDIT,
          changeFrequency: 'weekly',
          priority: 0.8,
        },
        {
          url: `${baseUrl}/municipios`,
          lastModified: today,
          changeFrequency: 'weekly' as const,
          priority: 0.8,
        },
        {
          url: `${baseUrl}/compliance`,
          lastModified: today,
          changeFrequency: 'weekly' as const,
          priority: 0.7,
        },
        {
          url: `${baseUrl}/itens`,
          lastModified: today,
          changeFrequency: 'weekly' as const,
          priority: 0.7,
        },
        {
          url: `${baseUrl}/glossario`,
          lastModified: STATIC_LAST_EDIT,
          changeFrequency: 'weekly',
          priority: 0.8,
        },
        {
          url: `${baseUrl}/casos`,
          lastModified: STATIC_LAST_EDIT,
          changeFrequency: 'monthly' as const,
          priority: 0.8,
        },
        {
          url: `${baseUrl}/perguntas`,
          lastModified: STATIC_LAST_EDIT,
          changeFrequency: 'weekly' as const,
          priority: 0.8,
        },
        {
          url: `${baseUrl}/masterclass`,
          lastModified: STATIC_LAST_EDIT,
          changeFrequency: 'weekly' as const,
          priority: 0.8,
        },
        // STORY-431 AC6: Observatório de Licitações
        {
          url: `${baseUrl}/observatorio`,
          lastModified: today,
          changeFrequency: 'monthly' as const,
          priority: 0.8,
        },
        // STORY-SEO-017 AC4: removido /observatorio/raio-x-marco-2026 — rota nao existe
        // em frontend/app/observatorio/, gerava 404 no sitemap sweep 2026-04-24.
        // S3: Comparador de Editais
        {
          url: `${baseUrl}/comparador`,
          lastModified: STATIC_LAST_EDIT,
          changeFrequency: 'weekly' as const,
          priority: 0.8,
        },
        // S5: Demo Interativo
        {
          url: `${baseUrl}/demo`,
          lastModified: STATIC_LAST_EDIT,
          changeFrequency: 'weekly' as const,
          priority: 0.8,
        },
        // S8: Tech Stack page
        {
          url: `${baseUrl}/stack`,
          lastModified: STATIC_LAST_EDIT,
          changeFrequency: 'monthly' as const,
          priority: 0.7,
        },
        {
          url: `${baseUrl}/como-avaliar-licitacao`,
          lastModified: STATIC_LAST_EDIT,
          changeFrequency: 'monthly',
          priority: 0.7,
        },
        {
          url: `${baseUrl}/como-evitar-prejuizo-licitacao`,
          lastModified: STATIC_LAST_EDIT,
          changeFrequency: 'monthly',
          priority: 0.7,
        },
        {
          url: `${baseUrl}/como-filtrar-editais`,
          lastModified: STATIC_LAST_EDIT,
          changeFrequency: 'monthly',
          priority: 0.7,
        },
        {
          url: `${baseUrl}/como-priorizar-oportunidades`,
          lastModified: STATIC_LAST_EDIT,
          changeFrequency: 'monthly',
          priority: 0.7,
        },
        // REPO-009 #761: Consultoria B2G landing
        {
          url: `${baseUrl}/consultoria-b2g`,
          lastModified: new Date('2026-05-07'),
          changeFrequency: 'monthly' as const,
          priority: 0.8,
        },
        // PSEO-HUB-001 (#879): pSEO hub for "licitações públicas 2026"
        {
          url: `${baseUrl}/licitacoes-publicas-2026`,
          lastModified: new Date('2026-05-08'),
          changeFrequency: 'daily' as const,
          priority: 0.9,
        },
        // SEO-PLAYBOOK S4: Weekly digest hub
        {
          url: `${baseUrl}/blog/weekly`,
          lastModified: today,
          changeFrequency: 'weekly' as const,
          priority: 0.8,
        },
        // SEO Wave 3.2: Licitações do dia hub
        {
          url: `${baseUrl}/blog/licitacoes-do-dia`,
          lastModified: today,
          changeFrequency: 'daily' as const,
          priority: 0.9,
        },
        // SEO-PLAYBOOK P7: RSS feed
        {
          url: `${baseUrl}/blog/rss.xml`,
          lastModified: today,
          changeFrequency: 'daily' as const,
          priority: 0.3,
        },
        // S9: Estatísticas embed
        {
          url: `${baseUrl}/estatisticas/embed`,
          lastModified: STATIC_LAST_EDIT,
          changeFrequency: 'monthly' as const,
          priority: 0.6,
        },
        // STORY-SEO-008: Pillar Pages (topical authority hub)
        {
          url: `${baseUrl}/guia`,
          lastModified: new Date('2026-04-22'),
          changeFrequency: 'monthly' as const,
          priority: 0.9,
        },
        {
          url: `${baseUrl}/guia/licitacoes`,
          lastModified: new Date('2026-04-22'),
          changeFrequency: 'monthly' as const,
          priority: 0.9,
        },
        {
          url: `${baseUrl}/guia/lei-14133`,
          lastModified: new Date('2026-04-22'),
          changeFrequency: 'monthly' as const,
          priority: 0.9,
        },
        {
          url: `${baseUrl}/guia/pncp`,
          lastModified: new Date('2026-04-22'),
          changeFrequency: 'monthly' as const,
          priority: 0.9,
        },
      ];

    // -----------------------------------------------------------------------
    // id:1 — Sector Landing Pages (no backend, ~60 URLs)
    // Uses SECTORS constant — no network calls needed.
    // -----------------------------------------------------------------------
    case 1: {
      const sectorRoutes: MetadataRoute.Sitemap = SECTORS.map((sector) => ({
        url: `${baseUrl}/licitacoes/${sector.slug}`,
        changeFrequency: 'daily' as const,
        priority: 0.8,
      }));

      const programmaticSectorRoutes: MetadataRoute.Sitemap = generateSectorParams().map(({ setor }) => ({
        url: `${baseUrl}/blog/programmatic/${setor}`,
        changeFrequency: 'daily' as const,
        priority: 0.8,
      }));

      const panoramaSectorRoutes: MetadataRoute.Sitemap = generateSectorParams().map(({ setor }) => ({
        url: `${baseUrl}/blog/panorama/${setor}`,
        lastModified: STATIC_LAST_EDIT,
        changeFrequency: 'weekly' as const,
        priority: 0.7,
      }));

      // SEO Wave 3.1: /blog/contratos/{setor} pillar pages (15)
      const blogContratosRoutes: MetadataRoute.Sitemap = generateSectorParams().map(({ setor }) => ({
        url: `${baseUrl}/blog/contratos/${setor}`,
        changeFrequency: 'weekly' as const,
        priority: 0.8,
      }));

      // SEO-661: /blog/programmatic/{setor}/{uf} leaf pages (15×27=405)
      // Previously only in sitemap-blog.xml (now deleted). daily/0.7 matches legacy signal.
      const programmaticSectorUfRoutes: MetadataRoute.Sitemap = generateSectorUfParams().map(({ setor, uf }) => ({
        url: `${baseUrl}/blog/programmatic/${setor}/${uf}`,
        changeFrequency: 'daily' as const,
        priority: 0.7,
      }));

      return [
        ...sectorRoutes,
        ...programmaticSectorRoutes,
        ...panoramaSectorRoutes,
        ...blogContratosRoutes,
        ...programmaticSectorUfRoutes,
      ];
    }

    // -----------------------------------------------------------------------
    // id:2 — Sector×UF Programmatic Combos (~1620 URLs, needs backend)
    // SEO-440: licitações filtradas pelo endpoint; contratos/fornecedores usam todas as 405.
    // -----------------------------------------------------------------------
    case 2: {
      // Parallelizar: licitacoesIndexable é o único endpoint necessário neste sub-sitemap.
      // Contratos e fornecedores setor×UF usam todas as 405 combos (generateSectorUfParams).
      const indexableCombos = await fetchLicitacoesIndexable();

      // SEO-643: normalise backend sector IDs to frontend slugs and dedup.
      // /v1/sitemap/licitacoes-indexable returns backend IDs (e.g. software_desenvolvimento,
      // manutencao_predial) which 404 on the frontend.  Multiple backend IDs can map to the
      // same slug (software_desenvolvimento + software_licencas → software), so we dedup
      // by the normalised slug×UF key before building URLs.
      const licitacoesSeenKeys = new Set<string>();
      const licitacoesUfRoutes: MetadataRoute.Sitemap = indexableCombos
        .map(({ setor, uf }) => ({ slug: backendIdToFrontendSlug(setor), uf }))
        .filter(({ slug, uf }) => {
          const key = `${slug}/${uf}`;
          if (licitacoesSeenKeys.has(key)) return false;
          licitacoesSeenKeys.add(key);
          return true;
        })
        .map(({ slug, uf }) => ({
          url: `${baseUrl}/blog/licitacoes/${slug}/${uf}`,
          changeFrequency: 'daily' as const,
          priority: 0.8,
        }));

      // S3: Alertas Publicos — same normalisation + dedup as licitacoes above.
      const alertasSeenKeys = new Set<string>();
      const alertasRoutes: MetadataRoute.Sitemap = indexableCombos
        .map(({ setor, uf }) => ({ slug: backendIdToFrontendSlug(setor), uf }))
        .filter(({ slug, uf }) => {
          const key = `${slug}/${uf}`;
          if (alertasSeenKeys.has(key)) return false;
          alertasSeenKeys.add(key);
          return true;
        })
        .map(({ slug, uf }) => ({
          url: `${baseUrl}/alertas-publicos/${slug}/${uf}`,
          changeFrequency: 'hourly' as const,
          priority: 0.8,
        }));

      // SEO Wave 2 (12.2.1): Contratos setor×UF (405 combos — sem filtro de dados)
      // SEO-CAC-ZERO A1: modalidadeRoutes removidas do sitemap (ISSUE-SEO-002)
      const contratosUfRoutes: MetadataRoute.Sitemap = generateSectorUfParams().map(({ setor, uf }) => ({
        url: `${baseUrl}/contratos/${setor}/${uf}`,
        changeFrequency: 'daily' as const,
        priority: 0.6,
      }));

      // SEO Wave 2 (12.2.2): Fornecedores setor×UF (405 combos)
      const fornecedoresUfRoutes: MetadataRoute.Sitemap = generateSectorUfParams().map(({ setor, uf }) => ({
        url: `${baseUrl}/fornecedores/${setor}/${uf}`,
        changeFrequency: 'daily' as const,
        priority: 0.6,
      }));

      // SEO-P0-003 (#989): drop slugs flagged by the uniqueness audit.
      const filteredLicitacoes = filterNoindexedSitemap(licitacoesUfRoutes, 'blog-licitacoes-setor-uf');
      const filteredAlertas = filterNoindexedSitemap(alertasRoutes, 'alertas-publicos');
      const filteredContratos = filterNoindexedSitemap(contratosUfRoutes, 'contratos-setor-uf');
      const filteredFornecedores = filterNoindexedSitemap(fornecedoresUfRoutes, 'fornecedores-setor-uf');

      return [
        ...filteredLicitacoes,
        ...filteredAlertas,
        ...filteredContratos,
        ...filteredFornecedores,
      ];
    }

    // -----------------------------------------------------------------------
    // id:3 — Content/Blog Pages (no backend, ~500 URLs)
    // Articles, glossary, questions, masterclasses, cases, city pages.
    // -----------------------------------------------------------------------
    case 3: {
      // STORY-261 AC10: Blog article routes — use actual publishDate/lastModified
      const blogArticleRoutes: MetadataRoute.Sitemap = getAllSlugs().map((slug) => {
        const article = getArticleBySlug(slug);
        const dateStr = article?.lastModified || article?.publishDate || '2026-04-06';
        return {
          url: `${baseUrl}/blog/${slug}`,
          lastModified: new Date(dateStr),
          changeFrequency: 'monthly' as const,
          priority: 0.7,
        };
      });

      // SEO-PLAYBOOK S1: Individual glossary term pages
      const glossaryRoutes: MetadataRoute.Sitemap = GLOSSARY_TERMS.map((t) => ({
        url: `${baseUrl}/glossario/${t.slug}`,
        lastModified: STATIC_LAST_EDIT,
        changeFrequency: 'weekly' as const,
        priority: 0.7,
      }));

      // S10: Individual question pages (53+)
      const questionRoutes: MetadataRoute.Sitemap = getAllQuestionSlugs().map((slug) => ({
        url: `${baseUrl}/perguntas/${slug}`,
        lastModified: STATIC_LAST_EDIT,
        changeFrequency: 'weekly' as const,
        priority: 0.7,
      }));

      // S13: Individual masterclass pages
      const masterclassRoutes: MetadataRoute.Sitemap = getAllMasterclassTemas().map((tema) => ({
        url: `${baseUrl}/masterclass/${tema}`,
        lastModified: STATIC_LAST_EDIT,
        changeFrequency: 'weekly' as const,
        priority: 0.8,
      }));

      // SEO-PLAYBOOK P5: Cases de sucesso
      const caseRoutes: MetadataRoute.Sitemap = getAllCaseSlugs().map((slug) => ({
        url: `${baseUrl}/casos/${slug}`,
        lastModified: STATIC_LAST_EDIT,
        changeFrequency: 'monthly' as const,
        priority: 0.8,
      }));

      // S7+S11: Author pages
      const authorRoutes: MetadataRoute.Sitemap = getAllAuthorSlugs().map((slug) => ({
        url: `${baseUrl}/blog/author/${slug}`,
        lastModified: STATIC_LAST_EDIT,
        changeFrequency: 'monthly' as const,
        priority: 0.6,
      }));

      // SEO-PLAYBOOK S4: Weekly digest pages (last 12 weeks)
      const weeklyRoutes: MetadataRoute.Sitemap = Array.from({ length: 12 }, (_, i) => {
        const d = new Date();
        d.setDate(d.getDate() - i * 7);
        const jan4 = new Date(d.getFullYear(), 0, 4);
        const weekNum = Math.ceil(((d.getTime() - jan4.getTime()) / 86400000 + jan4.getDay() + 1) / 7);
        return {
          url: `${baseUrl}/blog/weekly/${d.getFullYear()}-w${weekNum}`,
          lastModified: today,
          changeFrequency: 'weekly' as const,
          priority: 0.8,
        };
      });

      // STORY-SEO-017: Licitacoes do dia — apenas datas com >=5 bids ativos.
      // Substitui Array.from({length:30}) hardcoded que gerava 42 URLs 404 no GSC
      // sweep 2026-04-24 (datas sem dados em pncp_raw_bids: fim de semana, feriado).
      const indexableDates = await fetchSitemapJsonWithRetry<string[]>(
        '/v1/sitemap/licitacoes-do-dia-indexable',
        (d) => ((d as { dates?: string[] }).dates ?? []),
        'licitacoes-do-dia-indexable',
      );
      const todayStr = today.toISOString().slice(0, 10);
      const licitacoesDoDialRoutes: MetadataRoute.Sitemap = (indexableDates ?? [])
        .slice(0, 30)
        .map((dateStr) => {
          const d = new Date(dateStr + 'T12:00:00');
          const isToday = dateStr === todayStr;
          return {
            url: `${baseUrl}/blog/licitacoes-do-dia/${dateStr}`,
            lastModified: isToday ? today : d,
            changeFrequency: (isToday ? 'hourly' : 'daily') as 'hourly' | 'daily',
            priority: isToday ? 0.9 : 0.7,
          };
        });

      // SEO Frente 4: City pSEO pages (/blog/licitacoes/cidade/[cidade])
      // STORY-439 AC2: City × Sector pSEO pages (1.215 URLs) removidas do sitemap.
      const cidadeRoutes: MetadataRoute.Sitemap = CITIES.map((c) => ({
        url: `${baseUrl}/blog/licitacoes/cidade/${c.slug}`,
        lastModified: today,
        changeFrequency: 'daily' as const,
        priority: 0.7,
      }));

      return [
        ...blogArticleRoutes,
        ...glossaryRoutes,
        ...questionRoutes,
        ...masterclassRoutes,
        ...caseRoutes,
        ...authorRoutes,
        ...weeklyRoutes,
        ...licitacoesDoDialRoutes,
        ...cidadeRoutes,
      ];
    }

    // -----------------------------------------------------------------------
    // id:4 — Entity Pages (~10k+ URLs, needs backend)
    // CNPJs, órgãos, fornecedores, municípios, itens, contratos por órgão.
    // Lowest crawl priority — Google processes these last.
    // -----------------------------------------------------------------------
    case 4: {
      // 6 fetches paralelos saturavam o backend (todos timeoutavam em ~30s+) → sitemap vazio em produção.
      // Serializados: 5-7s cada, total ~30-45s, dentro do orçamento de runtime ISR.
      //
      // HOTFIX 2026-04-30 (Stage 8 wedge): build-time pre-flight probe.
      // Backend saturado pelo SSG fan-out (4146 pages) → cascade timeout em sitemap/4.xml
      // → Next.js worker mata route em 60s × 3 attempts → build FAILED.
      // Memory: feedback_build_hammers_backend_cascade. Probe 3s cheap; abort entity
      // sitemap quando backend unreachable evita 6×(15+2+15)s = 192s wasted hammering.
      // ISR revalidate=3600 garante recovery automática quando backend voltar saudável.
      {
        const backendUrl = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
        try {
          const probe = await ssgLimitedFetch(`${backendUrl}/health/live`, {
            signal: AbortSignal.timeout(3000),
            next: { revalidate: 60 }, // SEN-FE-001: align with sitemap revalidate=3600; short TTL for health probe
          });
          if (!probe.ok) {
            const err = new Error(`sitemap/4 probe HTTP ${probe.status}`);
            console.warn('[sitemap/4] backend probe non-ok — skipping entity sitemap', probe.status);
            Sentry.captureMessage('sitemap_4_backend_probe_failed', {
              level: 'warning',
              tags: { sitemap_id: '4', sitemap_outcome: 'probe_http_error', status: String(probe.status) },
              contexts: { sitemap: { url: `${backendUrl}/health/live` } },
            });
            void err;
            return [];
          }
        } catch (e) {
          console.warn('[sitemap/4] backend probe timeout/error — skipping entity sitemap', e);
          Sentry.captureMessage('sitemap_4_backend_probe_failed', {
            level: 'warning',
            tags: { sitemap_id: '4', sitemap_outcome: 'probe_timeout' },
            contexts: { sitemap: { url: `${backendUrl}/health/live` } },
          });
          return [];
        }
      }

      // SEO-COVERAGE-MANIFEST-001 (#1039): fetch coverage manifest in parallel with entity lists.
      // Fail-open: if the manifest is unavailable, all slugs are included unchanged.
      const [
        cnpjList,
        contratosOrgaoList,
        orgaoList,
        fornecedoresCnpjList,
        municipiosList,
        itensList,
        coverageManifest,
      ] = await Promise.all([
        fetchSitemapCnpjs(),
        fetchContratosOrgaoIndexable(),
        fetchSitemapOrgaos(),
        fetchSitemapFornecedoresCnpj(),
        fetchSitemapMunicipios(),
        fetchSitemapItens(),
        fetchCoverageManifest(),
      ]);

      // SEO-PLAYBOOK Onda 1: CNPJ pages from datalake (≥1 bid, ~4k-5k URLs)
      const cnpjRoutes: MetadataRoute.Sitemap = cnpjList.map((cnpj) => ({
        url: `${baseUrl}/cnpj/${cnpj}`,
        lastModified: today,
        changeFrequency: 'weekly' as const,
        priority: 0.5,
      }));

      // SEO-PLAYBOOK Onda 2: Órgãos compradores pages from datalake (≥1 bid, top 2000)
      const orgaoRoutes: MetadataRoute.Sitemap = orgaoList.map((cnpj) => ({
        url: `${baseUrl}/orgaos/${cnpj}`,
        lastModified: today,
        changeFrequency: 'weekly' as const,
        priority: 0.5,
      }));

      // Parte 13 Sprint 3: /fornecedores/{cnpj} — perfis de fornecedores (top 5k)
      const fornecedoresCnpjRoutes: MetadataRoute.Sitemap = fornecedoresCnpjList.map((cnpj) => ({
        url: `${baseUrl}/fornecedores/${cnpj}`,
        lastModified: today,
        changeFrequency: 'weekly' as const,
        priority: 0.5,
      }));

      // Parte 13 Sprint 4: /municipios/{slug} — licitações por município (200 pré-renderizados)
      const municipiosRoutes: MetadataRoute.Sitemap = municipiosList.map((slug) => ({
        url: `${baseUrl}/municipios/${slug}`,
        lastModified: today,
        changeFrequency: 'daily' as const,
        priority: 0.7,
      }));

      // Parte 13 Sprint 6: /itens/{catmat} — benchmark por código CATMAT
      const itensRoutes: MetadataRoute.Sitemap = itensList.map((catmat) => ({
        url: `${baseUrl}/itens/${catmat}`,
        lastModified: today,
        changeFrequency: 'weekly' as const,
        priority: 0.6,
      }));

      // SEO-460: /contratos/orgao/{cnpj} — usa lista filtrada por contratos reais.
      // Endpoint /v1/sitemap/contratos-orgao-indexable consulta pncp_supplier_contracts
      // (não pncp_raw_bids) para garantir que apenas CNPJs com contratos assinados
      // entram no sitemap, eliminando os 794 404s do GSC.
      const contratosOrgaoRoutes: MetadataRoute.Sitemap = contratosOrgaoList.map((cnpj) => ({
        url: `${baseUrl}/contratos/orgao/${cnpj}`,
        lastModified: today,
        changeFrequency: 'weekly' as const,
        priority: 0.5,
      }));

      // SEO-P0-003 (#989): drop slugs flagged by the uniqueness audit.
      const filteredMunicipios = filterNoindexedSitemap(municipiosRoutes, 'municipios');
      const filteredItens = filterNoindexedSitemap(itensRoutes, 'itens');
      const filteredCnpj = filterNoindexedSitemap(cnpjRoutes, 'cnpj');
      const filteredOrgaos = filterNoindexedSitemap(orgaoRoutes, 'orgaos');
      const filteredFornecedoresCnpj = filterNoindexedSitemap(fornecedoresCnpjRoutes, 'fornecedores-cnpj');
      const filteredContratosOrgao = filterNoindexedSitemap(contratosOrgaoRoutes, 'contratos-orgao');

      // SEO-COVERAGE-MANIFEST-001 (#1039): apply coverage gate after noindex filter.
      // Excludes coverage_status='empty' slugs; demotes 'historical_empty' to priority=0.3.
      // Fail-open: if coverageManifest is empty (fetch failed), returns unmodified list.
      const coveredMunicipios = applyCoverageFilter(filteredMunicipios, 'municipio', coverageManifest);
      const coveredCnpj = applyCoverageFilter(filteredCnpj, 'cnpj', coverageManifest);
      const coveredOrgaos = applyCoverageFilter(filteredOrgaos, 'cnpj', coverageManifest);
      const coveredFornecedoresCnpj = applyCoverageFilter(filteredFornecedoresCnpj, 'fornecedor', coverageManifest);

      return [
        ...coveredMunicipios, // Highest priority within entities (geographic, SSG)
        ...filteredItens,     // CATMAT codes: no coverage gate (no entity_type in manifest yet)
        ...coveredCnpj,
        ...coveredOrgaos,
        ...coveredFornecedoresCnpj,
        ...filteredContratosOrgao, // contratos orgão: already filtered by supplier_contracts
      ];
    }

    default:
      return [];
  }
}
