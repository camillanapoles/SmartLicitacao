/**
 * BIZ-METRIC-001 (AC11, AC14): tests for /admin/calibration page.
 *
 * Covers:
 *   * Loads aggregate on mount
 *   * Renders summary cards + histogram bars
 *   * Recalibrate (dry-run) shows old vs new
 *   * Recalibrate (apply) refreshes the aggregate
 *   * 403 error renders restricted-access banner
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";

import CalibrationDashboardPage from "../../app/admin/calibration/page";

const aggregatePayload = {
  range_days: 90,
  sample_size: 35,
  after_outlier_removal: 30,
  median_hours: 3.5,
  mean_hours: 3.8,
  iqr_q1: 2.0,
  iqr_q3: 5.0,
  iqr_lower_bound: -2.5,
  iqr_upper_bound: 9.5,
  median_per_bid: 0.4,
  median_bid_count: 10,
  histogram: [
    { range_label: "<0.5h", count: 0 },
    { range_label: "0.5-1.0h", count: 1 },
    { range_label: "1.0-2.0h", count: 5 },
    { range_label: "2.0-3.0h", count: 12 },
    { range_label: "3.0-5.0h", count: 8 },
    { range_label: "5.0-8.0h", count: 3 },
    { range_label: "8.0-12.0h", count: 1 },
    { range_label: "12.0-20.0h", count: 0 },
    { range_label: "20.0-50.0h", count: 0 },
    { range_label: ">=50.0h", count: 0 },
  ],
  current_constant: 2.0,
};

describe("CalibrationDashboardPage", () => {
  let originalFetch: typeof fetch;

  beforeEach(() => {
    originalFetch = global.fetch;
  });

  afterEach(() => {
    global.fetch = originalFetch;
    jest.restoreAllMocks();
  });

  function fakeFetchResponse(body: unknown, status = 200) {
    return {
      ok: status >= 200 && status < 300,
      status,
      json: async () => body,
      text: async () => JSON.stringify(body),
      headers: new Map(),
    } as unknown as Response;
  }

  function mockFetchSuccess() {
    global.fetch = jest.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const u = typeof url === "string" ? url : url.toString();
      if (u.startsWith("/api/admin/survey/export-time-saved")) {
        return fakeFetchResponse(aggregatePayload);
      }
      if (u === "/api/admin/calibration/recalibrate") {
        const body = JSON.parse((init?.body as string) || "{}");
        return fakeFetchResponse({
          range_days: body.range_days ?? 90,
          sample_size: 35,
          after_outlier_removal: 30,
          eligible: true,
          reason: null,
          old_value: 2.0,
          new_value: 3.5,
          diff_pct: 75.0,
          applied: !!body.apply,
          median_per_bid: 0.4,
          median_bid_count: 10,
        });
      }
      return fakeFetchResponse({});
    }) as unknown as typeof fetch;
  }

  it("loads aggregate and renders summary cards + histogram", async () => {
    mockFetchSuccess();
    render(<CalibrationDashboardPage />);
    await waitFor(() => screen.getByTestId("current-constant"));
    expect(screen.getByTestId("current-constant").textContent).toMatch(/2\.00/);
    expect(screen.getByTestId("median-hours").textContent).toMatch(/3\.50/);
    expect(screen.getByTestId("sample-size").textContent).toMatch(/30 \/ 35/);
    const histogram = screen.getByTestId("histogram");
    expect(histogram).toBeInTheDocument();
  });

  it("recalibrate dry-run shows result without applying", async () => {
    mockFetchSuccess();
    render(<CalibrationDashboardPage />);
    await waitFor(() => screen.getByTestId("current-constant"));

    fireEvent.click(screen.getByTestId("recalibrate-dryrun"));

    await waitFor(() => screen.getByTestId("recalibrate-result"));
    const result = screen.getByTestId("recalibrate-result");
    expect(result.textContent).toContain("3.50");
    expect(result.textContent).toContain("não"); // applied: não
  });

  it("recalibrate apply re-fetches aggregate", async () => {
    mockFetchSuccess();
    const fetchSpy = global.fetch as jest.Mock;
    render(<CalibrationDashboardPage />);
    await waitFor(() => screen.getByTestId("current-constant"));
    const initialCalls = fetchSpy.mock.calls.length;

    fireEvent.click(screen.getByTestId("recalibrate-apply"));
    await waitFor(() => screen.getByTestId("recalibrate-result"));
    // Recalibrate POST + aggregate refetch GET => at least 2 more fetches.
    expect(fetchSpy.mock.calls.length).toBeGreaterThanOrEqual(initialCalls + 2);
  });

  it("403 from aggregate endpoint surfaces restricted-access banner", async () => {
    global.fetch = jest.fn(async () => ({
      ok: false,
      status: 403,
      json: async () => ({}),
      text: async () => "",
    })) as unknown as typeof fetch;
    render(<CalibrationDashboardPage />);
    await waitFor(() => screen.getByTestId("error-banner"));
    expect(screen.getByTestId("error-banner").textContent).toMatch(/administradores/);
  });
});
