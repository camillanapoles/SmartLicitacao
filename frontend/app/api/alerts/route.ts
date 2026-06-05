/**
 * STORY-301 / ENTITY-003: API proxy for alerts collection operations.
 * GET  /api/alerts   -> GET    BACKEND_URL/v1/alerts
 * POST /api/alerts   -> POST   BACKEND_URL/v1/alerts
 */
import { createProxyRoute } from "../../../lib/create-proxy-route";
export const { GET, POST } = createProxyRoute({
  backendPath: "/v1/alerts",
  methods: ["GET", "POST"],
  requireAuth: true,
  errorMessage: "Erro ao processar alertas",
});
