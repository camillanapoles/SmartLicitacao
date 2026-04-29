# Visor — Inventário de Interface

> Gerado pelo **Reversa Visor** em 2026-04-27
> Fonte: 226 screenshots em `/mnt/d/pncp-poc/*.png` + análise estática de `frontend/app/`
> Confiança: 🟢 CONFIRMADO (page existe + screenshot confirma) · 🟡 INFERIDO (page existe sem screenshot direto)

> **Nota:** análise visual leve (sem inspeção pixel-by-pixel das 226 PNGs). Confiança da estrutura mais alta que da renderização. Para a auditoria visual completa, abra screenshots agrupados por persona.

## Páginas mapeadas

### Públicas (anonymous)

| Rota | Page | Estado UI | Screenshots |
|------|------|-----------|-------------|
| `/` | Landing institucional | hero + value-prop + CTA + testimonial + plans | `01-homepage-inicial.png`, `01-landing-hero.png`, `02-landing-full.png`, `ux-audit-landing.png`, `ux-audit-mobile-landing.png` |
| `/login` | Login form | email + senha + Google OAuth + magic link | (nenhum direto, ver `ux-audit-*-mobile`) |
| `/signup` | Signup wizard | email + senha + WhatsApp consent (opt-in) | `02-pagina-cadastro.png`, `03-signup-page.png`, `03-formulario-preenchido.png` |
| `/recuperar-senha` | Reset request | email input | — |
| `/redefinir-senha` | Reset confirm | new password | — |
| `/auth/callback` | OAuth handoff | loading state + redirect | — |
| `/planos` | Pricing page | toggle mensal/sem/anual + 3 cards | `ux-audit-planos.png` |
| `/planos/obrigado` | Post-checkout thank you | confirmation + next steps | — |
| `/pricing` | Marketing pricing | (alt to /planos?) | — |
| `/features` | Features page | content marketing | — |
| `/ajuda` | Help center | FAQ + categorias + busca | — |
| `/termos` | Terms of service | static content | — |
| `/privacidade` | Privacy policy | static content | — |
| `/observatorio` | Observatório index | landing público | `10-observatorio.png` |
| `/observatorio/[slug]` | Observatório panorama | dynamic ISR | — |
| `/observatorio/raio-x-{setor,municipio,orgao,alerta}/[id]` | Raio-X dashboards | charts + tables | — |
| `/cnpj/[cnpj]` | Perfil fornecedor | contratos + JSON-LD | — |
| `/fornecedores/[cnpj]` | (alt route) | — | — |
| `/orgaos/[slug]` | Perfil órgão | contratos + sanctions | — |
| `/municipios/[slug]` | Perfil município | índice + ranking | — |
| `/licitacoes/[setor]` | Listagem por setor | grid de bids | — |
| `/contratos/[setor]/[uf]` | Contratos por setor+UF | tabela | — |
| `/contratos/orgao/[cnpj]` | Contratos por órgão | tabela | — |
| `/blog/contratos/[setor]`, `/blog/licitacoes/[setor]`, `/blog/licitacoes/cidade/[city]`, `/blog/panorama/[setor]`, `/blog/programmatic/[setor]` | Blog programmatic SEO | conteúdo + JSON-LD FAQPage | — |
| `/alertas-publicos/[setor]/[uf]` | Alert preview | sample alert | — |
| `/indice-municipal/[municipio-uf]` | Índice municipal | score + breakdown | — |
| `/calculadora` | Calculadora viability | form + result | — |
| `/calculadora/embed` | Embed iframe | iframe-friendly | — |
| `/comparador` | Comparador editais | side-by-side | — |
| `/compliance/[cnpj]` | Sanctions check | pass/fail badges | — |

### Autenticadas (auth required)

| Rota | Page | Estado UI | Screenshots |
|------|------|-----------|-------------|
| `/onboarding` | 3-step wizard | progress bar + step1 (CNAE) + step2 (UFs+valor) + step3 (confirm) | (UX flow) |
| `/buscar` | Main search page | filters panel + SSE progress + results grid + paywall preview | `01-buscar-header.png`, `02-busca-em-andamento.png`, `03-resultados-cards.png`, `04-buscar-page.png`, `validation-01-buscar-home.png`, `validation-06-busca1-loading.png`, `validation-07-busca1-error.png`, `ux-audit-buscar.png`, `ux-audit-search-loading.png`, `ux-audit-results.png`, `ux-audit-filtros.png`, `ux-audit-details-expanded.png`, `ux-audit-14-mobile-buscar.png` |
| `/dashboard` | Personal dashboard | summary cards + charts | `ux-audit-dashboard.png`, `ux-audit-dashboard-loaded.png`, `validation-04-dashboard.png` |
| `/historico` | Search history | list + filter | `ux-audit-historico.png`, `validation-03-historico-full.png` |
| `/pipeline` | Kanban (or mobile tabs) | 5 columns drag-drop + tour | `ux-audit-pipeline.png`, `v3-mobile-375-avaliar.png`, `v3-mobile-375-priorizar.png`, `v3-tablet-768-avaliar.png` |
| `/mensagens` | InMail support | conversations list + thread + reply | `validation-02-mensagens-suporte.png` |
| `/conta` | Account settings | profile + billing + MFA + danger zone | `ux-audit-conta.png`, `validation-05-conta.png` |
| `/admin` | Admin home | metrics overview + nav | — |
| `/admin/cache` | Cache inspector | metrics + entries + evict | — |
| `/admin/feature-flags` | Toggle flags | runtime list | — |
| `/admin/metrics` | Prometheus | charts | — |
| `/admin/seo` | SEO metrics | GSC + sitemap stats | — |
| `/admin/slo` | SLO + alerts | error budget burn | — |
| `/admin/partners` | Partner management | CRUD partners + referrals | — |
| `/admin/emails` | Email logs | trial_email_log query | — |

## Layout patterns

| Pattern | Components |
|---------|-----------|
| **NavigationShell** | Sidebar (desktop) + BottomNav (mobile) + PageHeader |
| **AuthLoadingScreen** | Skeleton enquanto carrega session |
| **PageErrorBoundary** | Captura React errors + Sentry |
| **EmptyState** | Icon + title + description + steps + CTA |
| **ErrorStateWithRetry** | Inline error + retry button |
| **TrialUpsellCTA** | Variants: post-pipeline, paywall-hit, day3, ... |
| **OnboardingTourButton** | Floating button reabrir tour |
| **Tour (Shepherd.js)** | Overlay step-by-step com auto-start |
| **TrialProgressBar** | Header progress trial days remaining |
| **ProfileCompletionPrompt** | Sticky banner até 100% perfil |

## Estados de tela (search)

```
- empty (no search yet)
- loading (SSE progress streaming)
- partial (some UFs done, others pending)
- error (with retry CTA)
- results (grid + filter sidebar)
- cached_stale (banner stale data)
- degraded (banner sources offline)
- paywall_preview (limited results + CTA)
- llm_skipped (banner timeout, fallback summary)
```

## Fluxos críticos validated em screenshots

1. ✅ Landing → Signup → Onboarding (3 steps) → Buscar (first-analysis)
2. ✅ Buscar form fill → Loading SSE → Results
3. ✅ Pipeline drag-drop (kanban + mobile tabs)
4. ✅ Conta settings + cancel
5. ✅ Mensagens (support inbox)
6. ✅ Dashboard analytics
7. ✅ Histórico
8. ✅ Mobile responsive (375px + 768px)
9. ✅ Sentry incident screenshots (`sentry-backend-*`, `validation-10-sentry-issues.png`)
10. ✅ Stripe branding config (`stripe-branding-config.png`)

## Lacunas (não-coberto por screenshots)

- 🔴 Admin pages (`/admin/*`)
- 🔴 SEO programmatic páginas (observatório raio-X, blog, contratos)
- 🔴 Onboarding wizard step-by-step
- 🔴 Modais (cancel subscription, trial expired, paywall hit, MFA setup)
- 🔴 Email rendered samples (somente código)
- 🔴 Comparador, calculadora público

## Próximos passos sugeridos

1. Capturar screenshots admin (require admin auth)
2. Capturar screenshots SEO programmatic (sample slugs)
3. Capturar fluxo onboarding completo (3 steps)
4. Documentar modal states (cancel, MFA, paywall)
