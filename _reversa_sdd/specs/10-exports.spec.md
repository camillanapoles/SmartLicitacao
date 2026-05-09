# Spec: Exports

> Spec executável (SDD) gerada pelo **Reversa Writer** em 2026-05-08
> Confiança: 🟢 CONFIRMADO

## Component
- **ID**: `exports`
- **Path**: `backend/excel.py`, `backend/google_sheets.py`, `backend/pdf_generator_edital.py`, `backend/routes/export.py` (ou equivalente), `backend/routes/export_sheets.py`, `backend/routes/auth_oauth.py` (OAuth Google)

## Purpose

Três formatos de exportação de licitações com lógica de paywall:
1. **Excel** — `.xlsx` via openpyxl, gerado via ARQ background job, paywall preview para trial
2. **Google Sheets** — OAuth user-scoped, via Sheets API v4, paid only
3. **PDF** — A4 per-edital via ReportLab, trial com watermark diagonal

## Sub-Módulo 1: Excel Export

### Pipeline (ARQ Background Job)

```
stage_generate → ARQ excel_generation_job
  → create_excel(licitacoes)
      → Workbook() + Sheet1 'Licitacoes'
      → header row: green (#2E7D32) + white bold + 11 colunas
      → for licit in licitacoes:
          sanitize_for_excel(objeto, orgao)  # NFKD ASCII strip
          parse_datetime(data_encerramento)
          append row
      → totals row: =SUM(G2:GN) em coluna valor
      → paywall_preview AND total_before > N?
          → Sim: trim para N rows
                 append "+X bids ocultas — assine para acessar"
          → Não: skip
      → Sheet2 'Metadata' (search_params, generated_at, setor, UFs)
      → BytesIO output
      → base64 encode → persist em Redis
      → SSE event: excel_ready(download_url)
```

### Colunas Excel (11)

| # | Coluna | Fonte |
|---|--------|-------|
| A | Número | `numero_controle_pncp` |
| B | Modalidade | `modalidade_nome` |
| C | Objeto | `objeto_compra` (sanitizado) |
| D | Órgão | `orgao_entidade` (sanitizado) |
| E | UF | `uf_sigla` |
| F | Município | `municipio_nome` |
| G | Valor Estimado | `valor_total_estimado` |
| H | Data Publicação | `data_publicacao` |
| I | Data Encerramento | `data_encerramento_proposta` |
| J | Viabilidade | `viability_level` (Alta/Média/Baixa) |
| K | Link PNCP | URL formatada |

### Paywall Logic (Excel)

```python
# trial plan:
if paywall_preview and len(licitacoes) > TRIAL_MAX_EXCEL_ROWS:
    visible = licitacoes[:TRIAL_MAX_EXCEL_ROWS]
    hidden_count = len(licitacoes) - TRIAL_MAX_EXCEL_ROWS
    # append row: "+{hidden_count} bids ocultas — Assine para acessar"
```

**Env vars:** `TRIAL_MAX_EXCEL_ROWS` (default definido em `config.py`).

## Sub-Módulo 2: Google Sheets Export

### OAuth Google Linking Flow

```
GET /api/auth/google
  → gen state = secrets.token_urlsafe()
  → SET oauth_state:{state} user_id ex=600 (Redis)
  → redirect to Google authorize_url (scope: spreadsheets)

GET /api/auth/google/callback?code&state
  → GET oauth_state:{state} → user_id (ou 403 invalid state)
  → exchange code for {access_token, refresh_token}
  → Fernet.encrypt(refresh_token) com OAUTH_FERNET_KEY
  → INSERT user_oauth_credentials(provider=google, encrypted_refresh)
  → redirect /conta?google=connected

DELETE /api/auth/google
  → revogar token Google + DELETE user_oauth_credentials
```

### Sheets Export Endpoint

```
POST /api/export/google-sheets
  → require_auth + check OAuth linked (user_oauth_credentials WHERE provider=google)
  → SELECT encrypted_refresh FROM user_oauth_credentials
  → Fernet.decrypt → refresh_token
  → google.oauth2.Credentials.refresh() → access_token
  → spreadsheet_id given?
      → Sim (update mode): spreadsheets.values.clear + batchUpdate
      → Não (create mode): spreadsheets.create(title, sheets=[Sheet1])
  → batchUpdate: format ops (header bold, freeze row, col widths)
  → INSERT google_sheets_exports(user_id, spreadsheet_id, search_id, created_at)
  → 200 {url, spreadsheet_id}
```

**Acesso restrito:** disponível apenas para planos paid (verificado via `require_active_plan` + capabilities check).

### Dados Estruturais

```python
# user_oauth_credentials
{
  "user_id": uuid,
  "provider": "google",
  "encrypted_refresh": bytes,  # Fernet AES-256
  "created_at": datetime
}

# google_sheets_exports
{
  "id": uuid,
  "user_id": uuid,
  "spreadsheet_id": str,
  "search_id": uuid,
  "url": str,
  "created_at": datetime
}
```

## Sub-Módulo 3: PDF Export

### Per-Edital PDF (POST /v1/export/pdf)

```
POST /v1/export/pdf + PdfEditalRequest
  → require_auth
  → plan_type from user (para watermark decision)
  → asyncio.wait_for(
        asyncio.to_thread(generate_edital_pdf, bid_data, plan_type),
        timeout=10
    )
        → TimeoutError: 503 (PT-BR message)
        → Exception: 500
        → ok: pdf_bytes (ReportLab Canvas)
  → _safe_filename(objeto): NFKD ASCII strip
  → Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="SmartLic_{title}_{date}.pdf"'}
    )
```

### PDF Layout (ReportLab A4)

```
Canvas A4 portrait
  → Header: logo + SmartLic brand (BRAND_DARK_BLUE #1B3A5C)
  → Title: objeto truncado 80 chars
  → Metadata 2-col: orgao, UF, modalidade, valor estimado, data publicação, data encerramento
  → Viability box: background color by level (green/yellow/gray)
  → AI Summary section: resumo_executivo (se disponível)
  → Recomendação section
  → plan_type == 'free_trial'?
      → Sim: watermark diagonal "SMARTLIC TRIAL" (gray, translucido, 45°)
      → Não: skip watermark
  → Footer: "página 1/1" + URL smartlic.tech
```

**Cores brand:**
- `BRAND_DARK_BLUE` = `#1B3A5C`
- `BRAND_MEDIUM_BLUE` = `#2C5F8A`
- `BRAND_LIGHT_BLUE` = `#E8F0FE`
- `VIABILITY_GREEN` = `#16A34A`
- `VIABILITY_YELLOW` = `#CA8A04`
- `VIABILITY_GRAY` = `#64748B`

## Functional Requirements

**Excel:**
- **FR-1**: `create_excel(licitacoes)` gera `.xlsx` com header verde + 11 cols + totals row
- **FR-2**: Trial plan → paywall preview (N rows visíveis, +X ocultas row)
- **FR-3**: `sanitize_for_excel` limpa caracteres ilegais NFKD ASCII (XLSX constraint)
- **FR-4**: ARQ background job → base64 Redis → SSE `excel_ready(download_url)`

**Google Sheets:**
- **FR-5**: OAuth Google CSRF com state Redis 10min
- **FR-6**: Fernet AES-256 encrypt/decrypt refresh token (nunca plaintext)
- **FR-7**: Create mode: nova spreadsheet; Update mode: clear + batchUpdate
- **FR-8**: Format ops: header bold + freeze row 1 + col widths adequadas
- **FR-9**: Persiste `google_sheets_exports` com spreadsheet_id + URL

**PDF:**
- **FR-10**: `generate_edital_pdf` via `asyncio.to_thread` (não bloqueia event loop)
- **FR-11**: Timeout 10s → 503 (PT-BR)
- **FR-12**: Trial watermark diagonal em todos PDFs de trial users
- **FR-13**: `_safe_filename` strip NFKD para evitar encoding issues no Content-Disposition

## Non-Functional Requirements

- **NFR-1**: Excel generation <30s (ARQ job, sem timeout de rota)
- **NFR-2**: PDF generation <10s (asyncio.wait_for)
- **NFR-3**: Google Sheets API call <15s (httpx timeout)
- **NFR-4**: OAuth callback <2s (Google token exchange)
- **NFR-5**: Fernet encrypt/decrypt <1ms (CPU bound, sync ok)

## Constraints

- **CON-1**: `OAUTH_FERNET_KEY` rotation NÃO implementado — rotacionar invalida todos refresh tokens
- **CON-2**: Google Sheets requires paid plan (trial user → 403 `pipeline_not_available`)
- **CON-3**: Excel gerado via ARQ — se worker offline, gerado inline (SSE `excel_ready` pode demorar)
- **CON-4**: PDF gerado síncrono (thread) — Railway timeout 120s é o limite real
- **CON-5**: `asyncio.wait_for` + `asyncio.to_thread` — POOL-LEAK-001: thread continua até OS kill mesmo após timeout (expected behavior)

## Acceptance Criteria

- AC-1: Excel trial plan → arquivo com ≤N rows + footer "X bids ocultas"
- AC-2: Excel paid plan → arquivo com todos os resultados sem footer
- AC-3: Google Sheets OAuth flow completo → `user_oauth_credentials` row com encrypted_refresh
- AC-4: Google Sheets export → spreadsheet acessível via URL retornada
- AC-5: PDF trial → watermark "SMARTLIC TRIAL" visível diagonal
- AC-6: PDF paid → sem watermark
- AC-7: `POST /v1/export/pdf` com LLM timeout > 10s → 503 (não 500)
- AC-8: OAuth state inválido (CSRF) → 403 `oauth_state_invalid`

## Errors

| Code | HTTP | Trigger |
|------|------|---------|
| `pipeline_not_available` | 403 | Google Sheets em trial plan |
| `oauth_not_linked` | 400 | usuário sem OAuth Google linked |
| `oauth_state_invalid` | 403 | CSRF state mismatch |
| `oauth_exchange_failed` | 502 | Google token exchange fail |
| `pdf_timeout` | 503 | PDF generation > 10s |
| `pdf_error` | 500 | ReportLab exception |
| `sheets_api_error` | 502 | Google Sheets API failure |
| `excel_generation_failed` | 500 | openpyxl exception em job |

## Code Traceability

- `backend/excel.py` — `create_excel`, `sanitize_for_excel`, `parse_datetime`
- `backend/google_sheets.py` — `export_to_sheets`, `update_spreadsheet`
- `backend/pdf_generator_edital.py` — `generate_edital_pdf`, `_safe_filename`, `_build_canvas`
- `backend/routes/auth_oauth.py` — OAuth Google linking 3 endpoints
- `backend/oauth.py` — `Fernet.encrypt/decrypt`, CSRF state management
- `backend/jobs/queue/jobs.py:excel_generation_job` — ARQ async job

## Dependencies

- `openpyxl` (Excel generation)
- `ReportLab` (PDF generation — Canvas, SimpleDocTemplate)
- `google-auth`, `google-auth-oauthlib`, `googleapiclient` (Sheets API v4)
- `cryptography.fernet` (refresh token encryption)
- Redis (OAuth CSRF state, Excel base64 result)
- Supabase (`user_oauth_credentials`, `google_sheets_exports`)
- ARQ (excel_generation_job dispatch)
- Auth: `require_auth`, `require_active_plan`
