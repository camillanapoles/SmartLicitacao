interface Feature {
  title: string;
  description: string;
}

const FEATURES: Feature[] = [
  {
    title: 'Encontra licitações do seu setor automaticamente',
    description:
      'Agrega PNCP, ComprasGov e Portal de Compras Públicas em uma busca única — sem abrir três portais, sem duplicatas.',
  },
  {
    title: 'IA classifica relevância — você só vê o que importa',
    description:
      'Classificação setorial com precisão ≥85%. Menos tempo em editais irrelevantes, mais tempo elaborando propostas.',
  },
  {
    title: 'Análise de viabilidade em 4 fatores',
    description:
      'Modalidade, timeline, valor e geografia pontuam cada edital antes de você abrir o PDF. Decida em segundos se vale a pena.',
  },
  {
    title: 'Pipeline Kanban de oportunidades',
    description:
      'Do radar até a proposta enviada em uma tela. Acompanhe cada edital com drag-and-drop sem planilha paralela.',
  },
  {
    title: 'Relatórios Excel prontos para apresentar',
    description:
      'Exporte resultados formatados com resumo executivo gerado por IA. Leve para a reunião sem trabalho extra.',
  },
  {
    title: 'Histórico de 2 milhões de contratos públicos',
    description:
      'Benchmarke preços, mapeie concorrentes e entenda o mercado B2G antes de entrar em qualquer disputa.',
  },
];

export default function FundadoresFeatures() {
  return (
    <section aria-labelledby="features-heading" className="mt-16">
      <h2 id="features-heading" className="text-2xl font-semibold text-slate-900 mb-2">
        O que está incluído
      </h2>
      <p className="text-slate-600 mb-8">
        Tudo que você precisa para encontrar, qualificar e acompanhar licitações públicas.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
        {FEATURES.map((feat) => (
          <div
            key={feat.title}
            className="rounded-lg border border-slate-200 bg-slate-50 p-5"
          >
            <h3 className="font-semibold text-slate-900 mb-1">{feat.title}</h3>
            <p className="text-sm text-slate-600 leading-relaxed">{feat.description}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
