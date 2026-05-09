# ADR-PARITY-BE-FE-001: `response_model=` is Mandatory on Every FastAPI Route

| Field | Value |
|-------|-------|
| Status | Accepted (2026-05-09) |
| Story | [PARITY-BE-FE-001](../stories/2026-05/PARITY-BE-FE-001-response-model-coverage.story.md) |
| Issue | [#951](https://github.com/tjsasakifln/SmartLic/issues/951) |
| Stakeholders | @architect (lead), @dev, @qa |
| Supersedes | (extends [STORY-2.1 EPIC-TD-2026Q2](../stories/EPIC-TD-2026Q2/) Pydantic→TS sync) |

## Context

`STORY-2.1` shipped the Pydantic→TypeScript codegen pipeline
(`frontend/app/api-types.generated.ts` regenerated from the backend's
OpenAPI schema, gated by `.github/workflows/api-types-check.yml`).

That gate detects schema **drift**, but it cannot detect schema
**absence**. A FastAPI route declared without `response_model=`:

```python
@router.get("/admin/foo")
async def get_foo() -> dict:
    return {"answer": 42}
```

still ships in OpenAPI — it just lands as

```jsonc
{
  "200": {
    "content": {
      "application/json": {
        "schema": { "additionalProperties": true }
      }
    }
  }
}
```

which `openapi-typescript` faithfully renders as
`{ [k: string]: unknown }` on the frontend. The CI gate sees no diff,
so it stays green — and consumers of the route end up calling
`(data as any).answer`, killing IDE autocompletion and the type-narrowing
guarantees the rest of the codebase relies on.

The 2026-05-09 audit found 68 of 212 routes (32%) in this state. Every
admin panel, public stats endpoint, and conversion path had at least one
route serving `unknown` to the frontend.

## Decision

**Every FastAPI route exposed to the frontend MUST declare
`response_model=` on its decorator.** This is enforced by two layers:

1. `backend/scripts/audit_response_model_coverage.py` — AST walks
   `backend/routes/*.py`, counts decorators that declare the kwarg, and
   reports per-file coverage.
2. `.github/workflows/audit-response-model-coverage.yml` — fails the PR
   when overall coverage shrinks vs the committed baseline JSON, or when
   a brand-new route module ships without typing every route.

The baseline is committed at
`backend/scripts/audit_response_model_coverage_baseline.json`. The gate
allows the baseline to move forward (more typed routes) but never
backwards.

### Acceptable values

| Pattern | When |
|---------|------|
| `response_model=SomeModel` | Default. Use a Pydantic v2 `BaseModel`. Prefer reusing a model from `backend/schemas/*.py`; create new ones in the appropriate module. |
| `response_model=List[SomeModel]` / `Dict[str, SomeModel]` | Compositions. Imported via `typing` like the rest of the codebase. |
| `response_model=None` | Documented escape hatch. Required when the route returns a non-JSON body (`StreamingResponse`, `RedirectResponse`, `HTMLResponse`, file downloads, raw `Response`). The route MUST include a one-line docstring rationale. |

### Permissive schemas (`backend/schemas/parity.py`)

Some routes (admin SLO dashboard, health snapshots, org dashboards,
partner program reports) return structurally complex dicts assembled
from many sources, where pinning every field would cause silent key
stripping. For those, Pass 2 introduced
`backend/schemas/parity.py` — Pydantic models that:

* Inherit from `_PermissiveBase` (`ConfigDict(extra="allow")`), so extra
  keys flow through.
* Declare every field as `Optional[...] = None`, so missing keys do not
  crash validation.

This is **not** the long-term shape — it's the safe migration step that
lets the OpenAPI surface stop returning `unknown` without forcing
hand-by-hand schema audits across 30+ legacy routes. Future work can
tighten individual schemas as the consuming UI surface stabilizes.

## Consequences

### Positive

* `frontend/app/api-types.generated.ts` no longer collapses critical
  schemas to `{ [k: string]: unknown }` (340 named schemas in OpenAPI
  post-Pass-2 vs 244 in main, +39%).
* IDE autocompletion + `tsc --noEmit` catch refactor mistakes early
  instead of at runtime.
* The CI gate is decremental-baseline-aware, so legacy routes can be
  typed incrementally without forcing a single big-bang sweep.

### Negative

* New routes have to declare a schema even for one-off admin endpoints.
  Mitigation: `parity.py::_PermissiveBase` makes "permissive shape"
  one extra import + a 4-line model.
* `response_model=None` requires reviewer attention to confirm the route
  genuinely streams / redirects. Mitigation: required docstring
  rationale; CI does not block it but it is visible during review.

### Neutral

* The audit script is dependency-free (stdlib only) so it can run in
  pre-commit hooks or any CI environment without backend deps.
* `parity.py` is intentionally a separate file so future tightening
  passes can move models out into the canonical `schemas/` modules
  without touching every route.

## Migration path

1. **Pass 1 (shipped 2026-05-09, PR #956):** Audit script + baseline JSON
   + admin Pass 1 (`admin_trace`, `admin_cron`, `admin_llm_cost` =
   100% typed). Baseline at 67.92%.
2. **Pass 2 (this ADR):** Backfill remaining admin / public / health /
   conversion routes. Permissive `parity.py` schemas. CI gate enabled.
   Baseline at 100%.
3. **Future (optional):** Tighten individual permissive schemas once
   downstream UI surfaces stabilize. Each tightening lands as a
   non-breaking schema addition — the gate only forbids reduction.

## References

* Story: [`docs/stories/2026-05/PARITY-BE-FE-001-response-model-coverage.story.md`](../stories/2026-05/PARITY-BE-FE-001-response-model-coverage.story.md)
* Issue: https://github.com/tjsasakifln/SmartLic/issues/951
* Audit script: [`backend/scripts/audit_response_model_coverage.py`](../../backend/scripts/audit_response_model_coverage.py)
* CI workflow: [`.github/workflows/audit-response-model-coverage.yml`](../../.github/workflows/audit-response-model-coverage.yml)
* Companion gate: [`.github/workflows/api-types-check.yml`](../../.github/workflows/api-types-check.yml)
* Permissive base: [`backend/schemas/parity.py`](../../backend/schemas/parity.py)
* Frontend parity test: [`frontend/__tests__/types/parity.test.ts`](../../frontend/__tests__/types/parity.test.ts)
