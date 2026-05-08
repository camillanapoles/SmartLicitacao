/**
 * Issue #786: FundadoresClient smoke tests
 *
 * Verifies the /fundadores page renders without crash and contains
 * the required CTA copy. Full interaction tests live in FundadoresForm.test.tsx.
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

  it('contains the hero headline', () => {
    render(<FundadoresClient />);
    expect(
      screen.getByText(/Pare de perder licitações por falta de informação/i)
    ).toBeInTheDocument();
  });

  it('contains the CTA "Garantir acesso vitalício"', () => {
    render(<FundadoresClient />);
    const ctaButtons = screen.getAllByText(/Garantir acesso vitalício/i);
    expect(ctaButtons.length).toBeGreaterThanOrEqual(1);
  });

  it('contains urgency copy about encerra date', () => {
    render(<FundadoresClient />);
    const matches = screen.getAllByText(/Encerra 30\/06\/2026/i);
    expect(matches.length).toBeGreaterThanOrEqual(1);
  });

  it('contains comparison section headline', () => {
    render(<FundadoresClient />);
    expect(screen.getByText(/Fundador vs Assinatura recorrente/i)).toBeInTheDocument();
  });

  it('contains "Por que empresas B2G perdem licitações" section', () => {
    render(<FundadoresClient />);
    expect(screen.getByText(/Por que empresas B2G perdem licitações/i)).toBeInTheDocument();
  });

  it('contains "Ajude a financiar a próxima fase" message', () => {
    render(<FundadoresClient />);
    expect(screen.getByText(/Ajude a financiar a próxima fase do SmartLic/i)).toBeInTheDocument();
  });
});
