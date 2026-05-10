/**
 * Issue #1006 (COPY-CROSS-007): FoundersCrossSellBanner tests.
 *
 * Covers:
 *  - Variant 'planos': render with seats counter; non-dismissable when seats <= 10;
 *    dismissable persistence in localStorage; copy fidelity.
 *  - Variant 'dashboard': hidden when trial_day < 3; hidden when trial_day >= 12;
 *    rendered for 3..11; sessionStorage dismiss; 24h click anti-fatigue.
 *  - Common: hidden when isFounder; hidden when sold_out (seats=0);
 *    hidden when API returns available=false; fallback copy when API errors.
 */

import React from "react";
import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Stub framer-motion to a passthrough <div> + useReducedMotion
jest.mock("framer-motion", () => ({
  motion: { div: (props: React.HTMLAttributes<HTMLDivElement>) => <div {...props} /> },
  useReducedMotion: () => false,
}));

// Mock Mixpanel wrappers (verify they fire without external SDK)
const trackView = jest.fn();
const trackClick = jest.fn();
const trackDismiss = jest.fn();
jest.mock("../../lib/analytics/founders", () => ({
  trackFoundersBannerView: (p: unknown) => trackView(p),
  trackFoundersBannerClick: (p: unknown) => trackClick(p),
  trackFoundersBannerDismiss: (p: unknown) => trackDismiss(p),
}));

// Mock the SWR hook directly so we control availability state per test
const mockUseAvailability = jest.fn();
jest.mock("../../hooks/useFoundersAvailability", () => ({
  useFoundersAvailability: () => mockUseAvailability(),
}));

import { FoundersCrossSellBanner } from "../../app/components/FoundersCrossSellBanner";

const futureDeadline = "2099-06-30T23:59:59Z";

const dataAvailable = (seats: number) => ({
  data: { available: true, seats_remaining: seats, deadline_at: futureDeadline },
  isLoading: false,
  error: null,
});

const dataSoldOut = {
  data: { available: true, seats_remaining: 0, deadline_at: futureDeadline },
  isLoading: false,
  error: null,
};

const dataUnavailable = {
  data: { available: false, seats_remaining: 0, deadline_at: futureDeadline },
  isLoading: false,
  error: null,
};

const dataError = {
  data: null,
  isLoading: false,
  error: new Error("boom"),
};

const dataLoading = {
  data: null,
  isLoading: true,
  error: null,
};

beforeEach(() => {
  jest.clearAllMocks();
  localStorage.clear();
  sessionStorage.clear();
  mockUseAvailability.mockReset();
});

describe("FoundersCrossSellBanner — variant=planos", () => {
  it("renders with seats counter when API returns availability", () => {
    mockUseAvailability.mockReturnValue(dataAvailable(42));
    render(<FoundersCrossSellBanner variant="planos" />);
    const banner = screen.getByTestId("founders-cross-sell-banner-planos");
    expect(banner).toBeInTheDocument();
    expect(banner).toHaveTextContent(/42 vagas vitalícias por R\$997/);
    expect(banner).toHaveTextContent(/Encerra 30\/06/);
    expect(screen.getByTestId("founders-cross-sell-cta-planos")).toHaveTextContent(/Ver Plano Fundadores/);
  });

  it("hides dismiss button when seats <= 10 (real scarcity)", () => {
    mockUseAvailability.mockReturnValue(dataAvailable(8));
    render(<FoundersCrossSellBanner variant="planos" dismissable />);
    expect(screen.queryByTestId("founders-cross-sell-dismiss-planos")).not.toBeInTheDocument();
  });

  it("dismissable above scarcity threshold; click persists to localStorage", async () => {
    mockUseAvailability.mockReturnValue(dataAvailable(50));
    const user = userEvent.setup();
    const { rerender } = render(<FoundersCrossSellBanner variant="planos" dismissable />);
    const btn = screen.getByTestId("founders-cross-sell-dismiss-planos");
    await user.click(btn);
    expect(trackDismiss).toHaveBeenCalledWith({ route: "planos" });
    expect(localStorage.getItem("founders_cross_sell_planos_dismissed")).not.toBeNull();

    rerender(<FoundersCrossSellBanner variant="planos" dismissable />);
    expect(screen.queryByTestId("founders-cross-sell-banner-planos")).not.toBeInTheDocument();
  });

  it("hides when isFounder", () => {
    mockUseAvailability.mockReturnValue(dataAvailable(50));
    render(<FoundersCrossSellBanner variant="planos" isFounder />);
    expect(screen.queryByTestId("founders-cross-sell-banner-planos")).not.toBeInTheDocument();
  });

  it("hides when sold out (seats_remaining=0)", () => {
    mockUseAvailability.mockReturnValue(dataSoldOut);
    render(<FoundersCrossSellBanner variant="planos" />);
    expect(screen.queryByTestId("founders-cross-sell-banner-planos")).not.toBeInTheDocument();
  });

  it("hides when API returns available=false", () => {
    mockUseAvailability.mockReturnValue(dataUnavailable);
    render(<FoundersCrossSellBanner variant="planos" />);
    expect(screen.queryByTestId("founders-cross-sell-banner-planos")).not.toBeInTheDocument();
  });

  it("renders fallback copy without number when API errors", () => {
    mockUseAvailability.mockReturnValue(dataError);
    render(<FoundersCrossSellBanner variant="planos" />);
    const banner = screen.getByTestId("founders-cross-sell-banner-planos");
    expect(banner).toBeInTheDocument();
    expect(banner).toHaveTextContent(/vagas vitalícias por R\$997/);
    expect(banner).not.toHaveTextContent(/^\d+ vagas/); // no specific number in fallback
  });

  it("renders nothing while still loading and no data", () => {
    mockUseAvailability.mockReturnValue(dataLoading);
    const { container } = render(<FoundersCrossSellBanner variant="planos" />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("FoundersCrossSellBanner — variant=dashboard", () => {
  it.each([0, 1, 2])("hides when trial_day=%i (< 3)", (day) => {
    mockUseAvailability.mockReturnValue(dataAvailable(50));
    render(<FoundersCrossSellBanner variant="dashboard" trialDay={day} />);
    expect(screen.queryByTestId("founders-cross-sell-banner-dashboard")).not.toBeInTheDocument();
  });

  it.each([12, 13, 14])("hides when trial_day=%i (>= 12, urgent TrialProgressBar own)", (day) => {
    mockUseAvailability.mockReturnValue(dataAvailable(50));
    render(<FoundersCrossSellBanner variant="dashboard" trialDay={day} />);
    expect(screen.queryByTestId("founders-cross-sell-banner-dashboard")).not.toBeInTheDocument();
  });

  it.each([3, 7, 11])("renders for trial_day=%i (3..11) with CTA copy", (day) => {
    mockUseAvailability.mockReturnValue(dataAvailable(25));
    render(<FoundersCrossSellBanner variant="dashboard" trialDay={day} />);
    const banner = screen.getByTestId("founders-cross-sell-banner-dashboard");
    expect(banner).toHaveTextContent(/Já está vendo valor\?/);
    expect(banner).toHaveTextContent(/25 vagas restantes/);
    expect(screen.getByTestId("founders-cross-sell-cta-dashboard")).toHaveTextContent(/Pegar minha vaga R\$997/);
  });

  it("dismiss is session-scoped (sessionStorage), not localStorage", async () => {
    mockUseAvailability.mockReturnValue(dataAvailable(25));
    const user = userEvent.setup();
    render(<FoundersCrossSellBanner variant="dashboard" trialDay={5} dismissable />);
    await user.click(screen.getByTestId("founders-cross-sell-dismiss-dashboard"));
    expect(sessionStorage.getItem("founders_cross_sell_dashboard_dismissed_session")).toBe("1");
    expect(localStorage.getItem("founders_cross_sell_dashboard_dismissed_session")).toBeNull();
  });

  it("hides when 24h click anti-fatigue is active", () => {
    localStorage.setItem("founders_cross_sell_dashboard_clicked_at", String(Date.now()));
    mockUseAvailability.mockReturnValue(dataAvailable(25));
    render(<FoundersCrossSellBanner variant="dashboard" trialDay={5} />);
    expect(screen.queryByTestId("founders-cross-sell-banner-dashboard")).not.toBeInTheDocument();
  });

  it("CTA click writes 24h anti-fatigue timestamp + fires analytics", async () => {
    mockUseAvailability.mockReturnValue(dataAvailable(25));
    const user = userEvent.setup();
    render(<FoundersCrossSellBanner variant="dashboard" trialDay={5} />);
    await user.click(screen.getByTestId("founders-cross-sell-cta-dashboard"));
    expect(localStorage.getItem("founders_cross_sell_dashboard_clicked_at")).not.toBeNull();
    expect(trackClick).toHaveBeenCalledWith({ route: "dashboard" });
  });

  it("hides when isFounder", () => {
    mockUseAvailability.mockReturnValue(dataAvailable(25));
    render(<FoundersCrossSellBanner variant="dashboard" trialDay={5} isFounder />);
    expect(screen.queryByTestId("founders-cross-sell-banner-dashboard")).not.toBeInTheDocument();
  });

  it("renders fallback copy without number when API errors", () => {
    mockUseAvailability.mockReturnValue(dataError);
    render(<FoundersCrossSellBanner variant="dashboard" trialDay={5} />);
    const banner = screen.getByTestId("founders-cross-sell-banner-dashboard");
    expect(banner).toHaveTextContent(/Já está vendo valor\?/);
    expect(banner).not.toHaveTextContent(/\d+ vagas restantes/);
  });
});

describe("FoundersCrossSellBanner — analytics", () => {
  it("fires founders_banner_view once on mount when eligible", () => {
    mockUseAvailability.mockReturnValue(dataAvailable(50));
    render(<FoundersCrossSellBanner variant="planos" />);
    expect(trackView).toHaveBeenCalledWith({ route: "planos", dismissed_count: undefined });
  });

  it("does not fire view event when banner is hidden", () => {
    mockUseAvailability.mockReturnValue(dataSoldOut);
    render(<FoundersCrossSellBanner variant="planos" />);
    expect(trackView).not.toHaveBeenCalled();
  });
});

describe("FoundersCrossSellBanner — accessibility", () => {
  it("dismiss button has accessible name + min 44px tap target classes", () => {
    mockUseAvailability.mockReturnValue(dataAvailable(50));
    render(<FoundersCrossSellBanner variant="planos" dismissable />);
    const btn = screen.getByLabelText(/Fechar banner Plano Fundadores/);
    expect(btn).toHaveClass("min-w-[44px]");
    expect(btn).toHaveClass("min-h-[44px]");
  });

  it("CTA link has min 44px tap target", () => {
    mockUseAvailability.mockReturnValue(dataAvailable(50));
    render(<FoundersCrossSellBanner variant="planos" />);
    const cta = screen.getByTestId("founders-cross-sell-cta-planos");
    expect(cta).toHaveClass("min-h-[44px]");
  });
});
