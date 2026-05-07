'use client';

import React from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { GradientButton } from '@/app/components/ui/GradientButton';
import { useScrollAnimation } from '@/lib/animations';
import { fadeInUp, staggerContainer } from '@/lib/animations';
import { hero } from '@/lib/copy/valueProps';

interface HeroSectionProps {
  className?: string;
}

const HERO_SCREENSHOT_BLUR =
  'data:image/webp;base64,UklGRk4AAABXRUJQVlA4IEIAAADQAgCdASoUAA0ALvmczmclLy8vDwD4SzgGWWK505WAAP7wLrgqjz50IhRgDbeGwhDdH55pOuyAD9i3oi0FuVjIAAA=';

/**
 * STORY-174 AC1: Hero Section Redesign - Premium SaaS Aesthetic
 * SAB-006 AC2/AC5: Removed stats badges (consolidated into StatsSection), CTA above fold
 * DEBT-125: 50/50 layout with annotated product screenshot
 * REPO-006: Copymasters consensus v1 — B2G intelligence positioning
 * REPO-007: Founding disclaimer below CTAs
 */
export default function HeroSection({ className = '' }: HeroSectionProps) {
  const { ref, isVisible } = useScrollAnimation(0.1);

  return (
    <section
      ref={ref}
      className={`
        relative
        max-w-landing
        mx-auto
        px-4 sm:px-6 lg:px-8
        py-16 sm:py-24
        overflow-hidden
        ${className}
      `}
    >
      {/* Background gradient mesh */}
      {/* eslint-disable-next-line local-rules/no-inline-styles -- DYNAMIC: radial-gradient uses CSS custom properties (--brand-blue-subtle) not expressible in Tailwind */}
      <div
        className="absolute inset-0 -z-10 opacity-40"
        style={{
          background: `
            radial-gradient(circle at 20% 50%, var(--brand-blue-subtle) 0%, transparent 50%),
            radial-gradient(circle at 80% 20%, var(--brand-blue-subtle) 0%, transparent 40%)
          `,
        }}
      />

      {/* DEBT-125: 50/50 layout — text left, screenshot right (desktop) / stacked (mobile) */}
      <motion.div
        className="flex flex-col lg:flex-row items-center gap-12 lg:gap-16"
        variants={staggerContainer}
        initial="hidden"
        animate={isVisible ? 'visible' : 'hidden'}
      >
        {/* Left column — text content */}
        <div className="flex-1 text-center lg:text-left max-w-xl lg:max-w-none">
          {/* Headline with gradient text */}
          <motion.h1
            className="
              text-4xl sm:text-5xl lg:text-6xl
              font-display
              font-black
              tracking-tighter
              leading-[1.1]
            "
            variants={fadeInUp}
          >
            <span className="text-ink">
              Decisão comercial em licitação não nasce de PDF.
            </span>
            <br />
            <span className="text-gradient">
              Nasce de inteligência.
            </span>
          </motion.h1>

          {/* Subheadline */}
          <motion.p
            className="
              text-lg sm:text-xl
              text-ink-secondary
              mt-6
              font-medium
              leading-relaxed
              max-w-2xl
              lg:max-w-lg
            "
            variants={fadeInUp}
          >
            SmartLic lê o edital, mapeia o concorrente, calcula a chance real. Sua empresa decide go/no-go em minutos — não em três dias de leitura.
          </motion.p>

          {/* CTA Buttons — AC5: Primary CTA visible above the fold */}
          <motion.div
            className="flex flex-col sm:flex-row items-center lg:items-start justify-center lg:justify-start gap-4 mt-10"
            variants={fadeInUp}
          >
            <Link href="/signup?source=hero-primary" data-testid="hero-cta-primary">
              <GradientButton
                variant="primary"
                size="lg"
                glow={true}
              >
                Testar plataforma
              </GradientButton>
            </Link>

            <Link href="/consultoria-b2g#diagnostico" data-testid="hero-cta-secondary">
              <GradientButton
                variant="secondary"
                size="lg"
                glow={false}
              >
                Solicitar diagnóstico B2G
              </GradientButton>
            </Link>
          </motion.div>

          {/* REPO-007: Founding disclaimer — below CTAs, non-competitive */}
          <motion.p
            className="text-sm text-zinc-400 dark:text-zinc-500 max-w-md mx-auto lg:mx-0 text-center lg:text-left mt-4"
            variants={fadeInUp}
          >
            {hero.disclaimer}
          </motion.p>

          {/* Trust indicators */}
          <motion.div
            className="mt-6 flex flex-wrap items-center justify-center lg:justify-start gap-x-6 gap-y-2 text-xs text-ink-muted"
            variants={fadeInUp}
          >
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              Fontes oficiais verificadas
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              Critérios objetivos, não opinião
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              Sem dados fabricados
            </span>
          </motion.div>
        </div>

        {/* Right column — annotated product screenshot (DEBT-125 AC1-AC8) */}
        <motion.div
          className="flex-1 w-full lg:w-auto"
          variants={fadeInUp}
        >
          <div className="relative w-full max-w-2xl mx-auto lg:mx-0">
            {/* Browser chrome frame */}
            <div className="rounded-xl overflow-hidden shadow-xl ring-1 ring-black/5 dark:ring-white/10 dark:shadow-2xl">
              {/* Browser bar */}
              <div className="flex items-center gap-2 px-4 py-2.5 bg-gray-100 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
                <div className="flex gap-1.5">
                  <span className="w-3 h-3 rounded-full bg-red-400" />
                  <span className="w-3 h-3 rounded-full bg-yellow-400" />
                  <span className="w-3 h-3 rounded-full bg-green-400" />
                </div>
                <div className="flex-1 mx-4">
                  <div className="bg-white dark:bg-gray-700 rounded-md px-3 py-1 text-xs text-gray-500 dark:text-gray-400 text-center truncate">
                    smartlic.tech/buscar
                  </div>
                </div>
              </div>

              {/* Screenshot image — AC5: priority for LCP, AC6: descriptive alt, AC8: dark mode filter */}
              <Image
                src="/images/hero-screenshot.webp"
                alt="Tela de resultados do SmartLic mostrando classificacao por IA e analise de viabilidade"
                width={1280}
                height={800}
                priority={true}
                sizes="(max-width: 1024px) 100vw, 50vw"
                placeholder="blur"
                blurDataURL={HERO_SCREENSHOT_BLUR}
                className="w-full h-auto dark:brightness-[0.85] dark:contrast-[1.1]"
              />
            </div>
          </div>
        </motion.div>
      </motion.div>
    </section>
  );
}
