// DEBT-v3-S2 AC20: StatsSection is now an RSC wrapper.
// The full interactive version (counter animations, IntersectionObserver, SWR fetch)
// lives in StatsClientIsland.tsx ('use client').
//
// SSR renders static fallback HTML with final values for SEO + no-JS.
// The client island hydrates on top with animations.
// This thin RSC wrapper ensures the component name stays the same in page.tsx imports.
import StatsClientIsland from './StatsClientIsland';

interface StatsSectionProps {
  className?: string;
}

/**
 * SAB-006 AC2/AC6: Consolidated stats section with counter animation.
 * DEBT-v3-S2 AC20: Server Component shell -- delegates to StatsClientIsland for interactivity.
 *
 * Architecture: RSC renders a <noscript> fallback with static values for crawlers/SEO,
 * then the client island renders the full interactive version with animations.
 */
export default function StatsSection({ className = '' }: StatsSectionProps) {
  return (
    <>
      {/* No-JS / SSR fallback for crawlers -- hidden once client island hydrates */}
      <noscript>
        <section className={`max-w-landing mx-auto px-4 sm:px-6 lg:px-8 py-12 sm:py-16 bg-brand-blue-subtle/50 ${className}`}>
          <h2 className="text-3xl sm:text-4xl font-bold text-center text-ink tracking-tight mb-10">
            Impacto real no mercado de licita&#231;&#245;es
          </h2>
          <div className="flex flex-col lg:flex-row items-center gap-8 lg:gap-12">
            <div className="flex-shrink-0 text-center p-8 lg:p-12 bg-surface-0 rounded-card border border-[var(--border)] shadow-sm">
              <div className="text-5xl sm:text-6xl lg:text-7xl font-display tracking-tighter text-brand-navy tabular-nums">15</div>
              <div className="text-lg text-ink-secondary mt-2 font-medium">setores especializados</div>
              <div className="w-16 h-1 bg-brand-blue mx-auto mt-4 rounded-full" />
            </div>
            <div className="flex-1 grid sm:grid-cols-3 gap-6 w-full">
              <div className="text-center p-6 bg-surface-0 rounded-card border border-[var(--border)]">
                <div className="text-3xl sm:text-4xl font-bold text-brand-blue tabular-nums">87%</div>
                <div className="text-sm text-ink-secondary mt-1">de editais descartados</div>
              </div>
              <div className="text-center p-6 bg-surface-0 rounded-card border border-[var(--border)]">
                <div className="text-3xl sm:text-4xl font-bold text-brand-blue tabular-nums">1000+</div>
                <div className="text-sm text-ink-secondary mt-1">regras de filtragem</div>
              </div>
              <div className="text-center p-6 bg-surface-0 rounded-card border border-[var(--border)]">
                <div className="text-3xl sm:text-4xl font-bold text-brand-blue tabular-nums">27</div>
                <div className="text-sm text-ink-secondary mt-1">estados cobertos</div>
              </div>
            </div>
          </div>
          {/* #627: Volume social proof row (noscript mirror) */}
          <div className="mt-8 grid sm:grid-cols-3 gap-4">
            <div className="text-center p-5 bg-brand-blue-subtle/30 rounded-card border border-brand-blue/20">
              <div className="text-2xl sm:text-3xl font-bold text-brand-navy">+2 milh&#245;es</div>
              <div className="text-sm text-ink-secondary mt-1">contratos p&#250;blicos monitorados</div>
            </div>
            <div className="text-center p-5 bg-brand-blue-subtle/30 rounded-card border border-brand-blue/20">
              <div className="text-2xl sm:text-3xl font-bold text-brand-navy">27 estados</div>
              <div className="text-sm text-ink-secondary mt-1">cobertos em tempo real</div>
            </div>
            <div className="text-center p-5 bg-brand-blue-subtle/30 rounded-card border border-brand-blue/20">
              <div className="text-2xl sm:text-3xl font-bold text-brand-navy">R$ 1k &#8211; R$ 500M+</div>
              <div className="text-sm text-ink-secondary mt-1">faixa de valor analisada</div>
            </div>
          </div>
        </section>
      </noscript>

      {/* Client island: full interactive version with animations + SWR data */}
      <StatsClientIsland />
    </>
  );
}
