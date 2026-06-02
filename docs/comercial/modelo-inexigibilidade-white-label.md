# Modelo de Proposta — Contratação Direta por Inexigibilidade (Art. 74, I, Lei 14.133)

## SmartLic — Plataforma de Inteligência em Licitações Públicas

> **Documento template para órgãos públicos.** Substitua `{{VAR}}` pelos dados do caso concreto.
> Versão: 1.0 — Junho 2026

---

## 1. Dados do Órgão Contratante

| Campo | Preenchimento |
|-------|---------------|
| Órgão | `{{ORGAO_NOME}}` |
| CNPJ | `{{ORGAO_CNPJ}}` |
| Endereço | `{{ORGAO_ENDERECO}}` |
| Município/UF | `{{ORGAO_MUNICIPIO}}` / `{{ORGAO_UF}}` |
| Gestor responsável | `{{GESTOR_NOME_CARGO}}` |
| Contato | `{{GESTOR_EMAIL}}` / `{{GESTOR_TELEFONE}}` |

---

## 2. Dados da Contratada

| Campo | Preenchimento |
|-------|---------------|
| Razão Social | CONFENGE Avaliações e Inteligência Artificial LTDA |
| CNPJ | 52.407.089/0001-09 |
| Endereço | Av. Pref. Osmar Cunha, 416 — Centro, Florianópolis — SC, 88015-100 |
| Representante Legal | `{{REPRESENTANTE_NOME}}` |

---

## 3. Objeto

Contratação de licenciamento e suporte da plataforma **SmartLic** — sistema integrado de inteligência artificial voltado à busca multi-fonte, classificação setorial automatizada e análise de viabilidade de licitações públicas — para uso pelo `{{ORGAO_NOME}}`.

---

## 4. Fundamentação Jurídica

### 4.1. Art. 74, I, §3º da Lei 14.133/2021

A contratação direta por inexigibilidade de licitação é cabível quando houver **inviabilidade de competição**, nos termos do Art. 74, inciso I da Lei 14.133/2021:

> **Art. 74.** É inexigível a licitação quando inviável a competição, em especial nos casos de:
>
> **I —** aquisição de materiais, de equipamentos ou de gêneros que só possam ser fornecidos por produtor, empresa ou representante comercial exclusivo;
>
> **§ 3º** Para os fins do inciso I do **caput** deste artigo, considera-se empresa exclusiva aquela que detenha **exclusividade de entrega** ou **exclusividade de representação comercial** devidamente comprovada por documento do fornecedor, ou ainda aquela cujo produto ou serviço **não possa ser substituído por similar** em razão de **singularidade técnica**.

### 4.2. Justificativa de Singularidade

A plataforma SmartLic apresenta **singularidade técnica** que inviabiliza a competição pelos seguintes fundamentos:

1. **Sistema proprietário de classificação setorial por IA:** O SmartLic emprega modelo de linguagem proprietário (GPT-4.1-nano) especialmente ajustado para classificação semântica de editais em 20 setores econômicos, com arquitetura de decisão em três camadas (keyword → llm_standard → llm_zero_match) que não encontra equivalente em solução de prateleira ou em outro fornecedor do mercado brasileiro.

2. **Multi-fonte consolidada em tempo real:** Agrega exclusivamente as três principais bases de dados de compras públicas brasileiras — PNCP (Portal Nacional de Contratações Públicas), PCP v2 (Portal de Compras Públicas) e ComprasGov v3 (Dados Abertos) — em pipeline único de deduplicação e busca, eliminando a necessidade de consulta fragmentada a múltiplos sistemas.

3. **Análise de viabilidade em 4 fatores proprietários:** A plataforma aplica modelo de scoring ponderado (modalidade 30%, prazo 25%, valor estimado 25%, geografia 20%) com pesos validados contra série histórica de editais vitoriosos, o que constitui know-how técnico não replicável por meios convencionais.

4. **Arquitetura de cache e desempenho:** Infraestrutura em três camadas (L1 InMemoryCache, L2 Redis, L3 Supabase) com busca em DataLake PostgreSQL de ~1,5 milhão de registros com resposta <100ms p95, sem equivalente funcional disponível no mercado para contratação pública.

### 4.3. Enquadramento Legal Detalhado

| Requisito Legal | Atendimento |
|-----------------|-------------|
| Inviabilidade de competição (Art. 74, I) | Serviço singular, com características técnicas proprietárias não reproduzíveis por múltiplos fornecedores no mercado brasileiro |
| Singularidade técnica (§3º) | Demonstrada na Seção 4.2 |
| Comprovação de exclusividade ou singularidade | Relatório técnico anexo + atestados de capacidade técnica |
| Vantajosidade econômica | Justificada na Seção 6 |

---

## 5. Atestados de Capacidade Técnica

*Anexar nesta seção:*

- [ ] Atestado de capacidade técnica emitido por cliente pessoa jurídica de direito público ou privado
- [ ] Comprovação de execução de serviço similar no mercado de inteligência em licitações
- [ ] Certidões de regularidade fiscal e trabalhista
- [ ] Certidão de falência e recuperação judicial

### Atestados anexados

| # | Emitente | Objeto | Data |
|---|----------|--------|------|
| `{{ATESTADO_1_EMITENTE}}` | `{{ATESTADO_1_OBJETO}}` | `{{ATESTADO_1_DATA}}` |
| `{{ATESTADO_2_EMITENTE}}` | `{{ATESTADO_2_OBJETO}}` | `{{ATESTADO_2_DATA}}` |
| `{{ATESTADO_3_EMITENTE}}` | `{{ATESTADO_3_OBJETO}}` | `{{ATESTADO_3_DATA}}` |

---

## 6. Estrutura da Proposta Comercial

### 6.1. Escopo do Fornecimento

| Item | Descrição | Quantidade |
|------|-----------|------------|
| 1 | Licenciamento plataforma SmartLic — busca multi-fonte (PNCP + PCP + ComprasGov) | `{{QTD_MESES}}` meses |
| 2 | Classificação setorial por IA (20 setores) | Incluso no item 1 |
| 3 | Análise de viabilidade 4 fatores por edital | Incluso no item 1 |
| 4 | Relatórios executivos e exportação Excel | Incluso no item 1 |
| 5 | Suporte técnico e atualizações | `{{NIVEL_SUPORTE}}` |
| 6 | Treinamento inicial da equipe | `{{CARGA_TREINAMENTO}}` horas |
| 7 | Customizações e integrações | Conforme TR `{{TR_ANEXO}}` |

### 6.2. Investimento

| Rubrica | Valor (R$) |
|---------|-----------|
| Licenciamento anual (parcela única) | `{{VALOR_ANUAL}}` |
| Suporte e manutenção | `{{VALOR_SUPORTE}}` |
| Treinamento | `{{VALOR_TREINAMENTO}}` |
| **Valor total** | **R$ `{{VALOR_TOTAL}}`** |
| **Valor mensal estimado** | **R$ `{{VALOR_MENSAL}}`** |
| **Desconto para pagamento antecipado** | `{{DESCONTO_ANTECIPADO}}`% |

### 6.3. Condições de Pagamento

- `{{CONDICAO_PAGAMENTO}}`
- Reajuste anual por `{{INDICE_REAJUSTE}}` (IPCA/IGP-M)
- Vigência: `{{VIGENCIA_MESES}}` meses, prorrogável por iguais períodos

### 6.4. Vigência e Prorrogação

- **Prazo de vigência:** `{{VIGENCIA_MESES}}` meses, contados da assinatura do contrato
- **Prorrogação:** Nos termos do Art. 106 da Lei 14.133/2021, mediante termo aditivo

---

## 7. Cronograma de Implantação

| Fase | Prazo (dias corridos) | Descrição |
|------|----------------------|-----------|
| Fase 1 — Setup | Dias 1–5 | Provisionamento de ambiente, configuração de acesso |
| Fase 2 — Parametrização | Dias 6–10 | Customização de setores e filtros conforme demanda do órgão |
| Fase 3 — Treinamento | Dias 11–12 | Treinamento da equipe usuária (carga horária: `{{CARGA_TREINAMENTO}}`h) |
| Fase 4 — Operação assistida | Dias 13–20 | Suporte intensivo para primeiras buscas e análises |
| Fase 5 — Operação autônoma | Dia 21+ | Transferência para operação com suporte regular |

---

## 8. Gestão de Riscos

| Risco | Probabilidade | Mitigação |
|-------|--------------|-----------|
| Indisponibilidade das fontes de dados (PNCP/ComprasGov) | Média | Cache local com 24h de retenção + fallback para dados do DataLake |
| Alteração unilateral na Lei 14.133 | Baixa | Atualização contínua do sistema acompanhando alterações normativas |
| Descontinuidade de serviço | Baixa | SLA 99,5% com monitoramento 24/7 e notificação proativa |

---

## 9. Considerações Finais

A contratação por inexigibilidade nos termos do Art. 74, I e §3º da Lei 14.133/2021 é juridicamente segura e vantajosa para a administração pública, considerando:

1. **Economicidade:** Valor compatível com o mercado de soluções de inteligência em licitações, com custo inferior ao equivalente de equipe interna dedicada
2. **Eficiência:** Redução de tempo de análise de editais em mais de 70% em relação ao método manual
3. **Qualidade técnica:** Sistema proprietário com resultados validados em benchmark contra base de 15 mil editais classificados
4. **Transparência:** Relatórios auditáveis com trilha de classificação por edital

---

*Documento gerado em {{DATA_EMISSAO}}*

**CONFENGE Avaliações e Inteligência Artificial LTDA**
SmartLic.tech — Inteligência em Licitações Públicas
