/**
 * CONV-018: User segmentation save proxy.
 *
 * POST /api/segment/save — forwards to POST /v1/segment/save
 */
import { createProxyRoute } from "../../../../lib/create-proxy-route";

export const { POST } = createProxyRoute({
  backendPath: "/v1/segment/save",
  methods: ["POST"],
  requireAuth: true,
  errorMessage: "Erro ao salvar segmentação",
});
