'use client';

/**
 * Client island for /orgaos-publicos contact form.
 * Submits to the lead-capture API with source='orgaos-publicos'.
 */

import { useState, useRef } from 'react';
import { trackFormStarted, trackFormSubmitted } from '@/lib/analytics-events';
import { getStoredUTMParams } from '@/hooks/useAnalytics';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Status = 'idle' | 'loading' | 'success' | 'error';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function validate(fields: {
  nome: string;
  orgao: string;
  cargo: string;
  email: string;
  telefone: string;
  servidores: string;
  mensagem: string;
}): string | null {
  if (!fields.nome.trim() || fields.nome.trim().length < 2)
    return 'Nome obrigatório (mínimo 2 caracteres).';
  if (!fields.email.trim() || !EMAIL_RE.test(fields.email.trim()))
    return 'Informe um e-mail válido.';
  return null;
}

function formatPhone(raw: string): string {
  const digits = raw.replace(/\D/g, '').slice(0, 11);
  if (digits.length <= 2) return digits.length ? `(${digits}` : '';
  if (digits.length <= 7)
    return `(${digits.slice(0, 2)}) ${digits.slice(2)}`;
  return `(${digits.slice(0, 2)}) ${digits.slice(2, 7)}-${digits.slice(7)}`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function OrgaosPublicosForm() {
  const [nome, setNome] = useState('');
  const [orgao, setOrgao] = useState('');
  const [cargo, setCargo] = useState('');
  const [email, setEmail] = useState('');
  const [telefone, setTelefone] = useState('');
  const [servidores, setServidores] = useState('');
  const [mensagem, setMensagem] = useState('');

  const [status, setStatus] = useState<Status>('idle');
  const [errorMsg, setErrorMsg] = useState('');

  const startedRef = useRef(false);

  function handleFirstTouch() {
    if (startedRef.current) return;
    startedRef.current = true;
    trackFormStarted({ form_name: 'orgaos_publicos_form', source: 'orgaos-publicos' });
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();

    const error = validate({ nome, orgao, cargo, email, telefone, servidores, mensagem });
    if (error) {
      setErrorMsg(error);
      setStatus('error');
      return;
    }

    setStatus('loading');
    setErrorMsg('');

    const utms = getStoredUTMParams();

    try {
      const res = await fetch('/api/lead-capture', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nome: nome.trim(),
          email: email.trim().toLowerCase(),
          telefone: telefone.replace(/\D/g, '') || undefined,
          empresa: orgao.trim() || undefined,
          mensagem: [
            cargo.trim() && `Cargo: ${cargo.trim()}`,
            servidores && `Servidores na área de licitação: ~${servidores}`,
            mensagem.trim() && mensagem.trim(),
          ]
            .filter(Boolean)
            .join(' | '),
          source: 'orgaos-publicos',
          ...utms,
        }),
      });

      if (!res.ok) {
        let msg = 'Não foi possível enviar. Tente novamente em instantes.';
        try {
          const data = await res.json();
          if (typeof data?.error === 'string') msg = data.error;
          else if (typeof data?.detail === 'string') msg = data.detail;
        } catch {
          // ignore JSON parse errors
        }
        setErrorMsg(msg);
        setStatus('error');
        return;
      }

      trackFormSubmitted({
        form_name: 'orgaos_publicos_form',
        source: 'orgaos-publicos',
      });

      setStatus('success');
    } catch (err) {
      import('@sentry/nextjs')
        .then((Sentry) => {
          Sentry.captureException(err, {
            tags: { component: 'OrgaosPublicosForm' },
          });
        })
        .catch(() => {});
      setErrorMsg('Falha de rede. Verifique sua conexão e tente novamente.');
      setStatus('error');
    }
  }

  const loading = status === 'loading';
  const inputBase =
    'mt-1 block w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-500 disabled:bg-slate-50 disabled:text-slate-400';

  if (status === 'success') {
    return (
      <div
        role="status"
        aria-live="polite"
        className="rounded-xl bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 p-6 sm:p-8 text-center"
      >
        <p className="text-green-800 dark:text-green-200 font-medium text-lg">
          Recebemos seu contato! Retornaremos em até 48 horas com uma análise
          personalizada para o seu órgão.
        </p>
        <p className="text-green-700 dark:text-green-300 text-sm mt-2">
          Enquanto isso, conheça mais sobre a plataforma{' '}
          <a href="/buscar" className="underline font-semibold">
            SmartLic
          </a>
          .
        </p>
      </div>
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 p-6 sm:p-8 space-y-4"
      noValidate
    >
      {/* Nome */}
      <div>
        <label
          htmlFor="op-nome"
          className="block text-sm font-medium text-slate-900 dark:text-slate-100"
        >
          Nome completo <span className="text-red-500">*</span>
        </label>
        <input
          id="op-nome"
          type="text"
          value={nome}
          onChange={(e) => setNome(e.target.value)}
          onFocus={handleFirstTouch}
          required
          maxLength={200}
          placeholder="Seu nome completo"
          className={inputBase}
          disabled={loading}
        />
      </div>

      {/* Órgão + Cargo side by side */}
      <div className="grid sm:grid-cols-2 gap-4">
        <div>
          <label
            htmlFor="op-orgao"
            className="block text-sm font-medium text-slate-900 dark:text-slate-100"
          >
            Órgão público{' '}
            <span className="text-slate-400 font-normal">(opcional)</span>
          </label>
          <input
            id="op-orgao"
            type="text"
            value={orgao}
            onChange={(e) => setOrgao(e.target.value)}
            onFocus={handleFirstTouch}
            maxLength={200}
            placeholder="Prefeitura, secretaria, autarquia..."
            className={inputBase}
            disabled={loading}
          />
        </div>

        <div>
          <label
            htmlFor="op-cargo"
            className="block text-sm font-medium text-slate-900 dark:text-slate-100"
          >
            Cargo{' '}
            <span className="text-slate-400 font-normal">(opcional)</span>
          </label>
          <input
            id="op-cargo"
            type="text"
            value={cargo}
            onChange={(e) => setCargo(e.target.value)}
            onFocus={handleFirstTouch}
            maxLength={200}
            placeholder="Secretário, diretor, pregoeiro..."
            className={inputBase}
            disabled={loading}
          />
        </div>
      </div>

      {/* E-mail + Telefone side by side */}
      <div className="grid sm:grid-cols-2 gap-4">
        <div>
          <label
            htmlFor="op-email"
            className="block text-sm font-medium text-slate-900 dark:text-slate-100"
          >
            E-mail institucional <span className="text-red-500">*</span>
          </label>
          <input
            id="op-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            onFocus={handleFirstTouch}
            required
            maxLength={320}
            placeholder="seu@orgao.gov.br"
            className={inputBase}
            disabled={loading}
          />
        </div>

        <div>
          <label
            htmlFor="op-telefone"
            className="block text-sm font-medium text-slate-900 dark:text-slate-100"
          >
            Telefone{' '}
            <span className="text-slate-400 font-normal">(opcional)</span>
          </label>
          <input
            id="op-telefone"
            type="tel"
            inputMode="numeric"
            value={telefone}
            onChange={(e) => setTelefone(formatPhone(e.target.value))}
            onFocus={handleFirstTouch}
            placeholder="(48) 99999-9999"
            className={inputBase}
            disabled={loading}
          />
        </div>
      </div>

      {/* Servidores na área de licitação */}
      <div>
        <label
          htmlFor="op-servidores"
          className="block text-sm font-medium text-slate-900 dark:text-slate-100"
        >
          Servidores na área de compras/licitação{' '}
          <span className="text-slate-400 font-normal">(opcional)</span>
        </label>
        <select
          id="op-servidores"
          value={servidores}
          onChange={(e) => setServidores(e.target.value)}
          onFocus={handleFirstTouch}
          className={inputBase}
          disabled={loading}
        >
          <option value="">Selecione...</option>
          <option value="1-5">1 a 5</option>
          <option value="6-15">6 a 15</option>
          <option value="16-50">16 a 50</option>
          <option value="50+">Mais de 50</option>
        </select>
      </div>

      {/* Mensagem */}
      <div>
        <label
          htmlFor="op-mensagem"
          className="block text-sm font-medium text-slate-900 dark:text-slate-100"
        >
          Mensagem{' '}
          <span className="text-slate-400 font-normal">(opcional)</span>
        </label>
        <textarea
          id="op-mensagem"
          value={mensagem}
          onChange={(e) => setMensagem(e.target.value)}
          onFocus={handleFirstTouch}
          maxLength={500}
          rows={4}
          placeholder="Conte sobre sua necessidade — quantos editais por mês, principais dificuldades, prazos..."
          className={inputBase}
          disabled={loading}
        />
        {mensagem.length > 400 && (
          <p className="mt-1 text-xs text-slate-500 text-right">
            {mensagem.length}/500
          </p>
        )}
      </div>

      {/* Error */}
      {status === 'error' && errorMsg && (
        <div
          role="alert"
          className="rounded bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-800"
        >
          {errorMsg}
        </div>
      )}

      {/* Submit */}
      <button
        type="submit"
        disabled={loading}
        className="w-full rounded-lg bg-blue-600 px-4 py-3 font-semibold text-white hover:bg-blue-700 disabled:bg-slate-300 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
      >
        {loading ? 'Enviando...' : 'Solicitar contato comercial'}
      </button>
    </form>
  );
}
