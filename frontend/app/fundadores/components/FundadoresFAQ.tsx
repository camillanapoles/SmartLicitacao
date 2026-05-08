'use client';

import { useState } from 'react';

interface FaqItem {
  q: string;
  a: string;
}

const FAQS: FaqItem[] = [
  {
    q: 'Por que pagar R$997 de uma vez em vez de assinar mensalmente?',
    a: 'Matemática simples: o plano Pro custa R$397/mês. Em 12 meses, você pagaria R$4.764. Com o Plano Fundadores, paga R$997 uma única vez e nunca mais paga nada — acesso permanente. A partir do segundo ano, o SmartLic é gratuito para você. Sem mensalidade, sem cobrança automática, sem surpresas no cartão.',
  },
  {
    q: 'O que acontece se o SmartLic fechar ou mudar de direção?',
    a: 'Entendemos a preocupação — é exatamente por isso que temos 30 dias de garantia incondicional. Se dentro desse prazo você não ficar satisfeito por qualquer motivo, devolvemos 100% do valor sem perguntas. Além disso, o compromisso vitalício é real: o Tiago Sasaki (fundador) está disponível diretamente em tiago@smartlic.tech para qualquer dúvida ou problema.',
  },
  {
    q: 'Tem suporte incluso? Como funciona?',
    a: 'Sim, e é suporte prioritário. Como Fundador, você tem acesso direto ao fundador via email (tiago@smartlic.tech) com tempo de resposta inferior a 4 horas úteis para problemas críticos. Você não cai em fila de chamados — fala direto com quem construiu o produto. Os primeiros Fundadores também recebem uma sessão de onboarding personalizada.',
  },
  {
    q: 'Posso usar em quantas empresas ou CNPJs?',
    a: 'O Plano Fundadores cobre 1 conta vinculada a 1 CNPJ. Se você gerencia licitações para múltiplas empresas (consultoria, assessoria), entre em contato para discutir um plano adequado. Upgrades estão disponíveis e Fundadores têm condições especiais.',
  },
  {
    q: 'Como acesso o SmartLic após o pagamento?',
    a: 'Imediatamente após a confirmação do pagamento pelo Stripe, você recebe um email automático com magic link de acesso. Em até 24 horas, sua conta é configurada com o Plano Fundadores ativo. Se houver qualquer problema, escreva para tiago@smartlic.tech e resolvemos na hora.',
  },
  {
    q: 'O SmartLic funciona para meu setor?',
    a: 'O SmartLic cobre 20 setores B2G com classificação por IA — de construção e TI a saúde e meio ambiente. Se o seu setor não estiver listado, entre em contato antes de comprar. Fundadores têm voz direta na priorização de novos setores.',
  },
  {
    q: 'O que está incluído no Plano Fundadores?',
    a: 'Acesso vitalício completo: busca multi-fonte unificada, classificação por IA com precisão ≥85%, análise de viabilidade em 4 fatores, pipeline Kanban de oportunidades, relatórios Excel estilizados, resumo executivo por IA e histórico de 2 milhões de contratos públicos para benchmark de preço. Tudo que existe hoje e tudo que for lançado no futuro.',
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
