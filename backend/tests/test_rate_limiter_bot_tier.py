"""Tests for OBS-001 — Bot rate-limit tier middleware.

Covers:
    - User-Agent classification (is_bot / classify_tier)
    - Tiered rate limiter (bot vs human bucket isolation)

Memory: project_backend_outage_2026_04_29_stage5 — Googlebot wave saturated
perfil/orgao/contratos publicos endpoints. Tier isolation is the structural
fix.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from bot_detection import classify_tier, is_bot


class TestBotDetection:
    """User-Agent pattern matching for bot tier classification."""

    @pytest.mark.parametrize(
        "ua,expected",
        [
            # Search-engine crawlers
            (
                "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
                True,
            ),
            ("Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)", True),
            ("DuckDuckBot/1.0", True),
            ("Mozilla/5.0 (compatible; YandexBot/3.0)", True),
            ("Baiduspider/2.0", True),
            # SEO crawlers
            ("Mozilla/5.0 (compatible; AhrefsBot/7.0)", True),
            ("Mozilla/5.0 (compatible; SemrushBot/7~bl)", True),
            ("MJ12bot/v1.4.8", True),
            # Social-media preview bots
            ("facebookexternalhit/1.1", True),
            ("Twitterbot/1.0", True),
            ("LinkedInBot/1.0", True),
            # HTTP libraries / scripts
            ("python-requests/2.31.0", True),
            ("curl/8.5.0", True),
            ("Wget/1.21.4", True),
            # Real human browsers
            (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
                "(KHTML, like Gecko) Version/17.2 Safari/605.1.15",
                False,
            ),
            (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                False,
            ),
            (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
                False,
            ),
            # Edge cases — empty/None default to bot (conservative)
            ("", True),
            (None, True),
        ],
    )
    def test_is_bot(self, ua, expected):
        assert is_bot(ua) is expected

    def test_classify_tier_bot(self):
        assert classify_tier("Googlebot/2.1") == "bot"
        assert classify_tier("python-requests/2.31") == "bot"

    def test_classify_tier_human(self):
        assert (
            classify_tier(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/121.0"
            )
            == "human"
        )

    def test_classify_tier_empty_defaults_to_bot(self):
        assert classify_tier(None) == "bot"
        assert classify_tier("") == "bot"


@pytest.mark.asyncio
class TestTieredRateLimit:
    """Tiered rate limiter: bot vs human bucket isolation + tier-specific limits."""

    @patch("rate_limiter.get_redis_pool", new_callable=AsyncMock, return_value=None)
    async def test_returns_allowed_under_limit_human(self, _mock_pool):
        from rate_limiter import check_rate_limit_tiered

        allowed, tier, retry_after = await check_rate_limit_tiered(
            "user-123",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/121.0",
        )
        assert allowed is True
        assert tier == "human"
        assert retry_after == 0

    @patch("rate_limiter.get_redis_pool", new_callable=AsyncMock, return_value=None)
    async def test_returns_allowed_under_limit_bot(self, _mock_pool):
        from rate_limiter import check_rate_limit_tiered

        allowed, tier, retry_after = await check_rate_limit_tiered(
            "user-123", "Googlebot/2.1"
        )
        assert allowed is True
        assert tier == "bot"
        assert retry_after == 0

    @patch("rate_limiter.get_redis_pool", new_callable=AsyncMock, return_value=None)
    async def test_bot_and_human_have_separate_buckets(self, _mock_pool):
        """Bot exhaustion must NOT affect human quota — bucket isolation."""
        from rate_limiter import (
            BOT_RATE_LIMIT_PER_MINUTE,
            check_rate_limit_tiered,
        )

        # Drain the bot bucket for this identifier
        for _ in range(BOT_RATE_LIMIT_PER_MINUTE):
            allowed, tier, _ = await check_rate_limit_tiered(
                "user-iso", "Googlebot/2.1"
            )
            assert allowed is True
            assert tier == "bot"

        # One more bot request — should be throttled
        allowed_bot, tier_bot, retry_bot = await check_rate_limit_tiered(
            "user-iso", "Googlebot/2.1"
        )
        assert allowed_bot is False
        assert tier_bot == "bot"
        assert retry_bot >= 1

        # But a human request with the SAME identifier must still be allowed —
        # different bucket key (rl:bot:* vs rl:human:*).
        allowed_human, tier_human, retry_human = await check_rate_limit_tiered(
            "user-iso",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/121.0",
        )
        assert allowed_human is True
        assert tier_human == "human"
        assert retry_human == 0

    @patch("rate_limiter.get_redis_pool", new_callable=AsyncMock, return_value=None)
    async def test_bot_limit_lower_than_human_limit(self, _mock_pool):
        """By default bot tier (10/min) is more restrictive than human (60/min)."""
        from rate_limiter import (
            BOT_RATE_LIMIT_PER_MINUTE,
            HUMAN_RATE_LIMIT_PER_MINUTE,
        )

        assert BOT_RATE_LIMIT_PER_MINUTE <= HUMAN_RATE_LIMIT_PER_MINUTE
