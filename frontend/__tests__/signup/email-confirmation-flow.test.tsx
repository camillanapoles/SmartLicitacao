/**
 * CONV-INST-003 AC3+AC8: Email confirmation flow — 5-min timeout → modal + event.
 *
 * Uses jest.useFakeTimers() to advance 5 minutes and assert:
 *   - email_verification_timeout event fires
 *   - <EmailDeadEndModal> becomes visible
 *
 * Per advisor: wrap timer advance in `act(async () => { jest.advanceTimersByTime(...) })`
 * and flush microtasks after to avoid spurious failures.
 */
/** @jest-environment jsdom */
import React from "react";
import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockTrackEvent = jest.fn();
jest.mock("../../hooks/useAnalytics", () => ({
  useAnalytics: () => ({ trackEvent: mockTrackEvent }),
}));

jest.mock("next/link", () => {
  const MockLink = ({ href, children, ...rest }: { href: string; children: React.ReactNode; [k: string]: unknown }) => (
    <a href={href} {...rest}>{children}</a>
  );
  MockLink.displayName = "MockLink";
  return MockLink;
});

// Use real EmailDeadEndModal so we can assert its presence
// but mock next/link inside it via the above mock already registered.

import { SignupSuccess } from "../../app/signup/components/SignupSuccess";

// ── Constants ─────────────────────────────────────────────────────────────────

const FIVE_MINUTES_MS = 5 * 60 * 1000;
const DEFAULT_PROPS = {
  email: "user@acme.com",
  isConfirmed: false,
  countdown: 60,
  isResending: false,
  onResend: jest.fn(),
  onChangeEmail: jest.fn(),
  rolloutBranch: "legacy" as const,
};

// ── Tests ─────────────────────────────────────────────────────────────────────

beforeEach(() => {
  jest.clearAllMocks();
  jest.useFakeTimers();
});

afterEach(() => {
  jest.runOnlyPendingTimers();
  jest.useRealTimers();
});

describe("Email confirmation flow — 5-minute timeout", () => {
  it("does NOT show dead-end modal before 5 minutes", () => {
    render(
      <SignupSuccess
        {...DEFAULT_PROPS}
        signupStartedAt={Date.now()}
      />
    );

    // Advance 4 minutes — modal should NOT appear
    act(() => {
      jest.advanceTimersByTime(4 * 60 * 1000);
    });

    expect(screen.queryByTestId("email-dead-end-modal")).not.toBeInTheDocument();
  });

  it("shows dead-end modal after 5 minutes without confirmation", async () => {
    const startedAt = Date.now();
    render(
      <SignupSuccess
        {...DEFAULT_PROPS}
        signupStartedAt={startedAt}
      />
    );

    await act(async () => {
      jest.advanceTimersByTime(FIVE_MINUTES_MS + 100);
      await Promise.resolve(); // flush microtasks
    });

    expect(screen.getByTestId("email-dead-end-modal")).toBeInTheDocument();
  });

  it("fires email_verification_timeout event at 5 minutes", async () => {
    const startedAt = Date.now();
    render(
      <SignupSuccess
        {...DEFAULT_PROPS}
        signupStartedAt={startedAt}
      />
    );

    await act(async () => {
      jest.advanceTimersByTime(FIVE_MINUTES_MS + 100);
      await Promise.resolve();
    });

    const timeoutCalls = mockTrackEvent.mock.calls.filter(
      (c: unknown[]) => c[0] === "email_verification_timeout"
    );
    expect(timeoutCalls).toHaveLength(1);
    const payload = timeoutCalls[0][1] as Record<string, unknown>;
    expect(payload.email_domain).toBe("acme.com");
  });

  it("fires email_verification_timeout only ONCE (not twice)", async () => {
    const startedAt = Date.now();
    render(
      <SignupSuccess
        {...DEFAULT_PROPS}
        signupStartedAt={startedAt}
      />
    );

    // Advance twice past 5 minutes
    await act(async () => {
      jest.advanceTimersByTime(FIVE_MINUTES_MS + 100);
      await Promise.resolve();
    });
    await act(async () => {
      jest.advanceTimersByTime(FIVE_MINUTES_MS);
      await Promise.resolve();
    });

    const timeoutCalls = mockTrackEvent.mock.calls.filter(
      (c: unknown[]) => c[0] === "email_verification_timeout"
    );
    expect(timeoutCalls).toHaveLength(1); // timeoutFiredRef prevents double-fire
  });

  it("does NOT fire timeout if email is confirmed before 5 minutes", async () => {
    const { rerender } = render(
      <SignupSuccess
        {...DEFAULT_PROPS}
        signupStartedAt={Date.now()}
        isConfirmed={false}
      />
    );

    // Confirm at 3 minutes
    act(() => {
      jest.advanceTimersByTime(3 * 60 * 1000);
    });

    rerender(
      <SignupSuccess
        {...DEFAULT_PROPS}
        signupStartedAt={Date.now() - 3 * 60 * 1000}
        isConfirmed={true}
      />
    );

    await act(async () => {
      jest.advanceTimersByTime(3 * 60 * 1000); // advance past original 5min
      await Promise.resolve();
    });

    const timeoutCalls = mockTrackEvent.mock.calls.filter(
      (c: unknown[]) => c[0] === "email_verification_timeout"
    );
    expect(timeoutCalls).toHaveLength(0);
    expect(screen.queryByTestId("email-dead-end-modal")).not.toBeInTheDocument();
  });

  it("modal has 3 actions: check spam, resend, support link", async () => {
    const startedAt = Date.now();
    render(
      <SignupSuccess
        {...DEFAULT_PROPS}
        signupStartedAt={startedAt}
      />
    );

    await act(async () => {
      jest.advanceTimersByTime(FIVE_MINUTES_MS + 100);
      await Promise.resolve();
    });

    expect(screen.getByTestId("email-dead-end-modal")).toBeInTheDocument();
    // (a) Verificar SPAM
    expect(screen.getByTestId("dead-end-check-spam")).toBeInTheDocument();
    // (b) Reenviar email
    expect(screen.getByTestId("dead-end-resend")).toBeInTheDocument();
    // (c) Falar com suporte
    const supportLink = screen.getByTestId("dead-end-support");
    expect(supportLink).toBeInTheDocument();
    expect(supportLink).toHaveAttribute("href", "mailto:tiago@smartlic.tech");
  });

  it("modal closes on ESC key", async () => {
    const startedAt = Date.now();
    render(
      <SignupSuccess
        {...DEFAULT_PROPS}
        signupStartedAt={startedAt}
      />
    );

    await act(async () => {
      jest.advanceTimersByTime(FIVE_MINUTES_MS + 100);
      await Promise.resolve();
    });

    expect(screen.getByTestId("email-dead-end-modal")).toBeInTheDocument();

    await act(async () => {
      const event = new KeyboardEvent("keydown", { key: "Escape", bubbles: true });
      document.dispatchEvent(event);
      await Promise.resolve();
    });

    expect(screen.queryByTestId("email-dead-end-modal")).not.toBeInTheDocument();
  });
});

describe("EmailDeadEndModal — accessibility", () => {
  it("has role=dialog and aria-modal attributes", async () => {
    const startedAt = Date.now();
    render(
      <SignupSuccess
        {...DEFAULT_PROPS}
        signupStartedAt={startedAt}
      />
    );

    await act(async () => {
      jest.advanceTimersByTime(FIVE_MINUTES_MS + 100);
      await Promise.resolve();
    });

    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveAttribute("aria-modal", "true");
  });
});
