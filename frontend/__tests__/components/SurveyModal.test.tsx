/**
 * BIZ-METRIC-001 (AC14): tests for ExportTimeSavedModal + frequency hook.
 *
 * Covers:
 *   * Modal renders with slider in [0.5, 20] range and labels.
 *   * Submit calls onSubmit with parsed values.
 *   * Dismiss / Esc closes.
 *   * Frequency throttling: every 3rd export opens modal.
 *   * Lifetime cap: after 5 submissions modal stops opening.
 *   * Eligibility gate: <3 searches → never opens.
 *   * Hours out of range cannot be submitted (slider max=20).
 */

import { fireEvent, render, screen, act } from "@testing-library/react";
import React from "react";
import { renderHook } from "@testing-library/react";

import ExportTimeSavedModal, {
  useExportTimeSavedSurvey,
} from "../../components/survey/ExportTimeSavedModal";

class MemoryStorage implements Storage {
  private map = new Map<string, string>();
  get length(): number { return this.map.size; }
  clear(): void { this.map.clear(); }
  getItem(k: string): string | null { return this.map.has(k) ? this.map.get(k)! : null; }
  key(n: number): string | null { return Array.from(this.map.keys())[n] ?? null; }
  removeItem(k: string): void { this.map.delete(k); }
  setItem(k: string, v: string): void { this.map.set(k, v); }
}

describe("ExportTimeSavedModal (component)", () => {
  it("renders headline + slider with the documented bounds", () => {
    render(
      <ExportTimeSavedModal
        open={true}
        onClose={jest.fn()}
        onSubmit={jest.fn()}
      />,
    );
    expect(screen.getByText(/Sem o SmartLic/i)).toBeInTheDocument();
    const slider = screen.getByTestId("hours-slider") as HTMLInputElement;
    expect(slider.min).toBe("0.5");
    expect(slider.max).toBe("20");
  });

  it("calls onSubmit with parsed hours + trimmed free_text", async () => {
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    render(
      <ExportTimeSavedModal
        open={true}
        onClose={jest.fn()}
        onSubmit={onSubmit}
        initialHours={3}
      />,
    );
    fireEvent.change(screen.getByTestId("hours-slider"), { target: { value: "4.5" } });
    fireEvent.change(screen.getByTestId("freetext-input"), {
      target: { value: "  manual on PNCP  " },
    });
    fireEvent.click(screen.getByTestId("submit-button"));
    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit).toHaveBeenCalledWith({
      estimatedManualHours: 4.5,
      freeText: "manual on PNCP",
    });
  });

  it("dismiss button calls onClose without submitting", () => {
    const onSubmit = jest.fn();
    const onClose = jest.fn();
    render(
      <ExportTimeSavedModal open={true} onClose={onClose} onSubmit={onSubmit} />,
    );
    fireEvent.click(screen.getByTestId("dismiss-button"));
    expect(onClose).toHaveBeenCalled();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("Esc key triggers onClose", () => {
    const onClose = jest.fn();
    render(
      <ExportTimeSavedModal open={true} onClose={onClose} onSubmit={jest.fn()} />,
    );
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalled();
  });

  it("returns null when not open", () => {
    const { container } = render(
      <ExportTimeSavedModal open={false} onClose={jest.fn()} onSubmit={jest.fn()} />,
    );
    expect(container.firstChild).toBeNull();
  });
});

describe("useExportTimeSavedSurvey (hook)", () => {
  it("respects min-search eligibility (totalSearches < 3)", () => {
    const local = new MemoryStorage();
    const session = new MemoryStorage();
    const { result } = renderHook(() =>
      useExportTimeSavedSurvey({
        totalSearches: 1,
        localStorageImpl: local,
        sessionStorageImpl: session,
      }),
    );
    act(() => {
      result.current.maybeOpen({ exportType: "excel" });
      result.current.maybeOpen({ exportType: "excel" });
      result.current.maybeOpen({ exportType: "excel" });
      result.current.maybeOpen({ exportType: "excel" });
    });
    expect(result.current.modalProps.open).toBe(false);
  });

  it("opens on every 3rd export", () => {
    const local = new MemoryStorage();
    const session = new MemoryStorage();
    const { result } = renderHook(() =>
      useExportTimeSavedSurvey({
        totalSearches: 10,
        localStorageImpl: local,
        sessionStorageImpl: session,
      }),
    );
    // 1st export → not open
    act(() => result.current.maybeOpen({ exportType: "excel" }));
    expect(result.current.modalProps.open).toBe(false);
    // 2nd export → still not open
    act(() => result.current.maybeOpen({ exportType: "excel" }));
    expect(result.current.modalProps.open).toBe(false);
    // 3rd export → opens
    act(() => result.current.maybeOpen({ exportType: "excel" }));
    expect(result.current.modalProps.open).toBe(true);
  });

  it("opens at most once per session", () => {
    const local = new MemoryStorage();
    const session = new MemoryStorage();
    const { result } = renderHook(() =>
      useExportTimeSavedSurvey({
        totalSearches: 10,
        localStorageImpl: local,
        sessionStorageImpl: session,
      }),
    );
    // Get to the 3rd export to trigger open
    act(() => result.current.maybeOpen({ exportType: "excel" }));
    act(() => result.current.maybeOpen({ exportType: "excel" }));
    act(() => result.current.maybeOpen({ exportType: "excel" }));
    expect(result.current.modalProps.open).toBe(true);
    // Close it
    act(() => result.current.modalProps.onClose());
    expect(result.current.modalProps.open).toBe(false);
    // Subsequent exports in the same "session" do not re-open
    act(() => result.current.maybeOpen({ exportType: "excel" }));
    act(() => result.current.maybeOpen({ exportType: "excel" }));
    act(() => result.current.maybeOpen({ exportType: "excel" }));
    expect(result.current.modalProps.open).toBe(false);
  });

  it("caps total submissions at 5 lifetime", () => {
    const local = new MemoryStorage();
    // Pre-seed lifetime count at the cap.
    local.setItem("smartlic.export_survey.count", "5");
    const session = new MemoryStorage();
    const { result } = renderHook(() =>
      useExportTimeSavedSurvey({
        totalSearches: 100,
        localStorageImpl: local,
        sessionStorageImpl: session,
      }),
    );
    act(() => result.current.maybeOpen({ exportType: "excel" }));
    act(() => result.current.maybeOpen({ exportType: "excel" }));
    act(() => result.current.maybeOpen({ exportType: "excel" }));
    expect(result.current.modalProps.open).toBe(false);
  });

  it("submits via fetch and increments lifetime counter", async () => {
    const local = new MemoryStorage();
    const session = new MemoryStorage();
    const fetchImpl = jest.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({ id: "ok", submitted_at: "2026-04-28T10:00:00Z" }),
    });
    const { result } = renderHook(() =>
      useExportTimeSavedSurvey({
        totalSearches: 10,
        localStorageImpl: local,
        sessionStorageImpl: session,
        fetchImpl: fetchImpl as unknown as typeof fetch,
      }),
    );
    // Reach 3rd export to open
    act(() => result.current.maybeOpen({ exportType: "excel", searchId: "s1", bidCount: 12 }));
    act(() => result.current.maybeOpen({ exportType: "excel", searchId: "s1", bidCount: 12 }));
    act(() => result.current.maybeOpen({ exportType: "excel", searchId: "s1", bidCount: 12 }));
    expect(result.current.modalProps.open).toBe(true);

    await act(async () => {
      await result.current.modalProps.onSubmit({ estimatedManualHours: 4, freeText: null });
    });

    expect(fetchImpl).toHaveBeenCalledTimes(1);
    const [url, init] = fetchImpl.mock.calls[0];
    expect(url).toBe("/api/survey/export-time-saved");
    expect((init as RequestInit).method).toBe("POST");
    const body = JSON.parse(((init as RequestInit).body as string) || "{}");
    expect(body).toMatchObject({
      export_type: "excel",
      estimated_manual_hours: 4,
      search_id: "s1",
      bid_count: 12,
      free_text: null,
    });
    expect(local.getItem("smartlic.export_survey.count")).toBe("1");
  });
});
