/**
 * #1011: Preview pro-rata math for the Pro -> Lifetime upgrade modal.
 */
import { createProxyRoute } from "../../../../../lib/create-proxy-route";

export const { GET } = createProxyRoute({
  backendPath: "/v1/api/subscriptions/upgrade-to-lifetime/preview",
  methods: ["GET"],
  requireAuth: true,
  allowRefresh: true,
  errorMessage: "Erro temporário ao carregar preview",
});
