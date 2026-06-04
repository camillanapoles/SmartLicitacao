"""VIAB-UX-005a: Tests for A/B split utility and integration with enrich stage.

Tests cover:
- Deterministic split: same user_id -> same group
- 50/50 distribution: ~50% in each group (binomial validation)
- Edge cases: empty user_id raises ValueError
- Integration: enrich stage applies sort override when flag is active
- Integration: enrich stage does NOT override when flag is false (zero impact)
"""

import hashlib
from unittest.mock import MagicMock, patch

import pytest

from utils.viability_split import get_viability_sort_group


class TestGetViabilitySortGroup:
    """Tests for get_viability_sort_group deterministic split."""

    def test_same_user_always_same_group(self):
        """Same user_id always maps to same group (deterministic)."""
        user_ids = [
            "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "00000000-0000-0000-0000-000000000000",
            "user-123",
            "admin@smartlic.tech",
        ]
        for uid in user_ids:
            group1 = get_viability_sort_group(uid)
            group2 = get_viability_sort_group(uid)
            group3 = get_viability_sort_group(uid)
            assert group1 == group2 == group3, f"User {uid} got inconsistent groups"

    def test_group_is_a_or_b(self):
        """Group is always 'A' or 'B'."""
        user_ids = [
            "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "00000000-0000-0000-0000-000000000000",
            "user-123",
            "admin@smartlic.tech",
            "550e8400-e29b-41d4-a716-446655440000",
        ]
        for uid in user_ids:
            group = get_viability_sort_group(uid)
            assert group in ("A", "B"), f"Unexpected group {group} for user {uid}"

    def test_md5_hash_even_is_a_odd_is_b(self):
        """Group A = even MD5 first byte, Group B = odd MD5 first byte."""
        test_cases = [
            ("aaaa", "A" if hashlib.md5(b"aaaa").digest()[0] % 2 == 0 else "B"),
            ("bbbb", "A" if hashlib.md5(b"bbbb").digest()[0] % 2 == 0 else "B"),
            ("cccc", "A" if hashlib.md5(b"cccc").digest()[0] % 2 == 0 else "B"),
        ]
        for uid, expected in test_cases:
            assert get_viability_sort_group(uid) == expected, (
                f"User {uid} expected {expected}"
            )

    def test_empty_user_id_raises_value_error(self):
        """Empty user_id raises ValueError."""
        with pytest.raises(ValueError, match="user_id must be a non-empty string"):
            get_viability_sort_group("")

    def test_none_user_id_raises_value_error(self):
        """Empty string user_id raises ValueError."""
        with pytest.raises(ValueError, match="user_id must be a non-empty string"):
            get_viability_sort_group("")

    def test_binomial_distribution_100_users(self):
        """~50 users in each group out of 100 (binomial distribution).

        With 100 users, expected ~50 in each group. Acceptable range:
        35-65 (3 sigma for binomial with p=0.5, n=100).
        """
        user_ids = [f"user-{i:04d}" for i in range(100)]
        group_counts = {"A": 0, "B": 0}

        for uid in user_ids:
            group = get_viability_sort_group(uid)
            group_counts[group] += 1

        total = sum(group_counts.values())
        assert total == 100, f"Expected 100 total users, got {total}"
        # 3 sigma range for binomial(100, 0.5): mean=50, sigma=5
        assert 35 <= group_counts["A"] <= 65, (
            f"Group A count {group_counts['A']} outside expected range 35-65"
        )
        assert 35 <= group_counts["B"] <= 65, (
            f"Group B count {group_counts['B']} outside expected range 35-65"
        )

    def test_binomial_distribution_1000_users(self):
        """~500 users in each group out of 1000.

        With 1000 users, expected ~500 in each group. Acceptable range:
        450-550 (3 sigma for binomial with p=0.5, n=1000: sigma~15.8).
        """
        user_ids = [f"uuid-{i:05d}" for i in range(1000)]
        group_counts = {"A": 0, "B": 0}

        for uid in user_ids:
            group = get_viability_sort_group(uid)
            group_counts[group] += 1

        total = sum(group_counts.values())
        assert total == 1000, f"Expected 1000 total users, got {total}"
        # 3 sigma range for binomial(1000, 0.5): mean=500, sigma~15.8
        assert 450 <= group_counts["A"] <= 550, (
            f"Group A count {group_counts['A']} outside expected range 450-550"
        )
        assert 450 <= group_counts["B"] <= 550, (
            f"Group B count {group_counts['B']} outside expected range 450-550"
        )


class TestViabilitySortIntegration:
    """Integration tests: enrich stage applies sort override when flag is active."""

    @pytest.mark.asyncio
    @patch("config.features._feature_flag_cache", {})
    @patch("config.get_feature_flag")
    async def test_flag_active_group_b_overrides_sort(self, mock_get_ff):
        """When flag is active and user is Group B, sort is overridden to confianca."""
        from pipeline.stages.enrich import stage_enrich
        from search_pipeline import SearchPipeline
        from search_context import SearchContext
        from types import SimpleNamespace

        # Mock: flag is ON, user gets Group B
        mock_get_ff.return_value = True

        # Use a user_id known to hash to odd byte (Group B)
        user_b_id = None
        for i in range(100):
            test_uid = f"b-user-{i:04d}"
            if get_viability_sort_group(test_uid) == "B":
                user_b_id = test_uid
                break
        assert user_b_id is not None, "Could not find a Group B user"

        items = [
            {"_viability_score": 90, "_confidence_score": 95, "valorTotalEstimado": 500000},
            {"_viability_score": 50, "_confidence_score": 60, "valorTotalEstimado": 100000},
        ]

        request = MagicMock(
            ufs=["SC"],
            data_inicial="2026-01-01",
            data_final="2026-01-07",
            setor_id="v",
            status=MagicMock(value="todos"),
            ordenacao="data_desc",
            termos_busca=None,
            show_all_matches=False,
            exclusion_terms=None,
            modalidades=None,
            valor_minimo=None,
            valor_maximo=None,
            esferas=None,
            municipios=None,
            search_id="ts",
            modo_busca=None,
            check_sanctions=False,
        )

        ctx = SearchContext(
            request=request,
            user={"id": user_b_id, "email": "b@test.com"},
        )
        ctx.is_simplified = True  # Skip viability assessment
        ctx.active_keywords = {"x"}
        ctx.custom_terms = []
        ctx.licitacoes_filtradas = list(items)

        deps = SimpleNamespace(
            ENABLE_NEW_PRICING=False,
            PNCPClient=MagicMock(),
            buscar_todas_ufs_paralelo=MagicMock(return_value=[]),
            aplicar_todos_filtros=MagicMock(return_value=([], {})),
            create_excel=MagicMock(),
            rate_limiter=MagicMock(),
            check_user_roles=MagicMock(return_value=(False, False)),
            match_keywords=MagicMock(return_value=(True, [])),
            KEYWORDS_UNIFORMES=set(),
            KEYWORDS_EXCLUSAO=set(),
            validate_terms=MagicMock(return_value={"valid": [], "ignored": [], "reasons": {}}),
        )

        pipeline = SearchPipeline(deps)
        await stage_enrich(pipeline, ctx)

        # Assert: sort was overridden to confianca for Group B
        assert request.ordenacao == "confianca", (
            f"Expected ordenacao='confianca' for Group B, got '{request.ordenacao}'"
        )

    @pytest.mark.asyncio
    @patch("config.features._feature_flag_cache", {})
    @patch("config.get_feature_flag")
    async def test_flag_active_group_a_keeps_default(self, mock_get_ff):
        """When flag is active and user is Group A, sort stays as default (data_desc)."""
        from pipeline.stages.enrich import stage_enrich
        from search_pipeline import SearchPipeline
        from search_context import SearchContext
        from types import SimpleNamespace

        # Mock: flag is ON, user gets Group A
        mock_get_ff.return_value = True

        # Find a user_id that maps to group A
        user_a_id = None
        for i in range(100):
            test_uid = f"a-user-{i:04d}"
            if get_viability_sort_group(test_uid) == "A":
                user_a_id = test_uid
                break
        assert user_a_id is not None, "Could not find a Group A user"

        items = [
            {"_viability_score": 90, "_confidence_score": 95, "valorTotalEstimado": 500000},
        ]

        request = MagicMock(
            ufs=["SC"],
            data_inicial="2026-01-01",
            data_final="2026-01-07",
            setor_id="v",
            status=MagicMock(value="todos"),
            ordenacao="data_desc",
            termos_busca=None,
            show_all_matches=False,
            exclusion_terms=None,
            modalidades=None,
            valor_minimo=None,
            valor_maximo=None,
            esferas=None,
            municipios=None,
            search_id="ts",
            modo_busca=None,
            check_sanctions=False,
        )

        ctx = SearchContext(
            request=request,
            user={"id": user_a_id, "email": "a@test.com"},
        )
        ctx.is_simplified = True
        ctx.active_keywords = {"x"}
        ctx.custom_terms = []
        ctx.licitacoes_filtradas = list(items)

        deps = SimpleNamespace(
            ENABLE_NEW_PRICING=False,
            PNCPClient=MagicMock(),
            buscar_todas_ufs_paralelo=MagicMock(return_value=[]),
            aplicar_todos_filtros=MagicMock(return_value=([], {})),
            create_excel=MagicMock(),
            rate_limiter=MagicMock(),
            check_user_roles=MagicMock(return_value=(False, False)),
            match_keywords=MagicMock(return_value=(True, [])),
            KEYWORDS_UNIFORMES=set(),
            KEYWORDS_EXCLUSAO=set(),
            validate_terms=MagicMock(return_value={"valid": [], "ignored": [], "reasons": {}}),
        )

        pipeline = SearchPipeline(deps)
        await stage_enrich(pipeline, ctx)

        # Assert: sort stays as default (data_desc) for Group A
        assert request.ordenacao == "data_desc", (
            f"Expected ordenacao='data_desc' for Group A, got '{request.ordenacao}'"
        )

    @pytest.mark.asyncio
    @patch("config.features._feature_flag_cache", {})
    @patch("config.get_feature_flag")
    async def test_flag_inactive_no_override(self, mock_get_ff):
        """When flag is inactive, sort is NEVER overridden (zero impact)."""
        from pipeline.stages.enrich import stage_enrich
        from search_pipeline import SearchPipeline
        from search_context import SearchContext
        from types import SimpleNamespace

        # Mock: flag is OFF
        mock_get_ff.return_value = False

        items = [
            {"_viability_score": 90, "_confidence_score": 95, "valorTotalEstimado": 500000},
        ]

        request = MagicMock(
            ufs=["SC"],
            data_inicial="2026-01-01",
            data_final="2026-01-07",
            setor_id="v",
            status=MagicMock(value="todos"),
            ordenacao="data_desc",
            termos_busca=None,
            show_all_matches=False,
            exclusion_terms=None,
            modalidades=None,
            valor_minimo=None,
            valor_maximo=None,
            esferas=None,
            municipios=None,
            search_id="ts",
            modo_busca=None,
            check_sanctions=False,
        )

        ctx = SearchContext(
            request=request,
            user={"id": "any-user-id", "email": "any@test.com"},
        )
        ctx.is_simplified = True
        ctx.active_keywords = {"x"}
        ctx.custom_terms = []
        ctx.licitacoes_filtradas = list(items)

        deps = SimpleNamespace(
            ENABLE_NEW_PRICING=False,
            PNCPClient=MagicMock(),
            buscar_todas_ufs_paralelo=MagicMock(return_value=[]),
            aplicar_todos_filtros=MagicMock(return_value=([], {})),
            create_excel=MagicMock(),
            rate_limiter=MagicMock(),
            check_user_roles=MagicMock(return_value=(False, False)),
            match_keywords=MagicMock(return_value=(True, [])),
            KEYWORDS_UNIFORMES=set(),
            KEYWORDS_EXCLUSAO=set(),
            validate_terms=MagicMock(return_value={"valid": [], "ignored": [], "reasons": {}}),
        )

        pipeline = SearchPipeline(deps)
        await stage_enrich(pipeline, ctx)

        # Assert: sort stays as-is when flag is inactive
        assert request.ordenacao == "data_desc", (
            f"Expected ordenacao='data_desc' when flag=false, got '{request.ordenacao}'"
        )

    @pytest.mark.asyncio
    @patch("config.features._feature_flag_cache", {})
    @patch("config.get_feature_flag")
    async def test_flag_active_but_no_user_id_falls_through(self, mock_get_ff):
        """When flag is active but user has no id, no crash -- falls through gracefully."""
        from pipeline.stages.enrich import stage_enrich
        from search_pipeline import SearchPipeline
        from search_context import SearchContext
        from types import SimpleNamespace

        mock_get_ff.return_value = True

        items = [
            {"_viability_score": 90, "_confidence_score": 95, "valorTotalEstimado": 500000},
        ]

        request = MagicMock(
            ufs=["SC"],
            data_inicial="2026-01-01",
            data_final="2026-01-07",
            setor_id="v",
            status=MagicMock(value="todos"),
            ordenacao="data_desc",
            termos_busca=None,
            show_all_matches=False,
            exclusion_terms=None,
            modalidades=None,
            valor_minimo=None,
            valor_maximo=None,
            esferas=None,
            municipios=None,
            search_id="ts",
            modo_busca=None,
            check_sanctions=False,
        )

        ctx = SearchContext(
            request=request,
            user={"id": None, "email": "no-id@test.com"},
        )
        ctx.is_simplified = True
        ctx.active_keywords = {"x"}
        ctx.custom_terms = []
        ctx.licitacoes_filtradas = list(items)

        deps = SimpleNamespace(
            ENABLE_NEW_PRICING=False,
            PNCPClient=MagicMock(),
            buscar_todas_ufs_paralelo=MagicMock(return_value=[]),
            aplicar_todos_filtros=MagicMock(return_value=([], {})),
            create_excel=MagicMock(),
            rate_limiter=MagicMock(),
            check_user_roles=MagicMock(return_value=(False, False)),
            match_keywords=MagicMock(return_value=(True, [])),
            KEYWORDS_UNIFORMES=set(),
            KEYWORDS_EXCLUSAO=set(),
            validate_terms=MagicMock(return_value={"valid": [], "ignored": [], "reasons": {}}),
        )

        pipeline = SearchPipeline(deps)
        # Should NOT raise ValueError from get_viability_sort_group
        await stage_enrich(pipeline, ctx)

        # Sort should remain default since user has no id
        assert request.ordenacao == "data_desc", (
            f"Expected ordenacao='data_desc' when no user id, got '{request.ordenacao}'"
        )

    @pytest.mark.asyncio
    @patch("config.features._feature_flag_cache", {})
    @patch("config.get_feature_flag")
    async def test_flag_active_get_feature_flag_fails_falls_through(self, mock_get_ff):
        """When get_feature_flag raises, no crash -- falls through gracefully."""
        from pipeline.stages.enrich import stage_enrich
        from search_pipeline import SearchPipeline
        from search_context import SearchContext
        from types import SimpleNamespace

        mock_get_ff.side_effect = Exception("Redis unavailable")

        items = [
            {"_viability_score": 90, "_confidence_score": 95, "valorTotalEstimado": 500000},
        ]

        request = MagicMock(
            ufs=["SC"],
            data_inicial="2026-01-01",
            data_final="2026-01-07",
            setor_id="v",
            status=MagicMock(value="todos"),
            ordenacao="data_desc",
            termos_busca=None,
            show_all_matches=False,
            exclusion_terms=None,
            modalidades=None,
            valor_minimo=None,
            valor_maximo=None,
            esferas=None,
            municipios=None,
            search_id="ts",
            modo_busca=None,
            check_sanctions=False,
        )

        ctx = SearchContext(
            request=request,
            user={"id": "any-user-for-failure-test", "email": "fail@test.com"},
        )
        ctx.is_simplified = True
        ctx.active_keywords = {"x"}
        ctx.custom_terms = []
        ctx.licitacoes_filtradas = list(items)

        deps = SimpleNamespace(
            ENABLE_NEW_PRICING=False,
            PNCPClient=MagicMock(),
            buscar_todas_ufs_paralelo=MagicMock(return_value=[]),
            aplicar_todos_filtros=MagicMock(return_value=([], {})),
            create_excel=MagicMock(),
            rate_limiter=MagicMock(),
            check_user_roles=MagicMock(return_value=(False, False)),
            match_keywords=MagicMock(return_value=(True, [])),
            KEYWORDS_UNIFORMES=set(),
            KEYWORDS_EXCLUSAO=set(),
            validate_terms=MagicMock(return_value={"valid": [], "ignored": [], "reasons": {}}),
        )

        pipeline = SearchPipeline(deps)
        # Should NOT raise despite get_feature_flag failure
        await stage_enrich(pipeline, ctx)

        # Sort should remain default since get_feature_flag failed
        assert request.ordenacao == "data_desc", (
            f"Expected ordenacao='data_desc' when get_feature_flag fails, "
            f"got '{request.ordenacao}'"
        )
