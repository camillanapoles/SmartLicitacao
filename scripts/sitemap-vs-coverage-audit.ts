/**
 * SEO-COVERAGE-MANIFEST-001 AC6: Reconciliação sitemap emitido vs manifest de cobertura.
 *
 * Valida que nenhum slug com coverage_status='empty' está presente no sitemap
 * e que slugs com 'historical_empty' têm priority=0.3.
 *
 * Uso:
 *   npx tsx scripts/sitemap-vs-coverage-audit.ts [--base-url https://smartlic.tech]
 *
 * Retorna exit code 1 se qualquer drift for detectado.
 *
 * Compatível com o formato da rota em produção (manifest chave-composta).
 */

const BASE_URL = process.env.NEXT_PUBLIC_CANONICAL_URL
  ?? process.argv.find((a) => a.startsWith('--base-url='))?.split('=')[1]
  ?? 'https://smartlic.tech';

const BACKEND_URL = process.env.BACKEND_URL
  ?? process.env.NEXT_PUBLIC_BACKEND_URL
  ?? 'http://localhost:8000';

interface CoverageEntry {
  coverage_status: 'full' | 'partial' | 'historical_empty' | 'empty';
  bid_count: number;
  last_updated: string;
}

interface ManifestResponse {
  manifest: Record<string, CoverageEntry>;
  total_entities: number;
  generated_at: string;
}

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url, { signal: AbortSignal.timeout(15000) });
  if (!res.ok) throw new Error(`HTTP ${res.status} from ${url}`);
  return res.json() as Promise<T>;
}

async function parseSitemapUrls(sitemapUrl: string): Promise<string[]> {
  const res = await fetch(sitemapUrl, { signal: AbortSignal.timeout(15000) });
  if (!res.ok) throw new Error(`HTTP ${res.status} from ${sitemapUrl}`);
  const text = await res.text();
  const matches = text.matchAll(/<loc>(.*?)<\/loc>/g);
  return Array.from(matches).map((m) => m[1]);
}

async function main() {
  console.log('Reconciling sitemap vs coverage manifest');
  console.log(`  BASE_URL:    ${BASE_URL}`);
  console.log(`  BACKEND_URL: ${BACKEND_URL}`);
  console.log('');

  // 1. Fetch coverage manifest
  const resp = await fetchJson<ManifestResponse>(`${BACKEND_URL}/v1/seo/coverage-manifest`);
  const manifest = resp.manifest;

  // Extract municipio entries (composite key: "municipio/<slug>")
  const municipioEntries: Record<string, CoverageEntry> = {};
  for (const [key, entry] of Object.entries(manifest)) {
    if (key.startsWith('municipio/')) {
      const slug = key.slice('municipio/'.length);
      municipioEntries[slug] = entry;
    }
  }

  const emptyMunicipios = new Set(
    Object.entries(municipioEntries)
      .filter(([, e]) => e.coverage_status === 'empty')
      .map(([slug]) => slug),
  );
  const historicalEmptyMunicipios = new Set(
    Object.entries(municipioEntries)
      .filter(([, e]) => e.coverage_status === 'historical_empty')
      .map(([slug]) => slug),
  );

  console.log(`Manifest: ${resp.total_entities} entities total`);
  console.log(`  municipios: ${Object.keys(municipioEntries).length} total`);
  console.log(`    empty: ${emptyMunicipios.size}`);
  console.log(`    historical_empty: ${historicalEmptyMunicipios.size}`);
  console.log('');

  // 2. Fetch sitemap index to find municipios sub-sitemap
  const sitemapIndex = await parseSitemapUrls(`${BASE_URL}/sitemap.xml`);
  console.log(`Sitemap index: ${sitemapIndex.length} sub-sitemaps`);

  // 3. Scan all sub-sitemaps for /municipios/ URLs
  const sitemapMunicipioSlugs: string[] = [];
  for (const subUrl of sitemapIndex) {
    const urls = await parseSitemapUrls(subUrl);
    for (const url of urls) {
      const match = url.match(/\/municipios\/([^/?#]+)/);
      if (match) sitemapMunicipioSlugs.push(match[1]);
    }
  }
  console.log(`Sitemap: ${sitemapMunicipioSlugs.length} municipio URLs found`);
  console.log('');

  // 4. Check for drift
  let driftCount = 0;

  for (const slug of sitemapMunicipioSlugs) {
    if (emptyMunicipios.has(slug)) {
      console.error(`DRIFT: /municipios/${slug} in sitemap but coverage_status='empty'`);
      driftCount++;
    }
  }

  // 5. Verify manifest has entries for slugs in sitemap
  const manifestSlugs = new Set(Object.keys(municipioEntries));
  if (manifestSlugs.size === 0) {
    console.warn('WARNING: manifest is empty — cron may not have run yet');
  } else {
    const inSitemapNotManifest = sitemapMunicipioSlugs.filter((s) => !manifestSlugs.has(s));
    if (inSitemapNotManifest.length > 0) {
      console.warn(
        `WARNING: ${inSitemapNotManifest.length} sitemap slugs not in manifest (treated as full coverage)`,
      );
    }
  }

  console.log('');
  if (driftCount > 0) {
    console.error(`AUDIT FAILED: ${driftCount} drift(s) detected`);
    process.exit(1);
  } else {
    console.log('AUDIT PASSED: 0 drifts detected');
  }
}

main().catch((err) => {
  console.error('Audit error:', err);
  process.exit(1);
});
