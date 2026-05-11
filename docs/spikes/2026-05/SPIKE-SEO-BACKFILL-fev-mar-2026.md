# SPIKE-SEO-BACKFILL: Viabilidade Backfill Fev/Mar 2026

**Date:** 2026-05-10
**Author:** @dev (Dex)
**Issue:** #1040
**Status:** SPIKE COMPLETE
**Decision:** PARTIAL-GO (PCP v2 only)

---

## Problema

`pncp_raw_bids` tem zero rows para Fev/Mar 2026. A retenção original era de 12-30
dias, bump para 400 dias veio na STORY-OBS-001 (abril 2026) — tarde demais para
preservar esses meses. O PNCP API tem janela contínua máxima de 365 dias, mas os
registros de Fev/Mar 2026 ainda estão dentro dessa janela. No entanto, o `crawl_backfill`
existente já cobre isso para PNCP. O gap real é: ComprasGov v3 e PCP v2 não são
ingeridos em `pncp_raw_bids` — eles alimentam apenas a pipeline de busca ao vivo.

**Nota arquitetural importante descoberta durante o spike:** `pncp_raw_bids` é
exclusivamente PNCP. ComprasGov v3 e PCP v2 operam via `ComprasGovAdapter` /
`PortalComprasAdapter` na pipeline de busca em tempo real (live search), sem
persistência histórica em nenhuma tabela. O gap Fev/Mar é exclusivamente de PNCP —
backfill via `crawl_backfill --days 120` já deveria resolver.

---

## Fontes Investigadas

### ComprasGov v3

- **Endpoint testado:** `https://dadosabertos.compras.gov.br/modulo-legado/1_consultarLicitacao`
  e `https://dadosabertos.compras.gov.br/modulo-contratacoes/1_consultarContratacoes_PNCP_14133`
- **Cobertura histórica:** NÃO — evidência: ambos os endpoints retornam `HTTP 404` com
  `{"statusCode": 404, "message": "Resource not found"}` para qualquer request,
  incluindo sem filtro de data. A própria suíte de testes do projeto documenta isso:
  `backend/tests/contracts/test_compras_gov_contract.py` linha 6-8:
  > *"as of 2026-03-03, the live ComprasGov v3 homepage is returning JSON 404 for the
  > entire API"*
- **Compatibilidade schema:** NONE — API indisponível; não é possível verificar.
- **Campos disponíveis:** N/A (API down)
- **Campos ausentes:** N/A (API down)
- **Volume estimado (Fev+Mar 2026):** 0 (API down; dados inacessíveis)
- **Rate limit / paginação:** Não aplicável — API completamente inativa.
- **Status da API:** DOWN desde ao menos 2026-03-03. Infraestrutura Azure
  (`x-azure-ref` no header de resposta), projeto hospedado no Azure mas sem rota
  válida registrada. Não há indicação de quando/se voltará.

```
# Evidência bruta — request ao endpoint raiz sem filtros:
$ curl -s --max-time 15 "https://dadosabertos.compras.gov.br/modulo-legado/1_consultarLicitacao?pagina=1&tamanhoPagina=1"
{ "statusCode": 404, "message": "Resource not found" }

# Headers retornados:
< HTTP/2 404
< content-type: application/json
< x-azure-ref: 20260511T024344Z-1564d889648v5zskhC1GRUgrnn0000000n30000000002gfk
< x-cache: CONFIG_NOCACHE
```

---

### PCP v2 (Portal de Compras Públicas)

- **Endpoint testado:** `https://compras.api.portaldecompraspublicas.com.br/v2/licitacao/processos`
- **Cobertura histórica:** SIM — evidência direta:
  - Fev 2026: `total: 5536` registros em `pageCount: 554` páginas
  - Mar 2026: `total: 7948` registros em `pageCount: 795` páginas
  - Total combinado Fev+Mar: **~13.484 registros**
- **Compatibilidade schema:** PARTIAL — detalhes abaixo.
- **Campos disponíveis (mapeamento para `pncp_raw_bids`):**

  | Campo pncp_raw_bids | Campo PCP v2 | Disponível? |
  |---------------------|--------------|-------------|
  | `pncp_id` (PK)      | `pcp_{codigoLicitacao}` | SIM (prefixado) |
  | `objeto_compra`     | `resumo`      | SIM |
  | `data_publicacao`   | `dataHoraPublicacao` | SIM |
  | `data_abertura`     | `dataHoraInicioPropostas` | SIM |
  | `data_encerramento` | `dataHoraFinalPropostas` | SIM |
  | `uf`                | `unidadeCompradora.uf` | SIM |
  | `municipio`         | `unidadeCompradora.cidade` | SIM |
  | `orgao_razao_social`| `razaoSocial` ou `nomeUnidade` | SIM |
  | `modalidade_nome`   | `tipoLicitacao.modalidadeLicitacao` | SIM |
  | `situacao_compra`   | `statusProcessoPublico.descricao` | SIM |
  | `codigo_municipio_ibge` | `unidadeCompradora.codigoMunicipioIbge` | SIM (pode ser null) |

- **Campos ausentes / requerem workaround:**

  | Campo pncp_raw_bids (NOT NULL) | Situação no PCP v2 |
  |--------------------------------|-------------------|
  | `modalidade_id` (INTEGER NOT NULL) | AUSENTE — PCP v2 usa `codigoModalidadeLicitacao` mas é sempre 0 para muitos registros; sem mapeamento direto para os códigos PNCP (4,5,6,7,8,12). Requer tabela de mapeamento ou valor default. |
  | `orgao_cnpj`    | AUSENTE — nem `unidadeCompradora` nem raiz do registro têm CNPJ. Campo nullable na tabela. |
  | `valor_total_estimado` | AUSENTE — a v2 listing API não inclui valor. Campo nullable. |
  | `esfera_id`     | AUSENTE — PCP v2 não informa esfera (F/E/M). Campo nullable. |

- **Volume estimado (Fev+Mar 2026):** ~13.484 registros (5.536 Fev + 7.948 Mar)
- **Rate limit / paginação:** Fixo 10 registros por página; sem limitação documentada.
  Integração existente usa `RATE_LIMIT_DELAY=0.2s` e `MAX_PAGES` configurável.
  Para 13k registros: ~1.350 páginas × 0,2s ≈ **~4,5 min de ingestão** (estimativa).
- **Nota crítica — `modalidade_id` NOT NULL:** A tabela exige um INTEGER NOT NULL.
  Será necessário um valor de fallback (ex: `0` para "desconhecido") ou um
  mapeamento PCP→PNCP modalidade. Isso é o único bloqueador técnico não-trivial.

```
# Evidência bruta — Fev 2026:
$ curl -s "https://compras.api.portaldecompraspublicas.com.br/v2/licitacao/processos?dataInicial=2026-02-01&dataFinal=2026-02-28&tipoData=1&pagina=1"
{
  "total": 5536,
  "pageCount": 554,
  "result": [
    {
      "codigoLicitacao": 456969,
      "resumo": "É objeto do presente instrumento a aquisição de Placas e Medalhas...",
      "razaoSocial": "CÂMARA MUNICIPAL DE BOM DESPACHO",
      "dataHoraPublicacao": "2026-02-24T19:49:00Z",
      "dataHoraInicioPropostas": "2026-02-25T03:00:00Z",
      "dataHoraFinalPropostas": "2026-02-28T02:59:00Z",
      "unidadeCompradora": {
        "nomeUnidadeCompradora": "CÂMARA MUNICIPAL DE BOM DESPACHO",
        "cidade": "Bom Despacho",
        "uf": "MG"
      },
      "tipoLicitacao": {
        "codigoModalidadeLicitacao": 0,
        "modalidadeLicitacao": "Dispensa"
      }
    }
  ]
}

# Mar 2026:
$ curl -s ".../processos?dataInicial=2026-03-01&dataFinal=2026-03-31&tipoData=1&pagina=1"
{ "total": 7948, "pageCount": 795 }
```

---

## Tabela Comparativa

| Fonte | Cobertura Hist. | Campos Compat. | Volume Est. | Esforço Impl. | Risco |
|-------|----------------|----------------|-------------|---------------|-------|
| ComprasGov v3 | NÃO (API down) | N/A | 0 | N/A | BLOCKER: API inativa |
| PCP v2 | SIM | PARTIAL (4 campos ausentes, 1 NOT NULL gap) | ~13.484 | M (2-3d) | MÉDIO: `modalidade_id` NOT NULL precisa de workaround |

---

## Decisão: PARTIAL-GO

**PCP v2:** GO. A API está acessível, tem dados históricos de Fev/Mar 2026, e a
integração já existe. O único bloqueador real é `modalidade_id NOT NULL` — resolvível
com uma constante de fallback (`999` ou `-1`) + coluna `source` diferenciada para
filtrar na busca.

**ComprasGov v3:** NO-GO. API completamente inativa desde ao menos 2026-03-03. Não
há evidência de que voltará; sem dados acessíveis para backfill.

**PNCP:** O gap Fev/Mar para PNCP pode já ser resolvido pelo `crawl_backfill`
existente (`backend/scripts/backfill_pncp_historical.py --days 120`). Recomenda-se
rodar isso como primeiro passo.

---

### Se GO ou PARTIAL-GO

- **Implementation estimate:** M = 2-3 dias
- **Recommended approach:**
  1. Rodar `backfill_pncp_historical.py --days 120` para cobrir gap PNCP
  2. Criar `backend/scripts/backfill_pcp_v2.py` usando `PortalComprasAdapter.fetch()`
     - Iterar Fev 2026 (2026-02-01→2026-02-28) e Mar 2026 (2026-03-01→2026-03-31)
     - Mapear `UnifiedProcurement` → schema `pncp_raw_bids` com `modalidade_id=999`
       (ou criar migration para tornar `modalidade_id` nullable)
     - Chamar `bulk_upsert()` — dedup por `pncp_id` (prefixo `pcp_`) é idempotente
  3. Adicionar migration `ALTER TABLE pncp_raw_bids ALTER COLUMN modalidade_id DROP NOT NULL`
     ou adicionar valor sentinela documentado
- **Suggested next story:** `feat(ingest): backfill PCP v2 data Fev/Mar 2026 into pncp_raw_bids [#1040]`

### Pré-condição importante
Antes de implementar o backfill de PCP v2, verificar se o gap em Fev/Mar realmente
impacta SEO/programmatic pages. Se `pncp_raw_bids` só exibe dados PNCP e as páginas
SEO não usam fonte PCP, o impacto real pode ser menor do que assumido.

---

## Evidências Brutas

```
# ComprasGov v3 — todos os endpoints retornam 404:
GET /modulo-legado/1_consultarLicitacao?pagina=1&tamanhoPagina=1 → 404
GET /modulo-contratacoes/1_consultarContratacoes_PNCP_14133?... → 404
GET /modulo-licitacao/licitacao?... → 404
Infraestrutura: Azure (x-azure-ref presente nos headers)

# PCP v2 — dados confirmados:
GET /v2/licitacao/processos?dataInicial=2026-02-01&dataFinal=2026-02-28&tipoData=1
→ { total: 5536, pageCount: 554 }

GET /v2/licitacao/processos?dataInicial=2026-03-01&dataFinal=2026-03-31&tipoData=1
→ { total: 7948, pageCount: 795 }

# Campos PCP confirmados: codigoLicitacao, resumo, razaoSocial, dataHoraPublicacao,
# dataHoraInicioPropostas, dataHoraFinalPropostas, unidadeCompradora.{uf,cidade},
# tipoLicitacao.{modalidadeLicitacao, codigoModalidadeLicitacao}

# Campos PCP ausentes: cnpj, valor_total_estimado, esfera_id, modalidade_id numérico PNCP
```

---

## Referências

- Integração existente ComprasGov v3: `backend/clients/compras_gov_client.py`
- Integração existente PCP v2: `backend/clients/portal_compras_client.py`
- Transformer PNCP para pncp_raw_bids: `backend/ingestion/transformer.py`
- Loader (bulk_upsert): `backend/ingestion/loader.py`
- Schema pncp_raw_bids: `supabase/migrations/20260326000000_datalake_raw_bids.sql`
- Script backfill PNCP existente: `backend/scripts/backfill_pncp_historical.py`
- Contract tests ComprasGov (nota sobre API down): `backend/tests/contracts/test_compras_gov_contract.py`
- Configuração ingestion: `backend/ingestion/config.py`
