const UF_PATTERN = [
  "ac", "al", "am", "ap", "ba", "ce", "df", "es", "go", "ma",
  "mg", "ms", "mt", "pa", "pb", "pe", "pi", "pr", "rj", "rn",
  "ro", "rr", "rs", "sc", "se", "sp", "to",
].join("|");

// STORY-SEO-028: legacy backend/underscore sector IDs observed in GSC 404s.
// Keep this intentionally narrow: invalid/removed categories should stay 404/410,
// not be redirected to unrelated pages.
const LEGACY_LICITACOES_SECTOR_SLUGS = {
  engenharia_rodoviaria: "engenharia-rodoviaria",
  frota_veicular: "transporte",
  manutencao_predial: "manutencao-predial",
  materiais_hidraulicos: "materiais-hidraulicos",
  medicamentos: "saude",
  software_desenvolvimento: "software",
  software_licencas: "software",
};

function buildLegacyLicitacoesRedirects() {
  return Object.entries(LEGACY_LICITACOES_SECTOR_SLUGS).map(([sourceSlug, destinationSlug]) => ({
    source: `/blog/licitacoes/${sourceSlug}/:uf(${UF_PATTERN})`,
    destination: `/blog/licitacoes/${destinationSlug}/:uf`,
    statusCode: 301,
  }));
}

module.exports = {
  LEGACY_LICITACOES_SECTOR_SLUGS,
  UF_PATTERN,
  buildLegacyLicitacoesRedirects,
};
