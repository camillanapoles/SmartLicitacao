interface Feature {
  title: string;
  description: string;
}

// 9 bullets — "Tudo, pra sempre" (Issue #1000)
const FEATURES: Feature[] = [
  { title: 'Busca multi-fonte unificada', description: 'PNCP + ComprasGov + Portal de Compras Públicas em uma busca só. Dedup automático. Sem abrir três portais.' },
  { title: 'Classificação por IA (20 setores)', description: 'GPT-4.1-nano classifica cada edital pelo seu setor. Precisão ≥85% validada em benchmark.' },
  { title: 'Análise de viabilidade em 4 fatores', description: 'Modalidade, timeline, valor e geografia pontuam cada edital antes de você abrir o PDF.' },
  { title: 'Pipeline Kanban de oportunidades', description: 'Do radar até a proposta enviada em uma tela. Drag-and-drop, sem planilha paralela.' },
  { title: 'Relatórios Excel + resumo executivo IA', description: 'Exporte resultados formatados, com resumo gerado por IA. Pronto para a reunião.' },
  { title: 'Histórico de 2.187.430 contratos públicos', description: 'Benchmark de preços, mapeamento de concorrentes, panorama setorial. Você decide com dados.' },
  { title: 'Cobertura nacional (27 UFs)', description: 'Todo o Brasil, sem custo extra por estado. De Roraima ao Rio Grande do Sul.' },
  { title: 'Todas as atualizações futuras', description: 'Cada feature nova entra automaticamente na sua conta. Sem upgrade, sem upsell, sem letra miúda.' },
  { title: 'Sem mensalidade, sem renovação', description: 'Você paga R$997 uma vez. Acesso fica na sua conta. Não precisa lembrar de cancelar nada.' },
];

export default function FundadoresFeatures() {
  return (
    <section aria-labelledby="features-heading" className="mt-16">
      <h2 id="features-heading" className="text-2xl font-semibold text-slate-900 mb-2">
        O que está incluído (tudo, pra sempre)
      </h2>
      <p className="text-slate-600 mb-8">
        Não tem &quot;plano básico&quot; vs &quot;plano avançado&quot;. Fundador pega tudo —
        e tudo que vier também.
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
