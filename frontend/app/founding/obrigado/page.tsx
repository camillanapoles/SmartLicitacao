import { permanentRedirect } from 'next/navigation';

/**
 * 301 permanent redirect: /founding/obrigado → /fundadores/obrigado
 * Issue #786 — pt-BR route rename.
 */
export default function FoundingObrigadoPage() {
  permanentRedirect('/fundadores/obrigado');
}
