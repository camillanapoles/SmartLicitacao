# Story DEBT-101: Security Critical — Token Hash, SIGSEGV & LLM Truncation

## Metadata
- **Story ID:** DEBT-101
- **Epic:** EPIC-DEBT
- **Batch:** B (Foundation)
- **Sprint:** 1 (Semanas 1-2)
- **Estimativa:** 12h
- **Prioridade:** P0 (Imediato)
- **Agent:** @dev

## Descricao

Como responsavel pela seguranca da plataforma, quero corrigir os 3 debitos CRITICAL mais urgentes (token hash collision CVSS 9.1, SIGSEGV em producao, e truncamento de JSON em 20-30% das chamadas LLM), para que a plataforma opere sem riscos de seguranca, crashes silenciosos e classificacoes incorretas.

## Debt Items Cobertos

| ID | Debito | Severidade | Horas |
|----|--------|:---:|:---:|
| SYS-004 | Token hash usa partial payload em vez de FULL SHA256 — risco de collision (CVSS 9.1) | CRITICAL | 4h |
| SYS-001 | faulthandler enabled + uvicorn WITHOUT `[standard]` extra — uvloop SIGSEGV em Railway Linux | CRITICAL | 4h |
| SYS-002 | LLM_STRUCTURED_MAX_TOKENS=300 causa JSON truncation em 20-30% das chamadas | CRITICAL | 4h |

## Acceptance Criteria

- [x] AC1: Token hash usa SHA256 do payload COMPLETO (nao parcial); collision probability < 2^-128
- [x] AC2: Dual-hash lookup implementado para transicao (aceita hash antigo + novo por 1h apos deploy)
- [x] AC3: `uvicorn[standard]` no requirements.txt; faulthandler desabilitado em producao
- [ ] AC4: Railway staging deploy sem SIGSEGV por 1h de monitoramento
- [x] AC5: LLM_STRUCTURED_MAX_TOKENS aumentado para valor que elimina truncation (>= 800)
- [x] AC6: JSON parse success rate > 99% (medido com golden samples test)
- [x] AC7: Golden samples baseline executado ANTES da mudanca de MAX_TOKENS (Condicao 2 do QA Gate)
- [x] AC8: Classificacao por acceptance rate nao diverge mais que 5% do baseline

## Testes Requeridos

- **SYS-004:** `test_security_story210.py` + teste de 2 requests concorrentes com tokens diferentes nao cross-poluem
- **SYS-001:** Deploy em Railway staging, verificar ausencia de SIGSEGV por 1h. Verificar faulthandler disabled via `python -c "import faulthandler; print(faulthandler.is_enabled())"`
- **SYS-002:** `pytest -k test_golden_samples` antes E depois da mudanca. Comparar acceptance rates. Verificar JSON parse success > 99% com novo MAX_TOKENS
- Todos: `python scripts/run_tests_safe.py` — 0 failures

## Notas Tecnicas

- **SYS-004 (Token Hash):**
  - Arquivo: `backend/auth.py` (funcao de geracao de hash)
  - Risco: thundering herd on cache invalidation se muitos tokens invalidados
  - Mitigacao: deploy em 2-4 AM BRT; dual-hash lookup (old + new) por 1h de transicao
  - Rollback: revert para partial hash (single line em auth.py)

- **SYS-001 (SIGSEGV):**
  - Arquivo: `backend/requirements.txt` (adicionar `uvicorn[standard]`)
  - Arquivo: `backend/main.py` ou `backend/config.py` (desabilitar faulthandler)
  - Rollback: remover `[standard]` extra de requirements.txt

- **SYS-002 (LLM Truncation):**
  - Arquivo: `backend/config.py` (LLM_STRUCTURED_MAX_TOKENS)
  - Risco: mudanca no comportamento de classificacao
  - Rollback: reverter MAX_TOKENS para 300 (single config line)

## Dependencias

- **Depende de:** Nenhuma (deve ser executado PRIMEIRO, antes de qualquer outro fix)
- **Bloqueia:** DEBT-102 (SYS-004 token hash DEVE preceder SYS-005 JWT rotation)

## Definition of Done

- [x] Codigo implementado
- [ ] Deploy em staging com monitoramento de 1h sem SIGSEGV
- [x] Golden samples test antes/depois com <5% divergencia
- [x] JSON parse success > 99% confirmado
- [x] Testes passando (backend full suite)
- [ ] Deploy em producao em low-traffic window (2-4 AM BRT)
- [x] Documentacao atualizada (CLAUDE.md se necessario)
