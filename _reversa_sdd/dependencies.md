# Dependências — SmartLic

> Gerado pelo **Reversa Scout** em 2026-04-27
> Fontes: `backend/requirements.txt`, `backend/requirements-dev.txt`, `frontend/package.json`, `package.json` (root)

## Backend (Python 3.12)

### Runtime — `backend/requirements.txt`

| Pacote | Versão | Papel | Notas críticas |
|--------|--------|-------|----------------|
| fastapi | 0.136.0 | HTTP framework | — |
| uvicorn | 0.41.0 | ASGI server | **SEM `[standard]`** — uvloop causa SIGSEGV (CRIT-SIGSEGV-v2) |
| gunicorn | 23.0.0 | WSGI prefork | Opt-in via `RUNNER=gunicorn`; padrão é uvicorn spawn |
| pydantic[email] | 2.12.5 | Schema validation | — |
| pydantic-settings | 2.13.1 | Env config | — |
| starlette | 0.52.1 | ASGI core | — |
| python-multipart | >=0.0.22 | Form parsing | CVE-2026-24486 fix (STORY-279) |
| httpx | 0.28.1 | Async HTTP client | Usado em PNCP/PCP/ComprasGov clients |
| openpyxl | 3.1.5 | Excel | — |
| reportlab | 4.4.0 | PDF | Pure Python — Railway-safe |
| jsonschema | 4.24.0 | JSON Schema | Contract tests + PNCP canary shape drift |
| openai | 1.109.1 | LLM SDK | GPT-4.1-nano |
| supabase | 2.28.0 | Auth + DB | — |
| PyJWT | >=2.12.0,<3.0.0 | JWT validation | CVE-2026-32597 fix; ES256/JWKS |
| bcrypt | >=4.0.0,<5.0.0 | Password hash | MFA TOTP recovery codes (STORY-317) |
| stripe | 11.4.1 | Billing | — |
| redis | 5.3.1 | Cache + queue | Feature flag caching |
| google-api-python-client | 2.190.0 | Google APIs | Sheets export |
| google-auth | 2.48.0 | OAuth | — |
| google-auth-oauthlib | 1.3.1 | OAuth flow | — |
| google-auth-httplib2 | 0.3.0 | HTTP transport | — |
| cryptography | >=46.0.6,<47.0.0 | Crypto | **Pin OBRIGATÓRIO** — fork-safety com Gunicorn `--preload` |
| resend | >=2.0.0,<3.0.0 | Email | — |
| PyYAML | >=6.0,<7.0 | Sectors config | — |
| python-json-logger | >=2.0.4,<3.0.0 | Structured logs | STORY-220 |
| sentry-sdk[fastapi] | 2.52.0 | Error tracking | **Pin exato** — STORY-413 (StarletteIntegration regression 2026-04-10) |
| prometheus_client | >=0.20.0 | Metrics | — |
| arq | >=0.26,<1.0 | Job queue | Background LLM + Excel |
| opentelemetry-api | >=1.25,<2.0 | Tracing | — |
| opentelemetry-sdk | >=1.25,<2.0 | Tracing | — |
| opentelemetry-exporter-otlp-proto-http | >=1.25,<2.0 | OTLP HTTP | **NÃO** umbrella `opentelemetry-exporter-otlp` (puxa grpcio fork-unsafe) |
| opentelemetry-instrumentation-fastapi | >=0.46b0 | Auto-instrument | — |
| opentelemetry-instrumentation-httpx | >=0.46b0 | Auto-instrument | — |

### Pacotes deliberadamente removidos no Dockerfile (CRIT-041)
`grpcio`, `grpcio-status`, `opentelemetry-exporter-otlp-proto-grpc`, `opentelemetry-exporter-otlp` (umbrella), `httptools`, `uvloop` — todos fork-unsafe. `pip uninstall -y` no build.

### Dev — `backend/requirements-dev.txt`
SQLAlchemy + psycopg2-binary movidos para dev (STORY-201, ainda usados em `database.py` para compat de testes).

## Frontend (Node 18+, npm)

### Runtime — `frontend/package.json` `dependencies`

| Pacote | Versão |
|--------|--------|
| next | ^16.1.6 |
| react | ^18.3.1 |
| react-dom | ^18.3.1 |
| @supabase/ssr | ^0.8.0 |
| @supabase/supabase-js | ^2.99.3 |
| @sentry/nextjs | ^10.49.0 |
| @stripe/react-stripe-js | ^6.2.0 |
| @stripe/stripe-js | ^9.2.0 |
| framer-motion | ^12.38.0 |
| recharts | ^3.7.0 |
| swr | ^2.4.1 |
| @dnd-kit/core | ^6.3.1 |
| @dnd-kit/sortable | ^10.0.0 |
| @dnd-kit/utilities | ^3.2.2 |
| react-hook-form | ^7.73.1 |
| @hookform/resolvers | ^5.2.2 |
| zod | ^4.3.6 |
| @radix-ui/react-slot | ^1.2.4 |
| @tailwindcss/typography | ^0.5.19 |
| class-variance-authority | ^0.7.1 |
| clsx | ^2.1.1 |
| tailwind-merge | ^3.5.0 |
| date-fns | ^4.1.0 |
| react-day-picker | ^9.14.0 |
| react-markdown | ^10.1.0 |
| remark-gfm | ^4.0.1 |
| sonner | ^2.0.7 |
| nprogress | ^0.2.0 |
| use-debounce | ^10.1.0 |
| uuid | ^13.0.0 |
| web-vitals | ^5.2.0 |
| focus-trap-react | ^12.0.0 |
| lucide-react | ^0.563.0 |
| mixpanel-browser | ^2.74.0 |
| react-simple-pull-to-refresh | ^1.3.4 |

### Dev — `frontend/package.json` `devDependencies`

| Pacote | Versão |
|--------|--------|
| typescript | ^5.9.3 |
| jest | ^29.7.0 |
| @swc/jest | ^0.2.29 |
| jest-environment-jsdom | ^29.7.0 |
| jest-axe | ^10.0.0 |
| jest-junit | ^16.0.0 |
| @testing-library/react | ^14.1.2 |
| @testing-library/jest-dom | ^6.1.5 |
| @testing-library/user-event | ^14.5.1 |
| @playwright/test | ^1.58.2 |
| @axe-core/playwright | ^4.11.1 |
| @chromatic-com/playwright | ^0.13.1 |
| storybook | ^8.6.18 |
| @storybook/nextjs | ^8.6.18 |
| @storybook/react | ^8.6.18 |
| @storybook/react-webpack5 | ^8.6.18 |
| @lhci/cli | ^0.15.0 |
| @next/bundle-analyzer | ^16.2.4 |
| size-limit | ^11.2.0 |
| @size-limit/file | ^11.2.0 |
| openapi-typescript | ^7.13.0 |
| next-sitemap | ^4.2.3 |
| tailwindcss | ^3.4.19 |
| postcss | ^8.5.6 |
| autoprefixer | ^10.4.24 |
| eslint-plugin-local-rules | ^3.0.2 |
| @types/node | ^25.2.0 |
| @types/react | ^19.2.9 |
| @types/react-dom | ^19.2.3 |
| @types/jest-axe | ^3.5.9 |
| @types/js-yaml | ^4.0.9 |
| @types/nprogress | ^0.2.3 |
| @types/uuid | ^10.0.0 |
| js-yaml | ^4.1.1 |

### Engines
- node: `>=18.0.0`
- npm: `>=9.0.0`

## Root Monorepo (`package.json`)

```json
{
  "dependencies": { "ajv": "^8.17.1", "js-yaml": "^4.1.1", "yaml": "^2.8.2" }
}
```
Apenas utilitários para scripts de tooling raiz (sync-setores, validations).

## Pinning Strategy — Notas Críticas

1. **`uvicorn` SEM `[standard]`** — uvloop+chardet+hiredis causam SIGSEGV em produção.
2. **`cryptography` pinado <47.0** — fork-safety com OpenSSL bindings.
3. **`sentry-sdk[fastapi]==2.52.0` exato** — bumps automáticos quebraram prod (STORY-413).
4. **OpenTelemetry: NÃO umbrella** — apenas `otlp-proto-http`; `pip uninstall` remove gRPC chain no Dockerfile.
5. **`python-multipart>=0.0.22`** — CVE-2026-24486 (Path Traversal).
6. **`PyJWT>=2.12.0`** — CVE-2026-32597 (crit header bypass).

## Auditoria

- CI: `dep-scan.yml` (Dependabot + manual `pip-audit`)
- Pre-commit: `.pre-commit-config.yaml`
- CodeQL: `codeql.yml`
- Mutation testing: `mutation-testing.yml`

## Atualizações 2026-05-10/12

| Package | Versão Anterior | Versão Atual | PR |
|---------|----------------|--------------|-----|
| `arq` | ≥0.26 | **0.28.0** | #1083 |
| `opentelemetry-api` | ≥1.25 | **1.41.1** | #1082 |
| `opentelemetry-instrumentation-httpx` | ≥0.46b0 | **0.62b1** | #1081 |
| `resend` | ≥2.0.0 | **2.30.0** | #1080 |
| `pyyaml` | ≥6.0 | **6.0.3** | #1085 |
| `pyjwt` | ≥2.12.0 | **2.12.1** | #1084 |
| `mixpanel` | ≥4.10.0 | **4.11.1** | #1086 |
| `hypothesis` (dev) | ≥6.152.4 | **6.152.5** | #1088 |
| `python-multipart` | ≥0.0.27 | **0.0.28** | #1089 |
| `actions/checkout` | v4 | **v6** | #1092 |
| `actions/setup-python` | v5 | **v6** | #1093 |
| `actions/setup-node` | v4 | **v6** | #1090 |
| `supabase/setup-cli` | v1 | **v2** | #1091 |
| `dependabot/fetch-metadata` | v1 | **v3** | #1094 |
| `tailwind-merge` (frontend) | — | **3.6.0** | #1079 |
