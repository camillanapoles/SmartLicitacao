'use client';

import { useState } from 'react';
import Link from 'next/link';

/**
 * CRO-CTA-003: Microfiltro Setorial para /blog/licitacoes-ti-software-2026
 *
 * Renderiza 6 opções de foco em TI como radio buttons. A seleção persiste
 * via state e alimenta os query params dos botões de CTA.
 */
const FOCOS_TI = [
  { id: 'desenvolvimento', label: 'Desenvolvimento de software sob demanda' },
  { id: 'licenciamento', label: 'Licenciamento e revenda (Microsoft, Oracle, etc.)' },
  { id: 'suporte', label: 'Suporte técnico e help desk' },
  { id: 'infra', label: 'Infraestrutura e cloud' },
  { id: 'seguranca', label: 'Segurança da informação' },
  { id: 'fabrica', label: 'Fábrica de software (body shop)' },
] as const;

export default function MicroFiltroSetorial() {
  const [selectedFoco, setSelectedFoco] = useState<string | null>(null);

  const buscarHref = selectedFoco
    ? `/buscar?setor=TI&foco=${selectedFoco}&source=blog-ti`
    : '/buscar?setor=TI&source=blog-ti';

  const buttonText = selectedFoco
    ? `Ver editais de ${FOCOS_TI.find((f) => f.id === selectedFoco)?.label.toLowerCase() || selectedFoco} abertos agora`
    : 'Ver editais de TI abertos agora';

  return (
    <div className="not-prose my-6 sm:my-8 bg-gradient-to-br from-brand-navy to-brand-blue rounded-xl p-5 sm:p-8 text-white">
      <p className="text-lg sm:text-xl font-bold mb-4">
        Qual o seu foco em TI?
      </p>
      <div className="space-y-2 mb-5">
        {FOCOS_TI.map((foco) => (
          <label
            key={foco.id}
            className={`flex items-center gap-3 p-2.5 rounded-lg cursor-pointer transition-colors ${
              selectedFoco === foco.id
                ? 'bg-white/20 ring-1 ring-white/40'
                : 'hover:bg-white/10'
            }`}
          >
            <input
              type="radio"
              name="foco-ti"
              value={foco.id}
              checked={selectedFoco === foco.id}
              onChange={() => setSelectedFoco(foco.id)}
              className="accent-white w-4 h-4"
            />
            <span className="text-sm sm:text-base text-white/90">{foco.label}</span>
          </label>
        ))}
      </div>
      <Link
        href={buscarHref}
        className="inline-block bg-white text-brand-navy font-semibold px-5 sm:px-6 py-2.5 sm:py-3 rounded-button text-sm sm:text-base transition-all hover:scale-[1.02] active:scale-[0.98]"
      >
        {buttonText}
      </Link>
      <p className="text-xs text-white/60 mt-3">
        Sua seleção filtra os editais por relevância real. Sem cadastro para ver a lista.
      </p>
    </div>
  );
}
