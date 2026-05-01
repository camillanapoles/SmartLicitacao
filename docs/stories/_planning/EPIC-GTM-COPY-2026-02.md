# EPIC: GTM-COPY — Reposicionamento Estratégico de Comunicação

**Data:** 2026-02-22
**Épico:** Reposicionamento completo da comunicação do SmartLic
**Prioridade:** P0 (GTM-blocker)
**Estimativa total:** 8 stories, ~40-60 ACs

## Contexto Estratégico

O SmartLic precisa migrar de um discurso genérico de "inteligência" para uma **promessa concreta de impacto no resultado do cliente**. A comunicação deve deixar explícito que o sistema existe para:

1. **Evitar desperdício de tempo** em licitações irrelevantes
2. **Reduzir o risco de perder** boas oportunidades
3. **Direcionar esforço** para o que tem real potencial de retorno

### Mensagem Central (North Star)

> O SmartLic não é uma ferramenta de busca. É um **filtro estratégico** que direciona o esforço do usuário para as oportunidades com maior potencial de retorno, reduzindo desperdício e aumentando a taxa de sucesso. **Não usar = risco operacional.**

### Princípios de Copy

| Princípio | Antes (evitar) | Depois (adotar) |
|-----------|----------------|-----------------|
| Orientação | Conceito/abstração | Consequência prática |
| Promessa | "Inteligência", "automação" | Ganho financeiro, redução de erro |
| Entrega | Listas extensas | Recomendações priorizadas com justificativa |
| Tom | Exploratório | Incisivo, orientado a ação |
| Prova | Afirmações genéricas | Exemplos reais de funcionamento |
| Confiança | Implícita | Transparência de critérios |
| Risco | "Alternativa opcional" | "Não usar = operar no escuro" |

### Território de Posicionamento

Sair de "licitações" (genérico) → Dominar **"decisão estratégica sobre quais oportunidades valem o esforço"** (específico, menos concorrência, intenção mais qualificada).

## Stories

| ID | Título | Prioridade | Escopo |
|----|--------|------------|--------|
| GTM-COPY-001 | Headlines, Subheadlines & Narrativa da Landing | P0 | Copy principal, tom incisivo |
| GTM-COPY-002 | CTAs Orientados a Ação Imediata | P0 | Todos os CTAs do site |
| GTM-COPY-003 | Prova de Funcionamento na Primeira Dobra | P0 | Exemplos reais, justificativa de priorização |
| GTM-COPY-004 | Elementos de Segurança na Decisão | P1 | Critérios, aderência, falsos positivos |
| GTM-COPY-005 | Credibilidade & Autoridade Explícita | P1 | Quem somos, metodologia, critérios |
| GTM-COPY-006 | Metadata SEO & Conteúdo AI-Friendly | P1 | Títulos, descriptions, structured data |
| GTM-COPY-007 | Páginas de Conteúdo Estratégico | P2 | 4-6 novas páginas respondendo perguntas reais |
| GTM-COPY-008 | Limpeza de Marca & Consistência SmartLic | P1 | Remover BidIQ, eliminar viés setorial |

## Dependências

```
GTM-COPY-001 ──┐
GTM-COPY-002 ──┤── Podem ser executadas em paralelo
GTM-COPY-003 ──┘
       │
GTM-COPY-004 ──── Depende de 001 (usa mesma narrativa)
GTM-COPY-005 ──── Independente
GTM-COPY-006 ──── Depende de 001 (metadata reflete nova copy)
GTM-COPY-007 ──── Depende de 001+005 (mesma voz, mesmos critérios)
GTM-COPY-008 ──── Independente (pode ser primeira)
```

## Arquivos Impactados

### Copy Centralizada
- `frontend/lib/copy/valueProps.ts` — Todas as value props, features, email copy
- `frontend/lib/copy/comparisons.ts` — Comparações, pain points, proof points

### Landing Page
- `frontend/app/components/landing/HeroSection.tsx`
- `frontend/app/components/ValuePropSection.tsx`
- `frontend/app/components/landing/OpportunityCost.tsx`
- `frontend/app/components/landing/BeforeAfter.tsx`
- `frontend/app/components/landing/DifferentialsGrid.tsx`
- `frontend/app/components/landing/HowItWorks.tsx`
- `frontend/app/components/ComparisonTable.tsx`
- `frontend/app/components/landing/FinalCTA.tsx`

### Páginas
- `frontend/app/page.tsx` — Landing composition
- `frontend/app/planos/page.tsx` — Pricing
- `frontend/app/features/page.tsx` — Features
- `frontend/app/ajuda/page.tsx` — Help/FAQ
- `frontend/app/login/page.tsx` — Login
- `frontend/app/signup/page.tsx` — Signup
- `frontend/app/layout.tsx` — Metadata SEO

### Novos Arquivos (GTM-COPY-007)
- `frontend/app/como-avaliar-licitacao/page.tsx`
- `frontend/app/como-filtrar-editais/page.tsx`
- `frontend/app/como-evitar-prejuizo-licitacao/page.tsx`
- `frontend/app/como-priorizar-oportunidades/page.tsx`

## Baseline de Testes

- Frontend: 40 fail / 2205 pass (pre-existing)
- TypeScript: `npx tsc --noEmit` clean
- Zero regressions toleradas
