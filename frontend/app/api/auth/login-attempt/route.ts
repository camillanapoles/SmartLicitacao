/**
 * MFA-EXT-001 AC5/AC6: Proxy for POST /v1/auth/login-attempt.
 *
 * Frontend AuthProvider calls this after every Supabase signInWithPassword
 * to report success/failure to the backend. The backend tracks consecutive
 * failures and triggers MFA enforcement when the threshold is crossed.
 *
 * Trust model: unauthenticated by design (failures occur before a
 * session). Rate-limited server-side (5/5min per IP). Always returns
 * 200/422 — caller treats it as fire-and-forget.
 */
import { NextRequest, NextResponse } from "next/server";
import { sanitizeProxyError, sanitizeNetworkError } from "../../../../lib/proxy-error-handler";

export async function POST(request: NextRequest) {
  const backendUrl = process.env.BACKEND_URL;
  if (!backendUrl) {
    console.error("[auth/login-attempt] BACKEND_URL is not configured");
    return NextResponse.json({ ok: false }, { status: 503 });
  }

  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json({ ok: false, error: "Invalid JSON" }, { status: 400 });
  }

  const correlationId =
    request.headers.get("X-Correlation-ID") ?? crypto.randomUUID();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Correlation-ID": correlationId,
  };

  // Forward client IP for backend rate limiting (Next handles X-Forwarded-For).
  const xff = request.headers.get("x-forwarded-for");
  if (xff) headers["X-Forwarded-For"] = xff;

  try {
    const res = await fetch(`${backendUrl}/v1/auth/login-attempt`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });
    const text = await res.text();
    if (!res.ok) {
      const sanitized = sanitizeProxyError(
        res.status,
        text,
        res.headers.get("content-type")
      );
      if (sanitized) return sanitized;
      return NextResponse.json({ ok: false }, { status: res.status });
    }
    try {
      const data = JSON.parse(text);
      return NextResponse.json(data);
    } catch {
      return NextResponse.json({ ok: true });
    }
  } catch (error) {
    console.error(
      "[auth/login-attempt] Network error:",
      error instanceof Error ? error.message : error
    );
    return sanitizeNetworkError(error);
  }
}
