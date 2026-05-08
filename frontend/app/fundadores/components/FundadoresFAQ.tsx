'use client';

import { useState } from 'react';

interface FaqItem {
  q: string;
  a: string;
}

const FAQS: FaqItem[] = [
  {
    q: 'R$997 é muito — e se eu não usar?',
    a: 'Quanto vale uma licitação ganha? Para a maioria das empresas B2G, o ROI aparece no primeiro contrato obtido com informação melhor. E sem mensalidade, não existe risco de esquecer de cancelar: você paga uma vez e o acesso está lá quando precisar.',
  },
  {
    q: 'Plano vitalício parece arriscado — e se a empresa fechar?',
    a: 'O SmartLic está em produção com clientes reais e infraestrutura estável (Railway + Supabase). Mas, mais importante: seu acesso não depende de renovação — está ativado permanentemente na sua conta. Se quiser transparência sobre a saúde do produto, é só perguntar.',
  },
  {
    q: 'O que exatamente está incluído no plano vitalício?',
    a: 'Busca unificada nos três principais portais (PNCP, ComprasGov, Portal de Compras Públicas), classificação por IA para o seu setor, análise de viabilidade em 4 fatores, pipeline Kanban para acompanhar oportunidades, relatórios Excel estilizados, e todas as novas funcionalidades lançadas futuramente — sem custo adicional.',
  },
  {
    q: 'Funciona para o meu setor?',
    a: 'O SmartLic cobre 20 setores B2G: construção civil, TI, saúde, limpeza e conservação, segurança, engenharia elétrica, hidráulica, rodoviário, entre outros. A classificação é automática por IA — você configura seu setor no onboarding e a plataforma filtra por relevância.',
  },
  {
    q: 'Como funciona o pagamento?',
    a: 'Cartão de crédito ou boleto bancário, processado com segurança via Stripe. O acesso é ativado imediatamente após a confirmação do pagamento — sem espera, sem burocracia.',
  },
  {
    q: 'Posso testar antes de comprar?',
    a: 'Sim. O plano trial está disponível em smartlic.tech — sem cartão, acesso imediato. O Plano Fundadores é para quem já testou (ou já decidiu) e quer garantir o acesso vitalício antes de 30/06/2026.',
  },
];

export default function FundadoresFAQ() {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  return (
    <section aria-labelledby="faq-heading" className="mt-16">
      <h2 id="faq-heading" className="text-2xl font-semibold text-slate-900 mb-6">
        Perguntas frequentes
      </h2>
      <div className="divide-y divide-slate-200 border border-slate-200 rounded-lg">
        {FAQS.map((item, idx) => {
          const isOpen = openIndex === idx;
          return (
            <div key={item.q}>
              <button
                type="button"
                className="w-full flex justify-between items-center px-4 py-3 text-left text-slate-900 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
                aria-expanded={isOpen}
                onClick={() => setOpenIndex(isOpen ? null : idx)}
              >
                <span className="font-medium">{item.q}</span>
                <span aria-hidden="true" className="ml-4 text-slate-500">
                  {isOpen ? '−' : '+'}
                </span>
              </button>
              {isOpen && (
                <div className="px-4 pb-4 text-slate-700 leading-relaxed">{item.a}</div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
