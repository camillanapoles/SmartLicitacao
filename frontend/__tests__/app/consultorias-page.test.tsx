/**
 * COPY-CONS-012 (#1010) — /consultorias page smoke + metadata tests.
 *
 * Verifies hero copy, white-label angle, pricing tier reference,
 * dual CTA and Schema.org Service JSON-LD. Server component, so we
 * mock the heavy navbar/footer islands.
 */

import { render, screen } from '@testing-library/react';

// Mock heavy layout islands (server-component children we don't need to render)
jest.mock('@/app/components/landing/LandingNavbar', () => ({
  __esModule: true,
  default: () => <nav data-testid="landing-navbar" />,
}));
jest.mock('@/app/components/Footer', () => ({
  __esModule: true,
  default: () => <footer data-testid="footer" />,
}));

import ConsultoriasPage, { metadata } from '@/app/consultorias/page';

describe('/consultorias — hero + white-label angle', () => {
  it('renders the hero headline targeting consultorias', () => {
    render(<ConsultoriasPage />);
    expect(
      screen.getByRole('heading', {
        level: 1,
        name: /atenda seus clientes B2G com inteligência sob seu logo/i,
      })
    ).toBeInTheDocument();
  });

  it('frames SmartLic as backbone and consultoria as relacionamento', () => {
    render(<ConsultoriasPage />);
    expect(screen.getByText(/Backbone tecnológico/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Relacionamento \+ expertise/i)
    ).toBeInTheDocument();
  });

  it('highlights the 5-user / 5.000-analyses / white-label features', () => {
    render(<ConsultoriasPage />);
    // White-label flag (logo on reports) must appear (AC requirement).
    expect(
      screen.getByText(
        /Logo da consultoria nos relatórios \(Excel \+ PDF\)/i
      )
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Até 5 usuários no mesmo workspace/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/5\.000 análises de licitação por mês/i)
    ).toBeInTheDocument();
  });

  it('shows the three target use-cases (assessor solo, advocacia, M&A)', () => {
    render(<ConsultoriasPage />);
    expect(
      screen.getByRole('heading', { name: /Assessor solo/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', {
        name: /Escritório de advocacia em licitações/i,
      })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: /Consultoria de M&A B2G/i })
    ).toBeInTheDocument();
  });

  it('shows transparent pricing for SmartLic Consultoria tier', () => {
    render(<ConsultoriasPage />);
    // R$ 997/mês is the canonical CONSULTORIA monthly price (multiple occurrences ok).
    expect(screen.getAllByText(/R\$ 997/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/cap 5 usuários/i)).toBeInTheDocument();
  });

  it('exposes both primary (consultive) and secondary (trial) CTAs', () => {
    render(<ConsultoriasPage />);
    // Primary: agendar conversa (consultive — multiple instances allowed)
    expect(
      screen.getAllByText(/Agendar conversa/i).length
    ).toBeGreaterThanOrEqual(1);
    // Secondary: trial
    expect(
      screen.getAllByText(/Testar 14 dias grátis/i).length
    ).toBeGreaterThanOrEqual(1);
  });

  it('does NOT include the Founders countdown / lifetime offer copy', () => {
    render(<ConsultoriasPage />);
    // Audience is distinct (consultorias, not B2G end-customers).
    expect(
      screen.queryByText(/acesso vitalício/i)
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Pare de perder licitações por falta/i)
    ).not.toBeInTheDocument();
  });

  it('includes a discreet cross-link to /fundadores in the footer area', () => {
    render(<ConsultoriasPage />);
    const fundadoresLink = screen
      .getAllByRole('link')
      .find((a) => a.getAttribute('href') === '/fundadores');
    expect(fundadoresLink).toBeDefined();
  });

  it('emits a Schema.org Service JSON-LD block', () => {
    const { container } = render(<ConsultoriasPage />);
    const ldScript = container.querySelector(
      'script[type="application/ld+json"]'
    );
    expect(ldScript).toBeTruthy();
    const parsed = JSON.parse(ldScript!.innerHTML);
    expect(parsed['@type']).toBe('Service');
    expect(parsed.name).toBe('SmartLic Consultoria');
    expect(parsed.offers.price).toBe(997);
    expect(parsed.offers.priceCurrency).toBe('BRL');
  });
});

describe('/consultorias — metadata', () => {
  it('exposes per-page canonical /consultorias (does not inherit root)', () => {
    expect(metadata.alternates?.canonical).toBe('/consultorias');
  });

  it('uses a white-label / B2B2G title', () => {
    expect(metadata.title).toMatch(/white-label/i);
  });

  it('description references white-label angle for consultorias', () => {
    expect(metadata.description).toMatch(/sob seu logo/i);
    expect(metadata.description).toMatch(/consultoria/i);
  });

  it('declares OpenGraph + Twitter card metadata for sharing', () => {
    expect(metadata.openGraph?.url).toBe('https://smartlic.tech/consultorias');
    expect(metadata.twitter?.card).toBe('summary_large_image');
  });
});
