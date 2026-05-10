/**
 * Issue #1008 (COPY-HALL-009) — tests for the Hall of Founders opt-in toggle.
 *
 * Coverage:
 * - Render disabled state for non-founders.
 * - Toggle ON triggers POST /api/founders-hall/consent and shows toast.
 * - Toggle OFF triggers POST with consent=false.
 * - Network failure reverts the local toggle state.
 */
import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock UserContext (session)
const mockUseUser = jest.fn();
jest.mock("../contexts/UserContext", () => ({
  useUser: () => mockUseUser(),
}));

// Mock next/link
jest.mock("next/link", () => {
  const MockLink = ({
    href,
    children,
    ...props
  }: {
    href: string;
    children: React.ReactNode;
    [k: string]: unknown;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  );
  MockLink.displayName = "MockLink";
  return MockLink;
});

// Mock sonner
const mockToastSuccess = jest.fn();
const mockToastError = jest.fn();
jest.mock("sonner", () => ({
  toast: { success: (...a: unknown[]) => mockToastSuccess(...a), error: (...a: unknown[]) => mockToastError(...a) },
}));

import HallOfFoundersConsent from "../app/conta/perfil/HallOfFoundersConsent";

describe("HallOfFoundersConsent", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUseUser.mockReturnValue({ session: { access_token: "tok-123" } });
    global.fetch = jest.fn();
  });

  it("renders disabled state when user is not a founder", () => {
    render(<HallOfFoundersConsent isFounder={false} />);
    expect(screen.getByText(/Disponível apenas para Fundadores/i)).toBeInTheDocument();
    const checkbox = screen.getByRole("checkbox") as HTMLInputElement;
    expect(checkbox.disabled).toBe(true);
  });

  it("opt-in: posts consent=true and shows success toast", async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ consent: true, display_name: "", logo_url: "" }),
    });

    render(<HallOfFoundersConsent isFounder={true} />);
    const checkbox = screen.getByRole("checkbox") as HTMLInputElement;
    fireEvent.click(checkbox);

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toBe("/api/founders-hall/consent");
    expect(init.method).toBe("POST");
    const body = JSON.parse(init.body);
    expect(body.consent).toBe(true);
    await waitFor(() => expect(mockToastSuccess).toHaveBeenCalled());
  });

  it("opt-out: posts consent=false from initialConsent=true", async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ consent: false }),
    });

    render(<HallOfFoundersConsent isFounder={true} initialConsent={true} />);
    const checkbox = screen.getByRole("checkbox") as HTMLInputElement;
    expect(checkbox.checked).toBe(true);
    fireEvent.click(checkbox);

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
    const [, init] = (global.fetch as jest.Mock).mock.calls[0];
    const body = JSON.parse(init.body);
    expect(body.consent).toBe(false);
  });

  it("reverts toggle when backend returns non-OK", async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: false });

    render(<HallOfFoundersConsent isFounder={true} initialConsent={false} />);
    const checkbox = screen.getByRole("checkbox") as HTMLInputElement;
    fireEvent.click(checkbox);

    await waitFor(() => expect(mockToastError).toHaveBeenCalled());
    // After error, checkbox should reflect the original (false) state again.
    expect(checkbox.checked).toBe(false);
  });
});
