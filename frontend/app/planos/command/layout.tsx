import { Metadata } from "next";
import { ErrorBoundary } from "../../../components/ErrorBoundary";

export const metadata: Metadata = {
  title: "SmartLic Command — Inteligencia Executiva em Licitacoes Publicas",
  description:
    "O Bloomberg de compras publicas. Plataforma enterprise para diretores, consultorias e equipes B2G que exigem inteligencia definitiva em licitacoes publicas. Multi-usuario, API exclusiva, relatorios executivos com IA.",
  alternates: {
    canonical: "https://smartlic.tech/planos/command",
  },
  openGraph: {
    title: "SmartLic Command — O Bloomberg de Compras Publicas",
    description:
      "Inteligencia definitiva para decisoes bilionarias. Multi-usuario, API exclusiva, relatorios executivos com IA e analise preditiva de mercado.",
    url: "https://smartlic.tech/planos/command",
    siteName: "SmartLic",
    type: "website",
    locale: "pt_BR",
  },
};

export default function CommandLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <ErrorBoundary pageName="planos-command">{children}</ErrorBoundary>;
}
