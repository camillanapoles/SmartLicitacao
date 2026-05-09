# Security Test Baseline (SEC-TEST-2026-001)

**Status:** Active
**Owner:** @qa + @dev
**Substitui:** Issue #201 TD-TEST-003 (Security Vulnerability Tests Missing — escopo monolítico >5d, fechado 2026-05-08)
**Reversa anchor:** `_reversa_sdd/review-report.md §10.4` test/CI + RBAC/Security
**OWASP refs:** [Top-10 2021](https://owasp.org/Top10/) + [Top-10 2025 release candidate](https://owasp.org/www-project-top-ten/)

---

## Por quê uma baseline (vs comprehensive suite)

Issue #201 propunha "comprehensive security test suite" — escopo monolítico (>5d) que nunca foi shipped. Esta baseline cobre **as 5 classes de vetor mais prováveis no SmartLic** em ~1d de implementação, deixando extensão futura (Top-6 a Top-10) explicitamente delegada a SEC-TEST-002+.

Trade-off consciente: baseline early > comprehensive never. Cada tentativa monolítica de "everything-at-once" historicamente vira backlog que nunca executa (vapor x5 — ver §11 da review-report).

---

## Cobertura — 5 classes (mapped to OWASP Top-10 2021)

| # | Classe | OWASP 2021 | Arquivo | # tests | Estratégia |
|---|--------|------------|---------|---------|-----------|
| 1 | Auth bypass | A01 (Broken Access) + A07 (Auth Failures) | `test_auth_bypass.py` | 10 | JWT signature tamper (full-replacement, NÃO single-char flip — memory `feedback_jwt_base64url_flaky_test`); claim tamper (alg=none, expired, wrong-aud); role escalation via `require_admin` UUID allowlist |
| 2 | SQL Injection | A03 (Injection) | `test_sqli_fuzz.py` | 32 | 10 OWASP payloads × type-constrained Pydantic fields (UUID, int) → `ValidationError`; free-text fields → preserved verbatim (parametrized via supabase-py bind vars); regex allowlist for admin search (Issue #205) |
| 3 | SSRF | A10 (SSRF) | `test_ssrf_external_fetch.py` | 12 | **Regression guards**: `BASE_URL` é constante hardcoded (`https://pncp.gov.br/...`), construtores não aceitam `url=`/`base_url=` kwargs, env override não é honrado em re-import. Payload library completa para SEC-TEST-002 (file://, loopback v4/v6, AWS IMDS 169.254.169.254, gopher) — pronta quando user-supplied URL surface for adicionada |
| 4 | Stripe webhook spoof | A02 (Crypto Failures) + A08 (Integrity) | `test_stripe_webhook_spoof.py` | 8 | Header ausente → 400; `SignatureVerificationError` (forge + replay 5min tolerance) → 400; envelope sem id/type → 400; secret `None` → 400 (não bypass) |
| 5 | Rate-limit bypass | A04 (Insecure Design) | `test_rate_limit_bypass.py` | 7 | **Property test**: JWT presente → bucket `user:{sub}` (XFF spoofing NÃO escapa per-user bucket); JWT malformado → fallback seguro a IP, sem crash; flag disable só via deploy-time config (header injection sem efeito); 429 levanta HTTPException, nunca silently passes |

**Total: 69 tests passing** (≥25 floor — story DoD +176%; advisor pediu margem confortável para 1 flaky não quebrar gate).

### Por que SSRF é regression-guard, não fuzz

Auditoria do código real (advisor-confirmed): `clients/pncp/{async,sync}_client.py`, `portal_compras_client.py`, `compras_gov_client.py` usam `BASE_URL` hardcoded. Não há parâmetro de URL controlável pelo usuário no fetcher surface. Fuzzing payloads contra um input que não existe seria security theater.

A pivot honesta: assert que **a propriedade que torna SSRF impossível continua verdadeira** — se um futuro PR adicionar `url=` kwarg ou `os.getenv("PNCP_BASE_URL")`, o teste quebra antes do regression shipar.

Quando user-supplied URLs forem introduzidos em `auth_oauth.py::redirect_uri`, `export_sheets.py::spreadsheet_url`, ou `intel_reports.py::pdf_url`, SEC-TEST-002 vai exercer a payload library completa contra eles.

### Por que rate-limit bypass por XFF não é "bug"

`_get_client_ip` lê XFF first-value — comportamento **correto** atrás do Railway proxy (Railway popula XFF, não a app). Defesa real está na chave de bucket: quando há JWT, key é `user:{sub}` e XFF não importa. Property asserted: `test_authenticated_xff_spoof_does_not_bypass_user_bucket`.

Para endpoints unauth, XFF-trust é by-design. Defesa-em-profundidade futura (Cloudflare Turnstile, validação de Railway-trust-proxy boundary) fica em SEC-TEST-002+.

---

## CI Gate (AC2)

`.github/workflows/security-tests.yml` roda em cada PR contra `main`:
- `pytest backend/tests/security/ -v --timeout=30`
- Coverage report **dedicated** (`--cov=auth --cov=admin --cov=rate_limiter --cov=webhooks/stripe.py`) — não mistura com `backend-tests.yml` general suite
- Fail PR se qualquer test FAIL (zero-failure policy)
- Artefato `security-coverage.xml` retido 30d para audit

---

## Roadmap — extensão futura

| Story | Escopo | Trigger |
|-------|--------|---------|
| **SEC-TEST-002** | OWASP A05 (Misconfig) + A06 (Vulnerable Components) | Após pip-audit baseline shipped (DEBT-123 AC1 já ativo — só falta extension test) |
| **SEC-TEST-003** | OWASP A09 (Logging & Monitoring Failures) | Após Sentry frontend quiescent investigation (SMARTLIC-FE-F) |
| **SEC-TEST-004** | A02 expand: secrets-at-rest, key rotation, Fernet validation | Antes de growth scale (n≥30 paid users) |
| **SEC-TEST-005** | SSRF actual fuzz quando user-supplied URLs forem introduzidos | Trigger: PR introduzindo `url=` user param |
| **SEC-TEST-006** | RBAC org cross-tenant deep tests | Após RBAC-ORG-002 propagation completo |

Cada story ≤ 1d (ATOMIC). Anti-monolítico — lição #201.

---

## Mapeamento OWASP Top-10 2021/2025

| OWASP # | 2021 | 2025 RC | Cobertura SEC-TEST-2026-001 |
|---------|------|---------|------------------------------|
| A01 | Broken Access Control | Broken Access Control | ✅ test_auth_bypass (role escalation) |
| A02 | Cryptographic Failures | Cryptographic Failures | ✅ test_stripe_webhook_spoof (HMAC sig) |
| A03 | Injection | Injection | ✅ test_sqli_fuzz |
| A04 | Insecure Design | Insecure Design | ✅ test_rate_limit_bypass |
| A05 | Security Misconfiguration | Security Misconfiguration | ⏳ SEC-TEST-002 (audit-prod-env CI gate parcial via RES-BE-013) |
| A06 | Vulnerable Components | SCM Failures (NEW 2025) | ⏳ SEC-TEST-002 (pip-audit ativo) |
| A07 | Identification & Auth Failures | Identification & Auth Failures | ✅ test_auth_bypass (JWT) |
| A08 | Software & Data Integrity | Software Supply Chain (NEW 2025) | ✅ test_stripe_webhook_spoof (replay) |
| A09 | Logging & Monitoring Failures | Logging Failures | ⏳ SEC-TEST-003 |
| A10 | SSRF | SSRF | ✅ test_ssrf_external_fetch (regression guards) |

Cobertura baseline: **6/10 categorias**, todas P1.
