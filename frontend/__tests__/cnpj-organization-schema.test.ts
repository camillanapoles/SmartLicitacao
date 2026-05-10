/**
 * #996 SEO-P2-009 — Organization JSON-LD validation for /cnpj/[cnpj] entity profiles.
 *
 * Validates the Schema.org Organization fields required for Knowledge Panel signals
 * and SERP differentiation against directory competitors (cnpj.biz, cnpja.com).
 */

import { buildOrgSchema, formatCnpjMask, type PerfilB2GLite } from '@/app/cnpj/[cnpj]/_jsonld';

const BASE_PERFIL: PerfilB2GLite = {
  empresa: {
    razao_social: 'Empresa Teste LTDA',
    cnpj: '09225035000101',
    cnae_principal: '4781-4/00',
    porte: 'ME',
    uf: 'SP',
    situacao: 'ATIVA',
  },
  setor_nome: 'Vestuário e Têxtil',
  total_contratos_24m: 7,
  valor_total_24m: 850_000,
  ufs_atuacao: ['SP', 'RJ'],
};

describe('buildOrgSchema (#996 SEO-P2-009)', () => {
  it('returns a Schema.org Organization with @context and @type', () => {
    const schema = buildOrgSchema(BASE_PERFIL);
    expect(schema['@context']).toBe('https://schema.org');
    expect(schema['@type']).toBe('Organization');
  });

  it('emits @id, name, legalName, and url for entity disambiguation', () => {
    const schema = buildOrgSchema(BASE_PERFIL);
    expect(schema['@id']).toBe('https://smartlic.tech/cnpj/09225035000101#organization');
    expect(schema.name).toBe('Empresa Teste LTDA');
    expect(schema.legalName).toBe('Empresa Teste LTDA');
    expect(schema.url).toBe('https://smartlic.tech/cnpj/09225035000101');
  });

  it('formats taxID with the canonical CNPJ mask', () => {
    const schema = buildOrgSchema(BASE_PERFIL);
    expect(schema.taxID).toBe('09.225.035/0001-01');
  });

  it('exposes raw CNPJ + CNAE via identifier PropertyValue array', () => {
    const schema = buildOrgSchema(BASE_PERFIL);
    expect(schema.identifier).toEqual([
      { '@type': 'PropertyValue', propertyID: 'CNPJ', value: '09225035000101' },
      { '@type': 'PropertyValue', propertyID: 'CNAE', value: '4781-4/00' },
    ]);
  });

  it('emits PostalAddress with addressRegion (UF) and addressCountry=BR', () => {
    const schema = buildOrgSchema(BASE_PERFIL);
    expect(schema.address).toEqual({
      '@type': 'PostalAddress',
      addressRegion: 'SP',
      addressCountry: 'BR',
    });
  });

  it('builds sameAs with Receita Federal + LinkedIn search URLs', () => {
    const schema = buildOrgSchema(BASE_PERFIL);
    const sameAs = schema.sameAs as string[];
    expect(sameAs).toHaveLength(2);
    expect(sameAs[0]).toContain('servicos.receita.fazenda.gov.br');
    expect(sameAs[0]).toContain('09225035000101');
    expect(sameAs[1]).toContain('linkedin.com/search/results/companies');
    expect(sameAs[1]).toContain(encodeURIComponent('Empresa Teste LTDA'));
  });

  it('writes a contract-history-rich description when total_contratos_24m > 0', () => {
    const schema = buildOrgSchema(BASE_PERFIL);
    const description = schema.description as string;
    expect(description).toContain('Empresa Teste LTDA');
    expect(description).toContain('09.225.035/0001-01');
    expect(description).toContain('7 contratos');
    expect(description).toContain('Vestuário e Têxtil');
    // BRL currency format may use NBSP or regular space depending on Node ICU build
    expect(description).toMatch(/R\$[\s ]?850\.000/);
  });

  it('writes a fallback description when total_contratos_24m == 0', () => {
    const schema = buildOrgSchema({
      ...BASE_PERFIL,
      total_contratos_24m: 0,
      valor_total_24m: 0,
      ufs_atuacao: [],
    });
    const description = schema.description as string;
    expect(description).toContain('Sem histórico de contratos públicos');
    expect(description).toContain('Vestuário e Têxtil');
  });

  it('emits knowsAbout with the SmartLic sector name', () => {
    const schema = buildOrgSchema(BASE_PERFIL);
    expect(schema.knowsAbout).toBe('Vestuário e Têxtil');
  });

  it('maps porte to size when present', () => {
    const schema = buildOrgSchema(BASE_PERFIL);
    expect(schema.size).toBe('ME');
  });

  it('omits size when porte is empty string', () => {
    const schema = buildOrgSchema({
      ...BASE_PERFIL,
      empresa: { ...BASE_PERFIL.empresa, porte: '' },
    });
    expect(schema.size).toBeUndefined();
  });

  it('emits areaServed as AdministrativeArea[] from ufs_atuacao', () => {
    const schema = buildOrgSchema(BASE_PERFIL);
    expect(schema.areaServed).toEqual([
      { '@type': 'AdministrativeArea', name: 'SP', addressCountry: 'BR' },
      { '@type': 'AdministrativeArea', name: 'RJ', addressCountry: 'BR' },
    ]);
  });

  it('omits areaServed when ufs_atuacao is empty', () => {
    const schema = buildOrgSchema({ ...BASE_PERFIL, ufs_atuacao: [] });
    expect(schema.areaServed).toBeUndefined();
  });

  it('emits interactionStatistic for crawler-readable contract count', () => {
    const schema = buildOrgSchema(BASE_PERFIL);
    expect(schema.interactionStatistic).toEqual({
      '@type': 'InteractionCounter',
      interactionType: { '@type': 'SellAction', name: 'Contratos Públicos (24 meses)' },
      userInteractionCount: 7,
    });
  });

  it('omits interactionStatistic when there are no contracts', () => {
    const schema = buildOrgSchema({
      ...BASE_PERFIL,
      total_contratos_24m: 0,
      valor_total_24m: 0,
    });
    expect(schema.interactionStatistic).toBeUndefined();
  });

  it('produces JSON-serializable output (round-trip preserves shape)', () => {
    const schema = buildOrgSchema(BASE_PERFIL);
    const json = JSON.stringify(schema);
    const parsed = JSON.parse(json);
    expect(parsed['@type']).toBe('Organization');
    expect(parsed.taxID).toBe('09.225.035/0001-01');
  });
});

describe('formatCnpjMask', () => {
  it('formats a 14-digit CNPJ with the canonical mask', () => {
    expect(formatCnpjMask('09225035000101')).toBe('09.225.035/0001-01');
  });

  it('returns the raw input when length != 14', () => {
    expect(formatCnpjMask('123')).toBe('123');
    expect(formatCnpjMask('')).toBe('');
  });
});
