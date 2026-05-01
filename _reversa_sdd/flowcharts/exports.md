# Flowchart — Módulo `exports`

> Gerado pelo **Reversa Archaeologist** em 2026-04-27 · Confiança 🟢 CONFIRMADO

## Excel export pipeline

```mermaid
flowchart TD
    A[stage_generate ARQ excel_generation_job] --> B[create_excel licitacoes]
    B --> C[Workbook + Sheet1 'Licitacoes']
    C --> D[header row green 2E7D32 + white bold + 11 cols]
    D --> E[for licit in licitacoes]
    E --> F[sanitize_for_excel objeto/orgao]
    F --> G[parse_datetime data_encerramento]
    G --> H[append row]
    H --> E
    E -->|done| I[totals row =SUM G2:GN]
    I --> J{paywall_preview AND total_before > N?}
    J -->|sim| K[trim para N rows + append +X bids ocultas — assine]
    J -->|não| L[skip]
    K --> M[Sheet2 'Metadata']
    L --> M
    M --> N[BytesIO output]
    N --> O[base64 encode persist Redis]
    O --> P[SSE event excel_ready download_url]
```

## Google Sheets export

```mermaid
sequenceDiagram
    participant U as User
    participant API as POST /api/export/google-sheets
    participant DB as user_oauth_credentials
    participant F as Fernet
    participant GS as Sheets API v4

    U->>API: search_id ou licitacoes inline
    API->>API: require_auth + check OAuth linked
    API->>DB: SELECT encrypted_refresh WHERE user_id, provider=google
    DB-->>API: encrypted token
    API->>F: Fernet.decrypt
    F-->>API: refresh_token
    API->>GS: Credentials.refresh -> access_token
    alt update mode (spreadsheet_id given)
        API->>GS: spreadsheets.values.clear + update batch
    else create mode
        API->>GS: spreadsheets.create
    end
    API->>GS: batchUpdate format ops
    GS-->>API: spreadsheet response
    API->>DB: INSERT google_sheets_exports
    API-->>U: 200 url + spreadsheet_id
```

## PDF export per-edital

```mermaid
flowchart TD
    A[POST /v1/export/pdf + PdfEditalRequest] --> B[require_auth]
    B --> C[plan_type from user]
    C --> D[bid_data = request.model_dump]
    D --> E[asyncio.wait_for asyncio.to_thread generate_edital_pdf, timeout=10]
    E -->|TimeoutError| X1[503 timeout PT-BR]
    E -->|Exception| X2[500 internal error]
    E -->|ok| F[pdf_bytes ReportLab Canvas]
    F --> G[_safe_filename objeto NFKD ASCII strip]
    G --> H[Response application/pdf attachment SmartLic_TITLE_DATE.pdf]
```

## OAuth Google linking flow

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Frontend
    participant API as Backend
    participant R as Redis
    participant G as Google OAuth

    U->>FE: Click 'Conectar Google Sheets'
    FE->>API: GET /api/auth/google
    API->>API: gen state random url-safe
    API->>R: SET oauth_state:{state} user_id ex=600
    API-->>FE: redirect to Google authorize_url
    FE->>G: browser navigates
    G->>U: consent screen
    U->>G: allow
    G->>API: GET /api/auth/google/callback?code&state
    API->>R: GET oauth_state:{state}
    R-->>API: user_id (or 403 invalid)
    API->>G: exchange code for tokens
    G-->>API: access_token + refresh_token
    API->>API: Fernet.encrypt refresh_token
    API->>API: INSERT user_oauth_credentials encrypted_refresh
    API-->>FE: redirect /conta?google=connected
```

## PDF visual layout (trial watermark)

```mermaid
flowchart TD
    A[Canvas A4 portrait] --> B[Header logo + SmartLic brand]
    B --> C[Title: objeto truncado 80 chars]
    C --> D[Metadata 2-col: orgao, UF, modalidade, valor, datas]
    D --> E[Viability box bg=color level]
    E --> F[AI summary section if resumo_executivo]
    F --> G[Recomendação section]
    G --> H{plan_type == free_trial?}
    H -->|sim| W[overlay watermark SMARTLIC TRIAL diagonal gray translucent]
    H -->|não| X[skip]
    W --> Z[footer page 1/1 + URL]
    X --> Z
    Z --> OUT[bytes output]
```
