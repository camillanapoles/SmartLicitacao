# STORY-405: Toast/notificação para falha silenciosa do Excel

**Prioridade:** P1
**Esforço:** S
**Squad:** team-bidiq-frontend

## Contexto
Quando a geração do Excel falha em background (via ARQ job), o botão muda silenciosamente para "Gerar novamente" sem nenhuma notificação visual (toast, banner ou animação). O usuário pode não perceber que o Excel falhou, especialmente se estiver scrollando resultados.

## Problema (Causa Raiz)
- `frontend/app/buscar/hooks/useSearch.ts:1273,1279,1300`: `setResult(prev => { ...prev, excel_status: 'failed' })` — muda o estado sem disparar notificação.
- `frontend/app/buscar/components/SearchResults.tsx:787-802`: Botão "Gerar novamente" renderiza sem tooltip ou mensagem explicativa.
- Não há `toast.error()` ou notificação visível quando `excel_status` muda para `'failed'`.

## Critérios de Aceitação
- [x] AC1: Quando `excel_status` mudar para `'failed'`, disparar `toast.error("Não foi possível gerar o Excel. Você pode tentar novamente.")`.
- [x] AC2: Botão "Gerar novamente" deve ter tooltip: "A geração automática falhou. Clique para tentar novamente."
- [x] AC3: Se o regenerate também falhar, mostrar toast com mensagem mais detalhada: "Excel indisponível. Tente novamente em alguns instantes ou faça uma nova busca."
- [x] AC4: Logar evento Mixpanel `excel_generation_failed` com `search_id` e `attempt_number`.
- [x] AC5: Após 2 falhas consecutivas de regeneração, desabilitar botão e mostrar mensagem inline "Excel temporariamente indisponível" com link para suporte.

## Arquivos Impactados
- `frontend/app/buscar/hooks/useSearch.ts` — `handleExcelFailure()` centralizado: toast, Mixpanel, retry tracking.
- `frontend/app/buscar/components/SearchResults.tsx` — Tooltip no botão "Gerar novamente"; lógica de max retries com `excelFailCount` prop.
- `frontend/app/buscar/page.tsx` — Wire `excelFailCount` prop.

## Testes Necessários
- [x] Teste que toast aparece quando `excel_status` muda para `'failed'`.
- [x] Teste que botão desabilita após 2 falhas consecutivas.
- [x] Teste que tooltip está presente no botão "Gerar novamente".
- [x] Teste que evento Mixpanel é disparado com dados corretos.

## Notas Técnicas
- O projeto já usa `toast.success()` em `page.tsx:511`, então o import já existe.
- Cuidado para não disparar toast duplicado: `excel_status` pode ser setado em 3 pontos diferentes (linhas 1273, 1279, 1300). Usar um ref para garantir que o toast é disparado apenas 1 vez por search.
- `handleExcelFailure(isRegenerateAttempt)` centraliza toda lógica de falha: toast dedup via `excelToastFiredRef`, contagem via `excelFailCountRef`, Mixpanel via `trackEvent`.
- Reset automático ao iniciar nova busca (`buscar()`).
