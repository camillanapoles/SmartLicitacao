'use client';

/**
 * Thin client island for /consultoria-b2g.
 * Wraps DiagnosticForm so we can keep the parent page.tsx as a Server Component.
 */
import DiagnosticForm from '@/components/forms/DiagnosticForm';

interface Props {
  defaultModalidade?: 'radar' | 'report' | 'intel' | 'nao_sei';
}

export default function ConsultoriaForm({ defaultModalidade }: Props) {
  return (
    <DiagnosticForm
      source="consultoria-b2g"
      defaultModalidade={defaultModalidade}
    />
  );
}
