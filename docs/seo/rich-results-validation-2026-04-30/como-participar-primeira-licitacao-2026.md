# Rich Results Validation — como-participar-primeira-licitacao-2026

**CTR-OPT-002 AC2/AC3 | 2026-04-30**

## URL

- **Production:** https://smartlic.tech/blog/como-participar-primeira-licitacao-2026
- **Rich Results Test:** https://search.google.com/test/rich-results?url=https%3A%2F%2Fsmartlic.tech%2Fblog%2Fcomo-participar-primeira-licitacao-2026

> Note: The story referenced this slug as `como-participar-primeira-licitacao` (without `-2026` suffix).
> The actual slug is `como-participar-primeira-licitacao-2026` — confirmed in `frontend/lib/blog.ts` line 926.

## AC3 — Curl Validation (Googlebot UA)

```bash
curl -s -A "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)" \
  --max-time 20 \
  "https://smartlic.tech/blog/como-participar-primeira-licitacao-2026" \
  | grep -c 'application/ld+json'
```

**Result:** 8 JSON-LD blocks
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
| 7 | FAQPage | Content file: como-participar-primeira-licitacao-2026.tsx |
| 8 | HowTo | Content file (also includes MonetaryAmount inline) |

## Types Declared in Source Code

Extracted from `frontend/app/blog/content/como-participar-primeira-licitacao-2026.tsx`:
- `FAQPage` (with `Question` + `Answer` nested)
- `HowTo` (with `HowToStep` nested)
- `MonetaryAmount` (nested within HowTo steps)

This is the only article in the corpus with `MonetaryAmount` in its JSON-LD.

## AC2 — Rich Results Test

**Status:** Manual validation required (automated browser requires host Google session).

To validate:
1. Open https://search.google.com/test/rich-results?url=https%3A%2F%2Fsmartlic.tech%2Fblog%2Fcomo-participar-primeira-licitacao-2026
2. Expected result: "FAQ" rich result detected, "How-to" rich result detected
3. No errors or warnings on FAQPage / HowTo / MonetaryAmount structure

**Expected rich result types:** FAQ snippet + How-to snippet

## Assessment

**AC4 fires: NO** — JSON-LD is present and rendering correctly in production HTML.
