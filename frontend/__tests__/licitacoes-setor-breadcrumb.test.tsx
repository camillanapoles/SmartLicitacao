/**
 * Issue #662: Visual breadcrumb on /licitacoes/[setor].
 *
 * Asserts:
 * - <nav aria-label="Breadcrumb"> renders with 3 items
 * - aria-current="page" on last item
 * - Last item resolves to sector.name
 */

import React from 'react';
import { render, screen, within } from '@testing-library/react';

// RecentEditaisBlock and TopSuppliersBlock call fetch() in useEffect.
// jsdom does not ship with fetch — provide a no-op mock so the module
// loads without ReferenceError. Individual tests that care about data
// can override this mock locally.
global.fetch = jest.fn(() =>
  Promise.resolve({ ok: true, json: () => Promise.resolve([]) })
) as jest.Mock;


// Mock next/link
jest.mock('next/link', () => {
  return ({ children, href, ...props }: { children: React.ReactNode; href: string; [k: string]: unknown }) => (
    <a href={href} {...props}>
      {children}
    </a>
  );
});

// Mock next/navigation
jest.mock('next/navigation', () => ({
  notFound: jest.fn(),
}));

// Mock data dependencies
jest.mock('@/lib/sectors', () => ({
  getSectorBySlug: jest.fn(),
  getAllSectorSlugs: jest.fn(() => ['saude']),
  getRelatedSectors: jest.fn(() => []),
  fetchSectorStats: jest.fn(),
  formatBRL: jest.fn((v: number) => `R$ ${v}`),
  SECTORS: [],
}));
jest.mock('@/data/sector-faqs', () => ({ getSectorFaqs: jest.fn(() => []) }));
jest.mock('@/lib/seo', () => ({ getFreshnessLabel: jest.fn(() => 'Hoje') }));
jest.mock('@/components/seo/MicroDemo', () => ({ MicroDemo: () => null }));
jest.mock('@/components/seo/MicroDemoSchema', () => ({ MicroDemoSchema: () => null }));
jest.mock('@/lib/programmatic', () => ({ UF_NAMES: { SP: 'São Paulo' } }));

const { getSectorBySlug, fetchSectorStats, getRelatedSectors } = require('@/lib/sectors');
const { getSectorFaqs } = require('@/data/sector-faqs');
import SectorPage from '@/app/licitacoes/[setor]/page';

const MOCK_SECTOR = {
  id: 'saude',
  name: 'Saúde',
  slug: 'saude',
  description: 'Setor de saúde pública',
};

describe('/licitacoes/[setor] visual breadcrumb (#662)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    getSectorBySlug.mockReturnValue(MOCK_SECTOR);
    getSectorFaqs.mockReturnValue([]);
    getRelatedSectors.mockReturnValue([]);
    fetchSectorStats.mockResolvedValue({
      total_open: 10,
      total_value: 1_000_000,
      avg_value: 100_000,
      top_ufs: [{ name: 'SP', count: 5 }],
      sample_items: [],
      last_updated: '2026-05-04T12:00:00Z',
    });
  });

  it('renders <nav aria-label="Breadcrumb"> with exactly 3 visible items', async () => {
    const ui = await SectorPage({ params: Promise.resolve({ setor: 'saude' }) });
    render(ui as React.ReactElement);

    const nav = screen.getByRole('navigation', { name: /breadcrumb/i });
    expect(nav).toBeInTheDocument();

    // ol > li[content] (skip aria-hidden separators)
    const items = within(nav)
      .getAllByRole('listitem')
      .filter((li) => li.getAttribute('aria-hidden') !== 'true');
    expect(items).toHaveLength(3);

    expect(within(items[0]).getByRole('link', { name: /início/i })).toHaveAttribute('href', '/');
    expect(within(items[1]).getByRole('link', { name: /licitações/i })).toHaveAttribute('href', '/licitacoes');
    expect(items[2]).toHaveTextContent('Saúde');
  });

  it('marks last item with aria-current="page"', async () => {
    const ui = await SectorPage({ params: Promise.resolve({ setor: 'saude' }) });
    render(ui as React.ReactElement);

    const current = screen.getByText('Saúde', { selector: '[aria-current="page"]' });
    expect(current).toBeInTheDocument();
    expect(current.tagName.toLowerCase()).toBe('li');
  });
});
