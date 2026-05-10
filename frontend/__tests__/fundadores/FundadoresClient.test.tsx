/**
 * Issue #1000: FundadoresClient smoke tests
 *
 * Verifies the rewritten /fundadores page renders without crash and
 * contains the founder-letter / 60d guarantee / 4-question / "quem nao
 * deveria comprar" copy. Full interaction tests live in FundadoresForm.test.tsx.
 */

import { render, screen } from '@testing-library/react';
import FundadoresClient from '../../app/fundadores/FundadoresClient';

jest.mock('next/navigation', () => ({
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push: jest.fn(), replace: jest.fn(), back: jest.fn() }),
  usePathname: () => '/fundadores',
}));

// Suppress fetch errors from availability polling in tests
beforeEach(() => {
  (global.fetch as unknown as jest.Mock) = jest.fn().mockResolvedValue({
    ok: false,
    json: async () => ({}),
  });
});

describe('FundadoresClient', () => {
  it('renders without crashing', () => {
    render(<FundadoresClient />);
    expect(document.body).toBeTruthy();
  });

  it('contains the rewritten H1 "Pague R$997 uma vez. Use o SmartLic pra sempre."', () => {
    render(<FundadoresClient />);
    expect(
      screen.getByRole('heading', {
        level: 1,
        name: /pague r\$997 uma vez\. use o smartlic pra sempre\./i,
      })
    ).toBeInTheDocument();
  });

  it('renders the form CTA "Garantir acesso vitalício"', () => {
    render(<FundadoresClient />);
    const ctaButtons = screen.getAllByText(/Garantir acesso vitalício/i);
    expect(ctaButtons.length).toBeGreaterThanOrEqual(1);
  });

  it('mentions the 30/06/2026 deadline', () => {
    render(<FundadoresClient />);
    const matches = screen.getAllByText(/30\/06\/2026/);
    expect(matches.length).toBeGreaterThanOrEqual(1);
  });

  it('renders the founder letter section "Uma carta de quem fez isso"', () => {
    render(<FundadoresClient />);
    expect(
      screen.getByRole('heading', { name: /uma carta de quem fez isso/i })
    ).toBeInTheDocument();
  });

  it('renders the 60d guarantee section', () => {
    render(<FundadoresClient />);
    expect(
      screen.getByRole('heading', { name: /garantia incondicional de 60 dias/i })
    ).toBeInTheDocument();
  });

  it('renders the "Quem não deveria comprar" section', () => {
    render(<FundadoresClient />);
    expect(
      screen.getByRole('heading', { name: /quem não deveria comprar/i })
    ).toBeInTheDocument();
  });

  it('renders the "As 4 perguntas que todo mundo me faz" FAQ heading', () => {
    render(<FundadoresClient />);
    expect(
      screen.getByRole('heading', { name: /as 4 perguntas que todo mundo me faz/i })
    ).toBeInTheDocument();
  });

  it('renders the "A conta do uma vez vs todo mês" comparison table', () => {
    render(<FundadoresClient />);
    expect(
      screen.getByRole('heading', { name: /a conta do uma vez vs todo mês/i })
    ).toBeInTheDocument();
    // Spot-check the 5-year economy row
    expect(screen.getByText(/60 meses \(5 anos\)/i)).toBeInTheDocument();
  });

  it('renders the secondary "14 dias grátis" trial link to /planos', () => {
    render(<FundadoresClient />);
    const links = screen.getAllByRole('link', { name: /comece com 14 dias grátis/i });
    expect(links.length).toBeGreaterThanOrEqual(1);
    links.forEach((link) => {
      expect(link).toHaveAttribute('href', '/planos');
    });
  });

  it('exposes the personal email tiago@smartlic.tech for refund + contact', () => {
    render(<FundadoresClient />);
    const mailtos = screen.getAllByRole('link', { name: /tiago@smartlic\.tech/i });
    expect(mailtos.length).toBeGreaterThanOrEqual(1);
  });
});
