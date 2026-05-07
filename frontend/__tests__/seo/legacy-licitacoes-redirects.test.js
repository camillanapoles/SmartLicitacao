const {
  LEGACY_LICITACOES_SECTOR_SLUGS,
  UF_PATTERN,
  buildLegacyLicitacoesRedirects,
} = require("../../lib/legacy-licitacoes-redirects");

describe("STORY-SEO-028 legacy /blog/licitacoes sector redirects", () => {
  it("maps only observed legacy sector IDs to canonical frontend slugs", () => {
    expect(LEGACY_LICITACOES_SECTOR_SLUGS).toEqual({
      engenharia_rodoviaria: "engenharia-rodoviaria",
      frota_veicular: "transporte",
      manutencao_predial: "manutencao-predial",
      materiais_hidraulicos: "materiais-hidraulicos",
      medicamentos: "saude",
      software_desenvolvimento: "software",
      software_licencas: "software",
    });
  });

  it("builds 301 redirects for valid UF leaf URLs only", () => {
    const redirects = buildLegacyLicitacoesRedirects();

    expect(redirects).toContainEqual({
      source: `/blog/licitacoes/materiais_hidraulicos/:uf(${UF_PATTERN})`,
      destination: "/blog/licitacoes/materiais-hidraulicos/:uf",
      statusCode: 301,
    });
    expect(redirects).toContainEqual({
      source: `/blog/licitacoes/software_desenvolvimento/:uf(${UF_PATTERN})`,
      destination: "/blog/licitacoes/software/:uf",
      statusCode: 301,
    });
    expect(redirects).toHaveLength(Object.keys(LEGACY_LICITACOES_SECTOR_SLUGS).length);
  });

  it("does not create generic catch-all redirects", () => {
    const redirects = buildLegacyLicitacoesRedirects();

    expect(redirects.some((redirect) => redirect.destination === "/")).toBe(false);
    expect(redirects.some((redirect) => redirect.source.includes(":path*"))).toBe(false);
    expect(redirects.some((redirect) => redirect.source.includes("/cidade/"))).toBe(false);
    expect(UF_PATTERN.split("|")).toHaveLength(27);
  });
});
