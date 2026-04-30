# Rich Results Validation — pncp-guia-completo-empresas

**CTR-OPT-002 AC2/AC3 | 2026-04-30**

## URL

- **Production:** https://smartlic.tech/blog/pncp-guia-completo-empresas
- **Rich Results Test:** https://search.google.com/test/rich-results?url=https%3A%2F%2Fsmartlic.tech%2Fblog%2Fpncp-guia-completo-empresas

## AC3 — Curl Validation (Googlebot UA)

```bash
curl -s -A "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)" \
  --max-time 20 \
  "https://smartlic.tech/blog/pncp-guia-completo-empresas" \
  | grep -c 'application/ld+json'
```

**Result:** 8 JSON-LD blocks (grep count of `application/ld+json` occurrences — 1 per opening tag, varies from block count)
**HTTP status:** 200 OK

## JSON-LD Blocks in Production (2026-04-30)

| Block | @type | Source |
|-------|-------|--------|
| 1 | Organization | Global layout (BlogArticleLayout) |
| 2 | WebSite | Global layout |
| 3 | SoftwareApplication | Global layout |
| 4 | Article | BlogArticleLayout per-article |
| 5 | BreadcrumbList | BlogArticleLayout per-article |
| 6 | Organization | Duplicate (layout renders twice — see note) |
| 7 | FAQPage | Content file: pncp-guia-completo-empresas.tsx |
| 8 | HowTo | Content file: pncp-guia-completo-empresas.tsx |

## Types Declared in Source Code

Extracted from `frontend/app/blog/content/pncp-guia-completo-empresas.tsx`:
- `FAQPage` (with `Question` + `Answer` nested)
- `HowTo` (with `HowToStep` nested)

## AC2 — Rich Results Test

**Status:** Manual validation required (automated browser requires host Google session).

To validate:
1. Open https://search.google.com/test/rich-results?url=https%3A%2F%2Fsmartlic.tech%2Fblog%2Fpncp-guia-completo-empresas
2. Expected result: "FAQ" rich result detected, "How-to" rich result detected
3. No errors or warnings on FAQPage / HowTo structure

**Expected rich result types:** FAQ snippet + How-to snippet

## Assessment

**AC4 fires: NO** — JSON-LD is present and rendering correctly in production HTML.
- Server-side rendering confirmed (Googlebot receives pre-rendered JSON-LD in HTML)
- `dangerouslySetInnerHTML` in `<script>` tags is SSR-compatible
- Dynamic import uses default `ssr: true` (no `ssr: false` flag)
- CSP permits inline scripts via `'unsafe-inline'` in `script-src`
