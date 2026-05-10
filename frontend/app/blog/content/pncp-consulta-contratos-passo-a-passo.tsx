import Link from 'next/link';
import BlogInlineCTA from '../components/BlogInlineCTA';

/**
 * PNCP-SPOKE-04 (#992) — PNCP: consulta de contratos passo a passo
 * Cluster: PNCP | Pillar: pncp-guia-completo-empresas
 * Target: ~1100 words | Primary KW: pncp consulta contratos
 */
export default function PncpConsultaContratosPassoAPasso() {
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
                name: 'Como buscar contratos por CNPJ no PNCP?',
                acceptedAnswer: {
                  '@type': 'Answer',
                  text: 'Em pncp.gov.br/app/contratos, use o campo de busca avançada e informe o CNPJ do fornecedor ou do órgão contratante. O portal exibe todos os contratos vinculados, com objeto, valor, vigência e aditivos. Para análise consolidada do histórico, ferramentas especializadas como a SmartLic agregam os mesmos dados em um único perfil de empresa.',
                },
              },
              {
                '@type': 'Question',
                name: 'Quais informações um contrato exibe no PNCP?',
                acceptedAnswer: {
                  '@type': 'Answer',
                  text: 'Número e objeto, CNPJ e razão social do contratado, órgão contratante, modalidade licitatória de origem, valor inicial, datas de assinatura e vigência, situação (vigente, encerrado, rescindido), aditivos e prorrogações. A Lei 14.133/2021 (art. 87 e 174) exige publicação em até 20 dias úteis após a assinatura.',
                },
              },
              {
                '@type': 'Question',
                name: 'É possível filtrar por valor ou UF?',
                acceptedAnswer: {
                  '@type': 'Answer',
                  text: 'Sim — UF, órgão, modalidade, vigência e situação são filtros nativos. Faixa de valor está disponível na API; na interface web é parcial. Para combinações avançadas (setor + UF + valor + período), o uso da API ou de ferramentas como a SmartLic é mais eficiente.',
                },
              },
              {
                '@type': 'Question',
                name: 'O PNCP mostra notas fiscais e ordens de pagamento?',
                acceptedAnswer: {
                  '@type': 'Answer',
                  text: 'A integração com notas fiscais e ordens de pagamento está em fase de adoção. Atualmente a maioria dos contratos exibe apenas o cabeçalho contratual e os aditivos. Para acompanhamento financeiro completo, a fonte ainda é o portal de transparência do próprio órgão.',
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
        da SmartLic. Aqui o foco é o módulo mais subutilizado do portal:
        a consulta de contratos. Bem usado, ele é uma das mais poderosas
        ferramentas de inteligência competitiva B2G no Brasil.
      </p>

      <h2>Por que consultar contratos é tão valioso</h2>
      <p>
        Editais mostram <em>oportunidades futuras</em>. Contratos mostram{' '}
        <em>quem ganhou o quê, com que preço e para quem</em>. Para
        empresas B2G, isso responde a três perguntas centrais:
      </p>
      <ul>
        <li>
          Quem são meus concorrentes reais — não os que aparecem no
          edital, mas os que efetivamente ganham?
        </li>
        <li>
          Que faixa de preço o mercado consegue praticar para esse objeto
          neste órgão?
        </li>
        <li>
          Quais órgãos pagam em dia e quais empilham aditivos sem
          renegociar valor?
        </li>
      </ul>

      <h2>Passo 1 — Acessando o módulo de contratos</h2>
      <p>
        Em <code>pncp.gov.br/app/contratos</code> você encontra a busca
        unificada. Há quatro pontos de partida possíveis:
      </p>
      <ul>
        <li>
          <strong>Por CNPJ contratado:</strong> ver tudo o que uma empresa
          ganhou em compras públicas.
        </li>
        <li>
          <strong>Por CNPJ contratante (órgão):</strong> ver todos os
          contratos de um órgão.
        </li>
        <li>
          <strong>Por palavra-chave no objeto:</strong> ver, por exemplo,
          todos os contratos de "limpeza hospitalar".
        </li>
        <li>
          <strong>Por modalidade e UF:</strong> mapear contratos de
          pregão eletrônico em determinado estado.
        </li>
      </ul>

      <h2>Passo 2 — Lendo a ficha do contrato</h2>
      <p>
        Cada contrato no PNCP exibe os campos obrigatórios da Lei
        14.133/2021. Os mais analiticamente relevantes:
      </p>
      <ul>
        <li>
          <strong>Valor inicial vs valor atualizado:</strong> a diferença
          revela aditivos. Aditivo até 25% (50% para reformas) é legal —
          acima disso indica subdimensionamento e risco contratual.
        </li>
        <li>
          <strong>Vigência:</strong> contratos de serviço continuado podem
          chegar a 10 anos (art. 107). Cumulado com aditivos, isso
          imobiliza o mercado.
        </li>
        <li>
          <strong>Modalidade de origem:</strong> contratos de dispensa
          (art. 75) ou inexigibilidade (art. 74) sinalizam que a empresa
          tem relacionamento direto sem competição — útil para mapear
          fornecedores históricos.
        </li>
        <li>
          <strong>Situação:</strong> rescindidos por inexecução são
          alerta vermelho ao analisar reputação de concorrente.
        </li>
      </ul>

      <h2>Passo 3 — Cruzando dados para inteligência</h2>
      <p>
        A potência do PNCP não é o contrato individual — é o
        cruzamento. Três análises de alto valor:
      </p>
      <p>
        <strong>1. Mapa de player dominante.</strong> Filtre por objeto e
        por UF. Conte quantos contratos cada CNPJ tem. Se um único
        fornecedor concentra mais de 40% dos contratos, há um player
        instalado e sua estratégia precisa ou superá-lo em preço, ou
        diferenciar fortemente em técnica.
      </p>
      <p>
        <strong>2. Histórico de preço.</strong> Para o mesmo objeto, em
        órgãos comparáveis, qual a faixa de valor unitário? Isso
        calibra sua proposta sem chutar.
      </p>
      <p>
        <strong>3. Padrão de aditivos por órgão.</strong> Órgãos que
        sistematicamente fazem aditivos de prazo sem aditar valor são
        bons clientes; órgãos que aditam valor com frequência são sinal
        de subdimensionamento — você cota mais conservador.
      </p>

      <h2>Passo 4 — Exportando dados em volume</h2>
      <p>
        A interface web limita análises em massa. Para volumes maiores,
        use a API pública do PNCP — disponível em{' '}
        <code>pncp.gov.br/api/consulta/v1/contratos</code>. A API aceita
        filtros por período, UF, modalidade e CNPJ, retornando até 50
        registros por página em formato JSON. Para empresas que
        construirão dashboards próprios, é o caminho. Detalhes no spoke{' '}
        <Link href="/blog/pncp-api-integracao-empresas">
          API do PNCP — integração e automação
        </Link>
        .
      </p>

      <h2>Limitações e como contorná-las</h2>
      <p>
        Três limitações conhecidas do módulo de contratos do PNCP:
      </p>
      <ul>
        <li>
          <strong>Cobertura ainda parcial em municípios pequenos.</strong>{' '}
          Municípios com menos de 50 mil habitantes têm prazo estendido
          até 2026 para integração total. Para esses, complemente com o
          portal de transparência local.
        </li>
        <li>
          <strong>Atraso de publicação.</strong> Embora a lei exija 20
          dias úteis, parte dos órgãos publica próximo do limite. Faça a
          análise com defasagem de 30-45 dias para ter base completa.
        </li>
        <li>
          <strong>Dados estruturados x objeto descritivo.</strong> O
          campo "objeto" é texto livre — diferentes órgãos descrevem o
          mesmo serviço de formas distintas. Use busca por palavra-chave
          ampla e refine.
        </li>
      </ul>

      <h2>Casos de uso recorrentes em empresas B2G</h2>
      <p>
        <strong>Caso 1 — Avaliação pré-licitação:</strong> antes de
        decidir se vale disputar um pregão, busque os contratos similares
        do mesmo órgão nos últimos 24 meses. Veja quem ganhou e em que
        faixa de preço. Se você não consegue chegar a 95% do menor preço
        praticado, talvez não valha entrar.
      </p>
      <p>
        <strong>Caso 2 — Inteligência de concorrente.</strong> Pegue o
        CNPJ do principal concorrente e liste seus contratos vigentes.
        Você descobre nichos onde ele não atua e pode ser o primeiro
        movimento.
      </p>
      <p>
        <strong>Caso 3 — Argumentação em recurso administrativo.</strong>{' '}
        Em recurso por preço inexequível, contratos históricos do PNCP
        servem como prova objetiva de que aquele valor está fora da
        faixa praticada — uso reconhecido por TCE e TCU.
      </p>

      <BlogInlineCTA
        slug="pncp-consulta-contratos-passo-a-passo"
        campaign="guias"
        ctaMessage="Inteligência de contratos PNCP por CNPJ em segundos."
        ctaText="Ver demonstração"
      />

      <h2>Próximos passos no cluster PNCP</h2>
      <p>
        Veja{' '}
        <Link href="/blog/como-consultar-contratos-publicos-pncp">
          consulta de contratos públicos no PNCP — visão geral
        </Link>
        ,{' '}
        <Link href="/blog/pncp-api-integracao-empresas">
          API do PNCP — integração e automação
        </Link>
        , e o{' '}
        <Link href="/blog/pncp-guia-completo-empresas">
          Guia Completo do PNCP
        </Link>
        .
      </p>
    </>
  );
}
