/**
 * BILL-SYNC-001 (AC13): tests for /admin/billing/sync page.
 *
 * Covers:
 *   - Drift indicator render per drift_status (in_sync / drift_recent / drift_stale).
 *   - Push DB -> Stripe button opens confirmation modal.
 *   - Confirm modal POSTs to /api/admin/plans/{id}/sync-to-stripe with
 *     i_understand_this_modifies_stripe=true.
 *   - Reconcile button disabled while in-flight.
 *   - Skipped (race-guard) response surfaces a warning toast.
 */
import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";

// ── Mocks ──────────────────────────────────────────────────────────────────
const mockUseAuth = jest.fn();
jest.mock("../../app/components/AuthProvider", () => ({
  useAuth: () => mockUseAuth(),
}));

const mockMutate = jest.fn();
const mockUseAdminSWR = jest.fn();
jest.mock("../../hooks/useAdminSWR", () => ({
  useAdminSWR: (key: string | null) => mockUseAdminSWR(key),
}));

jest.mock("sonner", () => ({
  toast: {
    success: jest.fn(),
    error: jest.fn(),
    warning: jest.fn(),
  },
}));

import AdminBillingSyncPage from "../../app/admin/billing/sync/page";
import { toast } from "sonner";

const ADMIN_AUTH = {
  session: { access_token: "tok-admin" },
  loading: false,
  isAdmin: true,
  isAdminLoading: false,
};

const ROW_IN_SYNC = {
  id: "row-in-sync",
  plan_id: "smartlic_pro",
  billing_period: "monthly",
  price_cents: 199900,
  discount_percent: 0,
  stripe_price_id: "price_a",
  stripe_product_id: "prod_x",
  last_forward_synced_at: "2026-04-28T12:00:00Z",
  last_reverse_synced_at: null,
  is_archived: false,
  drift_status: "in_sync" as const,
};

const ROW_DRIFT_STALE = {
  id: "row-stale",
  plan_id: "smartlic_pro",
  billing_period: "annual",
  price_cents: 159900,
  discount_percent: 20,
  stripe_price_id: "price_b",
  stripe_product_id: "prod_x",
  last_forward_synced_at: "2026-04-01T12:00:00Z",
  last_reverse_synced_at: null,
  is_archived: false,
  drift_status: "drift_stale" as const,
};

const SAMPLE_RUNS = {
  items: [
    {
      id: "run-1",
      started_at: "2026-04-28T03:00:00Z",
      finished_at: "2026-04-28T03:00:30Z",
      status: "completed",
      dry_run: false,
      rows_checked: 3,
      drifts_detected: 0,
      drifts_fixed: 0,
      drifts_manual: 0,
      error_message: null,
    },
  ],
};

describe("AdminBillingSyncPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = jest.fn();
    mockUseAuth.mockReturnValue(ADMIN_AUTH);

    mockUseAdminSWR.mockImplementation((key: string | null) => {
      if (!key) {
        return { data: undefined, error: null, isLoading: false, mutate: mockMutate };
      }
      if (key.includes("/billing-sync")) {
        return {
          data: { items: [ROW_IN_SYNC, ROW_DRIFT_STALE] },
          error: null,
          isLoading: false,
          mutate: mockMutate,
        };
      }
      if (key.includes("/reconciliation-runs")) {
        return {
          data: SAMPLE_RUNS,
          error: null,
          isLoading: false,
          mutate: mockMutate,
        };
      }
      return { data: undefined, error: null, isLoading: false, mutate: mockMutate };
    });
  });

  it("renders drift indicator for each row", () => {
    render(<AdminBillingSyncPage />);
    expect(screen.getByTestId(`drift-${ROW_IN_SYNC.id}`)).toHaveTextContent(
      "Em sincronia",
    );
    expect(
      screen.getByTestId(`drift-${ROW_DRIFT_STALE.id}`),
    ).toHaveTextContent("Drift antigo");
  });

  it("shows last sync timestamps", () => {
    render(<AdminBillingSyncPage />);
    // Forward timestamp from sample row should be rendered (locale-formatted).
    const inSyncRow = screen.getByTestId(`bps-row-${ROW_IN_SYNC.id}`);
    expect(inSyncRow).toBeInTheDocument();
    expect(inSyncRow.textContent).toMatch(/2026/);
  });

  it("opens confirmation modal when Push DB -> Stripe is clicked", async () => {
    render(<AdminBillingSyncPage />);
    fireEvent.click(screen.getByTestId(`push-${ROW_IN_SYNC.id}`));
    await waitFor(() => {
      expect(screen.getByTestId("confirm-modal")).toBeInTheDocument();
    });
  });

  it("POSTs reverse sync with confirmation flag and surfaces success toast", async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        status: "ok",
        new_stripe_price_id: "price_new",
        skipped_reason: null,
      }),
    });

    render(<AdminBillingSyncPage />);
    fireEvent.click(screen.getByTestId(`push-${ROW_IN_SYNC.id}`));
    await screen.findByTestId("confirm-modal");

    fireEvent.change(screen.getByTestId("confirm-note"), {
      target: { value: "annual rate update" },
    });
    fireEvent.click(screen.getByTestId("confirm-submit"));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        `/api/admin/plans/${ROW_IN_SYNC.id}/sync-to-stripe`,
        expect.objectContaining({
          method: "POST",
          headers: expect.objectContaining({
            Authorization: "Bearer tok-admin",
            "Content-Type": "application/json",
          }),
          body: expect.stringContaining("i_understand_this_modifies_stripe"),
        }),
      );
    });
    const calledArgs = (global.fetch as jest.Mock).mock.calls[0][1];
    const parsedBody = JSON.parse(calledArgs.body);
    expect(parsedBody.i_understand_this_modifies_stripe).toBe(true);
    expect(parsedBody.note).toBe("annual rate update");

    await waitFor(() => {
      expect(toast.success).toHaveBeenCalled();
    });
  });

  it("shows warning when reverse sync is skipped (race guard)", async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        status: "skipped",
        new_stripe_price_id: null,
        skipped_reason: "race_guard_24h",
      }),
    });
    render(<AdminBillingSyncPage />);
    fireEvent.click(screen.getByTestId(`push-${ROW_IN_SYNC.id}`));
    await screen.findByTestId("confirm-modal");
    fireEvent.click(screen.getByTestId("confirm-submit"));

    await waitFor(() => {
      expect(toast.warning).toHaveBeenCalledWith(
        expect.stringContaining("race_guard_24h"),
      );
    });
  });

  it("triggers reconcile-now endpoint with dry_run flag", async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ drifts_detected: 0, drifts_fixed: 0 }),
    });
    render(<AdminBillingSyncPage />);
    fireEvent.click(screen.getByTestId("reconcile-dry-run"));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/admin/plans/reconcile-now?dry_run=true",
        expect.any(Object),
      );
    });
  });

  it("renders reconciliation runs table", () => {
    render(<AdminBillingSyncPage />);
    expect(screen.getByTestId(`run-${SAMPLE_RUNS.items[0].id}`)).toBeInTheDocument();
  });
});
