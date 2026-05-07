import React from 'react';
import { render, screen } from '@testing-library/react';
import ThreeTiersSection from '@/app/components/landing/ThreeTiersSection';

jest.mock('@/lib/analytics-events', () => ({
  trackCTAClick: jest.fn(),
}));

describe('ThreeTiersSection', () => {
  it('renders three tier cards', () => {
    render(<ThreeTiersSection />);
    expect(screen.getByText('SmartLic SaaS')).toBeInTheDocument();
    expect(screen.getByText('Radar B2G')).toBeInTheDocument();
    expect(screen.getByText('Consultoria B2G')).toBeInTheDocument();
  });

  it('renders correct data-cta-tier attributes', () => {
    const { container } = render(<ThreeTiersSection />);
    expect(container.querySelector('[data-cta-tier="saas"]')).toBeTruthy();
    expect(container.querySelector('[data-cta-tier="radar"]')).toBeTruthy();
    expect(container.querySelector('[data-cta-tier="consultoria"]')).toBeTruthy();
  });

  it('renders SaaS CTA with correct href', () => {
    render(<ThreeTiersSection />);
    const link = screen.getByText('Testar plataforma').closest('a');
    expect(link?.getAttribute('href')).toBe('/signup?source=tier-saas');
  });

  it('renders Radar CTA with correct href', () => {
    render(<ThreeTiersSection />);
    const link = screen.getByText('Receber radar da minha empresa').closest('a');
    expect(link?.getAttribute('href')).toBe('/consultoria-b2g?modalidade=radar#diagnostico');
  });

  it('renders Consultoria CTA with correct href', () => {
    render(<ThreeTiersSection />);
    const link = screen.getByText('Falar com especialista B2G').closest('a');
    expect(link?.getAttribute('href')).toBe('/consultoria-b2g#diagnostico');
  });
});
