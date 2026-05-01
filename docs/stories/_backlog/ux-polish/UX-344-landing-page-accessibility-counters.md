# UX-344 — Landing Page: Contadores Animados Inacessiveis

**Tipo:** Acessibilidade / WCAG 2.1 AA
**Prioridade:** Media
**Criada:** 2026-02-22
**Status:** Concluída
**Origem:** Teste de primeiro uso real em producao (UX Expert audit)

---

## Problema

Os contadores animados na hero section da landing page ("15 setores especializados", "1000+ regras de filtragem", "27 estados cobertos") usam animacao JavaScript que incrementa de 0 ate o valor final.

**O problema:** Screen readers e o accessibility tree capturam o valor INICIAL (0), nao o valor final.

### Evidencias

Snapshot do accessibility tree (Playwright):
```yaml
- generic [ref=e32]: "0"
- generic [ref=e33]: setores especializados
...
- generic [ref=e47]: "0"
- generic [ref=e48]: estados cobertos
```

O screenshot visual mostra "15" e "27" (animacao completou), mas screen readers leem **"0 setores especializados"** e **"0 estados cobertos"**.

### Impacto

- Violacao WCAG 2.1 SC 1.3.1 (Info and Relationships)
- Violacao WCAG 2.1 SC 4.1.2 (Name, Role, Value)
- Usuarios com deficiencia visual recebem informacao incorreta
- SEO: crawlers podem indexar "0" em vez de "15"

---

## Solucao

### Abordagem: `aria-label` com valor final + `aria-live` para atualizacao

### Criterios de Aceitacao

- [x] **AC1:** Contadores na hero tem `aria-label` com valor final:
  - `aria-label="15 setores especializados"`
  - `aria-label="1000+ regras de filtragem"`
  - `aria-label="27 estados cobertos"`
- [x] **AC2:** Mesma correcao aplicada aos contadores na secao "Impacto real no mercado" (mais abaixo na landing)
- [x] **AC3:** Screen reader (VoiceOver/NVDA) le valores corretos mesmo durante animacao
- [x] **AC4:** `aria-hidden="true"` no span animado + valor real em `aria-label` do container (pattern recomendado)
- [x] **AC5:** Alternativa: usar `<span role="text" aria-label="15">0</span>` com animacao apenas visual
- [x] **AC6:** Nenhum teste existente quebra

---

## Arquivos Envolvidos

### Modificar
- `frontend/app/page.tsx` (ou componente de landing) — adicionar aria-labels nos contadores

### Testes
- `frontend/__tests__/landing-accessibility.test.tsx` — **NOVO**: verificar aria-labels

---

## Estimativa

- **Complexidade:** Baixa (atributos HTML)
- **Risco:** Minimo
- **Tempo estimado:** 30min implementacao + 30min testes
