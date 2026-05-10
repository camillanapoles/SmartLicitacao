const ROWS = [
  { periodo: '12 meses (1 ano)', mensal: 4764, economia: 4764 - 997 },
  { periodo: '24 meses (2 anos)', mensal: 9528, economia: 9528 - 997 },
  { periodo: '60 meses (5 anos)', mensal: 23820, economia: 23820 - 997 },
];

export default function FundadoresComparisonTable() {
  return (
    <section aria-labelledby="conta-heading" className="mb-16">
      <h2 id="conta-heading" className="text-2xl font-semibold text-slate-900 mb-2">
        A conta do uma vez vs todo mês
      </h2>
      <p className="text-slate-600 mb-6">
        Pro mensal regular custa R$397/mês. Veja o que isso vira ao longo do tempo
        comparado ao pagamento único de fundador.
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="bg-slate-100">
              <th className="text-left px-4 py-3 font-semibold text-slate-700 border border-slate-200">
                Período
              </th>
              <th className="text-center px-4 py-3 font-semibold text-slate-700 border border-slate-200">
                Pro mensal (R$397/mês)
              </th>
              <th className="text-center px-4 py-3 font-semibold text-blue-700 border border-slate-200">
                Fundador (R$997 único)
              </th>
              <th className="text-center px-4 py-3 font-semibold text-emerald-700 border border-slate-200">
                Você economiza
              </th>
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row) => (
              <tr key={row.periodo} className="border border-slate-200 hover:bg-slate-50">
                <td className="px-4 py-3 text-slate-700 border border-slate-200 font-medium">
                  {row.periodo}
                </td>
                <td className="px-4 py-3 text-center text-slate-600 border border-slate-200">
                  R${row.mensal.toLocaleString('pt-BR')}
                </td>
                <td className="px-4 py-3 text-center font-medium text-blue-700 border border-slate-200">
                  R$997
                </td>
                <td className="px-4 py-3 text-center font-semibold text-emerald-700 border border-slate-200">
                  R${row.economia.toLocaleString('pt-BR')}
                </td>
              </tr>
            ))}
            <tr className="bg-emerald-50 border border-slate-200">
              <td
                colSpan={4}
                className="px-4 py-3 text-center text-emerald-800 border border-slate-200 font-semibold"
              >
                Em 5 anos, fundadores economizam mais de R$22 mil — e seguem com acesso
                pra sempre.
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  );
}
