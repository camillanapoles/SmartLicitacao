"""Unit tests for scripts/seo/uniqueness_audit.py.

Tests focus on pure logic — Jaccard, shingles, action classification, family
classification, sitemap parsing — using synthetic strings and deterministic
fixtures. We do NOT exercise the HTTP crawl path (covered by manual smoke
runs against staging).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make scripts/seo importable
_THIS = Path(__file__).resolve()
_SCRIPTS = _THIS.parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from seo.uniqueness_audit import (  # noqa: E402
    AuditRow,
    PageDoc,
    audit_pages,
    classify,
    classify_family,
    extract_visible_text,
    jaccard,
    parse_sitemap_xml,
    shingles,
    slug_from_url,
    stratified_sample,
    tokenize,
    write_csv,
    write_noindex_lib,
)


# --------------------------------------------------------------------------
# Tokenization + shingles + Jaccard
# --------------------------------------------------------------------------


class TestTokenize:
    def test_lowercases_and_keeps_pt_accents(self) -> None:
        assert tokenize("Construção CIVIL ÁGUA") == ["construção", "civil", "água"]

    def test_strips_punctuation(self) -> None:
        assert tokenize("hello, world! foo-bar.") == ["hello", "world", "foo", "bar"]

    def test_empty(self) -> None:
        assert tokenize("") == []
        assert tokenize("   ") == []

    def test_alphanum(self) -> None:
        assert tokenize("CNPJ 12345678000199 abc") == ["cnpj", "12345678000199", "abc"]


class TestShingles:
    def test_basic_5_grams(self) -> None:
        tokens = ["a", "b", "c", "d", "e", "f"]
        result = shingles(tokens, k=5)
        assert result == {"a b c d e", "b c d e f"}

    def test_short_input_returns_single_shingle(self) -> None:
        tokens = ["a", "b"]
        result = shingles(tokens, k=5)
        assert result == {"a b"}

    def test_empty_returns_empty_set(self) -> None:
        assert shingles([], k=5) == set()

    def test_exact_k(self) -> None:
        tokens = ["a", "b", "c", "d", "e"]
        assert shingles(tokens, k=5) == {"a b c d e"}


class TestJaccard:
    def test_identical_sets(self) -> None:
        a = {"x", "y", "z"}
        assert jaccard(a, a) == 1.0

    def test_disjoint_sets(self) -> None:
        assert jaccard({"a"}, {"b"}) == 0.0

    def test_partial_overlap(self) -> None:
        a = {"a", "b", "c", "d"}
        b = {"c", "d", "e", "f"}
        # intersection=2, union=6 -> 1/3
        assert jaccard(a, b) == pytest.approx(2 / 6)

    def test_empty_inputs_zero(self) -> None:
        assert jaccard(set(), set()) == 0.0
        assert jaccard({"x"}, set()) == 0.0
        assert jaccard(set(), {"x"}) == 0.0


# --------------------------------------------------------------------------
# Classification
# --------------------------------------------------------------------------


class TestClassify:
    def test_high_similarity_merge(self) -> None:
        assert classify(0.71, 1000) == "canonical_merge"
        assert classify(0.95, 50) == "canonical_merge"

    def test_mid_similarity_thin_noindex(self) -> None:
        assert classify(0.50, 200) == "noindex"
        assert classify(0.69, 299) == "noindex"

    def test_mid_similarity_thick_falls_through_to_noindex(self) -> None:
        # 0.40 <= sim < 0.70 + word_count >= 300 → falls into catch-all noindex
        # (mid duplication, even with content, drags HCU site-wide)
        assert classify(0.50, 500) == "noindex"

    def test_low_similarity_thick_keep(self) -> None:
        assert classify(0.10, 500) == "keep"
        assert classify(0.39, 300) == "keep"

    def test_low_similarity_thin_noindex(self) -> None:
        assert classify(0.10, 100) == "noindex"
        assert classify(0.0, 0) == "noindex"

    def test_boundary_70_is_merge(self) -> None:
        assert classify(0.70, 1000) == "canonical_merge"

    def test_boundary_40_is_noindex_when_thin(self) -> None:
        assert classify(0.40, 100) == "noindex"


# --------------------------------------------------------------------------
# Family classification
# --------------------------------------------------------------------------


class TestClassifyFamily:
    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://smartlic.tech/cnpj/12345678000199", "cnpj"),
            ("https://smartlic.tech/cnpj/12345678000199/", "cnpj"),
            ("https://smartlic.tech/fornecedores/12345678000199", "fornecedores-cnpj"),
            ("https://smartlic.tech/contratos/orgao/12345678000199", "contratos-orgao"),
            ("https://smartlic.tech/blog/licitacoes/construcao/SP", "blog-licitacoes-setor-uf"),
            ("https://smartlic.tech/blog/licitacoes/saude/RJ/", "blog-licitacoes-setor-uf"),
            ("https://smartlic.tech/orgaos/12345678000199", "orgaos"),
            ("https://smartlic.tech/fornecedores/construcao/SP", "fornecedores-setor-uf"),
            ("https://smartlic.tech/contratos/saude/RJ", "contratos-setor-uf"),
            ("https://smartlic.tech/municipios/sao-paulo-sp", "municipios"),
            ("https://smartlic.tech/itens/12345", "itens"),
        ],
    )
    def test_recognized_families(self, url: str, expected: str) -> None:
        assert classify_family(url) == expected

    @pytest.mark.parametrize(
        "url",
        [
            "https://smartlic.tech/",
            "https://smartlic.tech/login",
            "https://smartlic.tech/blog",
            "https://smartlic.tech/blog/some-article",
        ],
    )
    def test_unknown_routes(self, url: str) -> None:
        assert classify_family(url) is None


class TestSlugFromUrl:
    def test_strips_trailing_slash(self) -> None:
        assert slug_from_url("https://smartlic.tech/cnpj/12345/", "cnpj") == "cnpj:/cnpj/12345"

    def test_keeps_path(self) -> None:
        assert (
            slug_from_url("https://smartlic.tech/blog/licitacoes/saude/SP", "blog-licitacoes-setor-uf")
            == "blog-licitacoes-setor-uf:/blog/licitacoes/saude/SP"
        )


# --------------------------------------------------------------------------
# HTML extraction
# --------------------------------------------------------------------------


class TestExtractVisibleText:
    def test_strips_script(self) -> None:
        html = "<html><body><p>Hello</p><script>alert('x')</script><p>World</p></body></html>"
        text = extract_visible_text(html)
        assert "alert" not in text
        assert "Hello" in text and "World" in text

    def test_strips_style(self) -> None:
        html = "<html><body><style>p {color:red}</style>Visible</body></html>"
        text = extract_visible_text(html)
        assert "color:red" not in text
        assert "Visible" in text

    def test_strips_nav_footer(self) -> None:
        html = "<html><body><nav>menu</nav><main>conteúdo principal</main><footer>rodapé</footer></body></html>"
        text = extract_visible_text(html)
        assert "menu" not in text
        assert "rodapé" not in text
        assert "conteúdo principal" in text

    def test_handles_empty(self) -> None:
        assert extract_visible_text("") == ""

    def test_handles_malformed(self) -> None:
        # Should not raise.
        text = extract_visible_text("<html><body><p>oi <unclosed")
        assert "oi" in text


# --------------------------------------------------------------------------
# Sitemap parsing
# --------------------------------------------------------------------------


class TestParseSitemapXml:
    def test_parses_sitemap_index(self) -> None:
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <sitemap><loc>https://smartlic.tech/sitemap/1.xml</loc></sitemap>
          <sitemap><loc>https://smartlic.tech/sitemap/2.xml</loc></sitemap>
        </sitemapindex>"""
        subs, urls = parse_sitemap_xml(xml)
        assert subs == [
            "https://smartlic.tech/sitemap/1.xml",
            "https://smartlic.tech/sitemap/2.xml",
        ]
        assert urls == []

    def test_parses_urlset(self) -> None:
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url><loc>https://smartlic.tech/cnpj/123</loc></url>
          <url><loc>https://smartlic.tech/cnpj/456</loc></url>
        </urlset>"""
        subs, urls = parse_sitemap_xml(xml)
        assert subs == []
        assert urls == [
            "https://smartlic.tech/cnpj/123",
            "https://smartlic.tech/cnpj/456",
        ]

    def test_handles_malformed(self) -> None:
        subs, urls = parse_sitemap_xml("<not-xml")
        assert subs == [] and urls == []


# --------------------------------------------------------------------------
# Pairwise audit pipeline
# --------------------------------------------------------------------------


def _doc(url: str, family: str, text: str) -> PageDoc:
    tokens = tokenize(text)
    return PageDoc(url=url, family=family, word_count=len(tokens), shingles=shingles(tokens))


class TestAuditPages:
    def test_two_near_duplicates_get_high_similarity(self) -> None:
        common = " ".join(["palavra"] * 20)
        a = _doc("/a", "cnpj", f"prefix {common} suffix one")
        b = _doc("/b", "cnpj", f"prefix {common} suffix two")
        rows = audit_pages([a, b])
        assert len(rows) == 2
        for r in rows:
            assert r.similarity_score > 0.5

    def test_disjoint_documents_low_similarity(self) -> None:
        a = _doc("/a", "cnpj", "alpha beta gamma delta epsilon zeta eta theta iota kappa")
        b = _doc("/b", "cnpj", "uno dos tres cuatro cinco seis siete ocho nueve diez")
        rows = audit_pages([a, b])
        for r in rows:
            assert r.similarity_score == 0.0

    def test_singleton_family_keep_or_noindex_by_word_count(self) -> None:
        thick = _doc("/a", "cnpj", " ".join(["palavra"] * 400))
        thin = _doc("/b", "fornecedores-cnpj", "três palavras só")
        rows = audit_pages([thick, thin])
        actions = {r.url: r.action for r in rows}
        assert actions["/a"] == "keep"
        assert actions["/b"] == "noindex"

    def test_finds_nearest_neighbor_within_family_only(self) -> None:
        common = " ".join(["palavra"] * 30)
        a = _doc("/cnpj/1", "cnpj", f"alpha {common}")
        b = _doc("/cnpj/2", "cnpj", f"beta {common}")
        c = _doc("/forn/1", "fornecedores-cnpj", f"gamma {common}")
        rows = audit_pages([a, b, c])
        for r in rows:
            if r.family == "cnpj":
                assert r.nearest_neighbor_url in ("/cnpj/1", "/cnpj/2")
            else:
                # singleton in fornecedores-cnpj — no neighbor
                assert r.nearest_neighbor_url == ""


# --------------------------------------------------------------------------
# Stratified sampling
# --------------------------------------------------------------------------


class TestStratifiedSample:
    def test_returns_full_set_when_below_n(self) -> None:
        urls = {"cnpj": ["a", "b"], "fornecedores-cnpj": ["c"]}
        out = stratified_sample(urls, n_per_family=5, seed=42)
        assert sorted(out["cnpj"]) == ["a", "b"]
        assert out["fornecedores-cnpj"] == ["c"]

    def test_caps_per_family(self) -> None:
        urls = {"cnpj": [str(i) for i in range(100)]}
        out = stratified_sample(urls, n_per_family=10, seed=42)
        assert len(out["cnpj"]) == 10
        # Deterministic with same seed:
        out2 = stratified_sample(urls, n_per_family=10, seed=42)
        assert out["cnpj"] == out2["cnpj"]


# --------------------------------------------------------------------------
# CSV + TS lib emission
# --------------------------------------------------------------------------


class TestWriteCsv:
    def test_writes_header_and_rows(self, tmp_path: Path) -> None:
        rows = [
            AuditRow("https://x.tld/cnpj/1", "cnpj", "https://x.tld/cnpj/2", 0.5, 100, "noindex"),
        ]
        path = tmp_path / "out.csv"
        n = write_csv(rows, path)
        assert n == 1
        content = path.read_text(encoding="utf-8").splitlines()
        assert content[0] == "url,family,nearest_neighbor_url,similarity_score,word_count,action"
        assert "https://x.tld/cnpj/1" in content[1]
        assert "0.5000" in content[1]


class TestWriteNoindexLib:
    def test_emits_only_noindex_action(self, tmp_path: Path) -> None:
        rows = [
            AuditRow("https://x.tld/cnpj/1", "cnpj", "n", 0.5, 50, "noindex"),
            AuditRow("https://x.tld/cnpj/2", "cnpj", "n", 0.0, 1000, "keep"),
            AuditRow("https://x.tld/cnpj/3", "cnpj", "n", 0.9, 100, "canonical_merge"),
        ]
        path = tmp_path / "noindex-slugs.ts"
        n = write_noindex_lib(rows, path)
        assert n == 1
        content = path.read_text(encoding="utf-8")
        assert '"cnpj:/cnpj/1"' in content
        assert "/cnpj/2" not in content
        assert "/cnpj/3" not in content
        assert "AUTO-GENERATED" in content
        assert "export const NOINDEX_SLUGS" in content

    def test_idempotent(self, tmp_path: Path) -> None:
        rows = [
            AuditRow("https://x.tld/cnpj/3", "cnpj", "n", 0.5, 50, "noindex"),
            AuditRow("https://x.tld/cnpj/1", "cnpj", "n", 0.5, 50, "noindex"),
            AuditRow("https://x.tld/cnpj/2", "cnpj", "n", 0.5, 50, "noindex"),
        ]
        path = tmp_path / "noindex-slugs.ts"
        write_noindex_lib(rows, path)
        first = path.read_text(encoding="utf-8")
        write_noindex_lib(rows, path)
        second = path.read_text(encoding="utf-8")
        assert first == second
        # Sorted output → /cnpj/1 appears before /cnpj/2 before /cnpj/3
        idx_1 = first.index("/cnpj/1")
        idx_2 = first.index("/cnpj/2")
        idx_3 = first.index("/cnpj/3")
        assert idx_1 < idx_2 < idx_3
