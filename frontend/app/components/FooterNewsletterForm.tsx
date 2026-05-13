'use client';

import { useState } from 'react';
import { toast } from 'sonner';

/**
 * COPY-COP-006: Newsletter signup form for the site footer.
 *
 * Renders an email input + sector select + submit button.
 * Posts to /api/lead-capture with source='newsletter'.
 * Shows toast on success/failure.
 */
export function FooterNewsletterForm() {
  const [email, setEmail] = useState('');
  const [sector, setSector] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || loading) return;

    setLoading(true);
    try {
      const res = await fetch('/api/lead-capture', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          source: 'newsletter',
          sector: sector || null,
        }),
      });

      if (res.ok) {
        toast.success('Inscrito! Verifique seu email.');
        setEmail('');
        setSector('');
      } else {
        toast.error('Erro ao inscrever. Tente novamente.');
      }
    } catch {
      toast.error('Erro de conexão. Tente novamente.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <p className="text-sm text-ink-secondary">
        Receba alertas semanais de oportunidades para seu setor
      </p>
      <input
        type="email"
        required
        placeholder="seu@email.com"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-surface-0 text-ink placeholder:text-ink-secondary/50 focus:outline-none focus:ring-2 focus:ring-brand-blue"
      />
      <select
        value={sector}
        onChange={(e) => setSector(e.target.value)}
        className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-surface-0 text-ink focus:outline-none focus:ring-2 focus:ring-brand-blue"
        aria-label="Selecione seu setor"
      >
        <option value="">Todos os setores</option>
        <option value="saude">Saúde</option>
        <option value="informatica">TI e Hardware</option>
        <option value="engenharia">Engenharia</option>
        <option value="alimentos">Alimentação</option>
        <option value="vestuario">Vestuário e Uniformes</option>
        <option value="mobiliario">Mobiliário</option>
        <option value="papelaria">Papelaria</option>
        <option value="software">Software</option>
        <option value="facilities">Facilities</option>
        <option value="vigilancia">Vigilância</option>
        <option value="transporte">Transporte</option>
        <option value="manutencao-predial">Manutenção Predial</option>
        <option value="engenharia-rodoviaria">Eng. Rodoviária</option>
        <option value="materiais-eletricos">Materiais Elétricos</option>
        <option value="materiais-hidraulicos">Materiais Hidráulicos</option>
      </select>
      <button
        type="submit"
        disabled={loading}
        className="w-full px-4 py-2 text-sm font-semibold rounded-lg bg-brand-blue text-white hover:bg-blue-700 transition-colors disabled:opacity-50"
      >
        {loading ? 'Enviando...' : 'Quero receber'}
      </button>
    </form>
  );
}
