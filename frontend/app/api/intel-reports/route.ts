/**
 * Intel Report list proxy — GET /v1/intel-reports/
 * Returns array of user's Intel Report purchases.
 */
import { createProxyRoute } from "../../../lib/create-proxy-route";

export const { GET } = createProxyRoute({
  backendPath: "/v1/intel-reports/",
  methods: ["GET"],
  requireAuth: true,
  errorMessage: "Não foi possível carregar seus relatórios.",
});
