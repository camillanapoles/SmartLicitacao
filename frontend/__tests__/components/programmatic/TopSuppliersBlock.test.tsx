/**
 * Tests for TopSuppliersBlock — Issue #1007 (PSEODataBlock)
 *
 * Covers:
 *  - Loading skeleton is shown initially
 *  - Table renders supplier data from API
 *  - Empty state when API returns [] (nothing rendered)
 *  - CNPJ not present as visible text (LGPD compliance)
 *  - "Ver perfil →" link is present with href /cnpj/{cnpj}
 */

import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import { TopSuppliersBlock } from "@/app/components/programmatic/TopSuppliersBlock";

const MOCK_CNPJ = "12345678000100";
const MOCK_CNPJ_FORMATTED = "12.345.678/0001-00"; // formatted CNPJ — must NOT appear

const MOCK_RESPONSE = {
  setor: "engenharia_rodoviaria",
  uf: "SP",
  items: [
    {
      razao_social: "Construtora Alpha LTDA",
      cnpj: MOCK_CNPJ,
      contratos_count: 15,
      valor_total: 1500000.0,
    },
    {
      razao_social: "Rodovia Beta SA",
      cnpj: "22222222000122",
      contratos_count: 8,
      valor_total: 800000.0,
    },
  ],
  total_contracts_in_scope: 23,
  last_updated: "2026-05-10T00:00:00Z",
};

const EMPTY_RESPONSE = {
  setor: "engenharia_rodoviaria",
  uf: "SP",
  items: [],
  total_contracts_in_scope: 0,
  last_updated: "2026-05-10T00:00:00Z",
};

function mockFetch(response: object, status = 200) {
  global.fetch = jest.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => response,
  } as Response);
}

beforeEach(() => {
  jest.clearAllMocks();
});

describe("TopSuppliersBlock", () => {
  const defaultProps = {
    setor: "engenharia-rodoviaria",
    uf: "SP",
    setorLabel: "Engenharia Rodoviária",
    ufLabel: "São Paulo",
  };

  it("renders loading skeleton initially", () => {
    mockFetch(MOCK_RESPONSE);
    const { container } = render(<TopSuppliersBlock {...defaultProps} />);
    // Skeleton rows are rendered via animate-pulse divs
    const skeletons = container.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders supplier table after data loads", async () => {
    mockFetch(MOCK_RESPONSE);
    render(<TopSuppliersBlock {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("Construtora Alpha LTDA")).toBeInTheDocument();
    });
    expect(screen.getByText("Rodovia Beta SA")).toBeInTheDocument();
  });

  it("renders correct section header", async () => {
    mockFetch(MOCK_RESPONSE);
    render(<TopSuppliersBlock {...defaultProps} />);

    await waitFor(() => {
      expect(
        screen.getByText(/Quem ganha contratos de Engenharia Rodoviária em São Paulo/)
      ).toBeInTheDocument();
    });
  });

  it("shows nothing when API returns empty items", async () => {
    mockFetch(EMPTY_RESPONSE);
    const { container } = render(<TopSuppliersBlock {...defaultProps} />);

    await waitFor(() => {
      // No heading should be visible
      expect(
        screen.queryByText(/Quem ganha contratos/)
      ).not.toBeInTheDocument();
    });
    // Container should be essentially empty (null render)
    expect(container.firstChild).toBeNull();
  });

  it("shows nothing when API call fails", async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error("Network error"));
    const { container } = render(<TopSuppliersBlock {...defaultProps} />);

    await waitFor(() => {
      expect(screen.queryByText(/Quem ganha contratos/)).not.toBeInTheDocument();
    });
    expect(container.firstChild).toBeNull();
  });

  it("LGPD: CNPJ not visible as plain text in DOM", async () => {
    mockFetch(MOCK_RESPONSE);
    render(<TopSuppliersBlock {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("Construtora Alpha LTDA")).toBeInTheDocument();
    });

    // Raw CNPJ (14 digits) must not appear as text content
    expect(screen.queryByText(MOCK_CNPJ)).not.toBeInTheDocument();
    // Formatted CNPJ must not appear as text content
    expect(screen.queryByText(MOCK_CNPJ_FORMATTED)).not.toBeInTheDocument();
  });

  it("'Ver perfil →' link is present with href /cnpj/{cnpj}", async () => {
    mockFetch(MOCK_RESPONSE);
    render(<TopSuppliersBlock {...defaultProps} />);

    await waitFor(() => {
      const links = screen.getAllByRole("link", { name: /Ver perfil →/ });
      expect(links.length).toBeGreaterThan(0);
      // First supplier's link must reference the CNPJ in href (not as text)
      const firstLink = links[0] as HTMLAnchorElement;
      expect(firstLink.href).toContain(MOCK_CNPJ);
    });
  });

  it("renders CTA link to buscar", async () => {
    mockFetch(MOCK_RESPONSE);
    render(<TopSuppliersBlock {...defaultProps} />);

    await waitFor(() => {
      expect(
        screen.getByText(/Ver histórico completo de qualquer CNPJ concorrente/)
      ).toBeInTheDocument();
    });
  });

  it("does not render when API returns non-ok status", async () => {
    mockFetch({ detail: "Not Found" }, 404);
    const { container } = render(<TopSuppliersBlock {...defaultProps} />);

    await waitFor(() => {
      expect(screen.queryByText(/Quem ganha contratos/)).not.toBeInTheDocument();
    });
    expect(container.firstChild).toBeNull();
  });
});
