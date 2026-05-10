export default function FundadoresFounderLetter() {
  return (
    <section aria-labelledby="carta-heading" className="mb-16">
      <h2 id="carta-heading" className="text-2xl font-semibold text-slate-900 mb-6">
        Uma carta de quem fez isso
      </h2>
      <div className="flex items-start gap-4 mb-6">
        <div
          aria-hidden="true"
          className="h-16 w-16 rounded-full bg-slate-200 flex items-center justify-center text-slate-500 font-semibold flex-shrink-0"
        >
          TS
        </div>
        <div>
          <p className="font-semibold text-slate-900">Tiago Sasaki</p>
          <p className="text-sm text-slate-600">Fundador, SmartLic · CONFENGE Avaliações e IA</p>
          <p className="text-sm text-slate-600 mt-1">
            <a
              href="https://www.linkedin.com/in/tiagosasaki/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 underline"
            >
              LinkedIn
            </a>
            {' · '}
            <a href="mailto:tiago@smartlic.tech" className="text-blue-600 underline">
              tiago@smartlic.tech
            </a>
          </p>
        </div>
      </div>
      <div className="prose prose-slate max-w-none text-slate-700 leading-relaxed">
        <p>Olá. Sou o Tiago.</p>
        <p className="mt-4">
          Sou engenheiro civil. Passei 10 anos como servidor público no setor de obras
          de uma prefeitura. Desse outro lado do balcão, vi duas coisas todo dia:
        </p>
        <p className="mt-4">
          <strong>Primeiro:</strong> empresas pequenas e médias perdendo licitações
          boas porque não viram o edital a tempo. Edital publicado terça à tarde,
          prazo curto, abertura na sexta. Quem tinha equipe pra varrer PNCP toda hora
          entrava. Quem não tinha, ficava de fora — não por incompetência, por falta
          de informação no momento certo.
        </p>
        <p className="mt-4">
          <strong>Segundo:</strong> consultoria de licitação cobrando
          R$3.000–R$8.000/mês para fazer triagem manual que uma IA bem feita resolve.
          Empresário B2G pagando salário de gente para ler PDF.
        </p>
        <p className="mt-4">
          Saí em 2025 e construí o SmartLic com a CONFENGE. Hoje a plataforma indexa{' '}
          <strong>2.187.430 contratos públicos</strong>, monitora{' '}
          <strong>27 UFs em tempo real</strong>, classifica em{' '}
          <strong>20 setores</strong> com IA, e está em produção (Railway + Supabase,
          não é demo).
        </p>
        <p className="mt-4">
          Eu poderia esperar mais 6 meses, dar polimento, lançar com pricing tradicional
          R$397/mês, e tentar bootstrappar do zero. Não vou fazer isso.
        </p>
        <p className="mt-4">
          Estou abrindo <strong>50 vagas</strong> de acesso vitalício por R$997
          one-time. Em troca de quê? De runway honesto pros próximos 6 meses (50 ×
          R$997 = R$49.850, dá pra terminar o roadmap sem captar) e de 50 parceiros
          que vão usar de verdade, reclamar quando algo quebrar, e me dizer o que falta.
        </p>
        <p className="mt-4">
          Não é &quot;early bird&quot; de marketing. É um pacto: você banca a próxima
          fase, eu garanto que você nunca mais paga mensalidade — independentemente do
          que aconteça com o pricing depois.
        </p>
        <p className="mt-4">
          Se faz sentido pra você, está aí em cima.
        </p>
        <p className="mt-4">— Tiago</p>
      </div>
    </section>
  );
}
