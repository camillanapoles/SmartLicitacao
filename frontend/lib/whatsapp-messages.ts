/**
 * CONV-013: Centralized WhatsApp message builder per source template.
 *
 * Builds a context-aware pre-filled message for the founder's WhatsApp link.
 * The phone number is always +55 48 98834-4559 (founder direct line).
 *
 * Usage:
 *   import { buildWhatsAppUrl } from '@/lib/whatsapp-messages';
 *   const url = buildWhatsAppUrl('fornecedor_page', {
 *     entity: 'Empresa XYZ Ltda',
 *     setor: 'pavimentacao-asfaltica',
 *     uf: 'SC',
 *   });
 */

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const FOUNDER_PHONE = '5548988344559';
const WHATSAPP_BASE = `https://wa.me/${FOUNDER_PHONE}`;
const FALLBACK_MESSAGE = 'Olá! Vim do SmartLic e quero saber mais sobre como vocês podem ajudar minha empresa a ganhar licitações públicas.';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type WhatsAppSourceTemplate =
  | 'fornecedor_page'
  | 'orgao_page'
  | 'licitacoes_page'
  | 'cnpj_page'
  | 'blog_licitacoes_page';

export interface WhatsAppContext {
  /** Entity name or label (e.g. company name, orgao name, sector name) */
  entity?: string;
  /** Sector slug (e.g. 'pavimentacao-asfaltica') */
  setor?: string;
  /** Two-letter UF code (e.g. 'SC') */
  uf?: string;
}

// ---------------------------------------------------------------------------
// Message builders per source template
// ---------------------------------------------------------------------------

function buildFornecedorMessage(entity?: string, setor?: string, uf?: string): string {
  const entityLabel = entity || 'este fornecedor';
  const contextParts: string[] = ['quero analisar esta empresa'];
  if (uf) contextParts.push(`em ${uf}`);
  if (setor) contextParts.push(`no setor de ${setor.replace(/-/g, ' ')}`);
  return `Olá! Vim da página de fornecedor ${entityLabel} e ${contextParts.join(' ')}`;
}

function buildOrgaoMessage(entity?: string, setor?: string, uf?: string): string {
  const entityLabel = entity || 'este órgão';
  const contextParts: string[] = ['quero monitorar este órgão'];
  if (uf) contextParts.push(`no ${uf}`);
  return `Olá! Vim da página do órgão ${entityLabel} e ${contextParts.join(' ')}`;
}

function buildLicitacoesMessage(entity?: string, setor?: string, uf?: string): string {
  const setorLabel = entity || (setor ? setor.replace(/-/g, ' ') : 'este setor');
  const contextParts: string[] = ['quero oportunidades neste setor'];
  if (uf) contextParts.push(`no ${uf}`);
  return `Olá! Vim da página de licitações de ${setorLabel} e ${contextParts.join(' ')}`;
}

function buildCnpjMessage(entity?: string, setor?: string, uf?: string): string {
  const entityLabel = entity || 'esta empresa';
  const contextParts: string[] = ['quero relatório desta empresa'];
  if (uf) contextParts.push(`em ${uf}`);
  if (setor) contextParts.push(`no setor de ${setor.replace(/-/g, ' ')}`);
  return `Olá! Vim da página de consulta CNPJ de ${entityLabel} e ${contextParts.join(' ')}`;
}

function buildBlogLicitacoesMessage(entity?: string, setor?: string, uf?: string): string {
  const setorLabel = entity || (setor ? setor.replace(/-/g, ' ') : 'este setor');
  const locationLabel = uf ? `em ${uf}` : 'nesta região';
  return `Olá! Vim da página de licitações de ${setorLabel} ${locationLabel} e quero editais nesta região`;
}

// ---------------------------------------------------------------------------
// Message builder map
// ---------------------------------------------------------------------------

const MESSAGE_BUILDERS: Record<WhatsAppSourceTemplate, (entity?: string, setor?: string, uf?: string) => string> = {
  fornecedor_page: buildFornecedorMessage,
  orgao_page: buildOrgaoMessage,
  licitacoes_page: buildLicitacoesMessage,
  cnpj_page: buildCnpjMessage,
  blog_licitacoes_page: buildBlogLicitacoesMessage,
};

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Build a WhatsApp deep link with a pre-filled contextual message.
 *
 * @param source - The source template identifier
 * @param ctx - Contextual information (entity name, setor, uf)
 * @returns A `https://wa.me/...` URL with the message URL-encoded
 */
export function buildWhatsAppUrl(
  source: WhatsAppSourceTemplate,
  ctx: WhatsAppContext,
): string {
  const builder = MESSAGE_BUILDERS[source];
  const message = builder
    ? builder(ctx.entity, ctx.setor, ctx.uf)
    : FALLBACK_MESSAGE;
  return `${WHATSAPP_BASE}?text=${encodeURIComponent(message)}`;
}

/**
 * Get the human-readable label for a WhatsApp CTA button.
 * Used to display "Falar com especialista no WhatsApp" on all CTAs.
 */
export function getWhatsAppCtaLabel(): string {
  return 'Falar com especialista no WhatsApp';
}
