import { Suspense } from 'react';
import type { Metadata } from 'next';
import { FundadoresObrigadoClient } from './FundadoresObrigadoClient';

/**
 * Thank-you page after a successful Founders checkout.
 *
 * Server Component shell: exports metadata and wraps the dynamic content
 * in Suspense (required because FundadoresObrigadoClient reads useSearchParams).
 * The actual checkout polling and UI are handled by FundadoresObrigadoClient ("use client").
 */
export const metadata: Metadata = {
  title: 'Bem-vindo ao Plano Fundadores | SmartLic',
  description: 'Seu acesso vitalício ao SmartLic está sendo ativado.',
  robots: { index: false, follow: false },
};

export default function FundadoresObrigadoPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-pulse text-gray-500">Carregando...</div>
      </div>
    }>
      <FundadoresObrigadoClient />
    </Suspense>
  );
}
