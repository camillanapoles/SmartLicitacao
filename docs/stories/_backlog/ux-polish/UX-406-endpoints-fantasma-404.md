# STORY-406: Remover chamadas 404 ao dashboard (endpoints fantasma)

**Prioridade:** P1
**Esforço:** S
**Squad:** team-bidiq-frontend

## Contexto
A página de dashboard faz fetch para `/api/organizations/me` (linha 254) — endpoint que não existe no backend. Isso gera console errors 404 em cada load do dashboard, poluindo logs de observabilidade e potencialmente afetando métricas de erro do Sentry. A feature de organizações/times ainda não foi implementada.

## Problema (Causa Raiz)
- `frontend/app/dashboard/page.tsx:254`: `fetch("/api/organizations/me", ...)` — endpoint não existe.
- Linhas 271-284: `fetch(/api/organizations/${userOrg.id}/dashboard)` — dependente do primeiro fetch, também não existe.
- O `.catch(() => {})` silencia o erro no JS mas o 404 ainda aparece no console do browser e no proxy log.

## Critérios de Aceitação
- [x] AC1: Encapsular chamadas a `/api/organizations/me` e `/api/organizations/{id}/dashboard` dentro de feature flag `NEXT_PUBLIC_ORGS_ENABLED` (default: `false`).
- [x] AC2: Quando feature flag desativada, não fazer nenhum fetch e não renderizar toggle Team/Personal.
- [x] AC3: Nenhum console error 404 no dashboard quando feature desativada.
- [x] AC4: Manter todo o código de organizações intacto (não deletar), apenas gated pela feature flag para quando o backend for implementado.
- [x] AC5: Adicionar `NEXT_PUBLIC_ORGS_ENABLED` ao `.env.example` com documentação.

## Arquivos Impactados
- `frontend/app/dashboard/page.tsx` — Feature flag guard nos useEffects de organização.
- `frontend/.env.example` — Nova variável documentada.

## Testes Necessários
- [x] Teste que dashboard NÃO faz fetch a `/api/organizations/me` quando flag desativada.
- [x] Teste que toggle Team/Personal não renderiza quando flag desativada.
- [x] Teste que dashboard funciona normalmente quando flag desativada (sem regressão em analytics).

## Notas Técnicas
- O pattern de feature flags frontend já existe no projeto. Seguir o mesmo padrão.
