"""On-disk response cache, conditional-GET header construction, and the
``PoliteFetcher`` orchestrator.

Cache layout: one JSON file per URL, domain-sharded --
``{cache_dir}/{domain}/{sha256(url)}.json`` -- containing
``{url, status, headers, body, fetched_at}``. One file per URL keeps the
format simple enough to inspect by hand, which matters for debugging a
live source later (see sprint.md's Implementation Plan for this
ticket).

``PoliteFetcher`` is this package's public entry point: it composes an
injectable ``Fetcher`` with a robots.txt check, per-domain rate
limiting, and this cache, in the order SUC-002's Main Flow describes.
Ticket 004's adapters call ``PoliteFetcher.get(...)`` and never touch
``UrllibFetcher``, ``Throttle``, or these cache functions directly.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from partner_scrape import config
from partner_scrape.fetch.fetcher import DEFAULT_USER_AGENT, FetchResponse, Fetcher, UrllibFetcher
from partner_scrape.fetch.robots import RobotsDisallowed, is_allowed
from partner_scrape.fetch.throttle import DEFAULT_RATE_LIMIT_SECONDS, Throttle


def domain_of(url: str) -> str:
    """Return the hostname component of ``url`` (no scheme, no port)."""
    return urlparse(url).hostname or "unknown"


def _cache_key(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def cache_path(cache_dir: Path, url: str) -> Path:
    """The on-disk path a given URL's cache entry lives (or would live) at."""
    return cache_dir / domain_of(url) / f"{_cache_key(url)}.json"


def read_cache_entry(cache_dir: Path, url: str) -> dict[str, Any] | None:
    """Read ``url``'s cache entry, or ``None`` if it has never been cached."""
    path = cache_path(cache_dir, url)
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_cache_entry(cache_dir: Path, url: str, response: FetchResponse) -> None:
    """Write ``response`` as ``url``'s cache entry, creating parent dirs."""
    path = cache_path(cache_dir, url)
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "url": response.url,
        "status": response.status,
        "headers": response.headers,
        "body": response.body,
        "fetched_at": response.fetched_at.isoformat(),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entry, f, indent=2)


def touch_fetch_timestamp(cache_dir: Path, url: str, fetched_at: datetime) -> None:
    """Bump only the cached entry's ``fetched_at`` -- used on a 304 reply,
    where the body/headers are still current and must not be rewritten.

    A no-op if ``url`` has no cache entry (nothing to touch).
    """
    entry = read_cache_entry(cache_dir, url)
    if entry is None:
        return
    entry["fetched_at"] = fetched_at.isoformat()
    with open(cache_path(cache_dir, url), "w", encoding="utf-8") as f:
        json.dump(entry, f, indent=2)


def entry_to_response(entry: dict[str, Any]) -> FetchResponse:
    """Reconstruct a ``FetchResponse`` from a cache entry dict."""
    return FetchResponse(
        url=entry["url"],
        status=entry["status"],
        headers=entry["headers"],
        body=entry["body"],
        fetched_at=datetime.fromisoformat(entry["fetched_at"]),
    )


def _header(headers: dict[str, str], name: str) -> str | None:
    """Case-insensitive header lookup -- HTTP header names are
    case-insensitive, but a JSON-round-tripped dict is just a plain
    dict with whatever casing the server sent.
    """
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return None


def conditional_headers(entry: dict[str, Any] | None) -> dict[str, str]:
    """Build ``If-None-Match``/``If-Modified-Since`` headers from a cached
    entry's stored response headers, for a conditional GET.

    Returns ``{}`` when there is no cached entry, or the cached entry
    has neither an ``ETag`` nor a ``Last-Modified`` header.
    """
    if entry is None:
        return {}
    headers = entry.get("headers", {})
    conditional: dict[str, str] = {}
    etag = _header(headers, "ETag")
    if etag:
        conditional["If-None-Match"] = etag
    last_modified = _header(headers, "Last-Modified")
    if last_modified:
        conditional["If-Modified-Since"] = last_modified
    return conditional


class PoliteFetcher:
    """Fetch & Cache's public entry point: robots.txt + rate limit + cache.

    Composes an injectable ``Fetcher`` (defaults to ``UrllibFetcher``)
    with a robots.txt permission check, a per-domain ``Throttle``, and
    an on-disk conditional-GET cache under ``cache_dir``.

    ``rate_limit_seconds`` and ``respect_robots`` are accepted per call
    as plain values rather than read from a ``SourceConfig`` here --
    this module has no dependency on the Registry (see sprint.md's
    Component & Dependency Diagram: Fetch & Cache depends only on
    Config). Callers that have a ``SourceConfig`` (ticket 004's
    adapters) pull the values out of its ``acquisition_policy`` dict
    themselves.

    ``cache_dir`` defaults to ``config.get_scrape_cache_dir()`` when
    omitted -- the "FETCH reads cache dir from CFG" edge in sprint.md's
    dependency diagram. Tests always pass ``cache_dir`` explicitly (a
    ``tmp_path``) or monkeypatch ``SCRAPE_CACHE_DIR`` first; neither
    path ever touches the real configured cache directory.
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        fetcher: Fetcher | None = None,
        throttle: Throttle | None = None,
        user_agent: str = DEFAULT_USER_AGENT,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self.cache_dir = cache_dir if cache_dir is not None else config.get_scrape_cache_dir()
        self.fetcher = fetcher or UrllibFetcher(user_agent=user_agent)
        self.throttle = throttle or Throttle()
        self.user_agent = user_agent
        self._clock = clock

    def get(
        self,
        url: str,
        rate_limit_seconds: float = DEFAULT_RATE_LIMIT_SECONDS,
        respect_robots: bool = True,
    ) -> FetchResponse:
        """Politely, cache-aware-ly retrieve ``url``.

        Raises:
            RobotsDisallowed: ``respect_robots`` is true and ``url`` is
                disallowed by its site's robots.txt. Raised before the
                target URL itself is ever requested.
        """
        if respect_robots and not is_allowed(url, self.fetcher, self.user_agent):
            raise RobotsDisallowed(
                f"{url} is disallowed by robots.txt for {self.user_agent!r}"
            )

        cached_entry = read_cache_entry(self.cache_dir, url)
        headers = conditional_headers(cached_entry)

        self.throttle.wait(domain_of(url), rate_limit_seconds)
        response = self.fetcher.get(url, headers=headers)

        if response.status == 304 and cached_entry is not None:
            fetched_at = self._clock()
            touch_fetch_timestamp(self.cache_dir, url, fetched_at)
            reused = entry_to_response(cached_entry)
            reused.fetched_at = fetched_at
            return reused

        if 200 <= response.status < 300:
            response.fetched_at = self._clock()
            write_cache_entry(self.cache_dir, url, response)
            return response

        return response
