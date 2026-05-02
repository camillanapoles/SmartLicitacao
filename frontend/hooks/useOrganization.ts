"use client";

import useSWR from "swr";
import { useAuth } from "../app/components/AuthProvider";
import { FetchError } from "../lib/fetcher";

/**
 * FE-007: SWR-based organization hook.
 * Replaces two-step manual fetch in conta/equipe/page.tsx.
 * Step 1: GET /api/organizations → returns { id, name, role }
 * Step 2: GET /api/organizations/{id} → returns full org with members
 */

export interface OrgMember {
  id: string;
  user_id: string | null;
  email: string;
  name: string | null;
  role: "owner" | "member" | "viewer";
  status: "accepted" | "pending";
  joined_at: string | null;
  invited_at: string;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  max_seats: number;
  members: OrgMember[];
}

/** Fetches the full org in a single SWR key (two sequential requests). */
const fetchOrgWithAuth = async (token: string): Promise<Organization | null> => {
  // Step 1: get org ref
  const refRes = await fetch("/api/organizations", {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (refRes.status === 404) return null;

  if (!refRes.ok) {
    const data = await refRes.json().catch(() => ({}));
    throw new FetchError(data.message || "Erro ao carregar organização", refRes.status);
  }

  const ref: { id: string } = await refRes.json();

  // Step 2: get full org details
  const detailRes = await fetch(`/api/organizations/${ref.id}`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!detailRes.ok) {
    if (detailRes.status === 403) {
      throw new FetchError(
        "Acesso negado: sua função não permite ver os detalhes da organização.",
        403
      );
    }
    const data = await detailRes.json().catch(() => ({}));
    throw new FetchError(
      data.message || "Erro ao carregar detalhes da organização",
      detailRes.status
    );
  }

  return detailRes.json();
};

export function useOrganization() {
  const { session } = useAuth();
  const accessToken = session?.access_token;

  const { data, error, isLoading, mutate } = useSWR(
    accessToken ? ["organization", accessToken] : null,
    ([, token]: [string, string]) => fetchOrgWithAuth(token),
    {
      revalidateOnFocus: false,
      dedupingInterval: 30_000,
      errorRetryCount: 2,
    }
  );

  return {
    org: data ?? null,
    isLoading,
    error: error instanceof FetchError ? error.message : error ? String(error) : null,
    mutate,
    refresh: () => mutate(),
  };
}
