"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";

type PurchaseStatus = "pending" | "generating" | "ready" | "failed";

interface IntelReportPurchase {
  id: string;
  status: PurchaseStatus;
  pdf_url?: string;
  expires_at?: string;
}

const MAX_POLLS = 40; // 40 × 3s = 120s max
const POLL_INTERVAL_MS = 3000;

/**
 * Post-Stripe success page for Intel Report one-time purchases (#632).
 *
 * URL pattern: /intel-reports/{CHECKOUT_SESSION_ID}?status=processing
 * The page polls GET /api/intel-reports (list) to find the most recent
 * purchase and tracks it until status reaches "ready" or "failed".
 *
 * NOTE: The backend status endpoint (GET /v1/intel-reports/{purchase_id})
 * accepts a DB UUID, not the Stripe session ID in the URL. We resolve the
 * purchase by listing and taking the most recent pending/generating entry.
 */
export default function IntelReportSuccessPage() {
  const params = useParams();
  const sessionId = params.sessionId as string;

  const [purchase, setPurchase] = useState<IntelReportPurchase | null>(null);
  const [timedOut, setTimedOut] = useState(false);
  const pollCountRef = useRef(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (!sessionId) return;

    const fetchLatestPurchase = async (): Promise<IntelReportPurchase | null> => {
      try {
        const res = await fetch("/api/intel-reports");
        if (!res.ok) return null;
        const items: IntelReportPurchase[] = await res.json();
        // Most recent purchase is first (backend orders by created_at DESC)
        return items.length > 0 ? items[0] : null;
      } catch {
        return null;
      }
    };

    const doPoll = async () => {
      const item = await fetchLatestPurchase();
      pollCountRef.current += 1;

      if (item) {
        setPurchase(item);
        if (item.status === "ready" || item.status === "failed") {
          return; // terminal state — stop polling
        }
      }

      if (pollCountRef.current >= MAX_POLLS) {
        setTimedOut(true);
        return;
      }

      timerRef.current = setTimeout(doPoll, POLL_INTERVAL_MS);
    };

    // Small initial delay to let Stripe webhook land
    timerRef.current = setTimeout(doPoll, 1500);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [sessionId]);

  const handleDownload = () => {
    if (!purchase) return;
    window.open(`/api/intel-reports/${purchase.id}/download`, "_blank");
    if (typeof window !== "undefined" && window.mixpanel) {
      window.mixpanel.track("intel_report_downloaded", {
        purchase_id: purchase.id,
      });
    }
  };

  const isTerminal =
    purchase?.status === "ready" || purchase?.status === "failed";
  const isProcessing =
    !purchase || purchase.status === "pending" || purchase.status === "generating";

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 p-4">
      <div className="w-full max-w-md rounded-xl bg-white p-8 text-center shadow-sm">
        {/* Title */}
        <h1 className="mb-4 text-2xl font-bold text-gray-900">
          {purchase?.status === "ready"
            ? "Relatório pronto!"
            : purchase?.status === "failed"
              ? "Erro ao gerar relatório"
              : timedOut
                ? "Processando..."
                : "Gerando seu relatório..."}
        </h1>

        {/* Ready state */}
        {purchase?.status === "ready" && (
          <>
            <p className="mb-6 text-gray-600">
              Seu relatório de inteligência está disponível para download.
            </p>
            <button
              onClick={handleDownload}
              className="mb-4 w-full rounded-lg bg-blue-600 px-6 py-3 font-semibold text-white hover:bg-blue-700"
            >
              Baixar Relatório (PDF)
            </button>
            <p className="text-sm text-gray-500">
              Link válido por 30 dias. Você também receberá o link por email.
            </p>
            <div className="mt-6 rounded-lg bg-blue-50 p-4">
              <p className="text-sm text-blue-800">
                Ative 14 dias grátis SmartLic Pro →{" "}
                <Link href="/planos" className="font-semibold underline">
                  Conhecer planos
                </Link>
              </p>
            </div>
          </>
        )}

        {/* Failed state */}
        {purchase?.status === "failed" && (
          <p className="text-gray-600">
            Ocorreu um erro ao gerar seu relatório. Nossa equipe foi notificada.
            Entre em contato:{" "}
            <a
              href="mailto:tiago.sasaki@confenge.com.br"
              className="text-blue-600 underline"
            >
              tiago.sasaki@confenge.com.br
            </a>
          </p>
        )}

        {/* Processing / initial load */}
        {isProcessing && !timedOut && (
          <>
            <div className="mb-4 flex justify-center">
              <div className="h-10 w-10 animate-spin rounded-full border-b-2 border-blue-600" />
            </div>
            <p className="text-sm text-gray-500">
              Isso leva em torno de 30–60 segundos...
            </p>
          </>
        )}

        {/* Timed out but not yet in terminal state */}
        {timedOut && !isTerminal && (
          <p className="text-sm text-gray-600">
            Seu relatório está sendo processado. Você receberá um email quando
            estiver pronto. Não feche esta página ainda.
          </p>
        )}
      </div>
    </div>
  );
}
