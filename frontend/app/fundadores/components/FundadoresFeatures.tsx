interface Feature {
  title: string;
  description: string;
}

const FEATURES: Feature[] = [
  {
    title: 'Busca multi-fonte unificada',
    description:
      'PNCP + Portal de Compras Públicas + ComprasGov em uma busca consolidada com deduplicação automática.',
  },
  {
    title: 'Classificação por IA',
    description:
      'GPT-4.1-nano classifica relevância setorial com precisão ≥85%. Menos falso positivo, menos tempo perdido.',
  },
  {
    title: 'Análise de viabilidade',
    description:
      'Quatro fatores (modalidade, timeline, valor, geografia) pontuam cada edital antes de você abrir o PDF.',
  },
  {
    title: 'Pipeline Kanban',
    description:
      'Gestão de oportunidades com drag-and-drop. Do radar à proposta enviada em uma tela.',
  },
  {
    title: 'Relatórios Excel + IA',
    description:
      'Excel estilizado + resumo executivo gerado por IA para cada busca. Pronto para apresentar ao time.',
  },
  {
    title: '2 milhões de contratos indexados',
    description:
      'Histórico de licitações para benchmark de preço, mapeamento de concorrentes e análise de mercado B2G.',
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
