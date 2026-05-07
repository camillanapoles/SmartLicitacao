/**
 * Intel Report checkout proxy — POST /v1/intel-reports/checkout
 * Returns { checkout_url, session_id } from backend.
 * Frontend redirects user to checkout_url (Stripe Checkout).
 */
import { createProxyRoute } from "../../../../lib/create-proxy-route";

export const { POST } = createProxyRoute({
  backendPath: "/v1/intel-reports/checkout",
  methods: ["POST"],
  requireAuth: true,
  errorMessage: "Não foi possível iniciar o checkout do Intel Report.",
});
