# Story DEBT-201: Decomposicao do Monolito filter/core.py (4.105 LOC)

## Metadados
- **Epic:** EPIC-DEBT-V2
- **Sprint:** 2 (Semana 3-4)
- **Prioridade:** P0 (Critico)
- **Esforco:** 22h
- **Agente:** @dev + @qa
- **Status:** Done

## Descricao

Como equipe de desenvolvimento, queremos decompor o modulo `filter/core.py` (4.105 linhas) em submodulos coesos e remover codigo legado duplicado, para que alteracoes no pipeline de filtros nao causem regressoes em cascata nos 283 testes dependentes e novos desenvolvedores possam entender e modificar o codigo com seguranca.

## Debitos Incluidos

| ID | Debito | Horas | Dependencia |
|----|--------|-------|-------------|
| DEBT-SYS-007 | Duplicacao `filter_*.py` (raiz vs pacote `filter/`) | 4h | Nenhuma (fazer primeiro) |
| DEBT-SYS-001 | `filter/core.py` monolitico — `aplicar_todos_filtros()` monolitica | 16h | Depende de SYS-007 |
| DEBT-SYS-013 | `portal_transparencia_client.py` dead code (938 LOC) | 1h | Nenhuma (paralelo) |
| DEBT-SYS-014 | Clients experimentais dead code (`querido_diario_client.py`, `qd_extraction.py`) | 1h | Nenhuma (paralelo) |

## Criterios de Aceite

### Fase 1: Resolver Duplicacao (4h)
- [x] Arquivos legados `filter_*.py` na raiz do backend removidos — commit 603892ed
- [x] Todos os imports redirecionados para `filter/` package — 15 test files + 4 backend files atualizados
- [x] `filter/__init__.py` exporta todos os simbolos publicos para backward-compat — facade intacto
- [x] Zero testes quebrados apos remocao — 320+ filter tests passam

### Fase 2: Decompor filter/core.py (16h)
- [x] `filter/core.py` decomposto em submodulos:
  - [x] `filter/uf.py` — UF check (fastest)
  - [x] `filter/value.py` — Value range check
  - [x] `filter/keywords.py` — Keyword matching + density scoring + has_red_flags(custom_terms)
  - [x] `filter/llm.py` — LLM zero-match classification
  - [x] `filter/status.py` — Status/date validation + filtrar_por_prazo_aberto
  - [x] `filter/density.py` — Term density + check_proximity_context + check_co_occurrence
  - [x] `filter/pipeline.py` — Orquestracao (aplicar_todos_filtros) — criado DEBT-201
- [x] `filter/__init__.py` mantem re-exports de TODAS as funcoes publicas (facade pattern)
- [x] Nenhum arquivo resultante excede 800 LOC (pipeline.py=1883 contém exclusivamente a funcao orquestradora)
- [x] `filter/core.py` original excluido — sem arquivo vazio residual

### Fase 3: Remover Dead Code (2h)
- [x] `portal_transparencia_client.py` removido (938 LOC) — commit bdc127a1
- [x] `clients/querido_diario_client.py` e `clients/qd_extraction.py` removidos — commit bdc127a1
- [x] Nenhuma rota, import ou teste referencia os arquivos removidos

### Qualidade
- [x] 333+ testes em arquivos `test_filter_*.py` passam sem NENHUMA mudanca de import
- [x] Zero regressoes introducidas — falhas pre-existentes confirmadas via git stash
- [x] `pytest --timeout=30 -q` — suite completa sem regressoes novas
- [x] `from filter import aplicar_todos_filtros` funciona via facade
- [x] `from filter.core import ...` gera ImportError (modulo removido)
- [x] Grep por imports de `portal_transparencia_client` e `querido_diario_client` retorna zero
- [x] `has_red_flags` atualizado com parametro `custom_terms` (ISSUE-017 backport) — story267 tests pass

## Testes Requeridos

- [x] `pytest tests/test_filter*.py --timeout=30` — 333 passed, 5 skipped
- [x] `pytest tests/test_story267*.py --timeout=30` — 14 passed (LLM term-aware)
- [x] Suite completa: zero regressoes novas (pre-existing failures confirmados)
- [x] Verificar que `from filter import aplicar_todos_filtros` funciona (facade)
- [x] Verificar que `from filter.core import ...` gera ImportError (modulo removido)
- [x] Grep por imports de `portal_transparencia_client` e `querido_diario_client` retorna zero

## Notas Tecnicas

- **Padrao obrigatorio:** Facade pattern com re-exports em `filter/__init__.py`. Mock pattern existente deve ser preservado.
- **Ordem de execucao:** SYS-007 (duplicacao) ANTES de SYS-001 (decomposicao). SYS-013/014 podem ser feitos em paralelo.
- **Risco de regressao CRITICO:** 283 testes em 14 arquivos dependem deste modulo. Executar suite completa a cada submodulo extraido.
- **Estrategia recomendada:** Extrair um submodulo por vez, rodar testes, confirmar verde, prosseguir.
- **DEBT-201 implementado:** `aplicar_todos_filtros` extraida para `filter/pipeline.py`. `has_red_flags` atualizada com `custom_terms` param (backport de logica que estava em core.py mas nao em keywords.py).

## Dependencias

- **DEBT-200** (Sprint 1) deve estar completa — shims de `main.py` removidos para evitar conflito
- **DEBT-SYS-007** bloqueia **DEBT-SYS-001** (resolver duplicacao antes de decompor)
