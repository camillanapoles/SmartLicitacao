import React from "react";

export interface WalkthroughStepData {
  id: string;
  title: string;
  renderContent: () => React.ReactNode;
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(value);
}

/* ------------------------------------------------------------------ */
/*  Step 1 — Busca inteligente                                         */
/* ------------------------------------------------------------------ */

function Step1Busca() {
  const setores = ["Saúde", "Educação", "Tecnologia da Informação", "Construção Civil", "Transportes"];
  const ufs = ["SP", "RJ", "MG", "RS", "BA", "PR", "SC", "PE", "CE", "DF"];

  return (
    <div className="space-y-4">
      <p className="text-sm text-[var(--ink-secondary)]">
        Selecione o setor da sua empresa, os estados de interesse e o período para encontrar
        licitações compatíveis com seu perfil.
      </p>

      {/* Setor selector */}
      <div>
        <label className="block text-sm font-medium text-[var(--ink)] mb-1.5">
          Setor de atuação
        </label>
        <div className="flex flex-wrap gap-1.5">
          {setores.map((s) => (
            <span
              key={s}
              className={`px-3 py-1.5 text-xs font-medium rounded-full cursor-default ${
                s === "Tecnologia da Informação"
                  ? "bg-[var(--brand-blue)] text-white"
                  : "bg-[var(--surface-1)] text-[var(--ink-secondary)]"
              }`}
            >
              {s}
            </span>
          ))}
        </div>
      </div>

      {/* UFs */}
      <div>
        <label className="block text-sm font-medium text-[var(--ink)] mb-1.5">
          Estados (UFs)
        </label>
        <div className="flex flex-wrap gap-1.5">
          {ufs.map((uf) => (
            <span
              key={uf}
              className={`inline-flex items-center justify-center w-9 h-9 text-xs font-semibold rounded-md cursor-default ${
                ["SP", "RJ", "MG"].includes(uf)
                  ? "bg-[var(--brand-blue)] text-white"
                  : "bg-[var(--surface-1)] text-[var(--ink-secondary)]"
              }`}
            >
              {uf}
            </span>
          ))}
        </div>
      </div>

      {/* Periodo */}
      <div className="flex items-center gap-3">
        <div className="flex-1">
          <label className="block text-sm font-medium text-[var(--ink)] mb-1">
            Período
          </label>
          <div className="flex items-center gap-2">
            <div className="flex-1 h-9 rounded-md border border-[var(--border)] bg-[var(--surface-0)] px-3 flex items-center text-sm text-[var(--ink)]">
              01/05/2026
            </div>
            <span className="text-[var(--ink-muted)] text-sm">&mdash;</span>
            <div className="flex-1 h-9 rounded-md border border-[var(--border)] bg-[var(--surface-0)] px-3 flex items-center text-sm text-[var(--ink)]">
              31/05/2026
            </div>
          </div>
        </div>
      </div>

      {/* Search button */}
      <button
        type="button"
        className="w-full h-10 rounded-button bg-[var(--brand-navy)] text-white text-sm font-medium flex items-center justify-center gap-2 cursor-default"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        Buscar Licitações
      </button>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Step 2 — Resultados                                                */
/* ------------------------------------------------------------------ */

function Step2Resultados() {
  const cards = [
    {
      orgao: "Secretaria Municipal de Educação de São Paulo",
      objeto: "Contratação de serviços de manutenção predial para unidades escolares",
      valor: 4800000,
      uf: "SP",
      data: "15/06/2026",
      score: 87,
    },
    {
      orgao: "Governo do Estado do Rio de Janeiro",
      objeto: "Aquisição de equipamentos de informática para rede estadual de ensino",
      valor: 2350000,
      uf: "RJ",
      data: "22/06/2026",
      score: 72,
    },
    {
      orgao: "Prefeitura Municipal de Belo Horizonte",
      objeto: "Pavimentação e recapeamento asfáltico em 12 bairros",
      valor: 8900000,
      uf: "MG",
      data: "05/07/2026",
      score: 64,
    },
  ];

  return (
    <div className="space-y-4">
      <p className="text-sm text-[var(--ink-secondary)]">
        Resultados encontrados para sua busca. Cada card mostra o órgão, objeto, valor estimado e
        o score de viabilidade calculado pela IA.
      </p>

      <div className="flex items-center justify-between text-xs text-[var(--ink-secondary)] mb-2">
        <span>3 resultados encontrados</span>
        <span>Ordenar por: Relevância</span>
      </div>

      {cards.map((c, i) => (
        <div
          key={i}
          className="rounded-lg border border-[var(--border)] bg-[var(--surface-0)] p-4 space-y-2 cursor-default"
        >
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0">
              <p className="text-xs text-[var(--ink-secondary)] truncate">{c.orgao}</p>
              <p className="text-sm font-medium text-[var(--ink)] mt-0.5 line-clamp-2">{c.objeto}</p>
            </div>
            <span
              className={`shrink-0 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${
                c.score >= 80
                  ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
                  : c.score >= 60
                    ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200"
                    : "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300"
              }`}
            >
              {c.score}%
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-[var(--ink-secondary)]">
            <span>{formatCurrency(c.valor)}</span>
            <span>{c.uf}</span>
            <span>{c.data}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Step 3 — Score de viabilidade                                      */
/* ------------------------------------------------------------------ */

function Step3Viability() {
  const factors = [
    { label: "Modalidade", weight: "30%", value: 85, color: "bg-green-500" },
    { label: "Timeline", weight: "25%", value: 70, color: "bg-yellow-500" },
    { label: "Valor estimado", weight: "25%", value: 92, color: "bg-green-500" },
    { label: "Geografia", weight: "20%", value: 65, color: "bg-yellow-500" },
  ];

  const total = Math.round(factors.reduce((acc, f) => acc + f.value * parseInt(f.weight) / 100, 0));

  return (
    <div className="space-y-4">
      <p className="text-sm text-[var(--ink-secondary)]">
        Cada oportunidade recebe um score de viabilidade de 0 a 100%, calculado com base em 4 fatores
        ponderados pela IA.
      </p>

      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-0)] p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-[var(--ink)]">Score de Viabilidade</h3>
          <span className="text-2xl font-bold text-[var(--brand-blue)]">{total}%</span>
        </div>

        <div className="space-y-2.5">
          {factors.map((f) => (
            <div key={f.label}>
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-[var(--ink)] font-medium">{f.label}</span>
                <div className="flex items-center gap-2">
                  <span className="text-[var(--ink-muted)]">peso {f.weight}</span>
                  <span className="text-[var(--ink)] font-semibold">{f.value}%</span>
                </div>
              </div>
              <div className="h-2 rounded-full bg-[var(--surface-1)] overflow-hidden">
                <div
                  className={`h-full rounded-full ${f.color} transition-all`}
                  style={{ width: `${f.value}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Step 4 — Pipeline                                                  */
/* ------------------------------------------------------------------ */

function Step4Pipeline() {
  const columns = [
    {
      title: "Novo",
      color: "bg-blue-500",
      cards: [
        { label: "Manutenção predial - SP", value: "R$ 4,8 mi" },
        { label: "Equip. informática - RJ", value: "R$ 2,3 mi" },
      ],
    },
    {
      title: "Em Análise",
      color: "bg-yellow-500",
      cards: [
        { label: "Pavimentação - BH", value: "R$ 8,9 mi" },
      ],
    },
    {
      title: "Proposta",
      color: "bg-green-500",
      cards: [
        { label: "Medicamentos - BA", value: "R$ 12,5 mi" },
      ],
    },
  ];

  return (
    <div className="space-y-4">
      <p className="text-sm text-[var(--ink-secondary)]">
        Organize as oportunidades encontradas em um kanban de pipeline. Arraste os cards entre as
        colunas conforme avança no processo.
      </p>

      <div className="grid grid-cols-3 gap-2">
        {columns.map((col) => (
          <div
            key={col.title}
            className="rounded-lg border border-[var(--border)] bg-[var(--surface-1)] p-2"
          >
            <div className="flex items-center gap-1.5 mb-2">
              <span className={`w-2 h-2 rounded-full ${col.color}`} />
              <span className="text-xs font-semibold text-[var(--ink)]">{col.title}</span>
            </div>
            <div className="space-y-1.5">
              {col.cards.map((card) => (
                <div
                  key={card.label}
                  className="rounded-md bg-[var(--surface-0)] border border-[var(--border)] p-2 cursor-default"
                >
                  <p className="text-xs font-medium text-[var(--ink)] leading-tight">{card.label}</p>
                  <p className="text-xs text-[var(--ink-secondary)] mt-0.5">{card.value}</p>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Step 5 — Exportação                                                */
/* ------------------------------------------------------------------ */

function Step5Export() {
  return (
    <div className="space-y-4">
      <p className="text-sm text-[var(--ink-secondary)]">
        Exporte os resultados da sua busca em formato Excel ou PDF para compartilhar com sua equipe
        ou usar em apresentações.
      </p>

      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-0)] p-4 space-y-3">
        <h3 className="text-sm font-semibold text-[var(--ink)]">Exportar Resultados</h3>

        <div className="space-y-2">
          <label className="flex items-center gap-3 p-3 rounded-md border border-[var(--brand-blue)] bg-[var(--brand-blue)]/5 cursor-default">
            <input type="radio" checked readOnly className="accent-[var(--brand-blue)]" />
            <div>
              <p className="text-sm font-medium text-[var(--ink)]">Excel (.xlsx)</p>
              <p className="text-xs text-[var(--ink-secondary)]">Planilha com dados completos, filtros e totais</p>
            </div>
          </label>

          <label className="flex items-center gap-3 p-3 rounded-md border border-[var(--border)] cursor-default">
            <input type="radio" readOnly className="accent-[var(--brand-blue)]" />
            <div>
              <p className="text-sm font-medium text-[var(--ink)]">PDF</p>
              <p className="text-xs text-[var(--ink-secondary)]">Resumo executivo com principais oportunidades</p>
            </div>
          </label>
        </div>

        <div className="flex items-center gap-2 text-xs text-[var(--ink-secondary)] pt-1">
          <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
          </svg>
          <span>Relatório assinado digitalmente com dados oficiais do PNCP</span>
        </div>

        <button
          type="button"
          className="w-full h-10 rounded-button bg-[var(--brand-blue)] text-white text-sm font-medium flex items-center justify-center gap-2 cursor-default"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
          </svg>
          Exportar
        </button>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Steps array                                                        */
/* ------------------------------------------------------------------ */

export const WALKTHROUGH_STEPS: WalkthroughStepData[] = [
  {
    id: "busca-inteligente",
    title: "Busca Inteligente",
    renderContent: () => <Step1Busca />,
  },
  {
    id: "resultados",
    title: "Resultados da Busca",
    renderContent: () => <Step2Resultados />,
  },
  {
    id: "score-viabilidade",
    title: "Score de Viabilidade",
    renderContent: () => <Step3Viability />,
  },
  {
    id: "pipeline",
    title: "Pipeline de Oportunidades",
    renderContent: () => <Step4Pipeline />,
  },
  {
    id: "exportacao",
    title: "Exportação de Dados",
    renderContent: () => <Step5Export />,
  },
];
