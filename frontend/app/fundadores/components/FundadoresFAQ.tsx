'use client';

import { useState } from 'react';

interface FaqItem {
  q: string;
  a: string;
}

// 4 perguntas (Issue #1000) — as 4 que todo mundo me faz
const FAQS: FaqItem[] = [
  {
    q: 'E se o SmartLic acabar? Eu perco meus R$997?',
    a: 'Não. Três compromissos formais: (1) 60 dias de garantia incondicional — não gostou em qualquer momento dos primeiros dois meses, devolvo 100%, sem perguntas. (2) Se um dia o SmartLic precisar fechar, aviso com 90 dias de antecedência por email. (3) Você consegue exportar todos os seus dados a qualquer momento (buscas, pipeline, contratos analisados) — e a busca multi-fonte é open-source, fica no GitHub para sempre. Seu trabalho não some junto com a empresa.',
  },
  {
    q: 'Vocês não vão começar a cobrar mensalidade depois?',
    a: 'Não para você. Quem entra como fundador paga R$997 uma vez e nunca mais — está escrito no contrato (Termos do Plano Fundadores). Os 50 fundadores ficam vitalícios independentemente do que aconteça com o pricing depois de 30/06/2026. Quem entrar pelo plano regular a partir de julho/2026, sim, paga mensal.',
  },
  {
    q: 'Vale R$997 mesmo se eu nunca ganhar uma licitação?',
    a: 'Pergunta honesta. Se você nunca participar de licitação, não vale — não compra. Se você participa (mesmo de vez em quando), o break-even é uma proposta a mais por ano. Uma única licitação ganha porque você viu o edital antes paga R$997 muitas vezes. E sem mensalidade não tem risco de esquecer de cancelar: paga uma vez, fica na sua conta, usa quando precisar.',
  },
  {
    q: 'Por que essa oferta existe? Onde está a pegadinha?',
    a: 'Sem pegadinha — é matemática honesta. 50 fundadores × R$997 = R$49.850. Isso é mais ou menos 6 meses de runway para terminar o que está no roadmap (alertas WhatsApp, relatório de viabilidade PDF, integração com proposta comercial). Em troca, vocês 50 ganham acesso vitalício e influência direta no produto. Eu prefiro 50 parceiros pagantes hoje a 500 trials que talvez convertam em mensalidade. Pre-revenue, runway é tudo.',
  },
];

export default function FundadoresFAQ() {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  return (
    <section aria-labelledby="faq-heading" className="mt-16">
      <h2 id="faq-heading" className="text-2xl font-semibold text-slate-900 mb-2">
        As 4 perguntas que todo mundo me faz
      </h2>
      <p className="text-slate-600 mb-6">
        Recebi essas perguntas por email, LinkedIn e WhatsApp. Respondo aqui de uma vez.
      </p>
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
