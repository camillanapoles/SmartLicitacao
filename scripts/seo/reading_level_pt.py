#!/usr/bin/env python3
"""Reading level (Flesch-Kincaid PT-BR adaptation) for SmartLic landing pages.

Issue: #1012 [CI-READING-014]

## Formula

We compute two metrics and report both:

1. **Índice Flesch (PT-BR, Martins et al. 1996):**
       IF = 248.835 - 1.015 * ASL - 84.6 * ASW
   - ASL = average sentence length (words / sentences)
   - ASW = average syllables per word
   - Range: 0..100, higher = easier

2. **Flesch-Kincaid Grade Level (Kincaid et al. 1975, applied to PT-BR
   syllable counts):**
       FKGL = 0.39 * ASL + 11.8 * ASW - 15.59
   - Output approximates US grade level. We map to Brazilian "série"
     by ceil(FKGL) (5.x -> 5a/6a serie, 9.x -> 9a serie...).

Both are reported per page; the **grade** is what the threshold gates on.

## Threshold (issue #1012 AC)

- warn  if grade > 7  (>7a serie)
- fail  if grade > 9  (>9a serie)

**Per task instruction the workflow runs warn-only initially**
(no fail exit). Threshold stays in code but wrapped behind --strict flag.

## Allowlist semantics

Technical terms (CNPJ, PNCP, ComprasGov, etc.) still count as 1 word
but are forced to a syllable count of 1 — so they don't penalize ASW.
ASL still includes them. Documented in code: this is choice (b) from
the advisor review.

## Text extraction (.tsx / .ts / .md)

Pragmatic regex extractor: pulls JSX text nodes, single/double/template
string literals, and markdown body text. Strips HTML/JSX tags, code
fences, URLs. Accepts ~10% noise — documented limitation.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

# ---------------------------------------------------------------------------
# Allowlist (technical terms that should not penalize ASW).
# ---------------------------------------------------------------------------
ALLOWLIST_TERMS: set[str] = {
    "cnpj",
    "pncp",
    "comprasgov",
    "comprasnet",
    "smartlic",
    "lc",
    "lei",
    "decreto",
    "art",
    "tcu",
    "tce",
    "stj",
    "stf",
    "agu",
    "cgu",
    "pix",
    "pf",
    "pj",
    "saas",
    "api",
    "csv",
    "xlsx",
    "pdf",
    "url",
    "rfp",
    "rfb",
    "sicaf",
    "siasg",
    "bnc",
    "bbmnet",
    "licitacoes",  # técnico no contexto B2G
    # Termos compostos do domínio:
    "dispensa",
    "pregao",
    "concorrencia",
    "credenciamento",
    "habilitacao",
    "edital",
    "edital-tipo",
    "ata",
    "srp",
    "aro",
}


# ---------------------------------------------------------------------------
# Syllable counter (PT-BR, vowel-group heuristic).
#
# Approach: lowercase, strip diacritics for grouping, count maximal vowel
# groups. Treats hiatos as single group (over-count slightly) but is
# stable & deterministic — sufficient for Flesch averaging.
# ---------------------------------------------------------------------------

_DIACRITIC_MAP = str.maketrans(
    {
        "á": "a", "à": "a", "ã": "a", "â": "a", "ä": "a",
        "é": "e", "ê": "e", "è": "e", "ë": "e",
        "í": "i", "î": "i", "ï": "i",
        "ó": "o", "ô": "o", "õ": "o", "ö": "o",
        "ú": "u", "û": "u", "ü": "u",
        "ç": "c",
        "Á": "a", "À": "a", "Ã": "a", "Â": "a",
        "É": "e", "Ê": "e",
        "Í": "i",
        "Ó": "o", "Ô": "o", "Õ": "o",
        "Ú": "u",
        "Ç": "c",
    }
)

_VOWELS = "aeiouy"

_VOWEL_GROUP_RE = re.compile(rf"[{_VOWELS}]+")


def count_syllables_pt(word: str) -> int:
    """Count syllables in a Portuguese word using vowel-group heuristic."""
    w = word.lower().translate(_DIACRITIC_MAP)
    w = re.sub(r"[^a-z]", "", w)
    if not w:
        return 0
    groups = _VOWEL_GROUP_RE.findall(w)
    n = len(groups)
    return max(n, 1)


# ---------------------------------------------------------------------------
# Sentence / word tokenization
# ---------------------------------------------------------------------------

_SENT_SPLIT_RE = re.compile(r"[.!?]+(?:\s+|$)")
_WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:[-'][A-Za-zÀ-ÖØ-öø-ÿ]+)*")


def split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in _SENT_SPLIT_RE.split(text)]
    return [p for p in parts if p]


def extract_words(text: str) -> list[str]:
    return _WORD_RE.findall(text)


# ---------------------------------------------------------------------------
# Text extraction from .tsx / .ts / .md / .mdx
# ---------------------------------------------------------------------------

# Strings inside JSX/TS: '...', "...", `...` (no nested template support)
_STRING_LITERAL_RE = re.compile(
    r"""(?<![A-Za-z0-9_])(?:                       # not part of identifier
        '([^'\\\n]*(?:\\.[^'\\\n]*)*)'             # 'single'
      | "([^"\\\n]*(?:\\.[^"\\\n]*)*)"             # "double"
      | `([^`\\]*(?:\\.[^`\\]*)*)`                 # `template`
    )""",
    re.VERBOSE,
)
# JSX text between > and < that contains at least one letter
_JSX_TEXT_RE = re.compile(r">([^<>{}\n]*[A-Za-zÀ-ÖØ-öø-ÿ][^<>{}\n]*)<")
_IMPORT_RE = re.compile(r"^\s*import\s.+?from\s+['\"][^'\"]+['\"];?\s*$", re.MULTILINE)
_REQUIRE_RE = re.compile(r"require\s*\(\s*['\"][^'\"]+['\"]\s*\)")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_URL_RE = re.compile(r"https?://\S+|www\.\S+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
_CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`]+`")
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_MD_HEADING_HASHES_RE = re.compile(r"^#+\s*", re.MULTILINE)
_MD_EMPHASIS_RE = re.compile(r"[*_]{1,3}([^*_]+)[*_]{1,3}")


def _looks_like_human_text(s: str) -> bool:
    """Heuristic: keep only prose-like strings.

    To minimize noise from JSX/Tailwind/identifiers, we require:
    - >= 6 words OR contains sentence-ending punctuation
    - not a path, URL, classname, or identifier
    """
    s = s.strip()
    if len(s) < 12:
        return False
    if " " not in s:
        return False
    if s.startswith(("http://", "https://", "/", "./", "../", "#", "data:", "mailto:")):
        return False
    if "/" in s and " " not in s.split("/", 1)[0]:
        return False
    if not re.search(r"[aeiouAEIOU]", s):
        return False

    tokens = s.split()
    has_sentence_punct = bool(re.search(r"[.!?](?:\s|$)", s))

    # Need either real punctuation (a sentence) or many words (a paragraph).
    if not has_sentence_punct and len(tokens) < 6:
        return False

    # Filter className-like strings.
    css_like = sum(
        1 for t in tokens if len(t) <= 3 or ":" in t or t.startswith("-")
    )
    if css_like / max(len(tokens), 1) > 0.5:
        return False

    return True


def extract_text_from_tsx(source: str) -> str:
    src = _IMPORT_RE.sub("", source)
    src = _REQUIRE_RE.sub("", src)

    chunks: list[str] = []

    for m in _JSX_TEXT_RE.finditer(src):
        chunks.append(m.group(1))

    for m in _STRING_LITERAL_RE.finditer(src):
        s = m.group(1) or m.group(2) or m.group(3) or ""
        # remove JSX expressions inside template literals: ${...}
        s = re.sub(r"\$\{[^}]*\}", " ", s)
        if _looks_like_human_text(s):
            chunks.append(s)

    return " ".join(chunks)


def extract_text_from_md(source: str) -> str:
    s = _CODE_FENCE_RE.sub(" ", source)
    s = _INLINE_CODE_RE.sub(" ", s)
    s = _MD_LINK_RE.sub(r"\1", s)
    s = _HTML_TAG_RE.sub(" ", s)
    s = _MD_HEADING_HASHES_RE.sub("", s)
    s = _MD_EMPHASIS_RE.sub(r"\1", s)
    s = _URL_RE.sub("", s)
    return s


def extract_text(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    suffix = path.suffix.lower()
    if suffix in {".tsx", ".ts", ".jsx", ".js"}:
        return extract_text_from_tsx(raw)
    if suffix in {".md", ".mdx"}:
        return extract_text_from_md(raw)
    return raw


# ---------------------------------------------------------------------------
# Reading level metrics
# ---------------------------------------------------------------------------


@dataclass
class ReadingLevelReport:
    label: str
    words: int
    sentences: int
    syllables: int
    flesch_index_pt: float  # 0..100, higher = easier
    flesch_kincaid_grade: float  # ~ US grade level
    estimated_serie: int  # ceil of grade, clamp 1..15

    def as_dict(self) -> dict:
        return asdict(self)


def compute_reading_level(text: str, label: str = "") -> ReadingLevelReport | None:
    sentences = split_sentences(text)
    if not sentences:
        return None
    words = extract_words(text)
    if not words:
        return None

    n_sentences = len(sentences)
    n_words = len(words)

    syllables = 0
    for w in words:
        wl = w.lower()
        if wl in ALLOWLIST_TERMS:
            syllables += 1  # neutralize technical jargon
        else:
            syllables += count_syllables_pt(w)

    asl = n_words / n_sentences
    asw = syllables / n_words

    flesch_index = 248.835 - 1.015 * asl - 84.6 * asw
    fkgl = 0.39 * asl + 11.8 * asw - 15.59

    serie = max(1, min(15, math.ceil(fkgl)))

    return ReadingLevelReport(
        label=label,
        words=n_words,
        sentences=n_sentences,
        syllables=syllables,
        flesch_index_pt=round(flesch_index, 2),
        flesch_kincaid_grade=round(fkgl, 2),
        estimated_serie=serie,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


# Default targets per issue #1012 AC.
DEFAULT_TARGETS: list[str] = [
    "frontend/app/page.tsx",
    "frontend/app/planos/page.tsx",
    "frontend/app/pricing/page.tsx",
    "frontend/app/fundadores/page.tsx",
    "frontend/app/fundadores/FundadoresClient.tsx",
    "frontend/app/consultoria-b2g/page.tsx",
    "frontend/app/observatorio/page.tsx",
    "frontend/app/observatorio/[slug]/page.tsx",
    "frontend/app/observatorio/[slug]/ObservatorioRelatorioClient.tsx",
]


WARN_GRADE = 7
FAIL_GRADE = 9


def format_markdown_report(reports: list[ReadingLevelReport]) -> str:
    lines = [
        "## Reading Level (Flesch-Kincaid PT-BR)",
        "",
        f"Threshold: warn `grade > {WARN_GRADE}`, fail `grade > {FAIL_GRADE}` "
        "(currently warn-only).",
        "",
        "| Página | Palavras | Frases | IF (0-100) | Grade | Série | Status |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for r in reports:
        if r.flesch_kincaid_grade > FAIL_GRADE:
            status = "FAIL"
        elif r.flesch_kincaid_grade > WARN_GRADE:
            status = "WARN"
        else:
            status = "OK"
        lines.append(
            f"| `{r.label}` | {r.words} | {r.sentences} "
            f"| {r.flesch_index_pt:.1f} | {r.flesch_kincaid_grade:.2f} "
            f"| {r.estimated_serie}a | {status} |"
        )
    lines.append("")
    lines.append(
        "_Higher Flesch Index (IF) = easier. Grade approximates US grade level; "
        "Série is `ceil(grade)`._"
    )
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Reading level (Flesch-Kincaid PT-BR) for SmartLic pages."
    )
    p.add_argument(
        "paths",
        nargs="*",
        help="Files or globs. Defaults to issue #1012 target list.",
    )
    p.add_argument(
        "--root",
        default=".",
        help="Repository root (default: cwd).",
    )
    p.add_argument(
        "--format",
        choices=("markdown", "json", "text"),
        default="markdown",
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero on grade > FAIL_GRADE (default: warn-only).",
    )
    p.add_argument(
        "--output",
        default=None,
        help="Write report to this file in addition to stdout.",
    )
    return p.parse_args(argv)


def resolve_targets(root: Path, paths: Iterable[str]) -> list[Path]:
    resolved: list[Path] = []
    for p in paths:
        path = (root / p).resolve()
        if path.exists():
            resolved.append(path)
    return resolved


def run(argv: list[str] | None = None) -> int:
    ns = parse_args(argv)
    root = Path(ns.root).resolve()

    targets = ns.paths if ns.paths else DEFAULT_TARGETS
    files = resolve_targets(root, targets)

    if not files:
        print("No target files found.", file=sys.stderr)
        return 0

    reports: list[ReadingLevelReport] = []
    for f in files:
        text = extract_text(f)
        try:
            rel = f.relative_to(root)
        except ValueError:
            rel = f
        report = compute_reading_level(text, label=str(rel))
        if report is None:
            continue
        reports.append(report)

    if not reports:
        print("No measurable text extracted.", file=sys.stderr)
        return 0

    if ns.format == "json":
        out = json.dumps([r.as_dict() for r in reports], indent=2, ensure_ascii=False)
    elif ns.format == "text":
        out = "\n".join(
            f"{r.label}\twords={r.words}\tsent={r.sentences}\t"
            f"IF={r.flesch_index_pt:.1f}\tgrade={r.flesch_kincaid_grade:.2f}"
            for r in reports
        )
    else:
        out = format_markdown_report(reports)

    print(out)
    if ns.output:
        Path(ns.output).write_text(out + "\n", encoding="utf-8")

    if ns.strict:
        if any(r.flesch_kincaid_grade > FAIL_GRADE for r in reports):
            return 2
        if any(r.flesch_kincaid_grade > WARN_GRADE for r in reports):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(run())
