/**
 * #1011 UPGRADE-PATH-013: Tests for UpgradeToLifetimeModal — fetches preview,
 * shows pro-rata math, gates confirm button on eligibility, redirects to
 * Stripe checkout on success.
 */
import React from "react";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import "@testing-library/jest-dom";

jest.mock("sonner", () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

import { UpgradeToLifetimeModal } from "../../components/account/UpgradeToLifetimeModal";

describe("UpgradeToLifetimeModal", () => {
  const baseProps = {
    isOpen: true,
    onClose: jest.fn(),
    accessToken: "tk-test-001",
  };

  let originalLocation: Location;

  beforeAll(() => {
    originalLocation = window.location;
  });

  beforeEach(() => {
    jest.clearAllMocks();
    // jsdom: replace location to capture redirect
    Object.defineProperty(window, "location", {
      configurable: true,
      writable: true,
      value: { ...originalLocation, href: "" } as Location,
    });
  });

  afterAll(() => {
    Object.defineProperty(window, "location", {
      configurable: true,
      writable: true,
      value: originalLocation,
    });
  });

  it("renders preview and shows pro-rata math when eligible", async () => {
    global.fetch = jest.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        eligible: true,
        reason: "ok",
        lifetime_price_brl_cents: 99700,
        seats_remaining: 12,
        seats_total: 50,
        estimated_credit_brl_cents: 12000,
        net_charge_brl_cents: 87700,
        has_active_subscription: true,
        is_already_founder: false,
      }),
    });

    await act(async () => {
      render(<UpgradeToLifetimeModal {...baseProps} />);
    });

    await waitFor(() => {
      expect(screen.getByTestId("upgrade-preview")).toBeInTheDocument();
    });
    expect(screen.getByTestId("preview-net-charge")).toHaveTextContent("R$");
    // The component renders the confirm CTA with `data-testid="upgrade-confirm-btn"`.
    // (`preview-confirm-btn` was the originally proposed name in the spec but the
    // shipped UI uses `upgrade-confirm-btn`; either is acceptable for this assertion.)
    const confirmBtn =
      screen.queryByTestId("preview-confirm-btn") ??
      screen.getByTestId("upgrade-confirm-btn");
    expect(confirmBtn).toBeInTheDocument();
  });

  it("shows ineligible reason when already founder", async () => {
    global.fetch = jest.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        eligible: false,
        reason: "already_founder",
        lifetime_price_brl_cents: 99700,
        seats_remaining: 0,
        seats_total: 50,
        estimated_credit_brl_cents: 0,
        net_charge_brl_cents: 0,
        has_active_subscription: false,
        is_already_founder: true,
      }),
    });

    await act(async () => {
      render(<UpgradeToLifetimeModal {...baseProps} />);
    });

    await waitFor(() => {
      expect(screen.getByTestId("upgrade-not-eligible")).toBeInTheDocument();
    });
    expect(screen.getByTestId("upgrade-not-eligible")).toHaveTextContent(/já é fundador/i);
  });

  it("posts upgrade request and redirects to checkout on confirm", async () => {
    const fetchMock = jest
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          eligible: true,
          reason: "ok",
          lifetime_price_brl_cents: 99700,
          seats_remaining: 12,
          seats_total: 50,
          estimated_credit_brl_cents: 0,
          net_charge_brl_cents: 99700,
          has_active_subscription: true,
          is_already_founder: false,
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          checkout_url: "https://checkout.stripe.com/c/cs_test_99",
          session_id: "cs_test_99",
          estimated_credit_brl_cents: 0,
          net_charge_brl_cents: 99700,
        }),
      });
    global.fetch = fetchMock;

    await act(async () => {
      render(<UpgradeToLifetimeModal {...baseProps} />);
    });

    await waitFor(() => {
      expect(screen.getByTestId("upgrade-confirm-btn")).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.click(screen.getByTestId("upgrade-confirm-btn"));
    });

    await waitFor(() => {
      expect(window.location.href).toBe("https://checkout.stripe.com/c/cs_test_99");
    });

    // Second call uses POST method
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/subscriptions/upgrade-to-lifetime",
      expect.objectContaining({ method: "POST" }),
    );
  });
});
