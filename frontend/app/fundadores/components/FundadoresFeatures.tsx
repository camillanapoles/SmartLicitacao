interface Feature {
  title: string;
  description: string;
}

const FEATURES: Feature[] = [
  {
    title: 'Busca multi-fonte em minutos, não horas',
    description:
      'Agrega nossas fontes de dados públicos em uma busca consolidada com deduplicação automática. O que levava 4–8h/semana de pesquisa manual, o SmartLic faz em minutos.',
  },
  {
    title: 'IA decide o que é relevante para você',
    description:
      'GPT-4.1-nano classifica a relevância setorial com precisão ≥85%. Você vê apenas editais que fazem sentido para o seu negócio — sem ruído, sem perda de tempo com falsos positivos.',
  },
  {
    title: 'Análise de viabilidade antes de abrir o PDF',
    description:
      'Quatro fatores (modalidade, timeline, valor, geografia) pontuam cada edital automaticamente. Você decide em segundos se vale ou não vale o esforço de uma proposta.',
  },
  {
    title: 'Pipeline Kanban: do radar à proposta em uma tela',
    description:
      'Gestão de oportunidades com drag-and-drop. Acompanhe todos os editais do seu funil — prospecção, análise, proposta — sem planilha, sem post-it.',
  },
  {
    title: 'Relatórios prontos para apresentar',
    description:
      'Excel estilizado + resumo executivo gerado por IA para cada busca. Apresente resultados profissionais ao seu time ou cliente sem formatação manual.',
  },
  {
    title: 'Benchmark de preço com 2 milhões de contratos',
    description:
      'Histórico completo de licitações para saber quanto concorrentes cobram, quem ganha em cada órgão e qual é o preço justo para sua proposta vencer.',
  },
];

export default function FundadoresFeatures() {
  return (
    <>
      <section aria-labelledby="features-heading" className="mt-16">
        <h2 id="features-heading" className="text-2xl font-semibold text-slate-900 mb-2">
          O que você ganha — permanentemente
        </h2>
        <p className="text-slate-600 mb-8">
          Acesso vitalício a tudo que existe hoje e a tudo que for lançado no futuro. Sem mensalidade.
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

      {/* Social proof */}
      {/* TODO: adicionar depoimentos reais de usuários beta assim que coletados */}
      <section aria-labelledby="social-proof-heading" className="mt-16">
        <h2 id="social-proof-heading" className="text-2xl font-semibold text-slate-900 mb-6">
          O que dizem os primeiros usuários
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
          <blockquote className="rounded-lg border border-slate-200 bg-slate-50 p-5">
            <p className="text-slate-700 leading-relaxed italic mb-3">
              &ldquo;[TODO: adicionar depoimento real — ex: &apos;Antes gastava 6 horas na segunda-feira só pesquisando portais. Agora abro o SmartLic e em 10 minutos sei o que vale a pena trabalhar na semana.&apos;]&rdquo;
            </p>
            <footer className="text-sm text-slate-500">
              — [TODO: Nome, Cargo, Empresa]
            </footer>
          </blockquote>
          <blockquote className="rounded-lg border border-slate-200 bg-slate-50 p-5">
            <p className="text-slate-700 leading-relaxed italic mb-3">
              &ldquo;[TODO: adicionar depoimento real — ex: &apos;A análise de viabilidade mudou nossa forma de decidir quais editais vale disputar. Deixamos de perder tempo com processos impossíveis de ganhar.&apos;]&rdquo;
            </p>
            <footer className="text-sm text-slate-500">
              — [TODO: Nome, Cargo, Empresa]
            </footer>
          </blockquote>
        </div>
      </section>
    </>
  );
}
