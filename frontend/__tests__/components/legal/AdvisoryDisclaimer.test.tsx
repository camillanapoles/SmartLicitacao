import React from "react";
import { render, screen } from "@testing-library/react";
import { AdvisoryDisclaimer } from "@/components/legal/AdvisoryDisclaimer";

const DISCLAIMER_TEXT =
  "Recomendação algorítmica baseada em dados públicos. Não substitui análise jurídica, técnica ou comercial final.";

describe("AdvisoryDisclaimer", () => {
  it("renders disclaimer text in compact variant", () => {
    render(<AdvisoryDisclaimer variant="compact" />);
    const el = screen.getByTestId("advisory-disclaimer");
    expect(el).toBeInTheDocument();
    expect(el).toHaveTextContent(DISCLAIMER_TEXT);
  });

  it("renders disclaimer text in full variant", () => {
    render(<AdvisoryDisclaimer variant="full" />);
    const el = screen.getByTestId("advisory-disclaimer");
    expect(el).toBeInTheDocument();
    expect(el).toHaveTextContent(DISCLAIMER_TEXT);
  });

  it("defaults to compact when variant is not specified", () => {
    render(<AdvisoryDisclaimer />);
    const el = screen.getByTestId("advisory-disclaimer");
    expect(el).toBeInTheDocument();
    expect(el).toHaveTextContent(DISCLAIMER_TEXT);
    // compact uses text-zinc-500 without padding class
    expect(el.className).toContain("text-zinc-500");
    expect(el.className).not.toContain("p-3");
  });

  it("full variant includes padded card classes", () => {
    render(<AdvisoryDisclaimer variant="full" />);
    const el = screen.getByTestId("advisory-disclaimer");
    expect(el.className).toContain("p-3");
    expect(el.className).toContain("rounded");
    expect(el.className).toContain("bg-zinc-50");
  });
});
