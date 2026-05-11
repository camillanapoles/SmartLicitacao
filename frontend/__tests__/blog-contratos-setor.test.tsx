/**
 * Tests for /blog/contratos/[setor] page (Wave 3.1)
 */
import React from 'react';

// Mock next/navigation
jest.mock('next/navigation', () => ({
  notFound: jest.fn(),
  useRouter: () => ({ push: jest.fn(), back: jest.fn() }),
  usePathname: () => '/blog/contratos/informatica',
}));

jest.mock('@/app/components/landing/LandingNavbar', () => () => <nav data-testid="navbar" />);
jest.mock('@/app/components/Footer', () => () => <footer data-testid="footer" />);
jest.mock('@/components/blog/SchemaMarkup', () => () => <div data-testid="schema-markup" />);
jest.mock('@/components/blog/BlogCTA', () => () => <div data-testid="blog-cta" />);
jest.mock('@/components/blog/RelatedPages', () => () => <div data-testid="related-pages" />);

describe('ContratosSetorPillarPage', () => {
  it('exports revalidate = 3600', async () => {
    const mod = await import('@/app/blog/contratos/[setor]/page');
    expect(mod.revalidate).toBe(3600);
  });

  it('generateStaticParams returns 15 sectors', async () => {
    const mod = await import('@/app/blog/contratos/[setor]/page');
    const params = mod.generateStaticParams();
    expect(params.length).toBe(15);
    expect(params[0]).toHaveProperty('setor');
  });

  it('generateMetadata returns correct title for valid sector', async () => {
    const mockStats = {
      sector_id: 'informatica',
      sector_name: 'Informatica',
      total_contracts: 100,
      total_value: 10000000,
      avg_value: 100000,
      top_orgaos: [],
      top_fornecedores: [],
      monthly_trend: [],
      by_uf: [],
      last_updated: '2026-04-08T12:00:00Z',
    };

    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockStats),
    }) as jest.Mock;

    const mod = await import('@/app/blog/contratos/[setor]/page');
    const metadata = await mod.generateMetadata({
      params: Promise.resolve({ setor: 'informatica' }),
    });

    expect(metadata.title).toContain('Contratos');
    expect(metadata.title).toContain('Panorama Nacional');
  });

  it('generateMetadata returns empty for invalid sector', async () => {
    const mod = await import('@/app/blog/contratos/[setor]/page');
    const metadata = await mod.generateMetadata({
      params: Promise.resolve({ setor: 'nonexistent' }),
    });

    expect(metadata.title).toContain('nao encontrado');
  });
});

describe('programmatic.ts extensions', () => {
  it('fetchContratosSetorStats is exported', async () => {
    const mod = await import('@/lib/programmatic');
    expect(typeof mod.fetchContratosSetorStats).toBe('function');
  });

  it('generateContratosSetorFAQs returns 5 FAQs', async () => {
    const mod = await import('@/lib/programmatic');
    const faqs = mod.generateContratosSetorFAQs('Informatica', 100, 'Min Educacao');
    expect(faqs.length).toBe(5);
    expect(faqs[0]).toHaveProperty('question');
    expect(faqs[0]).toHaveProperty('answer');
  });

  it('getContratosEditorialContent returns non-empty string', async () => {
    const mod = await import('@/lib/programmatic');
    const content = mod.getContratosEditorialContent('informatica');
    expect(content.length).toBeGreaterThan(100);
  });

  it('getContratosEditorialContent returns fallback for unknown sector', async () => {
    const mod = await import('@/lib/programmatic');
    const content = mod.getContratosEditorialContent('nonexistent');
    expect(content.length).toBeGreaterThan(50);
  });
});
