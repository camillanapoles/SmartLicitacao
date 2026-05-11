# CNAE → SmartLic Sector Coverage

**Story:** DATA-CNAE-001
**Source of truth:** `public.cnae_setor_mapping` (Supabase) — seeded by
`supabase/migrations/20260511120000_cnae_setor_mapping.sql`.
**Code fallback:** `backend/utils/cnae_mapping.py::CNAE_TO_SETOR`.

## Snapshot (2026-05-11)

| Sector | CNAE count |
| --- | ---: |
| engenharia | 25 |
| vestuario | 5 |
| servicos_prediais | 4 |
| vigilancia | 2 |
| saude | 6 |
| alimentos | 4 |
| informatica | 5 |
| equipamentos | 3 |
| transporte | 5 |
| **Total mapped** | **59** |

IBGE CNAE 2.3 publishes ~1300 active subclasses (4-digit prefixes used as
keys here are wider — there are ~673 4-digit groups). With **59 entries
mapped**, coverage is roughly **9 %** at the 4-digit granularity. The
remaining ~91 % currently fall through `map_cnae_to_setor()` to the
default sector `"geral"` and emit `cnae_not_mapped` WARN logs.

## CNAEs that fall back to `geral`

Notable gaps (review-report.md Gap-8 backlog):

- **Educação** (CNAE 85xx): no mapping today.
- **Construção naval / aeronáutica** (3011, 3041): no mapping.
- **Mobiliário** (3101–3103): no mapping.
- **Energia** (3511–3520): no mapping.
- **Tratamento de resíduos** (3811–3839): no mapping.
- **Comércio atacadista geral** (469x não-saúde / não-alimento): no mapping.
- **Serviços profissionais** (69xx jurídico, contábil): no mapping.

Use `SELECT * FROM cnae_setor_mapping WHERE notes ILIKE 'seed%'` to see
the curated seed; everything outside this set is treated as `geral`.

## Adding new mappings at runtime

Admins can add/update without redeploys via:

```bash
curl -X POST https://api.smartlic.tech/v1/admin/cnae-mapping \
  -H "Authorization: Bearer <admin-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"cnae_code": "8511", "setor_id": "educacao", "confidence": 0.95,
       "notes": "Educação infantil — added 2026-05-11"}'
```

The backend LRU cache (`lookup_cnae_setor`) is invalidated by the admin
endpoint on every write, so the new value is visible on the next request.

## Soft delete

`DELETE /v1/admin/cnae-mapping/{cnae_code}` does not row-delete; it sets
`notes = 'deleted'` so the audit trail (created_at, updated_by) is
preserved. The lookup path treats those rows as missing and falls back
to the hardcoded dict (if any) or to `None`.
