# REF-SCALE-004: Sitemap Routes Factory Consolidation (1151L → ~400L)

**Priority:** P2
**Effort:** M (3-5 dias)
**Squad:** @dev + @architect
**Status:** Ready
**Epic:** [EPIC-SEO-PROG-2026-Q2](EPIC-SEO-PROG-2026-Q2.md)
**Sprint:** Sprint 4
**Dependências bloqueadoras:** [RES-BE-001](RES-BE-001-audit-execute-without-budget.md) (CI gate) · [RES-BE-002](RES-BE-002-budget-top5-routes.md) sitemap residuais cobertos

---

## Contexto

4 sitemap routers `routes/sitemap_*.py`:

| Arquivo | LOC |
|---------|-----|
| `sitemap_cnpjs.py` | 357 |
| `sitemap_licitacoes.py` | 312 |
| `sitemap_orgaos.py` | 298 |
| `sitemap_licitacoes_do_dia.py` | 184 |
| **Total** | **1151** |

Pattern fetch→filter→format_xml idêntico. PR #535 fixou antipattern .execute() async mas não consolidou estrutura. Memory `project_sitemap_endpoints_wedge_2026_04_27`: classe inteira tinha mesmo bug; classe inteira pode ser router-factory.

Distinção vs MON-SEO-04 (sitemaps-dinamicos-shards) e SEO-PROG-006 (sitemap-partitioned-index): MON-SEO-04 é frontend sharding strategy; SEO-PROG-006 é frontend partitioned index; esta story é **backend router factory** (ortogonal).

---

## Acceptance Criteria

### AC1: `routes/_sitemap_factory.py`

- [ ] `backend/routes/_sitemap_factory.py` (novo, ~200L):
  ```python
  def create_sitemap_router(
      *,
      entity_type: str,                  # "cnpjs", "licitacoes", etc.
      fetcher: Callable[..., Awaitable[list]],
      url_pattern: str,                   # f"https://smartlic.tech/{entity_type}/{{slug}}"
      lastmod_field: str = "updated_at",
      changefreq: str = "daily",
      priority: float = 0.7,
  ) -> APIRouter:
      ...
  ```
- [ ] Aplica `@with_budget_and_negative_cache` (RES-BE-002+003 pattern)
- [ ] Async + `to_thread` para `.execute()`
- [ ] XML serialization centralizada (`_serialize_sitemap_xml(urls)`)

### AC2: Migrate 4 routers

- [ ] `sitemap_cnpjs.py` reduz a ~80L: factory invocation + fetcher
- [ ] `sitemap_licitacoes.py` similar
- [ ] `sitemap_orgaos.py` similar
- [ ] `sitemap_licitacoes_do_dia.py` similar
- [ ] Total ~320L (vs 1151L atual) — saving ~830L

### AC3: ISR alignment preserved

- [ ] Cada sitemap retorna headers Cache-Control compatíveis com Next.js ISR `revalidate=3600` (memory `project_sitemap_serialize_isr_pattern`)
- [ ] `Content-Type: application/xml`

### AC4: Tests

- [ ] `test_sitemap_factory.py` (novo) — factory generation
- [ ] `test_sitemap_<entity>.py` continuam passando — endpoint behavior
- [ ] E2E: GET /sitemap-N.xml retorna XML válido < 50k URLs cap
- [ ] Cobertura ≥85%

### AC5: Documentação

- [ ] `docs/architecture/sitemap-factory.md` documenta pattern
- [ ] Update `.claude/rules/architecture-detail.md` referência

---

## Scope

**IN:** factory + 4 migrations + tests + docs
**OUT:** Frontend sitemap.ts changes (SEO-PROG-006 separate) · 5th sub-sitemap creation

---

## Definition of Done

- [ ] Factory + 4 routers migrated
- [ ] Tests pass cobertura ≥85%
- [ ] LOC reduction confirmed (~830L saving)
- [ ] Suite passa
- [ ] @po validation GO

---

## Dev Notes

- `routes/sitemap_*.py` 4 files
- Padrão referência: REF-VAL-003 _publicos_base.py (mesma factory pattern)
- Memory `feedback_sen_fe_001_recidiva_sitemap` — verify pós-fix grep global

---

## Risk & Rollback

| Trigger | Ação |
|---|---|
| Googlebot crawl regride após factory deploy | Soak 7d antes de deletar legacy files; revert factory if issue |
| ISR cache stale | Cache-Control headers preserved; Next.js fetch revalidates |

**Rollback:** revert PR; 4 routers monolíticos restaurados.

---

## Dependencies

**Entrada:** RES-BE-001 + RES-BE-002 sitemap residuais
**Saída:** habilita SEO-PROG-006 frontend partitioned index (backend factory provê foundation)

---

## PO Validation

**Validated by:** @po (Pax)
**Date:** 2026-04-28
**Verdict:** GO
**Score:** 10/10

### 10-Point Checklist

| # | Criterion | ✓/✗ | Notes |
|---|-----------|-----|-------|
| 1 | Clear and objective title | ✓ | Factory + LOC saving 1151→400L explícito. |
| 2 | Complete description | ✓ | Distinção MON-SEO-04 (frontend sharding) clarificada. |
| 3 | Testable acceptance criteria | ✓ | 5 ACs com factory test + ISR alignment + cap 50k URLs. |
| 4 | Well-defined scope | ✓ | OUT exclude frontend sitemap.ts changes. |
| 5 | Dependencies mapped | ✓ | RES-BE-001 + RES-BE-002 foundation. |
| 6 | Complexity estimate | ✓ | M (3-5d). |
| 7 | Business value | ✓ | LOC saving ~830L. |
| 8 | Risks documented | ✓ | Soak 7d antes delete legacy. |
| 9 | Criteria of Done | ✓ | 5 itens com LOC reduction. |
| 10 | Alignment with PRD/Epic | ✓ | EPIC-SEO-PROG-2026-Q2. |

Status: Draft → Ready.

---

## Change Log

| Data | Versão | Descrição | Autor |
|---|---|---|---|
| 2026-04-28 | 1.0 | Story criada via batch. Origem: `_reversa_sdd/sm-briefing-refactor.md` REF-SCALE-004. | @sm (River) |
| 2026-04-28 | 1.1 | PO validation: GO (10/10). Status: Draft → Ready. | @po (Pax) |
