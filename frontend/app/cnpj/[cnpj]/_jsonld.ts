/**
 * #996 SEO-P2-009 — JSON-LD builders for /cnpj/[cnpj] entity profile pages.
 *
 * Organization schema enriched with SmartLic-exclusive data (contract history,
 * sector classification, areas served) so CNPJ pages compete with directory
 * sites (cnpj.biz, cnpja.com) on entity richness and Knowledge Panel signals.
 *
 * Backend payload: PerfilB2G from `/v1/empresa/{cnpj}/perfil-b2g`. Fields not
 * yet supplied (foundingDate, municipio, full streetAddress, naics) are
 * intentionally omitted — adding them is a backend follow-up.
 */

export interface PerfilEmpresa {
  razao_social: string;
  cnpj: string;
  cnae_principal: string;
  porte: string;
  uf: string;
  situacao: string;
}

export interface PerfilB2GLite {
  empresa: PerfilEmpresa;
  setor_nome: string;
  total_contratos_24m: number;
  valor_total_24m: number;
  ufs_atuacao: string[];
}

export function formatCnpjMask(raw: string): string {
  if (raw.length !== 14) return raw;
  return `${raw.slice(0, 2)}.${raw.slice(2, 5)}.${raw.slice(5, 8)}/${raw.slice(8, 12)}-${raw.slice(12)}`;
}

export function buildOrgSchema(perfil: PerfilB2GLite): Record<string, unknown> {
  const { empresa, setor_nome, total_contratos_24m, valor_total_24m, ufs_atuacao } = perfil;

  const cnpjFormatted = formatCnpjMask(empresa.cnpj);
  const valorTotalBRL = new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    minimumFractionDigits: 0,
  }).format(valor_total_24m);

  // sameAs: external authoritative references for entity disambiguation (Knowledge Panel signals).
  const sameAs = [
    `https://servicos.receita.fazenda.gov.br/Servicos/cnpjreva/Cnpjreva_Solicitacao.asp?cnpj=${empresa.cnpj}`,
    `https://www.linkedin.com/search/results/companies/?keywords=${encodeURIComponent(empresa.razao_social)}`,
  ];

  const description =
    total_contratos_24m > 0
      ? `${empresa.razao_social} (CNPJ ${cnpjFormatted}) firmou ${total_contratos_24m} contratos públicos nos últimos 24 meses, totalizando ${valorTotalBRL}. Setor SmartLic: ${setor_nome}. Histórico completo no PNCP.`
      : `${empresa.razao_social} (CNPJ ${cnpjFormatted}) — perfil B2G no setor ${setor_nome}. Sem histórico de contratos públicos nos últimos 24 meses. Dados oficiais do PNCP via SmartLic.`;

  const orgSchema: Record<string, unknown> = {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    '@id': `https://smartlic.tech/cnpj/${empresa.cnpj}#organization`,
    name: empresa.razao_social,
    legalName: empresa.razao_social,
    taxID: cnpjFormatted,
    identifier: [
      {
        '@type': 'PropertyValue',
        propertyID: 'CNPJ',
        value: empresa.cnpj,
      },
      {
        '@type': 'PropertyValue',
        propertyID: 'CNAE',
        value: empresa.cnae_principal,
      },
    ],
    address: {
      '@type': 'PostalAddress',
      addressRegion: empresa.uf,
      addressCountry: 'BR',
    },
    url: `https://smartlic.tech/cnpj/${empresa.cnpj}`,
    sameAs,
    description,
    knowsAbout: setor_nome,
  };

  if (empresa.porte) {
    orgSchema.size = empresa.porte;
  }

  if (ufs_atuacao && ufs_atuacao.length > 0) {
    orgSchema.areaServed = ufs_atuacao.map((uf) => ({
      '@type': 'AdministrativeArea',
      name: uf,
      addressCountry: 'BR',
    }));
  }

  if (total_contratos_24m > 0) {
    orgSchema.interactionStatistic = {
      '@type': 'InteractionCounter',
      interactionType: { '@type': 'SellAction', name: 'Contratos Públicos (24 meses)' },
      userInteractionCount: total_contratos_24m,
    };
  }

  return orgSchema;
}
