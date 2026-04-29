# SAB-007: Signup — botão sem feedback de validação inline

**Origem:** UX Premium Audit P1-04
**Prioridade:** P1 — Alto
**Complexidade:** M (Medium)
**Sprint:** SAB-P1
**Owner:** @dev
**Screenshot:** `ux-audit/11-signup-page.png`

---

## Problema

Botão "Criar conta" aparece visualmente como desabilitado/greyed out sem nenhuma indicação do que falta preencher. Campos de validação não mostram erros inline.

**Esperado:** Validação inline em cada campo com mensagens claras. Botão com tooltip explicando o que falta quando disabled.

---

## Critérios de Aceite

### Validação Inline

- [x] **AC1:** Campo Nome — erro inline se vazio ao sair do campo (onBlur): "Nome é obrigatório"
- [x] **AC2:** Campo Email — erro inline para formato inválido: "Email inválido" (onBlur + onChange após primeiro blur)
- [x] **AC3:** Campo Senha — indicador de força (fraca/média/forte) com barra visual + requisitos: "Mínimo 8 caracteres"
- [x] **AC4:** Campo Confirmar Senha — erro inline se diferente: "Senhas não coincidem"

### Botão Submit

- [x] **AC5:** Botão "Criar conta" desabilitado com `cursor-not-allowed` e tooltip no hover: "Preencha todos os campos"
- [x] **AC6:** Quando todos os campos válidos: botão muda para estilo primary (ativo) com transição suave
- [x] **AC7:** Durante submit: botão mostra spinner + "Criando conta..."

### Testes

- [x] **AC8:** Teste: submit com campos vazios → erros inline aparecem em todos os campos
- [x] **AC9:** Teste: email inválido → erro inline específico
- [x] **AC10:** Teste: senhas diferentes → erro inline no campo de confirmação

---

## Arquivos Prováveis

- `frontend/app/signup/page.tsx` — formulário de signup
- `frontend/components/` — componentes de form (se existirem)

## Notas

- Verificar se já existe lib de validação no projeto (zod, react-hook-form).
- Se não existir, usar validação nativa HTML5 + state management mínimo (não adicionar lib nova para isso).
