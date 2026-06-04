"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useAuth } from "../../../app/components/AuthProvider";
import LandingNavbar from "../../../app/components/landing/LandingNavbar";
import Link from "next/link";
import { useAnalytics } from "../../../hooks/useAnalytics";
import { useClarity } from "../../../hooks/useClarity";
import { getUserFriendlyError } from "../../../lib/error-messages";
import { PlanToggle, type BillingPeriod } from "../../../components/subscriptions/PlanToggle";
import { formatCurrency } from "@/lib/copy/roi";
import { toast } from "sonner";
import {
  MessageCircle, Mail, Check, Shield, TrendingUp, BarChart3,
  Users, Globe, Lock, Zap, Headphones, FileText, Code, Building2,
  LineChart, Network,
} from "lucide-react";
import { Button, buttonVariants } from "../../../components/ui/button";
import { trackViewItem, trackBeginCheckout } from "../../../app/components/GoogleAnalytics";
import { COMMAND_PRICING } from "@/lib/plan-pricing";
import { PlanFAQ } from "../components/PlanFAQ";
import { CaseStudyCard } from "../../../components/CaseStudyCard";

const ANALYTICS = {
  LANDING_VIEWED: "command_landing_viewed",
  CHECKOUT_STARTED: "command_checkout_started",
  CHECKOUT_COMPLETED: "command_checkout_completed",
} as const;

const PRICING = COMMAND_PRICING;
const SUPPORT_WHATSAPP_NUMBER = "5548988344559";
const SUPPORT_WHATSAPP_MESSAGE = "Ola! Tenho interesse no SmartLic Command.";
const SUPPORT_WHATSAPP_URL = `https://web.whatsapp.com/send?phone=${SUPPORT_WHATSAPP_NUMBER}&text=${encodeURIComponent(SUPPORT_WHATSAPP_MESSAGE)}`;

const COMMAND_CAPABILITIES = [
  { icon: Users, title: "Ate 10 usuarios dedicados", description: "Sua equipe de alto desempenho com acesso simultaneo e permissoes granulares." },
  { icon: Code, title: "API exclusiva", description: "Integre inteligencia de licitacoes aos seus sistemas internos e workflows proprietarios." },
  { icon: FileText, title: "Relatorios executivos com IA", description: "Resumos estrategicos prontos para o board. Decisoes baseadas em dados, nao em achismo." },
  { icon: BarChart3, title: "Dashboard consolidado multi-equipe", description: "Visao 360 de todas as oportunidades em andamento com metricas em tempo real." },
  { icon: TrendingUp, title: "Analise preditiva de mercado", description: "Tendencias setoriais com projecoes inteligentes baseadas em 2M+ contratos historicos." },
  { icon: Globe, title: "Dados historicos ilimitados", description: "Acesso completo ao maior acervo de licitacoes e contratos publicos do Brasil." },
  { icon: Headphones, title: "Suporte executive 24/7", description: "Atendimento prioritario com gerente de conta dedicado e SLA garantido." },
  { icon: Building2, title: "Branding institucional", description: "Sua marca em todos os relatorios, exportacoes e apresentacoes para stakeholders." },
];

const COMMAND_FAQ = [
  { question: "O que diferencia o SmartLic Command dos outros planos?", answer: "Command e o tier enterprise do SmartLic, projetado para diretorias, grandes consultorias e departamentos de licitacao que precisam de inteligencia executiva em escala. Inclui API exclusiva, multi-usuario, relatorios com IA para o board, analise preditiva de mercado e suporte dedicado 24/7." },
  { question: "Quantos usuarios podem acessar simultaneamente?", answer: "O SmartLic Command inclui acesso para ate 10 usuarios dedicados com permissoes granulares. Cada membro da equipe pode realizar analises simultaneas sem disputa de cota." },
  { question: "Como funciona a API exclusiva?", answer: "A API do SmartLic Command permite integrar dados de licitacoes e contratos publicos diretamente aos seus sistemas internos, ERPs, CRMs e dashboards proprietarios. Fornecemos documentacao completa e suporte tecnico dedicado para a integracao." },
  { question: "Quais as formas de pagamento?", answer: "Aceitamos cartao de credito e Boleto Bancario. Para o plano Command, tambem oferecemos emissao de nota fiscal e faturamento corporativo sob consulta. Consulte nossa equipe comercial para condicoes especiais." },
  { question: "Posso migrar do SmartLic Pro para o Command?", answer: "Sim. A migracao e feita sem perder dados ou historico de analises. Entre em contato com nosso suporte para realizar a migracao de forma assistida." },
  { question: "Existe contrato de fidelidade?", answer: "Nao. Sem contrato de fidelidade, mesmo no plano anual. Cancele quando quiser e mantenha o acesso ate o fim do periodo ja pago." },
];

export default function CommandLandingPage() {
  const { session } = useAuth();
  const { trackEvent } = useAnalytics();
  const { clarityEvent, claritySet } = useClarity();
  const trackEventRef = useRef(trackEvent);
  trackEventRef.current = trackEvent;
  const [checkoutLoading, setCheckoutLoading] = useState(false);
  const [stripeRedirecting, setStripeRedirecting] = useState(false);
  const [billingPeriod, setBillingPeriod] = useState<BillingPeriod>("annual");
  const [openFaq, setOpenFaq] = useState<number | null>(null);

  useEffect(() => { trackEventRef.current(ANALYTICS.LANDING_VIEWED, { source: "url" }); }, []);

  useEffect(() => {
    const pricing = PRICING[billingPeriod];
    trackViewItem({ id: "command", name: "SmartLic Command", price: pricing.monthly, billing_period: billingPeriod, category: "subscription" });
  }, [billingPeriod]);

  const currentPricing = PRICING[billingPeriod];

  const handleCheckout = useCallback(async () => {
    if (!session) { window.location.href = "/login?redirect=/planos/command"; return; }
    setCheckoutLoading(true);
    trackEvent(ANALYTICS.CHECKOUT_STARTED, { plan_id: "command", billing_period: billingPeriod, source: "command_landing_page" });
    if (typeof window !== "undefined" && (window as any).mixpanel) {
      (window as any).mixpanel.track("plan_selected", { plan_id: "command", billing_period: billingPeriod });
    }
    clarityEvent("checkout_initiated");
    claritySet("selected_plan", "command");
    claritySet("billing_period", billingPeriod);
    trackBeginCheckout({ id: "command", name: "SmartLic Command", price: currentPricing.total, billing_period: billingPeriod, category: "subscription" });
    try {
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "/api";
      const res = await fetch(`${backendUrl}/v1/checkout?plan_id=command&billing_period=${billingPeriod}`, {
        method: "POST", headers: { Authorization: `Bearer ${session.access_token}` },
      });
      if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail || "Erro ao iniciar checkout"); }
      const data = await res.json();
      setStripeRedirecting(true);
      trackEvent(ANALYTICS.CHECKOUT_COMPLETED, { plan_id: "command", billing_period: billingPeriod });
      window.location.href = data.checkout_url;
    } catch (err) {
      trackEvent("checkout_failed", { plan_id: "command", billing_period: billingPeriod, error: err instanceof Error ? err.message : "unknown" });
      toast.error(getUserFriendlyError(err));
      setCheckoutLoading(false); setStripeRedirecting(false);
    }
  }, [session, billingPeriod, currentPricing, trackEvent, clarityEvent, claritySet]);

  return (
    <div className="min-h-screen bg-[var(--canvas)]">
      {stripeRedirecting && (
        <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-[var(--canvas)]/80 backdrop-blur-sm">
          <div role="status" className="backdrop-blur-xl bg-white/70 dark:bg-gray-900/60 border border-white/20 dark:border-white/10 rounded-card p-8 text-center shadow-glass max-w-sm mx-4">
            <div className="w-12 h-12 mx-auto mb-4 border-4 border-[var(--brand-blue)] border-t-transparent rounded-full animate-spin" />
            <h2 className="text-lg font-semibold text-[var(--ink)] mb-2">Redirecionando para o checkout</h2>
            <p className="text-sm text-[var(--ink-secondary)]">Voce sera redirecionado para o Stripe para concluir de forma segura.</p>
          </div>
        </div>
      )}
      <LandingNavbar />

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-[var(--brand-navy)] via-[var(--brand-navy)] to-indigo-950 opacity-[0.03] dark:opacity-[0.08]" />
        <div className="absolute top-0 right-0 w-1/2 h-full bg-gradient-to-l from-[var(--brand-blue)]/5 to-transparent" />
        <div className="max-w-4xl mx-auto pt-20 pb-16 px-4 text-center relative z-10">
          <div className="inline-flex items-center gap-2 rounded-full border border-[var(--brand-navy)]/30 bg-[var(--brand-navy)]/10 px-4 py-1.5 text-sm font-semibold text-[var(--brand-navy)] mb-6">
            <Zap className="w-4 h-4" /><span>SmartLic Command &mdash; Tier Enterprise</span>
          </div>
          <h1 className="text-4xl md:text-6xl font-display font-bold text-[var(--ink)] mb-4 leading-tight">
            O Bloomberg de <span className="text-[var(--brand-blue)]">Compras Publicas</span>
          </h1>
          <p className="text-xl md:text-2xl text-[var(--ink-secondary)] max-w-3xl mx-auto mb-4 font-semibold">
            Inteligencia definitiva para decisoes bilionarias
          </p>
          <p className="text-base text-[var(--ink-muted)] max-w-2xl mx-auto mb-8">
            A plataforma mais avancada do Brasil para diretorias, consultorias e departamentos B2G que exigem inteligencia executiva em licitacoes publicas. Multi-usuario, API exclusiva, relatorios com IA e analise preditiva de mercado.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-8">
            <Button variant="primary" size="lg" className="text-lg font-bold px-8 py-6 h-auto" onClick={handleCheckout} disabled={checkoutLoading} loading={checkoutLoading}>
              {checkoutLoading ? "Processando..." : "Assinar Command"}
            </Button>
            <a href={SUPPORT_WHATSAPP_URL} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 px-6 py-3 rounded-button border border-[var(--border)] text-[var(--ink-secondary)] hover:text-[var(--ink)] hover:bg-[var(--surface-1)] transition-colors font-medium">
              <MessageCircle className="w-5 h-5" />Falar com consultor
            </a>
          </div>
          <div className="flex flex-wrap justify-center gap-x-8 gap-y-2 text-sm text-[var(--ink-muted)]">
            <span className="flex items-center gap-1.5"><Lock className="w-4 h-4 text-[var(--success)]" />Pagamento seguro via Stripe</span>
            <span className="hidden sm:inline text-[var(--border)]">|</span>
            <span className="flex items-center gap-1.5"><Shield className="w-4 h-4 text-[var(--success)]" />Sem contrato de fidelidade</span>
            <span className="hidden sm:inline text-[var(--border)]">|</span>
            <span className="flex items-center gap-1.5"><Check className="w-4 h-4 text-[var(--success)]" />Cancele quando quiser</span>
          </div>
        </div>
      </section>

      {/* Data volume trust strip */}
      <div className="max-w-4xl mx-auto px-4 mb-12">
        <div className="backdrop-blur-md bg-white/60 dark:bg-gray-900/50 border border-white/20 dark:border-white/10 rounded-card p-6">
          <div className="flex flex-wrap justify-center gap-x-10 gap-y-4 text-sm text-[var(--ink-secondary)]">
            <div className="text-center"><p className="text-2xl font-bold text-[var(--brand-navy)]">+2 milhoes</p><p className="text-xs text-[var(--ink-muted)]">contratos publicos monitorados</p></div>
            <div className="text-center"><p className="text-2xl font-bold text-[var(--brand-navy)]">27 estados</p><p className="text-xs text-[var(--ink-muted)]">cobertura nacional em tempo real</p></div>
            <div className="text-center"><p className="text-2xl font-bold text-[var(--brand-navy)]">20 setores</p><p className="text-xs text-[var(--ink-muted)]">classificacao por inteligencia artificial</p></div>
            <div className="text-center"><p className="text-2xl font-bold text-[var(--brand-navy)]">R$ 1k a R$ 500M+</p><p className="text-xs text-[var(--ink-muted)]">faixa de valor analisada</p></div>
          </div>
        </div>
      </div>

      {/* Capabilities */}
      <section className="max-w-5xl mx-auto px-4 mb-16">
        <div className="text-center mb-10">
          <h2 className="text-3xl md:text-4xl font-display font-bold text-[var(--ink)] mb-3">Capacidades Enterprise</h2>
          <p className="text-base text-[var(--ink-secondary)] max-w-2xl mx-auto">Tudo que sua equipe precisa para transformar licitacoes publicas em vantagem competitiva.</p>
        </div>
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
          {COMMAND_CAPABILITIES.map((cap) => { const Icon = cap.icon; return (
            <div key={cap.title} className="backdrop-blur-md bg-white/60 dark:bg-gray-900/50 border border-white/20 dark:border-white/10 rounded-card p-6 hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200">
              <div className="w-10 h-10 rounded-lg bg-[var(--brand-navy)]/10 dark:bg-[var(--brand-navy)]/20 flex items-center justify-center mb-4"><Icon className="w-5 h-5 text-[var(--brand-navy)]" /></div>
              <h3 className="text-base font-semibold text-[var(--ink)] mb-2">{cap.title}</h3>
              <p className="text-sm text-[var(--ink-secondary)] leading-relaxed">{cap.description}</p>
            </div>
          );})}
        </div>
      </section>

      {/* Pricing */}
      <section className="max-w-4xl mx-auto px-4 mb-16">
        <div className="text-center mb-8">
          <h2 className="text-3xl md:text-4xl font-display font-bold text-[var(--ink)] mb-3">Investimento</h2>
          <p className="text-base text-[var(--ink-secondary)]">Escolha o periodo ideal para sua organizacao</p>
        </div>
        <div className="flex justify-center mb-10">
          <PlanToggle value={billingPeriod} onChange={setBillingPeriod} discounts={{ semiannual: PRICING.semiannual.discount, annual: PRICING.annual.discount }} />
        </div>
        <div className="max-w-lg mx-auto">
          <div className="backdrop-blur-xl bg-white/50 dark:bg-gray-900/40 border-2 border-[var(--brand-navy)] rounded-card p-8 shadow-gem-amethyst relative overflow-hidden">
            <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-[var(--brand-navy)] via-[var(--brand-blue)] to-[var(--brand-navy)]" />
            <div className="text-center mb-6">
              <h2 className="text-2xl font-bold text-[var(--ink)]">SmartLic Command</h2>
              <p className="text-sm text-[var(--ink-secondary)]">Inteligencia executiva para decisoes bilionarias</p>
            </div>
            <div className="text-center mb-6">
              <div className="flex items-baseline justify-center gap-1">
                <span className="text-5xl font-bold text-[var(--brand-navy)]">{formatCurrency(currentPricing.monthly)}</span>
                <span className="text-lg text-[var(--ink-muted)]">/mes</span>
              </div>
              {currentPricing.discount && (
                <div className="mt-2 space-y-1">
                  <span className="inline-block px-3 py-1 bg-[var(--success-subtle)] text-[var(--success)] text-sm font-semibold rounded-full">Economize {currentPricing.discount}% | 2 meses gratis no anual</span>
                  {billingPeriod === "semiannual" && <p className="text-xs text-[var(--ink-muted)]">Cobrado {formatCurrency(currentPricing.total)} a cada 6 meses</p>}
                  {billingPeriod === "annual" && <p className="text-xs text-[var(--ink-muted)]">Cobrado {formatCurrency(currentPricing.total)} por ano</p>}
                </div>
              )}
            </div>
            <ul className="space-y-3 mb-8">
              <li className="flex items-start gap-3"><span className="flex-shrink-0 mt-0.5 w-5 h-5 rounded-full bg-[var(--success)] text-white flex items-center justify-center text-xs font-bold">&#10003;</span><div><span className="text-sm font-medium text-[var(--ink)]">Ate 10 usuarios dedicados</span><span className="block text-xs text-[var(--ink-muted)]">Acesso simultaneo sem disputa de cota</span></div></li>
              <li className="flex items-start gap-3"><span className="flex-shrink-0 mt-0.5 w-5 h-5 rounded-full bg-[var(--success)] text-white flex items-center justify-center text-xs font-bold">&#10003;</span><div><span className="text-sm font-medium text-[var(--ink)]">API exclusiva</span><span className="block text-xs text-[var(--ink-muted)]">Integre dados aos seus sistemas</span></div></li>
              <li className="flex items-start gap-3"><span className="flex-shrink-0 mt-0.5 w-5 h-5 rounded-full bg-[var(--success)] text-white flex items-center justify-center text-xs font-bold">&#10003;</span><div><span className="text-sm font-medium text-[var(--ink)]">Relatorios executivos com IA</span><span className="block text-xs text-[var(--ink-muted)]">Resumos prontos para o board</span></div></li>
              <li className="flex items-start gap-3"><span className="flex-shrink-0 mt-0.5 w-5 h-5 rounded-full bg-[var(--success)] text-white flex items-center justify-center text-xs font-bold">&#10003;</span><div><span className="text-sm font-medium text-[var(--ink)]">Analise preditiva de mercado</span><span className="block text-xs text-[var(--ink-muted)]">Tendencias setoriais com IA</span></div></li>
              <li className="flex items-start gap-3"><span className="flex-shrink-0 mt-0.5 w-5 h-5 rounded-full bg-[var(--success)] text-white flex items-center justify-center text-xs font-bold">&#10003;</span><div><span className="text-sm font-medium text-[var(--ink)]">Dashboard multi-equipe</span><span className="block text-xs text-[var(--ink-muted)]">Visao consolidada de todas as oportunidades</span></div></li>
              <li className="flex items-start gap-3"><span className="flex-shrink-0 mt-0.5 w-5 h-5 rounded-full bg-[var(--success)] text-white flex items-center justify-center text-xs font-bold">&#10003;</span><div><span className="text-sm font-medium text-[var(--ink)]">Suporte executive 24/7</span><span className="block text-xs text-[var(--ink-muted)]">Gerente de conta dedicado</span></div></li>
            </ul>
            <Button variant="primary" size="lg" className="w-full text-lg font-bold hover:shadow-lg" onClick={handleCheckout} disabled={checkoutLoading} loading={checkoutLoading}>
              {checkoutLoading ? "Processando..." : "Assinar Command"}
            </Button>
            <p className="mt-3 text-center text-xs text-[var(--ink-muted)]">Cancele quando quiser. Sem contrato de fidelidade. Pagamento seguro via Stripe.</p>
            <div className="mt-4 flex items-center justify-center gap-3 pt-4 border-t border-white/10">
              <svg className="h-5 w-auto text-[var(--ink-muted)]" viewBox="0 0 60 25" fill="currentColor" aria-label="Stripe" role="img"><path d="M5 10.1c0-.7.6-1 1.5-1 1.3 0 3 .4 4.3 1.1V6.3c-1.5-.6-2.9-.8-4.3-.8C3.2 5.5.8 7.4.8 10.3c0 4.5 6.2 3.8 6.2 5.7 0 .8-.7 1.1-1.7 1.1-1.5 0-3.4-.6-4.9-1.4v3.9c1.7.7 3.3 1 4.9 1 3.4 0 5.7-1.7 5.7-4.6-.1-4.9-6.3-4-6.3-5.9zm11.5-4.3L12.3 7v7.7c0 2.8 2.1 4 4.1 4 1.3 0 2.3-.3 2.8-.6V15c-.5.2-2.9.9-2.9-1.3V9h2.9V5.9h-2.9l.2-.1zm6.8 4.8l-.3-1.6h-3.6v13h4.1v-8.8c1-1.3 2.6-1 3.1-.9V5.9c-.6-.2-2.5-.5-3.3 1.7zm4.3-1.7h4.1v13h-4.1zm0-1.6l4.1-.9V2.6l-4.1.9v3.8zm10 .1c-1.5 0-2.5.7-3 1.2l-.2-1h-3.6v17.4l4.1-.9v-4.2c.6.4 1.4 1 2.8 1 2.8 0 5.4-2.3 5.4-7.2-.1-4.6-2.7-7-5.5-7zm-1 10.7c-.9 0-1.5-.3-1.9-.8v-6c.4-.5 1-.8 1.9-.8 1.5 0 2.5 1.7 2.5 3.8 0 2.2-1 3.8-2.5 3.8zm13.8-10.6c-2.4 0-4 2-4 4.3 0 2.8 1.8 4.3 4.3 4.3 1.2 0 2.2-.3 2.9-.7v-3c-.7.4-1.5.6-2.5.6-1 0-1.9-.3-2-1.5h5c0-.1.1-.8.1-1.2-.1-2.5-1.3-4.8-3.8-4.8zm-1.5 3.5c0-1.1.7-1.6 1.3-1.6.7 0 1.3.5 1.3 1.6h-2.6z" /></svg>
              <div className="flex items-center gap-1.5 text-xs text-[var(--ink-muted)]"><svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg><span>Pagamento seguro</span></div>
            </div>
            <div className="mt-3 flex items-center justify-center gap-4 text-xs text-[var(--ink-muted)]">
              <div className="flex items-center gap-1.5"><svg className="w-5 h-3.5" viewBox="0 0 24 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><rect x="1" y="1" width="22" height="14" rx="2" /><line x1="1" y1="6" x2="23" y2="6" /><rect x="3" y="9" width="5" height="2" rx="0.5" fill="currentColor" stroke="none" /></svg><span>Cartao</span></div>
              <div className="flex items-center gap-1.5"><svg className="w-5 h-3.5" viewBox="0 0 24 16" fill="currentColor" aria-hidden="true"><rect x="1" y="1" width="1.5" height="14" /><rect x="4" y="1" width="1" height="14" /><rect x="6.5" y="1" width="2" height="14" /><rect x="10" y="1" width="1" height="14" /><rect x="12.5" y="1" width="1.5" height="14" /><rect x="15.5" y="1" width="1" height="14" /><rect x="18" y="1" width="2" height="14" /><rect x="21.5" y="1" width="1.5" height="14" /></svg><span>Boleto</span></div>
            </div>
          </div>
        </div>
      </section>

      {/* Case Studies */}
      <section className="max-w-4xl mx-auto px-4 mb-16">
        <div className="text-center mb-10">
          <h2 className="text-3xl md:text-4xl font-display font-bold text-[var(--ink)] mb-3">Resultados Reais</h2>
          <p className="text-base text-[var(--ink-secondary)] max-w-2xl mx-auto">Empresas que usam SmartLic para transformar licitacoes publicas em crescimento.</p>
        </div>
        <div className="grid md:grid-cols-2 gap-6">
          <CaseStudyCard sector="Limpeza e Conservacao" location="Curitiba-PR" companySize="12 funcionarios" problem="Monitorava editais manualmente nos portais oficiais 2h por dia" result="Encontrou Pregao Eletronico de R$87.000 (prefeitura vizinha) que nao apareceu na busca manual" highlight={{ value: "R$ 87.000", label: "em oportunidades encontradas", time: "em 6 minutos" }} />
          <CaseStudyCard sector="Insumos de Informatica" location="Porto Alegre-RS" companySize="Distribuidora regional" problem="Perdia editais por descobrir tarde demais" result="Identificou 3 pregoes em municipios do interior com prazo > 10 dias" highlight={{ value: "R$ 245.000", label: "valor total dos 3 editais", time: "identificados no primeiro acesso" }} />
        </div>
        <p className="text-xs text-[var(--ink-secondary)] text-center mt-4 opacity-70">* Cases baseados em dados reais de uso durante periodo de avaliacao. Valores e detalhes aproximados para preservar privacidade.</p>
        <div className="mt-10 backdrop-blur-md bg-white/60 dark:bg-gray-900/50 border border-white/20 dark:border-white/10 rounded-card p-8">
          <h3 className="text-lg font-semibold text-[var(--ink)] text-center mb-6">Por que empresas de alto desempenho escolhem o SmartLic</h3>
          <div className="grid md:grid-cols-3 gap-8 text-center">
            <div><div className="w-12 h-12 rounded-full bg-[var(--brand-blue)]/10 flex items-center justify-center mx-auto mb-3"><Network className="w-6 h-6 text-[var(--brand-blue)]" /></div><p className="text-sm font-medium text-[var(--ink)]">Multiplos usuarios</p><p className="text-xs text-[var(--ink-muted)] mt-1">Equipe inteira trabalhando em sincronia</p></div>
            <div><div className="w-12 h-12 rounded-full bg-[var(--brand-blue)]/10 flex items-center justify-center mx-auto mb-3"><LineChart className="w-6 h-6 text-[var(--brand-blue)]" /></div><p className="text-sm font-medium text-[var(--ink)]">Decisoes baseadas em dados</p><p className="text-xs text-[var(--ink-muted)] mt-1">Relatorios executivos com inteligencia artificial</p></div>
            <div><div className="w-12 h-12 rounded-full bg-[var(--brand-blue)]/10 flex items-center justify-center mx-auto mb-3"><TrendingUp className="w-6 h-6 text-[var(--brand-blue)]" /></div><p className="text-sm font-medium text-[var(--ink)]">Resultado comprovado</p><p className="text-xs text-[var(--ink-muted)] mt-1">Milhares de oportunidades identificadas</p></div>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <div className="max-w-4xl mx-auto px-4 mb-16">
        <PlanFAQ items={COMMAND_FAQ} openIndex={openFaq} onToggle={(i) => setOpenFaq(openFaq === i ? null : i)} />
      </div>

      {/* Final CTA */}
      <section className="max-w-4xl mx-auto px-4 mb-16">
        <div className="backdrop-blur-xl bg-gradient-to-br from-[var(--brand-navy)]/5 to-[var(--brand-blue)]/5 border border-[var(--brand-navy)]/20 rounded-card p-10 text-center">
          <h2 className="text-2xl md:text-3xl font-display font-bold text-[var(--ink)] mb-3">Pronto para decisoes bilionarias?</h2>
          <p className="text-base text-[var(--ink-secondary)] max-w-xl mx-auto mb-6">Junte-se as empresas que ja usam o SmartLic para transformar licitacoes publicas em vantagem competitiva.</p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Button variant="primary" size="lg" className="text-lg font-bold px-8 py-6 h-auto" onClick={handleCheckout} disabled={checkoutLoading} loading={checkoutLoading}>
              {checkoutLoading ? "Processando..." : "Assinar Command"}
            </Button>
            <a href={SUPPORT_WHATSAPP_URL} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 px-6 py-3 rounded-button border border-[var(--border)] text-[var(--ink-secondary)] hover:text-[var(--ink)] hover:bg-[var(--surface-1)] transition-colors font-medium">
              <MessageCircle className="w-5 h-5" />Falar com consultor
            </a>
          </div>
        </div>
      </section>

      {/* Contact */}
      <div className="max-w-4xl mx-auto px-4 mb-8">
        <div className="border-t border-gray-200 dark:border-gray-700" />
        <div className="py-8 text-center">
          <p className="text-lg font-semibold text-[var(--ink)] mb-4">Precisa de mais informacoes?</p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 sm:gap-8">
            <a href={SUPPORT_WHATSAPP_URL} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 text-[var(--ink-secondary)] hover:text-[var(--brand-blue)] transition-colors"><MessageCircle className="w-5 h-5" /><span className="font-medium">Fale conosco</span></a>
            <a href="mailto:tiago.sasaki@confenge.com.br" target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 text-[var(--ink-secondary)] hover:text-[var(--brand-blue)] transition-colors"><Mail className="w-5 h-5" /><span className="font-medium">tiago.sasaki@confenge.com.br</span></a>
          </div>
        </div>
        <div className="border-t border-gray-200 dark:border-gray-700" />
      </div>

      {/* Back link */}
      <div className="max-w-4xl mx-auto px-4 pb-12 text-center">
        <Link href="/planos" className={buttonVariants({ variant: "link", size: "sm", className: "text-[var(--ink-muted)]" })}>Ver todos os planos</Link>
      </div>
    </div>
  );
}
