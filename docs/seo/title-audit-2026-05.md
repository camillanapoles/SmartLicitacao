# pSEO Title/Meta Audit — Maio 2026

**Issue:** #768 — REPO-016
**Branch:** feat/768-repo-016-pseo-meta-refresh
**Data:** 2026-05-07

---

## 1. Páginas Low-CTR (GSC, período até 2026-05-06)

| URL | Impressões | CTR | Posição Média |
|-----|-----------|-----|--------------|
| /blog/subcontratacao-licitacoes-regras-lei-14133 | 22 | 0% | 6.7 |
| /perguntas/prazo-publicacao-edital | 22 | 0% | 6.9 |
| /blog/impugnacao-edital-quando-como-contestar | 22 | 0% | 8.6 |
| /blog/licitacoes/engenharia/ba | 14 | 0% | 5.4 |
| /blog/licitacoes/engenharia/sc | 13 | 0% | 5.2 |
| /fornecedores/53132398000186 | 12 | 0% | 5.9 |
| /blog/como-consultar-contratos-publicos-pncp | 11 | 0% | 10.3 |

### Mapeamento de Template por URL

| URL | Template | Em Escopo REPO-016? |
|-----|---------|---------------------|
| /blog/subcontratacao-licitacoes-regras-lei-14133 | blog/[slug]/page.tsx | NÃO — escopo blog |
| /perguntas/prazo-publicacao-edital | perguntas/[slug]/page.tsx | NÃO — escopo perguntas |
| /blog/impugnacao-edital-quando-como-contestar | blog/[slug]/page.tsx | NÃO — escopo blog |
| /blog/licitacoes/engenharia/ba | blog/licitacoes/[setor]/[uf]/page.tsx | NÃO — escopo blog |
| /blog/licitacoes/engenharia/sc | blog/licitacoes/[setor]/[uf]/page.tsx | NÃO — escopo blog |
| /fornecedores/53132398000186 | fornecedores/[cnpj]/page.tsx | **SIM — adicionado ao escopo** |
| /blog/como-consultar-contratos-publicos-pncp | blog/[slug]/page.tsx | NÃO — escopo blog |

**Nota importante:** Nenhuma das 7 URLs de baixo CTR mapeia diretamente para os 5 templates originalmente definidos no escopo (cnpj, orgaos, licitacoes, municipios, observatorio). O template `/fornecedores/[cnpj]` é o único hit direto do GSC e foi **adicionado ao escopo** desta PR. Os templates de blog são candidatos para uma PR futura (REPO-017 sugerido).

---

## 2. Templates Atualizados nesta PR

### 2.1 `/cnpj/[cnpj]` — Perfil B2G Empresarial

**Antes:** `"{razao_social} — Histórico de Contratos Públicos"`
**Decisão:** MUDAR — título anterior é descritivo, não transacional.
**Depois:** `"Quanto {razao_social} fatura com o governo? | SmartLic"`

**Rationale:** Query de intenção econômica alta ("quanto X fatura com governo?") é muito mais provável que o usuário B2G clique quando está avaliando um concorrente ou parceiro potencial. O modelo de intenção econômica converte melhor que o descritivo.

**Descrição:** Mantém dados factuais (total_contratos, valor_total, cnpj).

---

### 2.2 `/fornecedores/[cnpj]` — Perfil de Fornecedor Público

**Antes:** `"{razao_social} — Historico B2G | {total_contratos} contratos"`
**Decisão:** MUDAR — match direto com URL de baixo CTR no GSC.
**Depois:** `"Contratos públicos de {razao_social} — CNPJ {cnpj} | SmartLic"`

**Rationale:** Segue o modelo aprovado para cnpj. `fornecedores/[cnpj]` é distinto de `cnpj/[cnpj]`: serve dados de contratos assinados (pncp_supplier_contracts), não perfil B2G completo. Título econômico mas factual — sem "quanto fatura" pois não há dado de faturamento neste template.

**Descrição:** Atualizada com clareza sobre contratos PNCP e estados de atuação.

---

### 2.3 `/orgaos/[slug]` — Perfil de Órgão Comprador

**Antes:** `"{nome} — Licitações, Editais e Contratos"`
**Decisão:** MUDAR — título anterior é genérico.
**Depois:** `"Como {nome} compra e quais oportunidades publica? | SmartLic"`

**Rationale:** Pergunta direta que corresponde à intenção do usuário B2G pesquisando um órgão ("como a Prefeitura de X compra?"). Cria curiosidade e aumenta CTR.

**Noindex preservado:** thin-content gate (`total_licitacoes < MIN_ACTIVE_BIDS_FOR_INDEX`) mantido intacto.

---

### 2.4 `/licitacoes/[setor]` — Landing de Setor

**Antes:** `"Editais de {sector.name} 2026 — Para sua Empresa | SmartLic"`
**Decisão:** MUDAR — "Para sua Empresa" é vago.
**Depois:** `"Melhores oportunidades para empresas de {sector.name} | SmartLic"`

**Rationale:** Mais direto e orientado a resultado. Remove o ano estático "2026" que envelhece mal.

**Noindex preservado:** thin-content gate mantido.

---

### 2.5 `/municipios/[slug]` — Perfil de Município

**Antes:** `"Licitações em {nome}-{uf} — {total_licitacoes_abertas} editais abertos"`
**Decisão:** MUDAR — título sem brand e sem preposição correta.
**Depois:** `"Licitações abertas {preposicao} {nome}-{uf} | SmartLic"`

**Preposições UF implementadas inline** (conforme REPO-002):
- "no" → DF
- "em" → todos os demais UFs

**Nota:** Não existia utilitário `ufPreposicao` em `frontend/lib/` — função simples adicionada inline na função `generateMetadata`.

---

## 3. Templates Fora do Escopo desta PR

### 3.1 `/observatorio/[slug]` — Relatório Mensal

**Decisão:** DEFERIDO.

**Motivo:** O modelo aprovado `"Oportunidades em {categoria}: vale a pena disputar?"` pressupõe um campo `categoria` que não existe neste template. Os slugs são date-based (`raio-x-marco-2026`) — não há campo de categoria na interface `relatorio`. O título atual `"{N} editais em {mes} de {ano} — Raio-X das Licitações"` já carrega intenção econômica implícita (volume de editais).

**Alternativa futura:** `"{N} editais em {mes} {ano}: vale a pena disputar? | SmartLic"` — fica como sugestão para REPO-017.

### 3.2 Blog templates (4 URLs GSC low-CTR)

**Decisão:** DEFERIDO para PR futura (sugerido REPO-017).

Templates afetados:
- `blog/[slug]/page.tsx` (3 URLs)
- `blog/licitacoes/[setor]/[uf]/page.tsx` (2 URLs)

---

## 4. Templates Atualizados: Resumo

| Template | Arquivo | Título Anterior | Título Novo |
|----------|---------|----------------|-------------|
| cnpj/[cnpj] | frontend/app/cnpj/[cnpj]/page.tsx | `{razao_social} — Histórico de Contratos Públicos` | `Quanto {razao_social} fatura com o governo? \| SmartLic` |
| fornecedores/[cnpj] | frontend/app/fornecedores/[cnpj]/page.tsx | `{razao_social} — Historico B2G \| {total_contratos} contratos` | `Contratos públicos de {razao_social} — CNPJ {cnpj} \| SmartLic` |
| orgaos/[slug] | frontend/app/orgaos/[slug]/page.tsx | `{nome} — Licitações, Editais e Contratos` | `Como {nome} compra e quais oportunidades publica? \| SmartLic` |
| licitacoes/[setor] | frontend/app/licitacoes/[setor]/page.tsx | `Editais de {sector.name} 2026 — Para sua Empresa \| SmartLic` | `Melhores oportunidades para empresas de {sector.name} \| SmartLic` |
| municipios/[slug] | frontend/app/municipios/[slug]/page.tsx | `Licitações em {nome}-{uf} — {total_licitacoes_abertas} editais abertos` | `Licitações abertas {preposicao} {nome}-{uf} \| SmartLic` |

**Total: 5 templates atualizados** (4 mínimo exigido pela task + 1 bonus = fornecedores, GSC direct hit).
