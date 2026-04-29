# /radar-b2g — Monitoramento Contínuo de Editais B2G

## Purpose

Varredura diária automatizada de TODOS os editais novos relevantes para um cliente ou carteira de clientes. Baixa os PDFs, analisa os documentos, e entrega um briefing acionável com os editais que merecem atenção HOJE. O consultor acorda e já sabe o que fazer.

**Output primário:** `docs/radar/radar-{YYYY-MM-DD}.md` (briefing diário consolidado)
**Output por cliente:** `docs/radar/radar-{CNPJ}-{YYYY-MM-DD}.md` (briefing individual)
**Output alertas:** `docs/radar/alertas-{YYYY-MM-DD}.md` (apenas urgências)

---

## Usage

```
/radar-b2g                                           # varredura para TODA a carteira
/radar-b2g 12345678000190                            # varredura para 1 CNPJ
/radar-b2g --carteira docs/carteira-clientes.json    # usa arquivo de carteira
/radar-b2g --setor medicamentos                      # varredura por setor (sem cliente específico)
/radar-b2g --dias 3                                  # editais dos últimos 3 dias (padrão: 1)
/radar-b2g --urgente                                 # só editais com encerramento em <7 dias
```

## Arquivo de Carteira (opcional)

Se `--carteira` fornecido, usar JSON com perfil de cada cliente:

```json
{
  "clientes": [
    {
      "cnpj": "12345678000190",
      "nome_fantasia": "Empresa Alpha",
      "setor": "medicamentos",
      "keywords_extras": ["farmaceutico", "hospitalar"],
      "ufs_interesse": ["SP", "RJ", "MG", "PR"],
      "valor_min": 50000,
      "valor_max": 5000000,
      "modalidades": [4, 5, 6, 8],
      "pacote": "premium",
      "decisor": "João Silva",
      "whatsapp": "5511999998888",
      "email": "joao@alpha.com.br"
    }
  ]
}
```

Se carteira não fornecida, buscar CNPJs de reports anteriores em `docs/reports/` e `docs/propostas/` para inferir a carteira.

## Capacidades — DataLake-first (v2)

Phase 1 + 2a são executadas pelo coletor `scripts/radar-b2g-collect.py`:

| Aspecto | DataLake (default) | Live (fallback) |
|---------|-------------------|-----------------|
| Fonte | Tabela `pncp_raw_bids` via RPC `search_datalake` | API `pncp.gov.br/api/consulta/v1/contratacoes/publicacao` |
| Latência (carteira inteira) | ~30-90s | 5-10min |
| Hybrid mode | Se ETL atrasou >30min, complementa com 1 curl janela `[last_etl_at, NOW()]` | n/a |
| Frescor | ETL incremental 3×/dia (8h/14h/20h BRT) + complemento live | Real-time |
| Rate limit | Nenhum | ~100 req/min PNCP |

**NÃO migrado (continuam live, executados por Claude downstream após o coletor):**
- **Phase 2b (PCP v2):** API externa, não ingerida no DataLake. Claude executa direto se `--no-pcp` ausente.
- **Phase 3 (PDFs):** lista + download de arquivos. DataLake não armazena binários.

**Flags:**
- `DATALAKE_QUERY_ENABLED=true` no `.env` ativa DataLake (default)
- `--no-datalake` força fallback live full
- `--no-pcp` pula Phase 2b (default off — Claude executa)
- `--no-pdfs` pula Phase 3 (modo light)

---

## What It Does

### Phase 1+2a: Varredura DataLake-first (1 invocação)

```bash
cd /mnt/d/pncp-poc
python scripts/radar-b2g-collect.py \
    --carteira docs/carteira-clientes.json \
    --dias {DIAS} \
    [--urgente] [--no-datalake] [--no-pcp] [--no-pdfs] \
    --output docs/radar/radar-data-{YYYY-MM-DD}.json
```

Modos alternativos:
```bash
# 1 CNPJ específico (sem carteira)
python scripts/radar-b2g-collect.py --cnpj 12345678000190 --setor medicamentos --uf SP,RJ --dias 1 \
  --output docs/radar/radar-data-{CNPJ}-{YYYY-MM-DD}.json

# 1 setor (varredura genérica)
python scripts/radar-b2g-collect.py --setor uniformes --uf SP,MG --dias 1 \
  --output docs/radar/radar-data-uniformes-{YYYY-MM-DD}.json
```

O script automaticamente:

1. **Carrega carteira** (`--carteira` json) ou monta carteira ad-hoc de `--cnpj`/`--setor`.
2. **Resolve keywords** via `backend/sectors_data.yaml` + `keywords_extras` por cliente.
3. **Consolida UFs/keywords/modalidades** da carteira em uma tsquery OR (com `&` por palavra composta).
4. **Tenta DataLake primeiro:**
   - `DatalakeClient.search_bids(ufs, dias, tsquery, modalidades=[4,5,6,8], modo='abertas' if urgente else 'publicacao', paginate_by_uf_modalidade=True)`
   - Hybrid: `last_etl_at()` → se gap > 30min, 1 curl PNCP `[last_etl_at, NOW()]` (modo `publicacao`).
5. **Fallback live** (preserva fluxo legado) se DataLake desabilitado/falha.
6. **Calcula matching cliente×edital** (5 dimensões — keywords/valor/geo/prazo/habilitação).
7. **Output JSON estruturado** consumido pelas Phases 3-5.

**Output JSON:**
```json
{
  "fonte": "datalake|datalake_hybrid|live",
  "data_referencia": "2026-04-29",
  "dias": 1,
  "carteira": [{cnpj, nome_fantasia, setor, keywords, ufs_interesse, valor_min, valor_max}],
  "editais": [{pncp_id, objeto_compra, valor_total_estimado, uf, municipio, orgao_cnpj,
               orgao_razao_social, modalidade_id, modalidade_nome, data_publicacao,
               data_encerramento, link_pncp, ...}],
  "matching": [{cnpj_cliente, nome_cliente, edital_pncp_id, score, tag,
                dimensions:{keywords,valor,geografia,prazo,habilitacao}}],
  "etl_gap_min": 14, "live_complement_added": 7, "warnings":[],
  "generated_at": "2026-04-29T06:00:00"
}
```

### Phase 2b: PCP v2 (Claude direto — não migrado)

```bash
curl -s "https://compras.api.portaldecompraspublicas.com.br/v2/licitacao/processos?page=1"
```
- Paginar (max 3 páginas)
- Filtrar client-side por keywords + data
- Append em `editais` do JSON após dedup por `pncp_id`/`numeroControlePNCP`

### Phase 2c: Prazos vencendo (Claude direto)

Além de novos editais, checar editais já conhecidos (de reports anteriores em `docs/reports/`) cujo `dataEncerramentoProposta` está em <7 dias.

### Phase 3: Análise Documental Rápida (Claude direto)

Para cada edital novo encontrado, executar análise documental SIMPLIFICADA (versão fast do report-b2g Phase 2b):

**3a. Buscar documentos do edital**
```bash
curl -s "https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj_orgao}/compras/{anoCompra}/{sequencialCompra}/arquivos"
```

**3b. Download do PDF principal** (apenas tipoDocumentoId: 2 = Edital)
```bash
curl -s -o /tmp/radar_{cnpj}_{ano}_{seq}.pdf \
  "https://pncp.gov.br/pncp-api/v1/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos/1"
```

- Apenas 1 documento por edital (o edital principal — sem TR ou anexos)
- Max 20 páginas lidas
- Se PDF >5MB ou download falhar, usar apenas metadados da API

**3c. Análise rápida pelo Claude**

Extrair apenas os campos CRÍTICOS para decisão imediata:

| Campo | Prioridade |
|-------|-----------|
| Critério de julgamento (menor preço / técnica+preço) | CRÍTICA |
| Data e hora de encerramento | CRÍTICA |
| Valor estimado (se divulgado) | ALTA |
| Requisitos de habilitação mais restritivos | ALTA |
| Visita técnica obrigatória? (data limite) | ALTA |
| Amostra exigida? | MÉDIA |
| Exclusivo ME/EPP? | MÉDIA |
| Red flags (1-2 mais relevantes) | MÉDIA |
| Resumo do escopo (1 frase) | ALTA |

**Tempo-alvo:** <2 minutos por edital (análise rápida, não profunda como o report-b2g).

### Phase 4: Matching Cliente × Edital (já no coletor)

Já calculado em `payload.matching` pelo `radar-b2g-collect.py::score_matching`. Claude apenas consome — não recalcula.

**Relevance Score (0-100):**

| Dimensão | Peso | Critério |
|----------|------|----------|
| Aderência de keywords | 30% | Quantas keywords do setor aparecem no objeto |
| Faixa de valor | 20% | Valor estimado dentro do range do cliente |
| Geografia | 20% | Edital na UF de interesse do cliente |
| Prazo | 15% | Dias até encerramento (mais tempo = melhor) |
| Habilitação | 15% | Cliente provável apto vs não apto (capital_social / valor_total_estimado >= 10%) |

**Classificação:**

| Score | Tag | Ação |
|-------|-----|------|
| 80-100 | **QUENTE** | Alertar imediatamente — alta aderência |
| 60-79 | **MORNO** | Incluir no briefing diário |
| 40-59 | **FRIO** | Mencionar brevemente |
| <40 | Descartado | Não incluir no briefing |

### Phase 5: Geração do Briefing (@dev)

#### Briefing Diário Consolidado (`radar-{YYYY-MM-DD}.md`)

```markdown
# Radar B2G — {data}

## Resumo
- **Editais novos encontrados:** {N}
- **Relevantes para a carteira:** {N}
- **Alertas QUENTES:** {N}
- **Prazos vencendo esta semana:** {N}
- **Clientes impactados:** {N} de {total}

---

## 🔴 ALERTAS QUENTES (ação em 48h)

### 1. {Objeto resumido} — R${valor}
- **Órgão:** {nome} ({UF})
- **Encerra:** {data} ({N} dias)
- **Modalidade:** {tipo}
- **Critério:** {menor preço / T+P}
- **Relevante para:** {Cliente A} (score {X}), {Cliente B} (score {Y})
- **Do edital:** {1-2 fatos críticos extraídos do PDF}
- **Red flags:** {se houver}
- **Link:** {URL PNCP}

### 2. ...

---

## 🟡 EDITAIS MORNOS (avaliar esta semana)

| # | Objeto | Órgão | UF | Valor | Encerra | Cliente | Score |
|---|--------|-------|----|-------|---------|---------|-------|
| 1 | {resumo} | {orgao} | {UF} | R${val} | {data} | {nome} | {score} |
| ... |

---

## ⏰ PRAZOS VENCENDO (próximos 7 dias)

| Edital | Órgão | Encerra | Cliente | Status |
|--------|-------|---------|---------|--------|
| {num} | {orgao} | {data} ({N}d) | {nome} | Alerta enviado / Pendente |

---

## 📊 Estatísticas do Dia
- Editais varridos: {N} (PNCP: {N}, PCP: {N})
- PDFs analisados: {N}
- Taxa de relevância: {N}% (relevantes / total)
- Setores com mais editais: {setor1} ({N}), {setor2} ({N})
- UFs mais ativas: {UF1} ({N}), {UF2} ({N})
```

#### Briefing Individual por Cliente (`radar-{CNPJ}-{YYYY-MM-DD}.md`)

Versão filtrada apenas com editais relevantes para aquele CNPJ. Formato pronto para copiar e enviar ao cliente via WhatsApp/Email.

```markdown
# Radar de Oportunidades — {Nome Fantasia}
**Data:** {data} | **Setor:** {setor} | **UFs:** {ufs}

## Novos Editais Relevantes ({N})

### ⭐ {Objeto}
- **Órgão:** {nome} — {município}/{UF}
- **Valor:** R${valor}
- **Encerra:** {data} ({N} dias)
- **Critério:** {tipo}
- **O que você precisa:** {resumo de habilitação em 1 linha}
- **Nossa avaliação:** {PARTICIPAR / AVALIAR / MONITORAR}

### ...

## Prazos desta Semana
[editais já conhecidos com prazo vencendo]

---
Tiago Sasaki - Consultor de Licitações
(48)9 8834-4559
```

#### Output de Alertas (`alertas-{YYYY-MM-DD}.md`)

Apenas editais QUENTES (score >80) + prazos <3 dias. Formato ultra-compacto para ação imediata.

## Automação (recomendação de uso)

Este command é projetado para execução diária. Workflow recomendado:

```
06:00  /radar-b2g                           → gera briefing do dia
06:05  Consultor revisa alertas QUENTES     → 5 minutos
06:10  Encaminha briefings individuais       → WhatsApp/Email por cliente
       aos clientes relevantes
```

Para automatizar a execução diária, usar o command `/loop`:
```
/loop 24h /radar-b2g
```

Ou executar manualmente toda manhã como primeira tarefa.

## Downstream

```
/radar-b2g                               → identifica edital quente
/report-b2g {CNPJ}                       → análise profunda para o cliente
/war-room-b2g {edital}                   → prepara participação
/pricing-b2g {objeto} --setor {setor}    → inteligência de preço para ofertar
```

## APIs / Sources Reference

**Modo DataLake (default — Phase 1+2a):**
- Tabela `pncp_raw_bids` (Supabase Postgres) via RPC `search_datalake`
- Cliente: `scripts/datalake_helper.py::DatalakeClient`
- Modo híbrido: `last_etl_at()` + complemento live se gap >30min

**Modo Live (fallback ou complemento):**

| API | Endpoint | Uso no Radar |
|-----|----------|-------------|
| PNCP Consulta | `/api/consulta/v1/contratacoes/publicacao` | Phase 2a fallback / hybrid complement |
| PNCP Arquivos | `/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos` | Phase 3a — sempre live (binários) |
| PNCP Download | `/pncp-api/v1/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos/{n}` | Phase 3b — sempre live (binários) |
| PCP v2 | `compras.api.portaldecompraspublicas.com.br/v2/licitacao/processos` | Phase 2b — sempre live (não ingerido) |

## Limitações conhecidas

1. **Frescor:** ETL `pncp_raw_bids` roda incremental 3×/dia (8/14/20h BRT). Modo híbrido cobre gaps >30min com 1 curl PNCP. Para `--urgente` (modo `abertas`), o complemento live é desativado pois `dataEncerramentoProposta` não tem gap material.
2. **PCP v2 fora do DataLake:** `--no-pcp` ausente fará Claude executar Phase 2b separadamente (curl direto PCP).
3. **PDFs sempre live:** Phase 3 não usa DataLake (binários não armazenados).
4. **Compute cost:** com carteira full (27 UFs × 4 modalidades = 108 RPCs paginados), cada execução custa ~108 chamadas RPC + opcionalmente ~20 curls hybrid. 4×/dia = ~432-512 RPCs/dia.
5. **tsquery sintetizada:** keywords compostas (ex: "limpeza hospitalar") são convertidas para `(limpeza & hospitalar)`. Setores com >100 keywords podem produzir tsquery longa com alto fan-out — considere CSAT por cliente em vez de carteira agregada se latência crescer.

## Params

$ARGUMENTS
