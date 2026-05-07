"use client";

import Link from "next/link";

/**
 * Cancel URL after abandoned Stripe Checkout for Intel Report (#632).
 */
export default function IntelReportCanceladoPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 p-4">
      <div className="w-full max-w-md rounded-xl bg-white p-8 text-center shadow-sm">
        <h1 className="mb-4 text-2xl font-bold text-gray-900">
          Compra cancelada
        </h1>
        <p className="mb-6 text-gray-600">
          Nenhuma cobrança foi realizada. Você pode voltar e tentar novamente quando quiser.
        </p>
        <Link
          href="/"
          className="inline-block rounded-lg bg-blue-600 px-6 py-3 font-semibold text-white hover:bg-blue-700"
        >
          Voltar ao início
        </Link>
      </div>
    </div>
  );
}
