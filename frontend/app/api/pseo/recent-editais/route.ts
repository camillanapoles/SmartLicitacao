/**
 * API proxy: GET /api/pseo/recent-editais → backend GET /v1/pseo/recent-editais
 * Issue #1007: pSEO DataBlock — 5 últimos editais por setor+UF.
 * Public endpoint (no auth). Cache: 6h CDN + SWR.
 */
import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL;

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const params = new URLSearchParams();

  const setor = searchParams.get("setor");
  if (!setor) {
    return NextResponse.json({ error: "setor is required" }, { status: 400 });
  }
  params.set("setor", setor);

  const uf = searchParams.get("uf");
  if (uf) params.set("uf", uf);

  const municipio = searchParams.get("municipio");
  if (municipio) params.set("municipio", municipio);

  const limit = searchParams.get("limit");
  if (limit) params.set("limit", limit);

  try {
    const resp = await fetch(
      `${BACKEND_URL}/v1/pseo/recent-editais?${params.toString()}`,
      {
        headers: { "Content-Type": "application/json" },
        next: { revalidate: 21600 }, // 6h ISR cache alignment
      }
    );

    if (!resp.ok) {
      return NextResponse.json(
        { message: await resp.text() },
        { status: resp.status }
      );
    }

    const data = await resp.json();
    return NextResponse.json(data, {
      headers: {
        "Cache-Control": "public, s-maxage=21600, stale-while-revalidate=43200",
      },
    });
  } catch {
    return NextResponse.json({ message: "Erro de conexão" }, { status: 502 });
  }
}
