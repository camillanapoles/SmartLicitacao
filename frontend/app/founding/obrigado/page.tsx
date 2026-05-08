import { redirect } from 'next/navigation';

interface Props {
  searchParams: Promise<{ session_id?: string }>;
}

/**
 * Temporary 307 redirect: /founding/obrigado → /fundadores/obrigado
 * Preserves session_id query string so the Stripe checkout confirmation works.
 * Uses redirect (temporary/307) not permanentRedirect so browsers don't cache it.
 */
export default async function FoundingObrigadoPage({ searchParams }: Props) {
  const params = await searchParams;
  const sessionId = params.session_id;
  const target = sessionId
    ? `/fundadores/obrigado?session_id=${encodeURIComponent(sessionId)}`
    : '/fundadores/obrigado';
  redirect(target);
}
