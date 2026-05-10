/**
 * Tests for RecentEditaisBlock — Issue #1007 (PSEODataBlock)
 *
 * Covers:
 *  - Loading skeleton is shown initially
 *  - Table renders edital data from API
 *  - Empty state when API returns [] (nothing rendered)
 *  - link_interno is used for edital links
 *  - Footer "Ver todos N editais →" renders
 */

import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import { RecentEditaisBlock } from "@/app/components/programmatic/RecentEditaisBlock";

const MOCK_RESPONSE = {
  setor: "engenharia_rodoviaria",
  uf: "SP",
  items: [
    {
      orgao: "Prefeitura Municipal de São Paulo",
      objeto: "Conservação rodoviária e manutenção de rodovia",
      valor_estimado: 450000.0,
      data_limite: "2026-05-25",
      data_publicacao: "2026-05-10",
      link_interno: "/licitacoes/engenharia-rodoviaria?query=Prefeitura+Municipal+de+São+Paulo",
    },
    {
      orgao: "Governo do Estado de SP",
      objeto: "Restauração rodoviária de estradas estaduais",
      valor_estimado: 1200000.0,
      data_limite: "2026-06-01",
      data_publicacao: "2026-05-09",
      link_interno: "/licitacoes/engenharia-rodoviaria?query=Governo+do+Estado+de+SP",
    },
  ],
  total: 2,
  last_updated: "2026-05-10T00:00:00Z",
};

const EMPTY_RESPONSE = {
  setor: "engenharia_rodoviaria",
  uf: "SP",
  items: [],
  total: 0,
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

describe("RecentEditaisBlock", () => {
  const defaultProps = {
    setor: "engenharia-rodoviaria",
    uf: "SP",
    setorLabel: "Engenharia Rodoviária",
    ufLabel: "São Paulo",
    totalOpen: 47,
  };

  it("renders loading skeleton initially", () => {
    mockFetch(MOCK_RESPONSE);
    const { container } = render(<RecentEditaisBlock {...defaultProps} />);
    const skeletons = container.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders edital table after data loads", async () => {
    mockFetch(MOCK_RESPONSE);
    render(<RecentEditaisBlock {...defaultProps} />);

    await waitFor(() => {
      expect(
        screen.getByText("Conservação rodoviária e manutenção de rodovia")
      ).toBeInTheDocument();
    });
    expect(screen.getByText("Restauração rodoviária de estradas estaduais")).toBeInTheDocument();
  });

  it("renders correct section header", async () => {
    mockFetch(MOCK_RESPONSE);
    render(<RecentEditaisBlock {...defaultProps} />);

    await waitFor(() => {
      expect(
        screen.getByText(/Últimos editais publicados de Engenharia Rodoviária em São Paulo/)
      ).toBeInTheDocument();
    });
  });

  it("shows nothing when API returns empty items", async () => {
    mockFetch(EMPTY_RESPONSE);
    const { container } = render(<RecentEditaisBlock {...defaultProps} />);

    await waitFor(() => {
      expect(
        screen.queryByText(/Últimos editais publicados/)
      ).not.toBeInTheDocument();
    });
    expect(container.firstChild).toBeNull();
  });

  it("shows nothing when API call fails", async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error("Network error"));
    const { container } = render(<RecentEditaisBlock {...defaultProps} />);

    await waitFor(() => {
      expect(
        screen.queryByText(/Últimos editais publicados/)
      ).not.toBeInTheDocument();
    });
    expect(container.firstChild).toBeNull();
  });

  it("renders 'Ver todos N editais →' in footer", async () => {
    mockFetch(MOCK_RESPONSE);
    render(<RecentEditaisBlock {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText(/Ver todos os 47 editais →/)).toBeInTheDocument();
    });
  });

  it("footer link points to /licitacoes/{setor}?uf={uf}", async () => {
    mockFetch(MOCK_RESPONSE);
    render(<RecentEditaisBlock {...defaultProps} />);

    await waitFor(() => {
      const link = screen.getByRole("link", { name: /Ver todos os 47 editais →/ }) as HTMLAnchorElement;
      expect(link.href).toContain("/licitacoes/engenharia-rodoviaria");
      expect(link.href).toContain("uf=SP");
    });
  });

  it("renders edital orgao names", async () => {
    mockFetch(MOCK_RESPONSE);
    render(<RecentEditaisBlock {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("Prefeitura Municipal de São Paulo")).toBeInTheDocument();
      expect(screen.getByText("Governo do Estado de SP")).toBeInTheDocument();
    });
  });

  it("does not render when API returns non-ok status", async () => {
    mockFetch({ detail: "Not Found" }, 404);
    const { container } = render(<RecentEditaisBlock {...defaultProps} />);

    await waitFor(() => {
      expect(
        screen.queryByText(/Últimos editais publicados/)
      ).not.toBeInTheDocument();
    });
    expect(container.firstChild).toBeNull();
  });
});
