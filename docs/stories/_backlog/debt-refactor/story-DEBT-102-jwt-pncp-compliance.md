# Story DEBT-102: Security & Auth — JWT Rotation & PNCP Compliance

## Metadata
- **Story ID:** DEBT-102
- **Epic:** EPIC-DEBT
- **Batch:** B (Foundation)
- **Sprint:** 2-3 (Semanas 3-6)
- **Estimativa:** 16h
- **Prioridade:** P1 (Curto Prazo)
- **Agent:** @dev

## Descricao

Como arquiteto de seguranca, quero modernizar a autenticacao JWT de HS256 para ES256/JWKS com backward compatibility e corrigir a integracao PNCP para respeitar o novo limite de 50 resultados/pagina, para que a plataforma siga padroes de seguranca atuais e capture 100% das licitacoes disponiveis sem erros silenciosos.

## Debt Items Cobertos

| ID | Debito | Severidade | Horas |
|----|--------|:---:|:---:|
| SYS-005 | ES256/JWKS JWT signing + HS256 backward compat para algorithm rotation | CRITICAL | 8h |
| SYS-003 | PNCP API reduced max tamanhoPagina 500->50 (Feb 2026); >50 causa silent HTTP 400 | CRITICAL | 8h |

## Acceptance Criteria

- [x] AC1: Novos tokens JWT assinados com ES256 (asymmetric)
- [x] AC2: JWKS endpoint disponivel para verificacao de tokens
- [x] AC3: Tokens HS256 existentes continuam sendo aceitos (backward compat por periodo de transicao)
- [x] AC4: Rotation de keys suportada (2 keys ativas simultaneamente no JWKS)
- [x] AC5: PNCP client envia `tamanhoPagina=50` (nunca >50)
- [x] AC6: Validacao server-side rejeita `tamanhoPagina>50` com erro explicito
- [x] AC7: Health canary testa com `tamanhoPagina=50` (atualmente usa 10)
- [x] AC8: Paginacao correta quando ha >50 resultados (multiple pages)

## Testes Requeridos

- **SYS-005:**
  - Verificar HS256 backward compat + ES256 novos tokens trabalham simultaneamente
  - Testar JWKS rotation com 2 active keys
  - Testar expirado HS256 token rejeitado
  - Testar ES256 token com key ID correto aceito
- **SYS-003:**
  - Testar `tamanhoPagina=50` retorna sucesso
  - Testar `tamanhoPagina=51` gera erro graceful (nao silent 400)
  - Integration test com API PNCP real (canary)
  - Testar paginacao multipla quando >50 resultados disponiveis

## Notas Tecnicas

- **SYS-005 (JWT Rotation):**
  - Requer: geracoes de key pair ES256, JWKS endpoint, dual-algorithm verification
  - Arquivo principal: `backend/auth.py`
  - Supabase Auth usa HS256 por padrao — verificar como ES256 se integra
  - Considerar: `python-jose` ou `PyJWT` com ES256 support
  - Backward compat: verificar algoritmo do header JWT antes de selecionar key

- **SYS-003 (PNCP Page Size):**
  - Arquivo principal: `backend/pncp_client.py`
  - Constante atual provavelmente em `backend/config.py`
  - Health canary em `backend/health.py` usa `tamanhoPagina=10` — atualizar test para 50
  - Documentado em CLAUDE.md: "Max tamanhoPagina = 50"

## Dependencias

- **Depende de:** DEBT-101 (SYS-004 token hash DEVE estar completo antes de JWT rotation)
- **Bloqueia:** Nenhuma diretamente (SYS-005 e pre-requisito para escala de usuarios)

## Definition of Done

- [x] Codigo implementado
- [x] Testes unitarios + integration passando
- [ ] Deploy em staging com verificacao de backward compat
- [ ] PNCP integration test com API real passando
- [ ] Code review aprovado
- [x] Documentacao atualizada
