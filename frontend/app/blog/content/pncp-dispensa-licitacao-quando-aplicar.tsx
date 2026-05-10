import Link from 'next/link';
import BlogInlineCTA from '../components/BlogInlineCTA';

/**
 * PNCP-SPOKE-05 (#992) — PNCP e Dispensa de Licitação
 * Cluster: PNCP | Pillar: pncp-guia-completo-empresas
 * Target: ~1080 words | Primary KW: pncp dispensa licitação
 */
export default function PncpDispensaLicitacaoQuandoAplicar() {
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
                name: 'Quais os valores de dispensa pela Lei 14.133/2021?',
                acceptedAnswer: {
                  '@type': 'Answer',
                  text: 'O art. 75, incisos I e II, fixa os limites de dispensa em razão do valor: até R$ 119.812,02 para obras e serviços de engenharia, e até R$ 59.906,02 para outros bens e serviços (valores atualizados anualmente por decreto). Acima disso, é obrigatório licitar.',
                },
              },
              {
                '@type': 'Question',
                name: 'Dispensa eletrônica é obrigatoriamente publicada no PNCP?',
                acceptedAnswer: {
                  '@type': 'Answer',
                  text: 'Sim. Toda dispensa formalizada pela administração pública, inclusive a eletrônica, deve ser publicada no PNCP, com objeto, valor, fornecedor escolhido e justificativa. A obrigatoriedade decorre dos arts. 174 e 175 da Lei 14.133/2021.',
                },
              },
              {
                '@type': 'Question',
                name: 'Como uma empresa pequena participa de dispensas?',
                acceptedAnswer: {
                  '@type': 'Answer',
                  text: 'Há dois caminhos: (1) ser convidada pelo órgão a apresentar cotação na fase de pesquisa de preço; (2) participar da dispensa eletrônica via PNCP, plataforma na qual três fornecedores são chamados a competir online. Cadastrar-se no SICAF e em portais como BLL e Licitanet aumenta as chances de ser escolhido.',
                },
              },
              {
                '@type': 'Question',
                name: 'Dispensa é a mesma coisa que inexigibilidade?',
                acceptedAnswer: {
                  '@type': 'Answer',
                  text: 'Não. Dispensa (art. 75) ocorre quando há viabilidade de competição, mas a lei autoriza não licitar (valor baixo, urgência etc.). Inexigibilidade (art. 74) ocorre quando não há viabilidade de competição — fornecedor exclusivo, serviço técnico singular, contratação artística etc. As duas são publicadas no PNCP, mas com fundamentos jurídicos distintos.',
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
        da SmartLic. Aqui você entende quando a administração pode
        dispensar a licitação, como localizar dispensas no PNCP e por que
        este canal — frequentemente subestimado — é uma das vias mais
        ágeis para empresas iniciarem em B2G.
      </p>

      <h2>O que é dispensa de licitação</h2>
      <p>
        Dispensa é a hipótese em que, embora seja possível abrir uma
        competição entre fornecedores, a Lei 14.133/2021 autoriza a
        administração a contratar diretamente. Ao contrário da
        inexigibilidade — que pressupõe a impossibilidade de competição —,
        a dispensa parte do princípio de que <em>seria possível
        licitar</em>, mas não vale a pena pelo custo administrativo, pela
        urgência ou pelo baixo valor do objeto.
      </p>

      <h2>Hipóteses do art. 75</h2>
      <p>
        O art. 75 lista mais de 15 hipóteses. As mais usadas na prática:
      </p>
      <ul>
        <li>
          <strong>I — Obras e serviços de engenharia até R$ 119.812,02</strong>{' '}
          (valor atualizado).
        </li>
        <li>
          <strong>II — Outros bens e serviços até R$ 59.906,02.</strong>
        </li>
        <li>
          <strong>VIII — Compras emergenciais</strong> em situação de
          emergência ou calamidade pública (limitada a 1 ano, sem
          prorrogação).
        </li>
        <li>
          <strong>X — Compras de hortifrutigranjeiros</strong> diretamente
          de produtor rural pessoa física.
        </li>
        <li>
          <strong>XI — Aquisições por organismos internacionais</strong>{' '}
          quando há acordo de cooperação técnica.
        </li>
        <li>
          <strong>XV — Compras complementares</strong> a contratos
          vigentes, dentro do limite de 25% do valor original.
        </li>
      </ul>
      <p>
        Os valores dos incisos I e II são atualizados anualmente por
        decreto — sempre confira a versão vigente antes de orientar
        cliente ou montar planejamento.
      </p>

      <h2>Dispensa eletrônica — o caminho mais transparente</h2>
      <p>
        O Decreto 10.024/2019 e a IN SEGES/ME 67/2021 instituíram a{' '}
        <strong>dispensa eletrônica</strong>: mesmo nas hipóteses de
        valor (incisos I e II), o órgão precisa fazer uma chamada
        pública por sistema eletrônico, dando 3 dias úteis para que
        fornecedores cadastrados apresentem propostas. Funciona como um
        mini-pregão. Ao final, o órgão escolhe a proposta mais vantajosa
        e formaliza a contratação.
      </p>
      <p>
        A dispensa eletrônica é publicada no PNCP no momento da abertura
        e novamente no momento da homologação. Empresas iniciantes
        encontram nela uma porta de entrada: contratos pequenos, ciclo
        rápido, menos concorrentes que pregões grandes.
      </p>

      <h2>Como filtrar dispensas no PNCP</h2>
      <p>
        Em <code>pncp.gov.br/app/editais</code>, no filtro de modalidade,
        marque "Dispensa". Combine com:
      </p>
      <ul>
        <li>UF do seu estado.</li>
        <li>Faixa de valor compatível com seu porte.</li>
        <li>Período de publicação (últimos 7 dias para captura ágil).</li>
      </ul>
      <p>
        Para automatizar, a API aceita{' '}
        <code>codigoModalidadeContratacao=8</code> (dispensa) ou{' '}
        <code>=9</code> (inexigibilidade). Veja{' '}
        <Link href="/blog/pncp-api-integracao-empresas">
          API do PNCP — integração e automação
        </Link>
        .
      </p>

      <h2>Documentos exigidos</h2>
      <p>
        Mesmo em dispensa, a habilitação é simplificada — mas não
        ausente. O órgão exige tipicamente:
      </p>
      <ul>
        <li>Certidões de regularidade fiscal (federal, FGTS, trabalhista).</li>
        <li>Comprovante de inscrição no CNPJ.</li>
        <li>
          Atestado de capacidade técnica (em alguns casos, dispensado
          quando o valor é muito baixo).
        </li>
        <li>Contrato social atualizado.</li>
      </ul>
      <p>
        A vantagem prática: ciclo de 5 a 10 dias úteis entre detecção da
        dispensa e assinatura do contrato — comparado a 25-40 dias úteis
        de um pregão.
      </p>

      <h2>Riscos jurídicos para a empresa contratada</h2>
      <p>
        Dispensa é fiscalizada com rigor pelo TCU e pelos TCEs. Empresas
        que se beneficiam de dispensa devem garantir:
      </p>
      <ul>
        <li>
          <strong>Justificativa formal do órgão</strong> arquivada no
          processo administrativo (cópia disponível em recurso, se
          necessário).
        </li>
        <li>
          <strong>Pesquisa de preços documentada</strong> — três cotações
          ou painel oficial de preços (Painel de Preços do Governo
          Federal).
        </li>
        <li>
          <strong>Não fracionamento.</strong> Dividir uma compra em
          múltiplas dispensas para fugir do limite legal é fraude. O TCU
          é categórico sobre isso (Acórdão 1.927/2023).
        </li>
      </ul>

      <h2>Inexigibilidade — quando dispensa não cabe</h2>
      <p>
        Se o objeto exige fornecedor exclusivo (medicamento patenteado,
        software proprietário, serviço técnico singular, atração
        artística consagrada), a hipótese é{' '}
        <strong>inexigibilidade</strong> (art. 74), não dispensa. A
        diferença prática é que, na inexigibilidade, não há competição
        possível — e a justificativa precisa ser tecnicamente robusta.
        Empresas que se posicionam como referência em nicho específico
        podem se beneficiar dessa hipótese.
      </p>

      <BlogInlineCTA
        slug="pncp-dispensa-licitacao-quando-aplicar"
        campaign="guias"
        ctaMessage="Não perca dispensas eletrônicas — ciclo é curto."
        ctaText="Testar grátis"
      />

      <h2>Próximos passos no cluster PNCP</h2>
      <p>
        Continue por{' '}
        <Link href="/blog/pncp-modalidade-pregao-eletronico">
          PNCP e pregão eletrônico
        </Link>
        ,{' '}
        <Link href="/blog/pncp-erros-comuns-empresas-iniciantes">
          erros comuns de empresas iniciantes
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
