# Spec: Messages & Feedback

> Spec executável (SDD) gerada pelo **Reversa Writer** em 2026-05-08
> Confiança: 🟢 CONFIRMADO

## Component
- **ID**: `messages-feedback`
- **Path**: `backend/routes/messages.py`, `backend/routes/feedback.py`, `backend/feedback_analyzer.py`, `backend/schemas/messages.py`, `backend/schemas/feedback.py`

## Purpose

Dois sub-módulos independentes:
1. **InMail** — suporte interno via conversas com ciclo de vida 4-estado (support inbox)
2. **Feedback** — loop de retroalimentação de classificação IA (verdict FP/FN/correct) com análise de padrões admin + sugestões de exclusão por bi-gram

## Sub-Módulo 1: Messages (InMail)

### Conversation State Machine (4 estados)

```
[*] → open: POST /v1/conversations
open → awaiting_support: user posta primeira mensagem
awaiting_support → awaiting_user: admin reply
awaiting_user → awaiting_support: user reply
awaiting_user → closed: admin PATCH status=closed
awaiting_support → closed: admin PATCH status=closed
closed → awaiting_support: user reply (re-open automático)
closed → [*]
```

### Endpoints (6)

| Método | Path | Auth | Descrição |
|--------|------|------|-----------|
| `POST` | `/v1/conversations` | user | criar conversa + primeira mensagem |
| `GET` | `/v1/conversations` | user | listar conversas do usuário |
| `POST` | `/v1/conversations/{id}/messages` | user/admin | enviar mensagem + transição de estado |
| `GET` | `/v1/conversations/{id}/messages` | user/admin | listar mensagens |
| `PATCH` | `/v1/conversations/{id}/status` | admin | fechar/reabrir conversa |
| `GET` | `/v1/messages/unread-count` | user | count de mensagens admin não-lidas |

### Unread Count

```sql
SELECT count(messages)
FROM messages JOIN conversations
WHERE conversations.user_id = :me
  AND messages.created_at > conversations.last_read_at_user
  AND messages.sender_role = 'admin'
```

### Dados Estruturais

```python
# Conversation
{
  "id": uuid,
  "user_id": uuid,
  "status": "open|awaiting_support|awaiting_user|closed",
  "subject": str,
  "last_read_at_user": datetime | None,
  "created_at": datetime
}

# Message
{
  "id": uuid,
  "conversation_id": uuid,
  "sender_id": uuid,
  "sender_role": "user|admin",
  "body": str,
  "created_at": datetime
}
```

## Sub-Módulo 2: Feedback (Classification Loop)

### Feedback Submit (POST /v1/feedback)

```
POST /v1/feedback + JWT
  → require_auth
  → _check_feedback_enabled (feature flag)
      → off: 503 disabled
  → _check_rate_limit (count last 1h per user)
      → count >= LIMIT: 429 rate exceeded
  → SELECT existing (user_id, search_id, bid_id)
      → exists: UPDATE record
      → not exists: INSERT record
  → verdict in {fp, fn}?
      → sim: FEEDBACK_NEGATIVE_TOTAL[setor].inc() (Prometheus)
  → 201 FeedbackResponse (created|updated)
```

### Verdicts

| Verdict | Significado |
|---------|-------------|
| `correct` | classificação correta |
| `fp` | falso positivo (irrelevante classificado como relevante) |
| `fn` | falso negativo (relevante rejeitado) |

### Pattern Analysis (GET /admin/feedback/patterns)

```
GET /admin/feedback/patterns?setor_id=&days=
  → require_admin
  → SELECT * FROM classification_feedback WHERE created_at >= now-days
  → setor_id provided?
      → sim: load sector keywords from sectors.yaml
  → analyze_feedback_patterns():
      - Counter por verdict
      - precision = correct / (correct + fp)
      - fp_categories Counter
      - _extract_fp_keywords (top 10)
      - _suggest_exclusions (bi-gram analysis)
  → FeedbackPatternsResponse
```

### Keyword FP Extraction

```
for kw in sector_keywords:
  fp_count = bids com verdict=fp contendo kw
  correct_count = bids com verdict=correct contendo kw
  fp > 5 AND correct < 2?
    → _find_co_occurring_words(kw, fp_bid_texts)
    → suggestion = "excluir kw" ou "excluir kw + co_word"
    → append result
→ sort desc por count, top 10
```

### Bi-gram Exclusion Suggestion

```
fp_bigrams = Counter(bi-grams em fp bid_objeto)
correct_bigrams = Counter(bi-grams em correct bid_objeto)
for bigram, count in fp_bigrams.most_common(20):
  count >= 3 AND correct_bigrams[bigram] == 0?
    → append to exclusion suggestions
→ return top 10
```

### Dados Estruturais

```python
# Feedback record (table: classification_feedback)
{
  "id": uuid,
  "user_id": uuid,
  "search_id": uuid,
  "bid_id": str,  # PNCP unique id
  "setor_id": str,
  "verdict": "correct|fp|fn",
  "comment": str | None,
  "created_at": datetime,
  "updated_at": datetime
}

# FeedbackPatternsResponse
{
  "total_feedback": int,
  "precision": float,  # correct / (correct + fp)
  "verdict_counts": {"correct": int, "fp": int, "fn": int},
  "fp_keywords": [{"keyword": str, "count": int, "suggestion": str}],
  "exclusion_suggestions": [{"bigram": str, "count": int}]
}
```

## Functional Requirements

**Messages:**
- **FR-1**: `POST /v1/conversations` cria conversa + mensagem inicial, transiciona para `awaiting_support`
- **FR-2**: `POST /conversations/{id}/messages` user transiciona para `awaiting_support`; admin transiciona para `awaiting_user`
- **FR-3**: `PATCH /conversations/{id}/status` admin fecha (→ `closed`)
- **FR-4**: User reply em `closed` reabre automaticamente (→ `awaiting_support`)
- **FR-5**: `GET /messages/unread-count` retorna count de admin messages não-lidas

**Feedback:**
- **FR-6**: Upsert (INSERT or UPDATE) por `(user_id, search_id, bid_id)` triplet
- **FR-7**: Rate limit: `FEEDBACK_RATE_LIMIT` por user por 1h (Redis counter)
- **FR-8**: Feature flag `FEEDBACK_ENABLED` — `False` retorna 503
- **FR-9**: Prometheus `smartlic_feedback_negative_total{setor}` incrementado em FP/FN
- **FR-10**: `GET /admin/feedback/patterns` retorna análise com precision, keywords FP, bi-gram suggestions
- **FR-11**: `DELETE /v1/feedback/{id}` LGPD (user pode deletar próprio feedback)

## Non-Functional Requirements

- **NFR-1**: Unread count query <50ms (index em `messages.conversation_id, created_at, sender_role`)
- **NFR-2**: Feedback upsert <100ms (unique index em `user_id, search_id, bid_id`)
- **NFR-3**: Pattern analysis aceitável até 5s (admin-only, não crítico)

## Constraints

- **CON-1**: Conversations são user↔support apenas (sem multi-participant)
- **CON-2**: Admin pode ler/reply em qualquer conversa; user só vê as próprias
- **CON-3**: Feedback bi-gram analysis é best-effort (sem ML model) — baseada em Counter simples
- **CON-4**: Rate limit feedback usa Redis (não DB) — reset em restart

## Acceptance Criteria

- AC-1: POST conversa + mensagem → status = `awaiting_support` em DB
- AC-2: Admin reply → status = `awaiting_user`
- AC-3: User reply em `closed` → reabre para `awaiting_support` automaticamente
- AC-4: Feedback FP → `smartlic_feedback_negative_total{setor}` incrementado
- AC-5: Feedback upsert idempotente — segunda submissão atualiza (não duplica)
- AC-6: Pattern analysis com `setor_id` retorna keywords específicas do setor
- AC-7: Rate limit: >N feedbacks/1h retorna 429

## Errors

| Code | HTTP | Trigger |
|------|------|---------|
| `feedback_disabled` | 503 | feature flag off |
| `rate_limit_exceeded` | 429 | feedback count >= LIMIT last 1h |
| `conversation_not_found` | 404 | conversation_id inválido |
| `unauthorized` | 403 | user tentando acessar conversa de outro user |
| `feedback_not_found` | 404 | DELETE feedback não encontrado |

## Code Traceability

- `backend/routes/messages.py` — 6 endpoints conversation CRUD
- `backend/routes/feedback.py` — POST, DELETE feedback + admin patterns
- `backend/feedback_analyzer.py` — `analyze_feedback_patterns`, `_extract_fp_keywords`, `_suggest_exclusions`
- `backend/schemas/messages.py` — `ConversationResponse`, `MessageResponse`, `UnreadCountResponse`
- `backend/schemas/feedback.py` — `FeedbackRequest`, `FeedbackResponse`, `FeedbackPatternsResponse`
- `backend/metrics.py` — `FEEDBACK_NEGATIVE_TOTAL` Prometheus counter

## Dependencies

- Supabase (`conversations`, `messages`, `classification_feedback`)
- Redis (rate limit counter `feedback_rate:{user_id}`)
- Auth: `require_auth`, `require_admin`
- `backend/sectors_data.yaml` (keyword lookup para pattern analysis)
- Prometheus (`smartlic_feedback_negative_total{setor}`)
