/// CONV-016: Contratos urgency signal block.
/// Displays contract/sector recency data with UrgencyBadge and contextual messages.

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

interface ContratosUrgencyProps {
  atividade_recente?: AtividadeRecente | null;
  sectorName: string;
  ufLabel: string;
}

export function ContratosUrgency({ atividade_recente, sectorName, ufLabel }: ContratosUrgencyProps) {
  if (!atividade_recente) return null;

  const { contagem_30d, contagem_90d, valor_total_30d, tendencia_12m, tendencia_percentual, ultimo_evento_data } = atividade_recente;
  const daysSinceLast = daysSince(ultimo_evento_data);

  if (contagem_90d === 0) {
    return null;
  }

  const valorFmt = valor_total_30d >= 1_000_000
    ? `R$ ${(valor_total_30d / 1_000_000).toFixed(1)} mi`
    : valor_total_30d >= 1_000
    ? `R$ ${(valor_total_30d / 1_000).toFixed(0)} mil`
    : `R$ ${valor_total_30d.toFixed(2)}`;

  const tendenciaIcon = tendencia_12m === 'up' ? '↑' : tendencia_12m === 'down' ? '↓' : '→';

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 mb-6">
      <div className="flex items-center gap-2 mb-3">
        <UrgencyBadge daysSinceLastEvent={daysSinceLast} label={contagem_30d > 0 ? `${contagem_30d} contratos este mês` : undefined} />
        <span className="text-sm font-medium text-gray-700">{sectorName} — {ufLabel}</span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
        <div>
          <p className="text-xs text-gray-500">Contratos (30 dias)</p>
          <p className="font-semibold text-gray-900">{contagem_30d}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Contratos (90 dias)</p>
          <p className="font-semibold text-gray-900">{contagem_90d}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Valor contratado (30d)</p>
          <p className="font-semibold text-green-700">{valorFmt}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Tendência</p>
          <p className={`font-semibold ${
            tendencia_12m === 'up' ? 'text-green-600' :
            tendencia_12m === 'down' ? 'text-red-600' :
            'text-gray-600'
          }`}>
            {tendenciaIcon} {tendencia_12m === 'up' ? `+${tendencia_percentual}%` :
             tendencia_12m === 'down' ? `${tendencia_percentual}%` :
             'estável'}
          </p>
        </div>
      </div>

      {ultimo_evento_data && (
        <p className="text-xs text-gray-400 mt-2">
          Último contrato: {new Date(ultimo_evento_data).toLocaleDateString('pt-BR')}
          {daysSinceLast >= 0 && ` (há ${daysSinceLast} ${daysSinceLast === 1 ? 'dia' : 'dias'})`}
        </p>
      )}
    </div>
  );
}
