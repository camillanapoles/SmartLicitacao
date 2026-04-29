# Flowchart — Módulo `filter-llm-viability`

> Gerado pelo **Reversa Archaeologist** em 2026-04-27

## 1. Pipeline de Filtros (fail-fast)

```mermaid
flowchart TD
  In[licitacoes_raw] --> Uf[1. UF check]
  Uf -->|fail| Drop1[descarta]
  Uf -->|pass| Val[2. Value range]
  Val -->|fail| Drop2[descarta]
  Val -->|pass| Kw[3. Keyword density]
  Kw -->|>5%| Src1[source=keyword · ACCEPT]
  Kw -->|2-5%| LLMs[source=llm_standard]
  Kw -->|1-2%| LLMc[source=llm_conservative]
  Kw -->|0%| LLMz[source=llm_zero_match]
  LLMs --> LLMcall[LLM clarifier]
  LLMc --> LLMcall
  LLMz --> Batch[Batch zero_match · 20 items]
  LLMcall -->|YES| Acc[ACCEPT]
  LLMcall -->|NO| Drop3[REJECT]
  LLMcall -->|fail| FB{LLM_FALLBACK_PENDING_ENABLED?}
  Batch -->|YES| Acc
  Batch -->|NO| Drop3
  Batch -->|count_mismatch| RejAll[Reject ALL · zero-noise]
  FB -->|true| Pend[PENDING_REVIEW]
  FB -->|false| Drop3
  Acc --> St[4. Status / data validation]
  Pend --> St
  St -->|fail| Drop4[descarta]
  St -->|pass| Via[5. Viability assessment]
  Via --> Out[licitacoes_filtradas + viability_score]
```

## 2. Min-Match Floor (STORY-178 AC2.2)

```
total_terms | min_matches | comportamento
1           | 1           | original (sem mudança)
2           | 1           | original (sem mudança)
3           | 1           | original (sem mudança)
4-6         | 2           | exige overlap mínimo
7-9         | 3 (cap)     | evita exclusão excessiva
10+         | 3 (cap)     | preserva recall em buscas amplas
```

`should_include`:
- A: `matched_count >= min_matches` → True
- B: `has_phrase_match` (multi-word exato) → True (override A)

`score = min(1.0, matched/total + 0.15 × phrase_count)`

## 3. LLM Cache 2-Tier

```mermaid
flowchart LR
  Req[Classify request] --> Hash[MD5 do input]
  Hash --> L1{L1 in-mem hit?}
  L1 -->|sim| Ret1[return cached]
  L1 -->|não| L2{L2 Redis hit?}
  L2 -->|sim| Pop1[populate L1 + return]
  L2 -->|não| Call[OpenAI gpt-4.1-nano]
  Call --> Set[L1.set + L2.set + LRU evict if full]
  Set --> Ret2[return result]
```

## 4. Viability — 4 Fatores (D-04)

```
Total = 0.30 × modalidade
      + 0.25 × timeline
      + 0.25 × value_fit
      + 0.20 × geography

(+ porte bonus modality, STORY-260 AC7)
```

| Fator | 100 | 80 | 70 | 60 | 50 | 40 | 30 | 20 | 10 |
|-------|-----|----|----|----|----|----|----|----|----|
| Modalidade | Pregão Eletr. | Pregão Pres. | Concorr. Eletr. | Concorr. Pres. | Credenciamento / default | Dispensa | — | — | — |
| Timeline | >14 dias | 7-14d | — | 3-7d | n/a | — | 1-3d | — | encerrada |
| Value Fit | dentro range | — | — | abaixo ≥50% / acima ≤2x | valor=0 (neutro) | — | — | abaixo <50% / acima >2x | — |
| Geography | UF na busca | — | — | mesma macro-região | n/a | — | distante | — | — |

**Levels:** alta>70 · media 40-70 · baixa<40

## 5. Batch Zero-Match (UX-402 AC5)

```mermaid
flowchart TD
  Batch[até 20 items zero-match] --> Prompt[_build_zero_match_batch_prompt]
  Prompt --> LLM[OpenAI single call]
  LLM --> Raw[1. YES\n2. NO\n3. SIM\n...]
  Raw --> Re[regex parse]
  Re --> Cnt{count == expected?}
  Cnt -->|sim| Map[map decisions to items]
  Cnt -->|não| Reject[reject ALL · zero-noise philosophy]
```

## 6. Macro-regiões BR (geography)

```
norte:        AC AM AP PA RO RR TO
nordeste:     AL BA CE MA PB PE PI RN SE
centro_oeste: DF GO MS MT
sudeste:      ES MG RJ SP
sul:          PR RS SC
```
