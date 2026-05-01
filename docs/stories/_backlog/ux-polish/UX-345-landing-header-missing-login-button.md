# UX-345 — Landing Header: Sem Botao Login/Criar Conta para Visitantes

**Tipo:** UX / Conversao
**Prioridade:** Alta (impacta conversao direta)
**Criada:** 2026-02-22
**Status:** Concluida
**Origem:** Teste de primeiro uso real em producao (UX Expert audit)

---

## Problema

O header da landing page para visitantes NAO-autenticados mostra:

```
SmartLic.tech  |  Planos  |  Como Funciona  |  Suporte  |  [Ir para Busca]
```

**Problemas:**
1. Nao existe botao "Login" ou "Entrar" visivel
2. Nao existe botao "Criar Conta" ou "Cadastrar" visivel
3. O unico CTA e "Ir para Busca" — que redireciona para `/buscar` (que por sua vez redireciona para login se nao autenticado)
4. "Ir para Busca" nao comunica que e necessario criar conta

### Para usuario autenticado, o header mostra o mesmo:
```
SmartLic.tech  |  Planos  |  Como Funciona  |  Suporte  |  [Ir para Busca]
```

Nao ha diferenciacao de estado autenticado/nao-autenticado no header da landing.

### Impacto

- Visitante que quer fazer login nao encontra onde clicar
- Friccao desnecessaria: precisa clicar "Ir para Busca" → redirect → login → busca (3 passos em vez de 1)
- Padrao de mercado: TODA SaaS tem "Login" e "Comece gratis" no header
- Perda de conversao: visitante que retorna para fazer login pode desistir

---

## Solucao

### Header para visitante NAO-autenticado:
```
SmartLic.tech  |  Planos  |  Como Funciona  |  Suporte  |  [Entrar]  |  [Comece Gratis ▸]
```

### Header para usuario autenticado:
```
SmartLic.tech  |  Planos  |  Como Funciona  |  Suporte  |  [Ir para Busca ▸]
```

### Criterios de Aceitacao

- [x] **AC1:** Header da landing exibe botao "Entrar" (outline/ghost) para visitantes nao-autenticados
  - Link para `/login`
  - Estilo: outline/ghost, alinhado a direita
- [x] **AC2:** Header da landing exibe botao "Comece Gratis" (primary, filled) para visitantes nao-autenticados
  - Link para `/signup?source=header-cta`
  - Estilo: botao primary (azul), a direita de "Entrar"
- [x] **AC3:** Para usuarios autenticados, header exibe "Ir para Busca" (primary) — comportamento atual mantido
- [x] **AC4:** Deteccao de auth state via Supabase SSR session (nao via API call)
- [x] **AC5:** Botoes sao responsivos: em mobile (< 768px), "Entrar" e "Comece Gratis" ficam no menu hamburger
- [x] **AC6:** Nenhum teste existente quebra

---

## Arquivos Envolvidos

### Modificar
- `frontend/app/page.tsx` — header da landing page (ou componente de header se extraido)

### Testes
- `frontend/__tests__/landing-header.test.tsx` — **NOVO**: verificar botoes por estado de auth

---

## Estimativa

- **Complexidade:** Baixa (condicional de auth no header)
- **Risco:** Minimo
- **Dependencias:** Nenhuma
