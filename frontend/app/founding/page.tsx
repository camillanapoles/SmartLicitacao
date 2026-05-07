import { permanentRedirect } from 'next/navigation';

/**
 * 301 permanent redirect: /founding → /fundadores
 * Issue #786 — pt-BR route rename.
 */
export default function FoundingPage() {
  permanentRedirect('/fundadores');
}
