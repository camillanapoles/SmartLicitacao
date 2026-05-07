# STORY-SEO-028 — GSC `/blog/licitacoes` 404 Classification

Source: `gsc-404-urls.txt` in this worktree, filtered to unique `https://smartlic.tech/blog/licitacoes/` URLs.

Canonical sector source checked:

- `frontend/lib/sectors.ts`: frontend route slugs.
- `frontend/lib/programmatic.ts`: backend ID to frontend slug aliases already used by sitemap generation.
- `backend/sectors_data.yaml`: backend sector IDs.

## Summary

| Classification | Count | Mitigation |
| --- | ---: | --- |
| Renamed/migrated sector leaf URLs | 8 | 301 to canonical sector slug |
| Valid canonical sector leaf URLs | 31 | No-op; route exists, sitemap normalization already emits canonical slugs |
| Valid city URLs | 16 | No-op; `/blog/licitacoes/cidade/[cidade]` and `/blog/licitacoes/cidade/[cidade]/[setor]` exist |
| Removed category | 0 | No redirect needed |
| UF malformed | 0 | No redirect needed |
| Malformed/unsupported city shape | 0 | No redirect needed |

## Renamed/Migrated

| URL | Classification | Canonical URL |
| --- | --- | --- |
| `/blog/licitacoes/materiais_hidraulicos/mg` | renamed/migrated | `/blog/licitacoes/materiais-hidraulicos/mg` |
| `/blog/licitacoes/engenharia_rodoviaria/pi` | renamed/migrated | `/blog/licitacoes/engenharia-rodoviaria/pi` |
| `/blog/licitacoes/software_desenvolvimento/es` | renamed/migrated | `/blog/licitacoes/software/es` |
| `/blog/licitacoes/manutencao_predial/pr` | renamed/migrated | `/blog/licitacoes/manutencao-predial/pr` |
| `/blog/licitacoes/software_licencas/ms` | renamed/migrated | `/blog/licitacoes/software/ms` |
| `/blog/licitacoes/medicamentos/rj` | renamed/migrated | `/blog/licitacoes/saude/rj` |
| `/blog/licitacoes/manutencao_predial/sp` | renamed/migrated | `/blog/licitacoes/manutencao-predial/sp` |
| `/blog/licitacoes/frota_veicular/sp` | renamed/migrated | `/blog/licitacoes/transporte/sp` |

## Valid Canonical Sector Leaf URLs

These already use canonical frontend sector slugs and valid UFs. No redirect was added.

- `/blog/licitacoes/mobiliario/ce?modalidade=8`
- `/blog/licitacoes/informatica/ba?modalidade=4`
- `/blog/licitacoes/papelaria/pa`
- `/blog/licitacoes/informatica/ro?modalidade=4`
- `/blog/licitacoes/vigilancia/pa?modalidade=8`
- `/blog/licitacoes/software/pb?modalidade=6`
- `/blog/licitacoes/materiais-eletricos/ba?modalidade=6`
- `/blog/licitacoes/engenharia-rodoviaria/ro?modalidade=8`
- `/blog/licitacoes/manutencao-predial/ro?modalidade=12`
- `/blog/licitacoes/vigilancia/pi`
- `/blog/licitacoes/software/pe`
- `/blog/licitacoes/materiais-eletricos/pe?modalidade=12`
- `/blog/licitacoes/manutencao-predial/sp?modalidade=6`
- `/blog/licitacoes/saude/al?modalidade=4`
- `/blog/licitacoes/manutencao-predial/pa?modalidade=6`
- `/blog/licitacoes/engenharia/mg?modalidade=12`
- `/blog/licitacoes/vigilancia/ap?modalidade=6`
- `/blog/licitacoes/facilities/mg?modalidade=6`
- `/blog/licitacoes/manutencao-predial/ms?modalidade=12`
- `/blog/licitacoes/saude/go?modalidade=6`
- `/blog/licitacoes/vestuario/rs?modalidade=12`
- `/blog/licitacoes/papelaria/sp?modalidade=12`
- `/blog/licitacoes/engenharia/pa`
- `/blog/licitacoes/engenharia/rn?modalidade=6`
- `/blog/licitacoes/vestuario/pb?modalidade=8`
- `/blog/licitacoes/materiais-hidraulicos/pi?modalidade=4`
- `/blog/licitacoes/papelaria/ma`
- `/blog/licitacoes/facilities/sp?modalidade=6`
- `/blog/licitacoes/informatica/pe?modalidade=8`
- `/blog/licitacoes/vigilancia/mt`
- `/blog/licitacoes/informatica/rn?modalidade=12`

## Valid City URLs

These match existing city route shapes and canonical city/sector slugs. No redirect was added.

- `/blog/licitacoes/cidade/salvador/engenharia`
- `/blog/licitacoes/cidade/sao-goncalo/alimentos`
- `/blog/licitacoes/cidade/uberlandia/mobiliario`
- `/blog/licitacoes/cidade/ponta-grossa/manutencao-predial`
- `/blog/licitacoes/cidade/vitoria/mobiliario`
- `/blog/licitacoes/cidade/pelotas`
- `/blog/licitacoes/cidade/anapolis/facilities`
- `/blog/licitacoes/cidade/sao-jose/informatica`
- `/blog/licitacoes/cidade/caxias/facilities`
- `/blog/licitacoes/cidade/fortaleza/papelaria`
- `/blog/licitacoes/cidade/aparecida-de-goiania/saude`
- `/blog/licitacoes/cidade/ilheus/saude`
- `/blog/licitacoes/cidade/cascavel/engenharia`
- `/blog/licitacoes/cidade/vila-velha/materiais-hidraulicos`
- `/blog/licitacoes/cidade/juazeiro/vigilancia`
- `/blog/licitacoes/cidade/montes-claros/materiais-eletricos`

## Sitemap Check

`frontend/app/sitemap.ts` already normalizes backend sector IDs with `backendIdToFrontendSlug()` before emitting `/blog/licitacoes/{setor}/{uf}` URLs in sitemap shard `id:2`. That prevents legacy backend IDs such as `software_desenvolvimento`, `manutencao_predial`, and `materiais_hidraulicos` from being emitted.
