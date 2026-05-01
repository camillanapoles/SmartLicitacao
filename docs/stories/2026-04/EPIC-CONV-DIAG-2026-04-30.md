# EPIC-CONV-DIAG-2026-04-30: Diagnóstico de Conversão + CTR Multiplier

**Priority:** P0
**Owner:** @sm + @po
**Status:** Ready
**Sprint:** Conversion Diagnostics Sprint Q2 2026 (W1 imediato + W2-3 follow-up)
**Origem:** Sessão de diagnóstico 2026-04-30 com user — plan file `/home/tjsasakifln/.claude/plans/ainda-que-n-meros-p-fios-nested-mountain.md`

---

## Contexto

GSC 28 dias (2026-04-30): **126 clicks / 9.9k impressões / CTR 1.3% / pos média 7.1 / 2 signups / ZERO trials**.

Top 10 GSC mostra padrão crítico:
- 4 das top 10 URLs são `/contratos/orgao/[cnpj]` — **ZERO CTA signup** (confirmado via grep em `/mnt/d/pncp-poc/frontend/app/contratos/orgao/[cnpj]/page.tsx`, 292 linhas)
- `pncp-guia-completo-empresas` absorve 2867 impressões (29% do total) com CTR 0.2% — title/intent mismatch
- 6 das top 10 URLs são blog/programmatic SEM funil claro de conversão

Existem 5 hipóteses concorrentes para o zero-trial:
- **H1:** Bounce em programmatic pages (entram, vêem dado, saem — confirmado parcialmente: ZERO CTA)
- **H2:** Abandono no signup form (qual campo?)
- **H3:** Limbo email-confirmation (Supabase email não chega ou polling timeout)
- **H4:** Abandono no onboarding wizard 3-step
- **H5:** First-analysis dispatch falha silenciosamente (`onboarding/page.tsx:181-183` faz graceful fallback sem signal)

**Causa raiz só pode ser discriminada com instrumentação.** Memory `feedback_advisor_critical_discernment.md` aplica: discriminador empírico barato (<7d signal) antes de fix especulativo.

Memory `feedback_n2_below_noise_eng_theater.md` NÃO aplica aqui — não estamos automatizando trial→paid; estamos instrumentando para gerar signal pré-decisão.

**EPIC-CONVERSION-2026-04 (Done) tratou visibilidade backend→frontend. Este epic trata DIAGNÓSTICO + REMOÇÃO DE FUGA + CTR.**

---

## Stories deste Epic — Sprint W1 (P0, ~42pt, 7 stories)

| Story | Título | Eixo | Effort | Owner Exec | Status |
|-------|--------|------|--------|-----------|--------|
| [CONV-INST-001](CONV-INST-001-mixpanel-page-load-traffic-source.story.md) | Enrich `page_load` com traffic_source + landing flag | Instrumentação | 5pt | @dev | Ready |
| [CONV-INST-002](CONV-INST-002-mixpanel-signup-form-lifecycle.story.md) | Signup form lifecycle events (rendered, field_blur, field_error) | Instrumentação | 8pt | @dev | Ready |
| [CONV-INST-003](CONV-INST-003-email-confirmation-lifecycle.story.md) | Email-confirmation events + UI dead-end modal >5min | Instrumentação | 8pt | @dev | Ready |
| [CONV-INST-005](CONV-INST-005-clarity-trial-onboarding-tagging.story.md) | Clarity `trial_started` + step tagging + first-analysis events | Instrumentação | 5pt | @dev | Ready |
| [CONV-CTA-001](CONV-CTA-001-cta-trial-contratos-orgao.story.md) | Hero CTA trial em /contratos/orgao/[cnpj] | Remoção Fuga | 5pt | @dev | Ready |
| [CTR-OPT-001](CTR-OPT-001-rewrite-title-meta-top-blog.story.md) | Rewrite title/meta dos top-20 blog posts GSC | CTR | 8pt | @dev | Ready |
| [CTR-OPT-002](CTR-OPT-002-validar-faqpage-jsonld-prod.story.md) | Validar FAQPage JSON-LD rendering em prod | CTR | 3pt | @dev | Ready |

**Total W1: 42pt**

---

## Stories deste Epic — Sprint W2 (gated em signal de W1, ~45pt)

Listadas para visibilidade. Stories serão criadas após observação de 7-14d do signal de W1.

| Story (planned) | Título | Effort |
|---|---|---|
| CONV-INST-004 | E2E Playwright onboarding wizard 3-step + GTM-004 TTV SLA | 13pt |
| CONV-INST-006 | Mixpanel identityUser pré-auth no signup/page.tsx (distinct_id stitching) | 3pt |
| CONV-INST-007 | First-analysis error capture (Sentry + Clarity) substituindo silent catch | 5pt |
| CONV-INST-008 | Mixpanel `trial_activation_success` (distinto de Stripe `trial_started`) | 3pt |
| CONV-CTA-002 | Audit programmatic templates `/cnpj/`, `/orgaos/`, `/municipios/`, `/observatorio/` | 8pt |
| CTR-OPT-003 | Cluster viral B2G #1: "Top 50 órgãos que mais gastaram em [setor] 2026" | 13pt |

---

## KPIs e Discriminador Empírico

| Métrica | Baseline 2026-04-30 | Target 30d pós-W1 | Target 60d pós-W2 |
|---------|---|---|---|
| Signups | 2/30d | 5+ | 15+ |
| Trials iniciados | 0/30d | ≥1 (qualquer = win) | 5+ |
| GSC clicks 28d | 126 | 200+ | 400+ |
| GSC CTR | 1.3% | 2.0% | 3.5% |
| pncp-guia-completo CTR | 0.2% | 1.5% (lift 7x) | 3% (lift 15x) |
| Mixpanel funnel coverage | 84% (36ev) | 100% (50+ev) | 100% |
| Bounce em /contratos/orgao | desconhecido | medido (Clarity) | <60% |

**Discriminador pós W1 (7d signal):**
- Top abandono = signup form → H2 confirmada → priorizar UX form
- Top abandono = email-confirm → H3 → fix Supabase email + UI dead-end
- Top abandono = onboarding step 1/2/3 → H4 → simplificar wizard
- Top abandono = first-analysis fail → H5 → backend resiliência
- Top abandono = bounce programmatic → H1 → CONV-CTA-002 expand

---

## Dependências e Riscos

**Dependências:**
- Mixpanel já integrado (`useAnalytics.ts`, `AnalyticsProvider.tsx:36-167`) — REUSE
- Clarity já integrado (`ClarityAnalytics.tsx`, `useClarity.ts`) — REUSE
- `captureUTMParams()` já existe em `useAnalytics.ts:36` — REUSE
- LGPD consent gate funciona — REUSE
- Memory `reference_mixpanel_backend_token_gap_2026_04_24.md`: backend token JÁ corrigido (PR #536)
- Memory `reference_ms_clarity_instrumentation.md`: project ID `voop54cv1p` ativo

**Riscos catalogados:**
1. Memory `feedback_build_hammers_backend_cascade.md` — qualquer fetch SSR em programmatic deve usar `AbortSignal.timeout(10000)` (já presente em `contratos/orgao/[cnpj]/page.tsx:55`)
2. Memory `feedback_isr_fetch_cache_alignment_next16.md` — manter `next: { revalidate: N }` alinhado com `export const revalidate = N`
3. Memory `feedback_sen_fe_001_recidiva_sitemap.md` — após cada fix, grep global pelos antipatterns
4. Memory `feedback_frontend_sentry_silent_buildtime.md` — Sentry frontend silent suspect; CONV-INST-007 (W2) cobre

**Não-Goals:**
- Outreach off-page (descartado — memory `project_smartlic_onpage_pivot_2026_04_26.md`)
- Trial→paid lifecycle automation (n=2 abaixo noise floor)
- Refazer pricing/billing flow
- Backend perf tuning (epic separado)

---

## Change Log

| Data | Agente | Mudança |
|------|--------|---------|
| 2026-04-30 | @sm | Epic criado a partir de plan diagnóstico user-aprovado (3 Explore agents + GSC top-10 review + grep confirmation em /contratos/orgao) |
| 2026-04-30 | @po | Validação completa dos 7 drafts W1 — todos GO (8-10/10) — Status Draft → Ready em todos. Sprint W1 desbloqueado para @dev. CodeRabbit N/A (disabled em core-config.yaml). |
