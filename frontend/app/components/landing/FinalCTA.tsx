import AnimateOnScroll from '@/components/ui/AnimateOnScroll';

interface FinalCTAProps {
  className?: string;
}

/**
 * SAB-006 AC3: Absorbed beta counter content into FinalCTA.
 * DEBT-2: Converted to RSC with AnimateOnScroll client island.
 */
export default function FinalCTA({ className = '' }: FinalCTAProps) {
  return (
    <section
      className={`max-w-landing mx-auto px-4 sm:px-6 lg:px-8 py-12 sm:py-16 ${className}`}
    >
      <AnimateOnScroll threshold={0.3}>
        <div className="bg-brand-navy rounded-card p-10 sm:p-14 text-center text-white">
          <h2 className="text-2xl sm:text-3xl lg:text-4xl font-bold tracking-tight mb-4">
            Sua empresa pode estar perdendo o edital certo agora.
          </h2>

          <AnimateOnScroll delay={100}>
            <p className="text-lg sm:text-xl mb-6 text-white/80">
              Enquanto você decide, seus concorrentes já estão se preparando. Pare de perder oportunidades que pagam.
            </p>
          </AnimateOnScroll>

          {/* SAB-006: Absorbed beta counter */}
          <AnimateOnScroll delay={150} data-testid="beta-counter">
            <p className="text-sm mb-8 text-white/60">
              14 dias grátis. Cancele quando quiser.
            </p>
          </AnimateOnScroll>

          <AnimateOnScroll delay={200}>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <a
                href="/signup?source=landing-cta"
                className="w-full sm:w-auto bg-white text-brand-navy hover:bg-surface-1 font-bold px-8 py-4 rounded-button transition-all hover:scale-[1.02] active:scale-[0.98] text-center text-lg focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-white/50"
                data-testid="final-cta-primary"
              >
                Ver oportunidades do meu setor →
              </a>
              {/* COPY-LANDING-004 (#1003): Cross-sell sutil Plano Fundadores */}
              <a
                href="/planos#fundadores"
                className="w-full sm:w-auto border border-white/40 text-white hover:bg-white/10 font-semibold px-8 py-4 rounded-button transition-all text-center text-base focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-white/50"
                data-testid="final-cta-fundadores"
              >
                Vagas Fundadores se encerram: R$997 vitalício →
              </a>
            </div>
          </AnimateOnScroll>

          <AnimateOnScroll
            delay={300}
            hiddenClass="opacity-0"
            visibleClass="opacity-100"
          >
            <div className="mt-6 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-sm text-white/70">
              <span>Fontes oficiais verificadas</span>
              <span className="hidden sm:inline text-white/30">|</span>
              <span>Critérios objetivos</span>
              <span className="hidden sm:inline text-white/30">|</span>
              <span>Cancelamento em 1 clique</span>
            </div>
          </AnimateOnScroll>

          <AnimateOnScroll
            delay={400}
            hiddenClass="opacity-0"
            visibleClass="opacity-100"
          >
            <p className="mt-3 text-sm text-white/50">
              Últimas vagas do plano vitalício R$997. Se não agir hoje, pode perder — o edital e a vaga.
            </p>
          </AnimateOnScroll>
        </div>
      </AnimateOnScroll>
    </section>
  );
}
