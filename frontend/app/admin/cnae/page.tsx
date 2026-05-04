"use client";

/**
 * DATA-CNAE-001 (AC10-AC12): Admin UI for cnae_setor_mapping CRUD.
 *
 * Pairs with backend/routes/admin_cnae.py (/v1/admin/cnae-mapping).
 * Renders a paginated table with filters, inline edit/delete/restore,
 * an audit log drawer, and a CSV bulk-import flow with dry-run preview.
 */

import { useCallback, useMemo, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";

import { useAuth } from "../../components/AuthProvider";
import { useAdminSWR } from "../../../hooks/useAdminSWR";

// ─────────────────────────────────────────────────────────────────────────────
// Local types — mirror Pydantic schemas in backend/routes/admin_cnae.py.
// Keep optional fields permissive so the page renders even when the API
// returns a partial row (e.g. server-degraded mode).
// ─────────────────────────────────────────────────────────────────────────────
interface CnaeMapping {
  cnae_code: string;
  setor_id: string;
  confidence: number;
  notes: string | null;
  is_active: boolean;
  created_at?: string | null;
  updated_at?: string | null;
  updated_by?: string | null;
}

interface ListResponse {
  items: CnaeMapping[];
  total: number;
  limit: number;
  offset: number;
}

interface AuditEntry {
  id: string;
  cnae_code: string | null;
  action: string;
  old_value: Record<string, unknown> | null;
  new_value: Record<string, unknown> | null;
  actor_email: string | null;
  note: string | null;
  created_at: string;
}

interface DetailResponse {
  mapping: CnaeMapping;
  audit: AuditEntry[];
}

interface BulkPreviewItem {
  cnae_code: string;
  action: string;
  old: CnaeMapping | null;
  new: CnaeMapping | null;
  error: string | null;
}

interface BulkResponse {
  dry_run: boolean;
  creates: number;
  updates: number;
  deactivations: number;
  noops: number;
  errors: number;
  preview: BulkPreviewItem[];
}

const PAGE_SIZE = 50;

const SECTOR_OPTIONS = [
  // Yaml-canonical
  "vestuario",
  "alimentos",
  "informatica",
  "mobiliario",
  "papelaria",
  "engenharia",
  "software_desenvolvimento",
  "software_licencas",
  "servicos_prediais",
  "produtos_limpeza",
  "medicamentos",
  "equipamentos_medicos",
  "insumos_hospitalares",
  "vigilancia",
  "transporte_servicos",
  "frota_veicular",
  "manutencao_predial",
  "engenharia_rodoviaria",
  "materiais_eletricos",
  "materiais_hidraulicos",
  // Legacy aliases preserved by AC15
  "saude",
  "equipamentos",
  "transporte",
  "geral",
] as const;

// Loose CNAE format check — accepts "4781", "4781-4/00", "4781400"; the
// backend canonicalises the value anyway via _extract_prefix.
const CNAE_PATTERN = /^\d{4}(?:[-/]\d+)*$/;

// ─────────────────────────────────────────────────────────────────────────────
// Page component
// ─────────────────────────────────────────────────────────────────────────────
export default function AdminCnaeMappingPage() {
  const { session, loading: authLoading, isAdmin, isAdminLoading } = useAuth();

  // List filters / pagination state.
  const [search, setSearch] = useState("");
  const [setorFilter, setSetorFilter] = useState("");
  const [activeFilter, setActiveFilter] = useState<"" | "true" | "false">("");
  const [offset, setOffset] = useState(0);

  // Edit / detail / bulk-import drawers.
  const [editing, setEditing] = useState<CnaeMapping | null>(null);
  const [creating, setCreating] = useState(false);
  const [detailCode, setDetailCode] = useState<string | null>(null);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [bulkPreview, setBulkPreview] = useState<BulkResponse | null>(null);
  const [bulkFile, setBulkFile] = useState<File | null>(null);
  const [bulkBusy, setBulkBusy] = useState(false);

  const queryString = useMemo(() => {
    const params = new URLSearchParams();
    params.set("limit", String(PAGE_SIZE));
    params.set("offset", String(offset));
    if (search.trim()) params.set("search", search.trim());
    if (setorFilter) params.set("setor_id", setorFilter);
    if (activeFilter !== "") params.set("is_active", activeFilter);
    return params.toString();
  }, [search, setorFilter, activeFilter, offset]);

  const shouldFetch = isAdmin && !authLoading && !isAdminLoading;
  const listKey = shouldFetch
    ? `/api/admin/cnae-mapping?${queryString}`
    : null;
  const { data, error, isLoading, mutate } = useAdminSWR<ListResponse>(listKey);

  const detailKey = detailCode
    ? `/api/admin/cnae-mapping/${detailCode}`
    : null;
  const { data: detail } = useAdminSWR<DetailResponse>(detailKey);

  const authHeaders = useCallback(() => {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (session?.access_token) {
      headers.Authorization = `Bearer ${session.access_token}`;
    }
    return headers;
  }, [session?.access_token]);

  // ───────── Mutations ─────────
  const handleSave = useCallback(
    async (payload: Partial<CnaeMapping>, mode: "create" | "update", code?: string) => {
      const url =
        mode === "create"
          ? "/api/admin/cnae-mapping"
          : `/api/admin/cnae-mapping/${code}`;
      const method = mode === "create" ? "POST" : "PATCH";
      try {
        const res = await fetch(url, {
          method,
          headers: authHeaders(),
          body: JSON.stringify(payload),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `Erro ${res.status}`);
        }
        toast.success(mode === "create" ? "Mapping criado" : "Mapping atualizado");
        setEditing(null);
        setCreating(false);
        mutate();
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Erro ao salvar");
      }
    },
    [authHeaders, mutate]
  );

  const handleSoftDelete = useCallback(
    async (row: CnaeMapping) => {
      if (!window.confirm(`Desativar mapping ${row.cnae_code} → ${row.setor_id}?`)) {
        return;
      }
      try {
        const res = await fetch(`/api/admin/cnae-mapping/${row.cnae_code}`, {
          method: "DELETE",
          headers: authHeaders(),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `Erro ${res.status}`);
        }
        toast.success("Mapping desativado");
        mutate();
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Erro ao desativar");
      }
    },
    [authHeaders, mutate]
  );

  const handleRestore = useCallback(
    async (row: CnaeMapping) => {
      try {
        const res = await fetch(
          `/api/admin/cnae-mapping/${row.cnae_code}/restore`,
          { method: "POST", headers: authHeaders() }
        );
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `Erro ${res.status}`);
        }
        toast.success("Mapping restaurado");
        mutate();
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Erro ao restaurar");
      }
    },
    [authHeaders, mutate]
  );

  // ───────── Bulk import ─────────
  const handleBulkUpload = useCallback(
    async (mode: "preview" | "commit") => {
      if (!bulkFile) {
        toast.error("Selecione um arquivo CSV");
        return;
      }
      setBulkBusy(true);
      try {
        const fd = new FormData();
        fd.append("file", bulkFile);
        const dryRun = mode === "preview";
        const res = await fetch(
          `/api/admin/cnae-mapping/bulk-import?dry_run=${dryRun}`,
          {
            method: "POST",
            headers: session?.access_token
              ? { Authorization: `Bearer ${session.access_token}` }
              : undefined,
            body: fd,
          }
        );
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `Erro ${res.status}`);
        }
        const json = (await res.json()) as BulkResponse;
        setBulkPreview(json);
        if (mode === "commit") {
          toast.success(
            `Aplicado: ${json.creates} criados, ${json.updates} atualizados, ${json.errors} erros`
          );
          mutate();
        } else {
          toast.success(`Preview: ${json.preview.length} linhas processadas`);
        }
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Erro no bulk import");
      } finally {
        setBulkBusy(false);
      }
    },
    [bulkFile, session?.access_token, mutate]
  );

  const handleExport = useCallback(() => {
    if (!data?.items?.length) return;
    const header = "cnae_code,setor_id,confidence,notes,is_active\n";
    const body = data.items
      .map((r) => {
        const notes = r.notes ? `"${r.notes.replace(/"/g, '""')}"` : "";
        return `${r.cnae_code},${r.setor_id},${r.confidence},${notes},${r.is_active}`;
      })
      .join("\n");
    const blob = new Blob([header + body], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `cnae-mapping-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [data?.items]);

  // ───────── Auth/loading guards ─────────
  if (authLoading || isAdminLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p>Carregando…</p>
      </div>
    );
  }
  if (!session) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Link href="/login">Faça login</Link>
      </div>
    );
  }
  if (!isAdmin) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p>Acesso restrito a administradores.</p>
      </div>
    );
  }

  // ───────── Render ─────────
  return (
    <div className="p-6 max-w-7xl mx-auto" data-testid="admin-cnae-page">
      <header className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-semibold">CNAE → Setor</h1>
        <div className="flex gap-2">
          <button
            onClick={() => setCreating(true)}
            className="px-3 py-1.5 rounded bg-blue-600 text-white text-sm"
            data-testid="cnae-new"
          >
            Novo mapping
          </button>
          <button
            onClick={() => setBulkOpen(true)}
            className="px-3 py-1.5 rounded bg-amber-600 text-white text-sm"
            data-testid="cnae-bulk"
          >
            Bulk import CSV
          </button>
          <button
            onClick={handleExport}
            className="px-3 py-1.5 rounded bg-gray-200 text-gray-800 text-sm"
            data-testid="cnae-export"
          >
            Export CSV
          </button>
        </div>
      </header>

      {/* Filters */}
      <section className="grid grid-cols-1 md:grid-cols-4 gap-2 mb-4">
        <input
          placeholder="Buscar por CNAE / setor / nota…"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setOffset(0);
          }}
          className="border rounded px-2 py-1.5 text-sm"
          data-testid="cnae-search"
        />
        <select
          value={setorFilter}
          onChange={(e) => {
            setSetorFilter(e.target.value);
            setOffset(0);
          }}
          className="border rounded px-2 py-1.5 text-sm"
          data-testid="cnae-setor-filter"
        >
          <option value="">Todos os setores</option>
          {SECTOR_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select
          value={activeFilter}
          onChange={(e) => {
            setActiveFilter(e.target.value as "" | "true" | "false");
            setOffset(0);
          }}
          className="border rounded px-2 py-1.5 text-sm"
          data-testid="cnae-active-filter"
        >
          <option value="">Ativos + Inativos</option>
          <option value="true">Apenas ativos</option>
          <option value="false">Apenas inativos</option>
        </select>
        <div className="text-sm text-gray-600 self-center" data-testid="cnae-total">
          {data ? `${data.total} mappings` : ""}
        </div>
      </section>

      {/* Table */}
      <section>
        {error && (
          <p className="text-red-600" role="alert">
            Erro ao carregar mappings.
          </p>
        )}
        {isLoading && <p>Carregando…</p>}
        {data && (
          <table className="w-full text-sm" data-testid="cnae-table">
            <thead>
              <tr className="text-left border-b">
                <th className="py-2">CNAE</th>
                <th>Setor</th>
                <th>Conf.</th>
                <th>Ativo</th>
                <th>Notas</th>
                <th>Atualizado</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((row) => (
                <tr
                  key={row.cnae_code}
                  data-testid={`cnae-row-${row.cnae_code}`}
                  className={row.is_active ? "" : "opacity-50"}
                >
                  <td className="py-2 font-mono">{row.cnae_code}</td>
                  <td>{row.setor_id}</td>
                  <td>{row.confidence.toFixed(2)}</td>
                  <td>{row.is_active ? "✓" : "—"}</td>
                  <td className="max-w-xs truncate">{row.notes || ""}</td>
                  <td>{row.updated_at?.slice(0, 10) || ""}</td>
                  <td className="space-x-1">
                    <button
                      onClick={() => setEditing(row)}
                      data-testid={`cnae-edit-${row.cnae_code}`}
                      className="text-blue-600 hover:underline"
                    >
                      editar
                    </button>
                    <button
                      onClick={() => setDetailCode(row.cnae_code)}
                      data-testid={`cnae-audit-${row.cnae_code}`}
                      className="text-purple-600 hover:underline"
                    >
                      audit
                    </button>
                    {row.is_active ? (
                      <button
                        onClick={() => handleSoftDelete(row)}
                        data-testid={`cnae-delete-${row.cnae_code}`}
                        className="text-red-600 hover:underline"
                      >
                        desativar
                      </button>
                    ) : (
                      <button
                        onClick={() => handleRestore(row)}
                        data-testid={`cnae-restore-${row.cnae_code}`}
                        className="text-green-600 hover:underline"
                      >
                        restaurar
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {/* Pagination */}
        {data && data.total > PAGE_SIZE && (
          <div className="flex justify-center gap-2 my-4">
            <button
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              className="px-2 py-1 border rounded disabled:opacity-50"
            >
              ← anterior
            </button>
            <span className="text-sm self-center">
              {offset + 1}–{Math.min(offset + PAGE_SIZE, data.total)} / {data.total}
            </span>
            <button
              disabled={offset + PAGE_SIZE >= data.total}
              onClick={() => setOffset(offset + PAGE_SIZE)}
              className="px-2 py-1 border rounded disabled:opacity-50"
            >
              próximo →
            </button>
          </div>
        )}
      </section>

      {/* Edit modal */}
      {(editing || creating) && (
        <CnaeMappingForm
          initial={editing || undefined}
          onCancel={() => {
            setEditing(null);
            setCreating(false);
          }}
          onSubmit={(payload) => {
            if (editing) {
              handleSave(payload, "update", editing.cnae_code);
            } else {
              handleSave(payload, "create");
            }
          }}
        />
      )}

      {/* Audit drawer */}
      {detailCode && (
        <AuditDrawer
          code={detailCode}
          detail={detail}
          onClose={() => setDetailCode(null)}
        />
      )}

      {/* Bulk import modal */}
      {bulkOpen && (
        <BulkImportModal
          onClose={() => {
            setBulkOpen(false);
            setBulkPreview(null);
            setBulkFile(null);
          }}
          onFileChange={setBulkFile}
          onPreview={() => handleBulkUpload("preview")}
          onCommit={() => handleBulkUpload("commit")}
          preview={bulkPreview}
          busy={bulkBusy}
          file={bulkFile}
        />
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components (kept in-file because they're tightly coupled).
// ─────────────────────────────────────────────────────────────────────────────
interface FormProps {
  initial?: CnaeMapping;
  onCancel: () => void;
  onSubmit: (payload: Partial<CnaeMapping>) => void;
}

function CnaeMappingForm({ initial, onCancel, onSubmit }: FormProps) {
  const [code, setCode] = useState(initial?.cnae_code ?? "");
  const [setor, setSetor] = useState(initial?.setor_id ?? "engenharia");
  const [confidence, setConfidence] = useState(initial?.confidence ?? 1.0);
  const [notes, setNotes] = useState(initial?.notes ?? "");
  const [isActive, setIsActive] = useState(initial?.is_active ?? true);
  const isEdit = Boolean(initial);

  const validateAndSubmit = () => {
    if (!isEdit) {
      if (!CNAE_PATTERN.test(code)) {
        toast.error("CNAE inválido — formato esperado: XXXX, XXXX-X/XX ou XXXXXXX");
        return;
      }
    }
    if (!setor) {
      toast.error("Setor obrigatório");
      return;
    }
    if (confidence < 0 || confidence > 1) {
      toast.error("Confiança deve estar em [0, 1]");
      return;
    }
    const payload: Partial<CnaeMapping> = {
      setor_id: setor,
      confidence,
      notes: notes || null,
    };
    if (!isEdit) {
      payload.cnae_code = code;
    } else {
      payload.is_active = isActive;
    }
    onSubmit(payload);
  };

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      data-testid="cnae-form-modal"
    >
      <div className="bg-white rounded-lg p-6 w-full max-w-md">
        <h2 className="text-lg font-semibold mb-4">
          {isEdit ? `Editar ${initial?.cnae_code}` : "Novo mapping"}
        </h2>
        <label className="block mb-3">
          <span className="text-sm">CNAE (4-digit prefix)</span>
          <input
            value={code}
            onChange={(e) => setCode(e.target.value)}
            disabled={isEdit}
            placeholder="ex: 4781 ou 4781-4/00"
            className="border rounded w-full px-2 py-1.5 text-sm font-mono"
            data-testid="cnae-form-code"
          />
        </label>
        <label className="block mb-3">
          <span className="text-sm">Setor</span>
          <select
            value={setor}
            onChange={(e) => setSetor(e.target.value)}
            className="border rounded w-full px-2 py-1.5 text-sm"
            data-testid="cnae-form-setor"
          >
            {SECTOR_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <label className="block mb-3">
          <span className="text-sm">Confiança (0–1)</span>
          <input
            type="number"
            step={0.05}
            min={0}
            max={1}
            value={confidence}
            onChange={(e) => setConfidence(Number(e.target.value))}
            className="border rounded w-full px-2 py-1.5 text-sm"
            data-testid="cnae-form-confidence"
          />
        </label>
        <label className="block mb-3">
          <span className="text-sm">Notas</span>
          <textarea
            value={notes ?? ""}
            onChange={(e) => setNotes(e.target.value)}
            className="border rounded w-full px-2 py-1.5 text-sm"
            data-testid="cnae-form-notes"
            rows={3}
          />
        </label>
        {isEdit && (
          <label className="flex items-center gap-2 mb-3 text-sm">
            <input
              type="checkbox"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
              data-testid="cnae-form-active"
            />
            Ativo
          </label>
        )}
        <div className="flex gap-2 justify-end">
          <button onClick={onCancel} className="px-3 py-1.5 rounded border text-sm">
            Cancelar
          </button>
          <button
            onClick={validateAndSubmit}
            className="px-3 py-1.5 rounded bg-blue-600 text-white text-sm"
            data-testid="cnae-form-save"
          >
            Salvar
          </button>
        </div>
      </div>
    </div>
  );
}

interface AuditProps {
  code: string;
  detail: DetailResponse | undefined;
  onClose: () => void;
}

function AuditDrawer({ code, detail, onClose }: AuditProps) {
  return (
    <div
      className="fixed inset-0 bg-black/50 flex justify-end z-50"
      data-testid="cnae-audit-drawer"
    >
      <aside className="bg-white w-full max-w-lg p-6 overflow-y-auto">
        <header className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Audit log — {code}</h2>
          <button onClick={onClose} className="text-sm">
            Fechar
          </button>
        </header>
        {!detail && <p>Carregando…</p>}
        {detail && (
          <>
            <p className="text-sm mb-2">
              Setor atual: <strong>{detail.mapping.setor_id}</strong> (conf{" "}
              {detail.mapping.confidence.toFixed(2)})
              {!detail.mapping.is_active && (
                <span className="ml-2 text-red-600">[inativo]</span>
              )}
            </p>
            <ol className="border-l-2 border-gray-200 pl-3 space-y-3">
              {detail.audit.length === 0 && (
                <li className="text-sm text-gray-500">Nenhum evento registrado.</li>
              )}
              {detail.audit.map((entry) => (
                <li key={entry.id} data-testid={`cnae-audit-entry-${entry.id}`}>
                  <p className="text-xs text-gray-500">
                    {entry.created_at} · {entry.actor_email || "(sistema)"} · {entry.action}
                  </p>
                  {entry.note && <p className="text-xs italic">{entry.note}</p>}
                  <pre className="text-xs bg-gray-50 p-2 mt-1 rounded overflow-x-auto">
                    {JSON.stringify(
                      { old: entry.old_value, new: entry.new_value },
                      null,
                      2
                    )}
                  </pre>
                </li>
              ))}
            </ol>
          </>
        )}
      </aside>
    </div>
  );
}

interface BulkProps {
  onClose: () => void;
  onFileChange: (file: File | null) => void;
  onPreview: () => void;
  onCommit: () => void;
  preview: BulkResponse | null;
  busy: boolean;
  file: File | null;
}

function BulkImportModal({
  onClose,
  onFileChange,
  onPreview,
  onCommit,
  preview,
  busy,
  file,
}: BulkProps) {
  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      data-testid="cnae-bulk-modal"
    >
      <div className="bg-white rounded-lg p-6 w-full max-w-2xl max-h-[80vh] overflow-y-auto">
        <header className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Bulk import CSV</h2>
          <button onClick={onClose} className="text-sm">
            Fechar
          </button>
        </header>

        <p className="text-sm mb-2">
          CSV obrigatório com colunas <code>cnae_code,setor_id</code>. Opcionais:{" "}
          <code>confidence, notes, is_active</code>.
        </p>

        <input
          type="file"
          accept=".csv,text/csv"
          onChange={(e) => onFileChange(e.target.files?.[0] ?? null)}
          className="mb-3"
          data-testid="cnae-bulk-file"
        />

        <div className="flex gap-2 mb-4">
          <button
            onClick={onPreview}
            disabled={!file || busy}
            className="px-3 py-1.5 rounded bg-amber-600 text-white text-sm disabled:opacity-50"
            data-testid="cnae-bulk-preview"
          >
            {busy ? "Processando…" : "Preview (dry run)"}
          </button>
          <button
            onClick={onCommit}
            disabled={!preview || busy}
            className="px-3 py-1.5 rounded bg-red-600 text-white text-sm disabled:opacity-50"
            data-testid="cnae-bulk-commit"
          >
            Aplicar
          </button>
        </div>

        {preview && (
          <div className="text-sm" data-testid="cnae-bulk-preview-result">
            <p>
              <strong>Resumo:</strong> {preview.creates} criar · {preview.updates}{" "}
              atualizar · {preview.deactivations} desativar · {preview.noops} sem
              mudança · {preview.errors} erros
            </p>
            <table className="w-full mt-2 border-t">
              <thead>
                <tr className="text-left">
                  <th className="py-1">CNAE</th>
                  <th>Ação</th>
                  <th>Antes → Depois</th>
                  <th>Erro</th>
                </tr>
              </thead>
              <tbody>
                {preview.preview.map((p, idx) => (
                  <tr
                    key={`${p.cnae_code}-${idx}`}
                    className="border-t"
                    data-testid={`cnae-bulk-preview-row-${idx}`}
                  >
                    <td className="py-1 font-mono">{p.cnae_code}</td>
                    <td>{p.action}</td>
                    <td className="text-xs">
                      {p.old?.setor_id || "—"} → {p.new?.setor_id || "—"}
                    </td>
                    <td className="text-xs text-red-600">{p.error || ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
