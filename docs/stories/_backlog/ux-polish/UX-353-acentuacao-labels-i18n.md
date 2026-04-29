# UX-353 — Acentuacao, Labels e Consistencia Textual da Area Logada

**Status:** done
**Priority:** P2 — Polish pre-GTM
**Created:** 2026-02-22
**Origin:** Auditoria UX area logada (2026-02-22-ux-audit-area-logada.md)
**Dependencias:** Nenhuma (pode ser feita em paralelo)
**Estimativa:** S

---

## Problema

A area logada tem dezenas de textos sem acentuacao correta e inconsistencias com a landing page. Isso transmite amadorismo e quebra confianca — especialmente para publico B2G que valoriza profissionalismo.

### Inventario de problemas

| Local | Texto atual | Correto |
|---|---|---|
| Sidebar | "Historico" | "Historico" (com acento) |
| Sidebar | "Mensagens" | "Suporte" (alinhar com landing) |
| Sidebar aria-label | "Navegacao principal" | "Navegacao principal" (com cedilha) |
| Historico header | "Historico" | "Historico" (com acento) |
| Historico badges | "Concluida" | "Concluida" (com acento) |
| Historico badges | "vestuario" | "vestuario" (com acento) |
| Pipeline vazio | "voce" | "voce" (com acento) |
| Pipeline vazio | "licitacoes" | "licitacoes" (com cedilha) |
| Pipeline vazio | "inicio" | "inicio" (com acento) |
| Pipeline vazio | "avanca" | "avanca" (com cedilha) |
| Badges resultado | "confianca" | "confianca" (com cedilha) |
| Badges resultado | "Recomendacoes" | "Recomendacoes" (com cedilha) |
| Error detail | "tecnicos" | "tecnicos" (com acento) |
| Feedback dropdown | "Ja encerrada" | "Ja encerrada" (com acento) |
| Footer area logada | "Sistema desenvolvido por servidores publicos" | Remover (incorreto — SmartLic e da CONFENGE) |

---

## Solucao

### Criterios de Aceitacao

**Sidebar e navegacao**
- [x] **AC1:** "Historico" → "Historico" (sidebar e todas as paginas)
- [x] **AC2:** "Mensagens" → "Suporte" (sidebar) — manter rota /mensagens internamente
- [x] **AC3:** aria-label "Navegacao principal" → "Navegacao principal"

**Historico**
- [x] **AC4:** Header "Historico" com acento
- [x] **AC5:** Badge "Concluida" com acento
- [x] **AC6:** Badges de setor com acentuacao (vestuario, etc.)

**Pipeline**
- [x] **AC7:** Todos os textos do empty state com acentuacao correta

**Badges e resultados**
- [x] **AC8:** "confianca" → corrigido (acentuacao)
- [x] **AC9:** "Recomendacoes" → corrigido
- [x] **AC10:** "tecnicos" → corrigido

**Footer**
- [x] **AC11:** Footer da area logada alinhado com footer da landing page
- [x] **AC12:** Remover "Sistema desenvolvido por servidores publicos" (incorreto)

**Feedback**
- [x] **AC13:** "Ja encerrada" → corrigido

**Testes**
- [x] **AC14:** Busca textual no codebase por strings sem acento conhecidas retorna 0
- [x] **AC15:** Zero regressoes

---

## Arquivos Envolvidos

| Arquivo | Mudanca |
|---------|---------|
| `frontend/app/buscar/components/SearchResults.tsx` | AC8, AC9 |
| `frontend/app/buscar/components/ReliabilityBadge.tsx` | AC8 |
| `frontend/app/buscar/components/FeedbackButtons.tsx` | AC13 |
| `frontend/app/buscar/components/ErrorDetail.tsx` | AC10 |
| `frontend/app/historico/page.tsx` | AC4, AC5, AC6 |
| `frontend/app/pipeline/page.tsx` | AC7 |
| `frontend/components/Sidebar.tsx` ou layout | AC1, AC2, AC3 |
| `frontend/components/Footer.tsx` ou layout | AC11, AC12 |

---

## Notas

Esta story pode ser executada em paralelo com qualquer outra — nao tem dependencias tecnicas. E a mais simples de implementar (find & replace) mas com alto impacto percebido de profissionalismo.

---

## Referencias

- Audit: M01, M02, M04, M05
