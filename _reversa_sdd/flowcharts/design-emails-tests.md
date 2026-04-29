# Flowcharts — Módulos `design-system`, `email-templates`, `tests+migrations`

> Gerado pelo **Reversa Archaeologist** em 2026-04-27 · Confiança 🟢 CONFIRMADO

## Design system token resolution

```mermaid
flowchart LR
    A[Component .tsx] --> B[className 'bg-canvas text-ink rounded-card']
    B --> C[Tailwind compile]
    C --> D[CSS classes resolved]
    D --> E[bg-canvas → background-color: var(--canvas)]
    D --> F[text-ink → color: var(--ink)]
    D --> G[rounded-card → border-radius: 8px]
    E & F --> H[browser reads :root CSS vars]
    H -->|light| I[--canvas: #fff, --ink: #1e2d3b]
    H -->|dark via .dark| J[--canvas: #0a1e3f, --ink: #f7f8fa]
```

## Trial email lifecycle

```mermaid
sequenceDiagram
    participant U as New user signup
    participant DB as profiles
    participant CRON as _trial_sequence_loop
    participant T as templates/emails/trial
    participant R as Resend
    participant W as Webhook /trial-emails/webhook
    participant LOG as trial_email_log

    U->>DB: INSERT profiles trial_expires_at=now+14d
    Note over CRON: Tick every TRIAL_SEQUENCE_INTERVAL_SECONDS
    CRON->>DB: SELECT users WHERE day_in_trial in {0,3,7,10,13,16} AND no email_log entry
    DB-->>CRON: batch up to TRIAL_SEQUENCE_BATCH_SIZE
    CRON->>T: render template body for day N
    T-->>CRON: email_base wrapped HTML
    CRON->>R: send via Resend SDK
    R-->>CRON: {id, status: queued}
    CRON->>LOG: INSERT user_id, day_in_trial, sent_at, message_id, delivery_status=null
    R->>W: webhook delivered/bounced/opened/clicked
    W->>W: HMAC verify (GAP — não impl)
    W->>LOG: UPDATE delivery_status, opened_at, clicked_at WHERE message_id
```

## Migration apply pipeline (CRIT-050)

```mermaid
flowchart TD
    PR[PR opened] --> MG[migration-gate.yml]
    MG --> MG1[detects supabase/migrations/ changes]
    MG1 --> MG2{*.down.sql pair exists?}
    MG2 -->|não| BLOCK1[BLOCK: missing rollback]
    MG2 -->|sim| MG3[list pending migrations]
    MG3 --> MG4[POST warning comment to PR]
    MG --> MERGE[PR merged to main]
    MERGE --> DEP[deploy.yml]
    DEP --> DEP1[supabase db push --include-all]
    DEP1 --> DEP2[NOTIFY pgrst, 'reload schema']
    DEP2 --> DEP3[smoke test verify no PGRST205]
    DEP3 -->|ok| OK[deploy success]
    DEP3 -->|fail| DEG[mark DEGRADED não rollback]
    MERGE --> CHK[migration-check.yml push + daily]
    CHK --> CHK1{unapplied detected?}
    CHK1 -->|sim| BLOCK2[exit 1]
```

## Test execution (anti-hang)

```mermaid
flowchart TD
    A[pytest invoke] --> B[conftest.py loads fixtures]
    B --> C[_isolate_arq_module autouse]
    B --> D[_cleanup_pending_async_tasks autouse]
    B --> E[pytest-timeout 30s default]
    B --> F[timeout_method=thread Windows compat]
    A --> G[run test suite]
    G --> G1{test uses ARQ?}
    G1 -->|sim| H[sys.modules arq mock-fresh per test]
    G1 -->|não| I[skip]
    G --> G2{test fires asyncio.create_task?}
    G2 -->|sim| J[fixture cancels lingering tasks]
    G --> G3{test exceeds 30s?}
    G3 -->|sim| X[fail timeout — print stack]
    G3 -->|não| OK[pass]
    H & I & J & OK --> END[test result]
```

## Storybook component story

```mermaid
flowchart TD
    A[components/ui/button.stories.tsx] --> B[Storybook server picks up]
    B --> C[render Button variants: default, outline, ghost, destructive, link]
    C --> D[interactive controls knobs]
    D --> E[a11y addon: WCAG validation]
    E --> F[visual regression Chromatic? unconfirmed]
```
