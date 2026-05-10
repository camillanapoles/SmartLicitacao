/**
 * @jest-environment node
 *
 * Tests for POST /api/revalidate — on-demand ISR cache revalidation handler.
 */
import { NextRequest } from 'next/server';

// Mock next/cache before importing the route so the module sees the mock.
const mockRevalidatePath = jest.fn();
jest.mock('next/cache', () => ({
  revalidatePath: (...args: unknown[]) => mockRevalidatePath(...args),
}));

// Lazy import so the mock above is installed first.
// eslint-disable-next-line @typescript-eslint/consistent-type-imports
let POST: (req: NextRequest) => Promise<Response>;

beforeAll(async () => {
  const mod = await import('@/app/api/revalidate/route');
  POST = mod.POST;
});

const VALID_SECRET = 'test-secret-abc123';

function makeRequest(
  body: unknown,
  secret: string | null = VALID_SECRET,
): NextRequest {
  const headers: Record<string, string> = {
    'content-type': 'application/json',
  };
  if (secret !== null) {
    headers['x-revalidate-secret'] = secret;
  }
  return new NextRequest('http://localhost/api/revalidate', {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  });
}

describe('POST /api/revalidate', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    process.env.REVALIDATE_SECRET = VALID_SECRET;
  });

  afterEach(() => {
    delete process.env.REVALIDATE_SECRET;
  });

  describe('authentication', () => {
    it('returns 401 when REVALIDATE_SECRET env var is not set', async () => {
      delete process.env.REVALIDATE_SECRET;
      const req = makeRequest({ paths: ['/test'] });
      const res = await POST(req);
      expect(res.status).toBe(401);
      const data = await res.json();
      expect(data).toMatchObject({ error: 'Unauthorized' });
    });

    it('returns 401 when x-revalidate-secret header is missing', async () => {
      const req = makeRequest({ paths: ['/test'] }, null);
      const res = await POST(req);
      expect(res.status).toBe(401);
    });

    it('returns 401 when x-revalidate-secret header is wrong', async () => {
      const req = makeRequest({ paths: ['/test'] }, 'wrong-secret');
      const res = await POST(req);
      expect(res.status).toBe(401);
    });
  });

  describe('validation', () => {
    it('returns 400 when paths array is missing', async () => {
      const req = makeRequest({});
      const res = await POST(req);
      expect(res.status).toBe(400);
      const data = await res.json();
      expect(data).toMatchObject({ error: 'paths required' });
    });

    it('returns 400 when paths is an empty array', async () => {
      const req = makeRequest({ paths: [] });
      const res = await POST(req);
      expect(res.status).toBe(400);
    });

    it('returns 400 when body is not valid JSON', async () => {
      const req = new NextRequest('http://localhost/api/revalidate', {
        method: 'POST',
        headers: {
          'content-type': 'application/json',
          'x-revalidate-secret': VALID_SECRET,
        },
        body: 'not json {{',
      });
      const res = await POST(req);
      expect(res.status).toBe(400);
    });
  });

  describe('happy path', () => {
    it('returns 200 with revalidated count and calls revalidatePath for each path', async () => {
      const paths = ['/licitacoes/saude', '/observatorio/raio-x-maio-2026'];
      const req = makeRequest({ paths });
      const res = await POST(req);

      expect(res.status).toBe(200);
      const data = await res.json();
      expect(data).toEqual({ revalidated: 2, paths });

      expect(mockRevalidatePath).toHaveBeenCalledTimes(2);
      expect(mockRevalidatePath).toHaveBeenCalledWith('/licitacoes/saude');
      expect(mockRevalidatePath).toHaveBeenCalledWith('/observatorio/raio-x-maio-2026');
    });

    it('returns revalidated=1 for a single path', async () => {
      const req = makeRequest({ paths: ['/test-path'] });
      const res = await POST(req);
      expect(res.status).toBe(200);
      const data = await res.json();
      expect(data.revalidated).toBe(1);
      expect(mockRevalidatePath).toHaveBeenCalledWith('/test-path');
    });
  });
});
