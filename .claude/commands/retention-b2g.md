# /retention-b2g — Pacote de Retencao e Upsell B2G

## Purpose

Para clientes JA FECHADOS, gera relatorios periodicos de novas oportunidades, analisa performance, identifica sinais de churn, e recomenda upsell. Onde o LTV real da consultoria se constroi.

**Output primario:** `docs/retention/retention-{CNPJ}-{YYYY-MM-DD}.pdf` (report mensal do cliente)
**Output secundario:** `docs/retention/retention-{CNPJ}-{YYYY-MM-DD}.md` (markdown)
**Output terciario:** `docs/retention/health-{YYYY-MM-DD}.xlsx` (saude da carteira completa)
**Rodape:** "Tiago Sasaki - Consultor de Licitacoes (48)9 8834-4559"

---

## Usage

```
/retention-b2g 12345678000190                        # report mensal de 1 cliente
/retention-b2g all                                   # report de TODA a carteira
/retention-b2g all --health                          # dashboard de saude da carteira
/retention-b2g 12345678000190 --upsell               # foco em oportunidades de upsell
/retention-b2g 12345678000190 --churn-risk            # analise de risco de churn
```

## Capacidades — DataLake-first (v2)

Phase 1 (perfil + historico + oportunidades) executada por `scripts/retention-b2g-collect.py`:

| Aspecto | DataLake (default) | Live (fallback / cache miss) |
|---------|-------------------|------------------------------|
| Perfil cadastral | `enriched_entities` (TTL 30d) | OpenCNPJ live se cache miss |
| Contratos historicos | `pncp_supplier_contracts` (3m + baseline 12m) | n/a (DataLake mandatorio) |
| Oportunidades abertas | RPC `search_datalake` modo `abertas` filtro setor+UFs | n/a |
| Concorrencia (sinal churn) | `top_competitors(orgao_top, meses=24)` | n/a |
| Sancoes Portal Transparencia | placeholder (PT_KEY ausente em dev) | live com PT_KEY; cache `enriched_entities.data.sancoes` sub-TTL 7d |
| Latencia (1 cliente) | 3-5s | 30-60s live |

**Flags:**
- `DATALAKE_QUERY_ENABLED=true` (default) ativa
- `--no-datalake` força live full

---

## What It Does

### Phase 1: Coleta consolidada (1 invocação)

```bash
cd /mnt/d/pncp-poc

# 1 cliente
python scripts/retention-b2g-collect.py \
    --cnpj 12345678000190 \
    --setor medicamentos \
    --output docs/retention/retention-data-{CNPJ}-{YYYY-MM-DD}.json

# Toda a carteira (modo 'all')
python scripts/retention-b2g-collect.py \
    --cnpj all \
    --carteira docs/carteira-clientes.json \
    --health \
    --output docs/retention/retention-data-all-{YYYY-MM-DD}.json
```

O coletor automaticamente:

1. **Perfil** — `DatalakeClient.enriched_entity('fornecedor', cnpj)`; cache miss → OpenCNPJ live + (futuro: upsert no enriched_entities)
2. **Contratos** — `supplier_contracts(ni_fornecedor=cnpj, meses=3)` + baseline `meses=12` (para delta trimestre anterior)
3. **Oportunidades abertas** — `search_bids(ufs, dias=30, tsquery=setor_kws, modalidades=[4,5,6,8], modo='abertas')`, ranqueadas por valor desc + prazo asc, top 30
4. **Concorrência (sinal churn)** — identifica `orgao_cnpj` com mais contratos do cliente em 12m, chama `top_competitors(orgao_cnpj, meses=24)` para detectar fornecedores ganhando espaço no mesmo cliente do cliente
5. **Sancoes** — placeholder (warning emitido). Quando PT_KEY estiver disponível no `.env`, caller faz live + cache em `enriched_entities.data.sancoes`

**Output JSON (single CNPJ):**
```json
{
  "cnpj":"...","perfil":{razao_social,cnae_principal,porte,capital_social,ufs_atuacao,situacao},
  "performance":{contratos_3m, valor_3m, orgaos_unicos_3m, novos_orgaos_3m, novas_ufs_3m,
                 contratos_q_anterior, valor_q_anterior,
                 delta_vs_trimestre_anterior:{contratos,valor},
                 contratos_12m_total, valor_12m_total},
  "oportunidades":[{pncp_id, objeto_compra, valor_total_estimado, uf, orgao_cnpj,
                    data_encerramento, link_pncp}],
  "competitors_top_orgao":[{ni_fornecedor, nome_fornecedor, n_contratos, valor_total}],
  "sancoes":[...],
  "setor":"medicamentos","setor_keywords_used":[...],
  "warnings":[...],"fonte":"datalake","generated_at":"..."
}
```

**Modo `--cnpj all`:** payload `{modo:'all', n_clientes, clientes:[...]}` para dashboard de carteira.

**Phases 2-5 (analise + scores + sinais)** — Claude consome o JSON e calcula:
- Health Score (0-100) usando perfomance + sancoes + warnings
- Sinais de upsell (crescimento >30%, novas UFs, modalidade complexa, dependencia >60% 1 orgao)
- Sinais de churn (contratos_3m=0 + valor_q_anterior>0; sancao nova; competitors_top_orgao crescendo)

Os criterios estao na Phase 3-5 abaixo (preservados).

### Phase 2: Analise de Performance (@analyst)

**Metricas do cliente no periodo (mensal):**

| Metrica | Calculo | Meta |
|---------|---------|------|
| Editais monitorados | Total de editais identificados para o cliente | Crescente |
| Editais participados | Editais em que o cliente de fato participou | >30% dos monitorados |
| Editais ganhos | Contratos novos no periodo | Crescente |
| Taxa de vitoria | Ganhos / Participados | >20% |
| Valor contratado | Soma dos novos contratos | Crescente |
| ROI da consultoria | (Valor_contratado - Custo_consultoria) / Custo_consultoria | >5x |
| Novas UFs | UFs de atuacao que o cliente nao tinha antes | Expansao |
| Novos orgaos | Orgaos com quem o cliente nunca contratou | Diversificacao |

**Tendencia (3 meses rolling):**
- Faturamento gov: subindo / estavel / caindo
- Participacoes: aumentando / estavel / diminuindo
- Diversificacao: expandindo / concentrando

### Phase 3: Score de Saude do Cliente (@analyst)

**Customer Health Score (0-100):**

| Dimensao | Peso | Indicadores |
|----------|------|-------------|
| **Engajamento** | 30% | Frequencia de interacao, responde rapido, pede analises |
| **Resultados** | 30% | Contratos ganhos, valor, ROI positivo |
| **Expansao** | 20% | Novas UFs, novos orgaos, novos setores |
| **Risco** | 20% | Sancoes, queda de participacao, silencio prolongado |

| Score | Status | Acao |
|-------|--------|------|
| 80-100 | Saudavel | Manter + buscar upsell |
| 60-79 | Atencao | Aumentar frequencia de reports, proatividade |
| 40-59 | Risco | Reuniao urgente, entender dores, ajustar pacote |
| 0-39 | Critico | Intervencao imediata, risco alto de churn |

### Phase 4: Motor de Upsell (@analyst)

**Sinais de upsell (detectados automaticamente):**

| Sinal | Trigger | Oferta |
|-------|---------|--------|
| **Crescimento rapido** | Faturamento gov cresceu >30% em 3 meses | Upgrade de pacote |
| **Multi-setor** | Cliente tem CNAEs em setores nao monitorados | Adicionar monitoramento de setores adjacentes |
| **Expansao geografica** | Ganhou contrato em UF nova | Report de oportunidades na nova UF |
| **Modalidade complexa** | Primeiro contrato em Concorrencia (T+P) | Suporte a elaboracao de propostas tecnicas |
| **Volume alto** | >10 participacoes/mes | Gestao dedicada de pipeline (Enterprise) |
| **Dependencia de orgao** | >60% da receita de 1 orgao | Diversificacao de carteira de orgaos |

**Recomendacao de upsell personalizada:**
- Qual upgrade especifico faz sentido para ESTE cliente
- ROI projetado do upgrade
- Script de abordagem para o upsell

### Phase 5: Deteccao de Churn (@analyst)

**Sinais de churn (red flags):**

| Sinal | Peso | Deteccao |
|-------|------|----------|
| **Silencio** | Alto | Sem interacao ha >21 dias |
| **Queda de resultados** | Alto | Contratos ganhos caiu >50% vs trimestre anterior |
| **Reducao de participacao** | Medio | Participa de menos editais mesmo com mais oportunidades |
| **Questionou valor** | Medio | Pediu desconto, questionou entregaveis |
| **Mudanca de QSA** | Medio | Novo socio — pode mudar prioridades |
| **Sancao nova** | Alto | Impedimento pode fazer cliente abandonar licitacoes |
| **Concorrente** | Alto | Lead mencionou outro fornecedor de monitoramento |

**Acao por nivel de risco:**
- **Risco Baixo:** Aumentar proatividade, mandar report extra
- **Risco Medio:** Agendar call, perguntar satisfacao, ajustar entregas
- **Risco Alto:** Oferecer mes gratis, desconto de retencao, reuniao presencial

### Phase 6: Geracao dos Outputs (@dev)

#### Report Individual (PDF por cliente)

**Estrutura:**
1. **Capa** — "{Nome_Fantasia} — Relatorio Mensal de Oportunidades — {Mes/Ano}"
2. **Resumo Executivo** — 5 bullet points: resultados, tendencia, destaque do mes
3. **Performance** — Metricas com comparacao vs mes anterior (setas verde/vermelha)
4. **Oportunidades Abertas** — Top 10 editais abertos relevantes para o cliente
5. **Conquistas do Periodo** — Contratos ganhos (se houver)
6. **Radar de Mercado** — Tendencias do setor, novos orgaos comprando, mudancas regulatorias
7. **Recomendacoes** — Acoes priorizadas para o proximo mes
8. **Proximos Passos** — CTA especifico baseado no que foi identificado

**Rodape:** "Tiago Sasaki - Consultor de Licitacoes (48)9 8834-4559"

#### Dashboard de Saude da Carteira (Excel)

**Aba "Saude":**
| Coluna | Descricao |
|--------|-----------|
| Cliente | Nome fantasia |
| CNPJ | CNPJ formatado |
| Pacote | Basico/Premium/Enterprise |
| MRR | Receita mensal do cliente |
| Health Score | 0-100 |
| Status | Saudavel/Atencao/Risco/Critico |
| Tendencia | Subindo/Estavel/Caindo |
| Ultimo Contato | Data |
| Contratos/Mes (3m) | Media rolling |
| Sinal Upsell | Flag (se detectado) |
| Sinal Churn | Flag (se detectado) |
| Proximo Passo | Acao recomendada |

**Aba "Upsell":**
- Clientes com sinais de upsell
- Oferta recomendada
- Valor incremental projetado
- Script de abordagem

**Aba "Churn Risk":**
- Clientes com sinais de churn ordenados por risco
- Red flags detalhados
- Plano de retencao por cliente

**Aba "Financeiro":**
- MRR total da carteira
- MRR por pacote
- Receita em risco (clientes com health <60)
- Projecao de receita proximos 3 meses
- Cenarios: se perder {N} clientes vs se fizer {N} upsells

## Downstream

```
/intel-b2g + /qualify-b2g + /cadencia-b2g + /proposta-b2g  → Aquisicao
/pipeline-b2g                                               → Gestao
/retention-b2g {CNPJ}                                       → Report mensal para cliente
/retention-b2g all --health                                  → Saude da carteira
/retention-b2g {CNPJ} --upsell                               → Oportunidade de upgrade
/retention-b2g {CNPJ} --churn-risk                            → Intervencao preventiva
```

## APIs / Sources Reference

**Modo DataLake (default — Phase 1):**
- Tabela `pncp_supplier_contracts` (Supabase) — `idx_psc_ni_fornecedor` BTREE
- Tabela `enriched_entities` — perfil cache TTL 30d
- RPC `search_datalake` — oportunidades abertas
- Cliente: `scripts/datalake_helper.py::DatalakeClient`

**Modo Live (cache miss):**

| API | Endpoint | Uso |
|-----|----------|-----|
| OpenCNPJ | `https://api.opencnpj.org/{CNPJ}` | Perfil cadastral (cache miss) |
| Portal Transparência | `api.portaldatransparencia.gov.br/...` | Sanções (requer PT_KEY) |

## Limitações conhecidas

1. **Frescor:** ETL `pncp_supplier_contracts` 3×/sem (mon/wed/fri). Para `contratos_3m=0` em terça-feira após contrato segunda, considere fallback live (futuro — não implementado neste pilot).
2. **Sanções placeholder:** este pilot não consulta Portal Transparência. Quando `PT_KEY` for setado em `.env`, o coletor cacheará em `enriched_entities.data.sancoes` com sub-TTL 7d.
3. **Setor sem keywords:** se `--setor` não estiver em `backend/sectors_data.yaml`, oportunidades retornam vazio (sem fallback CNAE neste pilot).
4. **enriched_entities upsert futuro:** no pilot, OpenCNPJ live em cache miss apenas retorna o payload; não persiste no `enriched_entities` (requires service-role write — backlog).

## Ciclo Mensal Recomendado

| Semana | Acao | Command |
|--------|------|---------|
| **Semana 1** | Gerar reports mensais para cada cliente | `/retention-b2g {CNPJ}` (por cliente) |
| **Semana 1** | Enviar report por email/WhatsApp | Manual |
| **Semana 2** | Analisar saude da carteira | `/retention-b2g all --health` |
| **Semana 2** | Abordar clientes com upsell | `/retention-b2g {CNPJ} --upsell` |
| **Semana 3** | Intervir em churn risks | `/retention-b2g {CNPJ} --churn-risk` |
| **Semana 4** | Mapear novos leads | `/intel-b2g` → `/qualify-b2g` → `/cadencia-b2g` |

## Params

$ARGUMENTS
