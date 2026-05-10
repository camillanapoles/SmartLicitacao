import Link from 'next/link';
import BlogInlineCTA from '../components/BlogInlineCTA';

/**
 * PNCP-SPOKE-07 (#992) — API do PNCP: integração e automação
 * Cluster: PNCP | Pillar: pncp-guia-completo-empresas
 * Target: ~1150 words | Primary KW: pncp api
 */
export default function PncpApiIntegracaoEmpresas() {
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
                name: 'A API do PNCP exige autenticação?',
                acceptedAnswer: {
                  '@type': 'Answer',
                  text: 'Não, a API de Consulta v1 do PNCP é pública e não exige token. Basta fazer requisições HTTP GET aos endpoints documentados em pncp.gov.br/api/consulta. Há rate limit recomendado pela documentação (cerca de 60 requisições por minuto por origem) — abusar pode levar a bloqueio temporário.',
                },
              },
              {
                '@type': 'Question',
                name: 'Quantos registros a API retorna por página?',
                acceptedAnswer: {
                  '@type': 'Answer',
                  text: 'No máximo 50 por página (parâmetro tamanhoPagina). Tentativas de pedir mais são rejeitadas. Para coletar volumes maiores, é necessário paginar com o parâmetro pagina e somar os resultados — em geral, varredura completa de uma UF para um período de 30 dias exige 5-15 páginas.',
                },
              },
              {
                '@type': 'Question',
                name: 'Quais endpoints existem na API do PNCP?',
                acceptedAnswer: {
                  '@type': 'Answer',
                  text: 'Os principais são /v1/contratacoes/publicacao (editais publicados), /v1/contratacoes/atualizacao (alterações), /v1/contratos (contratos), /v1/atas (atas de registro de preços). Todos aceitam filtros por data, UF, modalidade, órgão e CNPJ. A documentação oficial está em pncp.gov.br/api/consulta.',
                },
              },
              {
                '@type': 'Question',
                name: 'Posso revender dados extraídos da API?',
                acceptedAnswer: {
                  '@type': 'Answer',
                  text: 'Os dados são públicos por força da Lei 12.527/2011 (LAI) e da Lei 14.133/2021. Empresas como a SmartLic agregam, classificam por IA e enriquecem esses dados em produtos próprios — atividade legal e juridicamente protegida (não há direito autoral sobre dados públicos). O que não pode é redistribuir mascarando a origem ou descumprindo termos de uso eventuais publicados pelo PNCP.',
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
        da SmartLic. Para empresas com time técnico, automatizar a busca
        no PNCP transforma horas de garimpo manual em pipeline contínuo.
        Aqui, o caminho prático para integrar.
      </p>

      <h2>O que a API do PNCP expõe</h2>
      <p>
        A API de Consulta v1 do PNCP é uma interface HTTP pública,
        documentada em <code>pncp.gov.br/api/consulta</code>. Ela expõe
        leitura sobre os principais módulos do portal:
      </p>
      <ul>
        <li>
          <strong>Editais publicados</strong> (contratações em fase de
          divulgação).
        </li>
        <li>
          <strong>Alterações de editais</strong> (úteis para detectar
          impugnações procedentes e mudanças de prazo).
        </li>
        <li>
          <strong>Contratos</strong> firmados e seus aditivos.
        </li>
        <li>
          <strong>Atas de Registro de Preços</strong> vigentes, com
          quantitativos e preços unitários.
        </li>
        <li>
          <strong>Itens das contratações</strong> (decomposição por
          item, quando o edital é de bem e usa CATMAT/CATSER).
        </li>
      </ul>
      <p>
        Não há endpoint para envio de proposta ou lance — a API é apenas
        de leitura. Para participar de pregões, ainda é necessário a
        plataforma operacional (ComprasGov, BLL, Licitanet etc.).
      </p>

      <h2>Construindo um pipeline básico</h2>
      <p>
        Um monitoramento mínimo viável tem cinco componentes:
      </p>
      <p>
        <strong>1. Coletor.</strong> Cron job que executa a cada 15-60
        minutos, faz GET no endpoint{' '}
        <code>/v1/contratacoes/publicacao</code> com filtros de UF e
        intervalo de datas, paginando até esgotar resultados.
      </p>
      <p>
        <strong>2. Persistência.</strong> Banco relacional (PostgreSQL é
        a escolha óbvia) com tabela bruta para os JSONs e tabela
        normalizada para consultas. Use o número de controle PNCP como
        chave de deduplicação — o mesmo edital pode aparecer em
        múltiplas chamadas se for atualizado.
      </p>
      <p>
        <strong>3. Classificador.</strong> Cada edital recebido é
        classificado contra os setores de interesse da empresa.
        Implementação simples: lista de palavras-chave com pesos.
        Implementação avançada: LLM com prompt curto avaliando se o
        edital é compatível com o setor. A SmartLic usa esse tier híbrido
        em produção (densidade de palavra-chave seguida de GPT-4.1-nano
        para zona cinzenta).
      </p>
      <p>
        <strong>4. Notificador.</strong> Editais aprovados pelo
        classificador disparam alertas — email, Slack, dashboard interno.
        O segredo é manter ruído baixo: muitos alertas falsos resultam
        em descarte humano de todos.
      </p>
      <p>
        <strong>5. Repositório histórico.</strong> Mesmo editais
        descartados ficam armazenados por 12-24 meses para análises
        posteriores (séries temporais, mapeamento de concorrente, etc.).
      </p>

      <h2>Boas práticas técnicas</h2>
      <ul>
        <li>
          <strong>Respeite o rate limit.</strong> Não dispare paralelismo
          agressivo — a documentação oficial sugere ~60 requisições por
          minuto. Se precisar de throughput maior, distribua coleta ao
          longo do dia.
        </li>
        <li>
          <strong>Trate falhas idempotentemente.</strong> A API tem
          janelas de instabilidade ocasional. Faça retry exponencial
          (1s, 2s, 4s, 8s) e marque batches falhos para reprocessamento.
        </li>
        <li>
          <strong>Use cache de leitura.</strong> O mesmo edital
          consultado por endpoints diferentes pode aparecer várias vezes.
          Cache local de 5-15 minutos reduz tráfego e custo.
        </li>
        <li>
          <strong>Prefira coleta incremental por data.</strong> Em vez de
          re-puxar tudo, use o filtro <code>dataInicial</code> /{' '}
          <code>dataFinal</code> para sincronizar apenas o delta.
        </li>
        <li>
          <strong>Persista o JSON bruto antes de transformar.</strong> Se
          o esquema da API mudar, você ainda terá os dados originais
          para reprocessar.
        </li>
      </ul>

      <h2>Casos de uso típicos</h2>
      <p>
        <strong>Caso A — Alerta diário por setor.</strong> Empresa de
        engenharia recebe email às 9h com todos os editais novos do dia
        anterior em obras civis em SP, MG e RJ. Custo: 1 servidor pequeno
        + cron + integração SMTP.
      </p>
      <p>
        <strong>Caso B — Inteligência competitiva.</strong> Consultoria
        agrega contratos por CNPJ para gerar relatório mensal de
        concorrentes (quantos contratos ganharam, em qual valor médio,
        em quais órgãos). Diferenciação para clientes B2G.
      </p>
      <p>
        <strong>Caso C — Detecção de oportunidade de carona.</strong>{' '}
        Empresa registrada em uma ata varre periodicamente atas
        similares de outros órgãos buscando objetos compatíveis para
        oferecer adesão proativa.
      </p>

      <h2>Por que não construir do zero</h2>
      <p>
        Construir é viável, mas tem três custos escondidos:
      </p>
      <ul>
        <li>
          <strong>Manutenção da integração.</strong> Mudanças de schema,
          janelas de instabilidade, novos endpoints — exige tempo de
          engenharia recorrente.
        </li>
        <li>
          <strong>Classificação de qualidade.</strong> Atingir 85% de
          precisão na classificação setorial exige iteração com dados
          rotulados — não é "uma tarde de trabalho".
        </li>
        <li>
          <strong>Cobertura multi-fonte.</strong> O PNCP cobre quase
          tudo, mas municípios pequenos ainda integram parcialmente.
          Cobertura completa exige complementar com PCP v2, ComprasGov
          v3 e portais de transparência locais — multiplicando a
          complexidade.
        </li>
      </ul>
      <p>
        Para empresas em que B2G é foco estratégico mas não core
        técnico, contratar plataforma especializada costuma sair mais
        barato do que manter time interno. A SmartLic, por exemplo,
        agrega PNCP + PCP v2 + ComprasGov v3 com classificação por IA e
        análise de viabilidade pronta — pague o que vai consumir, não o
        que precisa construir.
      </p>

      <BlogInlineCTA
        slug="pncp-api-integracao-empresas"
        campaign="guias"
        ctaMessage="Pule a integração — use a plataforma pronta."
        ctaText="Testar grátis"
      />

      <h2>Próximos passos no cluster PNCP</h2>
      <p>
        Veja{' '}
        <Link href="/blog/pncp-vs-comprasgov-diferencas">
          PNCP vs ComprasGov
        </Link>
        ,{' '}
        <Link href="/blog/pncp-consulta-contratos-passo-a-passo">
          PNCP — consulta de contratos passo a passo
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
