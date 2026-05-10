/**
 * Root layout metadata invariants (issues #990 + #988).
 *
 * SEO-P0-004 (#990): Global canonical default in layout.tsx.
 * SEO-P0-001 (#988): hreflang pt-BR + geo-target meta tags for HCU classifier.
 *
 * We assert against the source text of `frontend/app/layout.tsx` so the test
 * stays decoupled from runtime imports (the layout module pulls in many
 * providers + CSS which would otherwise need extensive mocking). The contract
 * we want to lock down is the *metadata declaration*, which is static.
 */
import { readFileSync } from 'fs';
import { join } from 'path';

const LAYOUT_PATH = join(__dirname, '..', '..', 'app', 'layout.tsx');
const SOURCE = readFileSync(LAYOUT_PATH, 'utf-8');

describe('Root layout metadata — SEO-P0 invariants', () => {
  describe('SEO-P0-004 (#990) — global canonical default', () => {
    it('declares metadataBase pointing to smartlic.tech', () => {
      expect(SOURCE).toMatch(/metadataBase:\s*new URL\([^)]*smartlic\.tech/);
    });

    it('declares alternates.canonical as relative "/" so per-page generateMetadata can override', () => {
      // The default MUST be relative so that route-level `generateMetadata`
      // returning a route-specific canonical takes precedence (Next.js merges
      // metadata top-down; absolute strings at the root would also override
      // but relative '/' keeps the contract explicit + portable across envs).
      expect(SOURCE).toMatch(/alternates:\s*\{[^}]*canonical:\s*['"]\/['"]/);
    });
  });

  describe('SEO-P0-001 (#988) — hreflang pt-BR + geo-target', () => {
    it('declares hreflang pt-BR in alternates.languages', () => {
      expect(SOURCE).toMatch(/['"]pt-BR['"]:\s*['"]/);
    });

    it('declares hreflang x-default fallback', () => {
      expect(SOURCE).toMatch(/['"]x-default['"]:\s*['"]/);
    });

    it('renders <html lang="pt-BR"> for the document', () => {
      expect(SOURCE).toMatch(/<html\s+lang="pt-BR"/);
    });

    it('emits <meta name="content-language" content="pt-BR">', () => {
      expect(SOURCE).toMatch(/<meta\s+name="content-language"\s+content="pt-BR"/);
    });

    it('emits <meta name="geo.region" content="BR"> for geo-targeting', () => {
      expect(SOURCE).toMatch(/<meta\s+name="geo\.region"\s+content="BR"/);
    });

    it('emits <meta name="geo.country" content="Brazil">', () => {
      expect(SOURCE).toMatch(/<meta\s+name="geo\.country"\s+content="Brazil"/);
    });

    it('emits <meta httpEquiv="Content-Language" content="pt-BR"> as legacy fallback', () => {
      expect(SOURCE).toMatch(/<meta\s+httpEquiv="Content-Language"\s+content="pt-BR"/);
    });
  });
});
