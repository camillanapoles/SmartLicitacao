import Link from 'next/link';
import BlogInlineCTA from '../components/BlogInlineCTA';

/**
 * PNCP-SPOKE-03 (#992) — PNCP vs ComprasGov
 * Cluster: PNCP | Pillar: pncp-guia-completo-empresas
 * Target: ~1080 words | Primary KW: pncp vs comprasgov
 */
export default function PncpVsComprasgovDiferencas() {
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
                name: 'PNCP e ComprasGov são a mesma coisa?',
                acceptedAnswer: {
                  '@type': 'Answer',
                  text: 'Não. PNCP (Portal Nacional de Contratações Públicas) é um portal de divulgação obrigatório para toda compra pública do país (Lei 14.133/2021). ComprasGov é a plataforma operacional do governo federal — onde os pregões da União são realizados. ComprasGov publica no PNCP; o inverso não é verdade.',
                },
              },
              {
                '@type': 'Question',
                name: 'Estados e municípios usam ComprasGov?',
                acceptedAnswer: {
                  '@type': 'Answer',
                  text: 'Em regra, não. O ComprasGov é o sistema do Executivo Federal. Estados e municípios usam plataformas próprias — BLL Compras, Licitanet, BNC Compras Públicas, ComprasNet de cada estado etc. Todas obrigatoriamente integradas ao PNCP. O PNCP é o agregador unificado.',
                },
              },
              {
                '@type': 'Question',
                name: 'Para participar de pregão municipal, preciso me cadastrar onde?',
                acceptedAnswer: {
                  '@type': 'Answer',
                  text: 'Na plataforma operacional indicada no edital — pode ser BLL, Licitanet, BNC, ComprasNet do estado etc. O PNCP serve apenas para descoberta e leitura do edital. A entrega da proposta e os lances sempre acontecem na plataforma operacional escolhida pelo órgão.',
                },
              },
              {
                '@type': 'Question',
                name: 'O PNCP vai substituir o ComprasGov?',
                acceptedAnswer: {
                  '@type': 'Answer',
                  text: 'Não. PNCP e ComprasGov coexistem por desenho — o primeiro é portal de transparência e descoberta; o segundo é sistema operacional. A Lei 14.133/2021 deixa claro que o PNCP centraliza divulgação, mas cada ente federativo continua livre para escolher sua plataforma operacional.',
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
        da SmartLic. PNCP e ComprasGov são confundidos com frequência — a
        diferença é simples, mas decisiva para qualquer empresa B2G.
      </p>

      <h2>Resumo em uma frase</h2>
      <p>
        <strong>PNCP é o portal de transparência</strong> obrigatório
        criado pela Lei 14.133/2021; <strong>ComprasGov é o sistema
        operacional</strong> usado pelo governo federal para conduzir
        pregões e dispensas. Eles têm finalidades diferentes, e empresas
        precisam de ambos — o primeiro para descobrir oportunidades, o
        segundo (ou equivalentes estaduais e municipais) para participar.
      </p>

      <h2>O que é cada um</h2>
      <h3>PNCP — Portal Nacional de Contratações Públicas</h3>
      <p>
        Criado pelo art. 174 da Lei 14.133/2021 e regulamentado pelo
        Decreto 10.764/2021, o PNCP é o ponto único de divulgação
        obrigatória de:
      </p>
      <ul>
        <li>Editais de licitação, dispensa e inexigibilidade.</li>
        <li>Atas de registro de preços.</li>
        <li>Contratos firmados, aditivos e prorrogações.</li>
        <li>Notas fiscais e ordens de pagamento (em fase de adoção).</li>
      </ul>
      <p>
        A obrigatoriedade vale para União, estados, Distrito Federal e
        municípios — toda a administração direta, autárquica e
        fundacional. Empresas estatais também publicam, embora com regime
        próprio (Lei 13.303/2016).
      </p>

      <h3>ComprasGov — Sistema operacional do Executivo Federal</h3>
      <p>
        Disponível em <code>compras.gov.br</code>, o ComprasGov é o
        ambiente onde:
      </p>
      <ul>
        <li>Órgãos federais publicam pregões eletrônicos próprios.</li>
        <li>
          Empresas se cadastram, enviam propostas e dão lances em pregões
          da União.
        </li>
        <li>
          O SICAF (Sistema de Cadastramento Unificado de Fornecedores) é
          mantido — o cadastro de fornecedores federal.
        </li>
      </ul>
      <p>
        O ComprasGov é gerido pela Secretaria de Gestão e Inovação (SEGES)
        do Ministério da Gestão. É o sucessor histórico do
        ComprasNet/SIASG.
      </p>

      <h2>Cobertura geográfica e de modalidades</h2>
      <p>
        Esta é a confusão mais comum: muita empresa pensa que ComprasGov
        cobre o país inteiro. Não cobre.
      </p>
      <ul>
        <li>
          <strong>ComprasGov:</strong> apenas órgãos federais. Cobertura
          nacional, mas{' '}
          <em>vertical</em> — ou seja, só União.
        </li>
        <li>
          <strong>PNCP:</strong> todos os entes federativos. Cobertura
          nacional <em>e horizontal</em> — União, estados, municípios.
        </li>
      </ul>
      <p>
        Estados e municípios usam plataformas operacionais próprias —{' '}
        <strong>BLL Compras</strong> (mais comum em Sul e Sudeste),{' '}
        <strong>Licitanet</strong>, <strong>BNC Compras Públicas</strong>,{' '}
        <strong>ComprasNet de cada estado</strong>, <strong>Bolsa
        Brasileira de Mercadorias</strong>, entre outras. Cada uma exige
        cadastro próprio. Mas todas, sem exceção, publicam no PNCP — o
        que torna o PNCP o ponto de partida correto para qualquer
        descoberta de oportunidade.
      </p>

      <h2>Quando usar cada um na rotina B2G</h2>
      <p>
        <strong>Use o PNCP para:</strong>
      </p>
      <ul>
        <li>Descobrir editais novos diariamente.</li>
        <li>Comparar contratos e preços históricos por CNPJ ou órgão.</li>
        <li>
          Investigar concorrentes — quem ganhou, em que valor, em que
          modalidade.
        </li>
        <li>Acessar a {''}
          <Link href="/blog/pncp-api-integracao-empresas">
            API pública para automação
          </Link>
          .
        </li>
      </ul>
      <p>
        <strong>Use o ComprasGov (ou plataforma equivalente) para:</strong>
      </p>
      <ul>
        <li>Cadastrar a empresa no SICAF.</li>
        <li>Enviar proposta em pregões da União.</li>
        <li>Dar lances na sessão pública.</li>
        <li>Receber recursos administrativos no sistema.</li>
      </ul>

      <h2>O cadastro: SICAF vs cadastros estaduais e municipais</h2>
      <p>
        Empresas que querem atuar nacionalmente precisam de mais de um
        cadastro:
      </p>
      <ul>
        <li>
          <strong>SICAF</strong> — federal, no ComprasGov. Necessário para
          pregões da União.
        </li>
        <li>
          <strong>Cadastros estaduais/municipais</strong> — varia por
          ente. Alguns aceitam o SICAF como suficiente; outros exigem
          cadastro próprio (CRC do TCE, por exemplo).
        </li>
        <li>
          <strong>Plataformas privadas</strong> — BLL, Licitanet, BNC etc.
          exigem cadastro próprio para participar dos pregões hospedados
          ali.
        </li>
      </ul>
      <p>
        Empresas iniciantes erram aqui constantemente — fazem só o SICAF e
        descobrem na hora do lance que precisariam ter cadastro na BLL,
        feito com 24h de antecedência.
      </p>

      <h2>O futuro: convergência com ressalvas</h2>
      <p>
        O Decreto 11.462/2023 e a evolução do PNCP sinalizam que, no
        médio prazo, parte do fluxo operacional pode migrar para o
        próprio PNCP, que já oferece módulos para dispensa eletrônica em
        municípios sem plataforma própria. Mas não há prazo para
        substituir as plataformas privadas, e a tendência é PNCP +
        ecossistema diversificado de operacionais.
      </p>

      <BlogInlineCTA
        slug="pncp-vs-comprasgov-diferencas"
        campaign="guias"
        ctaMessage="PNCP unifica ComprasGov, BLL, Licitanet e mais."
        ctaText="Testar grátis"
      />

      <h2>Próximos passos no cluster PNCP</h2>
      <p>
        Aprofunde com{' '}
        <Link href="/blog/pncp-api-integracao-empresas">
          API do PNCP — integração e automação
        </Link>
        ,{' '}
        <Link href="/blog/pncp-modalidade-pregao-eletronico">
          PNCP e pregão eletrônico
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
