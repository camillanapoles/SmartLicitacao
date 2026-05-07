"""TD-BE-023: Edge case tests for filter module (keyword + density pipeline).

These inputs can appear in real PNCP data and must not crash the pipeline.
Each test verifies that the function handles the input without raising an
exception and returns a valid (possibly empty) result.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from filter.keywords import (
    normalize_text,
    match_keywords,
    validate_terms,
    has_red_flags,
    has_sector_red_flags,
    _strip_org_context,
    KEYWORDS_EXCLUSAO,
    RED_FLAGS_MEDICAL,
    RED_FLAGS_ADMINISTRATIVE,
)
from filter.density import check_proximity_context, check_co_occurrence


# ──────────────────────────────────────────────────────────────────────
# normalize_text — edge cases
# ──────────────────────────────────────────────────────────────────────

class TestNormalizeTextEdgeCases:
    """Verify normalize_text never crashes and always returns a string."""

    @pytest.mark.timeout(30)
    def test_empty_string(self):
        result = normalize_text("")
        assert result == ""

    @pytest.mark.timeout(30)
    def test_whitespace_only(self):
        result = normalize_text("   ")
        assert isinstance(result, str)
        assert result == ""

    @pytest.mark.timeout(30)
    def test_very_long_string(self):
        """10 000 tokens of 'x ' must not raise and must return a string."""
        long_text = "x " * 10_000
        result = normalize_text(long_text)
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.timeout(30)
    def test_special_chars_punctuation(self):
        result = normalize_text("!@#$%^&*().,;:?!")
        assert isinstance(result, str)

    @pytest.mark.timeout(30)
    def test_unicode_accented_portuguese(self):
        """Common accented Portuguese words used in procurement descriptions."""
        result = normalize_text("licitação aquisição serviço")
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.timeout(30)
    def test_emoji(self):
        result = normalize_text("🎯 objetivo da licitação")
        assert isinstance(result, str)

    @pytest.mark.timeout(30)
    def test_numeric_only(self):
        result = normalize_text("12345 67890")
        assert isinstance(result, str)
        assert "12345" in result

    @pytest.mark.timeout(30)
    def test_rtl_text(self):
        """Arabic right-to-left text should not crash."""
        result = normalize_text("مرحبا")
        assert isinstance(result, str)

    @pytest.mark.timeout(30)
    def test_mixed_scripts(self):
        """Mix of Latin, Arabic, CJK in a single string."""
        result = normalize_text("uniforme 制服 زي موحد")
        assert isinstance(result, str)

    @pytest.mark.timeout(30)
    def test_newlines_and_tabs(self):
        result = normalize_text("aquisicao\nde\tuniforma\r\nescolar")
        assert isinstance(result, str)
        assert "aquisicao" in result

    @pytest.mark.timeout(30)
    def test_null_byte_and_control_chars(self):
        result = normalize_text("aquisicao\x00uniforme\x01")
        assert isinstance(result, str)


# ──────────────────────────────────────────────────────────────────────
# match_keywords — edge cases
# ──────────────────────────────────────────────────────────────────────

class TestMatchKeywordsEdgeCases:
    """Verify match_keywords never crashes on pathological inputs."""

    KEYWORDS = {"uniforme", "fardamento", "vestuario"}

    @pytest.mark.timeout(30)
    def test_empty_objeto(self):
        matched, kws = match_keywords("", self.KEYWORDS)
        assert matched is False
        assert kws == []

    @pytest.mark.timeout(30)
    def test_whitespace_only_objeto(self):
        matched, kws = match_keywords("   ", self.KEYWORDS)
        assert matched is False
        assert kws == []

    @pytest.mark.timeout(30)
    def test_very_long_objeto(self):
        long_text = ("uniforme escolar " * 500) + "x " * 5_000
        matched, kws = match_keywords(long_text, self.KEYWORDS)
        assert isinstance(matched, bool)
        assert isinstance(kws, list)

    @pytest.mark.timeout(30)
    def test_none_like_empty_string(self):
        """Passing "" is the normalised None — must return (False, [])."""
        matched, kws = match_keywords("", self.KEYWORDS)
        assert matched is False

    @pytest.mark.timeout(30)
    def test_special_chars_objeto(self):
        matched, kws = match_keywords("!!! @@@ *** ...", self.KEYWORDS)
        assert isinstance(matched, bool)

    @pytest.mark.timeout(30)
    def test_unicode_objeto(self):
        matched, kws = match_keywords("licitação de uniforme escolar", self.KEYWORDS)
        assert isinstance(matched, bool)

    @pytest.mark.timeout(30)
    def test_emoji_objeto(self):
        matched, kws = match_keywords("🎯 uniforme 🏫", self.KEYWORDS)
        assert isinstance(matched, bool)

    @pytest.mark.timeout(30)
    def test_numeric_only_objeto(self):
        matched, kws = match_keywords("12345 67890 00001", self.KEYWORDS)
        assert matched is False
        assert kws == []

    @pytest.mark.timeout(30)
    def test_rtl_texto(self):
        """Arabic text with no Portuguese keywords must return (False, [])."""
        matched, kws = match_keywords("مرحبا بالعالم", self.KEYWORDS)
        assert matched is False
        assert kws == []

    @pytest.mark.timeout(30)
    def test_empty_keywords_set(self):
        matched, kws = match_keywords("aquisicao de uniforme", set())
        assert matched is False
        assert kws == []

    @pytest.mark.timeout(30)
    def test_with_exclusions_empty_objeto(self):
        matched, kws = match_keywords("", self.KEYWORDS, exclusions=KEYWORDS_EXCLUSAO)
        assert matched is False

    @pytest.mark.timeout(30)
    def test_with_exclusions_long_objeto(self):
        long_text = "confeccao de uniforme " * 1_000
        matched, kws = match_keywords(
            long_text, self.KEYWORDS, exclusions=KEYWORDS_EXCLUSAO
        )
        assert isinstance(matched, bool)

    @pytest.mark.timeout(30)
    def test_keyword_longer_than_texto(self):
        """Keyword longer than the text itself must not crash."""
        very_long_kw = {"uniforme " * 200}
        matched, kws = match_keywords("uniforme", very_long_kw)
        assert isinstance(matched, bool)


# ──────────────────────────────────────────────────────────────────────
# validate_terms — edge cases
# ──────────────────────────────────────────────────────────────────────

class TestValidateTermsEdgeCases:
    """validate_terms must never crash and must maintain valid/ignored invariant."""

    @pytest.mark.timeout(30)
    def test_empty_list(self):
        result = validate_terms([])
        assert result["valid"] == []
        assert result["ignored"] == []

    @pytest.mark.timeout(30)
    def test_list_with_empty_string(self):
        result = validate_terms([""])
        assert "" in result["ignored"]
        assert result["valid"] == []

    @pytest.mark.timeout(30)
    def test_list_with_whitespace_only(self):
        result = validate_terms(["   "])
        assert len(result["ignored"]) == 1
        assert result["valid"] == []

    @pytest.mark.timeout(30)
    def test_list_with_special_chars(self):
        result = validate_terms(["!@#$"])
        assert isinstance(result, dict)
        assert "valid" in result and "ignored" in result

    @pytest.mark.timeout(30)
    def test_list_with_unicode(self):
        result = validate_terms(["licitação", "aquisição"])
        assert isinstance(result, dict)

    @pytest.mark.timeout(30)
    def test_list_with_numeric_only(self):
        result = validate_terms(["12345"])
        assert isinstance(result, dict)

    @pytest.mark.timeout(30)
    def test_list_with_very_long_term(self):
        long_term = "uniforme" * 500
        result = validate_terms([long_term])
        assert isinstance(result, dict)

    @pytest.mark.timeout(30)
    def test_valid_ignored_no_intersection(self):
        """Invariant: no term can appear in both valid and ignored."""
        terms = ["uniforme", "", "de", "  ", "licitacao", "!bad!", "1234"]
        result = validate_terms(terms)
        valid_set = set(result["valid"])
        ignored_set = set(v.strip().lower() for v in result["ignored"])
        # Normalised valid terms must not appear in ignored
        for v in valid_set:
            assert v not in ignored_set, f"'{v}' is in both valid and ignored"


# ──────────────────────────────────────────────────────────────────────
# _strip_org_context — edge cases
# ──────────────────────────────────────────────────────────────────────

class TestStripOrgContextEdgeCases:
    """_strip_org_context must not crash on edge inputs."""

    @pytest.mark.timeout(30)
    def test_empty_string(self):
        result = _strip_org_context("")
        assert result == ""

    @pytest.mark.timeout(30)
    def test_whitespace_only(self):
        result = _strip_org_context("   ")
        assert isinstance(result, str)

    @pytest.mark.timeout(30)
    def test_very_long_string(self):
        long_text = "aquisicao de uniforme " * 3_000
        result = _strip_org_context(long_text)
        assert isinstance(result, str)

    @pytest.mark.timeout(30)
    def test_special_chars(self):
        result = _strip_org_context("!!! @@@")
        assert isinstance(result, str)

    @pytest.mark.timeout(30)
    def test_unicode(self):
        result = _strip_org_context("licitação de fardamento")
        assert isinstance(result, str)

    @pytest.mark.timeout(30)
    def test_numeric_only(self):
        result = _strip_org_context("12345 00001")
        assert isinstance(result, str)


# ──────────────────────────────────────────────────────────────────────
# has_red_flags — edge cases
# ──────────────────────────────────────────────────────────────────────

class TestHasRedFlagsEdgeCases:
    """has_red_flags must not crash on edge inputs."""

    RED_FLAG_SETS = [RED_FLAGS_MEDICAL, RED_FLAGS_ADMINISTRATIVE]

    @pytest.mark.timeout(30)
    def test_empty_objeto_norm(self):
        has_flags, matched = has_red_flags("", self.RED_FLAG_SETS)
        assert has_flags is False
        assert matched == []

    @pytest.mark.timeout(30)
    def test_whitespace_only(self):
        has_flags, matched = has_red_flags("   ", self.RED_FLAG_SETS)
        assert isinstance(has_flags, bool)

    @pytest.mark.timeout(30)
    def test_very_long_texto(self):
        long_text = "tratamento paciente " * 3_000
        has_flags, matched = has_red_flags(long_text, self.RED_FLAG_SETS)
        assert isinstance(has_flags, bool)
        assert isinstance(matched, list)

    @pytest.mark.timeout(30)
    def test_special_chars(self):
        has_flags, matched = has_red_flags("!@#$%", self.RED_FLAG_SETS)
        assert isinstance(has_flags, bool)

    @pytest.mark.timeout(30)
    def test_unicode_text(self):
        has_flags, matched = has_red_flags(
            "licitação aquisição serviço", self.RED_FLAG_SETS
        )
        assert isinstance(has_flags, bool)

    @pytest.mark.timeout(30)
    def test_empty_red_flag_sets(self):
        has_flags, matched = has_red_flags("paciente hospitalar", [])
        assert has_flags is False
        assert matched == []

    @pytest.mark.timeout(30)
    def test_numeric_only(self):
        has_flags, matched = has_red_flags("12345 67890", self.RED_FLAG_SETS)
        assert isinstance(has_flags, bool)

    @pytest.mark.timeout(30)
    def test_rtl_text(self):
        has_flags, matched = has_red_flags("مرحبا بالعالم", self.RED_FLAG_SETS)
        assert isinstance(has_flags, bool)

    @pytest.mark.timeout(30)
    def test_with_custom_terms_empty(self):
        has_flags, matched = has_red_flags(
            "paciente hospitalar", self.RED_FLAG_SETS, custom_terms=[]
        )
        assert isinstance(has_flags, bool)

    @pytest.mark.timeout(30)
    def test_with_custom_terms_special_chars(self):
        has_flags, matched = has_red_flags(
            "paciente hospitalar",
            self.RED_FLAG_SETS,
            custom_terms=["!@#", ""],
        )
        assert isinstance(has_flags, bool)


# ──────────────────────────────────────────────────────────────────────
# has_sector_red_flags — edge cases
# ──────────────────────────────────────────────────────────────────────

class TestHasSectorRedFlagsEdgeCases:
    """has_sector_red_flags must not crash on edge inputs."""

    @pytest.mark.timeout(30)
    def test_empty_objeto_norm(self):
        has_flags, matched = has_sector_red_flags("", "vestuario")
        assert has_flags is False

    @pytest.mark.timeout(30)
    def test_unknown_sector(self):
        has_flags, matched = has_sector_red_flags(
            "some text", "sector_that_does_not_exist"
        )
        assert has_flags is False
        assert matched == []

    @pytest.mark.timeout(30)
    def test_very_long_texto(self):
        long_text = "engenharia de software " * 2_000
        has_flags, matched = has_sector_red_flags(long_text, "engenharia")
        assert isinstance(has_flags, bool)

    @pytest.mark.timeout(30)
    def test_special_chars_objeto(self):
        has_flags, matched = has_sector_red_flags("!@#$%", "vestuario")
        assert isinstance(has_flags, bool)

    @pytest.mark.timeout(30)
    def test_numeric_only(self):
        has_flags, matched = has_sector_red_flags("12345 67890", "informatica")
        assert isinstance(has_flags, bool)


# ──────────────────────────────────────────────────────────────────────
# check_proximity_context — edge cases
# ──────────────────────────────────────────────────────────────────────

class TestCheckProximityContextEdgeCases:
    """check_proximity_context must not crash on edge inputs."""

    @pytest.mark.timeout(30)
    def test_empty_texto(self):
        should_reject, reason = check_proximity_context(
            "", ["uniforme"], "vestuario", {"alimentos": {"merenda"}}
        )
        assert should_reject is False
        assert reason is None

    @pytest.mark.timeout(30)
    def test_whitespace_only_texto(self):
        should_reject, reason = check_proximity_context(
            "   ", ["uniforme"], "vestuario", {"alimentos": {"merenda"}}
        )
        assert isinstance(should_reject, bool)

    @pytest.mark.timeout(30)
    def test_very_long_texto(self):
        long_text = "uniforme escolar " * 2_000
        should_reject, reason = check_proximity_context(
            long_text,
            ["uniforme"],
            "vestuario",
            {"alimentos": {"merenda"}},
        )
        assert isinstance(should_reject, bool)

    @pytest.mark.timeout(30)
    def test_special_chars_texto(self):
        should_reject, reason = check_proximity_context(
            "!@# *** ...", ["uniforme"], "vestuario", {"alimentos": {"merenda"}}
        )
        assert isinstance(should_reject, bool)

    @pytest.mark.timeout(30)
    def test_unicode_texto(self):
        should_reject, reason = check_proximity_context(
            "licitação de uniforme escolar",
            ["uniforme"],
            "vestuario",
            {"alimentos": {"merenda"}},
        )
        assert isinstance(should_reject, bool)

    @pytest.mark.timeout(30)
    def test_numeric_only_texto(self):
        should_reject, reason = check_proximity_context(
            "12345 67890",
            ["uniforme"],
            "vestuario",
            {"alimentos": {"merenda"}},
        )
        assert should_reject is False

    @pytest.mark.timeout(30)
    def test_empty_matched_terms(self):
        should_reject, reason = check_proximity_context(
            "uniforme escolar", [], "vestuario", {"alimentos": {"merenda"}}
        )
        assert should_reject is False

    @pytest.mark.timeout(30)
    def test_zero_window_size(self):
        should_reject, reason = check_proximity_context(
            "uniforme merenda",
            ["uniforme"],
            "vestuario",
            {"alimentos": {"merenda"}},
            window_size=0,
        )
        assert should_reject is False

    @pytest.mark.timeout(30)
    def test_empty_other_sectors(self):
        should_reject, reason = check_proximity_context(
            "uniforme escolar", ["uniforme"], "vestuario", {}
        )
        assert should_reject is False

    @pytest.mark.timeout(30)
    def test_rtl_text(self):
        should_reject, reason = check_proximity_context(
            "مرحبا بالعالم",
            ["uniforme"],
            "vestuario",
            {"alimentos": {"merenda"}},
        )
        assert should_reject is False


# ──────────────────────────────────────────────────────────────────────
# check_co_occurrence — edge cases
# ──────────────────────────────────────────────────────────────────────

class TestCheckCoOccurrenceEdgeCases:
    """check_co_occurrence must not crash on edge inputs."""

    def _make_rule(self, trigger, negative_contexts, positive_signals=None):
        from types import SimpleNamespace
        return SimpleNamespace(
            trigger=trigger,
            negative_contexts=negative_contexts,
            positive_signals=positive_signals or [],
        )

    @pytest.mark.timeout(30)
    def test_empty_texto(self):
        rule = self._make_rule("confeccao", ["placa"], [])
        should_reject, reason = check_co_occurrence("", [rule], "vestuario")
        assert should_reject is False
        assert reason is None

    @pytest.mark.timeout(30)
    def test_whitespace_only_texto(self):
        rule = self._make_rule("confeccao", ["placa"], [])
        should_reject, reason = check_co_occurrence("   ", [rule], "vestuario")
        assert isinstance(should_reject, bool)

    @pytest.mark.timeout(30)
    def test_empty_rules(self):
        should_reject, reason = check_co_occurrence(
            "confeccao de placas", [], "vestuario"
        )
        assert should_reject is False
        assert reason is None

    @pytest.mark.timeout(30)
    def test_very_long_texto(self):
        rule = self._make_rule("confeccao", ["placa"], [])
        long_text = "aquisicao de material escolar " * 2_000
        should_reject, reason = check_co_occurrence(long_text, [rule], "vestuario")
        assert isinstance(should_reject, bool)

    @pytest.mark.timeout(30)
    def test_special_chars_texto(self):
        rule = self._make_rule("confeccao", ["placa"], [])
        should_reject, reason = check_co_occurrence("!@# *** ...", [rule], "vestuario")
        assert isinstance(should_reject, bool)

    @pytest.mark.timeout(30)
    def test_unicode_texto(self):
        rule = self._make_rule("confeccao", ["placa"], [])
        should_reject, reason = check_co_occurrence(
            "licitação confeccao de uniformes", [rule], "vestuario"
        )
        assert isinstance(should_reject, bool)

    @pytest.mark.timeout(30)
    def test_numeric_only_texto(self):
        rule = self._make_rule("confeccao", ["placa"], [])
        should_reject, reason = check_co_occurrence("12345 67890", [rule], "vestuario")
        assert should_reject is False

    @pytest.mark.timeout(30)
    def test_rtl_text(self):
        rule = self._make_rule("confeccao", ["placa"], [])
        should_reject, reason = check_co_occurrence(
            "مرحبا بالعالم", [rule], "vestuario"
        )
        assert should_reject is False
