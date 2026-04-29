# User Stories (extraídas) — SmartLic

> Geradas pelo **Reversa Writer** em 2026-04-27 a partir do código + git history + ADRs
> Confiança: 🟢 CONFIRMADO (extraídas do código) · 🟡 INFERIDO (deduzido de UI/comportamento)

---

## Persona — Empresa B2G CEO/Sócio

### US-001 — Descobrir oportunidades de licitação 🟢

**Como** dono de empresa B2G  
**Quero** encontrar editais de licitação relevantes para meu setor e região  
**Para que** eu não perca prazos e identifique oportunidades viáveis para minha empresa.

**Aceitação:**
- Configuro filtros: setor, UFs, faixa de valor, modalidades, esferas, datas
- Recebo resultados consolidados de PNCP + PCP + ComprasGov sem duplicatas
- Vejo classificação de relevância por keyword + LLM
- Vejo viability score 4-fator (HIGH/MEDIUM/LOW)
- Recebo resumo executivo IA dos top oportunidades
- Posso baixar Excel com 11 colunas formatadas
- Tempo total <80s p95

**Mapeamento código:** `routes/search/`, `search_pipeline.py`, módulos `search`, `filter-llm-viability`, `ingestion-datalake`

### US-002 — Acompanhar pipeline de oportunidades (kanban) 🟢

**Como** vendedor B2G  
**Quero** organizar oportunidades em colunas (descoberta, análise, preparando, enviada, resultado)  
**Para que** eu acompanhe progresso visual e não perca prazo de submission.

**Aceitação:**
- Adiciono edital ao pipeline com 1 clique a partir do resultado
- Drago entre stages livremente
- Vejo cards com border vermelha quando data_encerramento < 7d
- Notes editable por card
- Trial = cap 5 itens (banner + modal upsell)
- Pago = pipeline ilimitado
- Trial expired = read-only mode (incentivo conversão)
- Mobile: tabs em vez de drag

**Mapeamento código:** `routes/pipeline.py`, `frontend/app/pipeline/`, módulo `pipeline-kanban`

### US-003 — Receber alertas diários de novas oportunidades 🟢

**Como** sócio ocupado  
**Quero** receber email diário com novos editais matching meus filtros  
**Para que** eu não precise abrir a plataforma para descobrir oportunidades novas.

**Aceitação:**
- Configuro alerts por setor + UF + valor mínimo
- Recebo email diário com top N novos editais
- Posso unsubscribe individual via link no email
- Posso ver histórico de alertas enviados
- Posso ver preview do alert antes de submit

**Mapeamento código:** `routes/alerts.py`, `jobs/cron/notifications.py::run_search_alerts`, templates/emails/alert_digest.py

### US-004 — Exportar oportunidades para Excel/Google Sheets/PDF 🟢

**Como** consultor que prepara propostas para múltiplos clientes  
**Quero** exportar resultados de busca em Excel ou Sheets  
**Para que** eu possa compartilhar com colegas e analisar offline.

**Aceitação:**
- Excel xlsx com header verde, 11 colunas, totals SUM, meta sheet
- Google Sheets (paid) preserva share links em update
- PDF 1-page por edital (com watermark trial)
- Filename safe: `SmartLic_TITULO_YYYY-MM-DD.{xlsx,pdf}`
- Trial: Excel preview limitado + watermark PDF; Pago: full

**Mapeamento código:** `excel.py`, `google_sheets.py`, `pdf_generator_edital.py`, módulo `exports`

### US-005 — Trial 14 dias sem cartão 🟢

**Como** novo usuário interessado  
**Quero** experimentar a plataforma sem cadastrar cartão  
**Para que** eu valide ROI antes de pagar.

**Aceitação:**
- Signup só email + senha (telefone opcional via WhatsApp consent)
- 14 dias com quota limitada (5 buscas/mês trial)
- Pipeline cap 5 itens
- Email sequence: Day 0 welcome, Day 3 engagement, Day 7 paywall alert, Day 10 valor acumulado, Day 13 último dia, Day 16 expired
- Pós-expired: read-only mode + cupom 20% off (Day 16 email)
- Sem cobrança automática

**Mapeamento código:** `services/billing.py`, `routes/auth_signup.py`, `templates/emails/trial.py`, `jobs/cron/notifications.py::_trial_sequence_loop`, módulo `billing-quota`

### US-006 — Onboarding wizard 3-step + first-analysis automática 🟢

**Como** novo usuário pós-signup  
**Quero** ser guiado em 3 passos para configurar perfil  
**Para que** eu obtenha valor imediato (time-to-first-value <5min) sem aprender plataforma.

**Aceitação:**
- Step 1: CNAE + objetivo principal
- Step 2: UFs + faixa de valor + porte + experiência licitações
- Step 3: confirmação e dispatch first-analysis automática
- CNAE → setor mapping automático
- BuscaRequest construído com defaults inteligentes (10d window, status=RECEBENDO_PROPOSTA)
- Tour Shepherd.js auto-start em /buscar com primeiro resultado
- Telemetry tour_event eventos completos/skipped

**Mapeamento código:** `frontend/app/onboarding/page.tsx`, `routes/onboarding.py`, `utils/cnae_mapping.py`, módulo `onboarding+analytics`

### US-007 — Dashboard pessoal com métricas 🟢

**Como** usuário ativo  
**Quero** ver dashboard com minhas métricas (buscas, oportunidades, valor, ROI)  
**Para que** eu valide o valor da plataforma e veja progresso.

**Aceitação:**
- Total buscas + downloads + oportunidades + valor descoberto
- Estimated hours saved (2.5h × buscas)
- Avg results per search
- Success rate (state=COMPLETED %)
- Member since date
- Top UFs + Top sectors (DimensionItem)
- Searches over time series
- New opportunities since last search

**Mapeamento código:** `routes/analytics.py`, módulo `onboarding+analytics`

### US-008 — Mensagens com suporte (InMail) 🟢

**Como** usuário com dúvida  
**Quero** abrir conversation com SmartLic support sem sair da plataforma  
**Para que** receba ajuda contextualizada.

**Aceitação:**
- Subject + categoria + mensagem inicial
- Status: open → awaiting_support → awaiting_user → closed
- Re-open quando user posta nova mensagem em closed
- Unread count badge no header
- SLA tracking admin

**Mapeamento código:** `routes/messages.py`, módulo `messages+feedback`

### US-009 — Feedback de classificação 🟢

**Como** usuário que vê resultado errado  
**Quero** marcar bid como correct / false_positive / false_negative  
**Para que** SmartLic melhore precisão para meu setor.

**Aceitação:**
- Botão thumbs up/down no card de resultado
- Razão livre (max 500 chars)
- Categoria FP (modalidade errada, valor fora faixa, geografia, escopo, ...)
- Rate limit ≤ N feedbacks/h por user
- Upsert: editar feedback existente
- LGPD: posso deletar próprio feedback (`DELETE /v1/feedback/{id}`)

**Mapeamento código:** `routes/feedback.py`, `feedback_analyzer.py`, módulo `messages+feedback`

### US-010 — Compartilhar análise via link 🟡

**Como** consultor  
**Quero** gerar link público para compartilhar análise específica com cliente  
**Para que** ele veja resultado sem precisar criar conta.

**Aceitação:**
- POST /v1/share/analise gera hash UUID
- GET /v1/share/analise/{hash} público (sem auth)
- Capability `allow_share_analise` (paid only)
- Link expira após N dias?

**Mapeamento código:** `routes/share.py`, `frontend/app/share/`

### US-011 — Profile completeness + perfil contextual 🟢

**Como** usuário onboarded  
**Quero** completar perfil progressivamente (porte, experiência, regiões)  
**Para que** classificação LLM seja melhor calibrada.

**Aceitação:**
- Badge progresso de completeness
- Campos profile.context_jsonb: cnae, ufs_atuacao, faixa_valor, porte_empresa, experiencia_licitacoes, setores_de_interesse, tipos_de_servico
- Affecta LLM prompt (`user_profile` em SearchContext)
- ProfileCompletionPrompt component reaparece até 100%

**Mapeamento código:** `routes/user.py`, `frontend/components/ProfileCompletionPrompt.tsx`, módulo `routes`

---

## Persona — Consultoria/Assessoria de Licitação

### US-012 — Multi-tenancy organizations 🟡

**Como** sócio de consultoria  
**Quero** convidar membros para organização compartilhada  
**Para que** equipe veja mesmo pipeline + analyses.

**Aceitação:**
- Criar org (`POST /v1/organizations`)
- Invite por email (`POST /v1/organizations/{id}/invite`)
- Member accept (`POST /v1/organizations/{id}/accept`)
- Roles: owner | member | viewer (🔴 RBAC granular precisa validation)
- Dashboard org consolidado
- Logo customizável

**Mapeamento código:** `routes/organizations.py`, `frontend/app/organizations/?` (incompleto)

### US-013 — Plano Consultoria multi-seat 🟡

**Como** consultoria  
**Quero** comprar plano R$997/mês (anual R$797) com seats múltiplos  
**Para que** equipe inteira tenha acesso.

**Aceitação:**
- Plan `smartlic_consultoria` com `allow_organizations=true`
- Seats configuráveis (5? 10? 🔴 não confirmed)
- Billing único, RH-style

**Mapeamento código:** `services/billing.py` (plan defs), módulo `billing-quota`

---

## Persona — Admin SmartLic CONFENGE

### US-014 — Gerenciar usuários (CRUD) 🟢

**Aceitação:**
- List paginado com search sanitized
- Create user (email + password + plan)
- Update (name, email, phone, plan, is_admin)
- Delete (LGPD)
- Reset password (gera temp + envia email)
- Assign plan atomic
- Update credits (quota override)

**Mapeamento código:** `admin.py:256-644`

### US-015 — Inspecionar e evictar cache 🟢

**Aceitação:**
- Cache metrics dashboard (hits/misses por level)
- Inspect single entry por params_hash
- Evict single
- Nuke all (CB-protected, requires confirm)

**Mapeamento código:** `admin.py:677-797` + `cache/admin.py`

### US-016 — Reconciliation Stripe ↔ DB 🟢

**Aceitação:**
- History last N reconciliation runs
- Manual trigger via POST
- Auto cron daily

**Mapeamento código:** `admin.py:798-856`, `jobs/cron/billing.py::run_reconciliation`

### US-017 — Trial metrics + at-risk trials 🟢

**Aceitação:**
- Funnel: active / expired / converted / churned
- At-risk trials por risk score
- SLA support response

**Mapeamento código:** `admin.py:857-1132`, `jobs/cron/trial_risk_detection.py`

### US-018 — Feature flags runtime 🟢

**Aceitação:**
- List all flags
- Toggle individual sem restart
- Reload signal

**Mapeamento código:** `routes/feature_flags.py`

### US-019 — Search trace (debugging) 🟢

**Aceitação:**
- Full OTel span trace por search_id
- Estado transitions timeline
- Reset CB per source

**Mapeamento código:** `routes/admin_trace.py`

### US-020 — Trigger ingestion backfills + clear checkpoints 🟢

**Aceitação:**
- POST trigger contracts/bids backfill (admin)
- Clear checkpoints (re-crawl from scratch)

**Mapeamento código:** `routes/admin_cron.py`

### US-021 — LLM cost dashboard 🟢

**Aceitação:**
- Cost por modelo + source nas últimas N dias
- Total + breakdown classification vs summary

**Mapeamento código:** `routes/admin_llm_cost.py`

### US-022 — SLO dashboard 🟢

**Aceitação:**
- Error budget burn rate
- Active alerts

**Mapeamento código:** `routes/slo.py`

### US-023 — SEO metrics 🟢

**Aceitação:**
- GSC integration
- Sitemap stats

**Mapeamento código:** `routes/seo_admin.py`

---

## Persona — Googlebot / Visitor anônimo

### US-024 — Conteúdo SEO programático (~3k+ pages) 🟢

**Como** Googlebot crawler  
**Quero** indexar páginas dinâmicas de licitações por setor/UF/cidade/órgão/CNPJ  
**Para que** SmartLic apareça em busca orgânica.

**Aceitação:**
- ISR Next.js `revalidate=3600` (1h)
- Sitemaps dinâmicos (4 sub-sitemaps + index)
- JSON-LD FAQPage / Organization / ItemList
- Schema.org structured data
- Canonical URLs
- Mobile-first (responsive)
- TTFB <1s p95

**Mapeamento código:** `frontend/app/{observatorio,cnpj,fornecedores,orgaos,municipios,licitacoes,contratos,blog/*,alertas-publicos,indice-municipal,calculadora,comparador,compliance}/`, módulo `observatory+seo-programmatic`

### US-025 — Calculadora pública de viabilidade 🟢

**Aceitação:**
- Acessível sem auth (`/calculadora`)
- Embed iframe-friendly
- Resultado: viability_level + score + breakdown

**Mapeamento código:** `routes/calculadora.py`, `frontend/app/calculadora/embed/page.tsx`

### US-026 — Comparador de editais 🟢

**Aceitação:**
- Side-by-side editais
- Filter por setor

**Mapeamento código:** `routes/comparador.py`, `frontend/app/comparador/`

### US-027 — Lead capture forms 🟢

**Aceitação:**
- Forms em landing pages capturam lead
- Sem signup obrigatório
- Webhook trigger nurture sequence

**Mapeamento código:** `routes/lead_capture.py`

---

## Internal / Operational stories

### US-028 — Health canary PNCP breaking change 🟢

**Como** SRE on-call  
**Quero** ser alertado se PNCP API mudar shape ou max page size  
**Para que** eu fix imediato antes de impact em production.

**Aceitação:**
- Cron 10min probe `tamanhoPagina=51` (deve falhar)
- Cron 10min probe `tamanhoPagina=50` (deve OK)
- Cron 10min validate JSON Schema
- Sentry FATAL events com dedup 6h por reason

**Mapeamento código:** `jobs/cron/pncp_canary.py`, `backend/contracts/schemas/pncp_search_response.schema.json`

### US-029 — pg_cron health monitor 🟢

**Aceitação:**
- ARQ cron hourly verifica `cron.job_run_details`
- Sentry alert se job >25h sem rodar
- Endpoint `/v1/admin/cron-status` retorna snapshot

**Mapeamento código:** `jobs/cron/cron_monitor.py`

### US-030 — Incident response (graceful degradation) 🟢

**Aceitação:**
- Circuit breakers per source (15 fails / 60s cooldown)
- Backend wedge → InMemoryCache LRU fallback
- Negative cache em DB failure (PR #529 hotfix)
- Time budget waterfall protection

**Mapeamento código:** `pncp_client.py`, `redis_pool.InMemoryCache`, `pipeline/budget.py`, código de routes SEO

---

## Lacunas identificadas

- 🔴 **Founding plan** — pricing, deadline, cap not clear
- 🔴 **Partner program** — commission %, payout cycle, attribution
- 🔴 **Multi-tenant org_role** — owner/member/viewer enforcement em endpoints
- 🔴 **MFA enforcement policy** — quando obrigatório? trigger?
- 🔴 **HMAC verify Resend webhook** — gap aberto (memory)
- 🔴 **Estimated hours saved 2.5h** — base empírica?
- 🔴 **15 vs 20 setores** — inconsistência docs
