# STORY-371 — Email Dia 10 com Edital Real

**Status:** InProgress
**Priority:** P1 — Conversão (email mais próximo da decisão de compra, hoje genérico)
**Origem:** Conselho de CEOs Advisory Board — melhorias on-page funil conversão (2026-04-11)
**Componentes:** backend/services/trial_email_sequence.py, backend/routes/analytics.py
**Depende de:** nenhuma
**Bloqueia:** nenhuma
**Estimativa:** ~3h

---

## Contexto

O email do dia 10 é o **mais estratégico da sequência de trial**: é enviado 3 dias antes da expiração, quando o usuário ainda pode agir. Hoje ele mostra apenas números agregados ("você encontrou X oportunidades no valor total de R$Y").

Dados agregados não criam urgência real. Um edital específico cria:

> *"Pregão Eletrônico 023/2026 — Secretaria de Educação de Florianópolis — Aquisição de material didático — R$485.000 — vence em 8 dias"*

Esse nível de personalização transforma o email de lembrete em prova de valor concreta, endereçada diretamente ao setor e UF que o usuário configurou.

## Acceptance Criteria

### AC1: Extensão de `GET /v1/analytics/trial-value`

- [ ] Endpoint existente em `backend/routes/analytics.py` passa a retornar campo `top_opportunity` além dos campos já existentes — **uncheck 2026-04-28: endpoint atualmente retorna 503 (`column search_sessions.top_result_objeto does not exist`); 5 evt Sentry/24h. Code consumer existe mas migration faltando**
- [x] `top_opportunity` contém:
  ```json
  {
    "numero_controle": "string",
    "objeto": "string (max 120 chars, truncado com '...')",
    "orgao_nome": "string",
    "valor_global": number,
    "data_encerramento": "ISO date string | null",
    "dias_ate_encerramento": number | null,
    "setor": "string",
    "modalidade": "string"
  }
  ```
- [ ] Lógica de seleção: edital de maior `valor_global` encontrado nas sessões de busca do usuário durante o trial (join com `search_sessions` + `pncp_raw_bids` ou `search_results_cache`) — **uncheck 2026-04-28: commit edf82379 implementou SELECT direto em `search_sessions.top_result_*` sem JOIN; e cols não existem; populator (UPDATE search_sessions SET top_result_*) ausente — feature está sempre NULL**
- [x] Fallback: `top_opportunity: null` se usuário nunca executou busca com resultados
- [x] Schema Pydantic atualizado (`TopOpportunity` com 7 campos adicionais)
- [ ] Testes: usuário com buscas (retorna oportunidade), usuário sem buscas (retorna null), truncamento de objeto — **uncheck 2026-04-28: testes existem em `test_trial_value_top_opportunity.py` mas mockam dados — não capturam realidade de schema drift; não cobre runtime real**

### AC2: Template de email dia 10 com edital real

- [x] Modificar template do dia 10 em `backend/templates/emails/trial.py` (função `render_trial_value_email`)
- [x] Quando `top_opportunity` não é null: exibir bloco destacado com os dados do edital
  - Design: caixa com borda azul, ícone de prancheta, título do edital em negrito, órgão, valor formatado em BRL, prazo em dias
  - CTA específico: "Ver este edital agora →" linkando para `/buscar?highlight={numero_controle}`
- [x] Quando `top_opportunity` é null: manter copy atual agregado (fallback inalterado)
- [x] Template HTML responsivo (funciona em Gmail, Outlook mobile)
- [x] Sem imagens externas no email (evitar bloqueio de tracking pixel em clientes corporativos)

### AC3: Link de highlight no frontend

- [x] Query param `?highlight={numero_controle}` em `/buscar` faz scroll automático para o resultado correspondente se ele aparecer nos resultados
- [x] Se não aparecer (expirou do datalake), ignorar silenciosamente — sem erro visual
- [x] Implementação: `useEffect` que lê `searchParams.get('highlight')` e adiciona classe ring-2 ao resultado correspondente

### AC4: Formatação de valor e prazo

- [x] Novo helper `format_brl(value: float): str` em `backend/utils/formatters.py`
- [x] Novo helper `dias_ate_data(date_str: str) -> Optional[int]` — retorna None se data já passou
- [x] No template: valor formatado como "R$ 485.000" (sem centavos para valores > 10k)
- [x] No template: prazo exibido como "vence em X dias" ou "vence hoje" ou omitido se `data_encerramento` é null

### AC5: Testes

- [x] Teste unitário para lógica de seleção do top_opportunity (mock de search_sessions)
- [x] Teste de renderização do template: com e sem top_opportunity
- [x] Teste de truncamento do campo `objeto`
- [x] Teste dos helpers de formatação

## Escopo

**IN:**
- Extensão do endpoint `trial-value` com `top_opportunity`
- Template do email dia 10 personalizado
- Query param `?highlight=` no frontend
- Helpers de formatação

**OUT:**
- Personalizar outros emails da sequência (dias 0, 3, 7, 13, 16) — fora desta story
- Dashboard de click-through do email — fora desta story
- Re-envio automático se email não foi aberto — fora desta story

## Riscos

- `search_results_cache` tem TTL de 24h e `pncp_raw_bids` tem retenção de 12 dias: se usuário buscou há mais de 12 dias, `top_opportunity` pode ser null. Fallback cobre esse caso.
- Edital pode ter expirado entre a busca e o envio do email (dia 10): exibir mesmo assim com aviso "pode já ter encerrado" ou omitir — decisão de implementação para o dev, registrar no decision log.

## Arquivos a Criar/Modificar

- [x] `backend/routes/analytics.py` (modificar — TopOpportunity expandida + query com campos reais)
- [x] `backend/services/trial_email_sequence.py` (modificar — _get_top_trial_opportunity + injeção no dispatch)
- [x] `backend/templates/emails/trial.py` (modificar — _top_opportunity_block + chamada no body)
- [x] `backend/utils/formatters.py` (criar — format_brl, dias_ate_data, truncate_text)
- [x] `frontend/app/buscar/page.tsx` (modificar — useSearchParams + highlight useEffect)
- [x] `backend/tests/test_trial_value_top_opportunity.py` (novo)
- [x] `backend/tests/test_email_day10_template.py` (novo)

## Change Log

| Data | Agente | Ação |
|------|--------|------|
| 2026-04-11 | @sm | Story criada — Conselho de CEOs Advisory Board |
| 2026-04-11 | @po | GO 10/10 — Draft → Ready |
| 2026-04-28 | @sm | Status correction InReview→InProgress: ACs falsamente marcados [x] em sessão ancient-kahn discriminator. Commit edf82379 (2026-04-11) shipou apenas consumer code (analytics.py SELECT, trial_email_sequence.py SELECT, template HTML, frontend highlight, formatters) — NÃO incluiu migration adicionando 5 cols `top_result_*` a `search_sessions`, NÃO incluiu populator (UPDATE search_sessions SET top_result_* após search complete). Sintoma vivo: 5 evt Sentry/24h `42703 column does not exist`; endpoint /v1/analytics/trial-value 503 silent; email dia 10 cai em fallback genérico. Trabalho restante: criar migration `top_result_*` em search_sessions + .down.sql; implementar populator no fluxo de search complete (provável `backend/jobs/queue/search.py` ou search_state_manager.py); novos testes integração (não-mocked). |
