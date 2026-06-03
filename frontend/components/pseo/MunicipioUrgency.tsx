/// CONV-016: Municipio urgency signal block.
/// Displays bid recency data with UrgencyBadge and contextual messages for municipality pages.

import React from 'react';
import { UrgencyBadge } from './UrgencyBadge';
import { daysSince } from '@/lib/urgency-utils';

interface AtividadeRecente {
  contagem_30d: number;
  contagem_90d: number;
  valor_total_30d: number;
  tendencia_12m: string;
  tendencia_percentual: number;
  ultimo_evento_data: string | null;
  sazonalidade_mes_pico: number | null;
}

interface MunicipioUrgencyProps {
  atividade_recente?: AtividadeRecente | null;
  nome: string;
  uf: string;
}

export function MunicipioUrgency({ atividade_recente, nome, uf }: MunicipioUrgencyProps) {
  if (!atividade_recente) return null;

  const { contagem_30d, contagem_90d, valor_total_30d, ultimo_evento_data } = atividade_recente;
  const daysSinceLast = daysSince(ultimo_evento_data);

  if (contagem_90d === 0) {
    return null;
  }

  const valorFmt = valor_total_30d >= 1_000_000
    ? `R$ ${(valor_total_30d / 1_000_000).toFixed(1)} mi`
    : valor_total_30d >= 1_000
    ? `R$ ${(valor_total_30d / 1_000).toFixed(0)} mil`
    : `R$ ${valor_total_30d.toFixed(2)}`;

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 mb-6">
      <div className="flex items-center gap-2 mb-3">
        <UrgencyBadge daysSinceLastEvent={daysSinceLast} label={contagem_30d > 0 ? `${contagem_30d} licitações este mês` : undefined} />
        <span className="text-sm font-medium text-gray-700">{nome} — {uf}</span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm">
        <div>
          <p className="text-xs text-gray-500">Licitações (30 dias)</p>
          <p className="font-semibold text-gray-900">{contagem_30d}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Licitações (90 dias)</p>
          <p className="font-semibold text-gray-900">{contagem_90d}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Valor estimado (30d)</p>
          <p className="font-semibold text-green-700">{valorFmt}</p>
        </div>
      </div>

      {ultimo_evento_data && (
        <p className="text-xs text-gray-400 mt-2">
          Última licitação: {new Date(ultimo_evento_data).toLocaleDateString('pt-BR')}
          {daysSinceLast >= 0 && ` (há ${daysSinceLast} ${daysSinceLast === 1 ? 'dia' : 'dias'})`}
        </p>
      )}
    </div>
  );
}
