---
paths:
  - "backend/tests/**"
  - "backend/**/*test*.py"
  - "frontend/__tests__/**"
  - "frontend/e2e-tests/**"
  - "**/*.test.ts"
  - "**/*.test.tsx"
  - "**/*.spec.ts"
---

# Testing Strategy — SmartLic

## Backend (backend/tests/)

**454 test files, 5131+ passing (last verified), 0 failures** — CI gate: `.github/workflows/backend-tests.yml`

**Zero-Failure Policy:** 0 failures is the only acceptable baseline. Fix them, never treat as "pre-existing".

**Key Testing Patterns (IMPORTANT — wrong mocks cause hard-to-debug failures):**
- Auth: Use `app.dependency_overrides[require_auth]` NOT `patch("routes.X.require_auth")`
- Cache: Patch `supabase_client.get_supabase` (not `search_cache.get_supabase`)
- Config: Use `@patch("config.FLAG_NAME", False)` not `os.environ`
- LLM: Mock at `@patch("llm_arbiter._get_client")` level
- Quota: Tests mocking `/buscar` MUST also mock `check_and_increment_quota_atomic`
- ARQ: Mock with `sys.modules["arq"]` (not installed locally). Conftest autouse fixture `_isolate_arq_module` handles cleanup automatically — do NOT do raw `sys.modules["arq"] = ...` without cleanup

**Anti-Hang Rules (CRITICAL — violations cause full-suite freezes):**
- **pytest-timeout**: Every test has a 30s timeout (`pyproject.toml`). Override with `@pytest.mark.timeout(60)` for slow integration tests
- **NEVER use `asyncio.get_event_loop().run_until_complete()`** in tests — use `async def` + `@pytest.mark.asyncio` instead
- **NEVER use `sys.modules["arq"] = MagicMock()`** without cleanup — the conftest fixture handles isolation automatically
- **Fire-and-forget tasks**: Conftest `_cleanup_pending_async_tasks` cancels lingering `asyncio.create_task()` after each test
- **subprocess in tests**: Always use `timeout` parameter in `Popen.communicate()` and clean up with `proc.kill()`
- **Full-suite validation**: Run `pytest --timeout=30 -q` periodically to catch hanging tests early
- **timeout_method = "thread"**: Required for Windows compatibility (signal method is Unix-only)

## Frontend (frontend/__tests__/)

**376 test files, 2681+ passing (last verified), 0 failures** — CI gate: `.github/workflows/frontend-tests.yml`

**jest.setup.js polyfills:** `crypto.randomUUID` + `EventSource` (jsdom lacks both)

## E2E (Playwright)

**60 critical user flow tests** in `frontend/e2e-tests/`. CI: `.github/workflows/e2e.yml`
