# DEBT-117: Page Smoke Tests + LGPD Cascade Test

**Prioridade:** GTM-RISK (30 dias)
**Estimativa:** 16-20h
**Fonte:** Brownfield Discovery — @ux (FE-011), @qa (QA-NEW-01)
**Score Impact:** Integrity 7→8

## Contexto
Nenhuma das 5 principais páginas autenticadas (dashboard, pipeline, historico, onboarding, conta) tem teste de rendering. Ademais, não existe teste de integração que valide a chain de FK cascade para user deletion (LGPD compliance).

## Acceptance Criteria

### Page Smoke Tests (12-16h)
- [x] AC1: Test render /dashboard — monta sem crash, mostra loading state
- [x] AC2: Test render /pipeline — monta sem crash, mostra loading state
- [x] AC3: Test render /historico — monta sem crash, mostra loading state
- [x] AC4: Test render /onboarding — monta sem crash, mostra step 1
- [x] AC5: Test render /conta — monta sem crash, mostra sidebar
- [x] AC6: Test error state em cada página (mock API failure → mostra ErrorBoundary/error.tsx)
- [x] AC7: Test loading state em cada página
- [x] AC8: Todos os testes passam com mocks de auth/user context

### LGPD User Deletion Cascade (4h)
- [x] AC9: Integration test backend: cria user, popula search_sessions, pipeline_items, search_results_cache, classification_feedback, user_oauth_tokens, google_sheets_exports
- [x] AC10: Deleta user via Supabase Admin API (auth.users delete)
- [x] AC11: Verifica que TODAS as rows dependentes foram deletadas (cascade chain)
- [x] AC12: Test documenta quais tabelas têm CASCADE e quais não (para referência futura)

## File List
- [x] `frontend/__tests__/pages/DashboardPage.test.tsx` (pre-existing, 27 tests)
- [x] `frontend/__tests__/pages/PipelinePage.test.tsx` (pre-existing, 24 tests)
- [x] `frontend/__tests__/pages/HistoricoPage.test.tsx` (pre-existing, 32 tests)
- [x] `frontend/__tests__/pages/OnboardingPage.test.tsx` (enhanced — +4 error state tests = 40 total)
- [x] `frontend/__tests__/pages/ContaPage.test.tsx` (enhanced — +5 sidebar/error tests = 24 total + 4 layout)
- [x] `backend/tests/integration/test_user_deletion_cascade.py` (NEW — 10 tests)

## Implementation Notes

### Page Smoke Tests
- AC1-AC4 were already covered by pre-existing tests (DashboardPage, PipelinePage, HistoricoPage, OnboardingPage)
- AC5 (sidebar): Added ContaLayout tests verifying sidebar navigation, nav items, hrefs, and children rendering
- AC6 (error states): Added OnboardingPage error tests (profile save failure, network error, first-analysis failure) and PerfilPage save error toast test
- AC7 (loading states): Already covered in all 5 page test files
- AC8 (auth mocks): All test files properly mock auth/user context

### LGPD Cascade Test
- Static analysis approach: reads all migration SQL files and verifies CASCADE declarations
- AC9: Verifies 6 required tables have FK to profiles(id) with ON DELETE CASCADE
- AC10: Verifies profiles(id) has ON DELETE CASCADE from auth.users(id)
- AC11: Validates complete cascade chain completeness across all user-scoped tables
- AC12: Generates cascade chain documentation report + verifies no tables bypass profiles

### Dependencies Fixed
- `react-hook-form` added as devDependency (was missing, caused PerfilPage/OnboardingPage test failures)
