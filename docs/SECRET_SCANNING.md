# Secret Rotation Procedures

**Generated:** 2026-05-12
**Source:** RBAC-SEC-002 (#1152)

Procedures for rotating production secrets used by the SmartLic platform. Each
section covers one secret: where it is stored, rotation frequency recommendation,
step-by-step rotation procedure, and verification steps.

---

## 1. SUPABASE_ACCESS_TOKEN

### Where Used

| Location | Purpose |
|----------|---------|
| Railway `bidiq-backend` env vars | Used by `backend/scripts/audit_rls_coverage.py` (RLS audit) |
| GitHub Actions secrets (`SUPABASE_ACCESS_TOKEN`) | Used by CI workflows (`migration-check.yml`, `deploy.yml`, `audit-rls-coverage.yml`, `migration-gate.yml`) |
| Local `.env` | Development RLS audits |

### Rotation Frequency

Quarterly (or immediately on suspected compromise).

### Rotation Procedure

1. **Generate new token** in [Supabase Dashboard](https://supabase.com/dashboard/project/fqqyovlzdzimiwfofdjk/settings/api):
   - Settings > API > `service_role` or access token section
   - Click "Reveal" next to existing token, then "Generate new token"

2. **Rotate in Railway**:
   ```bash
   railway variables set SUPABASE_ACCESS_TOKEN=<new-token>
   ```

3. **Rotate in GitHub**:
   ```bash
   gh secret set SUPABASE_ACCESS_TOKEN --repo tjsasakifln/SmartLic --body "<new-token>"
   ```

4. **Update local `.env`**:
   ```bash
   # Edit .env manually — do NOT commit the file
   ```

### Verification

```bash
# Verify via Supabase Management API (from project root)
SUPABASE_ACCESS_TOKEN=<new-token> SUPABASE_PROJECT_REF=fqqyovlzdzimiwfofdjk python3 backend/scripts/audit_rls_coverage.py --no-write
# Expected: exit code 0, "compliant=59" or similar
```

---

## 2. OPENAI_API_KEY

### Where Used

| Location | Purpose |
|----------|---------|
| Railway `bidiq-backend` env vars | GPT-4.1-nano classification + executive summaries |
| Railway `bidiq-worker` env vars | Background ARQ jobs (LLM summaries, batch classification) |
| GitHub Actions secrets (`OPENAI_API_KEY`) | CI integration tests |
| Local `.env` | Development LLM calls |

### Rotation Frequency

Quarterly (or immediately on suspected compromise). OpenAI API keys are
project-scoped (not user-scoped), so rotation invalidates the old key for all
services using it.

### Rotation Procedure

1. **Generate new key** in [OpenAI Dashboard](https://platform.openai.com/api-keys):
   - Create a new project key for the `SmartLic` project
   - Set appropriate rate limits

2. **Rotate in Railway** (both services):
   ```bash
   railway variables set --service bidiq-backend OPENAI_API_KEY=<new-key>
   railway variables set --service bidiq-worker OPENAI_API_KEY=<new-key>
   ```

3. **Rotate in GitHub**:
   ```bash
   gh secret set OPENAI_API_KEY --repo tjsasakifln/SmartLic --body "<new-key>"
   ```

4. **Update local `.env`**.

### Verification

```bash
# Verify by running a classification test
cd backend && python3 -c "
import os
from openai import OpenAI
client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])
resp = client.chat.completions.create(
    model='gpt-4.1-nano',
    messages=[{'role': 'user', 'content': 'Respond with OK'}],
    max_tokens=10
)
print(f'OpenAI OK: {resp.choices[0].message.content}')
"
```

---

## 3. STRIPE_WEBHOOK_SECRET

### Where Used

| Location | Purpose |
|----------|---------|
| Railway `bidiq-backend` env vars (`STRIPE_WEBHOOK_SECRET`) | Verifying Stripe webhook signatures on `/webhooks/stripe` |
| Railway `bidiq-backend` env vars (`STRIPE_SECRET_KEY`) | Stripe API operations (checkout, subscriptions) |
| Stripe Dashboard Webhook settings | Must match the endpoint secret configured in Stripe |

### Rotation Frequency

Quarterly (or immediately on suspected compromise). Both `STRIPE_WEBHOOK_SECRET`
and `STRIPE_SECRET_KEY` should be rotated together since a compromise of one
implies the other may also be compromised.

### Rotation Procedure

1. **Regenerate webhook secret in Stripe Dashboard**:
   - Login to [Stripe Dashboard](https://dashboard.stripe.com/webhooks)
   - Select the endpoint for `https://api.smartlic.tech/webhooks/stripe`
   - Click "Reveal" → "Regenerate signing secret"

2. **Rotate Stripe secret key** (if needed):
   - Developers > API keys
   - Click "Rotate live secret key"

3. **Rotate in Railway**:
   ```bash
   railway variables set STRIPE_WEBHOOK_SECRET=<new-secret>
   railway variables set STRIPE_SECRET_KEY=<new-key>
   ```

4. **Update local `.env`**.

### Verification

```bash
# Trigger a test webhook from Stripe Dashboard
# Or use Stripe CLI:
stripe trigger payment_intent.succeeded
# Verify no 400/401 errors in backend logs
```

---

## 4. RESEND_API_KEY

### Where Used

| Location | Purpose |
|----------|---------|
| Railway `bidiq-backend` env vars | Sending transactional emails (welcome, billing, alerts, trial emails) |
| GitHub Actions secrets (`RESEND_API_KEY`) | CI notification emails (e.g. migration failure alerts, STORY-1.5) |
| Local `.env` | Development email testing |

### Rotation Frequency

Semi-annually (or immediately on suspected compromise).

### Rotation Procedure

1. **Generate new key** in [Resend Dashboard](https://resend.com/api-keys):
   - Create a new API key with `email` scope
   - Optionally restrict to `smartlic.tech` sending domain

2. **Rotate in Railway**:
   ```bash
   railway variables set RESEND_API_KEY=<new-key>
   ```

3. **Rotate in GitHub**:
   ```bash
   gh secret set RESEND_API_KEY --repo tjsasakifln/SmartLic --body "<new-key>"
   ```

4. **Update local `.env`**.

### Verification

```bash
# Send a test email via Resend API
curl -s -X POST "https://api.resend.com/emails" \
  -H "Authorization: Bearer <new-key>" \
  -H "Content-Type: application/json" \
  -d '{"from":"tiago@smartlic.tech","to":"tiago.sasaki@gmail.com","subject":"Test","text":"Rotation verification"}'
# Expected: HTTP 200 with {"id": "..."}
```

---

## 5. SENTRY_DSN

### Where Used

| Location | Purpose |
|----------|---------|
| Railway `bidiq-backend` env vars (`SENTRY_DSN`) | Error tracking (backend: project 4509666928623616) |
| Railway `bidiq-frontend` env vars (`SENTRY_DSN`) | Error tracking (frontend: project 4510878216224768) |
| GitHub Actions secrets (`SENTRY_DSN_BACKEND`, `SENTRY_DSN_FRONTEND`) | CI Sentry profiling |

### Rotation Frequency

Only on suspected compromise or project migration. Resend is idempotent —
multiple DSNs can be active simultaneously.

### Rotation Procedure

1. **Create new DSN** in [Sentry](https://sentry.smartlic.tech/settings/projects/):
   - Navigate to each project (SmartLic Backend / SmartLic Frontend)
   - Settings > Client Keys (DSN)
   - Create new key, copy the DSN

2. **Rotate in Railway**:
   ```bash
   railway variables set SENTRY_DSN=<new-dsn>
   ```

3. **Rotate in GitHub**:
   ```bash
   gh secret set SENTRY_DSN_BACKEND --repo tjsasakifln/SmartLic --body "<new-dsn-backend>"
   gh secret set SENTRY_DSN_FRONTEND --repo tjsasakifln/SmartLic --body "<new-dsn-frontend>"
   ```

4. **Wait 24h**, then delete the old DSN key from Sentry.

### Verification

```bash
# Trigger a test error in staging to verify the new DSN
# Or check Sentry > Project Settings > Client Keys for recent events on the new key
```

---

## 6. SEED_ADMIN_PASSWORD / SEED_MASTER_PASSWORD

### Where Used

| Location | Purpose |
|----------|---------|
| Railway `bidiq-backend` env vars | Seed scripts (`backend/seed_users.py`) for initial admin/master account creation |
| Not in CI or local `.env.example` | Deliberately excluded from CI; local dev uses `getpass` interactive prompt |

### Rotation Frequency

On every new environment bootstrap (staging, production). These are not runtime
secrets — they are used only during user seeding and can be discarded afterwards.

### Rotation Procedure

1. **Generate new passwords**:
   ```bash
   openssl rand -base64 18 | tr -d '+/'  # Secure 24-char password
   ```

2. **Set in Railway**:
   ```bash
   railway variables set SEED_ADMIN_PASSWORD=<new-password>
   railway variables set SEED_MASTER_PASSWORD=<new-password>
   ```

3. **Run seed script** (one-time):
   ```bash
   cd backend && python3 seed_users.py
   ```

4. After successful seeding, the environment variables can be **removed** from
   Railway (`railway variables remove SEED_ADMIN_PASSWORD`) — they are only
   read by `seed_users.py`, not by the running application.

### Verification

```bash
# Log in as admin/master user via Supabase Auth
# Verify the profile is created with correct role flags
```

---

## Cross-Cutting: Local `.env` Hygiene

Never commit `.env` to the repository. The file is git-ignored (`backend/.gitignore`
and root `.gitignore` should include `.env`). If `.env` must be shared (e.g. for
onboarding), use `.env.example` with placeholder values.

### Check for Accidental Exposure

```bash
# Check if .env was ever committed
git log --all --diff-filter=A -- .env
# If found, rotate ALL secrets immediately and consult GitHub support
# to purge the commit from history.
```

---

## CI Secret Inventory

Secrets configured in GitHub Actions (`<https://github.com/tjsasakifln/SmartLic/settings/secrets/actions>`):

| Secret | Used In |
|--------|---------|
| `SUPABASE_ACCESS_TOKEN` | `migration-check.yml`, `deploy.yml`, `audit-rls-coverage.yml`, `migration-gate.yml` |
| `SUPABASE_DB_URL` | `deploy.yml` (NOTIFY pgrst) |
| `OPENAI_API_KEY` | CI integration tests |
| `STRIPE_TEST_WEBHOOK_SECRET` | CI stripe billing tests |
| `RESEND_API_KEY` | CI notification emails (migration failure alerts) |
| `SENTRY_DSN_BACKEND` | CI Sentry profiling |
| `SENTRY_DSN_FRONTEND` | CI Sentry profiling |
