import Link from 'next/link';
import BlogInlineCTA from '../components/BlogInlineCTA';

/**
 * PNCP-SPOKE-06 (#992) — PNCP e Sistema de Registro de Preços
 * Cluster: PNCP | Pillar: pncp-guia-completo-empresas
 * Target: ~1100 words | Primary KW: pncp registro de preços
 */
export default function PncpRegistroPrecosComoParticipar() {
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
                name: 'O que é Sistema de Registro de Preços (SRP)?',
                acceptedAnswer: {
                  '@type': 'Answer',
                  text: 'É o procedimento pelo qual a administração registra preços para futuras contratações. Ao final de uma licitação SRP, gera-se uma Ata de Registro de Preços com vigência de até 12 meses, prorrogável por mais 12. Durante a vigência, o órgão pode comprar quando necessário, sem novo certame.',
                },
              },
              {
                '@type': 'Question',
                name: 'A empresa registrada na ata é obrigada a vender?',
                acceptedAnswer: {
                  '@type': 'Answer',
                  text: 'A empresa fica vinculada aos preços e quantitativos declarados durante a vigência. O órgão não é obrigado a comprar todo o quantitativo, mas, se decidir comprar, a empresa precisa entregar nas condições do edital. Recusa injustificada gera sanção e descredenciamento.',
                },
              },
              {
                '@type': 'Question',
                name: 'O que é "carona" em ata de registro de preços?',
                acceptedAnswer: {
                  '@type': 'Answer',
                  text: 'É quando outro órgão (não participante da licitação original) adere à ata vigente para comprar nas mesmas condições. A Lei 14.133/2021 limita a adesão a 50% dos quantitativos da ata, e cada adesão também respeita o teto. A "carona" é uma fonte de receita adicional para a empresa registrada — sem precisar disputar nova licitação.',
                },
              },
              {
                '@type': 'Question',
                name: 'Como localizar atas vigentes no PNCP?',
                acceptedAnswer: {
                  '@type': 'Answer',
                  text: 'Em pncp.gov.br/app/atas, filtre por objeto, UF e situação "Vigente". Cada ata mostra quantitativos, preços unitários, vigência e órgãos participantes. Para inteligência competitiva, agregar as atas por setor revela quem são os fornecedores cadastrados em cada região.',
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
        da SmartLic. O Sistema de Registro de Preços (SRP) é uma das vias
        mais lucrativas — e mais previsíveis — para empresas B2G. Quem
        domina SRP entende que vencer um pregão SRP não é evento isolado;
        é abrir uma <em>fonte recorrente</em> de receita por 12 a 24
        meses.
      </p>

      <h2>O que muda quando a licitação é SRP</h2>
      <p>
        Em uma licitação tradicional, o órgão licita o que vai comprar
        agora — quantidade certa, prazo certo. Numa licitação SRP, o
        órgão licita preços e condições; a compra efetiva acontece em
        múltiplos momentos durante a vigência da ata. Para a empresa
        vencedora, isso significa três coisas:
      </p>
      <ul>
        <li>
          <strong>Receita previsível</strong> ao longo de 12 meses (com
          eventual prorrogação por mais 12 — limite legal de 24 meses).
        </li>
        <li>
          <strong>Possibilidade de "carona"</strong> — outros órgãos
          podem aderir à ata e comprar, gerando receita adicional sem
          nova disputa.
        </li>
        <li>
          <strong>Entrega parcelada</strong> conforme demanda real do
          órgão, com logística distribuída no tempo.
        </li>
      </ul>

      <h2>Como funciona uma licitação SRP</h2>
      <p>
        O ciclo típico é:
      </p>
      <ol>
        <li>
          <strong>Levantamento de demanda:</strong> o órgão (ou um
          consórcio de órgãos) consolida quantitativos estimados para 12
          meses.
        </li>
        <li>
          <strong>Publicação no PNCP:</strong> edital com objeto,
          quantitativos máximos, vigência da ata e regras de adesão.
        </li>
        <li>
          <strong>Sessão pública:</strong> normalmente em pregão
          eletrônico, com lances pelos preços unitários.
        </li>
        <li>
          <strong>Homologação e assinatura da ata:</strong> a empresa
          vencedora assina a ata e fica registrada como fornecedor pelos
          preços ofertados.
        </li>
        <li>
          <strong>Compras durante a vigência:</strong> o órgão emite
          Ordem de Fornecimento sempre que precisar; a empresa entrega
          conforme as condições da ata.
        </li>
      </ol>

      <h2>Caronas — receita extra sem competir de novo</h2>
      <p>
        A figura do "órgão não participante" — popularmente "carona" —
        permite que órgãos que não participaram da licitação original
        adiram à ata. A Lei 14.133/2021 (art. 86) limita:
      </p>
      <ul>
        <li>
          <strong>50% dos quantitativos da ata</strong> como teto
          agregado para todas as caronas.
        </li>
        <li>
          <strong>100% por carona individual</strong> em relação ao
          quantitativo originalmente comprado pelo órgão participante.
        </li>
        <li>
          <strong>Anuência expressa</strong> do fornecedor antes de
          qualquer carona.
        </li>
      </ul>
      <p>
        Empresas que vencem ata em órgão de grande porte (universidade
        federal, hospital universitário, ministério) frequentemente
        recebem dezenas de pedidos de carona ao longo do ano —
        especialmente se o objeto é de uso geral (TI, escritório,
        material hospitalar). Aceitar carona é decisão da empresa, e
        deve considerar capacidade real de fornecimento.
      </p>

      <h2>Estratégias práticas para vencer pregão SRP</h2>
      <p>
        <strong>Estratégia 1 — Cotação de prazo longo.</strong> Em SRP, o
        preço fica congelado por 12 meses (com cláusulas de revisão
        excepcional). Cotar como se fosse contrato à vista é receita
        para prejuízo. Inclua provisão para inflação, oscilação cambial
        em insumos importados e custo financeiro de capital de giro.
      </p>
      <p>
        <strong>Estratégia 2 — Análise de demanda histórica.</strong>{' '}
        Antes de cotar, pesquise no PNCP atas anteriores do mesmo órgão
        para o mesmo objeto. Veja quanto efetivamente foi comprado vs
        quantitativo registrado — muitos órgãos compram só 30-50% do
        registrado.
      </p>
      <p>
        <strong>Estratégia 3 — Exposição a caronas.</strong> Atas de
        órgãos populares como UF (ministérios), hospitais
        universitários, IFs, exército recebem muitas caronas. Cotar
        considerando essa receita extra pode justificar margem mais
        agressiva.
      </p>

      <h2>Como localizar atas no PNCP</h2>
      <p>
        Em <code>pncp.gov.br/app/atas</code> você encontra a busca de
        atas vigentes. Use:
      </p>
      <ul>
        <li>Objeto (palavra-chave) para descobrir oportunidades de carona.</li>
        <li>UF e órgão para mapear quem detém ata em sua região.</li>
        <li>
          Status "Vigente" — atas vencidas só servem para histórico,
          não para nova compra.
        </li>
      </ul>
      <p>
        O detalhe da ata exibe os preços unitários — informação valiosa
        para construir cotações próprias e para acompanhar concorrentes.
      </p>

      <h2>Sanções por não cumprimento</h2>
      <p>
        Empresa registrada em ata que se recusa injustificadamente a
        entregar pode sofrer:
      </p>
      <ul>
        <li>
          <strong>Multa contratual</strong> conforme percentual do edital
          (tipicamente 10-20% do valor não entregue).
        </li>
        <li>
          <strong>Descredenciamento da ata.</strong>
        </li>
        <li>
          <strong>Impedimento de licitar</strong> de 6 meses a 5 anos
          (art. 156).
        </li>
        <li>
          <strong>Inscrição no CEIS</strong> (Cadastro Nacional de
          Empresas Inidôneas e Suspensas) — torna a empresa inelegível
          em todas as três esferas.
        </li>
      </ul>
      <p>
        Por isso, ao vencer ata, garanta capacidade real de
        fornecimento. Vencer sem entregar é o pior cenário possível.
      </p>

      <BlogInlineCTA
        slug="pncp-registro-precos-como-participar"
        campaign="guias"
        ctaMessage="Encontre atas SRP vigentes para carona."
        ctaText="Começar grátis"
      />

      <h2>Próximos passos no cluster PNCP</h2>
      <p>
        Veja{' '}
        <Link href="/blog/ata-registro-precos-como-escolher">
          ata de registro de preços — como escolher
        </Link>
        ,{' '}
        <Link href="/blog/ata-registro-precos-estrategia-licitacao">
          ata SRP como estratégia
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
