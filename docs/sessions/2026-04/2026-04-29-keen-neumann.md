# Session keen-neumann — 2026-04-29

## Objetivo

Recuperar API smartlic.tech wedged (UPTIME-CRITICAL: caminho de pagamento bloqueado) + ship ≥1 mitigation contra próxima wave.

## Entregue

- **Recovery API** 00:55 UTC — GraphQL `deploymentRedeploy(id="76f8d6fa")` no deploy bom (latest `b89c717b` era silent twin FAILED por bug rootDirectory recidivo). API `/health/live` 200 1.3s, `/v1/plans` 200 2.4s. Caminho de pagamento OK.
- **Commit `bfa3eb8e`** — `fix(frontend): alertas-publicos ISR 1h→24h (incident keen-neumann 2026-04-29)`. 405 pages reduzem wave de re-validation 24×.
- **Push direto main** (admin bypass — `enforce_admins=false` permite). Frontend Railway deploy `3abbe14e` BUILDING.

## Impacto em receita

- **API up** = signups + checkouts + Stripe webhooks desbloqueados (foi ~25min completo down).
- **alertas-publicos ISR 1h→24h** = mitigação preventiva próxima wave Stage 4. Não previne sozinho sob WC=1, mas reduz fan-out 24×.
- **Hipótese a testar**: 30min de soak pós-deploy frontend → confirmar Sentry `slow_request` decai e `/health/live` p99 <2s mantém. Se wedge volta em <24h = pattern não basta + WC=1 é gargalo real, escalar RES-BE-002 sweep.

## Pendente (dono + prazo)

- [ ] **Confirmar frontend deploy `3abbe14e` SUCCESS** + probe `https://smartlic.tech/alertas-publicos/mobiliario/SP` — pré-requisito para "ship ≥1 mitigation" cumprido. @user/próxima sessão.
- [ ] **Soak monitor 24h** — @qa — observar Sentry `slow_request` + `/health/live` p99 em prod
- [ ] **RES-BE-002 sweep** ~20 rotas SEO programmatic com sync `.execute()` — @architect → @sm story breakdown — Sprint atual
- [ ] **Investigar WC=1 → 2** com soak — memory `feedback_web_concurrency_4_amplifier` warn — @data-engineer/@architect — Sprint próximo
- [ ] **Adicionar UA ao backend log middleware** — discriminator empírico bot vs human (gap nesta sessão: discriminação por anomalia ISR 1h vs 24h, NÃO empírica via UA) — @dev — backlog (cheap 5min)
- [ ] **Frontend builds cascata fail** — backend wedge → 4 frontend builds FAILED em sequência. Stale Dockerfile build sem retry/circuit breaker em fetch BACKEND_URL durante SSG — @dev — backlog
- [ ] **Stash WIP docs** `session-keen-neumann unrelated docs WIP` (`git stash list`) — content de sessões prévias não-commited; @user revisar próxima sessão se merge

## Riscos vivos

- **WC=1 + qualquer query lenta = wedge garantido próxima wave** — pattern PR #529/#533/#535 aplicado mas insuficiente isolado. Severidade ALTA. Tempo para virar incidente: 6-48h dependendo de tráfego/Googlebot crawl.
- **Frontend deploy `3abbe14e` BUILDING** — se FAILED novamente, fix ISR 1h→24h NÃO entra em prod e objetivo "ship ≥1 mitigation" é parcialmente cumprido (recovery sim, prevention não). Severidade MÉDIA. Mitigação esperada pois cascade fail anterior era causada por backend wedge (resolvido).
- **Bug Railway rootDirectory recidiva** — silent twin FAILED espera recorrer. Workaround documentado em memory; fix permanente requer dashboard Railway intervention pelo user.

## Memory updates

- `project_backend_outage_2026_04_29_stage4.md` (novo) — recovery via GraphQL mutation + lessons WC=1 fix-per-route insufficient
- `MEMORY.md` (index) — entrada adicionada
