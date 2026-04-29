# UX-356 — Dashboard: Gráfico "Setores" Exibe Slugs em vez de Nomes Completos

**Status:** Done
**Priority:** P3 — Cosmetic
**Severity:** Visual (dados corretos, label errado)
**Created:** 2026-02-23
**Relates to:** UX-354 (Histórico Rendering Polish — resolvido no /historico)

---

## Problema

O gráfico "Setores mais buscados" no Dashboard (`/dashboard`) exibe slugs internos em vez dos nomes de exibição dos setores.

### Observado

```
Gráfico horizontal bar chart:
  engenharia ████████████████ 8
  vestuario  ████████████ 6
  saude      ██ 1
```

### Esperado

```
Gráfico horizontal bar chart:
  Engenharia, Projetos e Obras ████████████████ 8
  Vestuário e Uniformes        ████████████ 6
  Saúde                        ██ 1
```

### Contexto

UX-354 corrigiu exatamente este bug no `/historico` — adicionou mapeamento slug→nome. Porém o mesmo mapeamento NÃO foi aplicado no Dashboard.

O endpoint `/api/analytics?endpoint=top-dimensions` retorna slugs do backend. O frontend precisa fazer o mapeamento local.

## Acceptance Criteria

- [x] **AC1**: Gráfico "Setores mais buscados" exibe nomes completos (ex: "Engenharia, Projetos e Obras")
- [x] **AC2**: Todos 15 slugs mapeados (usar mesmo SECTOR_NAMES do /historico)
- [x] **AC3**: Slug desconhecido exibe o slug original como fallback (não quebra)
- [x] **AC4**: Nomes longos truncam com ellipsis se necessário (não quebrar layout)
- [x] **AC5**: Test: render chart com slug "vestuario" → exibe "Vestuário e Uniformes"
- [x] **AC6**: Zero regression nos outros gráficos do dashboard

## Solução Proposta

Extrair o `SECTOR_NAMES` mapping que já existe em `/historico` para um shared utility:

```typescript
// utils/sector-names.ts (ou constante compartilhada)
export const SECTOR_DISPLAY_NAMES: Record<string, string> = {
  vestuario: 'Vestuário e Uniformes',
  alimentos: 'Alimentos e Merenda',
  informatica: 'Hardware e Equipamentos de TI',
  // ... 15 setores
};

export function getSectorDisplayName(slug: string): string {
  return SECTOR_DISPLAY_NAMES[slug] || slug;
}
```

Depois usar no componente do chart em `app/dashboard/page.tsx`.

## Files Envolvidos

- `frontend/lib/constants/sector-names.ts` — NEW: Shared utility (SECTOR_DISPLAY_NAMES + getSectorDisplayName)
- `frontend/app/dashboard/page.tsx` — Chart rendering (uses sectorChartData + tickFormatter truncation)
- `frontend/app/historico/page.tsx` — Now imports from shared utility
- `frontend/__tests__/dashboard-sector-names.test.tsx` — NEW: 10 tests covering AC1-AC6

## Screenshot de Evidência

`validation-04-dashboard.png` — Capturado durante validação UX 2026-02-23
