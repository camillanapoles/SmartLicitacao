export default function FundadoresGuarantee() {
  return (
    <section
      aria-labelledby="garantia-heading"
      className="mt-16 rounded-xl border-2 border-emerald-300 bg-emerald-50 p-6"
    >
      <div className="flex items-start gap-4">
        <div
          aria-hidden="true"
          className="h-16 w-16 rounded-full bg-emerald-600 text-white flex items-center justify-center font-bold text-lg flex-shrink-0"
        >
          60d
        </div>
        <div>
          <h2 id="garantia-heading" className="text-2xl font-semibold text-slate-900 mb-2">
            Garantia incondicional de 60 dias
          </h2>
          <p className="text-slate-700 leading-relaxed mb-3">
            Use o SmartLic por 60 dias. Se em qualquer momento dos primeiros dois meses
            você decidir que não vale, devolvo 100% do valor pago. Sem perguntas, sem
            formulário longo, sem &quot;tem certeza?&quot; três vezes.
          </p>
          <p className="text-slate-700 leading-relaxed mb-2">
            <strong>Como pedir reembolso:</strong>
          </p>
          <ol className="list-decimal pl-5 space-y-1 text-slate-700 mb-3">
            <li>
              Envie um email para{' '}
              <a
                href="mailto:tiago@smartlic.tech?subject=reembolso"
                className="text-blue-700 underline font-medium"
              >
                tiago@smartlic.tech
              </a>{' '}
              com assunto <code className="bg-white px-1.5 py-0.5 rounded border border-slate-200">reembolso</code>.
            </li>
            <li>Não preciso saber por quê. Reembolso processado em até 5 dias úteis.</li>
            <li>Acesso à plataforma é encerrado após o reembolso confirmar.</li>
          </ol>
          <p className="text-sm text-slate-600">
            Vale para qualquer um dos primeiros 60 dias após o pagamento confirmado.
            Eu assino embaixo.
          </p>
        </div>
      </div>
    </section>
  );
}
