import Link from 'next/link';
import BlogInlineCTA from '../components/BlogInlineCTA';

/**
 * PNCP-SPOKE-01 (#992) — PNCP e Pregão Eletrônico
 * Cluster: PNCP | Pillar: pncp-guia-completo-empresas
 * Target: ~1100 words | Primary KW: pncp pregão eletrônico
 */
export default function PncpModalidadePregaoEletronico() {
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
                name: 'O pregão eletrônico é obrigatório no PNCP?',
                acceptedAnswer: {
                  '@type': 'Answer',
                  text: 'Sim. A Lei 14.133/2021 elege o pregão eletrônico como modalidade preferencial para aquisição de bens e serviços comuns, e toda compra pública passa a ser publicada no PNCP. Órgãos federais já operam 100% no PNCP; estados e municípios seguem cronograma escalonado, mas a tendência é convergência total até 2026.',
                },
              },
              {
                '@type': 'Question',
                name: 'Como filtrar apenas pregões eletrônicos no PNCP?',
                acceptedAnswer: {
                  '@type': 'Answer',
                  text: 'Na busca avançada do PNCP, selecione o filtro "Modalidade" e marque "Pregão Eletrônico". Combine com filtros de UF, faixa de valor e período de publicação para reduzir o volume. A API pública do PNCP também aceita o parâmetro codigoModalidadeContratacao=6 para pregão eletrônico.',
                },
              },
              {
                '@type': 'Question',
                name: 'Qual o prazo mínimo entre publicação e sessão do pregão?',
                acceptedAnswer: {
                  '@type': 'Answer',
                  text: 'A Lei 14.133/2021, art. 55, estabelece prazo mínimo de 8 dias úteis para pregão eletrônico de bens e serviços comuns, e 10 dias úteis quando envolver critério de melhor técnica e preço. Esse é o tempo que a empresa tem para ler o edital, montar a proposta e enviar.',
                },
              },
              {
                '@type': 'Question',
                name: 'Posso participar de pregão eletrônico em qualquer UF pelo PNCP?',
                acceptedAnswer: {
                  '@type': 'Answer',
                  text: 'Sim. O pregão eletrônico é, por definição, à distância — você participa de qualquer lugar do país. O que muda por UF é a plataforma de origem (ComprasGov para a União, BLL/Licitanet/BNC para municípios e estados), mas todas publicam no PNCP e o acesso é online.',
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
        da SmartLic. Aqui o foco é a modalidade que mais movimenta volume no
        portal: o pregão eletrônico — responsável por mais de 70% das compras
        publicadas no PNCP em 2025, segundo levantamento agregado pelo próprio
        portal e pelo Ministério da Gestão.
      </p>

      <h2>Por que o pregão eletrônico domina o PNCP</h2>
      <p>
        A Lei 14.133/2021 reorganizou as modalidades licitatórias em cinco
        categorias (pregão, concorrência, concurso, leilão e diálogo
        competitivo) e elegeu o <strong>pregão eletrônico</strong> como
        modalidade preferencial para a aquisição de bens e serviços comuns
        (art. 6º, inciso XLI). Isso significa que, salvo justificativa
        técnica robusta, qualquer compra de itens que tenham padrões
        objetivamente definidos no mercado — equipamentos de informática,
        material de escritório, serviços de limpeza, terceirização, frota,
        manutenção predial — será conduzida via pregão eletrônico e
        publicada no PNCP.
      </p>
      <p>
        Em termos práticos, mais de 70% dos editais que aparecem na busca
        diária do PNCP são pregões. Para empresas B2G, dominar essa
        modalidade não é opcional: é o canal principal de receita pública.
      </p>

      <h2>Como filtrar e encontrar pregões no PNCP</h2>
      <p>
        Na interface web do PNCP (pncp.gov.br/app/editais), o caminho mais
        rápido é o seguinte:
      </p>
      <ol>
        <li>
          <strong>Filtre por modalidade:</strong> selecione apenas "Pregão
          Eletrônico" no painel lateral.
        </li>
        <li>
          <strong>Restrinja por UF e cidade</strong> — começar pelo seu
          estado reduz drasticamente o volume e melhora a viabilidade
          logística.
        </li>
        <li>
          <strong>Use a faixa de valor estimado</strong> compatível com sua
          capacidade de execução. Disputar contratos muito pequenos (abaixo
          de R$ 50 mil) raramente compensa para empresas estruturadas;
          disputar contratos muito grandes sem atestado técnico equivalente
          é pedir desclassificação.
        </li>
        <li>
          <strong>Filtre pelo período de publicação</strong> — últimos 7 ou
          14 dias — para focar em editais ainda dentro do prazo de proposta.
        </li>
      </ol>
      <p>
        Para quem prefere automatizar, a{' '}
        <Link href="/blog/pncp-api-integracao-empresas">
          API pública do PNCP
        </Link>{' '}
        aceita o parâmetro <code>codigoModalidadeContratacao=6</code> e
        devolve até 50 registros por página, permitindo construir um
        monitoramento diário próprio.
      </p>

      <h2>Anatomia de um edital de pregão no PNCP</h2>
      <p>
        Todo edital publicado no PNCP segue uma estrutura padronizada
        (Anexo III da IN SEGES/ME 65/2021), o que facilita comparar e
        triar:
      </p>
      <ul>
        <li>
          <strong>Objeto:</strong> descrição clara do bem ou serviço,
          incluindo especificação técnica mínima.
        </li>
        <li>
          <strong>Valor estimado:</strong> teto referencial calculado pelo
          órgão. Propostas acima do estimado são desclassificadas; muito
          abaixo (geralmente menos de 75%) podem ser questionadas como
          inexequíveis.
        </li>
        <li>
          <strong>Prazo de execução e local de entrega:</strong> calcule
          frete e logística antes de cotar.
        </li>
        <li>
          <strong>Habilitação:</strong> regularidade fiscal, qualificação
          técnica (atestados), qualificação econômico-financeira (balanço,
          índices de liquidez) e habilitação jurídica.
        </li>
        <li>
          <strong>Critério de julgamento:</strong> menor preço (padrão para
          bens comuns) ou maior desconto sobre tabela.
        </li>
      </ul>

      <h2>O fluxo da sessão pública</h2>
      <p>
        Diferente da concorrência tradicional, o pregão eletrônico é
        dinâmico e veloz: a sessão tem três fases observáveis em tempo
        real.
      </p>
      <p>
        <strong>Fase 1 — Recebimento de propostas:</strong> antes do
        horário de abertura, todos os licitantes enviam proposta de preço
        inicial pelo sistema (ComprasGov, BLL, Licitanet, BNC etc.). O
        valor não é revelado.
      </p>
      <p>
        <strong>Fase 2 — Lances:</strong> a partir da abertura, os
        licitantes ofertam lances decrescentes em rodadas. O sistema
        encerra automaticamente após período aleatório (1 a 30 minutos)
        sem novos lances. É aqui que se ganha ou se perde — e onde mais
        empresas erram, oferecendo lances impulsivos sem cálculo de
        margem.
      </p>
      <p>
        <strong>Fase 3 — Habilitação:</strong> o pregoeiro verifica
        documentos do licitante mais bem classificado. Se faltar uma
        certidão, ele é desclassificado e o segundo colocado é convocado.
      </p>

      <h2>Erros que custam o contrato</h2>
      <p>
        Os tropeços mais comuns de empresas iniciantes em pregão estão
        documentados no spoke{' '}
        <Link href="/blog/pncp-erros-comuns-empresas-iniciantes">
          7 erros que empresas iniciantes cometem no PNCP
        </Link>
        . Os três mais letais:
      </p>
      <ul>
        <li>
          <strong>Certidão fiscal vencida</strong> — especialmente FGTS,
          que vence a cada 30 dias.
        </li>
        <li>
          <strong>Lance abaixo do custo</strong> sem ter feito a planilha
          de composição de preço; vitória que vira prejuízo.
        </li>
        <li>
          <strong>Atestado técnico incompatível</strong> — o pregoeiro
          aceita apenas atestados que comprovem objeto e quantitativo
          mínimo equivalente.
        </li>
      </ul>

      <h2>Cronograma típico — leitura, proposta, sessão</h2>
      <p>
        Entre a publicação do edital e a sessão pública há, no mínimo, 8
        dias úteis. Veja como os times bem-organizados distribuem esse
        tempo (detalhes no spoke{' '}
        <Link href="/blog/pncp-timeline-publicacao-edital">
          PNCP: timeline de publicação do edital
        </Link>
        ):
      </p>
      <ul>
        <li>
          <strong>Dias 1-2:</strong> triagem do objeto, leitura crítica,
          decisão go/no-go.
        </li>
        <li>
          <strong>Dias 3-5:</strong> coleta de cotações com fornecedores,
          montagem da planilha de composição de preço, validação interna.
        </li>
        <li>
          <strong>Dias 6-7:</strong> verificação de documentos de
          habilitação, atualização de certidões, ensaio de senha no
          sistema.
        </li>
        <li>
          <strong>Dia 8:</strong> envio da proposta com 24 horas de
          margem.
        </li>
      </ul>

      <BlogInlineCTA
        slug="pncp-modalidade-pregao-eletronico"
        campaign="guias"
        ctaMessage="Receba alertas só de pregões compatíveis com sua empresa."
        ctaText="Testar grátis"
      />

      <h2>Próximos passos no cluster PNCP</h2>
      <p>
        Para aprofundar:{' '}
        <Link href="/blog/pncp-timeline-publicacao-edital">
          PNCP — timeline de publicação do edital
        </Link>
        ,{' '}
        <Link href="/blog/pncp-vs-comprasgov-diferencas">
          PNCP vs ComprasGov
        </Link>{' '}
        e{' '}
        <Link href="/blog/pncp-erros-comuns-empresas-iniciantes">
          7 erros que empresas iniciantes cometem
        </Link>
        . Volte sempre ao{' '}
        <Link href="/blog/pncp-guia-completo-empresas">
          Guia Completo do PNCP
        </Link>{' '}
        para a visão consolidada do cluster.
      </p>
    </>
  );
}
