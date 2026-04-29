# STORY-403: Filtro de esfera rejeita 77% dos resultados silenciosamente

**Prioridade:** P1
**Esforço:** M
**Squad:** team-bidiq-feature

## Contexto
O filtro de esfera governamental (Federal/Estadual/Municipal) inicia com todas as esferas selecionadas (`["F", "E", "M"]`), mas o mecanismo de matching no backend é frágil: depende de campos `esferaId`/`esfera`/`tipoEsfera` que muitas licitações não preenchem. O fallback por keywords no nome do órgão ("ministério", "prefeitura") também é limitado. Resultado: 77% das licitações são rejeitadas pelo filtro de esfera mesmo quando o usuário quer ver "todas". Além disso, o filtro fica dentro de um accordion colapsado por padrão, tornando-o invisível.

## Problema (Causa Raiz)
- `backend/filter.py:2442-2477`: Filtro de esfera ativado quando `esferas` tem valor (mesmo `["F", "E", "M"]` = "todas"). Licitações sem `esferaId` e sem keywords no nome do órgão são rejeitadas.
- `frontend/app/buscar/hooks/useSearchFilters.ts:196`: `useState<Esfera[]>(["F", "E", "M"])` — envia todas as esferas ao backend, ativando o filtro desnecessariamente.
- `frontend/app/buscar/components/FilterPanel.tsx:62`: Accordion "Filtragem por Esfera" colapsado por padrão.

## Critérios de Aceitação
- [x] AC1: Backend (`filter.py`): Quando `esferas=["F", "E", "M"]` (todas selecionadas), tratar como `esferas=None` e pular o filtro inteiramente.
- [x] AC2: Backend (`filter.py`): Quando esfera não pode ser determinada (sem `esferaId` e sem match por keywords), incluir a licitação (fail-open) em vez de rejeitar (fail-close). Adicionar campo `_esfera_inferred: bool` para rastreabilidade.
- [x] AC3: Frontend (`useSearchFilters.ts`): Quando todas as 3 esferas estão selecionadas, enviar `esferas: undefined` (não enviar o campo) na request ao backend.
- [x] AC4: Frontend (`FilterPanel.tsx`): Renomear label "Filtragem por Esfera" para "Filtros avançados de localização" para melhor discoverability.
- [x] AC5: Frontend: Adicionar indicador visual (badge com count) no botão do accordion quando filtros de localização estão ativos e diferem do padrão.
- [x] AC6: Logar `stats["esfera_indeterminada"]` count no backend para monitorar quantas licitações têm esfera desconhecida.

## Arquivos Impactados
- `backend/filter.py` — Lógica de fail-open para esfera indeterminada; skip quando todas selecionadas.
- `frontend/app/buscar/hooks/useSearchFilters.ts` — Não enviar `esferas` quando todas selecionadas.
- `frontend/app/buscar/hooks/useSearch.ts` — Ajustar payload.
- `frontend/app/buscar/components/FilterPanel.tsx` — Renomear label, badge de filtros ativos.

## Testes Necessários
- [x] Backend: Teste que `esferas=["F","E","M"]` retorna mesma quantidade que `esferas=None`.
- [x] Backend: Teste que licitação sem `esferaId` é incluída (fail-open).
- [x] Backend: Teste que `stats["esfera_indeterminada"]` é incrementado corretamente.
- [x] Frontend: Teste que 3 esferas selecionadas não envia campo `esferas` no request body.
- [x] Frontend: Teste que accordion mostra badge quando filtro difere do padrão.

## Notas Técnicas
- A mudança para fail-open pode aumentar resultados irrelevantes. Monitorar via `esfera_indeterminada` e considerar adicionar classificação de esfera por IA (CNPJ range analysis) em story futura.
- Muitas licitações PNCP não preenchem `esferaId` — é um problema de qualidade da fonte, não do nosso código.
