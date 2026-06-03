/// CONV-016: Orgão urgency signal block.
/// Displays bid recency data with UrgencyBadge and contextual messages.

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

interface OrgaoUrgencyProps {
  atividade_recente?: AtividadeRecente | null;
  nome: string;
}

const MESES: Record<number, string> = {
  1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
  5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
  9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro',
};

export function OrgaoUrgency({ atividade_recente, nome }: OrgaoUrgencyProps) {
  if (!atividade_recente) return null;

  const { contagem_30d, contagem_90d, ultimo_evento_data, sazonalidade_mes_pico } = atividade_recente;
  const daysSinceLast = daysSince(ultimo_evento_data);

  if (contagem_90d === 0) {
    return null;
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 mb-6">
      <div className="flex items-center gap-2 mb-3">
        <UrgencyBadge daysSinceLastEvent={daysSinceLast} />
        <span className="text-sm font-medium text-gray-700">{nome}</span>
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
        {sazonalidade_mes_pico && (
          <div>
            <p className="text-xs text-gray-500">Mês de pico</p>
            <p className="font-semibold text-gray-900">{MESES[sazonalidade_mes_pico] || sazonalidade_mes_pico}</p>
          </div>
        )}
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
