# /pricing-b2g — Inteligência de Preços B2G

## Purpose

Analisa contratos homologados (e fallback estimado) já registrados no PNCP para um objeto/setor específico e calcula a distribuição estatística de preços reais praticados. Responde com precisão cirúrgica à pergunta mais importante do cliente: "quanto eu deveria ofertar?"

**Output primário:** `docs/pricing/pricing-{objeto_slug}-{YYYY-MM-DD}.md` (relatório de preços)
**Output secundário:** `docs/pricing/pricing-{objeto_slug}-{YYYY-MM-DD}.xlsx` (dados brutos + análise)
**Output intermediário:** `docs/pricing/pricing-{objeto_slug}-{YYYY-MM-DD}.json` (artefato bruto consumido pelas Phases 3-5)

---

## Capacidades — DataLake-first (v2)

Este command usa **DataLake Supabase como fonte primária** (~5-10s) com fallback automático para live PNCP API (~2-5min) quando DataLake estiver indisponível ou desabilitado.

| Aspecto | DataLake (default) | Live (fallback) |
|---------|-------------------|----------------|
| Fonte | Tabela `pncp_supplier_contracts` (~2M+ rows) | API `pncp.gov.br/api/consulta/v1/contratacoes/publicacao` |
| Latência | <5s para query agregada | 2-5min (paginação 20× × 4 modalidades) |
| Frescor | ETL 3x/sem (mon/wed/fri) | Real-time |
| Rate limit | Nenhum | ~100 req/min |

**Flags de controle:**
- `DATALAKE_QUERY_ENABLED=true` no `.env` ativa DataLake (default no projeto)
- `--no-datalake` força fallback live mesmo com flag ativa
- Em caso de falha do DataLake (Supabase down, query erro), fallback automático para live

**Caveat — `valor_global`:**
A coluna `pncp_supplier_contracts.valor_global` é populada pelo crawler (`backend/ingestion/contracts_crawler.py:191-218`) com cascade fallback: `valorGlobal` → `valorInicial` → `valorTotalEstimado`. Não há distinção formal entre "homologado puro" e "estimado fallback". Isso é **paridade semântica com a API live** (que também retorna `valorTotalHomologado` nullable com fallback para `valorTotalEstimado`). O relatório identifica este fato na seção "Metodologia".

---

## Usage

```
/pricing-b2g "serviço de limpeza hospitalar"
/pricing-b2g "pavimentação asfáltica" --uf SP,MG,PR
/pricing-b2g "medicamentos" --setor medicamentos
/pricing-b2g "manutenção predial" --meses 24 --modalidade 5
/pricing-b2g "uniformes" --cnpj-orgao 12345678000190
/pricing-b2g "limpeza hospitalar" --no-datalake     # força live
```

## Execution

### Phase 1: Coleta + Estatísticas (1 chamada)

```bash
cd /mnt/d/pncp-poc
python scripts/pricing-b2g-collect.py \
    --objeto "{OBJETO}" \
    --uf "{UFS}" \
    --meses {MESES} \
    --output docs/pricing/pricing-{slug}-{YYYY-MM-DD}.json
```

**Flags adicionais:**
- `--cnpj-orgao 12345678000190` — filtra contratos de um órgão específico
- `--modalidade 4,5,6,8` — restringe modalidades (only live; DataLake já cobre todas)
- `--no-datalake` — força fallback live
- `--valor-min 100` — descarta contratos abaixo deste valor (default 1.0)

O script automaticamente:

1. **Quebra `--objeto` em keywords** (lowercase, ≥4 chars, sem stopwords PT-BR; cap 8 keywords)
2. **Tenta DataLake primeiro** (se flag e `--no-datalake` permitirem)
   - Query: `SELECT FROM pncp_supplier_contracts WHERE objeto_contrato ILIKE ANY (keywords) AND uf IN (ufs) AND data_assinatura >= NOW() - meses ORDER BY data_assinatura DESC LIMIT 1000`
   - Agrega P10/P25/P50/P75/P90 + média + DP + CV em-memória
3. **Fallback live se DataLake falhar** — pagina PNCP API por modalidade ([4,5,6,8] default), filtra client-side por keywords + UF + valor mínimo
4. **Ranking por similaridade** preserva top 200 contratos para Phase 4

**Output JSON estruturado:**
```json
{
  "objeto": "limpeza hospitalar",
  "ufs": ["SP","MG"],
  "meses": 12,
  "fonte": "datalake",
  "confiabilidade": "ALTA",
  "stats": {"n": 87, "p10": 145000, "p25": 220000, "mediana": 380000,
            "p75": 580000, "p90": 920000, "media": 425000, "dp": 240000, "cv": 56.5},
  "sample": [{...top 200 contratos...}],
  "warnings": ["valor_global é cascade (homologado→inicial→estimado)"],
  "generated_at": "2026-04-29T10:30:00"
}
```

### Phase 2: Limpeza + Normalização (já no script)

O `pricing-b2g-collect.py` aplica:
- Filtragem por `--valor-min` (descarta zeros/null)
- DataLake já tem dedup por `content_hash` na ingestão
- Live preserva apenas contratos com `valorTotalHomologado` ou `valorTotalEstimado` válidos

**Não automatizado neste pilot (assumir paridade com fluxo legado):**
- Ajuste IPCA — todos os valores são em reais nominais. Para período >12 meses o operador deve mencionar inflação na conclusão.
- Normalização por unidade (preço/m², preço/un) — não disponível sem item-level data; cabe a ferramenta dedicada.
- Separação por porte do órgão — disponível via campo `esfera` no sample, mas não é entrada estatística atualmente.

### Phase 3: Análise Estatística

**3a. Distribuição de preços** — já calculada no JSON em `stats`:

| Métrica | Campo | O que significa |
|---------|-------|-----------------|
| **N (amostra)** | `stats.n` | Confiabilidade da análise |
| **Mediana** | `stats.mediana` | Preço "típico" — melhor que média |
| **P25 / P75** | `stats.p25` / `stats.p75` | Faixa de competição saudável |
| **P10 / P90** | `stats.p10` / `stats.p90` | Piso e teto do mercado |
| **Média / DP** | `stats.media` / `stats.dp` | Distorcido por outliers |
| **CV** | `stats.cv` | <30% mercado previsível, >50% volátil |

**3b-3e (análises avançadas — opcionais):**

Se a análise por UF / modalidade / temporal for necessária, processar `sample` em pandas:
- Por UF: groupby `uf` + percentile_cont
- Por modalidade: não disponível em DataLake (campo ausente em `pncp_supplier_contracts`); só no live
- Temporal: groupby trimestre da `data_assinatura`
- Por porte do órgão: groupby `esfera`

### Phase 4: Recomendação de Preço (Claude inline)

**4a. Se `--cnpj-orgao` ou contexto de edital específico:**

```markdown
## Recomendação de Preço

**Análise baseada em:** {stats.n} contratos similares (últimos {meses} meses, fonte: {fonte})

### Faixa de Preço Recomendada

| Estratégia | Valor Sugerido | Probabilidade de ganhar |
|------------|:---:|:---:|
| **Agressivo** | R${stats.p25} | Alta (margem apertada) |
| **Competitivo** | R${stats.mediana} | Média-Alta |
| **Conservador** | R${stats.p75} | Média-Baixa (margem confortável) |

**Risco de inexequibilidade:** Lei 14.133 define proposta inexequível como <75% do valor estimado.
Se ofertar abaixo de R${stats.p10}, há risco de questionamento.
```

**4b. Se consulta genérica:** apresentar tabela de referência completa.

### Phase 5: Geração dos Outputs

#### Relatório Markdown — `docs/pricing/pricing-{slug}-{YYYY-MM-DD}.md`

Lê o JSON da Phase 1 e renderiza:

```markdown
# Inteligência de Preços — {objeto}
**Data:** {data} | **Período:** {meses} meses | **Fonte:** {fonte} | **Amostra:** {N} contratos | **Confiabilidade:** {tag}

## Resumo Executivo
- Mediana do mercado: **R${valor}**
- Faixa recomendada: **R${P25} — R${P75}**
- Coeficiente de Variação: **{cv}%** ({mercado previsível/volátil})

## Distribuição de Preços
[tabela com P10, P25, Mediana, P75, P90, Média, DP, CV]

## Top 20 Contratos Similares
[tabela: Órgão | UF | Município | Esfera | Valor | Data | Objeto]

## Metodologia
- Fonte: {DataLake Supabase | API PNCP live}
- Keywords usadas: {keywords}
- Valor mínimo: R${valor_min}
- **Caveat:** `valor_global` é cascade do crawler (`valorGlobal → valorInicial → valorTotalEstimado`). Sem distinção formal entre homologado puro e estimado fallback. Mesma semântica que a API live.

## Recomendação
[seção 4a/4b]

---
Tiago Sasaki - Consultor de Licitações
(48)9 8834-4559
```

#### Planilha Excel — 3 abas (renderizada do mesmo JSON)

| Aba | Conteúdo |
|-----|----------|
| **Resumo** | Estatísticas + recomendação |
| **Dados Brutos** | Top 200 contratos do `sample` (órgão, UF, valor, data, objeto, esfera) |
| **Metodologia** | Fonte, keywords, caveat valor_global |

## Regras de Confiabilidade

Calculadas no script via `confiability(n, cv)`:

| N (amostra) | CV (variabilidade) | Confiabilidade | Ação |
|:-----------:|:------------------:|:--------------:|------|
| qualquer | >200% | **AMOSTRA_HETEROGENEA** | **Não usar mediana — keywords genéricas misturaram contratos não-comparáveis. Refinar objeto.** |
| >50 | ≤200% | ALTA | Recomendação firme |
| 20-50 | ≤200% | MEDIA | Recomendação com ressalva |
| 10-19 | ≤200% | BAIXA | "Amostra limitada — usar como referência" |
| <10 | ≤200% | INSUFICIENTE | "Considerar pesquisa adicional" |

**Por que o gate de CV?** Matching ILIKE AND restritivo previne 90% do enviesamento. Mas mesmo com AND, objetos com tokens semanticamente amplos (ex: `"limpeza hospitalar"` cobre desde produtos R$300 até serviço completo R$200k) podem produzir CV>200%. Nesse caso a mediana é estatisticamente sem sentido — o script avisa o operador via stdout `⚠ CV=...% > 200%` e a label do JSON é `AMOSTRA_HETEROGENEA`.

**Paridade DataLake vs Live (validada no pilot):**
- DataLake (`pncp_supplier_contracts` AND ILIKE) — pavimentação asfáltica SP+MG 12m: n=21, mediana R$509k, em <5s
- Live PNCP API (mesma query, 4 páginas) — alcançou apenas 1 contrato (R$465k) por timeouts da API em 3/4 modalidades, em ~120s
- Divergência mediana: 9.5% (R$465k vs R$509k) — dentro do ruído estatístico aceitável
- **Conclusão:** DataLake entrega amostra estatisticamente significativa de forma confiável; live é instável sob throttle PNCP. DataLake é fonte preferencial para qualquer análise de pricing.

## Downstream

```
/radar-b2g                               → identifica edital quente
/pricing-b2g --objeto "..." --cnpj-orgao → quanto ofertar neste órgão
/war-room-b2g {edital}                   → prepara participação com preço definido
/proposta-b2g {CNPJ}                     → inclui ROI baseado em preços reais
```

## APIs / Sources Reference

**Modo DataLake (default):**
- Tabela `pncp_supplier_contracts` (Supabase Postgres) — index `idx_psc_ni_fornecedor` BTREE
- Cliente: `scripts/datalake_helper.py::DatalakeClient`

**Modo Live (fallback):**

| API | Endpoint | Uso |
|-----|----------|-----|
| PNCP Consulta | `/api/consulta/v1/contratacoes/publicacao` | Contratos com homologado/estimado |

**Não usado neste pilot (futura extensão):**

| API | Endpoint | Para que serviria |
|-----|----------|-------------------|
| PNCP Itens | `/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/itens` | Preços unitários por item (precisa filtro adicional) |
| PNCP Arquivos | `/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos` | Especificações via PDF do edital (modo `--edital`) |

## Limitações conhecidas

1. **Frescor:** ETL `pncp_supplier_contracts` roda 3x/semana (mon/wed/fri). Para análise de contratos assinados nos últimos 2 dias, prefira `--no-datalake`.
2. **Modalidade:** o filtro `--modalidade` só funciona no fluxo live (campo ausente em `pncp_supplier_contracts`). DataLake retorna todas as modalidades.
3. **Item-level pricing:** requer extensão futura para usar `pncp/v1/orgaos/.../itens`. Pilot atual é por contrato total.
4. **`valor_global` cascade:** ver seção "Capacidades" e Metodologia do relatório.
5. **Matching de keywords é ILIKE AND (todos os tokens).** Restritivo por design — `"limpeza hospitalar"` exige AMBAS no objeto, não qualquer uma. Casos com keyword muito específica (typos, plurais não usuais) podem retornar n=0 e cair no fallback live. Para objetos com semântica ampla (ex: `"limpeza hospitalar"` cobre produtos a serviço completo), CV>200% rebaixa label para `AMOSTRA_HETEROGENEA` e avisa operador. Refinamento futuro: tsquery PT-BR com lemmatização ou similaridade vetorial.
6. **Live API instável sob carga.** Em pilot, paginação live PNCP teve 75% timeout em 4 modalidades × 3 páginas. DataLake é fonte preferencial; live só serve como diagnóstico de freshness ou inspeção pontual.

## Params

$ARGUMENTS
