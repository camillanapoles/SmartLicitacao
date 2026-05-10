import Link from 'next/link';
import BlogInlineCTA from '../components/BlogInlineCTA';

/**
 * PNCP-SPOKE-02 (#992) — PNCP: prazos e timeline de publicação
 * Cluster: PNCP | Pillar: pncp-guia-completo-empresas
 * Target: ~1050 words | Primary KW: prazo publicação edital pncp
 */
export default function PncpTimelinePublicacaoEdital() {
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
                name: 'Qual o prazo mínimo entre publicação no PNCP e a abertura do pregão?',
                acceptedAnswer: {
                  '@type': 'Answer',
                  text: 'Para pregão eletrônico de bens e serviços comuns, o prazo mínimo é de 8 dias úteis (Lei 14.133/2021, art. 55). Para pregão de melhor técnica e preço, 10 dias úteis. Concorrência exige no mínimo 25 dias úteis para julgamento por menor preço e 35 dias úteis para técnica e preço.',
                },
              },
              {
                '@type': 'Question',
                name: 'Em quanto tempo o edital aparece no PNCP após assinado pelo órgão?',
                acceptedAnswer: {
                  '@type': 'Answer',
                  text: 'Em geral, no mesmo dia ou em até 24 horas. A integração das plataformas (ComprasGov, BLL, Licitanet, BNC etc.) com o PNCP é praticamente em tempo real. Editais publicados após 18h normalmente só ficam visíveis na manhã seguinte.',
                },
              },
              {
                '@type': 'Question',
                name: 'O órgão pode reduzir o prazo de publicação?',
                acceptedAnswer: {
                  '@type': 'Answer',
                  text: 'Não. Os prazos da Lei 14.133/2021 são mínimos e não podem ser encurtados. O órgão pode estendê-los — e, em casos de alterações relevantes no edital, é obrigado a reabrir o prazo. Reduções fictícias são causa frequente de impugnação procedente.',
                },
              },
              {
                '@type': 'Question',
                name: 'Como saber se um edital teve o prazo reaberto após alteração?',
                acceptedAnswer: {
                  '@type': 'Answer',
                  text: 'O PNCP exibe o histórico de versões do edital na ficha pública da contratação, incluindo data de cada alteração e o novo prazo de abertura. Sempre verifique a versão vigente antes de finalizar a proposta — alterações de última hora podem mudar o objeto, o critério ou a habilitação.',
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
        da SmartLic. Aqui você entende quando um edital aparece no portal,
        quanto tempo você tem para reagir e como organizar a janela entre
        publicação e sessão para sair na frente.
      </p>

      <h2>Por que o cronograma do PNCP é vantagem competitiva</h2>
      <p>
        Quem percebe um edital no <strong>dia 1</strong> tem uma semana
        completa para preparar proposta. Quem só vê no dia 6 tem 48 horas
        para fazer o que os concorrentes fizeram em 7 dias. A vitória em
        licitações públicas é decidida muito antes da sessão começar — é
        decidida na velocidade de detecção e na qualidade da preparação.
      </p>
      <p>
        O PNCP, ao concentrar toda a publicação obrigatória de
        contratações públicas (Lei 14.133/2021, art. 174-176), tornou
        possível pela primeira vez monitorar o país inteiro em um único
        ponto. Antes disso, empresas precisavam acompanhar dezenas de
        Diários Oficiais e portais municipais.
      </p>

      <h2>Prazos legais por modalidade</h2>
      <p>
        A Lei 14.133/2021, artigo 55, fixou prazos mínimos entre a
        divulgação do edital e a apresentação de propostas:
      </p>
      <ul>
        <li>
          <strong>Pregão eletrônico, bens/serviços comuns, menor preço:</strong>{' '}
          8 dias úteis.
        </li>
        <li>
          <strong>Pregão eletrônico, melhor técnica e preço:</strong> 10
          dias úteis.
        </li>
        <li>
          <strong>Concorrência, menor preço:</strong> 25 dias úteis.
        </li>
        <li>
          <strong>Concorrência, técnica e preço:</strong> 35 dias úteis.
        </li>
        <li>
          <strong>Diálogo competitivo:</strong> mínimo de 25 dias úteis,
          em fases sucessivas.
        </li>
      </ul>
      <p>
        Esses prazos são contados em <strong>dias úteis</strong> — feriados
        nacionais, estaduais e municipais (no caso de licitação local)
        suspendem a contagem. Pequenos órgãos esquecem feriados locais e
        publicam editais com prazo nominalmente correto, mas materialmente
        curto. Isso é causa válida de impugnação.
      </p>

      <h2>O ciclo de publicação no PNCP</h2>
      <p>
        Depois que o órgão licitante assina o edital e publica em sua
        plataforma de origem (ComprasGov para a União, sistemas
        municipais/estaduais para outros entes), o registro é replicado ao
        PNCP por integração. Em condições normais:
      </p>
      <ul>
        <li>
          <strong>D+0 (até 18h):</strong> aparece no PNCP no mesmo dia.
        </li>
        <li>
          <strong>D+0 (após 18h):</strong> visível no portal na manhã do
          dia seguinte.
        </li>
        <li>
          <strong>D+1 a D+3:</strong> raros, geralmente decorrentes de
          falha de integração — denunciáveis junto ao Ministério da
          Gestão.
        </li>
      </ul>
      <p>
        Para empresas que dependem de detecção rápida, monitoramento por
        API a cada 15-30 minutos é o estado da arte. Veja como construir
        esse pipeline no spoke{' '}
        <Link href="/blog/pncp-api-integracao-empresas">
          API do PNCP — integração e automação
        </Link>
        .
      </p>

      <h2>Como organizar a janela entre publicação e sessão</h2>
      <p>
        A janela típica de 8 dias úteis (~10 dias corridos) deve ser
        dividida em três blocos:
      </p>
      <p>
        <strong>Bloco 1 — Triagem (24 horas após publicação).</strong>{' '}
        Decisão go/no-go com base em três critérios objetivos: a empresa
        atende ao objeto?; tem atestado técnico compatível?; tem caixa
        para suportar prazo de pagamento (geralmente 30 dias após o ateste
        do recebimento, mas pode chegar a 90 dias em alguns órgãos
        municipais)?
      </p>
      <p>
        <strong>Bloco 2 — Construção da proposta (40-50% do tempo).</strong>{' '}
        Cotação com fornecedores, planilha de composição de preço,
        verificação de margem mínima por item, validação jurídica do
        contrato-modelo anexo.
      </p>
      <p>
        <strong>Bloco 3 — Habilitação e ensaio (24-48 horas finais).</strong>{' '}
        Atualizar certidões, validar acesso ao sistema, ensaiar fluxo de
        lance, conferir nome de usuário e certificado digital.
      </p>

      <h2>Impugnação e prazos correlatos</h2>
      <p>
        A Lei 14.133/2021, art. 164, garante a qualquer cidadão o direito
        de impugnar o edital até{' '}
        <strong>3 dias úteis antes da sessão pública</strong>. O órgão tem
        igual prazo para responder. Se a impugnação for procedente e
        envolver alteração relevante (mudança de objeto, de critério, de
        habilitação ou de quantitativo), o prazo de propostas reabre — o
        que pode dilatar o cronograma em 8 a 25 dias úteis.
      </p>
      <p>
        Para o detalhamento prático de impugnação, leia também{' '}
        <Link href="/blog/impugnacao-edital-quando-como-contestar">
          impugnação de edital — quando e como contestar
        </Link>
        .
      </p>

      <BlogInlineCTA
        slug="pncp-timeline-publicacao-edital"
        campaign="guias"
        ctaMessage="Detecte editais no dia 1, não no dia 6."
        ctaText="Começar grátis"
      />

      <h2>Próximos passos no cluster PNCP</h2>
      <p>
        Continue por{' '}
        <Link href="/blog/pncp-modalidade-pregao-eletronico">
          PNCP e pregão eletrônico
        </Link>
        ,{' '}
        <Link href="/blog/impugnacao-edital-quando-como-contestar">
          impugnação de edital — guia completo
        </Link>{' '}
        e{' '}
        <Link href="/blog/pncp-erros-comuns-empresas-iniciantes">
          7 erros que empresas iniciantes cometem
        </Link>
        . O{' '}
        <Link href="/blog/pncp-guia-completo-empresas">
          Guia Completo do PNCP
        </Link>{' '}
        tem o mapa do cluster.
      </p>
    </>
  );
}
