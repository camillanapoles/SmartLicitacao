import * as Sentry from "@sentry/nextjs";

// STORY-211 AC6: Edge runtime Sentry initialization
const dsn = process.env.SENTRY_DSN;

if (dsn) {
  Sentry.init({
    dsn,
    tracesSampleRate: 0.1,
    sampleRate: 0.15,
    environment: process.env.ENVIRONMENT || process.env.NODE_ENV,

    beforeSend(event) {
      const message = event.exception?.values?.[0]?.value || "";

      // Drop ISR static→dynamic warnings (quota heavy)
      if (message.includes("Page changed from static to dynamic at runtime")) {
        return null;
      }

      // Drop user-cancelled requests
      const closeReason =
        (event.tags as Record<string, unknown> | undefined)?.close_reason ||
        (event.extra as Record<string, unknown> | undefined)?.close_reason;
      if (closeReason === "USER_CANCELLED" || closeReason === "NAVIGATION") {
        return null;
      }

      const isAbort =
        message.includes("AbortError") ||
        message.includes("The user aborted a request");
      if (isAbort && closeReason !== "TIMEOUT" && closeReason !== "UNKNOWN") {
        return null;
      }

      return event;
    },
  });
}
