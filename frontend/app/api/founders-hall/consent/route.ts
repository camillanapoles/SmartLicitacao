/**
 * Issue #1008: proxy for POST /api/founders/hall/consent.
 *
 * Authenticated. Toggles `profiles.founder_public_listing_consent`.
 */
import { createProxyRoute } from "../../../../lib/create-proxy-route";

export const { POST } = createProxyRoute({
  backendPath: "/api/founders/hall/consent",
  methods: ["POST"],
  requireAuth: true,
  errorMessage: "Erro ao atualizar preferência de listagem pública",
});
