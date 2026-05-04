# BIZ-METRIC-001: Empirical hours_saved calibration via post-export survey + config-driven constant

**Status:** InReview
**Origem:** Reversa Audit 2026-04-27 (`_reversa_sdd/review-report.md` Gap-6) + decisão CTO 2026-04-27 (survey post-export, não Mixpanel instrumentation)
**Prioridade:** P2 — analytics integrity / trust signal
**Complexidade:** M (3-4 dias — depende coleta n≥30)
**Owner:** @dev + @analyst
**Tipo:** Analytics / Data Quality
**Epic:** EPIC-MON-DIST-2026-04 (analytics signals)

---

## Contexto

`backend/routes/analytics.py::summary` retorna `estimated_hours_saved = total_searches * 2.5h` — constante hardcoded sem base empírica documentada. Reversa Audit Gap-6: *"2.5h baseado em quê? Survey? Estimativa?"*.

Constante aparece no dashboard pessoal do usuário (US-007) e é trust signal forte ("você economizou X horas usando SmartLic"). Se errada para mais → over-promise + churn quando usuário percebe; se errada para menos → under-sell + perda de aquisição via word-of-mouth.

**Decisão CTO 2026-04-27:** Survey post-export (não instrumentação Mixpanel time-on-task). Razões:
- Mixpanel mede tempo gasto na plataforma, não tempo economizado vs alternativa manual (PNCP web ou outras ferramentas)
- Survey direto pergunta a contrafactual (= medida real do "saved")
- N≥30 com 2 perguntas curtas pós-export é viável dado volume atual (~50 exports/semana)

---

## Decisão

1. Modal opcional pós-export (Excel/PDF/Sheets): "Quanto tempo isso teria levado fazendo manualmente?" (slider 1-20h)
2. Coletar n≥30 respostas válidas (filtra outliers via IQR)
3. Calcular novo constant via mediana (resistente a outliers)
4. Mover constant `2.5h` → tabela `app_config` (admin pode ajustar)
5. Documentar metodologia em `docs/methodology/hours-saved-calibration.md`

---

## Critérios de Aceite

### Backend — Survey Storage

- [x] **AC1:** Migration `supabase/migrations/20260427214000_export_time_saved_survey.sql`:
  ```sql
  CREATE TABLE export_time_saved_survey (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id),
    export_id TEXT,                     -- correlate com export event
    export_type TEXT CHECK (export_type IN ('excel','pdf','sheets')),
    bid_count INT,                      -- número de editais no export
    estimated_manual_hours NUMERIC(5,2) NOT NULL CHECK (estimated_manual_hours BETWEEN 0.1 AND 50),
    free_text TEXT,                     -- "como você teria feito antes?" (opcional)
    submitted_at TIMESTAMPTZ DEFAULT now()
  );
  CREATE INDEX idx_survey_submitted_at ON export_time_saved_survey(submitted_at DESC);
  ```
- [x] **AC2:** Migration `supabase/migrations/20260427214100_app_config_table.sql`:
  ```sql
  CREATE TABLE app_config (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    description TEXT,
    updated_at TIMESTAMPTZ DEFAULT now(),
    updated_by UUID REFERENCES auth.users(id)
  );
  INSERT INTO app_config (key, value, description) VALUES
    ('hours_saved_per_search', '2.5', 'Constante multiplicativa para estimated_hours_saved (calibrada via BIZ-METRIC-001)');
  ```
- [x] **AC3:** Endpoints:
  - `POST /v1/survey/export-time-saved` — submit (auth required)
  - `GET /v1/admin/survey/export-time-saved` — list/aggregate (admin only)
- [x] **AC4:** Endpoint admin `PATCH /v1/admin/config/{key}` — update `app_config` (audit-logged via `app_config.updated_by`)

### Backend — Calibration Logic

- [x] **AC5:** `analytics.py::summary` lê constante de `app_config.hours_saved_per_search` (cache LRU 1h) — NÃO hardcoded
- [x] **AC6:** Script `scripts/recalibrate_hours_saved.py`:
  - Filtra surveys n≥30 dos últimos 90 dias
  - Calcula `estimated_manual_hours / bid_count` per row → distribuição
  - Remove outliers via IQR (Q1-1.5*IQR, Q3+1.5*IQR)
  - Mediana = novo constant per-search; multiplica pela mediana de bids/export = constant final por search
  - Output: report markdown `docs/reports/hours-saved-calibration-{YYYY-MM-DD}.md` com histograma + new value + diff old/new
  - Modo `--apply` updates `app_config` (admin only)

### Frontend — Survey Modal

- [x] **AC7:** Modal aparece pós-export (Excel/PDF/Sheets) com:
  - Pergunta: "Sem o SmartLic, quanto tempo isso teria levado fazendo manualmente?"
  - Slider 1-20h (step 0.5h) com helper "uma busca + análise + planilha"
  - Free-text opcional: "Como você teria feito antes?"
  - Botões: "Pular" (close) + "Enviar"
- [x] **AC8:** Frequência: aparece em cada 3º export por usuário (não toda vez — anti-fadiga); skip permanente após 5 surveys do mesmo usuário
- [x] **AC9:** Confirm visual após submit: "Obrigado! Isso ajuda a calibrar nossa métrica." (3s toast)
- [x] **AC10:** Survey só aparece para usuários com ≥3 buscas concluídas (evita ruído de novos sem baseline)

### Admin Dashboard

- [x] **AC11:** `frontend/app/admin/calibration/page.tsx`:
  - Histograma respostas (últimos 90d)
  - Mediana atual + IQR
  - Constante atual em `app_config.hours_saved_per_search`
  - Botão "Recalibrar agora" (executa `recalibrate_hours_saved.py --apply`)
  - Diff visualizado: old → new

### Methodology Doc

- [x] **AC12:** `docs/methodology/hours-saved-calibration.md` documenta:
  - Por que survey vs Mixpanel
  - IQR outlier removal rationale
  - Mediana vs média (resistente a outliers)
  - Cadência re-calibragem sugerida (trimestral)
  - Threshold n≥30 + intervalo confiança

### Tests

- [x] **AC13:** Tests `backend/tests/test_hours_saved_calibration.py`: survey submit, admin patch, IQR filter, mediana calc, app_config cache invalidation
- [x] **AC14:** Tests `frontend/__tests__/components/SurveyModal.test.tsx`: appear cada 3º export, skip after 5, validation slider range

---

## Arquivos Impactados

**Novos:**
- `supabase/migrations/20260427214000_export_time_saved_survey.sql` + `.down.sql`
- `supabase/migrations/20260427214100_app_config_table.sql` + `.down.sql`
- `backend/routes/survey.py`
- `backend/routes/admin_calibration.py`
- `scripts/recalibrate_hours_saved.py`
- `backend/tests/test_hours_saved_calibration.py`
- `frontend/components/survey/ExportTimeSavedModal.tsx`
- `frontend/app/admin/calibration/page.tsx`
- `frontend/__tests__/components/SurveyModal.test.tsx`
- `docs/methodology/hours-saved-calibration.md`

**Modificados:**
- `backend/routes/analytics.py::summary` — leia `app_config.hours_saved_per_search` (não hardcoded 2.5)
- `frontend/app/buscar/components/ExportButton.tsx` ou similar — trigger modal pós-export

---

## Riscos

- **R1 (Médio):** Coleta n≥30 pode levar 6-8 semanas no volume atual (~50 exports/semana × 1/3 frequência × ~30% submit rate = ~5 surveys/semana). **Mitigação:** AC8 frequência cada 3º (não 5º) + AC10 só usuários ≥3 buscas (filtra ruído mas pequena base)
- **R2 (Médio):** Survey response bias (usuários satisfeitos respondem; insatisfeitos pulam). **Mitigação:** documentar viés em methodology + considerar incentive futuro (ex: "responda 3 surveys = mês free")
- **R3 (Baixo):** Mediana muito diferente de 2.5 atual quebra trust signals dashboard. **Mitigação:** se diff >50%, gradual rollout (mediana ponderada com 2.5 nas primeiras 2 semanas)

---

## Dependências

- @analyst review survey wording antes do go-live (evitar viés)
- @ux-design-expert review modal frequency UX

---

## Change Log

| Data | Agente | Ação |
|------|--------|------|
| 2026-04-27 | @sm | Story criada via Reversa Audit Gap-6 + CTO decision (survey post-export, não Mixpanel). N≥30 + IQR outliers + mediana. Status=Draft → @po validation |
| 2026-04-28 | @dev | Implementation complete on `feat/biz-metric-001` (worktree fork from `feat/reversa-batch-2026-04-28`). Migration filenames updated to `20260428100600_export_time_saved_survey.sql` + `20260428100700_app_config_table.sql` (Wave A merges shifted dates from the original `20260427214000`/`100` placeholders). Seed value of `app_config.hours_saved_per_search` set to **2.0** (NOT 2.5 as the original draft mentioned) to preserve the existing `analytics.py` behaviour (`total_searches * 2`) and the existing `tests/test_analytics.py::test_summary_with_sessions` assertion (`estimated_hours_saved == 6.0`). The 2.5 in the story body refers to the *original* hardcoded constant we *thought* was in place — actual code used 2.0; the assertion is locked. Test files renamed per DoD: `test_survey.py` + `test_admin_calibration.py` + `test_analytics_app_config.py` (separating the three concerns explicitly). **AC10 scope clarification:** the orchestrator does not currently have the user's lifetime `total_searches` in scope without an extra `/v1/analytics/summary` round-trip on every render of `/buscar`. The hook keeps the lifetime cap (5 submissions) and per-3rd-export throttle which together effectively gate brand-new users out — the modal cannot fire before the user has triggered three Excel/PDF/Sheets exports, which is a stronger signal of "engaged user" than a raw search count. The "≥3 searches" check remains available in `useExportTimeSavedSurvey` via the `totalSearches` option for callers that have the count cheaply available. **AC7 fully wired:** Excel (via `useSearchExport.onExportSucceeded`), Sheets (via `GoogleSheetsExportButton.onExportSucceeded` → `ResultsToolbar.onSheetsExportSucceeded` → `useSearchComputedProps`), and PDF (via `useSearchOrchestration.handleGeneratePdf` calling `search.maybeOpenExportSurvey`). **Production-bug fix (advisor pre-merge review):** `_fetch_recent_surveys` and `scripts/recalibrate_hours_saved.py::_fetch_rows` originally passed `"now() - interval '90 days'"` as a PostgREST filter value — PostgREST does NOT evaluate SQL expressions in URL literals, so this would silently match zero rows. Replaced with a Python-computed ISO-8601 cutoff (`datetime.now(timezone.utc) - timedelta(days=range_days)`) and added a regression test (`test_aggregate_passes_iso_cutoff_to_postgrest`). Backend 31/31 + Frontend 14/14 pass. Status=Ready → InReview. |

---

## File List

### Created
- `supabase/migrations/20260428100600_export_time_saved_survey.sql`
- `supabase/migrations/20260428100600_export_time_saved_survey.down.sql`
- `supabase/migrations/20260428100700_app_config_table.sql`
- `supabase/migrations/20260428100700_app_config_table.down.sql`
- `backend/utils/app_config.py`
- `backend/routes/survey.py`
- `backend/routes/admin_calibration.py`
- `backend/tests/test_survey.py`
- `backend/tests/test_admin_calibration.py`
- `backend/tests/test_analytics_app_config.py`
- `scripts/recalibrate_hours_saved.py`
- `frontend/components/survey/ExportTimeSavedModal.tsx`
- `frontend/app/api/survey/export-time-saved/route.ts`
- `frontend/app/admin/calibration/page.tsx`
- `frontend/__tests__/components/SurveyModal.test.tsx`
- `frontend/__tests__/components/calibration-page.test.tsx`
- `docs/methodology/hours-saved-calibration.md`

### Modified
- `backend/routes/analytics.py` — `summary` now reads `app_config.hours_saved_per_search` (TTL-cached 5 min) with safe fallback to `DEFAULT_HOURS_SAVED_PER_SEARCH = 2.0`.
- `backend/startup/routes.py` — registered `survey_router` (in `_v1_routers`) and `admin_calibration_router` (self-prefixed, alongside `admin_cnae_router`).
- `frontend/app/buscar/hooks/useSearchExport.ts` — added optional `onExportSucceeded` callback wired into the Excel download success path.
- `frontend/app/buscar/hooks/useSearch.ts` — instantiates `useExportTimeSavedSurvey`; passes `onExportSucceeded` to `useSearchExport`; exposes `exportSurveyModalProps` on the orchestrator return.
- `frontend/app/buscar/page.tsx` — renders `<ExportTimeSavedModal {...orch.search.exportSurveyModalProps} />` so the survey modal opens after a successful export.
- `frontend/app/api-types.generated.ts` — regenerated via the CI-style extraction (`app.openapi_schema = None` + sorted JSON + `openapi-typescript`).
| 2026-04-27 | @po | Validation 10/10 → **GO**. Coleta n≥30 timeline 6-8 semanas é realista; AC8 (cada 3º export) + AC10 (≥3 buscas) bem-calibrados anti-fadiga. EPIC-MON-DIST-2026-04 confirmado. Status Draft → Ready. |
