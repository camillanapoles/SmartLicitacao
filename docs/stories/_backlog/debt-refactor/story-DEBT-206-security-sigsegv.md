# Story DEBT-206: Seguranca — Monitoramento cryptography/SIGSEGV

## Metadados
- **Epic:** EPIC-DEBT-V2
- **Sprint:** 6 (Semana 11-12) + Recorrente
- **Prioridade:** P0 (Critico — monitoramento periodico)
- **Esforco:** 4h (inicial) + 4h (backlog, quando 47.x estavel)
- **Agente:** @devops
- **Status:** InProgress

## Descricao

Como equipe de seguranca, queremos monitorar periodicamente vulnerabilidades na dependencia `cryptography` pinada em <47.0 e testar compatibilidade com versoes mais recentes, para que a plataforma nao fique exposta a CVEs conhecidos sem patch disponivel e possamos fazer upgrade assim que possivel.

## Debitos Incluidos

| ID | Debito | Horas | Responsavel |
|----|--------|-------|-------------|
| DEBT-SYS-002 | SIGSEGV intermitente com C extensions (CRIT-SIGSEGV) — cryptography >= 47.0 pinada | 4h inicial + 4h futuro | @devops |

## Criterios de Aceite

### Investigacao Inicial (4h)
- [ ] cryptography 47.x instalado em environment de staging isolado — BLOQUEADO: 47.x nao existe no PyPI (ultimo: 46.0.6, verificado 2026-03-30)
- [x] Teste de carga: 100 requests sem SIGSEGV — CONCLUIDO: 100/100 OK, 0 erros, 1066 req/s com cryptography 46.0.6 (2026-03-30)
- [x] CVEs na faixa cryptography 46.x verificados via `pip-audit` e NVD — CONCLUIDO: ZERO CVEs em cryptography 46.0.6. PyJWT CVE-2026-32597 encontrado e corrigido (upgrade para 2.12.0)
- [x] Resultado documentado em `docs/security/cryptography-sigsegv-status.md` — atualizado com resultados completos de auditoria 2026-03-30
- [x] Se CVE critico encontrado: issue de seguranca criada imediatamente — N/A: nenhum CVE critico em cryptography encontrado. PyJWT CVE (MEDIUM) corrigido em requirements.txt

### Monitoramento Recorrente
- [x] Checklist trimestral definido — `docs/security/quarterly-checklist.md` criado (commit a39f7089)
- [x] Reminder criado para proxima verificacao (Q3 2026) — documentado no checklist
- [x] Script `scripts/security/check_cryptography_cves.py` criado (pip-audit wrapper, 158 LOC)
- [x] `requirements.txt` comentado com rationale do pin

### Backlog Futuro (4h — quando 47.x estavel)
- [ ] Upgrade de cryptography para >=47.0
- [ ] Remocao do pin de versao em `requirements.txt`
- [ ] Remocao das restricoes de uvloop relacionadas ao SIGSEGV
- [ ] Suite completa de testes em producao pos-upgrade

## Testes Requeridos

- [ ] Teste de carga em staging com cryptography 47.x (100 requests, zero crashes) — BLOQUEADO: 47.x nao publicado ainda
- [x] `pip-audit` em `requirements.txt` — zero CVEs criticos — CONCLUIDO: cryptography 46.0.6 = 0 CVEs. pyjwt CVE-2026-32597 (MEDIUM) corrigido
- [x] `pytest --timeout=30 -q` — suite completa — CONCLUIDO: 7774 passing, 231 pre-existentes (melhor que baseline 292). Auth: 74/74 pass

## Notas Tecnicas

- **Contexto CRIT-SIGSEGV:** Bug intermitente de segfault com C extensions (uvloop + cryptography >= 47.0). Pin atual em <47.0 e workaround, nao solucao.
- **Risco:** Se CVE critico for descoberto na faixa 46.x, o workaround se torna vulnerabilidade. Monitoramento e essencial.
- **Nao bloqueia outras stories:** Esta e uma atividade de monitoramento, nao de desenvolvimento.
- **uvloop:** Restricoes de uvloop tambem relacionadas — verificar se versao mais recente resolve.

## Dependencias

- Nenhuma — independente de todas as outras stories
- Executavel a qualquer momento
