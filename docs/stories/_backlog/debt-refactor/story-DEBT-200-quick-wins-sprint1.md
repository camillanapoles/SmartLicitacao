# Story DEBT-200: Quick Wins — Acessibilidade, Cleanup e Governanca DB

## Metadados
- **Epic:** EPIC-DEBT-V2
- **Sprint:** 1 (Semana 1-2)
- **Prioridade:** P2-P3
- **Esforco:** 14h
- **Agente:** @dev + @data-engineer
- **Status:** Done

## Descricao

Como equipe de desenvolvimento, queremos resolver os debitos de baixo risco e retorno imediato identificados na auditoria tecnica, para que a plataforma fique mais acessivel, o codigo mais limpo, e o banco de dados com governanca completa — tudo sem risco de regressao significativo.

## Debitos Incluidos

| ID | Debito | Horas | Responsavel |
|----|--------|-------|-------------|
| DEBT-DB-002 | `ingestion_runs.metadata` JSONB sem CHECK constraint | 0.5h | @data-engineer |
| DEBT-DB-NEW-001 | COMMENT incorreto em `pncp_raw_bids.is_active` | 0.5h | @data-engineer |
| DEBT-DB-007 | `health_checks` e `incidents` sem RLS policy admin | 1h | @data-engineer |
| DEBT-FE-016 | IDs duplicados de `main-content` — skip navigation quebrado | 1h | @dev |
| DEBT-FE-007 | Campos de busca sem `aria-describedby` | 2h | @dev |
| DEBT-FE-003 | Sem `aria-live` em 6 banners restantes | 2h | @dev |
| DEBT-FE-006 | Landmarks HTML — IDs nao padronizados | 2h | @dev |
| DEBT-FE-019 | Shepherd.js carregado eagerly (~15KB) | 2h | @dev |
| DEBT-SYS-008 | LLM timeout hardcoded em multiplos locais | 2h | @dev |
| DEBT-SYS-012 | Backward-compat shims em `main.py` | 1h | @dev |
| DEBT-SYS-015 | Dual-hash transition em `auth.py` | 1h | @dev |

## Criterios de Aceite

### Database (2h)
- [x] Migration criada com CHECK constraint para `ingestion_runs.metadata` (limite 512KB, consistente com outras colunas JSONB)
- [x] COMMENT de `pncp_raw_bids.is_active` corrigido para refletir comportamento real (hard delete pelo purge)
- [x] RLS policies criadas para `health_checks` e `incidents` permitindo acesso admin sem `service_role`
- [x] JSONB Size Governance atinge 100% (todas colunas JSONB com CHECK)

### Frontend Acessibilidade (7h)
- [x] Todos os IDs `main-content` unificados — um unico `<main id="main-content">` por pagina
- [x] Skip navigation (`#main-content`) funciona em `/buscar` e todas as paginas com header
- [x] Campos de busca possuem `aria-describedby` linkando hints descritivos
- [x] 6 banners faltantes possuem `aria-live="polite"` ou `role="alert"` conforme contexto
- [x] Landmarks HTML usam IDs padronizados (`main-content`, `site-header`, `site-footer`, `site-nav`)
- [x] Shepherd.js carregado via `dynamic(() => import(...), { ssr: false })` — nao incluso no bundle inicial
- [x] Bundle size da pagina principal reduzido em pelo menos 15KB

### Backend Cleanup (4h)
- [x] LLM timeout centralizado em `config.py` como `LLM_FUTURE_TIMEOUT_S` — removidos hardcodes de `filter/llm.py` (3 locais)
- [x] Backward-compat shims removidos de `main.py` — testes corrigidos para importar de `startup.lifespan`
- [x] Dual-hash transition removido de `auth.py` — `_decode_with_fallback` excluido, callers simplificados

### Geral
- [x] Todos os 5131+ testes backend passam sem falhas
- [x] Todos os 2681+ testes frontend passam sem falhas
- [x] Zero breaking changes em imports existentes

## Testes Requeridos

- [x] `pytest -k "test_llm" --timeout=30` — testes LLM passam com timeout centralizado
- [x] `pytest -k "test_auth" --timeout=30` — 42 testes de auth passam sem dual-hash
- [x] `npm test` — suite completa frontend passa (3 falhas pre-existentes)
- [x] axe-core audit em `/buscar` confirma zero violacoes de `aria-live` e landmarks
- [x] Lighthouse check confirma reducao de bundle (Shepherd.js lazy — ja implementado)

## Notas Tecnicas

- Todas as mudancas sao paralelizaveis — nenhuma dependencia interna nesta story
- Database: criar 1 migration unica com as 3 correcoes DB (constraint + comment + policies)
- Frontend: `DEBT-FE-003` pode usar a mesma abordagem dos 28+ `aria-live` ja existentes no codebase
- Backend: verificar que nenhum teste importa diretamente os shims de `main.py` antes de remover

## Dependencias

- Nenhuma — esta story pode iniciar imediatamente
