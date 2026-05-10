/**
 * #1011 UPGRADE-PATH-013: Pro mensal -> Lifetime founder upgrade proxy.
 * POST kicks off the cancel + checkout flow; GET preview returns pro-rata math.
 */
import { createProxyRoute } from "../../../../lib/create-proxy-route";

export const { POST } = createProxyRoute({
  backendPath: "/v1/api/subscriptions/upgrade-to-lifetime",
  methods: ["POST"],
  requireAuth: true,
  allowRefresh: true,
  errorMessage: "Erro temporário ao iniciar upgrade",
});
