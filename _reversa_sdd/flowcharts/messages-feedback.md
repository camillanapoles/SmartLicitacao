# Flowchart — Módulo `messages+feedback`

> Gerado pelo **Reversa Archaeologist** em 2026-04-27 · Confiança 🟢 CONFIRMADO

## Feedback submit (POST /feedback)

```mermaid
flowchart TD
    A[POST /v1/feedback + JWT] --> B[require_auth]
    B --> C[_check_feedback_enabled flag]
    C -->|off| X1[503 disabled]
    C -->|on| D[_check_rate_limit count last 1h]
    D -->|count >= LIMIT| X2[429 rate exceeded]
    D -->|ok| E[SELECT existing user_id, search_id, bid_id]
    E -->|exists| F[UPDATE record]
    E -->|not exists| G[INSERT record]
    F --> H{verdict in fp/fn?}
    G --> H
    H -->|sim| M[FEEDBACK_NEGATIVE_TOTAL setor.inc]
    H -->|não| OK[201 FeedbackResponse updated/created]
    M --> OK
```

## Pattern analysis (admin GET /admin/feedback/patterns)

```mermaid
flowchart TD
    A[GET /admin/feedback/patterns?setor_id&days] --> B[require_admin]
    B --> C[SELECT * FROM classification_feedback WHERE created_at >= now-days]
    C --> D{setor_id provided?}
    D -->|sim| E[load sector keywords from sectors.yaml]
    D -->|não| F[skip keywords]
    E --> G[analyze_feedback_patterns]
    F --> G
    G --> G1[Counter por verdict]
    G --> G2[precision = correct / correct+fp]
    G --> G3[fp_categories Counter]
    G --> G4[_extract_fp_keywords]
    G --> G5[_suggest_exclusions bi-gram analysis]
    G1 & G2 & G3 & G4 & G5 --> R[FeedbackPatternsResponse]
```

## Keyword extraction (FP)

```mermaid
flowchart TD
    A[for kw in sector_keywords] --> B[count fp_count: bids fp com kw]
    B --> C[count correct_count: bids correct com kw]
    C --> D{fp > 5 AND correct < 2?}
    D -->|não| N[skip kw]
    D -->|sim| E[_find_co_occurring_words kw em fp texts]
    E --> F[suggestion = excluir ou co-occurrence com top word]
    F --> G[append result]
    G --> H[sort desc por count, top 10]
```

## Bi-gram exclusion suggestion

```mermaid
flowchart TD
    A[fp_bigrams = Counter de bi-grams em FP bid_objeto] --> B[correct_bigrams = Counter em correct bid_objeto]
    B --> C[for bigram, count in fp_bigrams.most_common 20]
    C --> D{count >= 3 AND correct_bigrams[bigram] == 0?}
    D -->|sim| E[append to suggestions]
    D -->|não| N[skip]
    E --> F[return top 10 suggestions]
```

## Messages — conversation lifecycle

```mermaid
stateDiagram-v2
    [*] --> open: POST /conversations
    open --> awaiting_support: user posta primeira mensagem
    awaiting_support --> awaiting_user: admin reply
    awaiting_user --> awaiting_support: user reply
    awaiting_user --> closed: admin PATCH status=closed
    awaiting_support --> closed: admin PATCH status=closed
    closed --> awaiting_support: user reply (re-open)
    closed --> [*]
```

## Unread count

```mermaid
flowchart TD
    A[GET /api/messages/unread-count] --> B[require_auth]
    B --> C[SELECT count messages JOIN conversations WHERE conv.user_id=me AND msg.created_at > conv.last_read_at_user AND msg.sender_role=admin]
    C --> D[200 UnreadCountResponse count]
```
