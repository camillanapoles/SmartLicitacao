/**
 * DATA-CNAE-001 (AC17): tests for /admin/cnae page.
 *
 * Covers: list rendering, edit/delete/restore PATCH/DELETE/POST flows,
 * audit drawer fetch, bulk-import preview, non-admin gate.
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

jest.mock("next/link", () => {
  const MockLink = ({ href, children }: { href: string; children: React.ReactNode }) => (
    <a href={href}>{children}</a>
  );
  MockLink.displayName = "MockLink";
  return MockLink;
});

jest.mock("sonner", () => ({
  toast: {
    success: jest.fn(),
    error: jest.fn(),
  },
}));

import AdminCnaeMappingPage from "../../app/admin/cnae/page";
import { toast } from "sonner";

const ADMIN_AUTH = {
  session: { access_token: "tok-admin" },
  loading: false,
  isAdmin: true,
  isAdminLoading: false,
};

const SAMPLE_LIST = {
  items: [
    {
      cnae_code: "4120",
      setor_id: "engenharia",
      confidence: 1.0,
      notes: "seed",
      is_active: true,
      updated_at: "2026-04-28T12:00:00Z",
    },
    {
      cnae_code: "4781",
      setor_id: "vestuario",
      confidence: 0.9,
      notes: null,
      is_active: false,
      updated_at: "2026-04-28T13:00:00Z",
    },
  ],
  total: 2,
  limit: 50,
  offset: 0,
};

describe("AdminCnaeMappingPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = jest.fn();
    // The page uses useAdminSWR twice (list + detail).  We default
    // the detail call to nothing — individual tests override.
    mockUseAdminSWR.mockImplementation((key: string | null) => {
      if (!key) return { data: undefined, error: null, isLoading: false, mutate: mockMutate };
      if (key.includes("/cnae-mapping?")) {
        return {
          data: SAMPLE_LIST,
          error: null,
          isLoading: false,
          mutate: mockMutate,
        };
      }
      return { data: undefined, error: null, isLoading: false, mutate: mockMutate };
    });
  });

  it("renders the list when user is admin", () => {
    mockUseAuth.mockReturnValue(ADMIN_AUTH);
    render(<AdminCnaeMappingPage />);
    expect(screen.getByTestId("admin-cnae-page")).toBeInTheDocument();
    expect(screen.getByTestId("cnae-row-4120")).toBeInTheDocument();
    expect(screen.getByTestId("cnae-row-4781")).toBeInTheDocument();
    expect(screen.getByTestId("cnae-total")).toHaveTextContent("2 mappings");
  });

  it("blocks non-admin", () => {
    mockUseAuth.mockReturnValue({
      session: { access_token: "tok" },
      loading: false,
      isAdmin: false,
      isAdminLoading: false,
    });
    render(<AdminCnaeMappingPage />);
    expect(screen.queryByTestId("admin-cnae-page")).not.toBeInTheDocument();
    expect(screen.getByText(/restrito a administradores/i)).toBeInTheDocument();
  });

  it("opens the create modal when clicking Novo mapping", () => {
    mockUseAuth.mockReturnValue(ADMIN_AUTH);
    render(<AdminCnaeMappingPage />);
    fireEvent.click(screen.getByTestId("cnae-new"));
    expect(screen.getByTestId("cnae-form-modal")).toBeInTheDocument();
  });

  it("posts a create when form is submitted", async () => {
    mockUseAuth.mockReturnValue(ADMIN_AUTH);
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ mapping: SAMPLE_LIST.items[0], audit_id: "a1" }),
    });
    render(<AdminCnaeMappingPage />);
    fireEvent.click(screen.getByTestId("cnae-new"));
    fireEvent.change(screen.getByTestId("cnae-form-code"), { target: { value: "9988" } });
    fireEvent.change(screen.getByTestId("cnae-form-setor"), {
      target: { value: "manutencao_predial" },
    });
    fireEvent.click(screen.getByTestId("cnae-form-save"));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/admin/cnae-mapping",
        expect.objectContaining({
          method: "POST",
          headers: expect.objectContaining({ Authorization: "Bearer tok-admin" }),
        })
      );
    });
    expect(toast.success).toHaveBeenCalled();
  });

  it("rejects invalid CNAE format on create", async () => {
    mockUseAuth.mockReturnValue(ADMIN_AUTH);
    render(<AdminCnaeMappingPage />);
    fireEvent.click(screen.getByTestId("cnae-new"));
    fireEvent.change(screen.getByTestId("cnae-form-code"), { target: { value: "abc" } });
    fireEvent.click(screen.getByTestId("cnae-form-save"));
    expect(global.fetch).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalled();
  });

  it("DELETE confirms then calls API", async () => {
    mockUseAuth.mockReturnValue(ADMIN_AUTH);
    window.confirm = jest.fn(() => true);
    (global.fetch as jest.Mock).mockResolvedValue({ ok: true, json: async () => ({}) });
    render(<AdminCnaeMappingPage />);
    fireEvent.click(screen.getByTestId("cnae-delete-4120"));
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/admin/cnae-mapping/4120",
        expect.objectContaining({ method: "DELETE" })
      );
    });
  });

  it("DELETE bails out on confirm cancel", () => {
    mockUseAuth.mockReturnValue(ADMIN_AUTH);
    window.confirm = jest.fn(() => false);
    render(<AdminCnaeMappingPage />);
    fireEvent.click(screen.getByTestId("cnae-delete-4120"));
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("RESTORE calls /restore endpoint", async () => {
    mockUseAuth.mockReturnValue(ADMIN_AUTH);
    (global.fetch as jest.Mock).mockResolvedValue({ ok: true, json: async () => ({}) });
    render(<AdminCnaeMappingPage />);
    fireEvent.click(screen.getByTestId("cnae-restore-4781"));
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/admin/cnae-mapping/4781/restore",
        expect.objectContaining({ method: "POST" })
      );
    });
  });

  it("opens audit drawer and shows entries", async () => {
    mockUseAuth.mockReturnValue(ADMIN_AUTH);
    mockUseAdminSWR.mockImplementation((key: string | null) => {
      if (!key) return { data: undefined, error: null, isLoading: false, mutate: mockMutate };
      if (key.includes("/cnae-mapping?")) {
        return {
          data: SAMPLE_LIST,
          error: null,
          isLoading: false,
          mutate: mockMutate,
        };
      }
      // Detail
      return {
        data: {
          mapping: SAMPLE_LIST.items[0],
          audit: [
            {
              id: "audit-1",
              cnae_code: "4120",
              action: "create",
              old_value: null,
              new_value: { setor_id: "engenharia" },
              actor_email: "tiago@smartlic.tech",
              note: null,
              created_at: "2026-04-28T12:00:00Z",
            },
          ],
        },
        error: null,
        isLoading: false,
        mutate: mockMutate,
      };
    });
    render(<AdminCnaeMappingPage />);
    fireEvent.click(screen.getByTestId("cnae-audit-4120"));
    expect(screen.getByTestId("cnae-audit-drawer")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId("cnae-audit-entry-audit-1")).toBeInTheDocument();
    });
  });

  it("bulk-import preview posts CSV with dry_run=true", async () => {
    mockUseAuth.mockReturnValue(ADMIN_AUTH);
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
        dry_run: true,
        creates: 1,
        updates: 0,
        deactivations: 0,
        noops: 0,
        errors: 0,
        preview: [
          {
            cnae_code: "9988",
            action: "create",
            old: null,
            new: SAMPLE_LIST.items[0],
            error: null,
          },
        ],
      }),
    });
    render(<AdminCnaeMappingPage />);
    fireEvent.click(screen.getByTestId("cnae-bulk"));

    const file = new File(["cnae_code,setor_id\n9988,engenharia\n"], "in.csv", {
      type: "text/csv",
    });
    const input = screen.getByTestId("cnae-bulk-file") as HTMLInputElement;
    Object.defineProperty(input, "files", { value: [file] });
    fireEvent.change(input);

    fireEvent.click(screen.getByTestId("cnae-bulk-preview"));
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/admin/cnae-mapping/bulk-import?dry_run=true",
        expect.objectContaining({ method: "POST" })
      );
    });
    // The preview block renders after the fetch promise settles and
    // setState propagates — waitFor handles the second render tick.
    await waitFor(() => {
      expect(screen.getByTestId("cnae-bulk-preview-result")).toBeInTheDocument();
    });
  });
});
