/**
 * Intel Report status polling proxy — GET /v1/intel-reports/{purchaseId}
 * Returns { status, pdf_url, expires_at } for a purchase.
 */
import { NextRequest, NextResponse } from "next/server";
import { getRefreshedToken } from "../../../../lib/serverAuth";
import {
  sanitizeProxyError,
  sanitizeNetworkError,
} from "../../../../lib/proxy-error-handler";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ purchaseId: string }> },
) {
  const backendUrl = process.env.BACKEND_URL;
  if (!backendUrl) {
    console.error("[intel-reports-status] BACKEND_URL not configured");
    return NextResponse.json({ message: "Servidor não configurado" }, { status: 503 });
  }

  const token = await getRefreshedToken();
  const authHeader = token
    ? `Bearer ${token}`
    : request.headers.get("authorization");

  if (!authHeader) {
    return NextResponse.json({ message: "Autenticação necessária" }, { status: 401 });
  }

  const { purchaseId } = await params;

  const correlationId = request.headers.get("X-Correlation-ID");
  const headers: Record<string, string> = { Authorization: authHeader };
  if (correlationId) headers["X-Correlation-ID"] = correlationId;

  try {
    const res = await fetch(
      `${backendUrl}/v1/intel-reports/${purchaseId}`,
      { method: "GET", headers },
    );

    const body = await res.text();
    const sanitized = sanitizeProxyError(
      res.status,
      body,
      res.headers.get("content-type"),
    );
    if (sanitized) return sanitized;

    try {
      return NextResponse.json(JSON.parse(body), { status: res.status });
    } catch {
      return NextResponse.json(
        { message: "Erro ao carregar status do relatório" },
        { status: res.status },
      );
    }
  } catch (error) {
    console.error(
      "[intel-reports-status] Network error:",
      error instanceof Error ? error.message : error,
    );
    return sanitizeNetworkError(error);
  }
}
