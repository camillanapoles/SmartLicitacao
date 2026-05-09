# Flowchart — Módulo `intel-reports`

> Gerado pelo **Reversa Archaeologist** em 2026-05-09 · Confiança 🟢 CONFIRMADO
> Cross-reference: `_reversa_sdd/specs/07-intel-report-sector-uf.md`, `_reversa_sdd/specs/07b-intel-pdf-generator.md`, `_reversa_sdd/specs/13-intel-reports.spec.md`

Cobre os 3 fluxos canonicais do produto Intel Reports (one-time PDF reports gerados por LLM + dados agregados):

1. **v0.1 cnpj_supplier (R$67)** — relatório de inteligência sobre um fornecedor específico (CNPJ alvo).
2. **v0.2 sector_uf (R$147)** — relatório setorial × UF (e.g., "vigilância em SP").
3. **Failure paths** — webhook delivery, PDF timeout, Storage upload, email retry.

Os fluxos compartilham o mesmo skeleton: `Stripe checkout → webhook handler → ARQ job → RPC → LLM narrative → PDF generator → Storage upload → email + dashboard delivery`. Diferenças isoladas em **payload** (CNPJ vs setor+UF), **RPC** (`cnpj_supplier_intel` vs `sector_uf_intel`), **PDF generator** (`pdf_generator.py` vs `pdf_generator_sector_uf_report.py`), **email template** (Resend `intel-report-ready-cnpj` vs `intel-report-ready-sector`), **price** (R$67 vs R$147).

---

## Flow 1 — v0.1 cnpj_supplier (R$67)

```mermaid
sequenceDiagram
    participant U as User (browser)
    participant FE as Frontend
    participant API as POST /v1/intel-reports/checkout
    participant Stripe as Stripe
    participant WH as POST /v1/billing/webhook
    participant ARQ as ARQ queue
    participant Job as _generate_cnpj_supplier_report_pdf
    participant DB as Supabase (RPC + intel_reports)
    participant LLM as OpenAI GPT-4.1-nano
    participant PDF as pdf_generator.CNPJSupplierReport
    participant Stor as Supabase Storage (intel-reports bucket)
    participant Mail as Resend (smartlic.tech)

    U->>FE: clica CTA "Comprar Relatório R$67" + cnpj=...
    FE->>API: POST {cnpj, kind:"cnpj_supplier"}
    API->>API: require_auth + validate CNPJ
    API->>DB: INSERT intel_reports (status=pending, kind, cnpj, user_id, price_cents=6700)
    API->>Stripe: checkout.session.create(mode=payment, metadata.intel_report_id, line_items[R$67])
    Stripe-->>API: session.url
    API-->>FE: 200 {checkout_url}
    FE->>U: redirect Stripe Checkout

    U->>Stripe: pagamento (cartão / Pix)
    Stripe->>WH: checkout.session.completed (signature HMAC)
    WH->>WH: verify_signature (Stripe-Signature) + idempotency (stripe_webhook_events)
    WH->>DB: UPDATE intel_reports SET status='paid', stripe_session_id WHERE id=metadata.intel_report_id
    WH->>ARQ: enqueue _generate_cnpj_supplier_report_pdf(intel_report_id)
    WH-->>Stripe: 200 OK

    Note over ARQ,Job: Background — não bloqueia checkout
    ARQ->>Job: invoke (intel_report_id)
    Job->>DB: SELECT intel_reports WHERE id=...
    Job->>DB: UPDATE status='generating'
    Job->>DB: rpc('cnpj_supplier_intel', {cnpj, lookback_days=400})
    DB-->>Job: jsonb {contracts[], suppliers_top, panorama_setorial, monthly_trend, totals}
    Job->>LLM: chat.completions.create(model=gpt-4.1-nano, prompt=narrative(payload))
    LLM-->>Job: narrative_md (executive summary + insights)
    Job->>PDF: CNPJSupplierReport(payload, narrative_md).render()
    PDF-->>Job: pdf_bytes (ReportLab)
    Job->>Stor: storage.upload(bucket="intel-reports", path="cnpj_supplier/{id}.pdf", content=pdf_bytes)
    Stor-->>Job: storage_path
    Job->>DB: UPDATE intel_reports SET status='ready', storage_path, pdf_size_bytes
    Job->>Mail: send(template="intel-report-ready", to=user.email, link=signed_url(storage_path, 7d))
    Mail-->>Job: 200 message_id

    Note over FE,DB: Dashboard polling — Frontend
    FE->>API: GET /v1/intel-reports/me (poll a cada 5s pós-checkout, max 5min)
    API->>DB: SELECT WHERE user_id ORDER BY created_at DESC
    DB-->>API: [{id, status, storage_path, kind, created_at}]
    API-->>FE: list
    FE->>U: render badge "✓ Relatório pronto" + botão "Baixar"
    U->>FE: click Baixar
    FE->>API: GET /v1/intel-reports/{id}/download
    API->>API: require_auth + verify ownership
    API->>Stor: createSignedUrl(storage_path, expires=600s)
    Stor-->>API: signed_url
    API-->>FE: 302 redirect signed_url
    FE->>Stor: GET signed_url
    Stor-->>U: PDF download
```

**Source files:**
- `backend/routes/intel_reports.py` — `POST /v1/intel-reports/checkout`, `GET /v1/intel-reports/me`, `GET /v1/intel-reports/{id}/download`
- `backend/services/billing.py:create_intel_report_checkout` — Stripe session creation com metadata
- `backend/jobs/queue/jobs.py:_generate_cnpj_supplier_report_pdf` — ARQ worker
- `backend/pdf_generator.py:CNPJSupplierReport` — ReportLab template (ver spec 07b)
- `backend/email_service.py:send_intel_report_ready` — Resend wrapper
- `supabase/migrations/20260505113900_cnpj_supplier_intel_rpc.sql` — RPC `cnpj_supplier_intel(cnpj, lookback_days)`
- `supabase/migrations/20260505113800_intel_reports_schema.sql` — tabela `intel_reports`
- `supabase/migrations/20260507110000_create_intel_reports_bucket.sql` — Storage bucket setup

---

## Flow 2 — v0.2 sector_uf (R$147)

```mermaid
sequenceDiagram
    participant U as User (browser)
    participant FE as Frontend
    participant API as POST /v1/intel-reports/checkout
    participant Stripe as Stripe
    participant WH as POST /v1/billing/webhook
    participant ARQ as ARQ queue
    participant Job as _generate_sector_uf_report_pdf
    participant DB as Supabase (RPC + intel_reports)
    participant LLM as OpenAI GPT-4.1-nano
    participant PDF as pdf_generator_sector_uf_report.SectorUFReport
    participant Stor as Supabase Storage
    participant Mail as Resend

    U->>FE: clica CTA "Relatório Setorial R$147" + setor=vigilancia + uf=SP
    FE->>API: POST {setor_id, uf, kind:"sector_uf"}
    API->>API: require_auth + validate (setor in 20 known + uf in 27 UFs)
    API->>DB: INSERT intel_reports (status=pending, kind="sector_uf", payload={setor_id,uf}, price_cents=14700)
    API->>Stripe: checkout.session.create(R$147 line_item, metadata.intel_report_id)
    Stripe-->>FE: session.url
    FE->>U: redirect

    U->>Stripe: pagamento
    Stripe->>WH: checkout.session.completed
    WH->>WH: verify HMAC + idempotency
    WH->>DB: UPDATE intel_reports status='paid'
    WH->>ARQ: enqueue _generate_sector_uf_report_pdf(intel_report_id)

    ARQ->>Job: invoke
    Job->>DB: SELECT intel_reports WHERE id=...
    Job->>DB: UPDATE status='generating'
    Job->>DB: rpc('sector_uf_intel', {setor_id, uf, lookback_days=400})
    DB-->>Job: jsonb {orgaos_top[], suppliers_top[], modalidade_distribution, monthly_trend, panorama, totals}
    Job->>LLM: chat.completions(prompt=sector_uf_narrative(payload))
    LLM-->>Job: narrative_md (oportunidades + concorrência + sazonalidade)
    Job->>PDF: SectorUFReport(payload, narrative_md).render()
    PDF-->>Job: pdf_bytes
    Job->>Stor: storage.upload(bucket="intel-reports", path="sector_uf/{id}.pdf")
    Stor-->>Job: storage_path
    Job->>DB: UPDATE status='ready'
    Job->>Mail: send(template="intel-report-ready-sector", subject="Seu relatório de {setor}/{uf} está pronto", link=signed_url)
    Mail-->>Job: ok

    FE->>API: GET /v1/intel-reports/me (poll)
    API-->>FE: includes new sector_uf row
    U->>FE: download
```

**Diferenças vs Flow 1:**

| Aspecto | v0.1 cnpj_supplier | v0.2 sector_uf |
|---------|--------------------|----------------|
| Preço | R$67 (price_cents=6700) | R$147 (price_cents=14700) |
| Payload entrada | `{cnpj}` | `{setor_id, uf}` |
| RPC | `cnpj_supplier_intel(cnpj, lookback_days)` | `sector_uf_intel(setor_id, uf, lookback_days)` |
| PDF generator | `pdf_generator.CNPJSupplierReport` | `pdf_generator_sector_uf_report.SectorUFReport` |
| Email template | `intel-report-ready` (CNPJ-focused) | `intel-report-ready-sector` (setor-focused) |
| LLM prompt | foco em fornecedor (track record, contratos vencidos) | foco em mercado (oportunidades por modalidade × valor × sazonalidade) |
| Storage path prefix | `cnpj_supplier/` | `sector_uf/` |

**Source files (incremental):**
- `backend/pdf_generator_sector_uf_report.py` — ReportLab template v0.2
- `backend/jobs/queue/jobs.py:_generate_sector_uf_report_pdf` — sibling worker
- `backend/schemas/intel_report.py` — Pydantic models (`IntelReportKind`, `SectorUFPayload`, `CnpjSupplierPayload`)
- `supabase/migrations/20260508120000_sector_uf_intel_rpc.sql` — RPC

---

## Flow 3 — Failure paths

```mermaid
sequenceDiagram
    participant Stripe
    participant WH as POST /v1/billing/webhook
    participant ARQ
    participant Job
    participant DB as Supabase
    participant LLM as OpenAI
    participant Stor as Storage
    participant Mail as Resend
    participant Sentry

    Note over Stripe,WH: 1) Webhook delivery falha
    Stripe->>WH: checkout.session.completed
    WH--xWH: HTTP 500 (e.g. DB pool exhaustion)
    Stripe->>Sentry: webhook_delivery_failed
    Note over Stripe: Stripe retry policy: 3h / 6h / 24h / 48h / 72h (3 dias total)
    Stripe->>WH: retry attempt N
    WH->>DB: SELECT 1 FROM stripe_webhook_events WHERE event_id=?
    alt event_id já processado (idempotency hit)
        DB-->>WH: row exists
        WH-->>Stripe: 200 OK (no-op replay)
    else first time after recovery
        WH->>DB: INSERT stripe_webhook_events
        WH->>DB: UPDATE intel_reports status='paid'
        WH->>ARQ: enqueue
        WH-->>Stripe: 200 OK
    end

    Note over ARQ,Job: 2) PDF generation timeout
    ARQ->>Job: invoke (with arq job_timeout=300s)
    Job->>DB: rpc('sector_uf_intel') (15s statement_timeout)
    Job->>LLM: chat.completions (45s default openai timeout)
    alt LLM timeout / 503
        LLM--xJob: TimeoutError
        Job->>Sentry: capture_exception
        Job->>DB: UPDATE intel_reports status='failed', failure_reason='llm_timeout'
        Job->>ARQ: arq retry policy (max 3, exponential backoff 1m/5m/30m)
        alt retries esgotadas
            Job->>DB: status='failed_terminal'
            Job->>Mail: send(template="intel-report-failed-refund", subject="Houve um problema...", refund_promise)
        end
    end

    Note over Job,Stor: 3) Storage upload falha
    Job->>Stor: storage.upload(bucket, path, bytes)
    alt 5xx Supabase Storage
        Stor--xJob: HTTPError
        Job->>Sentry: storage_upload_failed
        Job->>ARQ: retry (3x backoff)
        alt persiste
            Job->>DB: UPDATE status='failed', failure_reason='storage_upload'
            Note over Job: PDF gerado mas não-persistido — operacionalmente perdido
        end
    end

    Note over Job,Mail: 4) Email delivery falha (Resend retry)
    Job->>Mail: send(template, to, link)
    alt 4xx (invalid email)
        Mail--xJob: 400
        Job->>DB: UPDATE intel_reports SET email_status='bounced'
        Note over Job: User ainda vê PDF no dashboard polling — degraded gracefully
    else 5xx (Resend down)
        Mail--xJob: 503
        Job->>ARQ: retry (3x exponential)
        alt persiste
            Job->>DB: email_status='failed_terminal'
            Job->>Sentry: alert
            Note over Job: Dashboard delivery sobrevive — email é canal secundário
        end
    end
```

**Failure mode summary:**

| Failure | Mitigação | Recuperação automática? | User-facing impact |
|---------|-----------|-------------------------|--------------------|
| Webhook delivery (Stripe→backend) | Stripe retry policy 3d + idempotency `stripe_webhook_events` | Sim (até 3 dias) | Latência variável até job iniciar |
| PDF generation timeout (LLM/RPC) | ARQ retry 3x exponential + `intel_reports.failure_reason` | Sim | Email refund promise se terminal |
| Storage upload | ARQ retry 3x | Sim | Operacionalmente perdido se persiste — manual intervention |
| Email delivery (Resend) | ARQ retry 3x + dashboard delivery preserva acesso | Parcial | Email pode falhar mas PDF acessível via dashboard |
| User abandona checkout | TTL Stripe session 24h, intel_reports SET status='abandoned' via cron job | Sim | Sem cobrança |

**Refund policy (gap atual — backlog):** decisão de refund quando `status='failed_terminal'` é manual hoje (admin via Stripe dashboard). Story `INTEL-FAIL-REFUND-001` no backlog para automatizar.

**HMAC webhook signature:** Stripe-Signature já enforced em `POST /v1/billing/webhook`. Diferente do gap aberto em `POST /v1/trial-emails/webhook` (HMAC ainda não-implementado — ver memory `reference_trial_email_log_delivery_status_null.md`). Esta diferenciação é importante: Intel Reports webhook está em paridade de segurança Stripe-recommended; trial-emails webhook NÃO está.

---

## Cross-references

- **Spec SDD:** `_reversa_sdd/specs/13-intel-reports.spec.md` — contrato funcional + AC
- **Spec v0.2 detalhe:** `_reversa_sdd/specs/07-intel-report-sector-uf.md` — payload sector_uf, prompts LLM, layout PDF
- **Spec PDF generator:** `_reversa_sdd/specs/07b-intel-pdf-generator.md` — ReportLab styles, footer com signed_url, paginação
- **Code analysis Module 19:** `_reversa_sdd/code-analysis.md` — files, LOC, confidence
- **Data master:** `_reversa_sdd/data-master.md` — `intel_reports` table + RPCs
