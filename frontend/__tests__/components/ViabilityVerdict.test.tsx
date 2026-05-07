/**
 * ViabilityVerdict Component Tests — REPO-012 (#764)
 *
 * Coverage:
 * - score → label auto-mapping (PARTICIPAR / AVALIAR / NÃO RECOMENDADO)
 * - explicit label prop override
 * - disclaimer always present in full mode (non-removable per spec)
 * - compact mode: renders badge only (no reasons, no disclaimer)
 * - reasons: max 3 bullets rendered, 4th truncated
 * - score display format (X.X/10)
 * - named + default export
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import ViabilityVerdict, { ViabilityVerdict as ViabilityVerdictNamed } from "@/components/ViabilityVerdict";

// ─── Helpers ─────────────────────────────────────────────────────────────────

function getBadge() {
  return screen.getByTestId("viability-verdict-badge");
}

function getVerdict() {
  return screen.getByTestId("viability-verdict");
}

// ─── Score → Label Mapping ────────────────────────────────────────────────────

describe("score → label auto-mapping", () => {
  it("maps score >= 7 to PARTICIPAR (green)", () => {
    render(<ViabilityVerdict score={7} />);
    const badge = getBadge();
    expect(badge).toHaveAttribute("data-verdict", "PARTICIPAR");
    expect(badge.className).toContain("bg-green-100");
    expect(badge).toHaveTextContent("PARTICIPAR");
  });

  it("maps score === 7 boundary to PARTICIPAR", () => {
    render(<ViabilityVerdict score={7.0} />);
    expect(getBadge()).toHaveAttribute("data-verdict", "PARTICIPAR");
  });

  it("maps score 10 to PARTICIPAR", () => {
    render(<ViabilityVerdict score={10} />);
    expect(getBadge()).toHaveAttribute("data-verdict", "PARTICIPAR");
  });

  it("maps score >= 4 and < 7 to AVALIAR (amber)", () => {
    render(<ViabilityVerdict score={5} />);
    const badge = getBadge();
    expect(badge).toHaveAttribute("data-verdict", "AVALIAR");
    expect(badge.className).toContain("bg-amber-100");
    expect(badge).toHaveTextContent("AVALIAR");
  });

  it("maps score === 4 boundary to AVALIAR", () => {
    render(<ViabilityVerdict score={4.0} />);
    expect(getBadge()).toHaveAttribute("data-verdict", "AVALIAR");
  });

  it("maps score === 6.9 to AVALIAR", () => {
    render(<ViabilityVerdict score={6.9} />);
    expect(getBadge()).toHaveAttribute("data-verdict", "AVALIAR");
  });

  it("maps score < 4 to NÃO RECOMENDADO (red)", () => {
    render(<ViabilityVerdict score={3} />);
    const badge = getBadge();
    expect(badge).toHaveAttribute("data-verdict", "NÃO RECOMENDADO");
    expect(badge.className).toContain("bg-red-100");
    expect(badge).toHaveTextContent("NÃO RECOMENDADO");
  });

  it("maps score 0 to NÃO RECOMENDADO", () => {
    render(<ViabilityVerdict score={0} />);
    expect(getBadge()).toHaveAttribute("data-verdict", "NÃO RECOMENDADO");
  });

  it("maps score 3.9 to NÃO RECOMENDADO", () => {
    render(<ViabilityVerdict score={3.9} />);
    expect(getBadge()).toHaveAttribute("data-verdict", "NÃO RECOMENDADO");
  });
});

// ─── Explicit label override ──────────────────────────────────────────────────

describe("explicit label prop", () => {
  it("uses PARTICIPAR when label is explicitly passed regardless of score", () => {
    render(<ViabilityVerdict score={2} label="PARTICIPAR" />);
    expect(getBadge()).toHaveAttribute("data-verdict", "PARTICIPAR");
  });

  it("uses NÃO RECOMENDADO when label is explicitly passed regardless of score", () => {
    render(<ViabilityVerdict score={9} label="NÃO RECOMENDADO" />);
    expect(getBadge()).toHaveAttribute("data-verdict", "NÃO RECOMENDADO");
  });

  it("uses AVALIAR when label is explicitly passed", () => {
    render(<ViabilityVerdict score={9} label="AVALIAR" />);
    expect(getBadge()).toHaveAttribute("data-verdict", "AVALIAR");
  });
});

// ─── Score Display ────────────────────────────────────────────────────────────

describe("score display", () => {
  it("shows score as X.X/10 in badge", () => {
    render(<ViabilityVerdict score={7.5} />);
    expect(getBadge()).toHaveTextContent("7.5/10");
  });

  it("shows integer score without decimal when already round", () => {
    render(<ViabilityVerdict score={8} />);
    expect(getBadge()).toHaveTextContent("8/10");
  });

  it("rounds to 1 decimal place", () => {
    render(<ViabilityVerdict score={6.75} />);
    // Math.round(6.75 * 10)/10 = 6.8
    expect(getBadge()).toHaveTextContent("6.8/10");
  });
});

// ─── Disclaimer ───────────────────────────────────────────────────────────────

describe("disclaimer", () => {
  it("always renders disclaimer in full mode (non-removable per spec)", () => {
    render(<ViabilityVerdict score={5} />);
    const disclaimer = screen.getByTestId("viability-verdict-disclaimer");
    expect(disclaimer).toBeInTheDocument();
    expect(disclaimer).toHaveTextContent(
      "Recomendação algorítmica baseada em dados públicos. Não substitui análise jurídica, técnica ou comercial final."
    );
  });

  it("disclaimer has discrete text-xs text-zinc-500 styling", () => {
    render(<ViabilityVerdict score={5} />);
    const disclaimer = screen.getByTestId("viability-verdict-disclaimer");
    expect(disclaimer.className).toContain("text-xs");
    expect(disclaimer.className).toContain("text-zinc-500");
  });
});

// ─── Compact Mode ────────────────────────────────────────────────────────────

describe("compact mode", () => {
  it("renders badge in compact mode", () => {
    render(<ViabilityVerdict score={7.5} compact />);
    expect(getBadge()).toBeInTheDocument();
  });

  it("does NOT render reasons in compact mode", () => {
    render(
      <ViabilityVerdict
        score={7.5}
        compact
        reasons={["Modalidade favorável", "Valor compatível"]}
      />
    );
    expect(screen.queryByTestId("viability-verdict-reasons")).not.toBeInTheDocument();
  });

  it("does NOT render disclaimer in compact mode", () => {
    render(<ViabilityVerdict score={7.5} compact />);
    expect(screen.queryByTestId("viability-verdict-disclaimer")).not.toBeInTheDocument();
  });

  it("still shows correct label in compact mode", () => {
    render(<ViabilityVerdict score={3.2} compact />);
    expect(getBadge()).toHaveAttribute("data-verdict", "NÃO RECOMENDADO");
  });
});

// ─── Reasons ─────────────────────────────────────────────────────────────────

describe("reasons", () => {
  it("renders reasons when provided", () => {
    render(
      <ViabilityVerdict
        score={7}
        reasons={["Modalidade favorável", "Valor compatível"]}
      />
    );
    const list = screen.getByTestId("viability-verdict-reasons");
    expect(list).toBeInTheDocument();
    expect(list).toHaveTextContent("Modalidade favorável");
    expect(list).toHaveTextContent("Valor compatível");
  });

  it("renders at most 3 reasons when 4 are provided", () => {
    render(
      <ViabilityVerdict
        score={7}
        reasons={["R1", "R2", "R3", "R4"]}
      />
    );
    const list = screen.getByTestId("viability-verdict-reasons");
    const items = list.querySelectorAll("li");
    expect(items).toHaveLength(3);
    expect(list).not.toHaveTextContent("R4");
  });

  it("renders exactly 3 reasons when exactly 3 provided", () => {
    render(
      <ViabilityVerdict score={7} reasons={["R1", "R2", "R3"]} />
    );
    const items = screen.getByTestId("viability-verdict-reasons").querySelectorAll("li");
    expect(items).toHaveLength(3);
  });

  it("does NOT render reasons list when reasons is empty array", () => {
    render(<ViabilityVerdict score={7} reasons={[]} />);
    expect(screen.queryByTestId("viability-verdict-reasons")).not.toBeInTheDocument();
  });

  it("does NOT render reasons list when reasons is undefined", () => {
    render(<ViabilityVerdict score={7} />);
    expect(screen.queryByTestId("viability-verdict-reasons")).not.toBeInTheDocument();
  });
});

// ─── SVG Icon ────────────────────────────────────────────────────────────────

describe("icons", () => {
  it("renders an SVG icon in the badge for PARTICIPAR", () => {
    render(<ViabilityVerdict score={8} />);
    const badge = getBadge();
    expect(badge.querySelector("svg")).toBeInTheDocument();
  });

  it("renders an SVG icon in the badge for AVALIAR", () => {
    render(<ViabilityVerdict score={5} />);
    expect(getBadge().querySelector("svg")).toBeInTheDocument();
  });

  it("renders an SVG icon in the badge for NÃO RECOMENDADO", () => {
    render(<ViabilityVerdict score={2} />);
    expect(getBadge().querySelector("svg")).toBeInTheDocument();
  });
});

// ─── Exports ─────────────────────────────────────────────────────────────────

describe("exports", () => {
  it("named export ViabilityVerdict renders correctly", () => {
    render(<ViabilityVerdictNamed score={7} />);
    expect(getVerdict()).toBeInTheDocument();
  });

  it("default export renders correctly", () => {
    render(<ViabilityVerdict score={5} />);
    expect(getVerdict()).toBeInTheDocument();
  });
});
