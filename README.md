# SmartLic — Plataforma de Inteligência em Licitações Públicas

[![Backend Tests](https://github.com/tjsasakifln/PNCP-poc/actions/workflows/backend-tests.yml/badge.svg)](https://github.com/tjsasakifln/PNCP-poc/actions/workflows/backend-tests.yml)
[![Frontend Tests](https://github.com/tjsasakifln/PNCP-poc/actions/workflows/frontend-tests.yml/badge.svg)](https://github.com/tjsasakifln/PNCP-poc/actions/workflows/frontend-tests.yml)
[![CodeQL](https://github.com/tjsasakifln/PNCP-poc/actions/workflows/codeql.yml/badge.svg)](https://github.com/tjsasakifln/PNCP-poc/actions/workflows/codeql.yml)

> Automação de procurement público com IA · API PNCP · ComprasGov · Classificação setorial GPT-4.1-nano · B2G SaaS · Govtech Brasil

> **SOFTWARE PROPRIETÁRIO** — © 2024-2026 CONFENGE AVALIAÇÕES E INTELIGÊNCIA ARTIFICIAL LTDA. Todos os direitos reservados.
> Contato: tiago.sasaki@confenge.com.br | WhatsApp: +55 (48) 9 8834-4559

---

🇧🇷 [Português](#português) · 🇺🇸 [English](#english)

---

## Português

**SmartLic** é uma plataforma em produção de inteligência em licitações públicas que automatiza a descoberta, análise e qualificação de oportunidades em contratos públicos para empresas B2G (Business-to-Government). Produto da **CONFENGE Avaliações e Inteligência Artificial LTDA**.

Conecta-se às principais fontes oficiais do governo brasileiro — **PNCP (Portal Nacional de Contratações Públicas)**, **ComprasGov** e **Portal de Compras Públicas** — e aplica IA para classificar editais por setor econômico, avaliar viabilidade e entregar inteligência comercial acionável.

**Produção:** https://smartlic.tech | **Versão:** v0.5 (beta com trials pagos) | **Backend:** 187 endpoints · 65 módulos | **Frontend:** 25 páginas + 10 mil+ páginas SEO programático

---

### Para Quem É

SmartLic foi construído para qualquer organização que precise monitorar, analisar ou operar no ecossistema de compras governamentais brasileiro:

#### Empresas que vendem para o governo (B2G)
Automatize a prospecção de editais relevantes por setor (saúde, TI, engenharia, limpeza, vigilância, alimentos, vestuário etc.), elimine a triagem manual do PNCP e concentre esforço nas oportunidades com maior viabilidade de participação.

#### Consultorias e assessorias de licitação
Gerencie múltiplos clientes e setores em um único painel. Use o pipeline Kanban para acompanhar o ciclo de vida de cada edital — da descoberta à proposta. Exporte relatórios Excel e resumos executivos gerados por IA para entregar mais valor aos clientes.

#### Escritórios de advocacia especializados em licitações
Monitore editais, prazos de habilitação, modalidades (pregão eletrônico, dispensa eletrônica, concorrência, RDC, credenciamento sob Lei 14.133/2021) e histórico de contratos por órgão ou CNPJ.

#### Plataformas de busca de editais e marketplaces B2G
Integre via API os dados consolidados de PNCP + ComprasGov + PCP v2 — 1,5 milhão de editais indexados com deduplicação, classificação setorial e avaliação de viabilidade já processados. Evite construir e manter crawlers próprios.

#### SaaS de procurement público e ERPs para prefeituras e órgãos públicos
Incorpore inteligência de mercado de fornecedores: histórico de contratos (~2 milhões de registros), preços praticados, fornecedores vencedores por órgão e por categoria. Enriqueça fluxos de compra com dados do DataLake SmartLic.

#### Softwares de gestão de contratos públicos
Use a API de contratos históricos para alimentar análises de preço de referência, benchmarking de fornecedores e detecção de anomalias em licitações.

#### Empresas de inteligência comercial e enriquecimento de dados
Acesse o DataLake de editais (400 dias) e contratos (~2 milhões de linhas) para gerar insights setoriais, mapear market share de fornecedores públicos, identificar padrões de compra por órgão, UF e CNAE.

#### Govtechs e civic-techs
Construa sobre uma infraestrutura de dados públicos já operacional: ingestão ETL diária, full-text search em PostgreSQL, 183 migrações versionadas, API pública de observatório municipal e setorial.

#### Portais de transparência, observatórios e órgãos de controle
Use os endpoints públicos de observatório (`/observatorio`, `/indice-municipal`, `/cnpj`, `/compliance`) para construir painéis de transparência, monitoramento de fornecedores, índices de risco e alertas de padrão anormal em contratos públicos. Compatível com uso por Tribunais de Contas, Controladorias e Ministérios Públicos.

#### Fintechs que financiam fornecedores públicos e seguradoras de seguro-garantia
Acesse o histórico de contratos por CNPJ para avaliação de risco de crédito, análise de capacidade operacional e verificação de regularidade fiscal de fornecedores públicos.

#### Empresas de compliance e due diligence
Pesquise histórico de licitações e contratos por CNPJ, órgão contratante e setor. Identifique padrões de concentração de contratos, sobrepreço e fornecedores com histórico de impedimentos.

#### Venture studios de govtech, aceleradoras e investidores B2G
Código-fonte completo de uma plataforma B2G em produção: DataLake com 3,5M+ registros, classificação por IA, billing Stripe, 5.131+ testes automatizados, arquitetura Railway + Supabase + Redis. Referência arquitetural para startups de govtech no Brasil.

#### Founders estrangeiros querendo entrar no mercado B2G brasileiro
Stack documentada, fontes de dados mapeadas (PNCP, ComprasGov, Lei 14.133/2021), lógica de negócio exposta — um mapa do ecossistema de procurement público brasileiro.

#### Plataformas de BI, RPA e automação (n8n, Make, Zapier)
Consuma a API REST para alimentar dashboards de Power BI, Tableau ou Metabase com dados de licitações. Use webhooks e endpoints SSE para disparar automações no n8n, Make ou Zapier quando novos editais relevantes forem publicados.

#### Associações comerciais, sindicatos empresariais e entidades como SEBRAE
Monitore oportunidades de compras governamentais para associados por setor e região. Exporte relatórios periódicos com editais classificados, valores estimados e análise de viabilidade.

#### Startups de IA aplicada a operações, consultorias de transformação digital e empresas de RPA
Referência de implementação de pipeline RAG-free com classificação setorial por LLM (GPT-4.1-nano), zero-shot classification, circuit breakers, SWR cache, SSE em tempo real e worker ARQ para jobs assíncronos — tudo em produção.

---

### Funcionalidades Principais

| Funcionalidade | Descrição |
|----------------|-----------|
| **Busca multi-fonte** | PNCP + PCP v2 + ComprasGov v3 agregados com deduplicação por prioridade de fonte |
| **DataLake próprio** | ~1,5M editais (`pncp_raw_bids`, 400d) + ~2M contratos (`pncp_supplier_contracts`); full-text search PostgreSQL <100ms p95 |
| **20 setores** | Classificação por keyword density + GPT-4.1-nano arbiter + zero-match (precisão ≥85%, recall ≥70%) |
| **Viabilidade** | Score automático: modalidade (30%), prazo (25%), valor (25%), geografia (20%) |
| **Pipeline Kanban** | Drag-and-drop para gestão de ciclo de vida de editais |
| **Relatórios** | Excel estilizado + resumo executivo IA + exportação Google Sheets |
| **SEO programático** | 10k+ páginas ISR: observatório setorial, CNPJ, órgãos, municípios, alertas, índice municipal |
| **API pública** | Endpoints de observatório, contratos, licitações por setor/UF/órgão — dados abertos sem autenticação |
| **Billing Stripe** | Pro R$ 397/mês · semestral R$ 357/mês · anual R$ 297/mês · Consultoria R$ 997/mês · Trial 14 dias |
| **Observabilidade** | Prometheus + OpenTelemetry + Sentry · canário PNCP · monitoramento pg_cron |

---

### Casos de Uso

#### Triagem automática de editais por setor
Empresa de TI cadastra setor "Tecnologia da Informação" e UFs de interesse. SmartLic monitora o PNCP diariamente, classifica editais por IA e envia alertas apenas para oportunidades relevantes — eliminando horas de triagem manual.

#### Inteligência de preço para fornecedores
Consultoria de licitação consulta histórico de contratos por CNPJ de órgão (`/contratos/orgao/{cnpj}`) para estimar preço de referência antes de elaborar proposta, usando os ~2 milhões de contratos históricos do DataLake.

#### Monitoramento de fornecedores concorrentes
Empresa mapeia contratos ganhos por concorrentes via CNPJ (`/cnpj/{cnpj}`, `/fornecedores/{cnpj}`), identificando em quais órgãos, setores e UFs estão ativos.

#### Dashboard de transparência municipal
Prefeitura ou observatório cívico embute o endpoint `/indice-municipal/{municipio-uf}` em portal próprio para exibir índice de saúde das contratações locais.

#### Automação n8n/Make/Zapier
Webhook SmartLic dispara flow no n8n quando novo edital de interesse é publicado — notificando equipe no Slack, criando card no CRM e agendando reunião de go/no-go automaticamente.

#### Due diligence de fornecedor
Fintech ou seguradora consulta `/compliance/{cnpj}` para verificar histórico de contratos, regularidade e padrões de risco antes de conceder crédito ou emitir seguro-garantia.

---

### Integrações e Ecossistema

SmartLic expõe API REST + SSE (Server-Sent Events) consumível por qualquer stack:

| Ferramenta | Tipo de integração |
|------------|-------------------|
| **n8n / Make / Zapier** | Webhook em novos editais · trigger por setor/UF · notificações automáticas |
| **Power BI / Tableau / Metabase** | Endpoints REST de contratos, licitações e índices para dashboards de BI |
| **Google Sheets** | Exportação direta via OAuth integrado ao SmartLic |
| **CRMs (HubSpot, Pipedrive, etc.)** | API de oportunidades qualificadas para enriquecer pipeline comercial |
| **ERP / sistemas de gestão** | API de contratos históricos e editais ativos para enriquecimento de dados |
| **Python / Node.js / qualquer cliente HTTP** | API REST documentada via Swagger em `/docs` |

---

### Fontes de Dados Oficiais

| Fonte | Base Legal | Endpoint |
|-------|-----------|----------|
| **PNCP** (Portal Nacional de Contratações Públicas) | Lei 14.133/2021 | `pncp.gov.br/api/consulta/v1` |
| **ComprasGov** (SIASG/CATMAT/CATSER) | Decreto 7.892/2013 | `dadosabertos.compras.gov.br` |
| **Portal de Compras Públicas (PCP v2)** | Público | `compras.api.portaldecompraspublicas.com.br/v2` |

---

### Stack Tecnológica

| Camada | Tecnologias |
|--------|-------------|
| **Backend** | FastAPI 0.136 · Python 3.12 · Pydantic 2.12 · httpx · OpenAI SDK 1.109 |
| **IA / LLM** | GPT-4.1-nano (classificação setorial + resumos executivos) |
| **Filas** | ARQ 0.26+ · Redis (cache · circuit breaker · SSE · rate limiter · locks distribuídos) |
| **Banco de dados** | Supabase Cloud (PostgreSQL 17 + Auth + RLS) · 183 migrações · 48 tabelas · 13+ RPCs |
| **Frontend** | Next.js 16.1 · React 18.3 · TypeScript 5.9 · Tailwind CSS 3.4 · Framer Motion · @dnd-kit |
| **Billing** | Stripe 11.4 (12 eventos webhook) · Resend (e-mail transacional) |
| **Infra** | Railway (web + worker + frontend) · Supabase Cloud · Redis · GitHub Actions |
| **Observabilidade** | Prometheus · OpenTelemetry · Sentry · Mixpanel |

---

### Arquitetura de Dados (3 camadas)

```
Camada 1 — Ingestão ETL (cron ARQ)
  pncp_raw_bids (~1,5M linhas, retenção 400 dias)  ←  rastreador diário (2h BRT)
  pncp_supplier_contracts (~2M linhas)              ←  rastreador 3×/semana

Camada 2 — Pipeline de Busca (consulta DataLake local)
  search_datalake RPC → PostgreSQL full-text → <100ms p95
  fallback: busca ao vivo nas 3 APIs quando DataLake retorna 0 resultados

Camada 3 — Cache de Resultados (passivo, por requisição)
  L1: InMemoryCache LRU (4h TTL)
  L2: Supabase search_results_cache (24h) + SWR reativo
```

---

### Arquitetura Geral

```
┌──────────────────┐
│   Next.js 16.1   │  25 páginas core + 10k+ páginas SEO programático (ISR)
└────────┬─────────┘
         │ API Proxy
┌────────▼─────────┐
│  FastAPI 0.136   │  187 endpoints · 65 módulos
└────────┬─────────┘
         │
         ├──► PNCP API           (ingestão diária + fallback live)
         ├──► PCP v2 API         (fallback live)
         ├──► ComprasGov v3      (fallback live)
         ├──► OpenAI API         (classificação setorial + resumos IA)
         ├──► Stripe API         (billing + webhooks)
         ├──► Supabase           (PostgreSQL 17 + Auth + RLS)
         ├──► Redis              (cache + ARQ jobs + locks distribuídos)
         └──► Resend             (e-mail transacional)
```

---

### Instalação Local

#### Pré-requisitos

- Python 3.12+
- Node.js 18+
- Supabase project (URL + chaves)
- Redis (opcional — há fallback)
- OpenAI API key

#### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
# Swagger disponível em http://localhost:8000/docs
```

#### Frontend

```bash
cd frontend
npm install
npm run dev
# Aplicação em http://localhost:3000
```

#### Variáveis de Ambiente

```bash
cp .env.example .env
# Preencha OPENAI_API_KEY, SUPABASE_URL, SUPABASE_ANON_KEY,
# SUPABASE_SERVICE_ROLE_KEY, STRIPE_SECRET_KEY, REDIS_URL, etc.
```

Veja [.env.example](.env.example) para a lista completa de 70+ variáveis documentadas.

---

### Testes

```bash
# Backend (454 arquivos, 5.131+ aprovados)
cd backend
pytest --timeout=30

# Frontend (376 arquivos, 2.681+ aprovados)
cd frontend
npm test

# E2E Playwright (60 fluxos críticos de usuário)
cd frontend
npm run test:e2e
```

---

### Deploy em Produção

| Componente | Plataforma |
|------------|-----------|
| Frontend | Railway (`RAILWAY_SERVICE_ROOT_DIRECTORY=frontend`) |
| Backend API | Railway web process (`PROCESS_TYPE=web`, Uvicorn multi-worker) |
| Worker ARQ | Railway worker process (`PROCESS_TYPE=worker`) |
| Banco de dados | Supabase Cloud (PostgreSQL 17 + Auth + RLS) |
| Cache | Redis (Upstash ou Railway addon) |
| CI/CD | GitHub Actions — testes + API types check + migration gate |

Push para `main` dispara deploy automático via Railway watch patterns.

---

### Documentação

- [PRD Técnico](./PRD.md) — Especificação completa do produto
- [Roadmap](./ROADMAP.md) — Status e backlog
- [CHANGELOG](./CHANGELOG.md) — Histórico de versões
- [Resumo de Resiliência GTM](./docs/summaries/gtm-resilience-summary.md)
- [Resumo de Correções GTM](./docs/summaries/gtm-fixes-summary.md)

---

### Parcerias e Licenciamento

Software proprietário. Contribuições externas não são aceitas sem autorização prévia por escrito da CONFENGE.

Para propostas de **parceria, integração, licenciamento de dados ou white-label**:
- **Email:** tiago.sasaki@confenge.com.br
- **WhatsApp:** +55 (48) 9 8834-4559

---

---

## English

**SmartLic** is a production-grade public procurement intelligence platform that automates the discovery, analysis, and qualification of government contracting opportunities for B2G (Business-to-Government) organizations. Built by **CONFENGE Avaliações e Inteligência Artificial LTDA** in Brazil.

Connects to Brazil's official procurement sources — **PNCP (National Public Procurement Portal)**, **ComprasGov**, and **Portal de Compras Públicas** — and applies AI to classify bids by economic sector, assess viability, and deliver actionable commercial intelligence.

**Production:** https://smartlic.tech | **Version:** v0.5 (beta with paid trials) | **Backend:** 187 endpoints · 65 modules | **Frontend:** 25 pages + 10k+ programmatic SEO pages

---

### Who Is It For

SmartLic is built for any organization that needs to monitor, analyze, or operate within Brazil's government procurement ecosystem:

#### B2G companies (businesses selling to government)
Automate bid discovery by sector (healthcare, IT, engineering, cleaning, security, food, apparel, etc.), eliminate manual PNCP screening, and focus effort on opportunities with the highest participation viability.

#### Procurement consulting firms and bid advisors
Manage multiple clients and sectors in one dashboard. Use the Kanban pipeline to track each bid's lifecycle. Export AI-generated Excel reports and executive summaries for client delivery.

#### Law firms specializing in public procurement
Monitor bids, qualification deadlines, procurement modalities (electronic bidding, direct award, concorrência, RDC, credenciamento under Lei 14.133/2021), and contract history by agency or CNPJ.

#### Bid search platforms and B2G marketplaces
Integrate via API the consolidated data from PNCP + ComprasGov + PCP v2 — 1.5M indexed bids with deduplication, sector classification, and viability scoring already processed. Avoid building and maintaining your own crawlers.

#### Public procurement SaaS and ERP vendors for municipalities and public agencies
Embed supplier market intelligence: contract history (~2M records), historical prices, winning suppliers per agency and category. Enrich procurement workflows with SmartLic DataLake data.

#### Public contract management software
Use the historical contracts API to power reference price analysis, supplier benchmarking, and procurement anomaly detection.

#### Commercial intelligence and data enrichment companies
Access the bid DataLake (400-day window) and contracts (~2M rows) to generate sector insights, map public supplier market share, and identify purchasing patterns by agency, state (UF), and CNAE industry code.

#### Govtechs and civic-techs
Build on top of an already operational public data infrastructure: daily ETL ingestion, PostgreSQL full-text search, 183 versioned migrations, and a public observatory API for municipal and sector-level data.

#### Transparency portals, observatories, and oversight bodies
Use public endpoints (`/observatorio`, `/indice-municipal`, `/cnpj`, `/compliance`) to build transparency dashboards, supplier monitoring tools, risk indices, and contract anomaly alerts. Suitable for Courts of Audit (Tribunais de Contas), Internal Control Bodies (Controladorias), and Public Ministries.

#### Fintechs financing public suppliers and surety bond insurers
Access contract history by CNPJ for credit risk assessment, operational capacity analysis, and supplier compliance verification before granting credit or issuing surety bonds.

#### Compliance and due diligence companies
Search procurement and contract history by CNPJ, contracting agency, and sector. Identify contract concentration patterns, price overruns, and suppliers with suspension history.

#### Govtech venture studios, accelerators, and B2G investors
Full source of a production B2G platform: DataLake with 3.5M+ records, AI classification, Stripe billing, 5,131+ automated tests, Railway + Supabase + Redis architecture. Architectural reference for govtech startups in Brazil.

#### Foreign founders entering the Brazilian B2G market
Documented stack, mapped data sources (PNCP, ComprasGov, Lei 14.133/2021), and exposed business logic — a map of the Brazilian public procurement ecosystem.

#### BI platforms, RPA, and automation tools (n8n, Make, Zapier)
Consume the REST API to feed Power BI, Tableau, or Metabase dashboards. Use webhooks and SSE endpoints to trigger n8n, Make, or Zapier automations when relevant new bids are published.

#### Trade associations, industry unions, and SME support organizations (SEBRAE)
Monitor government procurement opportunities for members by sector and region. Export periodic reports with classified bids, estimated values, and viability analysis.

#### AI-applied operations startups, digital transformation consultancies, and RPA companies
Production reference for: sector classification pipeline with LLM (GPT-4.1-nano), zero-shot classification, circuit breakers, SWR cache, real-time SSE, and async ARQ workers — all in production.

---

### Core Features

| Feature | Description |
|---------|-------------|
| **Multi-source search** | PNCP + PCP v2 + ComprasGov v3 aggregated with priority-based deduplication |
| **Proprietary DataLake** | ~1.5M bids (`pncp_raw_bids`, 400d) + ~2M contracts (`pncp_supplier_contracts`); PostgreSQL full-text <100ms p95 |
| **20 sectors** | Keyword density + GPT-4.1-nano arbiter + zero-match classification (precision ≥85%, recall ≥70%) |
| **Viability scoring** | Automatic score: modality (30%), timeline (25%), value (25%), geography (20%) |
| **Opportunity Kanban** | Drag-and-drop pipeline for bid lifecycle management |
| **Reports** | Styled Excel + AI executive summary + Google Sheets export |
| **Programmatic SEO** | 10k+ ISR pages: sectoral observatory, CNPJ, agencies, municipalities, alerts, municipal index |
| **Public API** | Observatory, contracts, and bids endpoints by sector/UF/agency — unauthenticated public data |
| **Stripe Billing** | Pro BRL 397/mo · semi-annual BRL 357/mo · annual BRL 297/mo · Consulting BRL 997/mo · 14-day trial |
| **Observability** | Prometheus + OpenTelemetry + Sentry · PNCP canary · pg_cron monitoring |

---

### Integrations and Ecosystem

SmartLic exposes a REST API + SSE (Server-Sent Events) consumable by any stack:

| Tool | Integration type |
|------|----------------|
| **n8n / Make / Zapier** | Webhook on new bids · sector/UF triggers · automatic notifications |
| **Power BI / Tableau / Metabase** | REST endpoints for contracts, bids, and indices for BI dashboards |
| **Google Sheets** | Direct export via OAuth integration built into SmartLic |
| **CRMs (HubSpot, Pipedrive, etc.)** | Qualified opportunity API to enrich commercial pipeline |
| **ERP / management systems** | Historical contracts and active bids API for data enrichment |
| **Python / Node.js / any HTTP client** | REST API documented via Swagger at `/docs` |

---

### Official Data Sources

| Source | Legal Basis | Endpoint |
|--------|-------------|----------|
| **PNCP** (National Public Procurement Portal) | Lei 14.133/2021 | `pncp.gov.br/api/consulta/v1` |
| **ComprasGov** (SIASG/CATMAT/CATSER) | Decreto 7.892/2013 | `dadosabertos.compras.gov.br` |
| **Portal de Compras Públicas (PCP v2)** | Public | `compras.api.portaldecompraspublicas.com.br/v2` |

---

### Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Backend** | FastAPI 0.136 · Python 3.12 · Pydantic 2.12 · httpx · OpenAI SDK 1.109 |
| **AI / LLM** | GPT-4.1-nano (sector classification + executive summaries) |
| **Queues** | ARQ 0.26+ · Redis (cache · circuit breaker · SSE · rate limiter · distributed locks) |
| **Database** | Supabase Cloud (PostgreSQL 17 + Auth + RLS) · 183 migrations · 48 tables · 13+ RPCs |
| **Frontend** | Next.js 16.1 · React 18.3 · TypeScript 5.9 · Tailwind CSS 3.4 · Framer Motion · @dnd-kit |
| **Billing** | Stripe 11.4 (12 webhook events) · Resend (transactional email) |
| **Infra** | Railway (web + worker + frontend) · Supabase Cloud · Redis · GitHub Actions |
| **Observability** | Prometheus · OpenTelemetry · Sentry · Mixpanel |

---

### Data Architecture (3 layers)

```
Layer 1 — ETL Ingestion (ARQ cron)
  pncp_raw_bids (~1.5M rows, 400-day retention)  ←  daily crawler (2am BRT)
  pncp_supplier_contracts (~2M rows)              ←  3×/week crawler

Layer 2 — Search Pipeline (queries local DataLake)
  search_datalake RPC → PostgreSQL full-text → <100ms p95
  fallback: live API fetch when DataLake returns 0 results

Layer 3 — Results Cache (passive, per-request)
  L1: InMemoryCache LRU (4h TTL)
  L2: Supabase search_results_cache (24h) + reactive SWR
```

---

### System Architecture

```
┌──────────────────┐
│   Next.js 16.1   │  25 core pages + 10k+ programmatic SEO pages (ISR)
└────────┬─────────┘
         │ API Proxy
┌────────▼─────────┐
│  FastAPI 0.136   │  187 endpoints · 65 modules
└────────┬─────────┘
         │
         ├──► PNCP API           (daily ingestion + live fallback)
         ├──► PCP v2 API         (live fallback)
         ├──► ComprasGov v3      (live fallback)
         ├──► OpenAI API         (sector classification + AI summaries)
         ├──► Stripe API         (billing + webhooks)
         ├──► Supabase           (PostgreSQL 17 + Auth + RLS)
         ├──► Redis              (cache + ARQ jobs + distributed locks)
         └──► Resend             (transactional email)
```

---

### Local Setup

```bash
# Backend
cd backend && python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
# Swagger at http://localhost:8000/docs

# Frontend
cd frontend && npm install && npm run dev
# App at http://localhost:3000

# Environment variables
cp .env.example .env
# Fill: OPENAI_API_KEY, SUPABASE_URL, SUPABASE_ANON_KEY,
# SUPABASE_SERVICE_ROLE_KEY, STRIPE_SECRET_KEY, REDIS_URL
```

---

### Tests

```bash
# Backend (454 files, 5,131+ passing)
cd backend && pytest --timeout=30

# Frontend (376 files, 2,681+ passing)
cd frontend && npm test

# E2E Playwright (60 critical user flows)
cd frontend && npm run test:e2e
```

---

### Production Deploy

| Component | Platform |
|-----------|---------|
| Frontend | Railway (`RAILWAY_SERVICE_ROOT_DIRECTORY=frontend`) |
| Backend API | Railway web process (`PROCESS_TYPE=web`, Uvicorn multi-worker) |
| ARQ Worker | Railway worker process (`PROCESS_TYPE=worker`) |
| Database | Supabase Cloud (PostgreSQL 17 + Auth + RLS) |
| Cache | Redis (Upstash or Railway addon) |
| CI/CD | GitHub Actions — tests + API types check + migration gate |

---

### Documentation

- [Technical PRD](./PRD.md) — Full product specification
- [Roadmap](./ROADMAP.md) — Status and backlog
- [CHANGELOG](./CHANGELOG.md) — Version history
- [GTM Resilience Summary](./docs/summaries/gtm-resilience-summary.md)
- [GTM Fixes Summary](./docs/summaries/gtm-fixes-summary.md)

---

### Partnerships and Licensing

Proprietary software. External contributions require prior written authorization from CONFENGE.

For **partnership, integration, data licensing, or white-label** inquiries:
- **Email:** tiago.sasaki@confenge.com.br
- **WhatsApp:** +55 (48) 9 8834-4559

---

## Licença / License

**© 2024-2026 CONFENGE AVALIAÇÕES E INTELIGÊNCIA ARTIFICIAL LTDA — Todos os direitos reservados / All rights reserved.**

Este software é propriedade exclusiva da CONFENGE. É estritamente proibido o uso, cópia, modificação, distribuição ou sublicenciamento sem consentimento prévio por escrito.

This software is the exclusive property of CONFENGE. Unauthorized use, copying, modification, distribution, or sublicensing is strictly prohibited.

Consulte / See [LICENSE](./LICENSE) for full terms.

**Contato / Contact:** tiago.sasaki@confenge.com.br · +55 (48) 9 8834-4559 · CONFENGE Avaliações e Inteligência Artificial LTDA
