/**
 * FOUND-SCALE-002: Tests for safeFetch + fetchWithBudget wrappers.
 */
import { safeFetch, fetchWithBudget } from '../../lib/safe-fetch';
import * as Sentry from '@sentry/nextjs';

jest.mock('@sentry/nextjs', () => ({
  captureException: jest.fn(),
  captureMessage: jest.fn(),
  addBreadcrumb: jest.fn(),
}));

const SentryMock = Sentry as unknown as {
  captureException: jest.Mock;
  captureMessage: jest.Mock;
  addBreadcrumb: jest.Mock;
};

// jsdom does not provide a global `Response` constructor. Build minimal
// mock matching Response shape we use (`ok`, `status`, `json()`).
function mockResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as unknown as Response;
}

describe('safeFetch (FOUND-SCALE-002 AC4)', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    SentryMock.captureException.mockReset();
    SentryMock.captureMessage.mockReset();
    SentryMock.addBreadcrumb.mockReset();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('returns Response on 200 OK', async () => {
    global.fetch = jest.fn().mockResolvedValue(
      mockResponse({ ok: true }, 200),
    ) as jest.Mock;
    const resp = await safeFetch('https://api.test/x');
    expect(resp).not.toBeNull();
    expect(resp?.status).toBe(200);
    expect(SentryMock.addBreadcrumb).toHaveBeenCalledWith(
      expect.objectContaining({
        category: 'fetch',
        level: 'info',
      }),
    );
  });

  it('returns null on HTTP error and emits Sentry message', async () => {
    global.fetch = jest.fn().mockResolvedValue(
      mockResponse({ error: true }, 502),
    ) as jest.Mock;
    const resp = await safeFetch('https://api.test/x', { label: 'test-502' });
    expect(resp).toBeNull();
    expect(SentryMock.captureMessage).toHaveBeenCalledWith(
      expect.stringContaining('HTTP 502'),
      expect.objectContaining({
        tags: expect.objectContaining({ fetch_outcome: 'http_error' }),
      }),
    );
  });

  it('returns null on network error and emits Sentry exception', async () => {
    const networkErr = new Error('ECONNREFUSED');
    global.fetch = jest.fn().mockRejectedValue(networkErr) as jest.Mock;
    const resp = await safeFetch('https://api.test/x', { label: 'test-net' });
    expect(resp).toBeNull();
    expect(SentryMock.captureException).toHaveBeenCalledWith(
      networkErr,
      expect.objectContaining({
        tags: expect.objectContaining({ fetch_outcome: 'network_error' }),
      }),
    );
  });

  it('returns null on TimeoutError and tags as timeout', async () => {
    const timeoutErr = new Error('signal timed out');
    timeoutErr.name = 'TimeoutError';
    global.fetch = jest.fn().mockRejectedValue(timeoutErr) as jest.Mock;
    const resp = await safeFetch('https://api.test/x', { label: 'test-timeout' });
    expect(resp).toBeNull();
    expect(SentryMock.captureException).toHaveBeenCalledWith(
      timeoutErr,
      expect.objectContaining({
        tags: expect.objectContaining({ fetch_outcome: 'timeout' }),
      }),
    );
  });
});

describe('fetchWithBudget (FOUND-SCALE-002 AC7)', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    SentryMock.captureException.mockReset();
    SentryMock.captureMessage.mockReset();
    SentryMock.addBreadcrumb.mockReset();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('returns parsed JSON on success (no retry)', async () => {
    global.fetch = jest.fn().mockResolvedValue(
      mockResponse({ value: 42 }, 200),
    ) as jest.Mock;
    const result = await fetchWithBudget<{ value: number }>('https://api.test/x', {
      label: 'test',
      retries: 0,
    });
    expect(result).toEqual({ value: 42 });
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  it('retries once and succeeds on 2nd attempt', async () => {
    global.fetch = jest
      .fn()
      .mockResolvedValueOnce(mockResponse({}, 502))
      .mockResolvedValueOnce(mockResponse({ value: 1 }, 200)) as jest.Mock;
    const result = await fetchWithBudget<{ value: number }>('https://api.test/x', {
      label: 'test-retry',
      retries: 1,
    });
    expect(result).toEqual({ value: 1 });
    expect(global.fetch).toHaveBeenCalledTimes(2);
  });

  it('returns fallback after all attempts fail', async () => {
    global.fetch = jest
      .fn()
      .mockResolvedValue(mockResponse({}, 503)) as jest.Mock;
    const fallback = { value: 0, fallback: true };
    const result = await fetchWithBudget('https://api.test/x', {
      label: 'test-exhausted',
      retries: 1,
      fallback,
    });
    expect(result).toEqual(fallback);
    expect(global.fetch).toHaveBeenCalledTimes(2);
    expect(SentryMock.captureMessage).toHaveBeenCalledWith(
      expect.stringContaining('fetchWithBudget_exhausted_test-exhausted'),
      expect.objectContaining({
        tags: expect.objectContaining({ fetch_outcome: 'budget_exhausted' }),
      }),
    );
  });

  it('applies extract transformer on parsed data', async () => {
    global.fetch = jest.fn().mockResolvedValue(
      mockResponse({ items: [{ id: 1 }, { id: 2 }] }, 200),
    ) as jest.Mock;
    const result = await fetchWithBudget<number[]>('https://api.test/x', {
      label: 'test-extract',
      retries: 0,
      extract: (data) => (data as { items: { id: number }[] }).items.map((i) => i.id),
    });
    expect(result).toEqual([1, 2]);
  });

  it('uses next.revalidate by default 3600s', async () => {
    const fetchMock = jest.fn().mockResolvedValue(mockResponse({ ok: true }, 200));
    global.fetch = fetchMock as jest.Mock;
    await fetchWithBudget('https://api.test/x', { label: 'test-isr', retries: 0 });
    expect(fetchMock).toHaveBeenCalledWith(
      'https://api.test/x',
      expect.objectContaining({
        next: expect.objectContaining({ revalidate: 3600 }),
      }),
    );
  });
});
