#!/bin/bash
# =============================================================================
# GTM-RESILIENCE-F01 AC6: Multi-process start script
# =============================================================================
# Supports two modes via PROCESS_TYPE env var:
#   web (default): Gunicorn + Uvicorn workers (FastAPI)
#   worker:        ARQ background job worker (LLM + Excel)
#
# Railway deployment: Create two services from the same Dockerfile,
# setting PROCESS_TYPE=web for one and PROCESS_TYPE=worker for the other.

set -e

PROCESS_TYPE="${PROCESS_TYPE:-web}"

case "$PROCESS_TYPE" in
  web)
    # CRIT-083: RUNNER=uvicorn (default) uses uvicorn spawn-based workers — SAFE with cryptography>=46.
    # spawn() creates clean processes; no fork() → no OpenSSL state corruption → no SIGSEGV.
    # RUNNER=gunicorn (opt-in) uses gunicorn prefork model — kept for comparison only.
    RUNNER="${RUNNER:-uvicorn}"

    if [ "$RUNNER" = "uvicorn" ]; then
      WORKERS="${WEB_CONCURRENCY:-2}"
      # SEN-BE-010 + ADR-MEMORY-BUDGET: time-based rotation (Component A) — workers
      # exit + restart after N requests so memory leaks don't accumulate. Uvicorn
      # respects --limit-max-requests like gunicorn --max-requests.
      LIMIT_MAX_REQUESTS="${GUNICORN_MAX_REQUESTS:-10000}"
      echo "Starting web process (uvicorn spawn-based workers=${WORKERS})..."
      echo "  CRIT-083: spawn() avoids os.fork() — eliminates cryptography/OpenSSL SIGSEGV."
      echo "  Cross-worker SSE: Redis Streams (STORY-276). Graceful timeout: 120s."
      echo "  host=0.0.0.0, port=${PORT:-8000}, workers=${WORKERS}, keep-alive=${GUNICORN_KEEP_ALIVE:-75}s"
      echo "  ADR-MEMORY-BUDGET rotation: limit_max_requests=${LIMIT_MAX_REQUESTS}"

      exec uvicorn main:app \
        --host "0.0.0.0" \
        --port "${PORT:-8000}" \
        --log-level "${UVICORN_LOG_LEVEL:-info}" \
        --timeout-keep-alive "${GUNICORN_KEEP_ALIVE:-75}" \
        --workers "${WORKERS}" \
        --limit-max-requests "${LIMIT_MAX_REQUESTS}" \
        --timeout-graceful-shutdown 120
    fi

    echo "Starting web process (gunicorn + uvicorn workers — opt-in via RUNNER=gunicorn)..."

    # STORY-303: --preload DISABLED by default (was true in CRIT-010).
    # cryptography>=46.0.5 + --preload causes SIGSEGV: OpenSSL initialized in master
    # pre-fork becomes invalid in forked workers. Without preload, each worker
    # initializes its own OpenSSL — safe. CRIT-010 404s mitigated by:
    #   1. Railway healthcheckTimeout=300s (no traffic until health check passes)
    #   2. /health ready:false flag during startup (main.py lifespan gate)
    #   3. Frontend BackendStatusIndicator handles transient unavailability
    PRELOAD_FLAG=""
    if [ "${GUNICORN_PRELOAD:-false}" = "true" ]; then
      PRELOAD_FLAG="--preload"
      echo "  WARNING: --preload enabled — verify cryptography fork-safety!"
    fi

    # SLA-002: WEB_CONCURRENCY 4→2 (Railway 1GB can't sustain 4 FastAPI workers
    # with in-memory caches + cron jobs + warmup — causes OOM kills).
    # --max-requests 1000 + jitter 50: recycle workers to prevent memory leaks.
    # GTM-INFRA-001 AC7/AC8: timeout=110s default (< Railway hard timeout 120s — prevents silent request death, TD-015).
    # CRIT-034 AC5+AC7: -c gunicorn_conf.py for worker lifecycle hooks.
    # DEBT-124: Align gunicorn graceful_timeout with GRACEFUL_SHUTDOWN_TIMEOUT (default 30s)
    # DEBT-04 AC1: GUNICORN_TIMEOUT=110 (< Railway 120s) to ensure workers abort before Railway kills the connection.
    GUNICORN_GRACEFUL_TIMEOUT="${GUNICORN_GRACEFUL_TIMEOUT:-${GRACEFUL_SHUTDOWN_TIMEOUT:-30}}"
    # SEN-BE-010 + ADR-MEMORY-BUDGET Component A: time-based rotation 10k/1k jitter
    # (was 1000/50 — too tight for sustained traffic + amplified leak detection).
    # Memory `feedback_pool_leak_caller_timeout_vs_sql_timeout` 5.5GB Stage 4-7.
    GUNICORN_MAX_REQUESTS_DEFAULT=10000
    GUNICORN_MAX_REQUESTS_JITTER_DEFAULT=1000
    echo "  timeout=${GUNICORN_TIMEOUT:-110}s, workers=${WEB_CONCURRENCY:-2}, graceful=${GUNICORN_GRACEFUL_TIMEOUT}s, keep-alive=${GUNICORN_KEEP_ALIVE:-75}s"
    echo "  ADR-MEMORY-BUDGET: max-requests=${GUNICORN_MAX_REQUESTS:-$GUNICORN_MAX_REQUESTS_DEFAULT}, jitter=${GUNICORN_MAX_REQUESTS_JITTER:-$GUNICORN_MAX_REQUESTS_JITTER_DEFAULT}"

    exec gunicorn main:app \
      -k uvicorn.workers.UvicornWorker \
      -w "${WEB_CONCURRENCY:-2}" \
      --bind "0.0.0.0:${PORT:-8000}" \
      --timeout "${GUNICORN_TIMEOUT:-110}" \
      --graceful-timeout "${GUNICORN_GRACEFUL_TIMEOUT}" \
      --keep-alive "${GUNICORN_KEEP_ALIVE:-75}" \
      --max-requests "${GUNICORN_MAX_REQUESTS:-$GUNICORN_MAX_REQUESTS_DEFAULT}" \
      --max-requests-jitter "${GUNICORN_MAX_REQUESTS_JITTER:-$GUNICORN_MAX_REQUESTS_JITTER_DEFAULT}" \
      -c gunicorn_conf.py \
      $PRELOAD_FLAG
    ;;
  worker)
    echo "Starting ARQ worker process..."
    # GTM-STAB-002 AC3: Restart wrapper — ARQ worker restarts on unexpected exit
    _WORKER_RESTART_DELAY="${WORKER_RESTART_DELAY:-5}"
    _WORKER_MAX_RESTARTS="${WORKER_MAX_RESTARTS:-10}"
    _restart_count=0
    while true; do
      # CRIT-051 AC3: --custom-log-dict redirects ARQ bootstrap logs to stdout.
      # Without this, Python's default StreamHandler writes to stderr, which
      # Railway classifies as error severity regardless of actual log level.
      arq job_queue.WorkerSettings --custom-log-dict job_queue.arq_log_config
      _exit_code=$?
      if [ $_exit_code -eq 0 ]; then
        echo "ARQ worker exited cleanly (code 0). Stopping."
        break
      fi
      _restart_count=$((_restart_count + 1))
      if [ $_restart_count -ge "$_WORKER_MAX_RESTARTS" ]; then
        echo "ARQ worker exceeded max restarts ($_WORKER_MAX_RESTARTS). Exiting."
        exit $_exit_code
      fi
      echo "ARQ worker exited with code $_exit_code (restart $_restart_count/$_WORKER_MAX_RESTARTS). Waiting ${_WORKER_RESTART_DELAY}s..."
      sleep "$_WORKER_RESTART_DELAY"
    done
    ;;
  *)
    echo "ERROR: Unknown PROCESS_TYPE='$PROCESS_TYPE'. Use 'web' or 'worker'."
    exit 1
    ;;
esac
