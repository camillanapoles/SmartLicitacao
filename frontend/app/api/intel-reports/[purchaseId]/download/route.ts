/**
 * Intel Report PDF download proxy — GET /v1/intel-reports/{purchaseId}/download
 * Streams the PDF back to the browser as an attachment.
 */
import { NextRequest, NextResponse } from "next/server";
import { getRefreshedToken } from "../../../../../lib/serverAuth";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ purchaseId: string }> },
) {
  const backendUrl = process.env.BACKEND_URL;
  if (!backendUrl) {
    console.error("[intel-reports-download] BACKEND_URL not configured");
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
      `${backendUrl}/v1/intel-reports/${purchaseId}/download`,
      { method: "GET", headers },
    );

    if (!res.ok) {
      let detail = "Erro ao baixar relatório";
      try {
        const err = await res.json();
        detail = err.detail || err.message || detail;
      } catch {
        // ignore parse error
      }
      return NextResponse.json({ detail }, { status: res.status });
    }

    const pdfBuffer = await res.arrayBuffer();

    return new NextResponse(pdfBuffer, {
      status: 200,
      headers: {
        "Content-Type": "application/pdf",
        "Content-Disposition": `attachment; filename="intel-report-${purchaseId.slice(0, 8)}.pdf"`,
      },
    });
  } catch (error) {
    console.error(
      "[intel-reports-download] Network error:",
      error instanceof Error ? error.message : error,
    );
    return NextResponse.json(
      { detail: "Erro de rede ao baixar relatório" },
      { status: 502 },
    );
  }
}
