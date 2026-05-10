"""Issue #1012 — unit tests for scripts/seo/reading_level_pt.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _load():
    here = Path(__file__).resolve().parents[2]
    mod_path = here / "scripts" / "seo" / "reading_level_pt.py"
    spec = importlib.util.spec_from_file_location("reading_level_pt", mod_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["reading_level_pt"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def rl():
    return _load()


# ---------- Syllable counter ---------------------------------------------------


@pytest.mark.parametrize(
    "word,expected",
    [
        ("casa", 2),
        ("computador", 4),
        ("a", 1),
        ("e", 1),
        ("Brasil", 2),
        ("Joao", 2),  # "joao" -> two vowel groups (jo-ao) per heuristic
        ("dia", 1),  # hiato collapsed (heuristic limit)
        ("rua", 1),
        ("contratação", 4),  # con-tra-ta-cao
        ("inteligência", 4),  # in-te-li-gen-cia (heuristic ~4)
    ],
)
def test_syllable_count_reasonable(rl, word, expected):
    got = rl.count_syllables_pt(word)
    # Allow ±1 for heuristic variation; this is averaged over many words.
    assert abs(got - expected) <= 1, f"{word}: got {got}, expected ~{expected}"


def test_syllable_empty_returns_zero(rl):
    assert rl.count_syllables_pt("") == 0
    assert rl.count_syllables_pt("123") == 0


# ---------- Sentence / word tokenization --------------------------------------


def test_split_sentences_basic(rl):
    text = "Olá mundo. Tudo bem? Sim! Continue."
    assert len(rl.split_sentences(text)) == 4


def test_extract_words(rl):
    text = "O CNPJ 12.345/0001-99 está ativo."
    words = rl.extract_words(text)
    assert "CNPJ" in words
    assert "ativo" in words
    assert "12" not in words  # numbers excluded


# ---------- Directional formula sanity ----------------------------------------


SIMPLE_TEXT = (
    "O céu é azul. A flor é bela. O sol brilha. O dia é bom. "
    "A casa é grande. O gato dorme. O pão é gostoso. A água é fria."
)

# Dense academic-style PT prose
COMPLEX_TEXT = (
    "A operacionalização sistemática dos paradigmas epistemológicos "
    "contemporâneos demanda uma reconfiguração metodológica abrangente, "
    "considerando especialmente as interdependências hermenêuticas "
    "subjacentes aos processos comunicacionais multidimensionais que "
    "permeiam a infraestrutura sociotécnica contemporânea, conforme "
    "demonstrado pela bibliografia especializada referente à temática "
    "em questão."
)


def test_simple_text_grade_lower_than_complex(rl):
    simple = rl.compute_reading_level(SIMPLE_TEXT, label="simple")
    complex_ = rl.compute_reading_level(COMPLEX_TEXT, label="complex")
    assert simple is not None
    assert complex_ is not None
    assert simple.flesch_kincaid_grade < complex_.flesch_kincaid_grade
    # Higher Flesch Index = easier
    assert simple.flesch_index_pt > complex_.flesch_index_pt


def test_simple_text_within_target_range(rl):
    """Simple PT-BR prose should land at ~5a-7a serie."""
    r = rl.compute_reading_level(SIMPLE_TEXT, label="simple")
    assert r is not None
    assert r.estimated_serie <= 7, (
        f"Simple text estimated_serie={r.estimated_serie}, expected <= 7"
    )


def test_complex_text_above_warn_threshold(rl):
    r = rl.compute_reading_level(COMPLEX_TEXT, label="complex")
    assert r is not None
    assert r.flesch_kincaid_grade > rl.WARN_GRADE


def test_empty_text_returns_none(rl):
    assert rl.compute_reading_level("", label="empty") is None
    assert rl.compute_reading_level("   ", label="ws") is None


# ---------- Allowlist -----------------------------------------------------------


def test_allowlist_neutralizes_jargon(rl):
    """A text with many technical terms should not score worse than the same
    text with those terms replaced by a 1-syllable filler — by construction
    of the allowlist semantics."""
    text_with_jargon = "O CNPJ é necessário. O PNCP publica editais. O TCU fiscaliza."
    text_neutral = "O CEP é necessário. O CEP publica editais. O CEP fiscaliza."
    a = rl.compute_reading_level(text_with_jargon, label="jargon")
    b = rl.compute_reading_level(text_neutral, label="neutral")
    assert a is not None and b is not None
    # Both should score the same since CNPJ/PNCP/TCU each forced to 1 syllable.
    # CEP is not in allowlist but has 1 vowel group anyway.
    assert abs(a.flesch_kincaid_grade - b.flesch_kincaid_grade) < 0.5


# ---------- Text extractors ----------------------------------------------------


def test_extract_text_from_tsx_pulls_jsx_and_strings(rl):
    src = """
    import React from 'react';
    export default function Page() {
      return (
        <div className="px-4 py-2">
          <h1>Bem-vindo ao SmartLic</h1>
          <p>{'Plataforma de inteligência B2G para empresas brasileiras.'}</p>
        </div>
      );
    }
    """
    text = rl.extract_text_from_tsx(src)
    assert "Bem-vindo ao SmartLic" in text
    assert "inteligência" in text
    # className tailwind tokens should not appear
    assert "px-4" not in text


def test_extract_text_from_md(rl):
    src = """
# Título

Este é um parágrafo com [link](https://exemplo.com) e `código inline`.

```python
x = 1
```

Outro parágrafo final.
    """
    text = rl.extract_text_from_md(src)
    assert "parágrafo" in text
    assert "código inline" not in text  # stripped
    assert "x = 1" not in text  # code fence stripped


# ---------- CLI ----------------------------------------------------------------


def test_run_with_explicit_file(tmp_path, capsys, rl):
    f = tmp_path / "sample.md"
    f.write_text(SIMPLE_TEXT, encoding="utf-8")
    rc = rl.run([str(f), "--root", str(tmp_path), "--format", "json"])
    assert rc == 0
    out = capsys.readouterr().out
    import json as _json

    data = _json.loads(out)
    assert len(data) == 1
    assert data[0]["words"] > 0


def test_run_strict_fails_on_complex(tmp_path, rl):
    # Build a text guaranteed above FAIL_GRADE
    f = tmp_path / "complex.md"
    f.write_text(COMPLEX_TEXT * 3, encoding="utf-8")
    rc = rl.run([str(f), "--root", str(tmp_path), "--strict", "--format", "text"])
    assert rc in (1, 2)
