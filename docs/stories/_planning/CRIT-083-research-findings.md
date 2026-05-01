# CRIT-083: Production Server Hardening — Research Findings

**Author:** @architect (Aria)
**Date:** 2026-03-23
**Status:** Research Complete

---

## Executive Summary

SmartLic's backend currently runs in **single-process uvicorn standalone mode** as an emergency fix for SIGSEGV crashes caused by Gunicorn's `os.fork()` interacting with `cryptography>=46` OpenSSL bindings. This document evaluates whether it is safe to re-enable multi-worker mode and what the optimal configuration is.

**Recommendation:** Re-enable multi-worker mode using **`uvicorn --workers 2`** (spawn-based, NOT Gunicorn fork-based). This eliminates all fork-safety concerns while restoring concurrency. Railway replicas (2 instances) can be added as a complementary layer for redundancy.

---

## Q1: Gunicorn + UvicornWorker Fork Safety

### Finding: Gunicorn ALWAYS uses `os.fork()` (pre-fork model)

Gunicorn's arbiter process calls `os.fork()` to create worker processes. This is fundamental to its architecture and cannot be changed. The `--preload` flag makes it worse by loading application code (including OpenSSL bindings) in the master process before forking, meaning forked workers inherit stale OpenSSL state.

**The specific failure chain in SmartLic:**
1. Gunicorn master loads `cryptography>=46` which initializes OpenSSL C bindings
2. `os.fork()` duplicates the process, but OpenSSL internal state (locks, PRNG, thread-local storage) is NOT safe to share across fork boundaries
3. When a forked worker processes an HTTP request that touches SSL/TLS (Supabase, Redis TLS, OpenAI API), OpenSSL encounters corrupted state and triggers SIGSEGV

**Without `--preload`**, each worker initializes OpenSSL independently after fork, which is safer but NOT guaranteed safe because:
- Python 3.12 emits `DeprecationWarning` for fork() in multi-threaded processes
- Any import that touches OpenSSL before the fork (even transitively via httpx, supabase-py, etc.) can trigger the issue
- The Gunicorn master itself may import modules that initialize OpenSSL during config loading

**Verdict:** Gunicorn pre-fork is inherently risky with `cryptography>=46`. The project's existing SIGSEGV history confirms this is not theoretical.

### Sources
- [Gunicorn issue #3289: Deprecation warning for os.fork on Python 3.12](https://github.com/benoitc/gunicorn/issues/3289)
- [Gunicorn issue #2761: Fork can eventually cause SIGSEGV on macOS](https://github.com/benoitc/gunicorn/issues/2761)
- [OpenSSL Wiki: Random fork-safety](https://wiki.openssl.org/index.php/Random_fork-safety)
- [pyca/cryptography FAQ](https://cryptography.io/en/latest/faq/)

---

## Q2: Gunicorn Prefork vs Spawn — Can Gunicorn Use Spawn?

### Finding: No. Gunicorn is fork-only by design.

Gunicorn has no option to use `multiprocessing.spawn()` instead of `os.fork()`. Its entire architecture is built around the pre-fork model. There is a GitHub issue (#3176) requesting spawn support for CUDA compatibility, but it has not been implemented.

**However, `uvicorn --workers N` uses `multiprocessing.spawn()`** — this is a critical difference:

| Server | Worker Creation | Fork-Safe? |
|--------|----------------|------------|
| `gunicorn -k uvicorn.workers.UvicornWorker` | `os.fork()` (pre-fork) | NO with cryptography |
| `uvicorn --workers N` | `multiprocessing.spawn()` | YES — clean process |
| `uvicorn` (standalone, no workers) | Single process | YES — no multi-process |

Uvicorn's spawn-based approach creates entirely new Python processes that re-import everything from scratch, avoiding all fork-unsafe state inheritance. This was confirmed in [uvicorn PR #672](https://github.com/encode/uvicorn/pull/672) which explicitly chose spawn for cross-platform safety.

**Trade-off:** Uvicorn's built-in process manager is less mature than Gunicorn's:
- No graceful worker recycling (`--max-requests` equivalent) — added in uvicorn 0.30.0+ via the new multiprocess manager
- Less sophisticated health monitoring of workers
- No equivalent of `gunicorn_conf.py` lifecycle hooks (when_ready, worker_abort, worker_exit)

**Mitigation:** Railway's own health checks, restart policies, and drain settings compensate for uvicorn's simpler process manager. The `gunicorn_conf.py` hooks are valuable for diagnostics but not critical for operation.

### Sources
- [Uvicorn PR #672: multiprocess spawn](https://github.com/encode/uvicorn/pull/672)
- [Uvicorn PR #2183: New multiprocess manager](https://github.com/encode/uvicorn/pull/2183)
- [Gunicorn issue #3176: Cannot use spawn start method](https://github.com/benoitc/gunicorn/issues/3176)
- [FastAPI docs: Server Workers](https://fastapi.tiangolo.com/deployment/server-workers/)

---

## Q3: Railway Multiple Instances (Replicas)

### Finding: YES — Railway supports horizontal scaling via replicas.

Railway allows configuring multiple replicas per service directly in the dashboard:

1. Go to **Service Settings > Deploy > Regions**
2. Increase replica count
3. Railway distributes traffic randomly across replicas (round-robin within a region)

**Key behaviors:**
- Scaling does NOT trigger a full redeploy — new replicas use the existing deployment image
- Removed replicas are drained gracefully (respects `drainingSeconds`)
- Each replica gets full resource allocation (not shared)
- Each replica is an independent process with its own memory and event loop

**Config-as-code:** Replicas can be configured in `railway.toml` under the deploy section, though the exact field name (`numReplicas`) should be verified against the latest Railway docs since the schema evolves.

**Cost:** Each replica is billed independently. 2 replicas = 2x compute cost.

**Recommendation for SmartLic:**
- **Phase 1:** Use `uvicorn --workers 2` within a single Railway instance (intra-process concurrency, no extra cost)
- **Phase 2:** If traffic grows, add a second Railway replica for true redundancy (2 instances x 2 workers = 4 concurrent request handlers)

### Sources
- [Railway Docs: Scaling](https://docs.railway.com/reference/scaling)
- [Railway Blog: So You Think You Can Scale?](https://blog.railway.com/p/launch-week-01-horizontal-scaling)
- [Railway Docs: Config as Code](https://docs.railway.com/reference/config-as-code)
- [Railway Docs: Optimize Performance](https://docs.railway.com/guides/optimize-performance)

---

## Q4: Hypercorn as Alternative

### Finding: Viable but not recommended — uvicorn with spawn is sufficient.

Hypercorn supports HTTP/1.1, HTTP/2, HTTP/3 (QUIC), and WebSockets. It uses `multiprocessing` for spawning workers (similar to uvicorn). However:

| Criterion | Uvicorn | Hypercorn |
|-----------|---------|-----------|
| Performance | Fastest (uvloop + httptools) | Slightly slower (~10-15%) |
| Protocol support | HTTP/1.1, WebSocket | HTTP/1.1, HTTP/2, HTTP/3, WebSocket |
| Worker model | spawn (safe) | multiprocessing (safe) |
| Ecosystem | Largest, best FastAPI integration | Smaller community |
| SSE support | Excellent | Good |
| Production maturity | Battle-tested | Less common in production |

**SmartLic does not need HTTP/2 or HTTP/3** (Railway's proxy terminates TLS). Uvicorn's performance advantage and ecosystem maturity make it the better choice. Since `uvicorn --workers` already uses spawn (not fork), there is no fork-safety advantage to switching to Hypercorn.

### Sources
- [Leapcell: Gunicorn, Uvicorn, Hypercorn comparison](https://leapcell.io/blog/gunicorn-uvicorn-hypercorn-choosing-the-right-python-web-server)
- [2024 Comparing ASGI Servers](https://medium.com/@onegreyonewhite/2024-comparing-asgi-servers-uvicorn-hypercorn-and-daphne-addb2fd70c57)
- [DeployHQ: Python Application Servers in 2026](https://www.deployhq.com/blog/python-application-servers-in-2025-from-wsgi-to-modern-asgi-solutions)

---

## Q5: jemalloc + cryptography SIGSEGV

### Finding: Known incompatibility — keep jemalloc disabled.

The Dockerfile already has jemalloc disabled with a comment explaining the issue. The root cause:

1. `LD_PRELOAD=libjemalloc.so.2` replaces glibc's `malloc()` globally
2. OpenSSL (via cryptography) uses internal memory allocation hooks that assume glibc malloc behavior
3. When Starlette's `BaseHTTPMiddleware` processes POST request bodies in a thread, OpenSSL's malloc hooks interact with jemalloc's thread-local caches, causing memory corruption
4. Result: SIGSEGV during POST body parsing (specifically auth endpoints in SmartLic's case)

**The jemalloc project was archived on June 2, 2025.** There will be no further fixes.

**Additional context:** The jemalloc issue tracker (#2472) documents segfaults when `LD_PRELOAD` is combined with `LD_AUDIT`, suggesting fundamental incompatibilities with certain library loading patterns.

**Verdict:** Keep jemalloc disabled. The RSS fragmentation benefit (~15-20% reduction) is not worth the SIGSEGV risk. Python 3.12's built-in pymalloc is adequate for SmartLic's workload.

### Sources
- [jemalloc issue #2472: LD_PRELOAD segfaults](https://github.com/jemalloc/jemalloc/issues/2472)
- [pyca/cryptography issue #3815: pip install segfault](https://github.com/pyca/cryptography/issues/3815)

---

## Recommendation: Proposed Configuration

### Strategy: `uvicorn --workers 2` (spawn-based, no Gunicorn)

This is the safest path to multi-worker concurrency:

1. **No fork()** — spawn creates clean processes, eliminating all cryptography/OpenSSL SIGSEGV risk
2. **No Gunicorn dependency** for worker management — Railway handles restarts and health checks
3. **No jemalloc** — keep it disabled permanently
4. **No `--preload`** — irrelevant since spawn re-imports everything per worker

### What We Lose (vs Gunicorn)

| Gunicorn Feature | Impact | Mitigation |
|-----------------|--------|------------|
| `gunicorn_conf.py` lifecycle hooks | No SIGSEGV/OOM diagnostics at worker level | Sentry + Railway restart logs |
| `--max-requests` worker recycling | No automatic memory leak mitigation | Railway restartPolicyType=ON_FAILURE + healthcheck |
| `worker_abort` timeout detection | No per-worker timeout logging | Uvicorn access logs + Sentry middleware |
| Graceful worker restart | Workers die ungracefully on OOM | Railway drainingSeconds=120 handles deploy drains |

### Proposed `railway.toml` startCommand

```toml
[deploy]
# CRIT-083: uvicorn spawn-based workers (NOT gunicorn fork).
# spawn creates clean processes — eliminates cryptography/OpenSSL SIGSEGV.
# 2 workers on Railway 1GB is safe (each ~200-300MB with in-memory cache).
startCommand = "sh -c 'uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --timeout-keep-alive 75 --workers ${WEB_CONCURRENCY:-2}'"
```

### Proposed `start.sh` Changes

Update the `web` case to use `uvicorn --workers` as default:

```bash
case "$PROCESS_TYPE" in
  web)
    WORKERS="${WEB_CONCURRENCY:-2}"
    echo "Starting web process (uvicorn spawn-based, workers=${WORKERS})..."
    exec uvicorn main:app \
      --host "0.0.0.0" \
      --port "${PORT:-8000}" \
      --log-level "${UVICORN_LOG_LEVEL:-info}" \
      --timeout-keep-alive "${GUNICORN_KEEP_ALIVE:-75}" \
      --workers "${WORKERS}"
    ;;
```

### Is it safe to enable 2 workers NOW?

**Yes, with caveats:**

1. **Memory budget:** Railway 1GB container with 2 uvicorn workers. Each SmartLic worker uses ~200-300MB (FastAPI + in-memory cache + httpx connection pools). 2 workers = ~500-600MB, leaving ~400MB headroom. This is tight but workable if `WEB_CONCURRENCY` is kept at 2.

2. **In-memory cache duplication:** Each spawn-based worker has its own `InMemoryCache` instance. This means 2x memory for cached data and cache misses on the "wrong" worker. This is acceptable because L2 (Supabase) provides cross-worker consistency.

3. **SSE progress tracking:** The `asyncio.Queue`-based progress tracker in `progress.py` is per-process. If POST `/buscar` hits worker 1 and GET `/buscar-progress/{id}` hits worker 2, the SSE stream will not find the tracker. **This is a pre-existing issue** that also affects Railway replicas. Mitigation: Railway's random load balancing means the same client often hits the same worker for short-lived connections, but this is NOT guaranteed.

4. **Testing plan:**
   - Deploy with `WEB_CONCURRENCY=2` to staging/preview environment first
   - Run 10 concurrent searches and verify SSE progress works
   - Monitor memory via Railway metrics for 24h
   - Check Sentry for any new SIGSEGV or unexpected crashes
   - If SSE issues appear, consider Redis-backed progress tracker (CRIT-083-FOLLOWUP)

### Phase 2: Railway Replicas (Future)

Once `uvicorn --workers 2` is validated in production:
- Add a second Railway replica via dashboard (Settings > Deploy > Regions > increase count to 2)
- This gives 2 instances x 2 workers = 4 total concurrent request handlers
- Requires Redis-backed SSE progress tracker to work correctly across instances (current in-memory Queue won't work cross-instance)

---

## Risk Matrix

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| SIGSEGV with uvicorn spawn | Very Low | High | spawn avoids fork entirely; no OpenSSL state inheritance |
| OOM with 2 workers on 1GB | Medium | Medium | Monitor RSS; fallback to WEB_CONCURRENCY=1 |
| SSE progress lost cross-worker | Medium | Low | Pre-existing issue; Railway random LB often routes same client to same worker |
| Worker crash without Gunicorn hooks | Low | Low | Sentry + Railway restart policy compensate |
| jemalloc re-enabled accidentally | Low | High | Dockerfile comment + this doc as reference |

---

## Decision Log

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Use `uvicorn --workers` not `gunicorn -k UvicornWorker` | spawn vs fork eliminates SIGSEGV root cause |
| 2 | Keep jemalloc permanently disabled | Project archived, known incompatibility with OpenSSL |
| 3 | Default to 2 workers (not 1, not 4) | Balance concurrency vs 1GB memory budget |
| 4 | Skip Hypercorn | No fork-safety advantage over uvicorn spawn; lower perf |
| 5 | Defer Railway replicas to Phase 2 | Requires Redis-backed SSE tracker first |
| 6 | Keep `start.sh` Gunicorn path as opt-in (`RUNNER=gunicorn`) | Backward compatibility for testing |
