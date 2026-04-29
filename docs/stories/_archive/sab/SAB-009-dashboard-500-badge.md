# SAB-009: Dashboard — erro 500 em /api/organizations/me + badge "0%" sem contexto

**Origem:** UX Premium Audit P1-06
**Prioridade:** P1 — Alto
**Complexidade:** M (Medium)
**Sprint:** SAB-P1
**Owner:** @dev
**Screenshots:** `ux-audit/22-dashboard.png`, `ux-audit/23-dashboard-bottom.png`

---

## Problema

Três issues na página de Dashboard:

| Issue | Detalhe |
|-------|---------|
| **HTTP 500** | Console error: `GET /api/organizations/me` retorna 500 |
| **Badge "0%"** | Canto superior direito — sem tooltip ou explicação do que significa |
| **"64h economizadas"** | KPI "Horas Economizadas: 64h" — cálculo não explicado, parece arbitrário |

---

## Critérios de Aceite

### Erro 500

- [x] **AC1:** Diagnosticar causa do `GET /api/organizations/me` 500 — rota existe? Table `organizations` existe no Supabase?
  - **Causa:** PGRST205 — migration `20260301100000_create_organizations.sql` não estava aplicada em produção. Resolvido por STORY-331.
  - Rota existe: `backend/routes/organizations.py` (STORY-322). Tabela existe: `organizations` + `organization_members` com RLS.
  - Guard defensivo `_is_schema_error()` converte PGRST205 → HTTP 503 (não mais 500).
- [x] **AC2:** Se a feature de organizations não está implementada: remover chamada do frontend (não chamar endpoint inexistente)
  - N/A — feature IS implemented (STORY-322), migration applied (STORY-331). Frontend handles gracefully: `.then(res => res.ok ? res.json() : null).catch(() => {})`.
- [x] **AC3:** Se está implementada mas com bug: corrigir o endpoint
  - Fixed by STORY-331: migration applied + defensive PGRST205 guard.
- [x] **AC4:** Zero erros de console (HTTP 4xx/5xx) na página `/dashboard` após fix
  - Verified: Frontend silently handles non-200 responses. No console errors.

### Badge "0%"

- [x] **AC5:** Identificar o que o badge "0%" representa (perfil completo? quota usada? algum score?)
  - Badge = `ProfileProgressBar` component (STORY-260). Shows **profile completeness** percentage (7 fields: ufs_atuacao, porte_empresa, experiencia_licitacoes, faixa_valor_min, capacidade_funcionarios, faturamento_anual, atestados). Calculated by `GET /v1/profile/completeness`.
- [x] **AC6:** Se representa "Perfil de Licitante" completude: adicionar tooltip "Perfil de Licitante: 0% — Preencha para melhorar análises"
  - Added `title` attribute: "Perfil de Licitante: {pct}% — Preencha para melhorar análises" (dynamic). Shows "completo" when 100%.
- [x] **AC7:** Se não tem utilidade clara: remover o badge da interface
  - N/A — badge IS useful (profile completeness). Tooltip added per AC6.

### KPI "Horas Economizadas"

- [x] **AC8:** Documentar o cálculo de "Horas Economizadas" (como 64h é calculado?)
  - Formula: `estimated_hours_saved = total_searches × 2`. Located in `backend/routes/analytics.py:102`. Assumes 2h saved per search vs manual portal research. 32 searches × 2h = 64h.
- [x] **AC9:** Adicionar tooltip no KPI explicando a metodologia (ex: "Estimativa baseada em X buscas × Y minutos por busca manual")
  - Added `tooltip` prop to StatCard: "Estimativa: {N} buscas × 2h por busca manual em portais governamentais" (dynamic).

---

## Files Changed

| File | Change |
|------|--------|
| `frontend/components/ProfileProgressBar.tsx` | Added `title` tooltip attribute (AC6) |
| `frontend/app/dashboard/page.tsx` | Added `tooltip` prop to StatCard, passed tooltip to "Horas economizadas" card (AC9) |
| `frontend/__tests__/story-sab009-dashboard-fixes.test.tsx` | 8 new tests: 4 tooltip, 2 methodology, 2 organizations resilience |
| `docs/stories/SAB-009-dashboard-500-badge.md` | Updated checkboxes with resolution details |

## Notas

- **AC1-AC4 (Organizations 500):** Already resolved by STORY-331 (migration applied + PGRST205 defensive guard). No code changes needed.
- **AC5-AC7 (Badge 0%):** `ProfileProgressBar` is useful — shows profile completeness. Added native tooltip via `title` attribute.
- **AC8-AC9 (Horas Economizadas):** Formula is `total_searches × 2h`. Added tooltip prop to `StatCard` component + dynamic tooltip on the card.
- All 8 pre-existing test suite failures are unrelated (Historico, Admin, error-states).
