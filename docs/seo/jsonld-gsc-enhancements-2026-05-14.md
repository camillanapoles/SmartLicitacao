# JSON-LD GSC Enhancements — 2026-05-14 Review

**CTR-OPT-002 AC6 — 14-day post-deploy placeholder**

Review date: 2026-05-14 (14 days after CTR-OPT-002 merged 2026-04-30)

## What to check

1. **Google Search Console — Enhancements tab**
   - Navigate to: https://search.google.com/search-console
   - Check "FAQ rich results" report under Enhancements
   - Look for increase in eligible pages (should be 70, all blog content files)
   - Check for any "Error" or "Warning" flags on FAQPage schema

2. **Rich Results impressions delta**
   - Compare rich result impressions 2026-04-30 to 2026-05-14
   - Benchmark: FAQPage rich snippets typically appear 7-14 days after schema is crawled
   - Expected lift: 20-40% CTR improvement on FAQ-showing URLs (Moz/SEJ benchmark)

3. **Top-5 pages CTR delta (GSC)**
   - pncp-guia-completo-empresas: baseline CTR = ~0.2% (2867 impr)
   - licitacoes-ti-software-2026
   - como-consultar-contratos-publicos-pncp
   - como-participar-primeira-licitacao-2026
   - analise-viabilidade-editais-guia

4. **Any new issues since CTR-OPT-002**
   - Organization block appearing twice (Blocks 1 + 6) — was pre-existing; check if GSC flags this
   - HowTo schema validity (Google may show warnings for MonetaryAmount in HowToStep)

## Pre-existing findings from CTR-OPT-002

- All 70 blog content files (100%) declared JSON-LD as of 2026-04-30
- Production HTML confirmed rendering JSON-LD for all 5 top pages via Googlebot UA curl
- No code fix was needed (AC4 did not fire)
- Organization block appears twice per page (Blocks 1 + 6 in render) — minor duplicate, not a schema violation

## Action items

- [ ] Check GSC Enhancements > FAQ tab for error count
- [ ] Compare CTR before/after for pncp-guia-completo-empresas (2867 impr page)
- [ ] File follow-up story if CTR lift < 10% despite valid schema (may need content/title changes)
