import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Termos do Plano Fundadores | SmartLic',
  description: 'Termos e condições do Plano Fundadores SmartLic — acesso vitalício one-time R$997',
  robots: { index: false, follow: false },
};

export default function TermosFundadoresPage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-white to-gray-50 dark:from-gray-900 dark:to-gray-950">
      <div className="container mx-auto px-4 py-16 max-w-4xl">
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-8 md:p-12">
          <h1 className="text-4xl font-bold mb-2 text-gray-900 dark:text-white">
            Termos do Plano Fundadores
          </h1>
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
            Vigência a partir de: 07 de maio de 2026
          </p>
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-8">
            Produto: SmartLic — CONFENGE Avaliações e Inteligência Artificial LTDA
          </p>

          <div className="mb-8 p-4 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
            <p className="text-sm text-amber-800 dark:text-amber-200 leading-relaxed">
              <strong>Aviso:</strong> Estes termos complementam os{' '}
              <a href="/termos" className="text-blue-600 dark:text-blue-400 hover:underline">
                Termos Gerais de Serviço
              </a>{' '}
              e são específicos para adquirentes do Plano Fundadores (acesso vitalício one-time).
              Em caso de conflito, estes termos prevalecem para os direitos e obrigações
              relacionados ao Plano Fundadores.
            </p>
          </div>

          <div className="prose prose-gray dark:prose-invert max-w-none">
            <section className="mb-8">
              <h2 className="text-2xl font-semibold mb-4 text-gray-900 dark:text-white">
                Art. 1 — Escopo do Acesso Vitalício
              </h2>
              <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                O <strong>Plano Fundadores</strong> confere ao adquirente acesso permanente ao conjunto de
                funcionalidades self-service do SmartLic na versão disponível à época da contratação,
                incluindo:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-gray-700 dark:text-gray-300 mb-4">
                <li>Busca multi-fonte de licitações públicas (PNCP, PCP v2, ComprasGov v3)</li>
                <li>Classificação por inteligência artificial (GPT-4.1-nano — relevância setorial)</li>
                <li>Análise de viabilidade com 4 fatores (modalidade, timeline, valor, geografia)</li>
                <li>Pipeline de oportunidades (kanban de editais com drag-and-drop)</li>
                <li>Geração de relatórios em Excel e resumo executivo com IA</li>
                <li>Histórico de buscas salvas, sessões e analytics pessoais</li>
              </ul>
              <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-2">
                <strong>O Plano Fundadores não inclui:</strong>
              </p>
              <ul className="list-disc pl-6 space-y-2 text-gray-700 dark:text-gray-300">
                <li>Features premium ou enterprise futuras que venham a ser lançadas em planos distintos</li>
                <li>Suporte prioritário vitalício (suporte disponível via canais padrão)</li>
                <li>Customizações ilimitadas ou desenvolvimento sob demanda</li>
                <li>SLA enterprise com garantia de uptime contratual</li>
                <li>Acesso a módulos de inteligência B2G avançada (Intel Reports, pipeline comercial)
                    que possam ser criados como produtos separados no futuro</li>
              </ul>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold mb-4 text-gray-900 dark:text-white">
                Art. 2 — Cláusula de Evolução da Plataforma
              </h2>
              <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                A SmartLic pode, a qualquer momento, alterar sua arquitetura técnica, modelo de negócio,
                estrutura de preços para novos clientes, ou descontinuar funcionalidades secundárias
                não listadas no escopo do Art. 1.
              </p>
              <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                O Fundador mantém acesso permanente ao escopo definido neste contrato,
                independentemente de mudanças no modelo de precificação aplicadas a novos assinantes.
              </p>
              <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                <strong>Mudanças materiais ao escopo incluído</strong> (remoção de funcionalidade
                listada no Art. 1) serão comunicadas com <strong>90 dias de antecedência</strong> por
                e-mail ao endereço cadastrado, garantindo tempo hábil para decisão de uso ou
                solicitação de reembolso nos termos do Art. 8.
              </p>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold mb-4 text-gray-900 dark:text-white">
                Art. 3 — Fair Use e Uso Aceitável
              </h2>
              <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                O acesso vitalício não isenta o Fundador das políticas de uso aceitável da plataforma.
                <strong> Rate limiting aplica-se a todos os usuários</strong>, incluindo Fundadores,
                para garantir a qualidade do serviço a toda a base de clientes.
              </p>
              <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-2">
                São expressamente proibidos, sob risco de suspensão com aviso prévio:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-gray-700 dark:text-gray-300">
                <li><strong>Revenda ou compartilhamento de acesso</strong> — a licença é pessoal e intransferível</li>
                <li><strong>Scraping massivo</strong> — extração automatizada em volume que exceda o uso normal
                    de plataforma (consulta direta à interface ou API autorizada)</li>
                <li><strong>Automação que degrada o serviço</strong> para outros usuários — bots, scripts de
                    consulta em loop contínuo ou requisições que saturem a infraestrutura compartilhada</li>
              </ul>
              <p className="text-gray-700 dark:text-gray-300 leading-relaxed mt-4">
                Violações reiteradas após aviso formal podem resultar em suspensão permanente,
                sem reembolso da taxa de adesão.
              </p>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold mb-4 text-gray-900 dark:text-white">
                Art. 4 — Sem Garantia de Êxito em Licitações
              </h2>
              <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                A SmartLic é uma <strong>ferramenta de inteligência de mercado</strong>. Sua função é
                descobrir, filtrar, classificar e apresentar oportunidades de licitação pública com base
                em dados disponíveis em APIs oficiais abertas.
              </p>
              <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                O resultado em processos licitatórios depende exclusivamente de fatores externos
                à plataforma, incluindo, mas não se limitando a: documentação de habilitação da empresa,
                qualidade técnica da proposta, formação de preço, estratégia comercial, e critérios de
                julgamento definidos pelo órgão contratante.
              </p>
              <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                <strong>A SmartLic não garante, implícita ou explicitamente, vitória, classificação
                favorável ou qualquer resultado positivo em processos de licitação</strong>, e não se
                responsabiliza por decisões estratégicas ou comerciais tomadas com base nas informações
                apresentadas pela plataforma.
              </p>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold mb-4 text-gray-900 dark:text-white">
                Art. 5 — Ausência de Vínculo Governamental
              </h2>
              <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                A SmartLic é um produto privado da <strong>CONFENGE Avaliações e Inteligência Artificial LTDA</strong>.
                Não possui qualquer vínculo, parceria oficial, credenciamento ou endosso dos seguintes entes:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-gray-700 dark:text-gray-300 mb-4">
                <li>Portal Nacional de Contratações Públicas (PNCP)</li>
                <li>ComprasNet / Ministério da Gestão e da Inovação em Serviços Públicos</li>
                <li>Tribunal de Contas da União (TCU)</li>
                <li>Portal de Compras Públicas (PCP)</li>
                <li>Qualquer órgão, entidade ou poder da Administração Pública direta ou indireta</li>
              </ul>
              <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                A SmartLic atua exclusivamente como <strong>consumidora de dados públicos</strong>
                disponibilizados em APIs abertas pelos próprios entes governamentais, nos termos da
                Lei de Acesso à Informação (Lei 12.527/2011) e da política de dados abertos do
                Governo Federal.
              </p>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold mb-4 text-gray-900 dark:text-white">
                Art. 6 — Benefício de Desconto em Consultoria
              </h2>
              <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                Como reconhecimento pelo apoio na fase inicial da plataforma, o Fundador tem direito a
                <strong> desconto de 50% (cinquenta por cento)</strong> em serviços de consultoria
                contratados diretamente com a SmartLic / CONFENGE.
              </p>
              <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-2">
                Condições de aplicação:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-gray-700 dark:text-gray-300 mb-4">
                <li>Aplica-se exclusivamente a <strong>serviços próprios SmartLic</strong> formalizados
                    em contrato escrito</li>
                <li>Não é transferível a terceiros e não se acumula com outras promoções vigentes</li>
                <li>Não inclui serviços prestados por terceiros, parceiros ou consultorias indicadas
                    pela SmartLic</li>
                <li>Deve ser solicitado antes da emissão da proposta comercial</li>
              </ul>
              <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                <strong>Prazo de validade:</strong> vitalício do cliente — enquanto a linha de
                consultoria estiver ativa — ou até a descontinuação formal do serviço de consultoria,
                o que ocorrer primeiro.
              </p>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold mb-4 text-gray-900 dark:text-white">
                Art. 7 — Prazo e Vagas da Oferta
              </h2>
              <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                A oferta do Plano Fundadores está disponível até o primeiro dos seguintes eventos:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-gray-700 dark:text-gray-300 mb-4">
                <li><strong>Data-limite:</strong> 30 de junho de 2026, às 23h59 (horário de Brasília)</li>
                <li><strong>Limite de vagas:</strong> 50 (cinquenta) adesões</li>
              </ul>
              <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                Após o encerramento da oferta, o acesso vitalício dos Fundadores já inscritos
                permanece ativo e inalterado. Apenas novos ingressos ao Plano Fundadores ficam
                indisponíveis. Os direitos previstos neste instrumento não são afetados pelo
                encerramento do prazo de adesão.
              </p>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold mb-4 text-gray-900 dark:text-white">
                Art. 8 — Direito de Retratação (CDC Art. 49)
              </h2>
              <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                Conforme o artigo 49 do Código de Defesa do Consumidor (Lei 8.078/1990), o consumidor
                que adquiriu o Plano Fundadores fora do estabelecimento comercial (compra online)
                tem direito ao <strong>reembolso integral</strong> da taxa de adesão, sem necessidade
                de justificativa, desde que:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-gray-700 dark:text-gray-300 mb-4">
                <li>A solicitação seja feita <strong>dentro de 7 (sete) dias corridos</strong> contados
                    da data da compra</li>
                <li>O uso acumulado na plataforma não exceda <strong>5 (cinco) buscas realizadas</strong>,
                    critério de fair use adotado para serviços digitais nos quais o conteúdo principal
                    é entregue de forma imediata e continuada</li>
              </ul>
              <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                Para exercer o direito de retratação, o consumidor deve entrar em contato com o
                suporte SmartLic através da plataforma ou pelo e-mail{' '}
                <a href="mailto:tiago@smartlic.tech" className="text-blue-600 dark:text-blue-400 hover:underline">
                  tiago@smartlic.tech
                </a>{' '}
                dentro do prazo.
              </p>
              <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                Reembolsos aprovados são processados via Stripe com prazo estimado de
                <strong> 5 a 10 dias úteis</strong> para crédito no meio de pagamento original.
              </p>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold mb-4 text-gray-900 dark:text-white">
                Art. 9 — Vigência e Foro
              </h2>
              <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                Estes Termos do Plano Fundadores vigem a partir da <strong>data da compra</strong>
                e permanecem válidos enquanto o adquirente mantiver acesso ativo à plataforma.
              </p>
              <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                Para dirimir quaisquer dúvidas ou litígios decorrentes destes Termos, as partes
                elegem o <strong>Foro da Comarca de São Paulo, Estado de São Paulo</strong>, com
                exclusão de qualquer outro, por mais privilegiado que seja.
              </p>
              <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                A versão em português deste documento é a versão oficial e prevalece sobre
                eventuais traduções.
              </p>
            </section>

            <section className="mt-12 p-6 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
              <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
                <strong>Ao concluir a aquisição do Plano Fundadores</strong>, você reconhece ter lido,
                compreendido e concordado com estes Termos, com os{' '}
                <a href="/termos" className="text-blue-600 dark:text-blue-400 hover:underline">
                  Termos Gerais de Serviço
                </a>{' '}
                e com a{' '}
                <a href="/privacidade" className="text-blue-600 dark:text-blue-400 hover:underline">
                  Política de Privacidade
                </a>{' '}
                da SmartLic.
              </p>
            </section>
          </div>

          <div className="mt-12 pt-8 border-t border-gray-200 dark:border-gray-700 flex flex-col sm:flex-row gap-4 justify-between">
            <a
              href="/termos"
              className="inline-flex items-center text-blue-600 dark:text-blue-400 hover:underline"
            >
              ← Termos Gerais de Serviço
            </a>
            <a
              href="/privacidade"
              className="inline-flex items-center text-blue-600 dark:text-blue-400 hover:underline"
            >
              Ver Política de Privacidade →
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
