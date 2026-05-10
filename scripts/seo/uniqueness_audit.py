#!/usr/bin/env python3
"""SEO-P0-003 — Programmatic SEO uniqueness audit.

Audita unicidade de páginas programáticas para identificar duplicatas que
estão sendo classificadas como "Scaled Content Abuse" (SCA) ou "doorway"
pelo classificador HCU do Google (March 2026 Core Update).

Pipeline:
  1. Crawla URLs do `sitemap.xml` (sitemap index + sub-sitemaps).
  2. Filtra URLs por `route family` (--families) — fornecedores, cnpj,
     contratos/orgao, blog/licitacoes/[setor]/[uf].
  3. Extrai conteúdo textual server-rendered (strip script/style/nav).
  4. Computa Jaccard similarity entre cada par (shingles k=5 tokens) dentro
     do mesmo route family — encontra o "nearest neighbor" para cada URL.
  5. Classifica em `action`:
       - similarity >= 0.70  → canonical_merge   (deferido para PR #990)
       - 0.40 <= sim < 0.70 + word_count < 300 → noindex
       - sim < 0.40 + word_count >= 300        → keep
       - else → noindex (low signal)
  6. Emite CSV com (url, family, nearest_neighbor_url, similarity_score,
     word_count, action).

Uso:
  python scripts/seo/uniqueness_audit.py \\
      --sitemap https://smartlic.tech/sitemap.xml \\
      --output  docs/seo/audits/uniqueness-2026-05.csv \\
      --sample  1000 \\
      --families fornecedores cnpj contratos-orgao blog-licitacoes-setor-uf

Notas operacionais:
  - O crawl real (~10k URLs) leva > 80 min com politeness 2 req/s — em
    sessão curta use `--sample N` para amostragem estratificada por família.
  - Threshold 0.70 vem de Discovered Labs 2026 (programmatic SEO uniqueness).
  - Stdlib + httpx (já em backend/requirements.txt). HTML parsing via
    `html.parser` (stdlib) — sem BeautifulSoup necessário.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable, Sequence
from urllib.parse import urlparse

# httpx é optional — script tem fallback para urllib se não disponível.
try:
    import httpx  # type: ignore

    HAS_HTTPX = True
except ImportError:  # pragma: no cover
    HAS_HTTPX = False
    import urllib.request


# Thresholds — ver docs/sessions/2026-05/seo-p0-003-uniqueness-audit.md
SIMILARITY_MERGE = 0.70
SIMILARITY_LOW = 0.40
WORD_COUNT_MIN = 300

# Sitemap namespace
SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"

# Route family classifier — order matters (most specific first).
# Each entry is (family_id, regex_against_path).
ROUTE_FAMILIES: list[tuple[str, re.Pattern[str]]] = [
    ("blog-licitacoes-setor-uf", re.compile(r"^/blog/licitacoes/[^/]+/[^/]+/?$")),
    ("contratos-orgao", re.compile(r"^/contratos/orgao/\d{14}/?$")),
    ("fornecedores-cnpj", re.compile(r"^/fornecedores/\d{14}/?$")),
    ("cnpj", re.compile(r"^/cnpj/\d{14}/?$")),
    ("orgaos", re.compile(r"^/orgaos/\d{14}/?$")),
    ("fornecedores-setor-uf", re.compile(r"^/fornecedores/[^/]+/[^/]+/?$")),
    ("contratos-setor-uf", re.compile(r"^/contratos/[^/]+/[^/]+/?$")),
    ("alertas-publicos", re.compile(r"^/alertas-publicos/[^/]+/[^/]+/?$")),
    ("municipios", re.compile(r"^/municipios/[^/]+/?$")),
    ("itens", re.compile(r"^/itens/[^/]+/?$")),
]


# ---------------------------------------------------------------------------
# HTML extraction
# ---------------------------------------------------------------------------


class _TextExtractor(HTMLParser):
    """Extracts visible text content. Drops script/style/nav/footer/header."""

    SKIP_TAGS = {"script", "style", "nav", "footer", "header", "noscript", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._buf: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            stripped = data.strip()
            if stripped:
                self._buf.append(stripped)

    def get_text(self) -> str:
        return " ".join(self._buf)


def extract_visible_text(html: str) -> str:
    """Server-rendered visible text. Robust to malformed HTML."""
    parser = _TextExtractor()
    try:
        parser.feed(html)
    except Exception:  # pragma: no cover — defensive only
        pass
    return parser.get_text()


# ---------------------------------------------------------------------------
# Tokenization + Jaccard
# ---------------------------------------------------------------------------


_TOKEN_RE = re.compile(r"[a-záéíóúâêôãõçü0-9]+", re.IGNORECASE)


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens — preserva acentos PT-BR."""
    return _TOKEN_RE.findall(text.lower())


def shingles(tokens: Sequence[str], k: int = 5) -> set[str]:
    """k-shingles (sliding windows of k tokens) — captura n-grams.

    Sets shingles handles `len(tokens) < k` returning a single shingle of all
    tokens (so very-short pages still hash to something). Empty tokens → empty
    set.
    """
    if not tokens:
        return set()
    if len(tokens) < k:
        return {" ".join(tokens)}
    return {" ".join(tokens[i : i + k]) for i in range(len(tokens) - k + 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity. Handles empty sets defensively (returns 0.0)."""
    if not a and not b:
        return 0.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    if union == 0:
        return 0.0
    return inter / union


# ---------------------------------------------------------------------------
# Action classifier
# ---------------------------------------------------------------------------


def classify(similarity: float, word_count: int) -> str:
    """Map (similarity, word_count) → action label.

    Thresholds documented in the issue body and the docs/sessions/ note.
    """
    if similarity >= SIMILARITY_MERGE:
        return "canonical_merge"
    if SIMILARITY_LOW <= similarity < SIMILARITY_MERGE and word_count < WORD_COUNT_MIN:
        return "noindex"
    if similarity < SIMILARITY_LOW and word_count >= WORD_COUNT_MIN:
        return "keep"
    # Catch-all: pouco texto e baixa similaridade → ainda noindex (low signal,
    # qualifica como thin content para o classificador HCU).
    return "noindex"


# ---------------------------------------------------------------------------
# Sitemap fetcher
# ---------------------------------------------------------------------------


def _http_get(url: str, *, timeout: float = 15.0) -> str:
    if HAS_HTTPX:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            r = client.get(url)
            r.raise_for_status()
            return r.text
    req = urllib.request.Request(url, headers={"User-Agent": "smartlic-seo-audit/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return resp.read().decode("utf-8", errors="replace")


def parse_sitemap_xml(xml_text: str) -> tuple[list[str], list[str]]:
    """Returns (sub_sitemaps, urls). One of the lists will be non-empty."""
    sub_sitemaps: list[str] = []
    urls: list[str] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return sub_sitemaps, urls

    if root.tag.endswith("sitemapindex"):
        for sm in root.findall(f"{SITEMAP_NS}sitemap"):
            loc = sm.find(f"{SITEMAP_NS}loc")
            if loc is not None and loc.text:
                sub_sitemaps.append(loc.text.strip())
    elif root.tag.endswith("urlset"):
        for u in root.findall(f"{SITEMAP_NS}url"):
            loc = u.find(f"{SITEMAP_NS}loc")
            if loc is not None and loc.text:
                urls.append(loc.text.strip())
    return sub_sitemaps, urls


def crawl_sitemap_index(root_sitemap_url: str, *, max_subs: int = 20) -> list[str]:
    """Returns the full URL list across the sitemap index + sub-sitemaps."""
    print(f"[audit] fetching sitemap index: {root_sitemap_url}", file=sys.stderr)
    xml = _http_get(root_sitemap_url)
    subs, urls = parse_sitemap_xml(xml)
    if urls:
        return urls
    all_urls: list[str] = []
    for sub_url in subs[:max_subs]:
        print(f"[audit] fetching sub-sitemap: {sub_url}", file=sys.stderr)
        try:
            sub_xml = _http_get(sub_url)
        except Exception as exc:  # noqa: BLE001
            print(f"[audit] failed sub-sitemap {sub_url}: {exc}", file=sys.stderr)
            continue
        _, sub_urls = parse_sitemap_xml(sub_xml)
        all_urls.extend(sub_urls)
    return all_urls


# ---------------------------------------------------------------------------
# Family classification
# ---------------------------------------------------------------------------


def classify_family(url: str) -> str | None:
    path = urlparse(url).path
    for family_id, pattern in ROUTE_FAMILIES:
        if pattern.match(path):
            return family_id
    return None


def slug_from_url(url: str, family: str) -> str:
    """Returns the slug used by `noindex-slugs.ts` to gate noindex.

    Convention: family + ":" + path-without-leading-slash. The frontend lib
    matches pages against this exact key (URL path post-/).
    """
    path = urlparse(url).path.rstrip("/")
    return f"{family}:{path}"


# ---------------------------------------------------------------------------
# Stratified sampling
# ---------------------------------------------------------------------------


def stratified_sample(
    urls_by_family: dict[str, list[str]],
    n_per_family: int,
    *,
    seed: int = 42,
) -> dict[str, list[str]]:
    """Sample `n_per_family` URLs per family, deterministic via seed."""
    import random

    rng = random.Random(seed)
    out: dict[str, list[str]] = {}
    for family, urls in urls_by_family.items():
        if len(urls) <= n_per_family:
            out[family] = list(urls)
        else:
            out[family] = rng.sample(urls, n_per_family)
    return out


# ---------------------------------------------------------------------------
# Main audit pipeline
# ---------------------------------------------------------------------------


@dataclass
class PageDoc:
    url: str
    family: str
    word_count: int
    shingles: set[str] = field(default_factory=set)


@dataclass
class AuditRow:
    url: str
    family: str
    nearest_neighbor_url: str
    similarity_score: float
    word_count: int
    action: str

    def as_csv(self) -> list[str]:
        return [
            self.url,
            self.family,
            self.nearest_neighbor_url,
            f"{self.similarity_score:.4f}",
            str(self.word_count),
            self.action,
        ]


def audit_pages(docs: list[PageDoc]) -> list[AuditRow]:
    """For each doc find the nearest neighbor in the same family + classify."""
    by_family: dict[str, list[PageDoc]] = defaultdict(list)
    for d in docs:
        by_family[d.family].append(d)

    rows: list[AuditRow] = []
    for family, family_docs in by_family.items():
        if len(family_docs) < 2:
            # Only one doc in this family — can't compare. Default to keep if
            # word_count >= 300, else noindex (thin).
            for d in family_docs:
                action = "keep" if d.word_count >= WORD_COUNT_MIN else "noindex"
                rows.append(
                    AuditRow(
                        url=d.url,
                        family=family,
                        nearest_neighbor_url="",
                        similarity_score=0.0,
                        word_count=d.word_count,
                        action=action,
                    )
                )
            continue

        for i, d in enumerate(family_docs):
            best_score = 0.0
            best_neighbor = ""
            for j, other in enumerate(family_docs):
                if i == j:
                    continue
                score = jaccard(d.shingles, other.shingles)
                if score > best_score:
                    best_score = score
                    best_neighbor = other.url
            rows.append(
                AuditRow(
                    url=d.url,
                    family=family,
                    nearest_neighbor_url=best_neighbor,
                    similarity_score=best_score,
                    word_count=d.word_count,
                    action=classify(best_score, d.word_count),
                )
            )
    return rows


def fetch_and_extract(
    url: str,
    *,
    timeout: float = 15.0,
    sleep_between: float = 0.5,
) -> tuple[str, int]:
    """Returns (visible_text, word_count). Polite delay handled by caller."""
    html = _http_get(url, timeout=timeout)
    text = extract_visible_text(html)
    if sleep_between > 0:
        time.sleep(sleep_between)
    tokens = tokenize(text)
    return text, len(tokens)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def write_csv(rows: Iterable[AuditRow], output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["url", "family", "nearest_neighbor_url", "similarity_score", "word_count", "action"]
        )
        for row in rows:
            writer.writerow(row.as_csv())
            n += 1
    return n


def write_noindex_lib(rows: Iterable[AuditRow], output_path: Path) -> int:
    """Auto-generates frontend/lib/seo/noindex-slugs.ts from action=noindex rows.

    Idempotent — `--check` mode in callers compares output bytes.
    """
    noindex_keys = sorted({slug_from_url(r.url, r.family) for r in rows if r.action == "noindex"})
    output_path.parent.mkdir(parents=True, exist_ok=True)

    header = [
        "// AUTO-GENERATED by scripts/seo/uniqueness_audit.py — do not edit by hand.",
        "// SEO-P0-003 (#989). To regenerate run:",
        "//   python scripts/seo/uniqueness_audit.py --sitemap <url> \\",
        "//     --output docs/seo/audits/uniqueness-<yyyy-mm>.csv \\",
        "//     --emit-noindex-lib frontend/lib/seo/noindex-slugs.ts",
        "//",
        "// Format of each entry: '<family>:<path>' — matches the key returned by",
        "// `noindexKey(family, path)` in `lib/seo/noindex.ts`.",
        "",
        "export const NOINDEX_SLUGS: ReadonlySet<string> = new Set([",
    ]
    body = [f"  {json.dumps(k)}," for k in noindex_keys]
    footer = ["]);", ""]
    contents = "\n".join(header + body + footer)
    output_path.write_text(contents, encoding="utf-8")
    return len(noindex_keys)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sitemap", default="https://smartlic.tech/sitemap.xml", help="Root sitemap (or sitemap index) URL.")
    parser.add_argument("--output", required=True, help="CSV output path.")
    parser.add_argument("--sample", type=int, default=0, help="Stratified sample size per family (0 = full crawl).")
    parser.add_argument(
        "--families",
        nargs="*",
        default=None,
        help="Restrict audit to these family ids (default: all known).",
    )
    parser.add_argument("--politeness", type=float, default=0.5, help="Sleep seconds between fetches.")
    parser.add_argument("--timeout", type=float, default=15.0, help="Per-request timeout seconds.")
    parser.add_argument(
        "--emit-noindex-lib",
        default=None,
        help="If set, write the resulting noindex slug list to this TS file path.",
    )
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for stratified sampling.")
    parser.add_argument("--dry-run", action="store_true", help="Skip the actual HTTP crawl; emit empty CSV.")
    args = parser.parse_args(argv)

    output = Path(args.output)
    if args.dry_run:
        n = write_csv([], output)
        print(f"[audit] dry-run: wrote header-only CSV to {output} ({n} rows)", file=sys.stderr)
        return 0

    # 1. Crawl sitemap
    all_urls = crawl_sitemap_index(args.sitemap)
    print(f"[audit] discovered {len(all_urls)} URLs from sitemap", file=sys.stderr)

    # 2. Family classification + filter
    by_family: dict[str, list[str]] = defaultdict(list)
    for url in all_urls:
        fam = classify_family(url)
        if fam is None:
            continue
        if args.families and fam not in args.families:
            continue
        by_family[fam].append(url)

    for fam, urls in by_family.items():
        print(f"[audit]   {fam}: {len(urls)} URLs", file=sys.stderr)

    # 3. Optional stratified sample
    if args.sample > 0:
        by_family = stratified_sample(by_family, args.sample, seed=args.seed)
        for fam, urls in by_family.items():
            print(f"[audit] sampled {fam}: {len(urls)} URLs", file=sys.stderr)

    # 4. Fetch + extract + tokenize
    docs: list[PageDoc] = []
    for fam, urls in by_family.items():
        for i, url in enumerate(urls):
            try:
                _, word_count = fetch_and_extract(
                    url, timeout=args.timeout, sleep_between=args.politeness
                )
                # Re-fetch text to extract shingles (avoid double tokenization)
                html = _http_get(url, timeout=args.timeout)
                text = extract_visible_text(html)
                tokens = tokenize(text)
                docs.append(
                    PageDoc(
                        url=url,
                        family=fam,
                        word_count=word_count,
                        shingles=shingles(tokens, k=5),
                    )
                )
                if i % 50 == 0:
                    print(f"[audit] {fam} {i}/{len(urls)}", file=sys.stderr)
            except Exception as exc:  # noqa: BLE001
                print(f"[audit] fetch failed {url}: {exc}", file=sys.stderr)

    # 5. Audit pairwise
    rows = audit_pages(docs)
    n_csv = write_csv(rows, output)

    by_action = defaultdict(int)
    for r in rows:
        by_action[r.action] += 1
    print(f"[audit] wrote {n_csv} rows to {output}", file=sys.stderr)
    for action, count in sorted(by_action.items()):
        print(f"[audit]   {action}: {count}", file=sys.stderr)

    # 6. Optional: emit TS noindex lib
    if args.emit_noindex_lib:
        ts_path = Path(args.emit_noindex_lib)
        n_keys = write_noindex_lib(rows, ts_path)
        print(f"[audit] wrote {n_keys} noindex keys to {ts_path}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
