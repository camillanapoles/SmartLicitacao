# Rich Results Validation — como-consultar-contratos-publicos-pncp

**CTR-OPT-002 AC2/AC3 | 2026-04-30**

## URL

- **Production:** https://smartlic.tech/blog/como-consultar-contratos-publicos-pncp
- **Rich Results Test:** https://search.google.com/test/rich-results?url=https%3A%2F%2Fsmartlic.tech%2Fblog%2Fcomo-consultar-contratos-publicos-pncp

## AC3 — Curl Validation (Googlebot UA)

```bash
curl -s -A "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)" \
  --max-time 20 \
  "https://smartlic.tech/blog/como-consultar-contratos-publicos-pncp" \
  | grep -c 'application/ld+json'
```

**Result:** 7 JSON-LD blocks
**HTTP status:** 200 OK

## JSON-LD Blocks in Production (2026-04-30)

| Block | @type | Source |
|-------|-------|--------|
| 1 | Organization | Global layout (BlogArticleLayout) |
| 2 | WebSite | Global layout |
| 3 | SoftwareApplication | Global layout |
| 4 | Article | BlogArticleLayout per-article |
| 5 | BreadcrumbList | BlogArticleLayout per-article |
| 6 | Organization | Duplicate (layout renders twice) |
| 7 | FAQPage | Content file: como-consultar-contratos-publicos-pncp.tsx |

## Types Declared in Source Code

Extracted from `frontend/app/blog/content/como-consultar-contratos-publicos-pncp.tsx`:
- `FAQPage` (with `Question` + `Answer` nested)
- No `HowTo` in this article (FAQ-only variant)

## AC2 — Rich Results Test

**Status:** Manual validation required (automated browser requires host Google session).

To validate:
1. Open https://search.google.com/test/rich-results?url=https%3A%2F%2Fsmartlic.tech%2Fblog%2Fcomo-consultar-contratos-publicos-pncp
2. Expected result: "FAQ" rich result detected
3. No errors or warnings on FAQPage structure

**Expected rich result types:** FAQ snippet only (no HowTo in this article)

## Assessment

**AC4 fires: NO** — JSON-LD is present and rendering correctly in production HTML.
