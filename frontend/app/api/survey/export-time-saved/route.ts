/**
 * BIZ-METRIC-001 (AC3): Survey API proxy.
 *
 * POST /api/survey/export-time-saved → POST BACKEND_URL/v1/survey/export-time-saved
 *
 * Auth required. The user's Supabase session is forwarded as a Bearer
 * token via createProxyRoute's requireAuth=true plumbing.
 */

import { createProxyRoute } from "../../../../lib/create-proxy-route";

export const { POST } = createProxyRoute({
  backendPath: "/v1/survey/export-time-saved",
  methods: ["POST"],
  requireAuth: true,
  errorMessage: "Erro ao enviar resposta da pesquisa",
});
