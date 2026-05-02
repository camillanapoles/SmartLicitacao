/**
 * Returns the backend URL for server-side fetches (SSG, ISR, route handlers).
 *
 * Chain de fallback documentado em SEO-PROG-008:
 *   1. BACKEND_URL — server-only, set via Railway bidiq-frontend service var
 *   2. NEXT_PUBLIC_BACKEND_URL — client-side default; fallback se BACKEND_URL ausente
 *   3. http://localhost:8000 — dev local fallback
 *
 * Memory references:
 *   - feedback_build_hammers_backend_cascade — sitemap-4.xml ficou vazio quando
 *     Dockerfile não tinha ARG BACKEND_URL.
 *   - reference_frontend_dockerfile_backend_url_gap — Dockerfile fix STORY-SEO-020
 *     adicionou ARG BACKEND_URL; helper reforça chain client+server.
 *   - reference_railway_backend_url_already_set — bidiq-frontend service tem
 *     BACKEND_URL=https://api.smartlic.tech configured.
 *
 * Build-time assertion em frontend/Dockerfile:138-153 falha o build em produção
 * se BACKEND_URL ou NEXT_PUBLIC_BACKEND_URL ausentes (defense-in-depth).
 */
export function getBackendUrl(): string {
  return (
    process.env.BACKEND_URL ||
    process.env.NEXT_PUBLIC_BACKEND_URL ||
    'http://localhost:8000'
  );
}
