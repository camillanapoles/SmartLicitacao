/**
 * Issue #786: FundadoresClient smoke tests
 *
 * Verifies the /fundadores page renders without crash and contains
 * the required CTA copy. Full interaction tests live in FundadoresForm.test.tsx.
 */

import { render, screen } from '@testing-library/react';
import FundadoresClient from '../../app/fundadores/FundadoresClient';

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
      screen.getByText(/Entre cedo na infraestrutura de inteligência B2G do SmartLic/i)
    ).toBeInTheDocument();
  });

  it('contains the CTA "Garantir acesso"', () => {
    render(<FundadoresClient />);
    // There are two FundadoresForm instances (hero + CTA final) — both should have the button
    const ctaButtons = screen.getAllByText(/Garantir acesso/i);
    expect(ctaButtons.length).toBeGreaterThanOrEqual(1);
  });

  it('contains sub-headline about vitalício access', () => {
    render(<FundadoresClient />);
    expect(
      screen.getByText(/Acesso vitalício antes da estrutura comercial definitiva/i)
    ).toBeInTheDocument();
  });

  it('contains "Menos PDF. Mais decisão." message', () => {
    render(<FundadoresClient />);
    expect(screen.getByText(/Menos PDF\. Mais decisão\./i)).toBeInTheDocument();
  });

  it('contains "A IA encontra. A inteligência decide." message', () => {
    render(<FundadoresClient />);
    expect(screen.getByText(/A IA encontra\. A inteligência decide\./i)).toBeInTheDocument();
  });

  it('contains "Ajude a financiar a próxima fase" message', () => {
    render(<FundadoresClient />);
    expect(screen.getByText(/Ajude a financiar a próxima fase do SmartLic/i)).toBeInTheDocument();
  });
});
