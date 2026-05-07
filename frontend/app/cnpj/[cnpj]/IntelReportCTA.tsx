"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface Props {
  cnpj: string;
}

/**
 * Intel Report CTA for /cnpj/[cnpj] pages (#632).
 *
 * Unauthenticated click → redirect to /signup?intent=intel_report.
 * Authenticated click → Stripe Checkout for Raio-X do Concorrente (R$197).
 *
 * Must be a separate "use client" file because the parent page.tsx is a
 * Server Component with ISR (revalidate=86400).
 */
export default function IntelReportCTA({ cnpj }: Props) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  const handleBuy = async () => {
    setLoading(true);
    try {
      if (typeof window !== "undefined" && window.mixpanel) {
        window.mixpanel.track("intel_report_cta_clicked", {
          cnpj,
          page_path: `/cnpj/${cnpj}`,
        });
      }

      const res = await fetch("/api/intel-reports/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ product_type: "cnpj", entity_key: cnpj }),
      });

      if (res.status === 401) {
        router.push(`/signup?redirect=/cnpj/${cnpj}&intent=intel_report`);
        return;
      }

      if (!res.ok) {
        throw new Error(`checkout failed: ${res.status}`);
      }

      const { checkout_url } = await res.json();

      if (typeof window !== "undefined" && window.mixpanel) {
        window.mixpanel.track("intel_report_checkout_started", {
          product_type: "cnpj",
          entity_key: cnpj,
        });
      }

      window.location.href = checkout_url;
    } catch {
      setLoading(false);
      alert("Não foi possível iniciar o checkout. Tente novamente.");
    }
  };

  return (
    <button
      onClick={handleBuy}
      disabled={loading}
      className="w-full rounded-lg bg-blue-600 px-6 py-3 font-semibold text-white transition-colors hover:bg-blue-700 disabled:opacity-60"
    >
      {loading ? "Aguarde..." : "Comprar Raio-X — R$197"}
    </button>
  );
}
