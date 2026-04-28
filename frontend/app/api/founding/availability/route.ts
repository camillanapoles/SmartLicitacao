/**
 * BIZ-FOUND-002: founding availability proxy.
 *
 * Public, no-auth GET endpoint that fronts the backend's
 * `/v1/founding/availability` RPC-backed snapshot. Used by the landing
 * page to render the seat counter (X/50) and the deadline countdown.
 *
 * Cache behaviour: short revalidate window (30s) — the seat counter
 * needs to be fresh enough that abandoned/completed bursts surface
 * quickly, but high frequency would hammer the backend RPC.
 */
import { createProxyRoute } from "../../../../lib/create-proxy-route";

export const { GET } = createProxyRoute({
  backendPath: "/v1/founding/availability",
  methods: ["GET"],
  requireAuth: false,
  fetchCache: { revalidate: 30 },
  errorMessage: "Não foi possível verificar disponibilidade founding.",
  logPrefix: "founding-availability",
});

export const runtime = "nodejs";
