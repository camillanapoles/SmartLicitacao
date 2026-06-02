/**
 * CONV-018: SegmentForm component tests.
 *
 * Tests:
 *   - All 3 form steps render correct content
 *   - Step navigation (back/next) works
 *   - Sector autocomplete filters by search
 *   - UF multi-select toggles states
 *   - Objective radio group selects option
 *   - Submit button is disabled until all steps completed
 */

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SegmentForm } from "@/components/SegmentForm";

// Mock next/navigation
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

// Mock AuthProvider
const mockUseAuth = jest.fn();
jest.mock("@/app/components/AuthProvider", () => ({
  useAuth: () => mockUseAuth(),
}));

// Mock fetch globally
const mockFetch = jest.fn();
global.fetch = mockFetch;

describe("SegmentForm", () => {
  const mockSession = { access_token: "test-token" };

  beforeEach(() => {
    jest.clearAllMocks();
    mockUseAuth.mockReturnValue({ session: mockSession, user: { id: "test-user" } });
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ status: "ok", context_data: { segmento_principal: 1, objetivo_tipo: "vencer_licitacao" } }),
    });
  });

  // ── Step Rendering ─────────────────────────────────────────────────────

  it("renders step 1 (sector) by default", () => {
    render(<SegmentForm />);

    expect(screen.getByText("O que sua empresa vende?")).toBeInTheDocument();
    expect(screen.getByTestId("segment-sector-input")).toBeInTheDocument();
    expect(screen.getByTestId("segment-btn-continue")).toBeInTheDocument();
  });

  it("shows sector dropdown on input focus", async () => {
    render(<SegmentForm />);

    const input = screen.getByTestId("segment-sector-input");
    fireEvent.focus(input);

    await waitFor(() => {
      expect(screen.getByTestId("segment-sector-dropdown")).toBeInTheDocument();
    });
  });

  it("filters sectors by search text", async () => {
    render(<SegmentForm />);

    const input = screen.getByTestId("segment-sector-input");
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: "vestuário" } });

    await waitFor(() => {
      const options = screen.getAllByTestId(/segment-sector-option-/);
      expect(options.length).toBeGreaterThan(0);
      // All visible options should match the search
      options.forEach((opt) => {
        expect(opt.textContent?.toLowerCase()).toContain("vestuário");
      });
    });
  });

  it("selects a sector from the dropdown", async () => {
    render(<SegmentForm />);

    const input = screen.getByTestId("segment-sector-input");
    fireEvent.focus(input);

    await waitFor(() => {
      expect(screen.getByTestId("segment-sector-dropdown")).toBeInTheDocument();
    });

    // Click first sector option
    const firstOption = screen.getAllByTestId(/segment-sector-option-/)[0];
    fireEvent.mouseDown(firstOption);

    // After selection, the continue button should be enabled
    await waitFor(() => {
      expect(screen.getByTestId("segment-btn-continue")).not.toBeDisabled();
    });
  });

  // ── Step Navigation ────────────────────────────────────────────────────

  it("navigates to step 2 (UFs) after selecting a sector", async () => {
    render(<SegmentForm />);

    // Select a sector
    const input = screen.getByTestId("segment-sector-input");
    fireEvent.focus(input);
    const firstOption = screen.getAllByTestId(/segment-sector-option-/)[0];
    fireEvent.mouseDown(firstOption);

    // Click continue
    fireEvent.click(screen.getByTestId("segment-btn-continue"));

    await waitFor(() => {
      expect(screen.getByText("Onde sua empresa atua?")).toBeInTheDocument();
    });
  });

  it("shows step 3 (objective) after UF selection", async () => {
    render(<SegmentForm />);

    // Step 1: select sector
    const input = screen.getByTestId("segment-sector-input");
    fireEvent.focus(input);
    const firstOption = screen.getAllByTestId(/segment-sector-option-/)[0];
    fireEvent.mouseDown(firstOption);
    fireEvent.click(screen.getByTestId("segment-btn-continue"));

    // Step 2: select UF
    await waitFor(() => {
      expect(screen.getByText("Onde sua empresa atua?")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("segment-uf-SP"));
    fireEvent.click(screen.getByTestId("segment-btn-continue"));

    // Step 3: objective
    await waitFor(() => {
      expect(
        screen.getByText("Qual seu objetivo principal?"),
      ).toBeInTheDocument();
    });
  });

  it("back button returns to previous step", async () => {
    render(<SegmentForm />);

    // Go to step 2
    const input = screen.getByTestId("segment-sector-input");
    fireEvent.focus(input);
    const firstOption = screen.getAllByTestId(/segment-sector-option-/)[0];
    fireEvent.mouseDown(firstOption);
    fireEvent.click(screen.getByTestId("segment-btn-continue"));

    await waitFor(() => {
      expect(screen.getByTestId("segment-btn-back")).toBeInTheDocument();
    });

    // Go back
    fireEvent.click(screen.getByTestId("segment-btn-back"));

    await waitFor(() => {
      expect(screen.getByText("O que sua empresa vende?")).toBeInTheDocument();
    });
  });

  // ── UF Selection ───────────────────────────────────────────────────────

  it("toggles UF selection on click", async () => {
    render(<SegmentForm />);

    // Go to step 2
    const input = screen.getByTestId("segment-sector-input");
    fireEvent.focus(input);
    const firstOption = screen.getAllByTestId(/segment-sector-option-/)[0];
    fireEvent.mouseDown(firstOption);
    fireEvent.click(screen.getByTestId("segment-btn-continue"));

    await waitFor(() => {
      expect(screen.getByText("Onde sua empresa atua?")).toBeInTheDocument();
    });

    // Select SP
    const spBtn = screen.getByTestId("segment-uf-SP");
    fireEvent.click(spBtn);
    expect(spBtn).toHaveAttribute("aria-pressed", "true");

    // Deselect SP
    fireEvent.click(spBtn);
    expect(spBtn).toHaveAttribute("aria-pressed", "false");
  });

  it("select all UFs button works", async () => {
    render(<SegmentForm />);

    // Go to step 2
    const input = screen.getByTestId("segment-sector-input");
    fireEvent.focus(input);
    const firstOption = screen.getAllByTestId(/segment-sector-option-/)[0];
    fireEvent.mouseDown(firstOption);
    fireEvent.click(screen.getByTestId("segment-btn-continue"));

    await waitFor(() => {
      expect(screen.getByTestId("segment-select-all-ufs")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("segment-select-all-ufs"));

    // Continue button should be enabled (at least one UF selected)
    expect(screen.getByTestId("segment-btn-continue")).not.toBeDisabled();
  });

  // ── Objective Selection ────────────────────────────────────────────────

  it("selects objective via radio group", async () => {
    render(<SegmentForm />);

    // Step 1: select sector
    const input = screen.getByTestId("segment-sector-input");
    fireEvent.focus(input);
    const firstOption = screen.getAllByTestId(/segment-sector-option-/)[0];
    fireEvent.mouseDown(firstOption);
    fireEvent.click(screen.getByTestId("segment-btn-continue"));

    // Step 2: select UF
    await waitFor(() => {
      expect(screen.getByTestId("segment-uf-SP")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("segment-uf-SP"));
    fireEvent.click(screen.getByTestId("segment-btn-continue"));

    // Step 3: select objective
    await waitFor(() => {
      expect(
        screen.getByTestId("segment-objetivo-vencer_licitacao"),
      ).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("segment-objetivo-vencer_licitacao"));
    expect(
      screen.getByTestId("segment-objetivo-vencer_licitacao"),
    ).toHaveAttribute("aria-pressed", "true");
  });

  // ── Submission ─────────────────────────────────────────────────────────

  it("submits form data on completion", async () => {
    render(<SegmentForm />);

    // Step 1: select sector
    const input = screen.getByTestId("segment-sector-input");
    fireEvent.focus(input);
    const firstOption = screen.getAllByTestId(/segment-sector-option-/)[0];
    fireEvent.mouseDown(firstOption);
    fireEvent.click(screen.getByTestId("segment-btn-continue"));

    // Step 2: select UF
    await waitFor(() => {
      expect(screen.getByTestId("segment-uf-SP")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("segment-uf-SP"));
    fireEvent.click(screen.getByTestId("segment-btn-continue"));

    // Step 3: select objective and submit
    await waitFor(() => {
      expect(
        screen.getByTestId("segment-objetivo-vencer_licitacao"),
      ).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("segment-objetivo-vencer_licitacao"));

    const submitBtn = screen.getByTestId("segment-btn-continue");
    expect(submitBtn).not.toBeDisabled();
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith("/api/segment/save", {
        method: "POST",
        headers: {
          "Authorization": "Bearer test-token",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          segmento_principal: 1,
          objetivo_tipo: "vencer_licitacao",
        }),
      });
    });
  });

  it("continue button is disabled when no state selected", () => {
    render(<SegmentForm />);

    // Step 1: no sector selected yet
    expect(screen.getByTestId("segment-btn-continue")).toBeDisabled();
  });

  it("shows success state after submission", async () => {
    render(<SegmentForm />);

    // Complete all steps
    const input = screen.getByTestId("segment-sector-input");
    fireEvent.focus(input);
    const firstOption = screen.getAllByTestId(/segment-sector-option-/)[0];
    fireEvent.mouseDown(firstOption);
    fireEvent.click(screen.getByTestId("segment-btn-continue"));

    await waitFor(() => {
      expect(screen.getByTestId("segment-uf-SP")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("segment-uf-SP"));
    fireEvent.click(screen.getByTestId("segment-btn-continue"));

    await waitFor(() => {
      expect(
        screen.getByTestId("segment-objetivo-vencer_licitacao"),
      ).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("segment-objetivo-vencer_licitacao"));
    fireEvent.click(screen.getByTestId("segment-btn-continue"));

    await waitFor(() => {
      expect(
        screen.getByText("Segmentação salva com sucesso!"),
      ).toBeInTheDocument();
    });
  });

  // ── Pre-filled data ────────────────────────────────────────────────────

  it("pre-fills UFs when prefillUfs prop is provided", () => {
    render(<SegmentForm prefillUfs={["SP", "RJ"]} />);

    // Go to step 2
    const input = screen.getByTestId("segment-sector-input");
    fireEvent.focus(input);
    const firstOption = screen.getAllByTestId(/segment-sector-option-/)[0];
    fireEvent.mouseDown(firstOption);
    fireEvent.click(screen.getByTestId("segment-btn-continue"));

    // SP and RJ should be pre-selected
    const spBtn = screen.getByTestId("segment-uf-SP");
    expect(spBtn).toHaveAttribute("aria-pressed", "true");
  });
});
