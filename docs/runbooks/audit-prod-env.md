# Audit Railway Prod Env Vars (RES-BE-013)

**Workflow:** `.github/workflows/audit-prod-env.yml`
**Script:** `.github/scripts/audit_prod_env.py`
**Lists:** `.github/audit/prod-env-blocklist.txt`, `.github/audit/prod-env-allowlist.txt`
**Origin:** memory `feedback_audit_env_vars_after_incident` — 2026-04-27 P0 Stage 2 found `PYTHONASYNCIODEBUG=1` in `bidiq-backend` prod with no PR trail.

---

## What this gate does

| Trigger | Behaviour |
|---|---|
| PR touches audit lists/scripts/workflow | Runs unit tests on the script (no Railway call). |
| Daily 14:00 UTC cron | Runs full audit against `bidiq-backend` and `bidiq-frontend`. Fails (exit 1) if any blocklisted var exists in prod. Emits `::warning::` for vars not in allowlist. |
| `workflow_dispatch` | Same as cron, with optional `service` input. |

The gate is **not** wired into `deploy.yml`. Hard-blocking deploys on env audit risks paging incident response when an operator legitimately needs to set a debug var temporarily. Detection + alert is the contract here, not enforcement.

---

## Run locally

```bash
# Audit live Railway prod (requires RAILWAY_TOKEN + railway CLI on PATH)
python3 .github/scripts/audit_prod_env.py --service bidiq-backend
python3 .github/scripts/audit_prod_env.py --service bidiq-frontend

# Audit a captured snapshot (offline, no Railway call)
railway variables --service bidiq-backend --kv > /tmp/backend.env
python3 .github/scripts/audit_prod_env.py --from-file /tmp/backend.env

# Strict mode: allowlist drift also fails (CI uses advisory by default)
python3 .github/scripts/audit_prod_env.py --from-file /tmp/backend.env --strict-allowlist

# JSON output (machine-readable)
python3 .github/scripts/audit_prod_env.py --service bidiq-backend --json
```

---

## When the gate fires

### Blocklist hit (`::error::`, exit 1)

A var listed in `prod-env-blocklist.txt` (or matching a wildcard there) is set on a Railway service.

**Action:**
1. Check Railway audit log: `railway logs --service <svc>` and the dashboard *Activity* tab — find who set the var, when, why.
2. If legitimate (e.g. on-call needed `DEBUG=true` to diagnose an incident), capture the diagnostic, then `railway variables --service <svc> --remove <KEY>`.
3. If the var is deemed acceptable in prod (rare), open a PR removing the entry from the blocklist with @architect + @devops review.

### Allowlist drift (`::warning::`, exit 0 by default)

A var is set on Railway that is not listed in `prod-env-allowlist.txt`.

**Action:**
1. If the var is new and legitimate (e.g. you just shipped a feature flag), open a PR adding it to the allowlist.
2. If the var is unknown / orphaned (set during a long-gone experiment), `railway variables --service <svc> --remove <KEY>`.

The allowlist is **advisory**, not exhaustive. Drift is expected as features ship; the warning exists so unknown vars don't sit in prod indefinitely.

---

## Adding entries to the lists

| List | Path | Adding requires |
|---|---|---|
| Blocklist | `.github/audit/prod-env-blocklist.txt` | PR review by `@architect` + `@devops` |
| Allowlist | `.github/audit/prod-env-allowlist.txt` | PR review by `@devops` |

Format:
- one var per line, exact match (case-sensitive) by default
- `*` suffix is wildcard (`TRACE_*` matches `TRACE_FOO`, `TRACE_BAR`)
- comments start with `#`

---

## Why this exists (incident memory)

> 2026-04-27 P0 Stage 2: `PYTHONASYNCIODEBUG=1` discovered in `bidiq-backend`
> prod during recovery. The flag serializes async execution and amplifies
> saturation under load. Nobody knew when or why it was set. Memory
> `feedback_audit_env_vars_after_incident`: "debug flags persist unnoticed.
> `--kv | grep -iE 'DEBUG|DEV|TRACE'` before declaring recovery."

This gate operationalises that memory as a system: lists are versioned, drift is auditable, blocklist regressions fail CI.

---

## Rollback

Revert the PR. There is no runtime change — only CI/docs. To temporarily silence the gate, set the workflow `on:` trigger to `workflow_dispatch:` only (manual-only).
