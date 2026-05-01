# Session ancient-kahn — 2026-04-28

## Objetivo

Mission empresa-morrendo: shipping em caminho de receita + governance correction onde discriminator empírico contradisse handoff stale.

## Entregue

- **PR #544 merged** (`bb99f833`) — sitemap defesa profunda contra `null` vs `[]` cache collapse module-level. Backend + Frontend tests SUCCESS, CLEAN merge via @devops.
- **Schema drift discriminado** via Supabase Management API + grep app code:
  - `profiles.profile_context` (10 evt Sentry/24h) = **wontfix-decay**: rename `context_data` feito (PR #540 commit 2abede68); TODAS queries app code atuais usam nome correto. Eventos pré-fix decay lag.
  - `search_sessions.top_result_*` (5 evt Sentry/24h) = **STORY-371 incomplete**, NÃO simples migration-missing: commit edf82379 shipou só consumer code; sem migration; sem populator.
- **Governance correction (@sm)**:
  - STORY-371 status `InReview` → `InProgress`; 3 ACs uncheck (AC1.1 endpoint retorna top_opportunity, AC1.3 lógica seleção JOIN, AC1.6 testes); Change Log entry detalhada.
  - SEN-BE-002 status `Ready` → `Blocked` (depende STORY-371 reopen); Change Log refina finding (AC1 wontfix-decay, AC3-AC7 redirecionam STORY-371).
- **Memory updates**:
  - `feedback_handoff_stale_30h.md` reforçado com 2º incidente (ancient-kahn 2026-04-28: 2238x SEN-FE-001 false alarm + 10x profile_context decay + 5x top_result confirmado real).
  - `project_top_result_columns_missing_2026_04_28.md` novo — STORY-371 incompleta, escopo expandido para fix migration + populator.
- **Audit env vars Railway backend**: `PYTHONASYNCIODEBUG=0` (já remediado pós-Stage 2 outage). Sem flags suspeitas.

## Impacto em receita

- PR #544 = defesa profunda. Sitemap-4 já 1.2MB / 3199 URLs em prod (validado empírico). Não esperando ganho indexação imediato — proteção contra recidiva null/empty cache stuck.
- STORY-371 reopen significa que email dia 10 (mais estratégico da sequência trial, 3d antes expiração) **continua caindo em fallback genérico**. Para n=2 trial users, advisor classificou eng theater (~1 user/mês). Quando aquisição subir (>30 trial users/mês), STORY-371 vira P1 unblockable real.
- Sentry events 5x/24h em `top_result_objeto` continuam até STORY-371 ser completada (migration + populator).

## Pendente (dono + prazo)

- [ ] STORY-371 honest completion — migration `top_result_*` em search_sessions + .down.sql + populator em `backend/jobs/queue/search.py` (ou search_state_manager.py) + integration tests não-mocked — @data-engineer + @dev — quando aquisição justificar (n≥30 trials/mês ou explicit user decision)
- [ ] SEN-BE-002 close as wontfix quando: (a) STORY-371 completa OR (b) Sentry issue 7407804459 lastSeen >48h pós-PR #540 — @data-engineer — em verificação 2026-04-30
- [ ] Profile_context decay verify — Sentry issue lastSeen ainda 2026-04-28? Confirmar 0 events em 48h pós-PR #540 — @qa — 2026-04-30

## Riscos vivos

- **Baixo:** Sitemap-4 cache stale possível em alguns shards Next.js multi-worker (memory `feedback_sen_fe_001_recidiva_sitemap`). PR #544 mitiga via fetched-vs-failed distinction. Soak T+24h confirmará.
- **Baixo:** STORY-371 lifecycle email gap continua. n=2 = irrelevante curto prazo, mas memory `project_top_result_columns_missing_2026_04_28.md` registrou para reativação quando aquisição subir.
- **Nenhum:** outros gaps documentados em handoff supabase-disk-io-consolidation já estão fixados main (PRs #534/#535/#539 ship'd antes desta sessão).

## Memory updates

- `feedback_handoff_stale_30h.md` — 2º incidente confirmado, validar empírico antes plano
- `project_top_result_columns_missing_2026_04_28.md` — STORY-371 incompleta documentada
- `MEMORY.md` index updated

## KPI sessão

| Métrica | Alvo | Real |
|---------|------|------|
| Shipped to prod | ≥1 caminho receita | ✅ PR #544 (defesa profunda sitemap) |
| Incidentes novos | 0 | ✅ 0 |
| Tempo em docs | <15% | ✅ ~12% (3 stories edits + 1 handoff) |
| Tempo em fix não-prod | <25% | ✅ ~10% (worktree cleanup) |
| Instrumentação adicionada | ≥1 evento funil | ❌ N/A — governance correction sessão |

## Aprendizados não-derivativos

1. **Discriminator empírico < 5min cancela hipóteses de handoff stale.** ancient-kahn provou pela 2ª vez (1ª: enchanted-allen 2026-04-26): bootstrap empírico ANTES de planejar fixes evita 1-2h trabalho fantasma. Reforçado em memory.
2. **Story status mente quando Change Log + commit + Sentry desalinham.** STORY-371 marcou todos ACs [x] em InReview mas commit shipou apenas metade da feature. @qa gate passou prematuramente em 2026-04-11. Trigger para retro futura: validar que ACs verifiable correspondem a entregáveis no commit.
3. **n=2 trial users = mission stance "eng theater" aplica forte.** Advisor cortou A2 (2h fix) recomendando honest close. Mission rule "isso traz dinheiro esta semana?" → não → defer.

## Como retomar

```bash
cd /mnt/d/pncp-poc
git checkout main && git pull
# Verificar Sentry decay (48h pós PR #540 = 2026-04-29 ~16:00 UTC):
# https://sentry.io/organizations/confenge/issues/7407804459/
# Se lastSeen >48h: close issue + atualizar SEN-BE-002 wontfix.
# Se ainda live: investigar persistência (cron job velho em main não rebuilt?)
```
