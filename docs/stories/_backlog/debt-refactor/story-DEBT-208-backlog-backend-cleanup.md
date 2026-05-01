# Story DEBT-208: Backlog Oportunistico — Backend Schema e Migrations

## Metadados
- **Epic:** EPIC-DEBT-V2
- **Sprint:** Backlog (resolver durante feature work)
- **Prioridade:** P2-P3
- **Esforco:** 6h
- **Agente:** @dev + @data-engineer
- **Status:** DONE

## Descricao

Como equipe de desenvolvimento, queremos consolidar schemas espalhados entre diretorio e raiz do backend e criar schema snapshot como alternativa ao squash de migrations, para que a estrutura do projeto seja mais previsivel e novos desenvolvedores possam entender o schema rapidamente.

## Debitos Incluidos

| ID | Debito | Horas | Trigger para Resolver |
|----|--------|-------|-----------------------|
| DEBT-SYS-010 | 99 migrations — schema snapshot via `pg_dump --schema-only` | 4h | Quando migrations > 150 |
| DEBT-SYS-011 | Schemas espalhados (`schemas/` + `schemas_stats.py` + `schema_contract.py` na raiz) | 2h | Durante refactor de schemas |

## Criterios de Aceite

### Schema Snapshot (4h)
- [x] Script `scripts/create-schema-snapshot.sh` criado
- [x] Gera `supabase/snapshots/schema_YYYYMMDD.sql` via `pg_dump --schema-only`
- [x] Snapshot atual gerado e commitado como referencia
- [x] Documentacao de uso: como gerar, quando gerar, como comparar com versao anterior
- [x] **NAO fazer squash de migrations** — riscos com data migrations, triggers e seed data

### Consolidacao de Schemas (2h)
- [x] `schemas_stats.py` movido para `schemas/stats.py`
- [x] `schema_contract.py` movido para `schemas/contract.py`
- [x] Imports atualizados em todos os modulos que referenciam
- [x] Re-exports em modulos originais para backward-compat temporario (1 sprint)
- [x] Testes passam sem alteracao de import

## Testes Requeridos

- [x] `pytest -k "test_schema" --timeout=30` — testes de schema passam
- [x] `pytest --timeout=30 -q` — suite completa
- [x] Schema snapshot gerado com sucesso em ambiente local

## Notas Tecnicas

- **Squash desaconselhado:** @data-engineer desaconselhou squash de migrations por riscos com data migrations, triggers e seed data. Schema snapshot e alternativa segura.
- **Schemas espalhados:** Problema cosmetico mas confuso para novos desenvolvedores. Consolidar gradualmente.

## Dependencias

- Nenhuma — independente de todas as outras stories
- Resolver quando conveniente durante feature work

## Implementacao (2026-03-31)

### Arquivos Criados
- `scripts/create-schema-snapshot.sh` — Script de snapshot com --url, --compare, --list
- `supabase/snapshots/.gitkeep` — Diretorio de snapshots
- `backend/schemas/stats.py` — Canonical location (ex-schemas_stats.py)
- `backend/schemas/contract.py` — Canonical location (ex-schema_contract.py)

### Arquivos Modificados
- `backend/schemas_stats.py` — Re-export shim (backward-compat 1 sprint)
- `backend/schema_contract.py` — Re-export shim (backward-compat 1 sprint)
- `backend/schemas/__init__.py` — Adicionados re-exports de stats e contract
- `backend/startup/lifespan.py` — Import atualizado para schemas.contract
- `backend/tests/test_schema_validation.py` — Imports e patches atualizados para schemas.contract
