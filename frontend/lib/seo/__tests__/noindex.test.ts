/**
 * Tests for lib/seo/noindex.ts (SEO-P0-003 #989).
 *
 * Mocks the auto-generated `noindex-slugs.ts` to a deterministic fixture so
 * we can exercise the `isNoindexed`, `noindexKey`, `filterNoindexedSitemap`
 * helpers without depending on whatever the latest audit produced.
 */

jest.mock('../noindex-slugs', () => ({
  __esModule: true,
  NOINDEX_SLUGS: new Set([
    'cnpj:/cnpj/12345678000199',
    'fornecedores-cnpj:/fornecedores/00000000000191',
    'blog-licitacoes-setor-uf:/blog/licitacoes/saude/SP',
  ]),
}));

import {
  filterNoindexedSitemap,
  isNoindexed,
  noindexKey,
} from '../noindex';

describe('noindexKey', () => {
  it('joins family and path with colon', () => {
    expect(noindexKey('cnpj', '/cnpj/123')).toBe('cnpj:/cnpj/123');
  });

  it('strips trailing slash', () => {
    expect(noindexKey('cnpj', '/cnpj/123/')).toBe('cnpj:/cnpj/123');
  });

  it('preserves leading slash', () => {
    expect(noindexKey('cnpj', '/cnpj/123')).toBe('cnpj:/cnpj/123');
  });

  it('adds leading slash when missing', () => {
    expect(noindexKey('cnpj', 'cnpj/123')).toBe('cnpj:/cnpj/123');
  });

  it('does not strip the root slash itself', () => {
    expect(noindexKey('cnpj', '/')).toBe('cnpj:/');
  });
});

describe('isNoindexed', () => {
  it('returns true for slugs in the set', () => {
    expect(isNoindexed('cnpj', '/cnpj/12345678000199')).toBe(true);
    expect(isNoindexed('fornecedores-cnpj', '/fornecedores/00000000000191')).toBe(true);
    expect(isNoindexed('blog-licitacoes-setor-uf', '/blog/licitacoes/saude/SP')).toBe(true);
  });

  it('returns false for slugs not in the set', () => {
    expect(isNoindexed('cnpj', '/cnpj/99999999000199')).toBe(false);
  });

  it('returns false when family does not match', () => {
    // Same path, wrong family -> different key -> not in set.
    expect(isNoindexed('orgaos', '/cnpj/12345678000199')).toBe(false);
  });

  it('normalizes trailing slash', () => {
    expect(isNoindexed('cnpj', '/cnpj/12345678000199/')).toBe(true);
  });
});

describe('filterNoindexedSitemap', () => {
  it('drops entries flagged for the given family', () => {
    const entries = [
      { url: 'https://smartlic.tech/cnpj/12345678000199', priority: 0.5 },
      { url: 'https://smartlic.tech/cnpj/99999999000199', priority: 0.5 },
    ];
    const out = filterNoindexedSitemap(entries, 'cnpj');
    expect(out.map((e) => e.url)).toEqual([
      'https://smartlic.tech/cnpj/99999999000199',
    ]);
  });

  it('keeps everything when family does not overlap', () => {
    const entries = [
      { url: 'https://smartlic.tech/orgaos/12345678000199' },
      { url: 'https://smartlic.tech/orgaos/22222222000222' },
    ];
    expect(filterNoindexedSitemap(entries, 'orgaos')).toHaveLength(2);
  });

  it('handles malformed URLs gracefully (keeps them)', () => {
    const entries = [{ url: 'not-a-url' }];
    expect(filterNoindexedSitemap(entries, 'cnpj')).toHaveLength(1);
  });

  it('is a no-op when called against a family whose slugs are not in the set', () => {
    // Same mocked set as the suite (3 slugs, none for `municipios`). Caller
    // doesn't lose data when nothing matches.
    const entries = [
      { url: 'https://smartlic.tech/municipios/sao-paulo' },
      { url: 'https://smartlic.tech/municipios/rio' },
    ];
    expect(filterNoindexedSitemap(entries, 'municipios')).toEqual(entries);
  });
});
