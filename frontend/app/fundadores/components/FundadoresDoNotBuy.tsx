export default function FundadoresDoNotBuy() {
  return (
    <section
      aria-labelledby="nao-deveria-heading"
      className="mt-16 rounded-xl border border-amber-200 bg-amber-50 p-6"
    >
      <h2 id="nao-deveria-heading" className="text-2xl font-semibold text-slate-900 mb-2">
        Quem não deveria comprar
      </h2>
      <p className="text-slate-700 mb-4">
        Honestidade vale mais do que conversão. Se você se encaixa em um destes três
        perfis, não compre — vai ficar frustrado e eu vou ter que devolver na garantia
        de 60 dias.
      </p>
      <ul className="space-y-3 text-slate-700">
        <li className="flex gap-3">
          <span aria-hidden="true" className="text-amber-700 font-bold">×</span>
          <span>
            <strong>Empresa com faturamento abaixo de R$200 mil/ano.</strong>{' '}
            Licitação pública exige capital de giro, fluxo de caixa, capacidade
            operacional. R$997 não vai te tornar elegível se a estrutura financeira
            não está pronta. Cresça primeiro, automatize depois.
          </span>
        </li>
        <li className="flex gap-3">
          <span aria-hidden="true" className="text-amber-700 font-bold">×</span>
          <span>
            <strong>Empresa sem CRC ou habilitação técnica do setor.</strong>{' '}
            O SmartLic encontra e qualifica editais — mas não emite atestado,
            não substitui registro profissional, não resolve falta de habilitação.
            Resolva o cadastro antes; o software vem depois.
          </span>
        </li>
        <li className="flex gap-3">
          <span aria-hidden="true" className="text-amber-700 font-bold">×</span>
          <span>
            <strong>Quem espera &quot;garantia de ganhar licitação&quot;.</strong>{' '}
            Não existe. Quem te promete isso está mentindo ou cobrando ilegalmente.
            O SmartLic aumenta a probabilidade de encontrar editais bons no momento
            certo — quem ganha é a sua proposta.
          </span>
        </li>
      </ul>
    </section>
  );
}
