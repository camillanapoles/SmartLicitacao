import type { Metadata } from 'next';
import FundadoresObrigadoClient from './FundadoresObrigadoClient';

export const metadata: Metadata = {
  title: 'Bem-vindo ao Plano Fundadores SmartLic',
  description: 'Próximos passos do seu acesso vitalício SmartLic como fundador.',
  robots: { index: false, follow: false },
};

export default function FundadoresObrigadoPage() {
  return <FundadoresObrigadoClient />;
}
