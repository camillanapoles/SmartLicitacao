/**
 * POST /api/revalidate — on-demand ISR cache revalidation (Next.js 16 Route Handler).
 *
 * Accepts a JSON body `{ paths: string[] }` and calls `revalidatePath` for each
 * path. Protected by a shared secret (`REVALIDATE_SECRET` env var).
 *
 * Called by the backend `revalidate_client.py` after a successful ingestion run,
 * and by the admin endpoint `POST /v1/admin/revalidate-seo`.
 *
 * Fixes: stale ISR cache (revalidate=3600/86400) after backend ingestion populates
 * missing data — reduces stale window from up to 24h to <60s.
 */
import { NextRequest, NextResponse } from 'next/server';
import { revalidatePath } from 'next/cache';

export async function POST(req: NextRequest) {
  const secret = req.headers.get('x-revalidate-secret');
  if (!process.env.REVALIDATE_SECRET || secret !== process.env.REVALIDATE_SECRET) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  const paths: string[] =
    body !== null &&
    typeof body === 'object' &&
    'paths' in (body as object) &&
    Array.isArray((body as { paths: unknown }).paths)
      ? (body as { paths: string[] }).paths
      : [];

  if (paths.length === 0) {
    return NextResponse.json({ error: 'paths required' }, { status: 400 });
  }

  for (const path of paths) {
    revalidatePath(path);
  }

  return NextResponse.json({ revalidated: paths.length, paths });
}
