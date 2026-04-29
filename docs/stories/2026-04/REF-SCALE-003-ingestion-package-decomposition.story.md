# REF-SCALE-003: `ingestion/` Package Decomposition (3458L → BaseCrawler ABC)

**Priority:** P2
**Effort:** L (5-7 dias)
**Squad:** @architect + @data-engineer + @dev
**Status:** Ready
**Epic:** [EPIC-RES-BE-2026-Q2](EPIC-RES-BE-2026-Q2.md) ou [EPIC-TD-2026Q2](EPIC-TD-2026Q2/)
**Sprint:** Sprint 5
**Dependências bloqueadoras:** Suite saudável <8min (RES-BE-009)

---

## Contexto

`backend/ingestion/` 3458L total:

| Arquivo | LOC |
|---------|-----|
| `contracts_crawler.py` | 772 |
| `crawler.py` | 692 (base abstrata pesada) |
| `enricher.py` | 460 |
| `scheduler.py` | 414 |
| `loader.py` | 316 |
| `transformer.py` | (incluso) |
| `checkpoint.py` | (incluso) |
| `config.py` | (incluso) |

Drives Layer 1 ETL: `pncp_raw_bids` 1.5M rows (400d retention STORY-OBS-001) + `pncp_supplier_contracts` 2M+ rows (drive SEO inbound). Crawler base abstrata pesada — adicionar nova fonte (PNCP v2 hipotético) é difícil.

`contracts_crawler.py` 772L + `crawler.py` 692L = 1464L provável duplicação de pattern crawl 3×/sem vs 1×/dia + 3 incrementais.

---

## Acceptance Criteria

### AC1: Phase 0 — diff funcional

- [ ] @architect Phase 0: read integral `crawler.py` + `contracts_crawler.py`. Identificar funções duplicadas vs especialização.
- [ ] Output `docs/architecture/ingestion-decomposition.md` ANTES de extração

### AC2: Estrutura alvo

- [ ] `backend/ingestion/_base/crawler.py` (novo, ~300L) — `BaseCrawler` ABC:
  ```python
  class BaseCrawler(ABC):
      @abstractmethod
      async def fetch_page(self, page: int) -> list[dict]: ...
      @abstractmethod
      async def transform(self, raw: dict) -> dict: ...
      @abstractmethod
      async def upsert_batch(self, rows: list[dict]) -> int: ...
      
      async def checkpoint_advance(self, page: int) -> None: ...  # shared
      async def run(self, max_pages: int) -> CrawlerResult: ...   # shared template
  ```
- [ ] `backend/ingestion/bids_crawler.py` (~250L) — `BidsCrawler(BaseCrawler)` especialização PNCP bids
- [ ] `backend/ingestion/contracts_crawler.py` (~250L) — `ContractsCrawler(BaseCrawler)` especialização supplier_contracts
- [ ] `backend/ingestion/crawler.py` deletado (foi monolítico)

### AC3: Tests per-class

- [ ] `test_base_crawler.py` (template behavior + ABC contracts)
- [ ] `test_bids_crawler.py` (PNCP-specific)
- [ ] `test_contracts_crawler.py` (supplier-contracts-specific)
- [ ] Cobertura ≥85%

### AC4: Performance — sem regressão

- [ ] Benchmark ETL latency: pre-split baseline em `docs/perf/ingestion-baseline-2026-04-28.md`
- [ ] Pós-split: latência ETL <105% baseline

### AC5: Façade

- [ ] `ingestion/__init__.py` re-export `BidsCrawler`, `ContractsCrawler` (importadores externos não mudam)

---

## Scope

**IN:** ABC + 2 specializations + tests + benchmark + façade
**OUT:** Add 3rd source (e.g., ComprasGov backfill) — separate · pg_cron migration · retention policy change

---

## Definition of Done

- [ ] BaseCrawler ABC + 2 specializations
- [ ] Tests pass cobertura ≥85%
- [ ] Performance benchmark pass
- [ ] Suite passa
- [ ] @po validation GO

---

## Dev Notes

- `backend/ingestion/crawler.py:692L`, `contracts_crawler.py:772L`
- Padrão referência: REF-MON-002 webhook ABC, REF-VAL-002 LLM strategy (mesma estrutura)
- Pattern existing: `jobs/queue/config.py:WorkerSettings` para registro ARQ functions

---

## Risk & Rollback

| Trigger | Ação |
|---|---|
| Phase 0 mostra zero duplicação real | Cancel story; report finding em ADR |
| ETL performance regride | Lazy imports + `__slots__` + profile; rollback se >5% |
| Schedule timing diff (3×/sem vs daily) | ABC permite override; specializations decidem cadence |

**Rollback:** revert PR; ingestion/ monolítico.

---

## Dependencies

**Entrada:** RES-BE-009 (suite <8min)
**Saída:** habilita futuras stories adicionar ComprasGov backfill ou outras fontes

---

## PO Validation

**Validated by:** @po (Pax)
**Date:** 2026-04-28
**Verdict:** GO
**Score:** 10/10

### 10-Point Checklist

| # | Criterion | ✓/✗ | Notes |
|---|-----------|-----|-------|
| 1 | Clear and objective title | ✓ | BaseCrawler ABC + LOC tabulado. |
| 2 | Complete description | ✓ | crawler.py 692L + contracts_crawler 772L duplicação documentada. |
| 3 | Testable acceptance criteria | ✓ | 5 ACs com Phase 0 diff funcional + benchmark. |
| 4 | Well-defined scope | ✓ | OUT exclude 3rd source addition. |
| 5 | Dependencies mapped | ✓ | RES-BE-009 suite saudável. |
| 6 | Complexity estimate | ✓ | L (5-7d) coerente. |
| 7 | Business value | ✓ | Future fontes (PNCP v2) sem dor. |
| 8 | Risks documented | ✓ | Phase 0 cancela story se zero duplicação real. |
| 9 | Criteria of Done | ✓ | 5 itens com benchmark. |
| 10 | Alignment with PRD/Epic | ✓ | EPIC-RES-BE ou EPIC-TD. |

Status: Draft → Ready.

---

## Change Log

| Data | Versão | Descrição | Autor |
|---|---|---|---|
| 2026-04-28 | 1.0 | Story criada via batch. Origem: `_reversa_sdd/sm-briefing-refactor.md` REF-SCALE-003. | @sm (River) |
| 2026-04-28 | 1.1 | PO validation: GO (10/10). Status: Draft → Ready. | @po (Pax) |
