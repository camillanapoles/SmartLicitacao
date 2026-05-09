# Spec: Intel Reports (Raio-X Concorrente)

> Spec executável (SDD) gerada pelo **Reversa Writer** em 2026-05-08
> Confiança: 🟢 CONFIRMADO

## Component
- **ID**: `intel-reports`
- **Path**: `backend/routes/intel_reports.py`, `backend/pdf_generator_intel_report.py`, `backend/schemas/intel_report.py`, `backend/services/billing.py` (create_intel_report_checkout), `backend/intel_sectors_config.yaml`

## Purpose

Módulo de relatórios de inteligência competitiva one-time purchase (#630). Dois produtos:
1. **INTEL-REPORT-001** — Raio-X do Concorrente (por CNPJ): R$197,00 — análise profunda de empresa concorrente
2. **INTEL-REPORT-002** — Relatório Setorial por UF (setor:uf): R$147,00 — panorama de mercado setorial

Fluxo: Stripe Checkout one-time → webhook fulfillment → PDF A4 (8-12 páginas) gerado via `pdf_generator_intel_report.py` → armazenado em Supabase Storage → download autenticado com ownership check.

## Products

| product_type | entity_key format | Preço | Descrição |
|-------------|------------------|-------|-----------|
| `cnpj` | `"12345678000195"` | R$197,00 | Análise empresa por CNPJ |
| `sector_uf` | `"limpeza:SP"` | R$147,00 | Mercado setorial por UF |

## Purchase Flow

```
1. POST /v1/intel-reports/checkout
   body: {product_type, entity_key}
   → require_auth
   → _create_checkout(product_type, entity_key, user_id)
       → Stripe Checkout Session (mode=payment, payment_once)
       → price_data inline (sem Price object pré-criado)
       → success_url: /intel-reports/{CHECKOUT_SESSION_ID}?status=processing
       → cancel_url: /intel-reports?cancelled=true
       → metadata: {user_id, product_type, entity_key}
   → INSERT intel_report_purchases(
           user_id, product_type, entity_key,
           status='pending', stripe_session_id
       )
   → 200 {checkout_url, session_id}

2. User pays → Stripe redirect to success_url

3. Stripe webhook: checkout.session.completed
   → handlers/intel_report.py (ou checkout.py extended)
   → verify signature
   → get metadata: {user_id, product_type, entity_key}
   → UPDATE intel_report_purchases SET status='processing' WHERE stripe_session_id
   → enqueue ARQ job: generate_intel_report_job(purchase_id, product_type, entity_key)

4. ARQ Worker: generate_intel_report_job
   → query DataLake (cnpj_supplier_intel RPC ou sector_uf_intel)
   → generate_cnpj_report(data) | generate_sector_report(data)
       → ReportLab PDF A4 8-12 páginas
       → BytesIO output
   → upload to Supabase Storage
   → UPDATE intel_report_purchases SET
           status='ready',
           pdf_url=storage_url,
           expires_at=now+30d
   → (opcional) send email via Resend: panorama_t1_delivery.py

5. Frontend polls: GET /v1/intel-reports/{purchase_id}
   → status: pending → processing → ready | failed
```

## Endpoints (4)

| Método | Path | Auth | Descrição |
|--------|------|------|-----------|
| `POST` | `/v1/intel-reports/checkout` | user | criar Stripe Checkout one-time |
| `GET` | `/v1/intel-reports/` | user | listar purchases do user |
| `GET` | `/v1/intel-reports/{purchase_id}` | user | poll status (pending/processing/ready/failed) |
| `GET` | `/v1/intel-reports/{purchase_id}/download` | user + ownership | stream PDF (ownership check) |

## Status State Machine

```
pending → processing: Stripe webhook checkout.session.completed
processing → ready: ARQ job completa PDF + upload Storage
processing → failed: ARQ job exception (PDF gen ou Storage failure)
ready → [*]: expires_at (30d TTL)
```

## Ownership Check Pattern

```python
# Anti-pattern evitado: .eq("user_id").eq("id") → ambíguo 404 vs 403
# Padrão correto:
result = await sb_execute(db.table("intel_report_purchases")
    .select("id, user_id, status, pdf_url")
    .eq("id", purchase_id)
    .single())

if not result.data:
    raise HTTPException(404, "Compra não encontrada.")

if result.data["user_id"] != user["id"]:
    raise HTTPException(403, "Acesso negado.")
```

## PDF Generation (pdf_generator_intel_report.py)

### Estrutura A4 (8-12 páginas)

```
Página 1 — Capa
  → Logo SmartLic + BRAND_DARK_BLUE (#1B3A5C)
  → Título: "Raio-X do Concorrente: {empresa_nome}"
  → CNPJ, data geração, footer SmartLic Intelligence

Página 2 — Resumo Executivo
  → Metric boxes (METRIC_BOX_BG #EFF6FF):
      total_contratos_ganhos, valor_total, ticket_medio, anos_atuacao
  → Principais setores (top 5)

Páginas 3-5 — Histórico de Contratos
  → Tabela (TABLE_HEADER_BG = BRAND_DARK_BLUE, TABLE_ALT_ROW #F8FAFC)
  → Colunas: Ano, Órgão, Valor, Modalidade, UF, Setor
  → Evolução temporal (ano a ano)

Página 6 — Análise por Órgão
  → Top 10 órgãos compradores (tabela + share %)

Página 7 — Análise por UF
  → Mapa de atuação geográfica

Página 8 — Perfil Societário
  → BrasilAPI enrichment (razao_social, porte, capital_social, socios)

Página 9+ — Sanções e Compliance
  → sanctions_master check
  → {sem_sanções} ou tabela de impedimentos

Última página — Footer
  → "SmartLic Intelligence — smartlic.tech | Dados: PNCP | Atualizado em {data}"
```

### Cores Brand

| Constante | Hex | Uso |
|-----------|-----|-----|
| `BRAND_DARK_BLUE` | `#1B3A5C` | Header, table header |
| `BRAND_MEDIUM_BLUE` | `#2C5F8A` | Subheader, accent |
| `BRAND_LIGHT_BLUE` | `#E8F0FE` | Section backgrounds |
| `BRAND_ACCENT` | `#3B82F6` | Links, highlights |
| `METRIC_BOX_BG` | `#EFF6FF` | KPI boxes |
| `TABLE_ALT_ROW` | `#F8FAFC` | Zebra striping |
| `TABLE_BORDER` | `#CBD5E1` | Grid lines |
| `VIABILITY_GREEN` | `#16A34A` | Positivo |
| `VIABILITY_YELLOW` | `#CA8A04` | Neutro |
| `VIABILITY_GRAY` | `#64748B` | N/A |

### DataLake Source (RPC)

```python
# Para product_type='cnpj':
data = sb.rpc('cnpj_supplier_intel', {
    'p_cnpj': entity_key,
    'p_days': 400  # full retention window
}).execute()

# Para product_type='sector_uf':
setor, uf = entity_key.split(':')
data = sb.rpc('sector_uf_intel', {
    'p_setor': setor,
    'p_uf': uf
}).execute()
```

### PDF Download (Streaming)

```python
# GET /v1/intel-reports/{purchase_id}/download
async with httpx.AsyncClient(timeout=30.0) as client:
    response = await client.get(purchase.pdf_url)
    response.raise_for_status()
    pdf_bytes = response.content

return StreamingResponse(
    content=iter([pdf_bytes]),
    media_type="application/pdf",
    headers={
        "Content-Disposition": f'attachment; filename="intel-report-{purchase_id[:8]}.pdf"',
        "Content-Length": str(len(pdf_bytes)),
    }
)
```

## intel_sectors_config.yaml

Configuração de setores suportados para `sector_uf` reports — subset dos 20 setores padrão, com metadados específicos de intel (thresholds, fontes de dados, etc.).

## Dados Estruturais

```python
# intel_report_purchases (table)
{
  "id": uuid,
  "user_id": uuid,
  "product_type": "cnpj|sector_uf",
  "entity_key": str,          # CNPJ ou "setor:uf"
  "status": "pending|processing|ready|failed",
  "stripe_session_id": str,
  "pdf_url": str | None,       # Supabase Storage presigned URL
  "expires_at": datetime | None,  # 30d após geração
  "created_at": datetime
}

# IntelReportCheckoutRequest
{
  "product_type": "cnpj|sector_uf",
  "entity_key": str
}

# IntelReportCheckoutResponse
{
  "checkout_url": str,
  "session_id": str
}

# IntelReportStatusResponse
{
  "status": "pending|processing|ready|failed",
  "pdf_url": str | None,
  "expires_at": datetime | None
}
```

## Invariants

1. **Ownership check first** — query by `id` only, then check `user_id` (distingue 404 de 403)
2. **Idempotência Stripe** — `events_processed` dedup por `stripe_event_id` (padrão billing)
3. **Storage presigned URL** — `pdf_url` é presigned (expira em T, não permanente) — usar `expires_at` para UI
4. **Status terminal** — `ready` e `failed` são terminais (sem transição reversa)
5. **Price data inline** — sem Price object pré-criado em Stripe (ok para dev/test; produção pode usar Price IDs)

## Functional Requirements

- **FR-1**: `POST /intel-reports/checkout` cria Stripe Checkout session one-time payment
- **FR-2**: Stripe webhook `checkout.session.completed` → status `processing` + ARQ job enqueue
- **FR-3**: ARQ job gera PDF via `pdf_generator_intel_report.py`, upload Storage, status `ready`
- **FR-4**: `GET /intel-reports/` lista purchases do user (ordered by created_at DESC)
- **FR-5**: `GET /intel-reports/{id}` poll status (frontend polling até `ready`)
- **FR-6**: `GET /intel-reports/{id}/download` stream PDF com ownership check + status=ready check
- **FR-7**: PDF expires após 30d (`expires_at`) — após expiração retorna 400

## Non-Functional Requirements

- **NFR-1**: Checkout creation <2s (Stripe API)
- **NFR-2**: PDF generation <60s (ARQ job, sem timeout de rota)
- **NFR-3**: Streaming download <30s (httpx timeout 30s)
- **NFR-4**: Status poll endpoint <100ms (single DB query)

## Constraints

- **CON-1**: `product_type` deve ser `cnpj` ou `sector_uf` (Pydantic Literal validation)
- **CON-2**: CNPJ deve ser 14 dígitos numéricos (validation antes de RPC)
- **CON-3**: `entity_key` para `sector_uf` deve seguir formato `"setor:uf"` (e.g. `"limpeza:SP"`)
- **CON-4**: Stripe IntelReport products devem ser criados manualmente no Dashboard antes de produção
- **CON-5**: Sem trial/plan check — qualquer usuário autenticado pode comprar (one-time payment)

## Acceptance Criteria

- AC-1: `POST /intel-reports/checkout` retorna `checkout_url` com Stripe session válida
- AC-2: Stripe webhook `checkout.session.completed` → `status='processing'` em DB em <500ms
- AC-3: ARQ job completa → `status='ready'`, `pdf_url` preenchido
- AC-4: `GET /intel-reports/{id}/download` com `status='ready'` → PDF stream (Content-Type: application/pdf)
- AC-5: `GET /intel-reports/{id}/download` com `status='processing'` → 400 (não 200 vazio)
- AC-6: Outro user tenta baixar purchase_id alheio → 403 (não 404)
- AC-7: PDF CNPJ tem ≥8 páginas com tabela de contratos históricos

## Errors

| Code | HTTP | Trigger |
|------|------|---------|
| `not_found` | 404 | purchase_id não existe |
| `forbidden` | 403 | purchase pertence a outro user |
| `report_not_ready` | 400 | download com status != ready |
| `invalid_product_type` | 422 | product_type inválido |
| `invalid_entity_key` | 422 | CNPJ malformado ou setor:uf inválido |
| `stripe_invalid_request` | 400 | Stripe rejeita checkout (log stripe_request_id) |
| `stripe_unavailable` | 503 | Stripe API down |
| `pdf_fetch_error` | 502 | Supabase Storage URL inacessível |
| `pdf_generation_failed` | 500 | ReportLab exception no ARQ job |

## Code Traceability

- `backend/routes/intel_reports.py` — 4 endpoints (checkout, list, status, download)
- `backend/pdf_generator_intel_report.py` — `generate_cnpj_report`, ReportLab A4 8-12p
- `backend/schemas/intel_report.py` — `IntelReportCheckoutRequest/Response`, `IntelReportStatusResponse`, `IntelReportPurchase`
- `backend/services/billing.py:create_intel_report_checkout` — Stripe one-time checkout
- `backend/intel_sectors_config.yaml` — config setores suportados para sector_uf
- Supabase `intel_report_purchases` table (migration #628)
- `backend/webhooks/handlers/checkout.py` (ou handler dedicado) — webhook fulfillment
- ARQ job `generate_intel_report_job` (em `backend/jobs/queue/definitions.py`)

## Dependencies

- Stripe SDK (one-time Checkout session)
- `reportlab` (PDF generation — SimpleDocTemplate, Platypus)
- Supabase (`intel_report_purchases`, Storage)
- Redis (ARQ job queue)
- `httpx` (streaming PDF download from Storage)
- Auth: `require_auth`
- `cnpj_supplier_intel` RPC (DataLake query por CNPJ)
- `sector_uf_intel` RPC (DataLake query por setor×UF)
- `pncp_supplier_contracts` (source dos dados contratuais)
- `enriched_entities` (BrasilAPI dados cadastrais)
- `sanctions_master` (impedimentos e sanções)
