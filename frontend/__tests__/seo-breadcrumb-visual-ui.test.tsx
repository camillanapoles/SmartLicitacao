/**
 * SEO-P1-007 (#993): Visual breadcrumb UI on SEO routes that previously emitted
 * BreadcrumbList JSON-LD only (no visible <nav>).
 *
 * Asserts that the shared `BreadcrumbNav` component (frontend/components/seo/BreadcrumbNav.tsx)
 * is wired into:
 *   - /casos/[slug]
 *   - /cnpj/[cnpj]            (via ContentPageLayout breadcrumbItems prop)
 *   - /orgaos/[slug]          (via ContentPageLayout breadcrumbItems prop)
 *
 * Verifies for each route:
 *   - <nav aria-label="Breadcrumb"> is rendered
 *   - Trail has the expected number of visible <li> items
 *   - Last item is non-link (current page) and marked with aria-current="page"
 *   - Inline JSON-LD BreadcrumbList script is emitted exactly once (no duplicate
 *     after we removed the bespoke breadcrumbSchema scripts)
 */

import React from 'react';
import { render, screen, within } from '@testing-library/react';

// --- Common mocks --------------------------------------------------------

jest.mock('next/link', () => {
  return ({
    children,
    href,
    ...props
  }: {
    children: React.ReactNode;
    href: string;
    [k: string]: unknown;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  );
});

jest.mock('next/navigation', () => ({
  notFound: jest.fn(),
}));

// Stub heavy / unrelated components so the page rendering stays focused on
// the breadcrumb wiring.
jest.mock('@/app/cnpj/[cnpj]/CnpjPerfilClient', () => ({
  __esModule: true,
  default: () => <div data-testid="cnpj-perfil-stub" />,
}));
jest.mock('@/app/cnpj/[cnpj]/IntelReportCTA', () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock('@/app/orgaos/[slug]/OrgaoPerfilClient', () => ({
  __esModule: true,
  default: () => <div data-testid="orgao-perfil-stub" />,
}));
jest.mock('@/app/components/InlineTrialCTA', () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock('@/components/LeadCapture', () => ({
  __esModule: true,
  LeadCapture: () => null,
}));
jest.mock('@/components/banners/FoundersRibbon', () => ({
  __esModule: true,
  FoundersRibbon: () => null,
}));
jest.mock('@/components/legal/AdvisoryDisclaimer', () => ({
  __esModule: true,
  AdvisoryDisclaimer: () => null,
}));
jest.mock('@/app/blog/components/BlogInlineCTA', () => ({
  __esModule: true,
  default: () => null,
}));

// Lightweight stubs for layout chrome (LandingNavbar/Footer pull in lots of deps).
jest.mock('@/app/components/landing/LandingNavbar', () => ({
  __esModule: true,
  default: () => <header data-testid="navbar-stub" />,
}));
jest.mock('@/app/components/Footer', () => ({
  __esModule: true,
  default: () => <footer data-testid="footer-stub" />,
}));

// --- Helpers --------------------------------------------------------------

function getBreadcrumbItems(container: HTMLElement) {
  const nav = within(container).getByRole('navigation', { name: /breadcrumb/i });
  const items = within(nav).getAllByRole('listitem');
  return { nav, items };
}

function findBreadcrumbJsonLd(container: HTMLElement) {
  const scripts = container.querySelectorAll<HTMLScriptElement>(
    'script[type="application/ld+json"]'
  );
  const matches: Array<Record<string, unknown>> = [];
  scripts.forEach((s) => {
    try {
      const parsed = JSON.parse(s.textContent || '');
      if (parsed && parsed['@type'] === 'BreadcrumbList') {
        matches.push(parsed);
      }
    } catch {
      // ignore non-JSON scripts
    }
  });
  return matches;
}

// --- /casos/[slug] --------------------------------------------------------

const CASE_FIXTURE = {
  slug: 'limpeza-sp-2025',
  title: 'Empresa de Limpeza dobra contratos públicos em 6 meses',
  description: 'Estudo de caso de empresa de limpeza em SP.',
  keywords: ['limpeza', 'SP'],
  publishDate: '2025-12-01',
  lastModified: '2026-01-15',
  company: 'Limpa Mais SA',
  companyProfile: 'PME do setor de limpeza com sede em SP.',
  sector: 'Limpeza e Conservação',
  sectorSlug: 'limpeza',
  uf: 'SP',
  problem: 'Falta de visibilidade sobre novos editais.',
  process: 'Implantou monitoramento automatizado.',
  result: 'Dobrou número de contratos.',
  metrics: {
    scoreMedio: 78,
    editaisAnalisados: 320,
    valorIdentificado: 'R$ 4,2M',
    tempoAnalise: '2 horas',
    reducaoTriagem: '85%',
    editaisPerdidosSemFiltro: 18,
  },
};

jest.mock('@/lib/cases', () => ({
  getAllCaseSlugs: jest.fn(() => ['limpeza-sp-2025']),
  getCaseBySlug: jest.fn(),
}));

describe('/casos/[slug] visual breadcrumb (#993)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    const { getCaseBySlug } = require('@/lib/cases');
    (getCaseBySlug as jest.Mock).mockReturnValue(CASE_FIXTURE);
  });

  it('renders <nav aria-label="Breadcrumb"> with 3 visible items', async () => {
    const CaseDetailPage = (await import('@/app/casos/[slug]/page')).default;
    const ui = await CaseDetailPage({
      params: Promise.resolve({ slug: 'limpeza-sp-2025' }),
    });
    const { container } = render(ui as React.ReactElement);

    const { items } = getBreadcrumbItems(container);
    expect(items).toHaveLength(3);
    expect(within(items[0]).getByRole('link', { name: /início/i })).toHaveAttribute(
      'href',
      'https://smartlic.tech'
    );
    expect(
      within(items[1]).getByRole('link', { name: /casos de sucesso/i })
    ).toHaveAttribute('href', 'https://smartlic.tech/casos');
    expect(items[2]).toHaveTextContent('Limpeza e Conservação');
  });

  it('marks last item with aria-current="page" and renders it as non-link', async () => {
    const CaseDetailPage = (await import('@/app/casos/[slug]/page')).default;
    const ui = await CaseDetailPage({
      params: Promise.resolve({ slug: 'limpeza-sp-2025' }),
    });
    const { container } = render(ui as React.ReactElement);

    const current = container.querySelector('[aria-current="page"]');
    expect(current).not.toBeNull();
    expect(current?.textContent).toContain('Limpeza e Conservação');
    // Last item must NOT be a link (it is the current page).
    const { items } = getBreadcrumbItems(container);
    expect(within(items[2]).queryByRole('link')).toBeNull();
  });

  it('emits exactly one BreadcrumbList JSON-LD (no duplicate from old inline script)', async () => {
    const CaseDetailPage = (await import('@/app/casos/[slug]/page')).default;
    const ui = await CaseDetailPage({
      params: Promise.resolve({ slug: 'limpeza-sp-2025' }),
    });
    const { container } = render(ui as React.ReactElement);

    const matches = findBreadcrumbJsonLd(container);
    expect(matches).toHaveLength(1);
    const items = matches[0].itemListElement as Array<Record<string, unknown>>;
    expect(items).toHaveLength(3);
    expect(items[items.length - 1].name).toBe('Limpeza e Conservação');
  });
});

// --- /cnpj/[cnpj] (via ContentPageLayout) --------------------------------

const CNPJ_PERFIL_FIXTURE = {
  empresa: {
    razao_social: 'ACME Indústria LTDA',
    cnpj: '12345678000199',
    cnae_principal: '4781-4/00',
    porte: 'EPP',
    uf: 'SP',
    situacao: 'ATIVA',
  },
  contratos: [],
  score: 'ATIVO',
  setor_detectado: 'vestuario',
  setor_nome: 'Vestuário e Têxtil',
  editais_abertos_setor: 0,
  editais_amostra: [],
  total_contratos_24m: 0,
  valor_total_24m: 0,
  ufs_atuacao: ['SP'],
  aviso_legal: 'Dados públicos.',
};

jest.mock('@/lib/safe-fetch', () => ({
  fetchWithBudget: jest.fn(),
}));
jest.mock('@/lib/backend-url', () => ({
  getBackendUrl: () => 'http://backend.local',
}));

describe('/cnpj/[cnpj] visual breadcrumb (#993)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    const { fetchWithBudget } = require('@/lib/safe-fetch');
    (fetchWithBudget as jest.Mock).mockResolvedValue(CNPJ_PERFIL_FIXTURE);
  });

  it('renders 3-level Breadcrumb with razao_social as current page', async () => {
    const CnpjPage = (await import('@/app/cnpj/[cnpj]/page')).default;
    const ui = await CnpjPage({
      params: Promise.resolve({ cnpj: '12345678000199' }),
    });
    const { container } = render(ui as React.ReactElement);

    const { items } = getBreadcrumbItems(container);
    expect(items).toHaveLength(3);
    expect(within(items[0]).getByRole('link', { name: /início/i })).toHaveAttribute(
      'href',
      'https://smartlic.tech'
    );
    expect(within(items[1]).getByRole('link', { name: /consulta cnpj/i })).toHaveAttribute(
      'href',
      'https://smartlic.tech/cnpj'
    );
    expect(items[2]).toHaveTextContent('ACME Indústria LTDA');
  });

  it('emits exactly one BreadcrumbList JSON-LD with 3 list items', async () => {
    const CnpjPage = (await import('@/app/cnpj/[cnpj]/page')).default;
    const ui = await CnpjPage({
      params: Promise.resolve({ cnpj: '12345678000199' }),
    });
    const { container } = render(ui as React.ReactElement);

    const matches = findBreadcrumbJsonLd(container);
    expect(matches).toHaveLength(1);
    expect((matches[0].itemListElement as Array<unknown>).length).toBe(3);
  });
});

// --- /orgaos/[slug] (via ContentPageLayout) ------------------------------

const ORGAO_STATS_FIXTURE = {
  nome: 'Prefeitura Municipal de Exemplo',
  cnpj: '12345678000100',
  esfera: 'municipal',
  uf: 'SP',
  municipio: 'Exemplo',
  total_licitacoes: 200,
  licitacoes_30d: 12,
  licitacoes_90d: 30,
  licitacoes_365d: 120,
  valor_medio_estimado: 50_000,
  valor_total_estimado: 10_000_000,
  top_modalidades: [],
  top_setores: [],
  ultimas_licitacoes: [],
  total_contratos_24m: 50,
  valor_total_contratos_24m: 5_000_000,
  aviso_legal: 'Dados públicos.',
};

describe('/orgaos/[slug] visual breadcrumb (#993)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    const { fetchWithBudget } = require('@/lib/safe-fetch');
    (fetchWithBudget as jest.Mock).mockResolvedValue(ORGAO_STATS_FIXTURE);
  });

  it('renders 3-level Breadcrumb with stats.nome as current page', async () => {
    const OrgaoPage = (await import('@/app/orgaos/[slug]/page')).default;
    const ui = await OrgaoPage({
      params: Promise.resolve({ slug: 'prefeitura-municipal-de-exemplo' }),
    });
    const { container } = render(ui as React.ReactElement);

    const { items } = getBreadcrumbItems(container);
    expect(items).toHaveLength(3);
    expect(within(items[0]).getByRole('link', { name: /início/i })).toHaveAttribute(
      'href',
      'https://smartlic.tech'
    );
    expect(
      within(items[1]).getByRole('link', { name: /órgãos compradores/i })
    ).toHaveAttribute('href', 'https://smartlic.tech/orgaos');
    expect(items[2]).toHaveTextContent('Prefeitura Municipal de Exemplo');
  });

  it('emits exactly one BreadcrumbList JSON-LD (no duplicate from old inline script)', async () => {
    const OrgaoPage = (await import('@/app/orgaos/[slug]/page')).default;
    const ui = await OrgaoPage({
      params: Promise.resolve({ slug: 'prefeitura-municipal-de-exemplo' }),
    });
    const { container } = render(ui as React.ReactElement);

    const matches = findBreadcrumbJsonLd(container);
    expect(matches).toHaveLength(1);
  });
});
