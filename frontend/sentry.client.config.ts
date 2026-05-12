import * as Sentry from "@sentry/nextjs";

// STORY-211 AC6: Client-side Sentry initialization
// AC18: Graceful no-op when DSN is not configured
const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;

// SMARTLIC-FE-F-INVEST-001 AC2: opt-in debug logging gate. Setting
// NEXT_PUBLIC_SENTRY_DEBUG=1 emits one console line per event the SDK
// considers, before beforeSend filter rules drop it. This is how we will
// surface in the future whether a "missing" event was filtered locally or
// quota-rate-limited by Sentry. Off by default to avoid prod console noise.
const SENTRY_DEBUG = process.env.NEXT_PUBLIC_SENTRY_DEBUG === "1";

if (dsn) {
  Sentry.init({
    dsn,
    tracesSampleRate: 0.1,
    sampleRate: 0.15,
    environment: process.env.NEXT_PUBLIC_ENVIRONMENT || process.env.NODE_ENV,

    // GTM-STAB-006 AC6 + STORY-422 (EPIC-INCIDENT-2026-04-10):
    // Reduce SSE proxy noise and drop legitimate user cancellations.
    beforeSend(event) {
      const message = event.exception?.values?.[0]?.value || "";

      if (SENTRY_DEBUG) {
        // eslint-disable-next-line no-console
        console.log(
          "[sentry-debug] beforeSend",
          event.event_id,
          event.level,
          message.slice(0, 160)
        );
      }

      // STORY-422 AC1/AC4: Drop events that carry an explicit
      // `close_reason: USER_CANCELLED` tag/extra. These are legitimate user
      // actions (e.g. clicking "Cancelar busca") and must not pollute the
      // Sentry dashboard. Sentry issue 7387910087 surfaced 34+ such events
      // before this filter was added.
      const closeReasonTag = (event.tags as Record<string, unknown> | undefined)?.close_reason;
      const closeReasonExtra = (event.extra as Record<string, unknown> | undefined)?.close_reason;
      const closeReason = String(closeReasonTag ?? closeReasonExtra ?? "");
      if (closeReason === "USER_CANCELLED" || closeReason === "NAVIGATION") {
        return null;
      }

      // STORY-422 AC4: Generic AbortError/Connection closed without explicit
      // reason and without retry context is almost always a navigation away —
      // drop unless tagged as unexpected.
      const isAbortError =
        message.includes("AbortError") ||
        message.includes("The user aborted a request") ||
        message.includes("Connection closed");
      if (isAbortError && closeReason !== "TIMEOUT" && closeReason !== "UNKNOWN") {
        return null;
      }

      // Expected SSE pipe errors during long searches — downgrade to warning
      if (
        message.includes("failed to pipe") ||
        message.includes("BodyTimeoutError") ||
        (message.includes("TypeError") && message.includes("terminated"))
      ) {
        event.level = "warning";
        event.tags = { ...event.tags, sse_pipe_error: "true" };
        // Drop if > 110s elapsed (expected timeout, not actionable)
        const elapsed = event.tags?.elapsed_ms;
        if (typeof elapsed === "number" && elapsed > 110000) {
          return null;
        }
      }
      return event;
    },
  });
}
