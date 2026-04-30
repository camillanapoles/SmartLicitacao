"""Bot detection middleware — User-Agent based tier classification.

OBS-001: Classifies requests into tiers ('bot' | 'human') so callers can
apply differentiated rate limits via ``rate_limiter.check_rate_limit_tiered``.

Known bots covered:
    - Search engines: Googlebot, Bingbot, DuckDuckBot, Baiduspider, YandexBot, Yahoo Slurp
    - Social/Preview: facebookexternalhit, Twitterbot, LinkedInBot, Slackbot,
                      TelegramBot, DiscordBot, WhatsApp
    - SEO crawlers: AhrefsBot, SemrushBot, MJ12bot, DotBot, RogerBot
    - Generic: */crawler/*, */spider/*, */bot/*, scraperapi
    - HTTP libs: python-requests, curl, wget, libwww-perl

Memory: project_backend_outage_2026_04_29_stage5 — Googlebot wave saturated
backend in Stage 2/4/5 of the outage cycle. Bot vs human bucket isolation
prevents bot crawls from consuming human-tier quota.
"""
from __future__ import annotations

import re
from typing import Final

# Patterns are case-insensitive — match anywhere in User-Agent string.
_BOT_PATTERNS: Final = re.compile(
    r"(?i)("
    r"googlebot|bingbot|slurp|duckduckbot|baiduspider|yandexbot|"
    r"sogou|exabot|facebookexternalhit|twitterbot|linkedinbot|slackbot|"
    r"telegrambot|discordbot|whatsapp|"
    r"ahrefsbot|semrushbot|mj12bot|dotbot|rogerbot|"
    r"crawler|spider|bot/|/bot|scraperapi|http_request|python-requests|"
    r"curl/|wget/|libwww-perl"
    r")"
)


def is_bot(user_agent: str | None) -> bool:
    """Returns True when the User-Agent matches a known bot/crawler pattern.

    Empty or missing User-Agent is treated as bot (conservative default —
    legitimate browsers always send a UA).
    """
    if not user_agent:
        return True
    return bool(_BOT_PATTERNS.search(user_agent))


def classify_tier(user_agent: str | None) -> str:
    """Returns the tier label for a request: ``"bot"`` or ``"human"``."""
    return "bot" if is_bot(user_agent) else "human"
