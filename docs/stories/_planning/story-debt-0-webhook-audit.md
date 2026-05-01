# STORY-DEBT-0: Stripe Webhook Audit + Fix

**Epic:** EPIC-DEBT-2026
**Batch:** 0
**Prioridade:** P0
**Estimativa:** 3h
**Agente:** @dev (implementacao) + @qa (validacao)

## Descricao

`startup/routes.py` registra o Stripe webhook router em DUAS rotas (linhas 46 e 70): uma em `/v1/` e outra no root. Isso significa que um unico webhook event do Stripe pode ser processado duas vezes se ambas as URLs estiverem configuradas no Stripe Dashboard, potencialmente causando double-charges, duplicacao de subscription records, ou corrupcao de estado de billing.

Este e o Batch 0 porque o resultado do audit informa diretamente o Batch 3 (DEBT-307 webhook decomposition) -- nao podemos decompor com seguranca sem entender o estado atual.

**Debt IDs:** DEBT-324

## Acceptance Criteria

- [ ] AC1: Verificado qual(is) URL(s) de webhook esta(o) configurada(s) no Stripe Dashboard (documentar no PR)
- [ ] AC2: Logs de producao (Railway) analisados para os ultimos 30 dias -- zero duplicatas de `event.id` processado mais de 1x, OU lista de events duplicados documentada com impacto
- [ ] AC3: Codigo de handler verificado para presenca/ausencia de idempotency check (verifica `event.id` antes de processar?)
- [ ] AC4: Registro duplicado removido de `startup/routes.py` -- webhook handler registrado em exatamente 1 rota
- [ ] AC5: Teste de integracao: enviar webhook test event via Stripe CLI (`stripe trigger payment_intent.succeeded`), verificar handler executa exatamente 1x (contar log entries)
- [ ] AC6: Se duplicatas foram encontradas (AC2), documentar impacto e plano de remediacao em `docs/prd/webhook-audit-findings.md`

## Tasks

- [ ] T1: Acessar Stripe Dashboard > Developers > Webhooks -- documentar todas as URLs registradas e eventos habilitados (0.5h)
- [ ] T2: Analisar logs Railway dos ultimos 30 dias buscando por webhook event processing (`railway logs` ou Railway dashboard) -- buscar eventos com mesmo `event_id` processados mais de 1x (1h)
- [ ] T3: Revisar handler code em `backend/webhooks/stripe.py` para verificar se `event.id` e checado contra processamento anterior (idempotency) (0.25h)
- [ ] T4: Remover registro duplicado em `startup/routes.py` (uma das linhas 46 ou 70) -- manter apenas a URL configurada no Stripe Dashboard (0.25h)
- [ ] T5: Testar com `stripe trigger` que handler executa exatamente 1x (0.5h)
- [ ] T6: Se impacto encontrado, criar documento de findings + remediacao (0.5h)

## Testes Requeridos

- Stripe CLI test event trigger: handler executa 1x (log count)
- Regression: todos os testes existentes de webhook passam (`pytest -k webhook`)
- Endpoint test: POST para rota removida retorna 404

## Definition of Done

- [ ] All ACs checked
- [ ] Tests pass (`pytest -k webhook` + manual Stripe CLI trigger)
- [ ] No regressions (full backend test suite)
- [ ] Audit findings documented in PR description
- [ ] Code reviewed

## File List

- `backend/startup/routes.py` (remover registro duplicado)
- `backend/webhooks/stripe.py` (audit de idempotency -- possivelmente adicionar check)
- `docs/prd/webhook-audit-findings.md` (novo, se impacto encontrado)

## Notas

- **Acesso necessario:** Stripe Dashboard (billing admin), Railway logs (deploy access)
- **Risco:** Se double-processing ocorreu, pode haver subscriptions duplicadas ou charges incorretos. Documentar ANTES de fix para permitir remediacao se necessario.
- **Bloqueio downstream:** DEBT-307 (webhook decomposition no Batch 3) NAO pode comecar ate este audit estar completo.
- **Stripe CLI:** `stripe listen --forward-to localhost:8000/v1/webhooks/stripe` para teste local
