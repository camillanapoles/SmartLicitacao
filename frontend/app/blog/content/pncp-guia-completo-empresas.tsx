import Link from 'next/link';
import BlogInlineCTA from '../components/BlogInlineCTA';
import PncpHubPanel from '@/components/blog/hubs/PncpHubPanel';

/**
 * T3: PNCP na prática — Hub de editais, contratos e fornecedores públicos
 *
 * PSEO-HUB-002: Transformado em hub utilitário com dados reais acima da dobra.
 * Target: 3,000+ words | Cluster: guias transversais
 * Primary keyword: pncp licitações
 */
export default function PncpGuiaCompletoEmpresas() {
  return (
    <>
      {/* Hub PNCP — acima da dobra com dados reais e CTAs (PSEO-HUB-002) */}
      <PncpHubPanel />
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
                name: 'O PNCP é obrigatório para todos os órgãos?',
                acceptedAnswer: {
                  '@type': 'Answer',
                  text: 'A obrigatoriedade de publicação no PNCP foi implementada de forma escalonada. Desde abril de 2023, todos os órgãos e entidades da administração federal direta, autarquias e fundações são obrigados a publicar no PNCP. Para estados e municípios de grande porte (acima de 50 mil habitantes), a obrigatoriedade entrou em vigor entre 2024 e 2025. Municípios de pequeno porte têm prazos estendidos até 2026. Na prática, a cobertura ainda é parcial — nem todos os municípios publicam no PNCP, o que exige busca complementar em portais estaduais e Diários Oficiais locais.',
                },
              },
              {
                '@type': 'Question',
                name: 'Posso baixar editais gratuitamente no PNCP?',
                acceptedAnswer: {
                  '@type': 'Answer',
                  text: 'Sim. O PNCP é uma plataforma pública e gratuita. Todos os editais, termos de referência, atas de registro de preços e contratos publicados no portal podem ser acessados e baixados sem custo e sem necessidade de cadastro. Basta acessar pncp.gov.br, buscar o edital desejado por palavra-chave, UF ou modalidade, e clicar para baixar os documentos anexados. A Lei 14.133/2021 (art. 174) garante o acesso público irrestrito a essas informações.',
                },
              },
              {
                '@type': 'Question',
                name: 'Qual a diferença entre PNCP e ComprasNet?',
                acceptedAnswer: {
                  '@type': 'Answer',
                  text: 'O PNCP e o ComprasNet (agora Compras.gov.br) têm funções complementares. O PNCP é o portal de publicação e transparência — centraliza editais, contratos e atas de todos os entes federativos (federal, estadual e municipal). O Compras.gov.br é o portal de operação — é onde os pregões eletrônicos do governo federal são efetivamente realizados (envio de propostas, fase de lances, habilitação). O fornecedor consulta o PNCP para encontrar editais e acessa o Compras.gov.br para participar do pregão. Para licitações estaduais e municipais, cada ente pode usar portais de operação diferentes (BEC-SP, Portal de Compras Públicas, Licitanet, etc.).',
                },
              },
              {
                '@type': 'Question',
                name: 'O PNCP envia alertas de novos editais?',
                acceptedAnswer: {
                  '@type': 'Answer',
                  text: 'O PNCP não possui, até abril de 2026, um sistema nativo de alertas por e-mail ou notificação push para novos editais. A busca é manual: o usuário precisa acessar o portal, inserir filtros e verificar os resultados periodicamente. Essa é uma das limitações mais apontadas por fornecedores. Ferramentas complementares como o SmartLic preenchem essa lacuna, oferecendo monitoramento automatizado com busca multi-fonte (PNCP + Portal de Compras Públicas + ComprasGov), classificação por setor e notificações de novas oportunidades.',
                },
              },
              {
                '@type': 'Question',
                name: 'Consigo ver resultados de licitações no PNCP?',
                acceptedAnswer: {
                  '@type': 'Answer',
                  text: 'Sim, parcialmente. O PNCP publica atas de julgamento, resultados de licitações e contratos firmados. É possível consultar quem venceu determinada licitação, o valor contratado e os termos do contrato. No entanto, a navegação entre o edital original e o resultado nem sempre é intuitiva — muitas vezes é necessário buscar o contrato separadamente. Os dados de resultados também dependem da publicação pelo órgão responsável, que nem sempre é feita de forma tempestiva.',
                },
              },
              {
                '@type': 'Question',
                name: 'A API do PNCP é gratuita?',
                acceptedAnswer: {
                  '@type': 'Answer',
                  text: 'Sim. A API do PNCP (disponível em pncp.gov.br/api) é pública e gratuita, sem necessidade de autenticação para consultas básicas. A API permite buscar contratações por data de publicação, UF, modalidade e outros filtros. Há limitações técnicas: o tamanho máximo de página é 50 registros por requisição, e o período de busca recomendado é de 10 a 15 dias por consulta. A API é utilizada por ferramentas de inteligência em licitações como o SmartLic para automatizar a busca e o monitoramento de editais em escala.',
                },
              },
            ],
          }),
        }}
      />

      {/* HowTo JSON-LD — 8 steps */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            '@context': 'https://schema.org',
            '@type': 'HowTo',
            name: 'Como Buscar e Monitorar Editais no PNCP',
            description:
              'Guia passo a passo com 8 etapas para empresas usarem o PNCP (Portal Nacional de Contratações Públicas) para buscar, filtrar e acompanhar editais de licitação.',
            totalTime: 'PT30M',
            step: [
              {
                '@type': 'HowToStep',
                position: 1,
                name: 'Acessar o PNCP',
                text: 'Acesse pncp.gov.br pelo navegador. O portal é público e não exige cadastro para consultar editais. A página inicial apresenta um campo de busca e filtros rápidos por modalidade e data.',
              },
              {
                '@type': 'HowToStep',
                position: 2,
                name: 'Buscar editais por palavra-chave',
                text: 'No campo de busca, insira termos relacionados ao objeto de interesse (ex.: "manutenção predial", "software de gestão", "material hospitalar"). O PNCP utiliza busca textual nos dados de descrição do objeto e do órgão licitante.',
              },
              {
                '@type': 'HowToStep',
                position: 3,
                name: 'Filtrar por UF, modalidade e data',
                text: 'Utilize os filtros laterais para refinar os resultados: selecione a UF (ou múltiplas UFs), escolha a modalidade (pregão, concorrência, dispensa) e defina o período de publicação. Filtros combinados reduzem o ruído e concentram os resultados em oportunidades relevantes.',
              },
              {
                '@type': 'HowToStep',
                position: 4,
                name: 'Analisar detalhes do edital',
                text: 'Clique em um resultado para ver os detalhes: órgão licitante, objeto, valor estimado (quando disponível), data de abertura, modalidade, critério de julgamento e documentos anexados. Avalie se o edital é compatível com o CNAE, porte e região de atuação da empresa.',
              },
              {
                '@type': 'HowToStep',
                position: 5,
                name: 'Baixar documentos do edital',
                text: 'Na página de detalhes, acesse os documentos anexados: edital completo, termo de referência, planilha de itens e eventuais adendos. Todos os documentos são gratuitos para download. O termo de referência contém as especificações técnicas detalhadas do objeto.',
              },
              {
                '@type': 'HowToStep',
                position: 6,
                name: 'Configurar rotina de monitoramento',
                text: 'Como o PNCP não possui alertas nativos, estabeleça uma rotina de busca periódica (diária ou semanal). Salve seus filtros favoritos e acesse o portal nos mesmos horários. Alternativamente, utilize ferramentas que automatizam essa busca, como o SmartLic.',
              },
              {
                '@type': 'HowToStep',
                position: 7,
                name: 'Acompanhar resultados e atas',
                text: 'Após a data de abertura, retorne ao PNCP para verificar o resultado da licitação. O portal publica atas de julgamento, contratos firmados e valores contratados. Esses dados são valiosos para calibrar preços em futuras participações.',
              },
              {
                '@type': 'HowToStep',
                position: 8,
                name: 'Usar a API do PNCP para automação',
                text: 'Para quem busca em volume, a API do PNCP (pncp.gov.br/api) permite consultas programáticas. Busque contratações por data, UF e modalidade. Limite de 50 registros por página. A API é gratuita e não exige autenticação para consultas básicas.',
              },
            ],
          }),
        }}
      />

      {/* Opening paragraph — must contain primary keyword */}
      <p className="text-base sm:text-xl leading-relaxed text-ink">
        O <strong>PNCP</strong> (Portal Nacional de Contratações Públicas) é
        a plataforma oficial criada pela Lei 14.133/2021 para centralizar a
        publicação de editais, contratos e atas de licitação de todos os entes
        federativos — União, estados e municípios. Para empresas que vendem
        para o governo, saber <strong>como usar o PNCP</strong> é tão
        fundamental quanto ter o cadastro no SICAF atualizado: é a ferramenta
        que reúne as oportunidades em um único lugar, substituindo a navegação
        fragmentada por dezenas de Diários Oficiais e portais estaduais. Este
        guia mostra, passo a passo, como buscar editais, usar cada filtro
        disponível, entender as limitações do portal e complementar a busca com
        ferramentas de automação.
      </p>

      <h2>O que é o PNCP e por que importa</h2>

      <p>
        O PNCP foi criado pelo art. 174 da Lei 14.133/2021 como o &quot;sítio
        eletrônico oficial destinado à divulgação centralizada e obrigatória dos
        atos exigidos por esta Lei&quot;. Na prática, é o portal onde órgãos
        públicos federais, estaduais e municipais publicam seus editais de
        licitação, contratos firmados, atas de registro de preços e resultados
        de certames. Antes do PNCP, uma empresa que quisesse monitorar
        licitações em todo o Brasil precisava navegar por centenas de portais
        diferentes: Diário Oficial da União, Diários Oficiais estaduais (27),
        portais municipais e plataformas privadas de pregão.
      </p>

      <p>
        O PNCP resolve parcialmente esse problema ao criar um ponto único de
        consulta. A palavra &quot;parcialmente&quot; é importante: como veremos
        adiante, a cobertura do portal ainda não é total, especialmente para
        municípios de pequeno porte. Mas para editais federais e de estados de
        grande porte, o PNCP já é a fonte mais completa disponível. Em termos
        de volume, o portal registra dezenas de milhares de publicações
        mensais — um fluxo de dados que seria impossível monitorar manualmente
        sem ferramentas de busca e triagem.
      </p>

      <h2>Quem publica no PNCP — obrigatoriedade escalonada</h2>

      <p>
        A obrigatoriedade de publicação no PNCP foi implementada de forma
        gradual, respeitando a capacidade técnica dos diferentes entes
        federativos:
      </p>

      <div className="not-prose my-6 sm:my-8 bg-surface-1 border border-[var(--border)] rounded-lg p-4 sm:p-6">
        <p className="text-sm font-semibold text-ink mb-3">
          Cronograma de obrigatoriedade do PNCP
        </p>
        <ul className="space-y-2 text-sm text-ink-secondary">
          <li>
            • <strong>Abril 2023:</strong> Órgãos e entidades da administração
            federal direta, autarquias e fundações federais
          </li>
          <li>
            • <strong>2024:</strong> Estados, Distrito Federal e municípios com
            mais de 50 mil habitantes
          </li>
          <li>
            • <strong>2025-2026:</strong> Municípios de pequeno porte (abaixo de
            50 mil habitantes) — implementação progressiva
          </li>
          <li>
            • <strong>Exceção:</strong> Empresas públicas e sociedades de
            economia mista seguem cronograma específico
          </li>
        </ul>
      </div>

      <p>
        O impacto prático para fornecedores é direto: se você busca editais
        federais, o PNCP é completo. Para editais estaduais de estados como
        São Paulo, Minas Gerais, Rio de Janeiro, Paraná e Rio Grande do Sul,
        a cobertura é boa, mas não exaustiva. Para municípios de pequeno porte,
        a publicação no PNCP ainda é inconsistente — muitos continuam
        utilizando apenas Diários Oficiais locais ou portais estaduais. Essa
        fragmentação é a principal razão pela qual ferramentas que agregam
        múltiplas fontes (PNCP + Portal de Compras Públicas + ComprasGov)
        oferecem cobertura superior à busca apenas no PNCP.
      </p>

      <h2>Como buscar editais passo a passo</h2>

      <h3>Passo 1 — Acessar o portal</h3>

      <p>
        Acesse <strong>pncp.gov.br</strong> pelo navegador. O portal é público
        e gratuito — não exige cadastro, login ou certificado digital para
        consultar editais. A página inicial apresenta um campo de busca
        centralizado e opções de filtro rápido. A navegação é responsiva e
        funciona em dispositivos móveis, embora a experiência desktop seja mais
        completa para consultas detalhadas.
      </p>

      <h3>Passo 2 — Buscar por palavra-chave</h3>

      <p>
        O campo de busca aceita termos relacionados ao objeto da licitação. A
        busca é textual e opera sobre os campos de descrição do objeto e dados
        do órgão licitante. Exemplos de buscas eficazes: &quot;manutenção
        predial&quot;, &quot;software de gestão hospitalar&quot;, &quot;material
        de escritório&quot;, &quot;serviço de limpeza&quot;. Dicas para
        melhorar os resultados: use termos específicos do setor (não genéricos),
        teste variações (singular/plural, com e sem acento) e combine com
        filtros para reduzir o volume.
      </p>

      <h3>Passo 3 — Aplicar filtros</h3>

      <p>
        Os filtros disponíveis no PNCP permitem refinar os resultados por
        múltiplos critérios. Combiná-los corretamente é a diferença entre
        encontrar 5 editais relevantes ou navegar por 500 irrelevantes.
      </p>

      <h3>Passo 4 — Analisar detalhes do edital</h3>

      <p>
        Ao clicar em um resultado, a página de detalhes exibe: órgão licitante
        (nome e CNPJ), objeto (descrição resumida), valor estimado (quando
        não sigiloso — conforme art. 24 da{' '}
        <Link href="/blog/lei-14133-guia-fornecedores">Lei 14.133/2021</Link>),
        data de publicação e data de abertura, modalidade e critério de
        julgamento, e links para documentos anexados. Avalie rapidamente se o{' '}
        <Link href="/glossario#edital">edital</Link> é compatível com seu
        CNAE, valor de operação e região antes de investir tempo na leitura
        completa.
      </p>

      <h3>Passo 5 — Baixar documentos</h3>

      <p>
        Os documentos anexados ao edital — incluindo o{' '}
        <Link href="/glossario#termo-de-referencia">termo de referência</Link>,
        a planilha de itens e eventuais adendos — estão disponíveis para
        download gratuito na página de detalhes. O termo de referência é o
        documento mais importante: contém as especificações técnicas detalhadas,
        os critérios de habilitação e as condições de execução. Para editais de
        engenharia, o projeto básico ou executivo também costuma estar anexado.
      </p>

      <BlogInlineCTA
        slug="pncp-guia-completo-empresas"
        campaign="guias"
        ctaHref="/explorar"
        ctaText="Explorar licitações grátis"
        ctaMessage="Descubra editais abertos no seu setor — busca gratuita"
      />

      <h2>Filtros disponíveis e como usar cada um</h2>

      <p>
        O PNCP oferece um conjunto de filtros que, quando usados corretamente,
        transformam uma busca caótica em uma triagem eficiente. Conhecer cada
        filtro e suas limitações é essencial:
      </p>

      <div className="not-prose my-6 sm:my-8 bg-surface-1 border border-[var(--border)] rounded-lg p-4 sm:p-6">
        <p className="text-sm font-semibold text-ink mb-3">
          Filtros do PNCP e recomendações de uso
        </p>
        <ul className="space-y-3 text-sm text-ink-secondary">
          <li>
            <strong>UF (Unidade Federativa):</strong> Filtra por estado do
            órgão licitante. Essencial para empresas que atuam regionalmente.
            Não há filtro por município específico — uma limitação relevante
            para quem atua em mercados locais.
          </li>
          <li>
            <strong>Modalidade:</strong> Pregão eletrônico, concorrência,
            dispensa, inexigibilidade, diálogo competitivo, leilão e concurso.
            Para iniciantes, filtre por &quot;pregão eletrônico&quot; e
            &quot;dispensa eletrônica&quot; — são as modalidades mais acessíveis.
          </li>
          <li>
            <strong>Data de publicação:</strong> Período em que o edital foi
            publicado. O PNCP permite selecionar intervalos de data. Para
            monitoramento diário, busque pelos últimos 1-3 dias. Para análise
            de mercado, expanda para 30-90 dias.
          </li>
          <li>
            <strong>Esfera:</strong> Federal, estadual ou municipal. Útil para
            segmentar a busca por nível de governo.
          </li>
          <li>
            <strong>Situação:</strong> Aberta, encerrada, suspensa, anulada.
            Para buscar oportunidades ativas, filtre por &quot;aberta&quot;.
            Para análise de preços e concorrência, consulte licitações
            encerradas.
          </li>
          <li>
            <strong>Valor estimado:</strong> Quando disponível (o orçamento pode
            ser sigiloso). Útil para descartar rapidamente editais fora da faixa
            de valor compatível com a operação da empresa.
          </li>
        </ul>
      </div>

      <p>
        Uma limitação importante: o PNCP não permite salvar buscas ou receber
        notificações. Cada consulta precisa ser refeita manualmente. Para
        empresas que monitoram editais diariamente, essa limitação impacta
        diretamente a produtividade da equipe de licitações.
      </p>

      <h2>Limitações do PNCP — o que ele não faz</h2>

      <p>
        Embora seja um avanço significativo em relação ao cenário anterior, o
        PNCP tem limitações que todo fornecedor precisa conhecer para não
        depender exclusivamente do portal:
      </p>

      <div className="not-prose my-6 sm:my-8 bg-surface-1 border border-[var(--border)] rounded-lg p-4 sm:p-6">
        <p className="text-sm font-semibold text-ink mb-3">
          Limitações do PNCP em 2026
        </p>
        <ul className="space-y-3 text-sm text-ink-secondary">
          <li>
            <strong>Sem alertas ou notificações:</strong> Não há sistema de
            alerta por e-mail, push ou RSS. A busca é 100% manual.
          </li>
          <li>
            <strong>Cobertura municipal incompleta:</strong> Muitos municípios
            de pequeno porte ainda não publicam no PNCP. Editais podem estar
            apenas em Diários Oficiais locais.
          </li>
          <li>
            <strong>Sem classificação por setor:</strong> O PNCP não classifica
            editais por setor de atuação. A busca é por palavra-chave —
            genérica e com alto volume de resultados irrelevantes.
          </li>
          <li>
            <strong>Sem análise de viabilidade:</strong> O portal exibe os
            dados brutos do edital, sem nenhuma camada de análise sobre
            viabilidade, risco ou adequação ao perfil da empresa.
          </li>
          <li>
            <strong>Navegação fragmentada:</strong> A correlação entre edital,
            resultado e contrato nem sempre é intuitiva. Encontrar o resultado
            de uma licitação específica pode exigir buscas separadas.
          </li>
          <li>
            <strong>Sem histórico de preços integrado:</strong> Embora contratos
            estejam publicados, não há ferramenta de análise de preços ou
            benchmark integrada ao portal.
          </li>
          <li>
            <strong>Sem filtro por município:</strong> O filtro geográfico mais
            granular é por UF. Não é possível buscar editais de um município
            específico diretamente.
          </li>
        </ul>
      </div>

      <p>
        Essas limitações não diminuem a importância do PNCP — o portal é a
        fonte primária de dados e a base sobre a qual ferramentas complementares
        operam. Mas explicam por que fornecedores que dependem exclusivamente
        do PNCP para monitorar oportunidades inevitavelmente perdem editais
        relevantes.
      </p>

      <h2>PNCP vs outros portais — comparação prática</h2>

      <p>
        O ecossistema de portais de compras públicas no Brasil é complexo.
        Entender o papel de cada portal evita confusão e garante cobertura
        adequada:
      </p>

      <div className="not-prose my-6 sm:my-8 bg-surface-1 border border-[var(--border)] rounded-lg p-4 sm:p-6">
        <p className="text-sm font-semibold text-ink mb-3">
          Comparação entre portais de licitação
        </p>
        <ul className="space-y-3 text-sm text-ink-secondary">
          <li>
            <strong>PNCP (pncp.gov.br):</strong> Publicação e transparência.
            Centraliza editais de todos os entes. Gratuito. Não realiza pregões.
          </li>
          <li>
            <strong>Compras.gov.br (ex-ComprasNet):</strong> Operação de pregões
            federais. É onde os pregões do governo federal são realizados. Exige
            cadastro e e-CNPJ.
          </li>
          <li>
            <strong>BEC-SP:</strong> Bolsa Eletrônica de Compras do estado de
            São Paulo. Operação de pregões e cotações estaduais de SP. Maior
            volume estadual.
          </li>
          <li>
            <strong>Portal de Compras Públicas:</strong> Portal privado utilizado
            por centenas de municípios e alguns estados para realizar pregões.
            Acesso gratuito para fornecedores.
          </li>
          <li>
            <strong>Licitanet, BLL, LicitaRio:</strong> Portais privados
            credenciados para operação de pregões municipais e estaduais.
          </li>
          <li>
            <strong>ComprasGov (dadosabertos.compras.gov.br):</strong> Portal de
            dados abertos de compras do governo federal. Oferece API para
            consultas programáticas.
          </li>
        </ul>
      </div>

      <p>
        A regra prática é: consulte o <Link href="/glossario#pncp">PNCP</Link>{' '}
        para encontrar editais, mas participe do pregão no portal específico
        indicado no edital (Compras.gov.br, BEC, Portal de Compras Públicas,
        etc.). Para cobertura máxima, a busca precisa abranger múltiplos portais
        — o que, feito manualmente, consome horas diárias. Conforme detalhamos
        no guia sobre{' '}
        <Link href="/blog/como-participar-primeira-licitacao-2026">
          como participar da primeira licitação em 2026
        </Link>, a automação dessa busca multi-fonte é o que separa equipes
        eficientes de equipes sobrecarregadas.
      </p>

      <h2>API do PNCP: para quem quer automatizar</h2>

      <p>
        O PNCP oferece uma API pública e gratuita (acessível em
        pncp.gov.br/api) que permite buscar contratações de forma programática.
        A API é utilizada por desenvolvedores, consultorias e plataformas de
        inteligência em licitações para automatizar o monitoramento de editais
        em escala.
      </p>

      <h3>Endpoints principais</h3>

      <p>
        A API do PNCP expõe endpoints de consulta para contratações (editais),
        contratos, atas de registro de preços e órgãos. O endpoint mais utilizado
        por fornecedores é o de consulta de contratações, que permite buscar por
        data de publicação, UF, modalidade e outros filtros.
      </p>

      <div className="not-prose my-6 sm:my-8 bg-surface-1 border border-[var(--border)] rounded-lg p-4 sm:p-6">
        <p className="text-sm font-semibold text-ink mb-3">
          Características da API do PNCP
        </p>
        <ul className="space-y-2 text-sm text-ink-secondary">
          <li>
            • <strong>Autenticação:</strong> Não é necessária para consultas
            básicas de contratações
          </li>
          <li>
            • <strong>Formato:</strong> JSON (REST API)
          </li>
          <li>
            • <strong>Paginação:</strong> Máximo de 50 registros por requisição
            (parâmetro tamanhoPagina). Valores acima de 50 retornam erro HTTP 400
          </li>
          <li>
            • <strong>Filtros disponíveis:</strong> Data de publicação, UF,
            modalidade de contratação, esfera, código do órgão
          </li>
          <li>
            • <strong>Rate limiting:</strong> Não documentado oficialmente, mas
            requisições excessivas podem resultar em bloqueio temporário
          </li>
          <li>
            • <strong>Disponibilidade:</strong> Geralmente estável, com eventuais
            períodos de manutenção. Sem SLA formal para uso externo
          </li>
        </ul>
      </div>

      <h3>Limitações técnicas da API</h3>

      <p>
        Para quem planeja integrar a API do PNCP em sistemas automatizados,
        há limitações importantes. O limite de 50 registros por página foi
        reduzido em fevereiro de 2026 (antes era 500), exigindo mais requisições
        para cobrir grandes volumes. A API não oferece busca por texto livre
        (full-text search) — a filtragem por palavras-chave precisa ser feita
        no lado do cliente, após o download dos dados. Também não há webhook
        ou mecanismo de push para novos editais: a única forma de monitorar
        é fazendo polling periódico.
      </p>

      <p>
        Essas limitações técnicas são a razão pela qual plataformas como o{' '}
        <Link href="/features">SmartLic</Link> implementam camadas adicionais
        sobre a API do PNCP: ingestão periódica dos dados para um banco local
        (com busca full-text em português), classificação por setor via
        inteligência artificial e avaliação de viabilidade automática — funcionalidades
        que a API bruta não oferece. Para entender como a{' '}
        <Link href="/blog/inteligencia-artificial-licitacoes-como-funciona">
          inteligência artificial complementa o PNCP na triagem de editais
        </Link>, consulte nosso artigo dedicado.
      </p>

      <h2>Ferramentas que complementam o PNCP</h2>

      <p>
        O PNCP é a base — a fonte oficial de dados. Mas para transformar dados
        brutos em oportunidades qualificadas, ferramentas complementares são
        necessárias. O mercado de inteligência em licitações cresceu
        significativamente desde a entrada em vigor do PNCP, com soluções que
        atacam as lacunas do portal:
      </p>

      <div className="not-prose my-6 sm:my-8 bg-surface-1 border border-[var(--border)] rounded-lg p-4 sm:p-6">
        <p className="text-sm font-semibold text-ink mb-3">
          O que ferramentas de inteligência adicionam ao PNCP
        </p>
        <ul className="space-y-3 text-sm text-ink-secondary">
          <li>
            <strong>Busca multi-fonte:</strong> Agregam PNCP + Portal de
            Compras Públicas + ComprasGov + portais estaduais, eliminando a
            necessidade de consultar múltiplos portais manualmente.
          </li>
          <li>
            <strong>Classificação por setor:</strong> Categorizam editais por
            setor de atuação (TI, engenharia, saúde, limpeza, etc.) usando
            inteligência artificial — algo que o PNCP não faz.
          </li>
          <li>
            <strong>Análise de viabilidade:</strong> Avaliam cada edital em
            múltiplos fatores (modalidade, timeline, valor, geografia) para
            indicar quais merecem investimento de tempo.
          </li>
          <li>
            <strong>Alertas automáticos:</strong> Notificam quando novos editais
            são publicados no setor e região de interesse — funcionalidade
            ausente no PNCP.
          </li>
          <li>
            <strong>Histórico de preços:</strong> Permitem consultar contratos
            anteriores para calibrar propostas com base em dados de mercado.
          </li>
          <li>
            <strong>Pipeline de oportunidades:</strong> Organizam os editais em
            estágios (triagem, análise, proposta, participação) para gestão
            eficiente do fluxo de trabalho.
          </li>
        </ul>
      </div>

      <p>
        O SmartLic é uma dessas ferramentas. Agrega dados do PNCP, Portal de
        Compras Públicas e ComprasGov, classifica editais em 15 setores com
        IA (GPT-4.1-nano), avalia viabilidade em 4 fatores e oferece pipeline
        de oportunidades com drag-and-drop. Para empresas que buscam editais
        de{' '}
        <Link href="/blog/licitacoes-ti-software-2026">TI e software</Link> ou{' '}
        <Link href="/blog/licitacoes-engenharia-2026">engenharia</Link>, a
        classificação setorial elimina o ruído de editais irrelevantes que a
        busca genérica do PNCP inevitavelmente retorna.
      </p>

      {/* CTA final — before FAQ */}
      <div className="not-prose mt-8 sm:mt-12 bg-brand-blue-subtle dark:bg-brand-navy/20 rounded-xl p-5 sm:p-8 text-center border border-brand-blue/20">
        <p className="text-lg sm:text-xl font-bold text-ink mb-2">
          Vá além do PNCP — busca multi-fonte com IA
        </p>
        <p className="text-sm sm:text-base text-ink-secondary mb-4 sm:mb-6 max-w-lg mx-auto">
          O SmartLic agrega PNCP, Portal de Compras Públicas e ComprasGov,
          classifica editais por setor com inteligência artificial e avalia
          viabilidade automaticamente. Sem custo para começar.
        </p>
        <Link
          href="/signup?source=blog&article=pncp-guia-completo-empresas&utm_source=blog&utm_medium=cta&utm_content=pncp-guia-completo-empresas&utm_campaign=guias"
          className="inline-block bg-brand-navy hover:bg-brand-blue-hover text-white font-semibold px-5 sm:px-6 py-2.5 sm:py-3 rounded-button text-sm sm:text-base transition-all hover:scale-[1.02] active:scale-[0.98]"
        >
          Teste Grátis por 14 Dias
        </Link>
        <p className="text-xs text-ink-secondary mt-3">
          Sem cartão de crédito. Veja todas as funcionalidades na{' '}
          <Link href="/features" className="underline hover:text-ink">
            página de recursos
          </Link>.
        </p>
      </div>

      <h2>Perguntas Frequentes</h2>

      <h3>O PNCP é obrigatório para todos os órgãos?</h3>
      <p>
        A obrigatoriedade foi implementada de forma escalonada. Órgãos federais
        publicam desde abril de 2023. Estados e municípios de grande porte desde
        2024. Municípios de pequeno porte (abaixo de 50 mil habitantes) têm
        prazos estendidos até 2026. A cobertura ainda é parcial — nem todos os
        entes publicam no portal, o que exige busca complementar em outras
        fontes.
      </p>

      <h3>Posso baixar editais gratuitamente no PNCP?</h3>
      <p>
        Sim. O PNCP é público e gratuito. Todos os editais, termos de
        referência, atas e contratos publicados podem ser acessados e baixados
        sem custo e sem necessidade de cadastro. Basta acessar pncp.gov.br e
        buscar pelo edital desejado.
      </p>

      <h3>Qual a diferença entre PNCP e ComprasNet?</h3>
      <p>
        O PNCP centraliza a publicação de editais de todos os entes (federal,
        estadual, municipal) — é o portal de transparência. O Compras.gov.br
        (ex-ComprasNet) é onde os pregões do governo federal são realizados — é
        o portal de operação. O fornecedor consulta o PNCP para encontrar
        editais e acessa o Compras.gov.br para participar do pregão federal.
      </p>

      <h3>O PNCP envia alertas de novos editais?</h3>
      <p>
        Não. Até abril de 2026, o PNCP não possui sistema nativo de alertas por
        e-mail ou notificação. A busca é 100% manual. Ferramentas complementares
        como o <Link href="/features">SmartLic</Link> preenchem essa lacuna com
        busca automatizada e classificação por setor.
      </p>

      <h3>Consigo ver resultados de licitações no PNCP?</h3>
      <p>
        Sim, parcialmente. O PNCP publica atas de julgamento, resultados e
        contratos firmados. É possível consultar quem venceu e o valor
        contratado. No entanto, a correlação entre edital e resultado nem sempre
        é intuitiva — pode ser necessário buscar o contrato separadamente.
      </p>

      <h3>A API do PNCP é gratuita?</h3>
      <p>
        Sim. A API (pncp.gov.br/api) é pública e gratuita, sem necessidade de
        autenticação para consultas básicas. O limite é de 50 registros por
        requisição. A API é utilizada por ferramentas de inteligência como o
        SmartLic para automatizar a busca de editais em escala.
      </p>
    </>
  );
}
