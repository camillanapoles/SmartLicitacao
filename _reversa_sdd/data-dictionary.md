# Dicionário de Dados — SmartLic

> Gerado pelo **Reversa Archaeologist** em 2026-04-27
> Construído incrementalmente módulo a módulo. Veja `code-analysis.md` e `.reversa/context/modules.json` para contexto completo.

---

## Módulo `search`

### `SearchContext` (`backend/search_context.py`) — dataclass de pipeline

| Campo | Tipo | Obrigatório | Default | Descrição |
|-------|------|-------------|---------|-----------|
| `request` | `BuscaRequest` | sim | — | Request de busca (`schemas.BuscaRequest`) |
| `user` | `dict` | sim | — | Payload de autenticação (`{id, email, plan_type, ...}`) |
| `start_time` | `float` | sim | `time.time()` | Timestamp Unix do início |
| `tracker` | `ProgressTracker?` | não | `None` | Emissor de eventos SSE |
| `quota_pre_consumed` | `bool` | sim | `False` | Quota consumida em POST antes do enqueue (CRIT-072 AC8) |
| `deadline_ts` | `float?` | não | `None` | Monotonic deadline (`time.monotonic`) |
| `is_admin` | `bool` | sim | `False` | Bypass de quota/rate (de `check_user_roles`) |
| `is_master` | `bool` | sim | `False` | Plano master |
| `quota_info` | `quota.QuotaInfo?` | não | `None` | Capabilities + uso |
| `sector` | `sectors.Sector?` | não | `None` | Setor selecionado |
| `active_keywords` | `set[str]` | sim | `{}` | Keywords ativas |
| `custom_terms` | `list[str]` | sim | `[]` | Termos customizados pelo usuário |
| `stopwords_removed` | `list[str]` | sim | `[]` | Stopwords descartadas |
| `min_match_floor_value` | `int?` | não | `None` | Floor de matches mínimos |
| `active_exclusions` | `set[str]` | sim | `{}` | Exclusões ativas |
| `active_context_required` | `set?` | não | `None` | Contexto obrigatório |
| `licitacoes_raw` | `list[UnifiedProcurement]` | sim | `[]` | Após `stage_execute` |
| `source_stats_data` | `list?` | não | `None` | Stats por source |
| `is_partial` | `bool` | sim | `False` | Resultados parciais |
| `data_sources` | `list[DataSourceStatus]?` | não | `None` | Status por fonte |
| `degradation_reason` | `str?` | não | `None` | Motivo da degradação |
| `failed_ufs` | `list[str]?` | não | `None` | UFs que falharam |
| `succeeded_ufs` | `list[str]?` | não | `None` | UFs OK |
| `is_truncated` | `bool` | sim | `False` | Atingiu `max_pages` em algum source |
| `truncated_ufs` | `list[str]?` | não | `None` | UFs truncadas |
| `truncation_details` | `dict?` | não | `None` | `{"pncp": True, "portal_compras": False}` |
| `cached` | `bool` | sim | `False` | Resultado de cache stale |
| `cached_at` | `str?` | não | `None` | ISO timestamp |
| `cached_sources` | `list[str]?` | não | `None` | Source codes em cache |
| `cache_status` | `Literal['fresh','stale']?` | não | `None` | UX-303 |
| `cache_level` | `Literal['supabase','redis','local']?` | não | `None` | UX-303 |
| `cache_fallback` | `bool` | sim | `False` | STORY-306: cache de outro date range |
| `cache_date_range` | `str?` | não | `None` | Range fallback |
| `from_cache` | `bool` | sim | `False` | Quota skipada porque tudo veio do cache |
| `response_state` | `Literal['live','cached','degraded','empty_failure']` | sim | `'live'` | Semantic state |
| `degradation_guidance` | `str?` | não | `None` | Mensagem ao usuário |
| `sources_degraded` | `list[str]` | sim | `[]` | Ex: `["PNCP"]` |
| `live_fetch_in_progress` | `bool` | sim | `False` | Progressive delivery |
| `licitacoes_filtradas` | `list` | sim | `[]` | Após `stage_filter` |
| `filter_stats` | `dict` | sim | `{}` | Stats por etapa de filtro |
| `hidden_by_min_match` | `int` | sim | `0` | Escondidos por floor |
| `filter_relaxed` | `bool` | sim | `False` | Auto-relaxação aplicada |
| `relaxation_level` | `int?` | não | `None` | 0=normal, 1=no floor, 2=no density, 3=top by value |
| `is_simplified` | `bool` | sim | `False` | LLM skipado por timeout |
| `zero_match_budget_exceeded` | `bool` | sim | `False` | CRIT-057 AC4 |
| `zero_match_classified` | `int` | sim | `0` | Quantos zero-match foram classificados |
| `zero_match_deferred` | `int` | sim | `0` | Diferidos para BG |
| `filter_summary` | `str?` | não | `None` | Texto humano se 0 results |
| `zero_match_candidates` | `list` | sim | `[]` | Candidates para BG job |
| `zero_match_job_id` | `str?` | não | `None` | ARQ job ID |
| `zero_match_candidates_count` | `int` | sim | `0` | Total de candidates |
| `resumo` | `ResumoLicitacoes?` | não | `None` | Após `stage_generate` |
| `excel_base64` | `str?` | não | `None` | Excel como base64 |
| `download_url` | `str?` | não | `None` | URL pré-assinada |
| `excel_available` | `bool` | sim | `False` | Excel disponível para download |
| `upgrade_message` | `str?` | não | `None` | Prompt de upgrade |
| `licitacao_items` | `list[LicitacaoItem]` | sim | `[]` | Items convertidos |
| `llm_source` | `Literal['ai','fallback','processing']?` | não | `None` | Provenance |
| `queue_mode` | `bool` | sim | `False` | Job ARQ dispatched |
| `llm_status` | `Literal['ready','processing']?` | não | `None` | — |
| `excel_status` | `Literal['ready','processing','skipped','failed']?` | não | `None` | — |
| `bid_analysis_status` | `Literal['ready','processing']?` | não | `None` | STORY-259 |
| `user_profile` | `dict?` | não | `None` | Profile context para LLM (STORY-260) |
| `session_id` | `str?` | não | `None` | UUID da search_session |
| `response` | `BuscaResponse?` | não | `None` | Response final |

### `SearchState` (Enum) — `backend/models/search_state.py`

| Valor | Tipo | Terminal? |
|-------|------|-----------|
| `created` | str | não |
| `validating` | str | não |
| `fetching` | str | não |
| `filtering` | str | não |
| `enriching` | str | não |
| `generating` | str | não |
| `persisting` | str | não |
| `completed` | str | sim |
| `failed` | str | sim |
| `rate_limited` | str | sim |
| `timed_out` | str | sim |

### `StateTransition` (dataclass) — `backend/models/search_state.py`

| Campo | Tipo | Obrigatório |
|-------|------|-------------|
| `search_id` | `str` | sim |
| `from_state` | `SearchState?` | não (None na primeira) |
| `to_state` | `SearchState` | sim |
| `stage` | `str?` | não |
| `details` | `dict` | sim (`{}` default) |
| `timestamp` | `float` | sim (`time.time`) |
| `duration_since_previous` | `int?` | não (ms) |
| `user_id` | `str?` | não |

### Tabelas DB referenciadas

| Tabela | Papel | Mutabilidade |
|--------|-------|--------------|
| `search_state_transitions` | Audit log append-only de cada transição | INSERT-only |
| `search_sessions` | Estado mutável da search atual (status, stage) | UPDATE em cada transição |
| `search_results_cache` | Cache L2 persistente, 24h TTL | UPSERT |

---

## Módulo `ingestion-datalake`

### `pncp_raw_bids` (tabela DataLake — schema inferido)

| Campo | Tipo | Obrigatório | Notas |
|-------|------|-------------|-------|
| `numero_controle_pncp` | text PK | sim | Formato `{cnpj}-{seq}-{edital}/{ano}` |
| `objeto_compra` | text | sim | Texto livre — usado em FTS pt-BR + embeddings |
| `valor_total_estimado` | numeric | não | Pode ser 0 (PCP v2 não fornece) |
| `situacao_compra` / `situacao_compra_nome` | text | sim | Estado da compra |
| `orgao_*` | text/jsonb | sim | CNPJ, razão social, esfera |
| `unidade_*` | text/jsonb | sim | Unidade orçamentária |
| `uf` | char(2) | sim | Estado |
| `municipio` | text | não | Município |
| `modalidade_id` | int | sim | 4/5/6/7/8/12 |
| `modalidade_nome` | text | sim | — |
| `data_publicacao` | timestamptz | sim* | Fallback `now()-1d` se NULL (STORY-2.12 AC4) |
| `data_abertura` | timestamptz | sim* | Fallback = `data_publicacao` |
| `data_encerramento` | timestamptz | não | Bids em aberto se > now() |
| `content_hash` | text | sim | SHA-256 hex |
| `crawl_batch_id` | uuid | sim | FK para `ingestion_runs.run_id` |
| `source` | text | sim | `pncp` |
| `objeto_embedding` | vector(1536) | não | pgvector — opt-in `EMBEDDING_ENABLED` (STORY-438) |
| `tsvector_*` | tsvector | sim | FTS multi-coluna (STORY-437) |
| `created_at` | timestamptz | sim | `now()` |
| `updated_at` | timestamptz | sim | `now()` em update |

### `ingestion_checkpoints`

| Campo | Tipo | Obrigatório |
|-------|------|-------------|
| `uf` | char(2) | sim |
| `modalidade_id` | int | sim |
| `source` | text | sim (`pncp`) |
| `status` | text | sim (`completed`, `failed`, `running`) |
| `last_date` | date | sim |
| `created_at` | timestamptz | sim |

PK composto: `(uf, modalidade_id, source)` — múltiplas linhas por status histórico.

### `ingestion_runs`

| Campo | Tipo | Obrigatório |
|-------|------|-------------|
| `run_id` | uuid PK | sim |
| `crawl_type` | text | sim (`full`, `incremental`, `backfill`, `purge`) |
| `started_at` | timestamptz | sim |
| `completed_at` | timestamptz | não |
| `ufs_processed` | int | sim (default 0) |
| `records_upserted` | int | sim (default 0) |
| `records_inserted` | int | não |
| `records_updated` | int | não |
| `records_unchanged` | int | não |
| `errors` | jsonb | não |
| `final_status` | text | não (`success`, `failed`, `partial`) |

### `supplier_contracts` (SEO crawler — schema inferido)

| Campo | Tipo | Obrigatório | Notas |
|-------|------|-------------|-------|
| `contract_id` | text PK | sim | — |
| `cnpj_fornecedor` | text | sim | — |
| `cnpj_orgao` | text | sim | — |
| `objeto` | text | sim | — |
| `valor_global` | numeric | sim | — |
| `data_inicio_vigencia` | date | não | — |
| `data_fim_vigencia` | date | não | — |
| `municipio`, `uf`, `esfera` | text | sim | — |
| `categoria` | text | não | Inferida |
| `created_at`, `updated_at` | timestamptz | sim | — |

### RPCs Supabase

| Nome | Assinatura | Retorno |
|------|-----------|---------|
| `upsert_pncp_raw_bids` | `(p_records jsonb)` | `(inserted int, updated int, unchanged int)` |
| `purge_old_bids` | `(p_retention_days int)` | count |
| `search_datalake` | `(ufs, data_inicial, data_final, modalidades, tsquery, websearch_text, modo_busca, limit, ...)` | linhas `pncp_raw_bids` |

---

## Módulo `filter-llm-viability`

### `ViabilityFactors` (Pydantic — `viability.py:30`)

| Campo | Tipo | Range | Descrição |
|-------|------|-------|-----------|
| `modalidade` | int | 0-100 | Score modality |
| `modalidade_label` | str | "" | "Ótimo"/"Bom"/"Regular"/"Baixo"/"Não informada" |
| `timeline` | int | 0-100 | — |
| `timeline_label` | str | "" | "{N} dias"/"Encerrada"/"Não informado" |
| `value_fit` | int | 0-100 | — |
| `value_fit_label` | str | "" | "Ideal"/"Abaixo"/"Muito abaixo"/"Acima"/"Muito acima"/"Não informado" |
| `geography` | int | 0-100 | — |
| `geography_label` | str | "" | "Sua região"/"Região adjacente"/"Distante"/"Não identificada" |

### `ViabilityAssessment` (Pydantic — `viability.py:43`)

| Campo | Tipo | Notas |
|-------|------|-------|
| `viability_score` | int 0-100 | Soma ponderada |
| `viability_level` | Literal | `alta` (>70), `media` (40-70), `baixa` (<40) |
| `factors` | `ViabilityFactors` | Breakdown |

### `Sector` (de `sectors_data.yaml`)

| Campo | Tipo | Obrigatório |
|-------|------|-------------|
| `name` | str | sim |
| `description` | str | sim |
| `max_contract_value` | int | sim |
| `viability_value_range` | tuple[float, float] | sim (D-04) |
| `keywords` | list[str] | sim |
| `exclusions` | list[str] | não |
| `context_required_keywords` | list[str] | não |

**Setor IDs (20):** `vestuario`, `alimentos`, `informatica`, `mobiliario`, `papelaria`, `engenharia`, `software_desenvolvimento`, `software_licencas`, `servicos_prediais`, `produtos_limpeza`, `medicamentos`, `equipamentos_medicos`, `insumos_hospitalares`, `vigilancia`, `transporte_servicos`, `frota_veicular`, `manutencao_predial`, `engenharia_rodoviaria`, `materiais_eletricos`, `materiais_hidraulicos`.

🟡 Discrepância: CLAUDE.md ainda afirma "15 Setores" (linha 37); YAML tem 20.

### `LLMClassification` (Pydantic — `classification.py`)

🟡 Schema inferido:
- `decision: bool`
- `confidence: float 0-1`
- `reasoning: str?`
- `evidence: str?`
- `source: Literal["keyword","llm_standard","llm_conservative","llm_zero_match"]`

### Constantes globais (filter+llm+viability)

| Const | Valor |
|-------|-------|
| `MODALITY_SCORES` | dict 16 entradas (com/sem acento) |
| `DEFAULT_MODALITY_SCORE` | 50 |
| `REGION_MAP` | dict 5 macro-regiões → UFs |
| `_UF_TO_REGION` | reverse map (pré-computado) |
| `DEFAULT_VALUE_RANGE` | (50_000, 5_000_000) |
| `_SECTOR_NEGATIVE_EXAMPLES` | dict 13+ setores → list[str] (org name traps STORY-328 AC13) |
| `PHRASE_MATCH_BONUS` | 0.15 |
| `MIN_MATCH_DIVISOR` | 3 |
| `MIN_MATCH_CAP` | 3 |
| `_PRICING_INPUT_PER_M` | 0.10 USD/M (gpt-4.1-nano) |
| `_PRICING_OUTPUT_PER_M` | 0.40 USD/M |
| `_ARBITER_CACHE_MAX` | 5000 (env `LRU_MAX_SIZE`) |
| `_ARBITER_REDIS_PREFIX` | `smartlic:arbiter:` |
| `LLM_TIMEOUT_S` | 5 (env `OPENAI_TIMEOUT_S`, 5× p99) |
| `LLM_MODEL` | `gpt-4.1-nano` |
| `LLM_MAX_TOKENS` | 1 (sector classification YES/NO) |
| `LLM_STRUCTURED_MAX_TOKENS` | 800 (output estruturado) |
| `LLM_TEMPERATURE` | 0 (determinístico) |

---

## Módulo `billing-quota`

### `PlanCapabilities` (TypedDict — `quota_core.py:85`)

| Campo | Tipo | Notas |
|-------|------|-------|
| `max_history_days` | int | 7-99999 |
| `allow_excel` | bool | — |
| `allow_pipeline` | bool | STORY-250 |
| `max_requests_per_month` | int | 10-99999 |
| `max_requests_per_min` | int | 2-120 |
| `max_summary_tokens` | int | 200-10000 |
| `priority` | str | `low/normal/high/critical` |

### `PlanPriority` (Enum)

`low | normal | high | critical`

### Planos (`PLAN_CAPABILITIES`)

`free_trial`, `smartlic_pro`, `founding_member`, `consultoria` (atuais)
`consultor_agil`, `maquina`, `sala_guerra` (legados)
`master`, `free` (admin/legado prod)

Detalhes capabilities em `code-analysis.md#módulo-5--billing-quota`.

### `QuotaInfo` (Pydantic — schema inferido 🟡)

| Campo | Tipo | Notas |
|-------|------|-------|
| `plan_id` | str | — |
| `plan_name` | str | de `PLAN_NAMES` |
| `capabilities` | `PlanCapabilities` | — |
| `used_this_month` | int | de `monthly_quota.searches_count` |
| `remaining_this_month` | int | `max_per_month - used` |
| `reset_date` | datetime | 1º próximo mês UTC |
| `in_trial` | bool | — |
| `trial_phase` | `TrialPhaseInfo?` | — |
| `can_search` | bool | — |
| `error_message` | str? | — |

### `TrialPhaseInfo` (Pydantic — schema inferido 🟡)

| Campo | Tipo |
|-------|------|
| `started_at` | datetime |
| `expires_at` | datetime |
| `days_remaining` | int |
| `phase` | Literal[`active`, `ending`, `expired`] |

### Tabelas DB

| Tabela | Papel | Notas |
|--------|-------|-------|
| `profiles` | `id` (=auth.users.id), `plan_type`, `is_admin`, `is_master`, `trial_expires_at`, `stripe_customer_id`, `context_data jsonb` | safety net |
| `user_subscriptions` | `user_id`, `is_active`, `stripe_subscription_id`, `expires_at`, `billing_period`, `created_at` | primária |
| `monthly_quota` | `user_id`, `month_year` (`YYYY-MM`), `searches_count` | PK composto, atomic increment |
| `org_subscriptions` | STORY-322 multi-user | — |
| `stripe_webhook_events` | `id` (Stripe event id, PK), `type`, `status`, `received_at`, `processed_at`, `payload jsonb` | idempotency + 5min stuck recovery |
| `plan_billing_periods` | `plan_id`, `period` (`monthly/semiannual/annual`), `price_cents`, `stripe_price_id` | source of truth pricing |
| `plan_features` | `plan_id`, `feature_key`, `feature_value` | — |
| `partner_referrals` | tracking referrals | STORY |

### `stripe_webhook_events.status` valores

- `processing` (claim inicial)
- `completed` (sucesso)
- `failed` (exception)
- `timeout` (asyncio.TimeoutError 30s)

### Eventos Stripe roteados (12)

```
checkout.session.{completed,expired,async_payment_succeeded,async_payment_failed}
customer.subscription.{created,updated,deleted,trial_will_end}
invoice.payment_{succeeded,failed,action_required}
```

### Constantes

| Const | Valor |
|-------|-------|
| `PLAN_CAPABILITIES_CACHE_TTL` | 300s |
| `PLAN_STATUS_CACHE_TTL` | 300s |
| `PLAN_STATUS_CACHE_MAXSIZE` | 1000 |
| `SUBSCRIPTION_GRACE_DAYS` | 3 (MED-SEC-002) |
| `WEBHOOK_DB_TIMEOUT_S` | 30s |

---

## Módulo `pipeline-kanban`

### `PipelineItemCreate` (`backend/schemas/pipeline.py`)

| Campo | Tipo | Obrigatório | Default | Constraint |
|-------|------|-------------|---------|-----------|
| `pncp_id` | str | sim | — | min_length=1, max_length=100 |
| `objeto` | str | sim | — | min_length=1, max_length=2000 |
| `orgao` | str? | não | None | max_length=500 |
| `uf` | str? | não | None | max_length=2 |
| `valor_estimado` | float? | não | None | ge=0 |
| `data_encerramento` | str? | não | None | ISO timestamp |
| `link_pncp` | str? | não | None | max_length=500 |
| `stage` | str? | não | "descoberta" | ∈ VALID_PIPELINE_STAGES |
| `notes` | str? | não | None | max_length=5000 |
| `search_id` | str? | não | None | max_length=100 (DEBT-120) |

### `PipelineItemUpdate`

| Campo | Tipo | Obrigatório | Default | Constraint |
|-------|------|-------------|---------|-----------|
| `stage` | str? | não | None | ∈ VALID_PIPELINE_STAGES |
| `notes` | str? | não | None | max_length=5000 |
| `version` | int? | não | None | optimistic locking (STORY-307) |

### `PipelineItemResponse`

| Campo | Tipo | Notas |
|-------|------|-------|
| `id` | str (uuid) | PK |
| `user_id` | str (uuid) | FK profiles |
| `pncp_id` | str | unique com user_id |
| `objeto`, `orgao`, `uf`, `valor_estimado`, `data_encerramento`, `link_pncp` | — | espelham create |
| `stage` | str | enum |
| `notes` | str? | — |
| `search_id` | str? | — |
| `created_at`, `updated_at` | str (timestamptz ISO) | — |
| `version` | int | default 1 |

### Tabela `pipeline_items` (DB)

| Coluna | Tipo | NULL | Notas |
|--------|------|------|-------|
| `id` | uuid | NO | PK gen_random_uuid() |
| `user_id` | uuid | NO | FK profiles ON DELETE CASCADE |
| `pncp_id` | text | NO | UNIQUE(user_id, pncp_id) |
| `objeto` | text | NO | — |
| `orgao` | text | YES | — |
| `uf` | char(2) | YES | — |
| `valor_estimado` | numeric | YES | — |
| `data_encerramento` | timestamptz | YES | — |
| `link_pncp` | text | YES | — |
| `stage` | text | NO | CHECK ∈ VALID_PIPELINE_STAGES, default 'descoberta' |
| `notes` | text | YES | — |
| `search_id` | text | YES | DEBT-120 |
| `version` | int | NO | default 1 (STORY-307) |
| `created_at` | timestamptz | NO | default now() |
| `updated_at` | timestamptz | NO | default now() (trigger update) |

### Constantes

| Const | Valor |
|-------|-------|
| `VALID_PIPELINE_STAGES` | `{descoberta, analise, preparando, enviada, resultado}` |
| `STAGES_ORDER` | `[descoberta, analise, preparando, enviada, resultado]` (display order) |
| `TRIAL_PAYWALL_MAX_PIPELINE` | 5 |
