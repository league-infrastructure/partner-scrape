"""Program Extraction Cache: (url, content_hash) -> ProgramExtractionResult.

Sprint 027 ticket 002. Mirrors ``enrich/cache.py``'s on-disk shape (one
JSON file per key, sharded via a hash of the key into a filesystem-safe
filename) and its ``content_hash`` convention, but keys on a page's raw
URL + body content hash rather than an ``Event``'s ``identity_key()`` --
there is no ``Event`` yet at fetch time for a program page, only a URL and
a fetched body. See ``adapters/DESIGN.md``'s sprint 027 section for the
full rationale, including why this is a separate cache/module rather than
a reuse of ``enrich.cache.EnrichmentCache``.

Unlike ``enrich/cache.py``'s deliberately single-threaded writes
(concurrency across sources only, via ``pipeline.py``'s per-source
``ThreadPoolExecutor``), concurrent writes here are safe by construction
without that same restriction: every cache key is a distinct URL+hash, so
two threads can only ever write two different files, never the same path.

This module only stores and retrieves cache entries: it never calls the
LLM and never decides anything about program eligibility or display --
that is ``adapters/program_page.py``/``adapters/program_listing.py``'s job
(tickets 003/004).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from partner_scrape import config
from partner_scrape.adapters.program_llm import ProgramExtractionResult

#: Subdirectory of ``SCRAPE_CACHE_DIR`` entries are stored under.
_CACHE_SUBDIR = "program_extraction_cache"

#: Bumped whenever ``ProgramExtractionResult``'s shape changes, or when
#: this cache's own on-disk entry shape changes. ``content_hash`` covers
#: only the page's raw body, never the result's own shape, so it cannot
#: detect a stored-value shape change on its own -- mirrors
#: ``enrich/cache.py``'s ``_CACHE_SCHEMA_VERSION`` convention and
#: rationale exactly. **(Ticket 006 exception revision)** bumped 1 -> 2
#: for the new list-valued ``lookup_many``/``store_many`` entry shape
#: (``"results"`` alongside the existing ``"result"`` key) -- forces
#: exactly one harmless re-extraction of any pre-revision cache entry, a
#: cache being a pure optimization (see ``adapters/DESIGN.md``'s Revision
#: note).
_CACHE_SCHEMA_VERSION = 2


def content_hash(body: str) -> str:
    """Compute a stable hash over a program page's raw ``body`` text.

    Analogous to ``enrich/cache.py``'s ``content_hash(event)``, but over
    the raw page text a program-page extraction call actually reads,
    rather than an ``Event``'s enrichable fields (there is no ``Event``
    yet at fetch time).
    """
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _url_filename(url: str) -> str:
    """Hash ``url`` into a filesystem-safe cache filename stem.

    URLs, like ``Event`` identity keys, can contain characters that are
    not safe to use as a filename directly -- mirrors ``enrich/cache.py``'s
    ``_identity_key_filename`` convention.
    """
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _entry_path(cache_dir: Path, url: str) -> Path:
    return cache_dir / _CACHE_SUBDIR / f"{_url_filename(url)}.json"


def _result_to_jsonable(result: ProgramExtractionResult) -> dict[str, Any]:
    return asdict(result)


def _result_from_jsonable(data: dict[str, Any]) -> ProgramExtractionResult:
    return ProgramExtractionResult(
        program_name=data["program_name"],
        audience_grades=data["audience_grades"],
        date_start=data["date_start"],
        date_end=data["date_end"],
        cost=data["cost"],
        eligibility=data["eligibility"],
        is_open=data["is_open"],
        opportunity_type=data["opportunity_type"],
    )


class ProgramExtractionCache:
    """Persisted ``url -> (content_hash, ProgramExtractionResult)`` map.

    One JSON file per URL under ``{cache_dir}/program_extraction_cache/``.
    ``cache_dir`` defaults to ``config.get_scrape_cache_dir()`` when
    omitted -- tests always pass an explicit ``tmp_path``.
    """

    def __init__(self, cache_dir: Path | None = None) -> None:
        self.cache_dir = cache_dir if cache_dir is not None else config.get_scrape_cache_dir()

    def lookup(self, url: str, body: str) -> ProgramExtractionResult | None:
        """Return the cached ``ProgramExtractionResult`` for ``url`` if its
        current content hash matches the cached entry's, else ``None``
        (no cache entry yet, or the page changed since it was last
        cached).
        """
        path = _entry_path(self.cache_dir, url)
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            entry = json.load(f)
        if entry.get("schema_version") != _CACHE_SCHEMA_VERSION:
            # Missing key or a stale version -- both are a miss, not a
            # deserialization error. Forces exactly one re-extraction.
            return None
        if entry.get("content_hash") != content_hash(body):
            return None
        return _result_from_jsonable(entry["result"])

    def store(self, url: str, body: str, result: ProgramExtractionResult) -> None:
        """Write a fresh cache entry for ``url`` at its current content hash."""
        path = _entry_path(self.cache_dir, url)
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "schema_version": _CACHE_SCHEMA_VERSION,
            "content_hash": content_hash(body),
            "result": _result_to_jsonable(result),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entry, f, indent=2)

    def lookup_many(self, url: str, body: str) -> list[ProgramExtractionResult] | None:
        """The list-valued counterpart to :meth:`lookup`, for
        ``program_page_multi`` sources (ticket 006 exception revision).

        Same URL + content-hash keying as :meth:`lookup`; returns
        ``None`` for no entry, a stale ``schema_version``, or a changed
        content hash -- identical miss conditions, applied to the
        list-shaped entry :meth:`store_many` writes.
        """
        path = _entry_path(self.cache_dir, url)
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            entry = json.load(f)
        if entry.get("schema_version") != _CACHE_SCHEMA_VERSION:
            return None
        if entry.get("content_hash") != content_hash(body):
            return None
        results = entry.get("results")
        if results is None:
            return None
        return [_result_from_jsonable(r) for r in results]

    def store_many(self, url: str, body: str, results: list[ProgramExtractionResult]) -> None:
        """The list-valued counterpart to :meth:`store`, for
        ``program_page_multi`` sources (ticket 006 exception revision).

        Writes a JSON list (``"results"``) instead of a single object
        (``"result"``) under the same URL-hashed cache file
        :meth:`store` would use for a ``program_page``/``program_listing``
        source -- safe by construction, since a real URL is only ever
        registered as one adapter type.
        """
        path = _entry_path(self.cache_dir, url)
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "schema_version": _CACHE_SCHEMA_VERSION,
            "content_hash": content_hash(body),
            "results": [_result_to_jsonable(r) for r in results],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entry, f, indent=2)
