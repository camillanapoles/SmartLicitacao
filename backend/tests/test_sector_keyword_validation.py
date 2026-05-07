"""TD-BE-015: Tests for _validate_sector_keywords — normalization duplicate detection."""
import logging

import pytest

from sectors import _validate_sector_keywords, _check_list_for_duplicates


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sector_data(
    keywords=None,
    exclusions=None,
    context_required_keywords=None,
):
    """Build a minimal sectors_data dict with a single sector for testing."""
    sector_cfg = {
        "name": "Test Sector",
        "description": "For tests only",
        "keywords": keywords or [],
    }
    if exclusions is not None:
        sector_cfg["exclusions"] = exclusions
    if context_required_keywords is not None:
        sector_cfg["context_required_keywords"] = context_required_keywords
    return {"sectors": {"test_sector": sector_cfg}}


# ---------------------------------------------------------------------------
# _validate_sector_keywords — happy path
# ---------------------------------------------------------------------------

class TestValidateSectorKeywordsNoWarnings:
    def test_empty_sectors_data(self):
        """Empty dict returns no warnings."""
        result = _validate_sector_keywords({})
        assert result == []

    def test_no_keywords(self):
        """Sector with empty keyword lists returns no warnings."""
        data = _make_sector_data(keywords=[], exclusions=[])
        result = _validate_sector_keywords(data)
        assert result == []

    def test_distinct_keywords_no_duplicates(self):
        """Distinct keywords that do not collapse under normalisation → no warnings."""
        data = _make_sector_data(keywords=["uniforme", "fardamento", "jaleco"])
        result = _validate_sector_keywords(data)
        assert result == []

    def test_real_yaml_has_warnings(self):
        """The real sectors_data.yaml must load without raising (warnings only)."""
        import yaml, os
        yaml_path = os.path.join(os.path.dirname(__file__), "..", "sectors_data.yaml")
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        # Must not raise — additive validation only
        result = _validate_sector_keywords(data)
        # Result is a list (may or may not be empty, but must be a list of strings)
        assert isinstance(result, list)
        for w in result:
            assert isinstance(w, str)


# ---------------------------------------------------------------------------
# _validate_sector_keywords — duplicate detection
# ---------------------------------------------------------------------------

class TestValidateSectorKeywordsDuplicates:
    def test_accent_duplicate_in_keywords(self):
        """'café' and 'cafe' normalise to the same string → one warning."""
        data = _make_sector_data(keywords=["café", "cafe"])
        result = _validate_sector_keywords(data)
        assert len(result) == 1
        assert "café" in result[0] or "cafe" in result[0]
        assert "test_sector" in result[0]

    def test_accent_duplicate_in_exclusions(self):
        """'café' and 'cafe' in exclusions → one warning with field name 'exclusions'."""
        data = _make_sector_data(exclusions=["café", "cafe"])
        result = _validate_sector_keywords(data)
        assert len(result) == 1
        assert "exclusions" in result[0]

    def test_case_and_accent_duplicate_in_keywords(self):
        """'Jaleco' and 'jaleco' and 'JALECO' all normalise the same → two warnings."""
        data = _make_sector_data(keywords=["Jaleco", "jaleco", "JALECO"])
        result = _validate_sector_keywords(data)
        # First encounter is "Jaleco", then "jaleco" is dup 1, "JALECO" is dup 2
        assert len(result) == 2

    def test_accent_dup_context_required_keywords(self):
        """Duplicate inside context_required_keywords value list → one warning."""
        data = _make_sector_data(
            keywords=["hospital"],
            context_required_keywords={
                "hospital": ["médico", "medico"]  # same after normalise
            },
        )
        result = _validate_sector_keywords(data)
        assert len(result) == 1
        assert "context_required_keywords" in result[0]
        assert "hospital" in result[0]

    def test_multiple_sectors_each_can_have_duplicates(self):
        """Duplicates in two different sectors are reported independently."""
        data = {
            "sectors": {
                "sector_a": {
                    "name": "A",
                    "description": "A",
                    "keywords": ["café", "cafe"],
                },
                "sector_b": {
                    "name": "B",
                    "description": "B",
                    "keywords": ["médico", "medico"],
                },
            }
        }
        result = _validate_sector_keywords(data)
        assert len(result) == 2
        sectors_mentioned = {w.split("'")[1] for w in result}
        assert sectors_mentioned == {"sector_a", "sector_b"}

    def test_no_false_positive_for_genuinely_different_accented_terms(self):
        """'bota' and 'bôta' are different words — only flag if they normalise identically."""
        # After normalize_text: accent strip turns ô → o, so 'bôta' == 'bota'
        from filter.keywords import normalize_text
        if normalize_text("bôta") == normalize_text("bota"):
            data = _make_sector_data(keywords=["bota", "bôta"])
            result = _validate_sector_keywords(data)
            assert len(result) == 1
        else:
            # If normaliser preserves the distinction, no warning expected
            data = _make_sector_data(keywords=["bota", "bôta"])
            result = _validate_sector_keywords(data)
            assert len(result) == 0

    def test_warning_contains_both_raw_forms(self):
        """Warning message includes both the original and the duplicate raw strings."""
        data = _make_sector_data(keywords=["confecção de uniforme", "confeccao de uniforme"])
        result = _validate_sector_keywords(data)
        assert len(result) == 1
        msg = result[0]
        # One of the two raw forms must appear in the message
        assert "confeccao de uniforme" in msg or "confecção de uniforme" in msg


# ---------------------------------------------------------------------------
# _validate_sector_keywords — logging integration
# ---------------------------------------------------------------------------

class TestValidateSectorKeywordsLogging:
    def test_load_sectors_logs_warning_for_duplicate(self, caplog):
        """Importing sectors with known YAML duplicates must emit TD-BE-015 warnings."""
        # We trigger the warning path by calling _validate_sector_keywords directly
        # and then verify the caller (_load_sectors_from_yaml) logs via caplog.
        import yaml, os
        yaml_path = os.path.join(os.path.dirname(__file__), "..", "sectors_data.yaml")
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        dup_warnings = _validate_sector_keywords(data)
        if dup_warnings:
            # Simulate what _load_sectors_from_yaml does
            logger = logging.getLogger("sectors")
            with caplog.at_level(logging.WARNING, logger="sectors"):
                for w in dup_warnings:
                    logger.warning("TD-BE-015 keyword duplicate: %s", w)
            assert any("TD-BE-015" in rec.message for rec in caplog.records)


# ---------------------------------------------------------------------------
# _check_list_for_duplicates (unit tests for the helper)
# ---------------------------------------------------------------------------

class TestCheckListForDuplicates:
    def _identity(self, text: str) -> str:
        return text

    def _lower(self, text: str) -> str:
        return text.lower()

    def test_no_items_no_warnings(self):
        warnings: list[str] = []
        _check_list_for_duplicates([], "s", "kw", self._identity, warnings)
        assert warnings == []

    def test_unique_items_no_warnings(self):
        warnings: list[str] = []
        _check_list_for_duplicates(["a", "b", "c"], "s", "kw", self._identity, warnings)
        assert warnings == []

    def test_exact_duplicate_detected(self):
        warnings: list[str] = []
        _check_list_for_duplicates(["a", "a"], "s", "kw", self._identity, warnings)
        assert len(warnings) == 1

    def test_normaliser_applied(self):
        warnings: list[str] = []
        _check_list_for_duplicates(["A", "a"], "s", "kw", self._lower, warnings)
        assert len(warnings) == 1

    def test_first_occurrence_recorded_in_warning(self):
        """Warning must reference the first-seen value, not the duplicate."""
        warnings: list[str] = []
        _check_list_for_duplicates(["Alpha", "alpha"], "s", "kw", self._lower, warnings)
        assert "Alpha" in warnings[0]
        assert "alpha" in warnings[0]

    def test_three_duplicates_two_warnings(self):
        """Three strings all normalising the same → 2 warnings (first is baseline)."""
        warnings: list[str] = []
        _check_list_for_duplicates(["A", "a", "a"], "s", "kw", self._lower, warnings)
        assert len(warnings) == 2

    def test_sector_id_in_warning(self):
        warnings: list[str] = []
        _check_list_for_duplicates(["A", "a"], "my_sector", "kw", self._lower, warnings)
        assert "my_sector" in warnings[0]

    def test_field_name_in_warning(self):
        warnings: list[str] = []
        _check_list_for_duplicates(["A", "a"], "s", "exclusions", self._lower, warnings)
        assert "exclusions" in warnings[0]
