# Legal Audit — Disclaimers & Promessas — 2026-05-07

## Sumário Executivo

Scan automatizado (grep) + revisão manual de 10 arquivos críticos do frontend e templates de email.

**Total de ocorrências com risco legal:** 14 itens identificados  
**Riscos ALTO:** 3 (CNPJ divergente, garantia de reembolso inconsistente, SLA enterprise não implementado)  
**Riscos MÉDIO:** 6 (linguagem ambígua de resultado, promises implícitas, "nunca perca" em copy)  
**Riscos BAIXO:** 5 (uso contextualmente correto de "garantia" técnica de licitação, cosmético)

**Achado mais crítico:** CNPJ divergente entre Footer (`56.688.745/0001-00`) e Política de Privacidade (`56.528.581/0001-00`). Divergência em documento legal é violação de transparência com risco regulatório real.

---

## Metodologia

- Scan automatizado com `grep` em todos os `.tsx` e `.ts` do `frontend/`
- Revisão manual dos arquivos listados no escopo: Footer, privacidade, termos, hero, valueProps, planos, fundadores, ajuda, buscar
- Padrões buscados: garantia/Garantia, vença/ganhe, automaticamente/nunca perca, parceiro oficial/credenciado
- Riscos classificados por impacto jurídico:
  - **ALTO**: Potencial violação CONAR (publicidade enganosa), CDC (promessa não cumprida) ou inconsistência em documento legal
  - **MÉDIO**: Ambiguidade que pode induzir expectativa não garantida pelo serviço
  - **BAIXO**: Uso contextualmente correto ou cosmético, sem risco jurídico imediato

---

## Tabela de Ocorrências

| # | Arquivo | Linha | Texto encontrado | Risco | Recomendação |
|---|---------|-------|-----------------|-------|-------------|
| 1 | `frontend/app/components/Footer.tsx` | 277 | `CNPJ 56.688.745/0001-00` | **ALTO** | Verificar CNPJ correto na Receita Federal. Corrigir em todos os documentos. Ver REPO-005. |
| 2 | `frontend/app/privacidade/page.tsx` | 28 | `CNPJ sob o n. 56.528.581/0001-00` | **ALTO** | CNPJ diferente do Footer. Divergência em documento legal LGPD é crítica. Ver item 1. |
| 3 | `frontend/app/components/TrialConversionScreen.tsx` | 292 | `Garantia 30 dias` (badge no conversion screen) | **ALTO** | Termos de Uso garantem apenas 7 dias (seção 6.2), mas Fundadores têm 30 dias. Copy sem qualificação pode criar expectativa de 30 dias para planos pagos regulares. Adicionar qualificação ("Fundadores: 30 dias / Pro: 7 dias") ou alinhar com termos. |
| 4 | `frontend/app/termos/fundadores/page.tsx` | 61 | `SLA enterprise com garantia de uptime contratual` (lista do que NÃO está incluso) | **MÉDIO** | Menção de "SLA enterprise com garantia de uptime contratual" implica que esse produto poderia existir — porém não está definido em nenhum lugar. Risco baixo pois está na seção de exclusões, mas pode gerar expectativa. |
| 5 | `frontend/app/fundadores/components/FundadoresFAQ.tsx` | 21 | `Sim. Oferecemos 30 dias de garantia. Se não ficar satisfeito por qualquer motivo dentro deste prazo, devolvemos 100% do valor pago sem questionamentos.` | **MÉDIO** | "Sem questionamentos" é promessa operacional que precisa estar nos Termos do Plano Fundadores. Verificar se está em Termos/Fundadores. (Termos/Fundadores art. 8 não foi lido — verificar alinhamento). |
| 6 | `frontend/app/fundadores/page.tsx` | 65 | `jsonLdFaq` — mesmo texto acima em schema.org | **MÉDIO** | Dado estruturado em JSON-LD indexado pelo Google. Se a promessa de reembolso não estiver formalizada nos termos, gera inconsistência indexável. |
| 7 | `frontend/app/fundadores/FundadoresClient.tsx` | 210 | `Garanta sua vaga agora` (CTA de ação) | **MÉDIO** | "Garanta" implica reserva futura garantida. Se o produto pode ser descontinuado, usar "Reserve" ou "Adquira" é mais seguro. Risco moderado — CDC art. 30 torna vinculante oferta pública. |
| 8 | `frontend/lib/copy/valueProps.ts` | 175 | `"Você Nunca Perde uma Oportunidade Por Não Saber Que Ela Existe"` (título de feature) | **MÉDIO** | Promessa absoluta ("nunca"). O serviço tem latência de ingestão (cron diário + incremental 3x/dia). Uma licitação publicada às 23h pode não aparecer até às 08h do dia seguinte. Adicionar qualificação: "Monitore oportunidades em 27 UFs — sem precisar acessar dezenas de portais". |
| 9 | `frontend/app/ajuda/faqData.ts` | 161 | `O SmartLic consolida automaticamente múltiplas fontes oficiais para garantir cobertura nacional (27 UFs) e atualização contínua.` | **MÉDIO** | "Garantir cobertura nacional" é promessa absoluta. Melhor: "O SmartLic consolida múltiplas fontes oficiais, cobrindo as 27 UFs." Remover "garantir". |
| 10 | `frontend/app/components/landing/HeroSection.tsx` | 19–20 | `HERO_DISCLAIMER = 'Criado por servidor público com mais de 10 anos em licitações. Plataforma independente, sem vínculo com órgãos governamentais.'` | **BAIXO** | Disclaimer correto e presente. Verificar se "servidor público" é a descrição correta do fundador — se ele é ex-servidor, usar "ex-servidor público" para não confundir o leitor. |
| 11 | `frontend/app/termos/page.tsx` | 174 | `Garantia de Reembolso: Planos pagos têm garantia de 7 dias` | **BAIXO** | Correto e formalizado em termos. Inconsistência potencial com TrialConversionScreen (item 3). |
| 12 | `frontend/app/termos/page.tsx` | 196 | `7.1 Isenção de Garantias` — `NÃO GARANTIMOS: Que o uso da Plataforma resultará em sucesso nas licitações` | **BAIXO** | Correto — cláusula de isenção presente. Mas precisaria estar no idioma coloquial também em páginas de produto (ex: `/buscar`). |
| 13 | `frontend/app/privacidade/page.tsx` | 28 | `sede na cidade de Sao Paulo/SP` | **BAIXO** | Termos de Uso (seção 11) define foro em São Paulo/SP, mas Footer indica endereço em Florianópolis/SC. Verificar qual é o endereço sede registrado. |
| 14 | `frontend/app/fundadores/components/FundadoresFAQ.tsx` | 33–34 | `Response time < 4h úteis para bugs críticos` | **BAIXO** | Promessa de SLA de suporte em FAQ sem formalização nos termos. Se não cumprida, pode ser alegada como promessa vinculante (CDC art. 30). Adicionar "sujeito a disponibilidade" ou incluir nos termos. |

---

## Verificação de CNPJ

| Arquivo | CNPJ encontrado | Status |
|---------|----------------|--------|
| `frontend/app/components/Footer.tsx` (linha 277) | `56.688.745/0001-00` | Pendente verificação Receita Federal |
| `frontend/app/privacidade/page.tsx` (linha 28) | `56.528.581/0001-00` | **DIVERGENTE** — RISCO ALTO |
| `frontend/app/fundadores/page.tsx` (JSON-LD, linha 28) | Sem CNPJ — usa razão social CONFENGE | OK (não expõe CNPJ) |
| `frontend/app/termos/fundadores/page.tsx` (linha 21) | Sem CNPJ — usa razão social CONFENGE | OK |
| `frontend/app/termos/page.tsx` | Sem CNPJ explícito | OK |

**Ação obrigatória:** Verificar qual CNPJ é o correto no portal da Receita Federal (https://www.receita.fazenda.gov.br/pessoajuridica/cnpj/cnpjreva/cnpjrevaicny.asp) e corrigir o divergente. REPO-005 é a issue designada para isso.

**Inconsistência de endereço:** Footer usa `Av. Pref. Osmar Cunha, 416 - Centro, Florianópolis - SC` enquanto Política de Privacidade menciona `sede na cidade de Sao Paulo/SP`. Verificar endereço cadastrado na Receita e nos Termos de Uso (foro São Paulo/SP na seção 11).

---

## Texto Proposto para Disclaimers

### Hero — não-afiliação (já implementado via REPO-007)

O disclaimer atual é:
> "Criado por servidor público com mais de 10 anos em licitações. Plataforma independente, sem vínculo com órgãos governamentais."

**Recomendação de refinamento** (se fundador não é mais servidor ativo):
> "Criado por ex-servidor público com mais de 10 anos em licitações. Plataforma independente — sem vínculo, parceria ou endosso de órgãos governamentais."

### Footer — não-afiliação (já implementado via STORY-173)

O texto atual em `valueProps.ts`:
> "SmartLic não é afiliado ao governo. Somos uma plataforma de inteligência de decisão para licitações."

Status: correto e adequado.

### Advisory pSEO (componente já existente)

`AdvisoryDisclaimer` (em `frontend/components/legal/AdvisoryDisclaimer.tsx`) já implementado em `/alertas-publicos/` via REPO-020. Verificar extensão para outras rotas pSEO com análises algorítmicas.

### Página de buscar — disclaimer de completude

Para `/buscar`, considerar adicionar texto pequeno próximo aos resultados:
> "Oportunidades obtidas de portais oficiais. Latência de até 24h após publicação. Não somos responsáveis por erros ou omissões nas fontes."

---

## Análise de Padrões "garantia" nos resultados do grep

Os resultados do grep de "garantia" retornaram **majoritariamente** menções em contexto de conteúdo educacional de blog sobre licitações (ex: "garantia de proposta", "seguro-garantia", "Art. 96 da Lei 14.133/2021"). Essas ocorrências **não são risco jurídico** — são uso técnico correto do termo no contexto de direito de licitações.

Ocorrências de risco real isoladas:
- `TrialConversionScreen.tsx:292` — "Garantia 30 dias" sem qualificação (item #3 acima)
- `FundadoresFAQ.tsx:21` — "30 dias de garantia... sem questionamentos" (item #5 acima)
- `fundadores/page.tsx:65` — mesmo conteúdo em JSON-LD (item #6 acima)

---

## Análise de Padrões "vença/ganhe" nos resultados do grep

Grep de "vença/ganhe" retornou principalmente:
- Conteúdo de blog educacional sobre licitações (ex: "probabilidade de vencer", "taxa de adjudicação")
- `frontend/app/indicar/page.tsx:112` — "Ganhe 1 mês grátis a cada amigo que assinar" — **sem risco** (programa de referral claramente descrito)
- `frontend/components/billing/TrialExtensionCard.tsx:97` — "Ganhe mais dias de trial" — **sem risco** (UI de extensão de trial)

Nenhum padrão de risco tipo "vença licitações com SmartLic" identificado nas páginas de produto.

---

## Análise de Padrões "automaticamente"

Ocorrências relevantes fora do blog:
- `faqData.ts:161` — "para garantir cobertura nacional" — risco MÉDIO (item #9 acima)
- `FaqStructuredData.tsx` — "o sistema consultará automaticamente as fontes oficiais" — OK, factual
- `faqData.ts:88` — "renovadas automaticamente no próximo ciclo de faturamento" — OK, Stripe comportamento padrão

---

## Próximos Passos

| ID | Ação | Prioridade | Issue |
|----|------|-----------|-------|
| REPO-005 | Verificar CNPJ correto na Receita Federal e corrigir Footer + Política de Privacidade | **CRÍTICO** | #755 |
| REPO-005b | Alinhar endereço de sede (Florianópolis vs. São Paulo) em todos os documentos | **CRÍTICO** | #755 |
| REPO-003a | Alinhar garantia de reembolso: `TrialConversionScreen` exibe "30 dias" mas Termos garantem 7 dias para Pro | **ALTO** | — |
| REPO-007 | Revisar "servidor público" → "ex-servidor público" se aplicável (verificar com fundador) | MÉDIO | #755 |
| REPO-021 | Suavizar promessa absoluta "Nunca Perde uma Oportunidade" em `valueProps.ts` | MÉDIO | — |
| REPO-003b | Formalizar promessa de "sem questionamentos" (reembolso Fundadores) nos Termos do Plano Fundadores | MÉDIO | — |
| REPO-003c | Formalizar SLA de suporte `< 4h úteis` nos Termos do Plano Fundadores ou suavizar para "melhor esforço" | BAIXO | — |
| REPO-020 | Verificar extensão de `AdvisoryDisclaimer` para demais rotas pSEO | BAIXO | — |
