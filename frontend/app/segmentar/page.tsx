"use client";

/**
 * CONV-018: Standalone segmentation page.
 *
 * 3-question form (sector, UFs, objective) for journey personalization.
 * Accessible at /segmentar — redirects to /buscar after completion.
 */

import { useRouter } from "next/navigation";
import { SegmentForm } from "../../components/SegmentForm";

export default function SegmentarPage() {
  const router = useRouter();

  return (
    <div className="min-h-screen bg-[var(--surface-0)] flex items-center justify-center p-4">
      <div className="w-full max-w-xl">
        {/* Header */}
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold text-[var(--ink)]">
            Vamos personalizar sua experiência
          </h1>
          <p className="text-sm text-[var(--ink-secondary)] mt-1">
            Três perguntas rápidas para encontrar as melhores oportunidades para
            você.
          </p>
        </div>

        {/* Card */}
        <div className="bg-[var(--surface-0)] border border-[var(--border)] rounded-xl p-6 shadow-sm">
          <SegmentForm
            onComplete={() => router.push("/buscar")}
            submitLabel="Ver Oportunidades"
          />
        </div>
      </div>
    </div>
  );
}
