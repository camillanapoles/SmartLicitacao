import Link from 'next/link';
import BlogInlineCTA from '../components/BlogInlineCTA';

/**
 * PNCP-SPOKE-08 (#992) — PNCP: 7 erros comuns de empresas iniciantes
 * Cluster: PNCP | Pillar: pncp-guia-completo-empresas
 * Target: ~1050 words | Primary KW: pncp erros
 */
export default function PncpErrosComunsEmpresasIniciantes() {
  return (
    <>
      {/* FAQPage JSON-LD */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            '@context': 'https://schema.org',
            '@type': 'FAQPage',
            mainEntity: [
              {
                '@type': 'Question',
                name: 'Qual o erro mais comum de empresa iniciante no PNCP?',
                acceptedAnswer: {
                  '@type': 'Answer',
                  text: 'Cadastrar-se apenas no SICAF e tentar participar de pregões municipais ou estaduais sem cadastro nas plataformas operacionais (BLL, Licitanet, BNC). Descobre-se na hora do lance que o cadastro adicional leva 24-72 horas — e a oportunidade está perdida.',
                },
              },
              {
                '@type': 'Question',
                name: 'O PNCP é difícil de usar para quem está começando?',
                acceptedAnswer: {
                  '@type': 'Answer',
                  text: 'A interface é funcional, mas o volume torna a triagem manual inviável. São 5-10 mil novos editais por dia em todo o país. Empresas iniciantes precisam de filtros bem configurados (UF, modalidade, faixa de valor, palavras-chave) — ou de uma ferramenta que automatize a triagem.',
                },
              },
              {
                '@type': 'Question',
                name: 'Vale a pena começar por dispensa ou direto por pregão?',
                acceptedAnswer: {
                  '@type': 'Answer',
                  text: 'Para empresas sem atestado técnico em compras públicas, a dispensa eletrônica é a porta de entrada mais inteligente: ciclo curto, menos exigências de habilitação, possibilidade de gerar atestado para pregões maiores. Iniciar por pregões R$ 500k+ sem atestado é receita para inabilitação.',
                },
              },
              {
                '@type': 'Question',
                name: 'Como evitar perder editais por falta de monitoramento?',
                acceptedAnswer: {
                  '@type': 'Answer',
                  text: 'Configure alertas. O PNCP tem cadastro de palavras-chave para notificação por email; ferramentas como a SmartLic vão além e classificam por setor com IA, reduzindo falsos positivos. O hábito de ver editais "uma vez por semana" garante perder os de prazo curto.',
                },
              },
            ],
          }),
        }}
      />

      <p className="text-base sm:text-xl leading-relaxed text-ink">
        Este guia faz parte do{' '}
        <Link href="/blog/pncp-guia-completo-empresas">
          Guia Completo do PNCP
        </Link>{' '}
        da SmartLic. Quem entra agora em compras públicas comete os
        mesmos sete erros — em sequência previsível. Mapear esses
        tropeços antes evita 80% da curva dolorosa.
      </p>

      <h2>Erro 1 — Cadastro incompleto</h2>
      <p>
        Empresa iniciante imagina que o SICAF (cadastro federal no
        ComprasGov) é suficiente para tudo. Não é. Para participar de
        pregões municipais e estaduais, é preciso ter cadastro nas
        plataformas operacionais usadas pelos órgãos: BLL Compras,
        Licitanet, BNC Compras Públicas, ComprasNet do estado etc. Cada
        cadastro leva 24-72 horas para validação. Faça os principais
        antes mesmo de identificar o primeiro edital — quando a
        oportunidade aparecer, você já estará pronto. Para entender a
        divisão de plataformas, veja{' '}
        <Link href="/blog/pncp-vs-comprasgov-diferencas">
          PNCP vs ComprasGov — diferenças
        </Link>
        .
      </p>

      <h2>Erro 2 — Filtros amplos demais</h2>
      <p>
        Sem filtros, o PNCP devolve 5 a 10 mil editais por dia. É
        impossível triar manualmente. O hábito típico do iniciante é
        olhar tudo "do meu setor" — e descobrir que palavra-chave
        ampla ("limpeza") devolve milhares de resultados, dos quais
        90% não são compatíveis com o porte da empresa. Estreite o
        filtro com:
      </p>
      <ul>
        <li>UF inicialmente só do seu estado.</li>
        <li>Faixa de valor compatível com sua capacidade.</li>
        <li>Modalidade (comece por pregão eletrônico).</li>
        <li>Palavras-chave específicas + exclusões.</li>
      </ul>

      <h2>Erro 3 — Subestimar o prazo de leitura do edital</h2>
      <p>
        Editais públicos são longos — 30 a 100 páginas é normal. Quem
        vai ler "um pouco antes do dia da sessão" perde detalhes que
        custam o contrato: cláusulas de garantia financeira, prazos de
        execução agressivos, exigências de equipe-chave residente,
        critérios de pontuação técnica que penalizam empresas pequenas.
        A regra é: <strong>leia o edital nas primeiras 48 horas</strong>{' '}
        após publicação, faça o go/no-go nesse momento, e use o resto
        do prazo para <em>preparar</em>, não para decidir.
      </p>

      <h2>Erro 4 — Não calcular planilha de composição de preço</h2>
      <p>
        Iniciante cota "olhando para o estimado" e baixando 10-20%.
        Profissional cota com planilha de composição: custo direto +
        custo indireto + tributos + margem. Em pregão, vença ou perca,
        você precisa saber qual é o seu lance mínimo abaixo do qual
        prefere perder. Sem isso, "ganha" e descobre depois que o
        contrato dá prejuízo. A Lei 14.133/2021, art. 59, considera
        inexequíveis propostas de obras abaixo de 75% do estimado —
        essa é a baliza objetiva.
      </p>

      <h2>Erro 5 — Certidão fiscal vencida na hora da habilitação</h2>
      <p>
        Pregoeiros são treinados a verificar todas as certidões na
        sessão. Uma única certidão fora da validade — especialmente FGTS
        (30 dias), que vence rápido — gera inabilitação imediata. Mantenha:
      </p>
      <ul>
        <li>FGTS sempre atualizado (renovação mensal automatizada).</li>
        <li>Receita/PGFN (180 dias) com renovação trimestral.</li>
        <li>CNDT (180 dias) com renovação trimestral.</li>
        <li>Estaduais e municipais conforme prazo de cada UF.</li>
      </ul>
      <p>
        Crie um calendário de vencimentos. Nunca dependa da memória.
      </p>

      <h2>Erro 6 — Atestado técnico incompatível</h2>
      <p>
        Empresa que nunca executou contrato público parecido com o
        objeto licitado raramente é habilitada em pregões médios e
        grandes — o atestado técnico exige objeto e quantitativo
        compatíveis. A saída inteligente é começar por dispensas
        eletrônicas (art. 75) e contratos pequenos para construir
        portfólio. Cada contrato bem executado vira um atestado novo,
        habilitando a empresa para pregões maiores. Veja{' '}
        <Link href="/blog/pncp-dispensa-licitacao-quando-aplicar">
          PNCP e dispensa de licitação
        </Link>
        .
      </p>

      <h2>Erro 7 — Não acompanhar prazos de impugnação e recurso</h2>
      <p>
        Editais com cláusulas restritivas (exigência exagerada de
        atestado, faixa de valor que afasta MEI/EPP, pontuação técnica
        artificial) podem ser impugnados até 3 dias úteis antes da
        sessão. Empresas iniciantes raramente exercem esse direito por
        desconhecimento — e perdem oportunidades. Da mesma forma, em
        recurso administrativo após o pregão, há 3 dias úteis para
        manifestação de intenção e 3 dias úteis adicionais para razões
        recursais. Quem perde por procedimento perde duas vezes: o
        contrato e o aprendizado.
      </p>

      <h2>Roteiro de primeiros 90 dias no PNCP</h2>
      <p>
        Para empresa que está começando, sugerimos:
      </p>
      <ul>
        <li>
          <strong>Dias 1-15:</strong> cadastro completo (SICAF + 3
          plataformas operacionais principais), atualização de certidões,
          configuração de alertas.
        </li>
        <li>
          <strong>Dias 16-45:</strong> participar de 3-5 dispensas
          eletrônicas pequenas, foco em ganhar primeiros atestados.
        </li>
        <li>
          <strong>Dias 46-90:</strong> primeiros pregões eletrônicos com
          atestado em mãos, escalada gradual para faixas de valor
          maiores.
        </li>
      </ul>
      <p>
        Não tente queimar etapas. Empresas que correm para pregões
        grandes sem base operacional tomam dois ou três tombos e desistem
        de B2G — quando o problema era método, não mercado.
      </p>

      <BlogInlineCTA
        slug="pncp-erros-comuns-empresas-iniciantes"
        campaign="guias"
        ctaMessage="Comece com o método certo desde o dia 1."
        ctaText="Testar grátis"
      />

      <h2>Próximos passos no cluster PNCP</h2>
      <p>
        Continue por{' '}
        <Link href="/blog/empresa-iniciante-ganhar-contratos-governo">
          empresa iniciante: como ganhar contratos com o governo
        </Link>
        ,{' '}
        <Link href="/blog/pncp-timeline-publicacao-edital">
          PNCP — timeline de publicação
        </Link>{' '}
        e o{' '}
        <Link href="/blog/pncp-guia-completo-empresas">
          Guia Completo do PNCP
        </Link>
        .
      </p>
    </>
  );
}
