"""Fetch & Cache: polite, cache-aware retrieval of remote resources.

See sprint.md's Architecture > Fetch & Cache for the design: an
injectable ``Fetcher`` protocol built on stdlib ``urllib`` (not Scrapy,
not requests -- see Design Rationale), wrapped by ``PoliteFetcher`` with
a robots.txt check, per-domain rate limiting, and an on-disk
conditional-GET cache under ``Config.SCRAPE_CACHE_DIR``. This module
only retrieves and caches raw responses -- it never interprets them
(that's the Adapter Framework's job, ticket 004).
"""

from __future__ import annotations

from partner_scrape.fetch.cache import PoliteFetcher, cache_path, conditional_headers
from partner_scrape.fetch.fetcher import (
    DEFAULT_USER_AGENT,
    FetchResponse,
    Fetcher,
    UrllibFetcher,
)
from partner_scrape.fetch.robots import RobotsDisallowed, is_allowed
from partner_scrape.fetch.throttle import DEFAULT_RATE_LIMIT_SECONDS, Throttle

__all__ = [
    "PoliteFetcher",
    "Fetcher",
    "FetchResponse",
    "UrllibFetcher",
    "DEFAULT_USER_AGENT",
    "RobotsDisallowed",
    "is_allowed",
    "Throttle",
    "DEFAULT_RATE_LIMIT_SECONDS",
    "cache_path",
    "conditional_headers",
]
