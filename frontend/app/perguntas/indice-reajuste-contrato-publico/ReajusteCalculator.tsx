'use client';

import { useState } from 'react';

/* ------------------------------------------------------------------
 * Hardcoded annual rates (IBGE/FGV official data + 2025 estimate)
 * Source: IBGE (IPCA/INPC) and FGV (IGP-M)
 * 2025 values are running estimates as of May 2026.
 * ------------------------------------------------------------------ */
const RATES: Record<string, Record<number, number>> = {
  IPCA: { 2020: 4.52, 2021: 10.06, 2022: 5.79, 2023: 4.62, 2024: 4.83, 2025: 5.48 },
  INPC: { 2020: 5.45, 2021: 10.16, 2022: 5.93, 2023: 3.71, 2024: 4.77, 2025: 5.2 },
  'IGP-M': { 2020: 23.14, 2021: 17.78, 2022: 5.45, 2023: -3.18, 2024: 6.54, 2025: 7.0 },
};

type Indice = 'IPCA' | 'INPC' | 'IGP-M';
type Periodicidade = 'anual' | 'semestral' | 'trimestral';

interface CalcResult {
  valorReajustado: number;
  percentualVariacao: number;
  variacaoAcumulada: number;
  periodos: number;
  indiceUsado: Indice;
  taxaPorPeriodo: number;
}

function getAnnualRate(indice: Indice, year: number): number {
  const ratesForIndice = RATES[indice];
  if (ratesForIndice[year] !== undefined) return ratesForIndice[year];
  // Fallback: use most recent available year
  const years = Object.keys(ratesForIndice).map(Number).sort((a, b) => b - a);
  return ratesForIndice[years[0]];
}

function calcularReajuste(
  valorBase: number,
  startYearMonth: string, // "YYYY-MM"
  adjustYearMonth: string, // "YYYY-MM"
  indice: Indice,
  periodicidade: Periodicidade,
): CalcResult | null {
  if (!valorBase || !startYearMonth || !adjustYearMonth) return null;

  const [startYear, startMonth] = startYearMonth.split('-').map(Number);
  const [adjustYear, adjustMonth] = adjustYearMonth.split('-').map(Number);

  const startDate = new Date(startYear, startMonth - 1);
  const adjustDate = new Date(adjustYear, adjustMonth - 1);

  if (adjustDate <= startDate) return null;

  const monthsDiff =
    (adjustYear - startYear) * 12 + (adjustMonth - startMonth);

  const periodsPerYear: Record<Periodicidade, number> = {
    anual: 1,
    semestral: 2,
    trimestral: 4,
  };
  const periods = periodsPerYear[periodicidade];
  const fractionPerPeriod = 1 / periods;

  // Compute compounded rate for the span, year by year
  let compoundedFactor = 1;
  const totalYears = monthsDiff / 12;

  // We iterate year by year (partial years allowed at boundaries)
  let remainingFraction = totalYears;
  let currentYear = startYear;

  while (remainingFraction > 0.001) {
    const yearFraction = Math.min(remainingFraction, 1);
    const annualRate = getAnnualRate(indice, currentYear) / 100;
    compoundedFactor *= Math.pow(1 + annualRate, yearFraction);
    remainingFraction -= yearFraction;
    currentYear += 1;
  }

  // How many discrete adjustment periods have elapsed
  const numPeriods = Math.floor(monthsDiff / (12 / periods));
  if (numPeriods < 1) return null; // minimum 1 period required

  // Rate per period from the compounded annual factor (proportional)
  // We use the proportional fraction of the annual rate per period
  // (simple, defensible for estimativa)
  const effectiveAnnualPct = (compoundedFactor - 1) * 100;
  const pctPerPeriod = effectiveAnnualPct * fractionPerPeriod;

  // Apply the rate compounded over the number of full periods
  const ratePerPeriodDecimal = pctPerPeriod / 100;
  const adjustmentFactor = Math.pow(1 + ratePerPeriodDecimal, numPeriods);
  const valorReajustado = valorBase * adjustmentFactor;
  const variacaoAcumulada = valorReajustado - valorBase;
  const percentualVariacao = (adjustmentFactor - 1) * 100;

  return {
    valorReajustado,
    percentualVariacao,
    variacaoAcumulada,
    periodos: numPeriods,
    indiceUsado: indice,
    taxaPorPeriodo: pctPerPeriod,
  };
}

function formatBRL(value: number): string {
  return value.toLocaleString('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function formatPct(value: number): string {
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
}

export default function ReajusteCalculator() {
  const [valorBase, setValorBase] = useState('');
  const [startDate, setStartDate] = useState('');
  const [adjustDate, setAdjustDate] = useState('');
  const [indice, setIndice] = useState<Indice>('IPCA');
  const [periodicidade, setPeriodicidade] = useState<Periodicidade>('anual');
  const [result, setResult] = useState<CalcResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  function handleCalc(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaved(false);

    const numValor = parseFloat(valorBase.replace(/\./g, '').replace(',', '.'));
    if (!numValor || numValor <= 0) {
      setError('Informe um valor base válido maior que zero.');
      setResult(null);
      return;
    }

    const calc = calcularReajuste(numValor, startDate, adjustDate, indice, periodicidade);
    if (!calc) {
      setError(
        'A data de aniversário deve ser posterior à data de início com pelo menos um período completo.',
      );
      setResult(null);
      return;
    }

    setResult(calc);
  }

  function handleValorInput(raw: string) {
    // Allow only digits and separators
    const cleaned = raw.replace(/[^0-9,]/g, '');
    setValorBase(cleaned);
  }

  const periodicidadeLabel: Record<Periodicidade, string> = {
    anual: 'ano',
    semestral: 'semestre',
    trimestral: 'trimestre',
  };

  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface-1)] overflow-hidden mb-8">
      {/* Header */}
      <div className="bg-[var(--brand-blue)] px-6 py-4">
        <h2 className="text-white font-bold text-xl">
          Calculadora de Reajuste Contratual
        </h2>
        <p className="text-blue-100 text-sm mt-1">
          IPCA · INPC · IGP-M — resultado imediato, sem cadastro
        </p>
      </div>

      <form onSubmit={handleCalc} className="p-6 space-y-5">
        {/* Valor base */}
        <div>
          <label
            htmlFor="calc-valor"
            className="block text-sm font-semibold text-[var(--ink-secondary)] mb-1"
          >
            Valor base do contrato (R$)
          </label>
          <input
            id="calc-valor"
            type="text"
            inputMode="decimal"
            required
            placeholder="Ex: 150.000,00"
            value={valorBase}
            onChange={(e) => handleValorInput(e.target.value)}
            className="w-full px-4 py-3 rounded-lg border border-[var(--border)] bg-[var(--surface-0)] text-[var(--ink-primary)] placeholder:text-[var(--ink-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--brand-blue)] min-h-[44px]"
          />
        </div>

        {/* Datas */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label
              htmlFor="calc-inicio"
              className="block text-sm font-semibold text-[var(--ink-secondary)] mb-1"
            >
              Data de início da vigência
            </label>
            <input
              id="calc-inicio"
              type="month"
              required
              min="2019-01"
              max="2030-12"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full px-4 py-3 rounded-lg border border-[var(--border)] bg-[var(--surface-0)] text-[var(--ink-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--brand-blue)] min-h-[44px]"
            />
          </div>
          <div>
            <label
              htmlFor="calc-aniversario"
              className="block text-sm font-semibold text-[var(--ink-secondary)] mb-1"
            >
              Data de aniversário / reajuste
            </label>
            <input
              id="calc-aniversario"
              type="month"
              required
              min="2019-01"
              max="2030-12"
              value={adjustDate}
              onChange={(e) => setAdjustDate(e.target.value)}
              className="w-full px-4 py-3 rounded-lg border border-[var(--border)] bg-[var(--surface-0)] text-[var(--ink-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--brand-blue)] min-h-[44px]"
            />
          </div>
        </div>

        {/* Índice e Periodicidade */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label
              htmlFor="calc-indice"
              className="block text-sm font-semibold text-[var(--ink-secondary)] mb-1"
            >
              Índice de reajuste
            </label>
            <select
              id="calc-indice"
              value={indice}
              onChange={(e) => setIndice(e.target.value as Indice)}
              className="w-full px-4 py-3 rounded-lg border border-[var(--border)] bg-[var(--surface-0)] text-[var(--ink-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--brand-blue)] min-h-[44px]"
            >
              <option value="IPCA">IPCA — IBGE (inflação oficial)</option>
              <option value="INPC">INPC — IBGE (mão de obra)</option>
              <option value="IGP-M">IGP-M — FGV (aluguéis e fornecimentos)</option>
            </select>
          </div>
          <div>
            <label
              htmlFor="calc-periodicidade"
              className="block text-sm font-semibold text-[var(--ink-secondary)] mb-1"
            >
              Periodicidade
            </label>
            <select
              id="calc-periodicidade"
              value={periodicidade}
              onChange={(e) => setPeriodicidade(e.target.value as Periodicidade)}
              className="w-full px-4 py-3 rounded-lg border border-[var(--border)] bg-[var(--surface-0)] text-[var(--ink-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--brand-blue)] min-h-[44px]"
            >
              <option value="anual">Anual (12 meses)</option>
              <option value="semestral">Semestral (6 meses)</option>
              <option value="trimestral">Trimestral (3 meses)</option>
            </select>
          </div>
        </div>

        {error && (
          <p className="text-sm text-red-600 bg-red-50 rounded-lg px-4 py-3" role="alert">
            {error}
          </p>
        )}

        <button
          type="submit"
          className="w-full py-3 px-6 bg-[var(--brand-blue)] hover:bg-[var(--brand-blue-hover)] text-white font-bold rounded-lg transition-colors min-h-[44px]"
        >
          Calcular reajuste
        </button>
      </form>

      {/* Result */}
      {result && (
        <div className="border-t border-[var(--border)] p-6">
          <h3 className="font-bold text-lg text-[var(--ink-primary)] mb-4">
            Resultado do reajuste
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-5">
            {/* Valor reajustado */}
            <div className="rounded-xl bg-[var(--brand-blue)] p-4 text-center">
              <p className="text-blue-100 text-xs font-medium uppercase tracking-wide">
                Valor reajustado
              </p>
              <p className="text-white font-bold text-2xl mt-1 break-all">
                {formatBRL(result.valorReajustado)}
              </p>
            </div>

            {/* Variação */}
            <div className="rounded-xl bg-[var(--surface-2)] p-4 text-center border border-[var(--border)]">
              <p className="text-[var(--ink-muted)] text-xs font-medium uppercase tracking-wide">
                Variação acumulada
              </p>
              <p
                className={`font-bold text-2xl mt-1 ${result.percentualVariacao >= 0 ? 'text-green-600' : 'text-red-600'}`}
              >
                {formatPct(result.percentualVariacao)}
              </p>
            </div>

            {/* Acréscimo em R$ */}
            <div className="rounded-xl bg-[var(--surface-2)] p-4 text-center border border-[var(--border)]">
              <p className="text-[var(--ink-muted)] text-xs font-medium uppercase tracking-wide">
                Acréscimo em R$
              </p>
              <p
                className={`font-bold text-2xl mt-1 break-all ${result.variacaoAcumulada >= 0 ? 'text-green-600' : 'text-red-600'}`}
              >
                {formatBRL(result.variacaoAcumulada)}
              </p>
            </div>
          </div>

          {/* Detalhes */}
          <div className="rounded-lg bg-[var(--surface-1)] border border-[var(--border)] p-4 text-sm text-[var(--ink-secondary)] space-y-1">
            <p>
              <span className="font-medium">Índice:</span> {result.indiceUsado}
            </p>
            <p>
              <span className="font-medium">Períodos aplicados:</span>{' '}
              {result.periodos} {periodicidadeLabel[periodicidade]}
              {result.periodos !== 1 ? 's' : ''}
            </p>
            <p>
              <span className="font-medium">Taxa por período:</span>{' '}
              {result.taxaPorPeriodo.toFixed(4)}%
            </p>
            <p className="text-[var(--ink-muted)] text-xs pt-1">
              Estimativa com base em taxas anuais acumuladas (IBGE/FGV). Use os índices oficiais
              publicados pelo IBGE ou FGV para fins contratuais.
            </p>
          </div>

          {/* Salvar */}
          <button
            type="button"
            disabled={saved}
            onClick={() => {
              const text =
                `Cálculo de reajuste — ${result.indiceUsado}\n` +
                `Valor base: ${formatBRL(parseFloat(valorBase.replace(',', '.')) || 0)}\n` +
                `Valor reajustado: ${formatBRL(result.valorReajustado)}\n` +
                `Variação: ${formatPct(result.percentualVariacao)}\n` +
                `Acréscimo: ${formatBRL(result.variacaoAcumulada)}`;
              navigator.clipboard.writeText(text).then(() => setSaved(true));
            }}
            className="mt-4 w-full py-2 px-4 border border-[var(--border)] rounded-lg text-sm font-medium text-[var(--ink-secondary)] hover:bg-[var(--surface-2)] transition-colors disabled:opacity-60 min-h-[44px]"
          >
            {saved ? 'Copiado para a área de transferência!' : 'Copiar resultado'}
          </button>
        </div>
      )}
    </div>
  );
}
