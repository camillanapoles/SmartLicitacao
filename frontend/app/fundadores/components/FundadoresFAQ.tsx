'use client';

import { useState } from 'react';

interface FaqItem {
  q: string;
  a: string;
}

const FAQS: FaqItem[] = [
  {
    q: 'O que está incluído no Plano Fundadores?',
    a: 'Acesso vitalício à plataforma SmartLic (busca multi-fonte, classificação IA, pipeline kanban, relatórios Excel, análise de viabilidade). Pagamento único de R$997 — sem mensalidade, sem surpresas.',
  },
  {
    q: 'Qual a diferença entre Fundador e assinante regular?',
    a: 'O assinante regular paga R$397/mês (Pro) ou R$997/mês (Consultoria) recorrente. O Fundador paga R$997 uma única vez e tem acesso permanente, incluindo todas as atualizações futuras da plataforma.',
  },
  {
    q: 'Posso cancelar ou pedir reembolso?',
    a: 'Sim. Oferecemos 30 dias de garantia. Se não ficar satisfeito por qualquer motivo dentro deste prazo, devolvemos 100% do valor pago sem questionamentos.',
  },
  {
    q: 'O SmartLic funciona para meu setor?',
    a: 'O SmartLic cobre 20 setores B2G com classificação por IA (GPT-4.1-nano). Se seu setor não estiver listado, entre em contato — adicionamos novos setores com base na demanda dos fundadores.',
  },
  {
    q: 'Quantas vagas restam?',
    a: 'O Plano Fundadores é limitado. As vagas são preenchidas por ordem de chegada. O contador ao topo da página mostra a disponibilidade em tempo real.',
  },
  {
    q: 'Que suporte recebo como Fundador?',
    a: 'Acesso à linha direta com o fundador (Tiago Sasaki) via email/WhatsApp. Response time < 4h úteis para bugs críticos. Sessão de onboarding inclusa para os primeiros clientes.',
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
