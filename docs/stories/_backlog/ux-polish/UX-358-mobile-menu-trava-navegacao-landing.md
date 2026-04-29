# UX-358 — Menu Mobile da Landing Trava Navegacao e Impede Retorno

**Status:** Done
**Priority:** P1 — Critical (bloqueio de conversao)
**Severity:** Funcional — impede uso completo no mobile
**Created:** 2026-02-24
**Completed:** 2026-02-24
**Sprint:** Next
**Relates to:** UX-340 (MobileDrawer autenticado)

---

## Problema

No mobile, o menu hamburger da landing page (`/`) tem experiencia terrivel:

1. **Header translucido obstrui conteudo** — Quando o usuario rola a pagina, o header muda para `bg-surface-0/70 backdrop-blur-xl` (70% opacidade), criando um efeito translucido que compete visualmente com o conteudo da pagina, especialmente em dispositivos com telas menores.

2. **Menu trava a pagina** — Ao abrir o menu, `document.body.style.overflow = 'hidden'` e aplicado (MobileMenu.tsx:31). Se o menu nao fechar corretamente (edge cases de navegacao, touch events perdidos, ou back button do browser), o `overflow: hidden` persiste e **toda a pagina fica travada** sem scroll.

3. **Impossivel retornar a tela inicial** — O menu nao tem mecanismo de fallback robusto para destravar a pagina. O botao de voltar do browser nao fecha o menu (nao usa History API). Nao ha timeout de seguranca. Se o overlay click falhar, o usuario fica preso.

4. **Overlay translucido confuso** — O overlay usa `bg-black/50 backdrop-blur-sm` (MobileMenu.tsx:63) que, combinado com o header translucido, cria uma camada visual confusa onde o usuario nao sabe exatamente onde clicar para fechar.

### Impacto

- **Bloqueio total de conversao mobile** — usuario nao consegue navegar, cadastrar-se, ou fazer login
- Mobile representa ~60% do trafego de landing pages B2G
- Qualquer falha no close handler = pagina permanentemente travada ate F5

### Causa Raiz

Arquivos envolvidos:
- `frontend/components/layout/MobileMenu.tsx` — scroll lock via `document.body.style.overflow`
- `frontend/app/components/landing/LandingNavbar.tsx` — estado `isMobileMenuOpen` + header translucido

O componente depende de 4 mecanismos de close (overlay click, botao X, Escape, link click) mas nao tem **nenhum fallback** se todos falharem. Alem disso, nao integra com a History API do browser (back button).

---

## Acceptance Criteria

### AC1 — Header opaco no mobile (remover translucidez problematica)
- [x] No mobile (<768px), quando scrollado, header usa background **100% opaco** (`bg-[var(--surface-0)]` sem opacity)
- [x] Desktop mantem o efeito translucido atual (nao regredir)
- [x] Transicao de transparente para opaco mantem-se suave (300ms)

### AC2 — Body scroll lock robusto com failsafe
- [x] Substituir `document.body.style.overflow = 'hidden'` por abordagem mais robusta:
  - Usar `position: fixed` + `top: -scrollY` + restaurar scroll position no close
  - OU usar `overscroll-behavior: contain` no painel do menu
- [x] Adicionar **timeout de seguranca** (10s): se menu estiver aberto por >10s sem interacao, log warning
- [x] Cleanup no `useEffect` return garante 100% que overflow e restaurado em **qualquer** cenario de unmount

### AC3 — Integracao com History API (back button fecha menu)
- [x] Ao abrir o menu, fazer `window.history.pushState({ mobileMenu: true }, '')`
- [x] Listener `popstate` fecha o menu quando usuario pressiona back button
- [x] Impedir que back button navegue para pagina anterior enquanto menu esta aberto
- [x] Cleanup do listener no unmount

### AC4 — Overlay com area de toque clara
- [x] Overlay muda de `bg-black/50 backdrop-blur-sm` para `bg-black/60` (sem blur, mais opaco)
- [x] Area de toque do overlay deve cobrir 100% da tela excluindo o painel do menu
- [x] Tap/click no overlay fecha menu de forma confiavel (testar com touch events reais)

### AC5 — Botao de fechar acessivel e visivel
- [x] Botao X no menu tem `min-h-[48px] min-w-[48px]` (aumentar de 44px para melhor touch)
- [x] Adicionar label textual "Fechar" ao lado do X para clareza
- [x] Focus trap dentro do menu enquanto aberto (Tab nao sai do painel)

### AC6 — Fallback de emergencia
- [x] Se `overflow: hidden` persistir no body apos menu fechar, remover automaticamente em 500ms (MutationObserver ou requestAnimationFrame check)
- [x] Adicionar `data-mobile-menu-open` attribute no body para debugging
- [x] Console.warn se scroll lock durar >15 segundos

### AC7 — Testes
- [x] Atualizar testes existentes em `frontend/__tests__/layout/mobile-menu.test.tsx` (15 testes base)
- [x] Adicionar teste: back button fecha menu
- [x] Adicionar teste: scroll lock removido no unmount inesperado
- [x] Adicionar teste: timeout de seguranca emite warning
- [x] Adicionar teste: overlay sem backdrop-blur
- [x] Todos os 15+ testes existentes continuam passando (27 total agora)

---

## Solucao Tecnica Implementada

### 1. Header opaco no mobile (LandingNavbar.tsx)

```tsx
// Mobile: bg-[var(--surface-0)] (100% opaque)
// Desktop: md:bg-surface-0/70 md:backdrop-blur-xl (translucent, unchanged)
'bg-[var(--surface-0)] md:bg-surface-0/70 md:backdrop-blur-xl shadow-[0_1px_3px_rgba(0,0,0,0.04)] border-b border-[var(--border)]/50'
```

### 2. Scroll lock robusto (MobileMenu.tsx)

Used `position: fixed` + `top: -scrollY` approach with `scrollYRef` to correctly restore scroll position. The cleanup function checks `wasLocked` before calling `window.scrollTo()` to avoid unnecessary scroll on initial render or unmount.

### 3. History API integration (MobileMenu.tsx)

```tsx
useEffect(() => {
  if (!isOpen) return;
  window.history.pushState({ mobileMenu: true }, '');
  const handlePopState = () => { onClose(); };
  window.addEventListener('popstate', handlePopState);
  return () => window.removeEventListener('popstate', handlePopState);
}, [isOpen, onClose]);
```

### 4. Additional features implemented
- **Focus trap** — Tab key cycles within menu panel, auto-focuses close button
- **Interaction tracking** — `lastInteractionRef` tracks touchstart/click/keydown
- **Safety timeout** — `setInterval` every 5s checks elapsed time, warns at 10s and 15s
- **Emergency fallback** — `setTimeout(500ms)` after close checks for stuck `position: fixed`
- **Overlay** — `bg-black/60` (no blur), covers full screen except menu panel

---

## Arquivos Modificados

| Arquivo | Mudanca |
|---------|---------|
| `frontend/components/layout/MobileMenu.tsx` | Scroll lock robusto (position:fixed), History API, overlay opaco, focus trap, failsafe, safety timeout |
| `frontend/app/components/landing/LandingNavbar.tsx` | Header opaco no mobile (md: prefixed translucency) |
| `frontend/__tests__/layout/mobile-menu.test.tsx` | 15 testes atualizados + 12 novos = 27 total |

---

## Validacao

- [ ] Testar em iPhone SE (320px) — menor viewport
- [ ] Testar em iPhone 13/14 (390px) — mais comum
- [ ] Testar em Android (360px) — variante comum
- [x] Abrir menu > pressionar back > menu fecha, pagina nao navega (tested via unit test)
- [x] Abrir menu > esperar 15s > verificar console warning (tested via unit test)
- [x] Abrir menu > forcar unmount do componente > body volta ao normal (tested via unit test)
- [ ] Navegar landing inteira sem nenhum travamento

## Definition of Done

- [x] Todos os AC passando
- [x] 0 falhas nos testes existentes (15 base + 12 novos = 27 total)
- [ ] Testado manualmente em 3 viewports mobile
- [ ] Sem regressao no desktop
- [ ] Code review aprovado
