# SEN-BE-005: sitemap_contratos_orgao_indexable retorna 502 "JSON could not be generated"

**Status:** Ready
**Origem:** Sentry unresolved — issue 7408168565 (17 evt em 14d)
**Prioridade:** P1 — Alto (SEO orgânico depende de sitemap indexável)
**Complexidade:** S (Small)
**Owner:** @dev + @data-engineer
**Tipo:** SEO / Performance

---

## Problema

`routes.sitemap_orgaos.sitemap_contratos_orgao_indexable` falha com:

```
{'message': 'JSON could not be generated', 'code': 502, 'hint': 'Refer to full message for details', 'details': '<html>\r\n<head><title>502 Bad Gateway</t...'}
```

PostgREST retorna 502 Bad Gateway — o upstream (PgBouncer/Supavisor) ou a query subjacente está falhando/travando. O HTML entrega pista de que é erro de proxy/gateway, não de PostgREST si.

Impacto:
- Sitemap de contratos por órgão (inbound SEO) fica vazio/desatualizado
- 17 eventos/14d = ~1.2/dia — sitemap crawler do Google pode rebaixar ranking
- Relacionado a SEN-BE-007 (slow_request /v1/sitemap/*) — possivelmente mesma causa raiz

---

## Critérios de Aceite

- [x] **AC1:** Identificar query SQL subjacente (RPC ou raw query) em `backend/routes/sitemap_orgaos.py`
- [x] **AC2:** Executar query direta em Supabase SQL Editor — medir tempo e confirmar erro PgBouncer
- [x] **AC3:** Substituir offset-paginated scan (2M+ rows, ~2000 req REST) por RPC `get_sitemap_contratos_orgao_json` com GROUP BY + ORDER BY + LIMIT < 1s
- [x] **AC4:** Cache layer: resposta de sitemap indexable tem TTL 6h em `backend/routes/sitemap_orgaos.py::_contratos_orgao_cache`
- [x] **AC5:** Stale-while-revalidate: se RPC timeout/falha, serve último cache válido (nunca retorna vazio)
- [ ] **AC6:** Sentry issue `7408168565` não recebe eventos por 48h após fix (deploy + monitor)
- [ ] **AC7:** Validação manual: `curl https://api.smartlic.tech/v1/sitemap/contratos-orgao-indexable` retorna 200 em <10s com payload válido (pós-deploy)

### Anti-requisitos

- NÃO trocar sitemap-indexable para resposta vazia como fallback — rompe SEO

---

## Referência de implementação

- `backend/routes/sitemap_orgaos.py::sitemap_contratos_orgao_indexable`
- RPC provável em `supabase/migrations/` — buscar `sitemap_contratos_orgao` function
- Padrão de ISR existente em `frontend/` — `export const revalidate = 3600` (ver memory `project_sitemap_serialize_isr_pattern`)

---

## Riscos

- **R1 (Médio):** Cache stale pode servir URL de órgão removido — mitigar com TTL 6h (não 24h)
- **R2 (Baixo):** Paginação aumenta latência total — mas cada batch fica abaixo de statement_timeout

## Dependências

- SEN-BE-007 (slow sitemap endpoints) — coordenar fix

---

## Change Log

| Data | Agente | Ação |
|------|--------|------|
| 2026-04-23 | @sm | Story criada — issue único, 17 eventos |
| 2026-04-23 | @po | Validação 10/10 → **GO**. LIVE (lastSeen 2026-04-22). Promovida Draft → Ready |
| 2026-05-12 | @dev | Implementado: RPC `get_sitemap_contratos_orgao_json` substitui scan paginado, stale cache fallback, 6h TTL |

## File List

- `backend/routes/sitemap_orgaos.py` — RPC call substitui offset-paginated scan, stale cache fallback com stale-while-revalidate
- `backend/tests/test_sitemap_orgaos.py` — mock RPC (string list), stale cache + timeout tests
- `supabase/migrations/20260512080000_sitemap_contratos_orgao_rpc.sql` — `get_sitemap_contratos_orgao_json` RPC
- `supabase/migrations/20260512080000_sitemap_contratos_orgao_rpc.down.sql` — rollback
