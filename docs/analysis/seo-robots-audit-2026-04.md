# SEO Robots.txt Audit — 2026-04-28 (SEO-PROG-007 AC6)

**Trigger:** Google Search Console reported 464 SEO programmatic pages bucketed as
"Bloqueada pelo robots.txt" (9.8% of 4,714 not-indexed) on 2026-04-28.

**Hypothesis:** the legacy `frontend/public/robots.txt` (62 lines, prefix-match
Disallow rules) over-blocks public routes whose paths share a prefix with
authenticated routes. Per RFC 9309 §2.2.2, `Disallow: /alertas` matches
`/alertas-publicos/*` (40+ public SEO pages). Same goes for `Disallow: /api`
catching `/api/sitemap-*.xml` proxies.

**Verdict:** confirmed. Refactor to path-exact (trailing slash) form lands in
`frontend/app/robots.ts` (this story) and supersedes the static file.

---

## Disallow rule audit table

| Disallow current | Bloqueia rota pública? | Decisão | Rule novo |
|---|---|---|---|
| `/admin` | Não — `/admin/*` é admin-only | manter (path-exact) | `/admin/` |
| `/auth/callback` | Não — endpoint OAuth | manter | `/auth/callback` |
| `/api` | **SIM** — bloqueia `/api/sitemap-*.xml` (Next route handlers públicos) + outras rotas API públicas | refactor: paths específicos | `/api/auth/`, `/api/admin/`, `/api/csp-report` |
| `/dashboard` | Não — auth-only | manter (path-exact) | `/dashboard/` |
| `/conta` | Não — auth-only | manter (path-exact) | `/conta/` |
| `/buscar` | Raiz é SPA shell autenticado (page.tsx é "use client" com QuotaBadge/UserMenu/TrialCountdown). | manter raiz **e** subpaths | `/buscar` + `/buscar/` |
| `/pipeline` | Não — auth-only | manter (path-exact) | `/pipeline/` |
| `/historico` | Não — auth-only | manter (path-exact) | `/historico/` |
| `/mensagens` | Não — auth-only | manter (path-exact) | `/mensagens/` |
| `/alertas` | **SIM** — bloqueia `/alertas-publicos/[setor]/[uf]` (40+ páginas SEO) | refactor: trailing slash | `/alertas/` |
| `/onboarding` | Não — auth-only | manter (path-exact) | `/onboarding/` |
| `/recuperar-senha` | Não — auth flow | manter | `/recuperar-senha` |
| `/redefinir-senha` | Não — auth flow | manter | `/redefinir-senha` |

**Consequence:** dynamic `app/robots.ts` ships 16 Disallow entries (15 from the
table + `/buscar` raiz separately listed). Validation that `/alertas-publicos/*`
and `/api/sitemap-*.xml` remain allowed is enforced by:

- Unit tests (`frontend/__tests__/app/robots.test.ts` — `it.each` over 10 public paths).
- Audit script (`frontend/scripts/audit-robots-coverage.ts` — exit 1 on any block).
- E2E (`frontend/e2e-tests/seo/robots.spec.ts` — runs against live `https://smartlic.tech/robots.txt`).

---

## 10 sample URLs to inspect via GSC URL Inspector

Confirm post-deploy that each of these reports "Crawl: Allowed" + "Indexable" (or
"Indexable, not in index" if discovery is slow). Copy/paste each into Google
Search Console → URL Inspection.

| # | URL | Pre-fix bucket | Expected post-fix |
|---|---|---|---|
| 1 | https://smartlic.tech/alertas-publicos/tecnologia-da-informacao/SP | Bloqueada por robots.txt | Crawl Allowed |
| 2 | https://smartlic.tech/alertas-publicos/saude/RJ | Bloqueada por robots.txt | Crawl Allowed |
| 3 | https://smartlic.tech/alertas-publicos/construcao/MG | Bloqueada por robots.txt | Crawl Allowed |
| 4 | https://smartlic.tech/api/sitemap-1.xml | Bloqueada por robots.txt | Crawl Allowed |
| 5 | https://smartlic.tech/api/sitemap-2.xml | Bloqueada por robots.txt | Crawl Allowed |
| 6 | https://smartlic.tech/blog/programmatic/saude/RJ | Allowed (validar não regrediu) | Crawl Allowed |
| 7 | https://smartlic.tech/cnpj/00000000000191 | Allowed (validar não regrediu) | Crawl Allowed |
| 8 | https://smartlic.tech/observatorio/raio-x-marco-2026 | Allowed (validar não regrediu) | Crawl Allowed |
| 9 | https://smartlic.tech/contratos/saude/SP | Allowed (validar não regrediu) | Crawl Allowed |
| 10 | https://smartlic.tech/admin/seo | Bloqueada (esperado) | Bloqueada (regression guard) |

**Cadence:** inspecionar todos os 10 em D+1 do deploy; recheck em D+7 e D+14
contra contagem GSC "Bloqueada por robots.txt" — esperar drop de 464 → < 50.

---

## Recomendações operacionais

1. **Não deletar `frontend/public/robots.txt` neste PR.** Next.js 16 prioriza
   `app/robots.ts` sobre o estático, mas mantemos o arquivo durante a janela
   de safety de 7 dias (rollback rápido sem revert se algo der errado).
   Follow-up scheduled: `+7d post-deploy`, deletar o estático.
2. **Re-submit sitemap_index no GSC** após deploy: GSC usa o `Sitemap:` declarado
   no robots.txt para descoberta automática. Memory `reference_gsc_playwright_resubmit.md`:
   resubmit manual via Playwright se host browser tem session ativa.
3. **Monitor metric:** GSC "Bloqueada por robots.txt" deve cair de 464 → < 50
   em 14 dias. Se ficar acima de 100 em D+14, abrir incident — provavelmente
   há regra de Cloudflare WAF cuspindo 403 em vez de robots.txt block real
   (out-of-scope desta story; tracked separadamente).
4. **Preview env detection:** `NEXT_PUBLIC_ENVIRONMENT=preview|staging` retorna
   block-all. Se Railway começar a expor preview environments, validar via
   `curl https://<preview>/robots.txt` que retorna `Disallow: /` antes do
   primeiro deploy ser indexado.

---

## Referências

- Story: `docs/stories/2026-04/SEO-PROG-007-robots-ts-dynamic.md`
- Next.js 16 metadata API: https://nextjs.org/docs/app/api-reference/file-conventions/metadata/robots
- RFC 9309 (Robots Exclusion Protocol): https://www.rfc-editor.org/rfc/rfc9309
- Memory: `feedback_handoff_stale_30h.md` (automation > manual edits para SEO state)
- Memory: `feedback_sen_fe_001_recidiva_sitemap.md` (regression guard discipline)
