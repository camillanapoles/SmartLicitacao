/**
 * Issue #657 — og:image dinâmica em 5 rotas pSEO
 *
 * Validates that generateMetadata() in the 5 affected programmatic SEO routes
 * exposes a route-specific openGraph.images entry pointing at /api/og?title=...
 * (instead of inheriting the generic site-wide OG image from layout.tsx).
 */

// next/navigation is referenced indirectly by some route imports; stub it out so
// importing the page module under jsdom does not pull Next runtime expectations.
jest.mock("next/navigation", () => ({
  notFound: jest.fn(),
}));

// LandingNavbar + Footer pull in client-only deps; a route's generateMetadata
// does not reach them, but the module-level imports do.
jest.mock("@/app/components/landing/LandingNavbar", () => () => null);
jest.mock("@/app/components/Footer", () => () => null);
jest.mock("@/components/LeadCapture", () => ({
  LeadCapture: () => null,
}));

// observatorio uses Sentry at module scope; keep it inert.
jest.mock("@sentry/nextjs", () => ({
  captureMessage: jest.fn(),
}));

type OGImageEntry = { url: string; width?: number; height?: number; alt?: string };

function firstImageUrl(metadata: { openGraph?: { images?: OGImageEntry[] | unknown } }): string {
  const images = metadata.openGraph?.images;
  expect(Array.isArray(images)).toBe(true);
  const arr = images as OGImageEntry[];
  expect(arr.length).toBeGreaterThan(0);
  const first = arr[0];
  expect(typeof first.url).toBe("string");
  return first.url;
}

function mockFetchOnce(payload: unknown, ok = true) {
  global.fetch = jest.fn().mockResolvedValue({
    ok,
    status: ok ? 200 : 404,
    json: () => Promise.resolve(payload),
  }) as jest.Mock;
}

describe("Issue #657 — og:image dinâmica em rotas pSEO", () => {
  // fetchAlertasPublicos / fetchSectorUfBlogStats short-circuit on missing BACKEND_URL.
  const ORIGINAL_BACKEND_URL = process.env.BACKEND_URL;
  beforeAll(() => {
    process.env.BACKEND_URL = "http://localhost:8000";
  });
  afterAll(() => {
    if (ORIGINAL_BACKEND_URL === undefined) delete process.env.BACKEND_URL;
    else process.env.BACKEND_URL = ORIGINAL_BACKEND_URL;
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("/municipios/[slug] gera /api/og?title= contextualizado", async () => {
    mockFetchOnce({
      slug: "sao-paulo-sp",
      nome: "São Paulo",
      uf: "SP",
      ibge_code: "3550308",
      populacao: 12000000,
      pib_per_capita: 50000,
      total_licitacoes_abertas: 42,
      valor_total_licitacoes: 1000000,
      licitacoes_recentes: [],
      faq_items: [],
      last_updated: "2026-05-04T00:00:00Z",
      aviso_legal: "ok",
    });

    const mod = await import("@/app/municipios/[slug]/page");
    const metadata = await mod.generateMetadata({
      params: Promise.resolve({ slug: "sao-paulo-sp" }),
    });

    const url = firstImageUrl(metadata);
    expect(url).toContain("/api/og?title=");
    expect(url).toContain(encodeURIComponent("São Paulo"));
  });

  it("/compliance/[cnpj] gera /api/og?title= com razao_social", async () => {
    mockFetchOnce({
      cnpj: "12345678000199",
      razao_social: "Empresa Teste LTDA",
      situacao_geral: "Sem registros",
      total_sancoes_ceis: 0,
      total_sancoes_cnep: 0,
      sancoes: [],
      fonte_dados: "Portal da Transparência",
      last_updated: "2026-05-04T00:00:00Z",
      aviso_legal: "ok",
    });

    const mod = await import("@/app/compliance/[cnpj]/page");
    const metadata = await mod.generateMetadata({
      params: Promise.resolve({ cnpj: "12345678000199" }),
    });

    const url = firstImageUrl(metadata);
    expect(url).toContain("/api/og?title=");
    expect(url).toContain(encodeURIComponent("Empresa Teste LTDA"));
  });

  it("/alertas-publicos/[setor]/[uf] gera /api/og?title= com setor + UF", async () => {
    // fetchAlertasPublicos uses fetch internally — return enough bids to clear MIN_ACTIVE_BIDS_FOR_INDEX
    mockFetchOnce({
      total: 10,
      bids: Array.from({ length: 10 }, (_, i) => ({ id: i })),
      last_updated: "2026-05-04T00:00:00Z",
    });

    const mod = await import("@/app/alertas-publicos/[setor]/[uf]/page");
    const metadata = await mod.generateMetadata({
      params: Promise.resolve({ setor: "informatica", uf: "sp" }),
    });

    const url = firstImageUrl(metadata);
    expect(url).toContain("/api/og?title=");
    expect(url).toContain(encodeURIComponent("Alertas:"));
  });

  it("/contratos/[setor]/[uf] gera /api/og?title= com setor + UF", async () => {
    // contratos route calls fetch twice (stats + blog stats); mock both.
    let callCount = 0;
    global.fetch = jest.fn().mockImplementation(() => {
      callCount += 1;
      if (callCount === 1) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () =>
            Promise.resolve({
              sector_id: "tecnologia",
              sector_name: "Tecnologia",
              uf: "SP",
              total_contracts: 100,
              total_value: 1000000,
              avg_value: 10000,
              top_orgaos: [],
              top_fornecedores: [],
              monthly_trend: [],
              sample_contracts: [],
              last_updated: "2026-05-04T00:00:00Z",
              aviso_legal: "ok",
            }),
        });
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ total_editais: 5 }),
      });
    }) as jest.Mock;

    const mod = await import("@/app/contratos/[setor]/[uf]/page");
    const metadata = await mod.generateMetadata({
      params: Promise.resolve({ setor: "informatica", uf: "sp" }),
    });

    const url = firstImageUrl(metadata);
    expect(url).toContain("/api/og?title=");
    expect(url).toContain(encodeURIComponent("Contratos Públicos"));
  });

  it("/observatorio/[slug] gera /api/og?title= com mês + ano", async () => {
    mockFetchOnce({
      total_editais: 1234,
      periodo: "abril-2026",
      por_uf: [],
      por_modalidade: [],
      por_setor: [],
    });

    const mod = await import("@/app/observatorio/[slug]/page");
    const metadata = await mod.generateMetadata({
      params: Promise.resolve({ slug: "raio-x-abril-2026" }),
    });

    const url = firstImageUrl(metadata);
    expect(url).toContain("/api/og?title=");
    expect(url).toContain(encodeURIComponent("Abril"));
  });
});
