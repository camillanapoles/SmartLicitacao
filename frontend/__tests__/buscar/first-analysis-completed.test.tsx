/**
 * CONV-INST-005: first-analysis Mixpanel lifecycle events via useSearchSSEHandler (AC4)
 *
 * Tests:
 * 1. When isAutoAnalysis=true + search_complete with results → trackEvent('first_analysis_completed')
 * 2. When isAutoAnalysis=true + search_complete without results → trackEvent('first_analysis_empty')
 * 3. When isAutoAnalysis=true + error stage → trackEvent('first_analysis_failed')
 * 4. Double-fire protection: first_analysis_completed fires only once even if SSE fires twice
 * 5. When isAutoAnalysis=false → none of the first_analysis_* events fire
 */

import { renderHook, act } from '@testing-library/react';

// ── Mocks ──────────────────────────────────────────────────────────────────

const mockTrackEvent = jest.fn();
const mockRefreshQuota = jest.fn().mockResolvedValue(undefined);

jest.mock('../../hooks/useAnalytics', () => ({
  useAnalytics: () => ({ trackEvent: mockTrackEvent }),
}));

jest.mock('../../hooks/useQuota', () => ({
  useQuota: () => ({ refresh: mockRefreshQuota }),
}));

// ── Helpers ─────────────────────────────────────────────────────────────────

function makeParams(overrides: Record<string, unknown> = {}) {
  return {
    session: { access_token: 'test-token' },
    searchId: 'search-abc',
    searchMode: 'setor' as const,
    ufsSelecionadasSize: 2,
    result: null,
    setResult: jest.fn(),
    setRawCount: jest.fn(),
    setError: jest.fn(),
    setLoading: jest.fn(),
    setSearchId: jest.fn(),
    setAsyncSearchActive: jest.fn(),
    asyncSearchActiveRef: { current: true },
    asyncSearchIdRef: { current: 'search-abc' },
    sseTerminalReceivedRef: { current: false },
    llmTimeoutRef: { current: null },
    setRetryCountdown: jest.fn(),
    setRetryMessage: jest.fn(),
    setRetryExhausted: jest.fn(),
    retryTimerRef: { current: null },
    handleExcelFailureRef: { current: null },
    excelFailCountRef: { current: 0 },
    excelToastFiredRef: { current: false },
    setLiveFetchInProgress: jest.fn(),
    liveFetchSearchIdRef: { current: null },
    ...overrides,
  };
}

function makeSearchCompleteEvent(hasResults: boolean) {
  return {
    stage: 'search_complete' as const,
    progress: 100,
    message: 'done',
    detail: {
      has_results: hasResults,
      search_id: 'search-abc',
      total_results: hasResults ? 1 : 0,
    },
  };
}

function makeErrorEvent() {
  return {
    stage: 'error' as const,
    progress: 0,
    message: 'error',
    detail: {
      error: 'pipeline_error',
      error_code: 'PIPELINE_TIMEOUT',
    },
  };
}

// ── Tests ────────────────────────────────────────────────────────────────────

describe('CONV-INST-005: first_analysis_completed event (AC4)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = jest.fn().mockImplementation((url: string) => {
      if (url.includes('buscar-results')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            licitacoes: [{ pncp_id: 'bid-1', viability_score: 0.8 }],
            total_filtrado: 1,
            total_raw: 5,
          }),
        });
      }
      return Promise.resolve({ ok: false });
    });
  });

  it('fires first_analysis_completed when isAutoAnalysis=true + search_complete with results', async () => {
    const { useSearchSSEHandler } = require('../../app/buscar/hooks/useSearchSSEHandler');
    const { result } = renderHook(() =>
      useSearchSSEHandler({ ...makeParams(), isAutoAnalysis: true })
    );

    await act(async () => {
      await result.current.handleSseEvent(makeSearchCompleteEvent(true));
    });

    expect(mockTrackEvent).toHaveBeenCalledWith(
      'first_analysis_completed',
      expect.objectContaining({
        search_id: 'search-abc',
        results_count: expect.any(Number),
        time_total_ms: expect.any(Number),
        viability_high_count: expect.any(Number),
      })
    );
  });

  it('fires first_analysis_empty when isAutoAnalysis=true + search_complete without results', async () => {
    const { useSearchSSEHandler } = require('../../app/buscar/hooks/useSearchSSEHandler');
    const { result } = renderHook(() =>
      useSearchSSEHandler({ ...makeParams(), isAutoAnalysis: true })
    );

    await act(async () => {
      await result.current.handleSseEvent(makeSearchCompleteEvent(false));
    });

    expect(mockTrackEvent).toHaveBeenCalledWith(
      'first_analysis_empty',
      expect.objectContaining({
        search_id: expect.anything(),
        time_total_ms: expect.any(Number),
      })
    );
  });

  it('fires first_analysis_failed when isAutoAnalysis=true + error event', async () => {
    const { useSearchSSEHandler } = require('../../app/buscar/hooks/useSearchSSEHandler');
    const { result } = renderHook(() =>
      useSearchSSEHandler({ ...makeParams(), isAutoAnalysis: true })
    );

    await act(async () => {
      await result.current.handleSseEvent(makeErrorEvent());
    });

    expect(mockTrackEvent).toHaveBeenCalledWith(
      'first_analysis_failed',
      expect.objectContaining({
        search_id: 'search-abc',
        error_code: 'PIPELINE_TIMEOUT',
        time_total_ms: expect.any(Number),
      })
    );
  });

  it('does NOT double-fire first_analysis_completed on repeated search_complete events', async () => {
    const { useSearchSSEHandler } = require('../../app/buscar/hooks/useSearchSSEHandler');
    const { result } = renderHook(() =>
      useSearchSSEHandler({ ...makeParams(), isAutoAnalysis: true })
    );

    await act(async () => {
      await result.current.handleSseEvent(makeSearchCompleteEvent(true));
      await result.current.handleSseEvent(makeSearchCompleteEvent(true));
    });

    const completedCalls = mockTrackEvent.mock.calls.filter(
      ([eventName]) => eventName === 'first_analysis_completed'
    );
    expect(completedCalls).toHaveLength(1);
  });

  it('does NOT fire first_analysis_* events when isAutoAnalysis=false', async () => {
    const { useSearchSSEHandler } = require('../../app/buscar/hooks/useSearchSSEHandler');
    const { result } = renderHook(() =>
      useSearchSSEHandler({ ...makeParams(), isAutoAnalysis: false })
    );

    await act(async () => {
      await result.current.handleSseEvent(makeSearchCompleteEvent(true));
    });

    const firstAnalysisCalls = mockTrackEvent.mock.calls.filter(
      ([eventName]) => eventName.startsWith('first_analysis_')
    );
    expect(firstAnalysisCalls).toHaveLength(0);
  });
});
