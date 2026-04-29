# Flowchart — Módulo `auth-oauth`

> Gerado pelo **Reversa Archaeologist** em 2026-04-27

## 1. JWT Validation Pipeline (cache 2-tier)

```mermaid
flowchart TD
  Req[HTTP Request com Bearer token] --> Hash[SHA256 do token completo · STORY-210 AC3]
  Hash --> L1{L1 OrderedDict hit?}
  L1 -->|sim, age <60s| MoveEnd[move_to_end · LRU refresh]
  MoveEnd --> Ret1[return user_data]
  L1 -->|não/expired| L2{L2 Redis hit?}
  L2 -->|sim, TTL 5min| Promote[promote para L1]
  Promote --> Ret2[return user_data]
  L2 -->|não| Strat[_get_jwt_key_and_algorithms]
  Strat --> S1{JWKS endpoint configurado?}
  S1 -->|sim| Jwks[PyJWKClient.get_signing_key_from_jwt → ES256]
  S1 -->|não| S2{SUPABASE_JWT_SECRET é PEM?}
  S2 -->|sim| Pem[ES256 com PEM public key]
  S2 -->|não| S3{SUPABASE_JWT_SECRET HS256?}
  S3 -->|sim| Hs[HS256 com symmetric secret]
  S3 -->|não| H401a[HTTP 401 Auth indisponível]
  Jwks --> Decode[jwt.decode · audience=authenticated]
  Pem --> Decode
  Hs --> Decode
  Decode -->|ExpiredSignatureError| H401b[HTTP 401 Token expirado]
  Decode -->|InvalidTokenError| H401c[HTTP 401 Token invalido]
  Decode -->|sucesso| Extract[user_id sub · email · role]
  Extract --> Store[L1.set + L2.setex fire-and-forget]
  Store --> Ret3[return user_data]
```

## 2. Authorization Roles

```mermaid
flowchart TD
  Auth[user_id autenticado] --> CB{Supabase CB aberto?}
  CB -->|sim| FailFast[return False, False · STORY-291]
  CB -->|não| Q[SELECT is_admin, plan_type FROM profiles]
  Q -->|404 missing column| Q2[SELECT plan_type only]
  Q -->|sucesso| Eval{is_admin=true?}
  Q2 --> Eval
  Eval -->|sim| Res1[is_admin=True, is_master=True · admin implies master]
  Eval -->|não| EvalM{plan_type=master?}
  EvalM -->|sim| Res2[is_admin=False, is_master=True]
  EvalM -->|não| Env{user_id em ADMIN_USER_IDS env?}
  Env -->|sim| Res3[bypass: is_admin=True, is_master=True]
  Env -->|não| Res4[is_admin=False, is_master=False]
```

## 3. Google OAuth Flow (Sheets export, STORY-180)

```mermaid
sequenceDiagram
  participant U as User
  participant FE as Frontend
  participant BE as Backend FastAPI
  participant G as Google OAuth
  participant DB as google_oauth_tokens
  U->>FE: Click "Conectar Google Sheets"
  FE->>BE: GET /google
  BE->>BE: state = secrets.token_urlsafe (CSRF)
  BE->>FE: 302 → Google authorize URL
  FE->>G: Authorize com scope=spreadsheets
  G->>BE: GET /google/callback?code=X&state=Y
  BE->>BE: validate state (CSRF check)
  BE->>G: POST /token (exchange code → access+refresh)
  G->>BE: tokens
  BE->>BE: Fernet.encrypt(access_token) + Fernet.encrypt(refresh_token)
  BE->>DB: INSERT user_id, encrypted_access, encrypted_refresh, expires_at
  BE->>FE: 302 → /conta?google=connected
  Note over BE,DB: Subsequent calls: decrypt + check expires_at; auto-refresh se expired
```

## 4. Frontend Middleware Decision Tree

```mermaid
flowchart TD
  Req[Request entrando] --> Headers[addSecurityHeaders · CSP enforcing + COOP + DNS-Prefetch off]
  Headers --> Path{pathname?}
  Path -->|começa com PUBLIC_ROUTES| Sess1{tem session?}
  Sess1 -->|sim| Redir1[redirect → /dashboard]
  Sess1 -->|não| Pass1[pass-through]
  Path -->|começa com PROTECTED_ROUTES| Sess2{tem session?}
  Sess2 -->|sim| Pass2[pass-through]
  Sess2 -->|não| Redir2[redirect → /login]
  Path -->|outras rotas| Pass3[pass-through]
```

**Protected routes:** `/buscar, /historico, /conta, /admin, /dashboard, /pipeline, /mensagens, /planos/obrigado`
**Public routes:** `/login, /signup, /planos, /auth/callback`
**Cacheable Cloudflare:** `/blog, /licitacoes, /glossario, /calculadora, /sobre, /cnpj, /features, /pricing`

## 5. CSP Header (DEBT-108 SEO-FIX hash-based)

```
Content-Security-Policy:
  default-src 'self';
  script-src 'self' 'unsafe-inline' https://js.stripe.com https://static.cloudflareinsights.com https://cdnjs.cloudflare.com https://cdn.sentry.io https://www.clarity.ms https://www.googletagmanager.com;
  style-src 'self' 'unsafe-inline';
  img-src 'self' data: https: blob:;
  font-src 'self' data:;
  connect-src 'self' https://*.supabase.co https://api.stripe.com https://*.railway.app https://*.ingest.sentry.io https://*.smartlic.tech https://api-js.mixpanel.com wss://*.supabase.co https://*.clarity.ms;
  frame-src 'self' https://js.stripe.com;
  object-src 'none';
  base-uri 'self';
  report-uri /api/csp-report;
  report-to csp-endpoint
```

`'unsafe-inline'` aceito como risk — Next.js 16 RSC inject inline scripts dinâmicos (industry consensus vercel/next.js#89754).
