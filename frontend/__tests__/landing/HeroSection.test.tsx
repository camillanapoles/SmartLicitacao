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
  it('renders headline with B2G intelligence positioning (REPO-006)', () => {
    render(<HeroSection />);

    expect(screen.getByText(/Decisão comercial em licitação não nasce de PDF/i)).toBeInTheDocument();
    expect(screen.getByText(/Nasce de inteligência/i)).toBeInTheDocument();
  });

  it('renders subheadline with go/no-go decision framing (REPO-006)', () => {
    render(<HeroSection />);

    expect(screen.getByText(/SmartLic lê o edital, mapeia o concorrente, calcula a chance real/i)).toBeInTheDocument();
    expect(screen.getByText(/go\/no-go em minutos/i)).toBeInTheDocument();
  });

  it('renders primary CTA with correct data-testid and href (REPO-006)', () => {
    render(<HeroSection />);

    const primaryCTA = screen.getByTestId('hero-cta-primary');
    expect(primaryCTA).toBeInTheDocument();
    expect(primaryCTA).toHaveAttribute('href', '/signup?source=hero-primary');
    expect(primaryCTA).toHaveTextContent('Testar plataforma');
  });

  it('renders secondary CTA with correct data-testid and href (REPO-006)', () => {
    render(<HeroSection />);

    const secondaryCTA = screen.getByTestId('hero-cta-secondary');
    expect(secondaryCTA).toBeInTheDocument();
    expect(secondaryCTA).toHaveAttribute('href', '/consultoria-b2g#diagnostico');
    expect(secondaryCTA).toHaveTextContent('Solicitar diagnóstico B2G');
  });

  it('does NOT use forbidden terms (AC11)', () => {
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

  // ---- DEBT-125: Product Screenshot Tests ----

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
      // 3 browser dots + 3 trust indicator dots = 6
      expect(dots.length).toBeGreaterThanOrEqual(6);
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
