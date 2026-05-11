import { render, screen } from '@testing-library/react';
import HeroSection from '@/app/components/landing/HeroSection';

// Mock next/image — render as plain img with all props
jest.mock('next/image', () => {
  const React = require('react');
  return {
    __esModule: true,
    default: React.forwardRef((props: Record<string, unknown>, ref: React.Ref<HTMLImageElement>) => {
      const { priority, blurDataURL, placeholder, ...rest } = props;
      return React.createElement('img', {
        ...rest,
        ref,
        'data-priority': priority ? 'true' : undefined,
        'data-placeholder': placeholder,
      });
    }),
  };
});

// Mock next/link — render as plain anchor
jest.mock('next/link', () => {
  const React = require('react');
  return {
    __esModule: true,
    default: ({ href, children, ...rest }: { href: string; children: React.ReactNode; [key: string]: unknown }) =>
      React.createElement('a', { href, ...rest }, children),
  };
});

describe('HeroSection', () => {
  // ---- COPY-LANDING-004 (#1003): Beachhead anti-assessor + trust signals 2026 ----

  it('renders V1 anti-assessor headline (COPY-LANDING-004)', () => {
    render(<HeroSection />);
    const headline = screen.getByTestId('hero-headline');
    expect(headline).toHaveTextContent(
      /Pare de pagar R\$3\.000\/mês ao assessor que copia o PNCP\./i
    );
  });

  it('renders sub with mensal + Fundadores price anchor (COPY-LANDING-004)', () => {
    render(<HeroSection />);
    const sub = screen.getByTestId('hero-subheadline');
    expect(sub).toHaveTextContent(/SmartLic lê o edital, mapeia o concorrente/i);
    expect(sub).toHaveTextContent(/R\$297\/mês/i);
    expect(sub).toHaveTextContent(/R\$997 vitalício/i);
    expect(sub).toHaveTextContent(/não R\$3\.000 por PDF no WhatsApp/i);
  });

  it('renders primary CTA "Testar 14 dias grátis" with sub "Sem cartão" (COPY-LANDING-004)', () => {
    render(<HeroSection />);
    const primaryCTA = screen.getByTestId('hero-cta-primary');
    expect(primaryCTA).toHaveAttribute('href', '/signup?source=hero-primary');
    expect(primaryCTA).toHaveTextContent(/Testar 14 dias grátis/i);
    expect(screen.getByTestId('hero-cta-primary-subtext')).toHaveTextContent(
      /Sem cartão\. Cancele em 1 clique\./i
    );
  });

  it('renders secondary CTA "Plano Fundadores R$997" (COPY-LANDING-004)', () => {
    render(<HeroSection />);
    const secondaryCTA = screen.getByTestId('hero-cta-secondary');
    expect(secondaryCTA).toHaveAttribute('href', '/planos#fundadores');
    expect(secondaryCTA).toHaveTextContent(/Ver Plano Fundadores R\$997/i);
  });

  it('renders founder strip with name + role + LinkedIn link (COPY-LANDING-004)', () => {
    render(<HeroSection />);
    const strip = screen.getByTestId('hero-founder-strip');
    expect(strip).toHaveTextContent(/Tiago Sasaki/i);
    expect(strip).toHaveTextContent(/7 anos servidor público/i);
    expect(strip).toHaveTextContent(/gestão e fiscalização de contratos/i);

    const linkedin = screen.getByTestId('hero-founder-linkedin');
    expect(linkedin).toHaveAttribute('href', 'https://www.linkedin.com/in/tiagosasaki');
    expect(linkedin).toHaveAttribute('target', '_blank');
    expect(linkedin).toHaveAttribute('rel', expect.stringContaining('noopener'));
  });

  it('renders 2026 trust signals: changelog + roadmap + 60d garantia + sources', () => {
    render(<HeroSection />);
    const trust = screen.getByTestId('hero-trust-signals');
    expect(trust).toHaveTextContent(/Changelog público/i);
    expect(trust).toHaveTextContent(/Roadmap aberto/i);
    expect(trust).toHaveTextContent(/60 dias de garantia/i);
    expect(trust).toHaveTextContent(/devolução incondicional/i);
    expect(trust).toHaveTextContent(/Fontes oficiais verificadas/i);

    expect(screen.getByTestId('hero-trust-changelog')).toHaveAttribute('href', '/changelog');
    expect(screen.getByTestId('hero-trust-roadmap')).toHaveAttribute('href', '/roadmap');
  });

  it('REMOVES legacy "Sem dados fabricados" microcopy (COPY-LANDING-004 AC)', () => {
    const { container } = render(<HeroSection />);
    const text = container.textContent || '';
    expect(text).not.toMatch(/Sem dados fabricados/i);
  });

  it('does NOT use forbidden marketing terms', () => {
    const { container } = render(<HeroSection />);
    const text = container.textContent || '';

    expect(text).not.toMatch(/economize.*tempo/i);
    expect(text).not.toMatch(/busca rápida/i);
    expect(text).not.toMatch(/ferramenta de busca/i);
    expect(text).not.toMatch(/planilha automatizada/i);
    expect(text).not.toMatch(/10h\/semana/i);
    expect(text).not.toMatch(/inteligência automatizada/i);
    expect(text).not.toMatch(/inovador/i);
  });

  it('uses design system tokens for styling', () => {
    const { container } = render(<HeroSection />);

    expect(container.querySelector('.text-ink')).toBeInTheDocument();
    expect(container.querySelector('.text-gradient')).toBeInTheDocument();
  });

  it('does NOT render stats badges (SAB-006 AC2 — stats consolidated into StatsSection)', () => {
    const { container } = render(<HeroSection />);
    const text = container.textContent || '';

    expect(text).not.toMatch(/87%/);
    expect(text).not.toMatch(/UFs cobertas/i);
  });

  // ---- DEBT-125: Product Screenshot Tests (preserved from previous spec) ----

  describe('DEBT-125: Product Screenshot', () => {
    it('AC1: renders product screenshot in desktop layout', () => {
      const { container } = render(<HeroSection />);

      const img = screen.getByRole('img', {
        name: /Tela de resultados do SmartLic/i,
      });
      expect(img).toBeInTheDocument();

      const flexContainer = container.querySelector('.lg\\:flex-row');
      expect(flexContainer).toBeInTheDocument();
    });

    it('AC3: screenshot shows buscar results page at correct dimensions', () => {
      render(<HeroSection />);

      const img = screen.getByRole('img', {
        name: /Tela de resultados do SmartLic/i,
      });
      expect(img).toHaveAttribute('width', '1280');
      expect(img).toHaveAttribute('height', '800');
    });

    it('AC5: image uses next/image with priority for LCP optimization', () => {
      render(<HeroSection />);

      const img = screen.getByRole('img', {
        name: /Tela de resultados do SmartLic/i,
      });
      expect(img).toHaveAttribute('data-priority', 'true');
    });

    it('AC6: image has descriptive Portuguese alt text', () => {
      render(<HeroSection />);

      const img = screen.getByRole('img', {
        name: /Tela de resultados do SmartLic mostrando classificacao por IA e analise de viabilidade/i,
      });
      expect(img).toBeInTheDocument();
    });

    it('AC8: dark mode applies CSS filter for automatic darkening', () => {
      render(<HeroSection />);

      const img = screen.getByRole('img', {
        name: /Tela de resultados do SmartLic/i,
      });
      expect(img.className).toContain('dark:brightness-');
      expect(img.className).toContain('dark:contrast-');
    });

    it('renders browser chrome frame around screenshot', () => {
      const { container } = render(<HeroSection />);

      expect(screen.getByText('smartlic.tech/buscar')).toBeInTheDocument();

      const dots = container.querySelectorAll('.rounded-full');
      // 3 browser dots + 4 trust signal dots + 1 founder avatar bubble = 8
      expect(dots.length).toBeGreaterThanOrEqual(7);
    });

    it('image uses blur placeholder', () => {
      render(<HeroSection />);

      const img = screen.getByRole('img', {
        name: /Tela de resultados do SmartLic/i,
      });
      expect(img).toHaveAttribute('data-placeholder', 'blur');
    });

    it('image has responsive sizes attribute', () => {
      render(<HeroSection />);

      const img = screen.getByRole('img', {
        name: /Tela de resultados do SmartLic/i,
      });
      expect(img).toHaveAttribute('sizes');
      expect(img.getAttribute('sizes')).toContain('50vw');
    });

    it('AC2: mobile layout stacks screenshot below headline (flex-col default)', () => {
      const { container } = render(<HeroSection />);

      const flexContainer = container.querySelector('.flex-col.lg\\:flex-row');
      expect(flexContainer).toBeInTheDocument();
    });

    it('no CLS: image has explicit width and height', () => {
      render(<HeroSection />);

      const img = screen.getByRole('img', {
        name: /Tela de resultados do SmartLic/i,
      });
      expect(img).toHaveAttribute('width');
      expect(img).toHaveAttribute('height');
    });
  });
});
