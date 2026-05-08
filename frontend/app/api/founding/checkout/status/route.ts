import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL =
  process.env.BACKEND_URL ??
  process.env.NEXT_PUBLIC_BACKEND_URL;

export async function GET(request: NextRequest) {
  if (!BACKEND_URL) {
    return NextResponse.json({ error: 'Backend unavailable' }, { status: 503 });
  }

  const sessionId = request.nextUrl.searchParams.get('session_id');
  if (!sessionId) {
    return NextResponse.json({ error: 'session_id required' }, { status: 400 });
  }

  try {
    const res = await fetch(
      `${BACKEND_URL}/v1/founding/checkout/status?session_id=${encodeURIComponent(sessionId)}`,
      { next: { revalidate: 0 } }
    );
    if (!res.ok) {
      return NextResponse.json({ status: 'pending' }, { status: 200 });
    }
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ status: 'pending' }, { status: 200 });
  }
}

export const runtime = 'nodejs';
