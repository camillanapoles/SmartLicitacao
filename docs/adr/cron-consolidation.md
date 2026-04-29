# ADR: Cron Consolidation — `backend/cron/` legacy → `backend/jobs/cron/` ARQ canonical

**Status:** Accepted
**Date:** 2026-04-28
**Decisão:** User via AskUserQuestion + audit prelim
**Story:** [REF-SCALE-002](../stories/2026-04/REF-SCALE-002-dual-cron-paths-consolidation-stub.story.md)

---

## Context

Backend tem **2 paths cron simultâneos**:

1. `backend/cron/` (legacy 1063 LOC, 6 files): asyncio loops antigos `_loop`, `cache`, `billing`, `health`, `notifications`, `pncp_status`
2. `backend/jobs/cron/` (modern 1684 LOC, 14 files): ARQ-based com Redis distributed locks

**Sobreposição confirmada audit prelim 2026-04-28:**

| File legacy | File modern equiv | Status prelim |
|-------------|-------------------|---------------|
| `cron/cache.py` 42L | (não existe) | **ATIVO** via `cron_jobs.py` façade — start_cache_cleanup_task |
| `cron/billing.py` 351L | `jobs/cron/billing.py` 354L | **uncertain** — confirm via grep cron_jobs imports |
| `cron/notifications.py` 357L | `jobs/cron/notifications.py` 287L | **ORPHAN provavelmente** — façade importa de jobs/cron/notifications |
| `cron/_loop.py` 113L | `jobs/cron/scheduler.py` 34L (parcial) | **uncertain** |
| `cron/health.py` 88L | (incluso em health canary) | **uncertain** |
| `cron/pncp_status.py` 45L | `jobs/cron/canary.py` 125L (substituiu) | **provavelmente ORPHAN** |

**`cron_jobs.py` é façade** que importa de ambos paths — single source-of-truth para lifespan registrations (18 task_registry.register em `startup/lifespan.py:234-251`).

Memory `feedback_supabase_disk_io_root_cause_pattern` (2026-04-28 greedy-piglet): WC=4 + 18 cron tasks paralelas startup queries saturaram Disk IO. Consolidação preventive future incident.

## Decision

### Canonical path

**`backend/jobs/cron/` ARQ-modern** é canonical. Razões:

- Redis distributed locks (prevent execução duplicada multi-worker)
- ARQ structured worker (vs asyncio loops ad-hoc)
- 14 files já organized by domain
- Padrão moderno consistente com `jobs/queue/` (search async)

### Migration timeline

**Soft transition: Audit (1d) → Deprecate-warn 30d → Hard remove**

| Fase | Duração | Ação |
|------|---------|------|
| **Audit (Phase 0)** | 1d | Per-file Q3a-d ATIVO/INATIVO via psql logs prod last 7d. Output `docs/audit/dual-cron-status.md`. |
| **Migrate** | 2-3d | Para cada legacy ATIVO: criar equivalente em `jobs/cron/` (se não existe) + register em ARQ WorkerSettings.functions OR lifespan (se não-ARQ). |
| **Deprecate-warn** | 30d | Legacy registers emitem `DeprecationWarning` em logs; Sentry tracks invocations residuais. |
| **Hard remove** | 1d | Delete `backend/cron/` files. Sem feature flag (decisão Q4). |

### Sem feature flag

Q4 confirmado: **não existe `USE_LEGACY_CRON` env var**. Migration soft via DeprecationWarning + Sentry tracking sem necessidade de runtime toggle.

### Preservação

- pg_cron jobs (purge-old-bids, cleanup-search-cache, cleanup-search-store) **preservados** (CLAUDE.md STORY-1.2)
- `cron_jobs.py` façade **preservado** durante migration; deletado pós-hard-remove se zero importadores externos
- `cron_monitor` (STORY-1.1) **preservado** monitorando pg_cron

## Consequences

### Positivas
- Eliminação dual-path confusion (memory `project_backend_outage_2026_04_27` reduziu surface)
- ARQ Redis locks prevent execução duplicada
- Soft transition 30d permite Sentry detectar surprise dependencies

### Negativas
- 30d soak window estende migration vs big-bang
- DeprecationWarning logs poluem brevemente

### Implementação (REF-SCALE-002)

- AC0 Phase 0 audit: `docs/audit/dual-cron-status.md`
- AC1 ADR `docs/adr/cron-consolidation.md` (esta)
- AC2 Migration plan execution per Q1 jobs/cron canonical
- AC3 Preservar pg_cron monitoring (STORY-1.1)
- AC4 Tests per-cron registration in canonical path APENAS
- AC5 7d soak validation pós-migration

## Monitoring

- Sentry alert em legacy registration invocation (DeprecationWarning capturado)
- pg_cron health monitor (STORY-1.1) continua funcionando
- `smartlic_cron_executions_total{path}` Prometheus counter para confirmar zero legacy invocations pós-hard-remove

## Revision

ADR canonical. Mudança canonical path (back para legacy, ou para 3rd option) requer new ADR + RES-BE story.
