/**
 * CONV-INST-003 AC1+AC8: SignupSuccess component instrumentation tests.
 *
 * AC1: email_verification_pending fires ONCE on mount (useRef gate).
 * AC8: Required test as per story acceptance criteria.
 *
 * Pattern: render <SignupSuccess> with mocked useAnalytics, assert event fired exactly once.
 */
/** @jest-environment jsdom */
import React from "react";
import { render, screen, act } from "@testing-library/react";

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockTrackEvent = jest.fn();
jest.mock("../../hooks/useAnalytics", () => ({
  useAnalytics: () => ({ trackEvent: mockTrackEvent }),
}));

// next/link: render as <a> to avoid router context requirement
jest.mock("next/link", () => {
  const MockLink = ({ href, children, ...rest }: { href: string; children: React.ReactNode; [k: string]: unknown }) => (
    <a href={href} {...rest}>{children}</a>
  );
  MockLink.displayName = "MockLink";
  return MockLink;
});

// EmailDeadEndModal: stub so we don't need to test its internals here
jest.mock("../../app/signup/components/EmailDeadEndModal", () => ({
  EmailDeadEndModal: ({ onClose }: { onClose: () => void }) => (
    <div data-testid="email-dead-end-modal">
      <button onClick={onClose}>Close</button>
    </div>
  ),
}));

import { SignupSuccess } from "../../app/signup/components/SignupSuccess";

// ── Helpers ───────────────────────────────────────────────────────────────────

function renderSuccess(overrides: Partial<Parameters<typeof SignupSuccess>[0]> = {}) {
  const defaults = {
    email: "test@example.com",
    isConfirmed: false,
    countdown: 60,
    isResending: false,
    onResend: jest.fn(),
    onChangeEmail: jest.fn(),
    signupStartedAt: Date.now(),
    rolloutBranch: "legacy",
  };
  return render(<SignupSuccess {...defaults} {...overrides} />);
}

// ── Tests ─────────────────────────────────────────────────────────────────────

beforeEach(() => {
  jest.clearAllMocks();
  jest.useFakeTimers();
});

afterEach(() => {
  jest.runOnlyPendingTimers();
  jest.useRealTimers();
});

describe("SignupSuccess — AC1: email_verification_pending", () => {
  it("fires email_verification_pending ONCE on mount", () => {
    renderSuccess();

    const calls = mockTrackEvent.mock.calls.filter(
      (c: unknown[]) => c[0] === "email_verification_pending"
    );
    expect(calls).toHaveLength(1);
  });

  it("includes email_domain (not full email) in payload — LGPD compliance", () => {
    renderSuccess({ email: "user@smartlic.tech", rolloutBranch: "legacy" });

    const call = mockTrackEvent.mock.calls.find(
      (c: unknown[]) => c[0] === "email_verification_pending"
    );
    expect(call).toBeDefined();
    const payload = call![1] as Record<string, unknown>;
    expect(payload.email_domain).toBe("smartlic.tech");
    // Must NOT contain the full email
    expect(JSON.stringify(payload)).not.toContain("user@smartlic.tech");
  });

  it("includes rollout_branch and signup_method in payload", () => {
    renderSuccess({ rolloutBranch: "card" });

    const call = mockTrackEvent.mock.calls.find(
      (c: unknown[]) => c[0] === "email_verification_pending"
    );
    expect(call).toBeDefined();
    const payload = call![1] as Record<string, unknown>;
    expect(payload.rollout_branch).toBe("card");
    expect(payload.signup_method).toBe("email");
  });

  it("does NOT fire email_verification_pending twice on re-render", () => {
    const { rerender } = renderSuccess({ countdown: 60 });
    rerender(
      <SignupSuccess
        email="test@example.com"
        isConfirmed={false}
        countdown={59}
        isResending={false}
        onResend={jest.fn()}
        onChangeEmail={jest.fn()}
        signupStartedAt={Date.now()}
        rolloutBranch="legacy"
      />
    );

    const pendingCalls = mockTrackEvent.mock.calls.filter(
      (c: unknown[]) => c[0] === "email_verification_pending"
    );
    expect(pendingCalls).toHaveLength(1); // Still exactly 1 — useRef gate works
  });

  it("shows mail icon and polling indicator when not confirmed", () => {
    renderSuccess();
    expect(screen.getByTestId("mail-icon")).toBeInTheDocument();
    expect(screen.getByTestId("polling-indicator")).toBeInTheDocument();
  });

  it("shows confirmed icon when isConfirmed=true", () => {
    renderSuccess({ isConfirmed: true });
    expect(screen.getByTestId("confirmed-icon")).toBeInTheDocument();
  });
});

describe("SignupSuccess — confirmed state does not fire pending", () => {
  it("still fires pending when isConfirmed=true (mount is before confirmation UI change)", () => {
    renderSuccess({ isConfirmed: true });
    // The pending event fires on mount regardless of isConfirmed
    // (component was just mounted after signup, regardless of polling state)
    const pendingCalls = mockTrackEvent.mock.calls.filter(
      (c: unknown[]) => c[0] === "email_verification_pending"
    );
    expect(pendingCalls).toHaveLength(1);
  });
});
