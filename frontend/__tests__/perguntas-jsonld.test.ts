/**
 * #991 — JSON-LD schema migration for /perguntas/[slug].
 *
 * Google deprecated FAQ rich results in May/2026 for non-gov/health sites,
 * so QAPage-only emission no longer surfaces in SERP. We migrate to
 * Article + BreadcrumbList (always) + HowTo (when slug starts with "como-"
 * or contains "passo-a-passo"), keeping QAPage as secondary for AI
 * Overviews ingestion.
 *
 * These tests exercise the pure JSON-LD builders directly — they assert
 * shape/contract, not React rendering, so they stay fast and deterministic
 * across our 53 question pages.
 */

import {
  buildPersonAuthorLd,
  buildArticleLd,
  buildBreadcrumbLd,
  buildQaPageLd,
  buildHowToLd,
  isHowToEligible,
  extractHowToSteps,
} from '@/app/perguntas/[slug]/json-ld';
import { getQuestionBySlug } from '@/lib/questions';

const PUBLISHED_AT = '2025-09-01';
const UPDATED_AT = '2026-05-10';

describe('isHowToEligible', () => {
  it('returns true for slugs starting with "como-"', () => {
    expect(isHowToEligible('como-calcular-preco-proposta-licitacao')).toBe(true);
  });

  it('returns true for slugs containing "passo-a-passo"', () => {
    expect(isHowToEligible('concorrencia-eletronica-passo-a-passo')).toBe(true);
  });

  it('returns false for definitional slugs', () => {
    expect(isHowToEligible('qualificacao-tecnica-lei-14133')).toBe(false);
    expect(isHowToEligible('prazo-publicacao-edital')).toBe(false);
  });
});

describe('extractHowToSteps', () => {
  it('extracts bold-numbered headings (**1. Title:**) into ordered steps', () => {
    const answer =
      '**1. Identificação:**\nMonitore o PNCP.\n\n' +
      '**2. Análise:**\nLeia o edital.\n\n' +
      '**3. Documentação:**\nReuna os documentos.\n\n' +
      '**4. Proposta:**\nFormule a proposta.';
    const steps = extractHowToSteps(answer);
    expect(steps).not.toBeNull();
    expect(steps).toHaveLength(4);
    expect(steps![0].name).toBe('Identificação');
    expect(steps![0].text).toContain('PNCP');
  });

  it('returns null when fewer than 3 numbered steps are detectable', () => {
    expect(extractHowToSteps('Texto puro sem estrutura.')).toBeNull();
    expect(extractHowToSteps('**1. Apenas um:**\nUm passo só.')).toBeNull();
  });

  it('strips markdown bold markers from extracted step text', () => {
    const answer =
      '**1. Primeiro:**\nUse o **PNCP** para buscar.\n\n' +
      '**2. Segundo:**\nLeia o **edital** com atenção.\n\n' +
      '**3. Terceiro:**\nEnvie a **proposta**.';
    const steps = extractHowToSteps(answer);
    expect(steps).not.toBeNull();
    expect(steps![0].text).not.toContain('**');
    expect(steps![1].text).not.toContain('**');
  });
});

describe('buildHowToLd', () => {
  it('emits a valid HowTo schema with positioned steps and pt-BR locale', () => {
    const question = getQuestionBySlug('como-calcular-preco-proposta-licitacao');
    expect(question).toBeDefined();
    const steps = extractHowToSteps(question!.answer);
    expect(steps).not.toBeNull();

    const ld = buildHowToLd(question!, question!.slug, steps!);
    expect(ld['@context']).toBe('https://schema.org');
    expect(ld['@type']).toBe('HowTo');
    expect(ld.name).toBe(question!.title);
    expect(ld.inLanguage).toBe('pt-BR');
    expect(ld.mainEntityOfPage['@id']).toContain('/perguntas/como-calcular-preco-proposta-licitacao');
    expect(Array.isArray(ld.step)).toBe(true);
    expect(ld.step.length).toBe(8);
    ld.step.forEach((step, i) => {
      expect(step['@type']).toBe('HowToStep');
      expect(step.position).toBe(i + 1);
      expect(typeof step.name).toBe('string');
      expect(typeof step.text).toBe('string');
    });
  });
});

describe('Article + BreadcrumbList always-present (sample slugs)', () => {
  const orgAuthor = buildPersonAuthorLd(undefined);

  it.each([
    'como-calcular-preco-proposta-licitacao',
    'qualificacao-tecnica-lei-14133',
    'prazo-publicacao-edital',
  ])('emits Article + BreadcrumbList + QAPage for "%s"', (slug) => {
    const question = getQuestionBySlug(slug);
    expect(question).toBeDefined();

    const articleLd = buildArticleLd(question!, slug, orgAuthor, PUBLISHED_AT, UPDATED_AT);
    expect(articleLd['@type']).toBe('Article');
    expect(articleLd.headline).toBe(question!.title);
    expect(articleLd.author).toBeDefined();
    expect(articleLd.publisher).toBeDefined();
    expect(articleLd.datePublished).toBe(PUBLISHED_AT);
    expect(articleLd.dateModified).toBe(UPDATED_AT);
    expect(articleLd.inLanguage).toBe('pt-BR');

    const breadcrumbLd = buildBreadcrumbLd(question!, slug);
    expect(breadcrumbLd['@type']).toBe('BreadcrumbList');
    expect(breadcrumbLd.itemListElement).toHaveLength(3);
    expect(breadcrumbLd.itemListElement[2].item).toContain(`/perguntas/${slug}`);

    // QAPage retained as secondary for AI Overviews (regression check).
    const qaLd = buildQaPageLd(question!, 'plain', orgAuthor);
    expect(qaLd['@type']).toBe('QAPage');
    expect(qaLd.mainEntity['@type']).toBe('Question');
  });
});

describe('HowTo conditional emission (sample slugs)', () => {
  it('emits HowTo for "como-*" slug with extractable steps', () => {
    const slug = 'como-calcular-preco-proposta-licitacao';
    const question = getQuestionBySlug(slug);
    expect(question).toBeDefined();
    expect(isHowToEligible(slug)).toBe(true);
    const steps = extractHowToSteps(question!.answer);
    // This particular question is procedural and has a "Passo a passo:" block
    // with exactly 8 procedure steps — extraction must be scoped to that block
    // only (not mixing the 7-item "Estrutura básica" cost-categories list).
    expect(steps).not.toBeNull();
    expect(steps!.length).toBe(8);
  });

  it('does NOT emit HowTo for definitional "qualificacao-*" slug', () => {
    const slug = 'qualificacao-tecnica-lei-14133';
    expect(isHowToEligible(slug)).toBe(false);
  });

  it('does NOT emit HowTo for "prazo-*" slug', () => {
    const slug = 'prazo-publicacao-edital';
    expect(isHowToEligible(slug)).toBe(false);
  });
});
