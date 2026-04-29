# SAB-001: Busca trava em 70% — resultados nunca renderizam

**Origem:** UX Premium Audit P0-01
**Prioridade:** P0 — BLOQUEADOR
**Complexidade:** L (Large)
**Sprint:** SAB-P0 (imediato)
**Owner:** @dev
**Screenshots:** `ux-audit/17-busca-loading.png` → `21-busca-stuck-backend-done.png`

---

## Problema

Ao buscar "Vestuário e Uniformes" em SP (últimos 10 dias), o backend completa em ~14s (logs confirmam `llm_summary_job`, `excel_generation_job`, `bid_analysis_job` concluídos), mas o frontend fica preso em "Filtrando resultados" 70% com skeletons de loading por 145+ segundos. Resultados **nunca** renderizam.

A barra inferior mostra "8 relevantes de 594 analisadas — Filtragem concluída" mas os cards de resultado não aparecem.

**Causa provável:** Desconexão SSE ou race condition entre a resposta principal do `POST /buscar` e os eventos SSE de background jobs (`llm_ready`, `excel_ready`). Possível que o state machine do `useSearch` não transicione para `results` quando recebe a resposta POST.

**Impacto:** Funcionalidade CORE do produto está quebrada. Usuário não consegue ver resultados.

---

## Critérios de Aceite

### Diagnóstico

- [x] **AC1:** Reproduzir o bug em ambiente de desenvolvimento com busca real (setor Vestuário, UF SP, 10 dias)
- [x] **AC2:** Instrumentar `useSearch.ts` com console.log em cada transição de estado: `idle → searching → filtering → results/error`
- [x] **AC3:** Verificar se a resposta do `POST /buscar` chega ao frontend (network tab) e se o JSON contém `resultados[]`

### Root Cause Fix

- [x] **AC4:** Se race condition SSE vs POST: garantir que o estado `results` é setado quando POST retorna com dados, independente do SSE
- [x] **AC5:** Se desconexão SSE: verificar que o `EventSource` reconecta ou que o frontend degrada gracefully para time-based progress
- [x] **AC6:** Se estado do `useSearch` fica preso em `filtering`: adicionar timeout de segurança — após POST retornar com dados, forçar transição para `results` em no máximo 5s

### Validação

- [x] **AC7:** Busca "Vestuário e Uniformes" SP 10 dias exibe resultados em < 30s
- [x] **AC8:** Busca com 0 resultados mostra mensagem "Nenhuma licitação encontrada" (não skeleton infinito)
- [x] **AC9:** Teste unitário cobrindo cenário: POST retorna antes do SSE completar → resultados renderizam

---

## Root Cause (Análise)

**Stale closure bug** na função `buscar()` do `useSearch.ts`:

A variável de estado `asyncSearchActive` era capturada pelo closure da função `buscar()` no momento da renderização que criou a função. Se uma busca anterior usou modo async (202), o closure da próxima busca mantinha `asyncSearchActive = true` (valor stale), mesmo após `setAsyncSearchActive(false)` ter sido chamado — pois `setState` atualiza o estado para o PRÓXIMO render, não o closure atual.

No bloco `finally` de `buscar()`:
```javascript
if (!asyncSearchActive && !asyncSearchIdRef.current) {
  setLoading(false);  // NUNCA executado quando closure tem asyncSearchActive=true
}
```

`setLoading(false)` nunca era chamado → `loading` ficava `true` para sempre → skeletons infinitos.

**Fix:** Introduzido `asyncSearchActiveRef` (useRef) sincronizado via useEffect. O `finally` block agora lê `asyncSearchActiveRef.current` (sempre atualizado) em vez da variável de estado do closure (potencialmente stale).

**Safety net:** Adicionado efeito de timeout de 5s que força `setLoading(false)` se `result` já estiver setado mas `loading` continuar `true` — previne qualquer futuro bug de state machine.

## Arquivos Modificados

- `frontend/app/buscar/hooks/useSearch.ts` — Fix do stale closure + safety timeout + instrumentação
- `frontend/__tests__/hooks/useSearch-sab001.test.ts` — 7 testes cobrindo AC4, AC6, AC8, AC9
- `docs/stories/SAB-001-busca-results-never-render.md` — Story atualizada

## Arquivos Prováveis (original)

- `frontend/app/buscar/page.tsx` — orquestração da busca
- `frontend/app/buscar/hooks/useSearch.ts` — state machine da busca (ROOT CAUSE)
- `frontend/app/buscar/components/SearchResults.tsx` — renderização de resultados
- `backend/routes/search.py` — endpoint `/buscar` e SSE (não afetado)

## Dependências

- SAB-005 (P1-02) — timeout/retry UX é fix complementar a este
- STORY-329 — progresso granular na filtragem (já concluída, mas pode ter introduzido regressão)

## Notas

- Os logs de backend confirmam que a busca completou com sucesso. O problema é exclusivamente frontend.
- STORY-329 NÃO introduziu regressão. A causa raiz é o stale closure de asyncSearchActive.
