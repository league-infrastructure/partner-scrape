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
from partner_scrape.storage import LocalStore, Store

#: Subdirectory of ``SCRAPE_CACHE_DIR`` entries are stored under.
_CACHE_SUBDIR = "programs"

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
#: note). **(Sprint 029 ticket 006)** bumped 2 -> 3 for
#: ``registration_deadline``'s addition to ``ProgramExtractionResult`` --
#: load-bearing here, not only tidy: tickets 001/002's real dry-runs
#: already populated cache entries for this revision's affected
#: competition sources under the old, now-corrected prompt; without this
#: bump, ticket 007's re-verification would read those stale entries
#: back and never invoke the corrected prompt at all.
_CACHE_SCHEMA_VERSION = 3


def content_hash(body: str) -> str:
    """Compute a stable hash over a program page's raw ``body`` text.

    Analogous to ``enrich/cache.py``'s ``content_hash(event)``, but over
    the raw page text a program-page extraction call actually reads,
    rather than an ``Event``'s enrichable fields (there is no ``Event``
    yet at fetch time).
    """
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _entry_filename(url: str, profile: str) -> str:
    """Hash ``(url, profile)`` into a filesystem-safe cache filename stem.

    URLs, like ``Event`` identity keys, can contain characters that are
    not safe to use as a filename directly -- mirrors ``enrich/cache.py``'s
    ``_identity_key_filename`` convention. The extraction ``profile``
    (``"program"``/``"competition"``/``"pd"``) is part of the key (sprint
    038, issue 42): the same URL and body extracted under two profiles
    are two distinct entries. There is deliberately no fallback read of
    the pre-038 profile-less key; those entries simply miss once.
    """
    canonical = f"{url}|{profile}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _entry_key(url: str, profile: str) -> str:
    return f"{_CACHE_SUBDIR}/{_entry_filename(url, profile)}.json"


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
        registration_deadline=data["registration_deadline"],
    )


class ProgramExtractionCache:
    """Persisted ``(url, profile) -> (content_hash, ProgramExtractionResult)`` map.

    One JSON file per ``(url, profile)`` under ``programs/`` in the
    scrape-cache Store: ``cache_dir`` (wrapped in a ``LocalStore``) when
    given, else ``config.get_scrape_cache_store()`` -- tests always pass
    an explicit ``tmp_path``.
    """

    def __init__(self, cache_dir: Path | None = None) -> None:
        self._store: Store = (
            LocalStore(cache_dir) if cache_dir is not None else config.get_scrape_cache_store()
        )

    def lookup(self, url: str, body: str, profile: str = "program") -> ProgramExtractionResult | None:
        """Return the cached ``ProgramExtractionResult`` for ``url`` if its
        current content hash matches the cached entry's, else ``None``
        (no cache entry yet, or the page changed since it was last
        cached).
        """
        entry = self._store.read_json(_entry_key(url, profile))
        if entry is None:
            return None
        if entry.get("schema_version") != _CACHE_SCHEMA_VERSION:
            # Missing key or a stale version -- both are a miss, not a
            # deserialization error. Forces exactly one re-extraction.
            return None
        if entry.get("content_hash") != content_hash(body):
            return None
        return _result_from_jsonable(entry["result"])

    def store(
        self, url: str, body: str, result: ProgramExtractionResult, profile: str = "program"
    ) -> None:
        """Write a fresh cache entry for ``url`` at its current content hash."""
        entry = {
            "schema_version": _CACHE_SCHEMA_VERSION,
            "content_hash": content_hash(body),
            "result": _result_to_jsonable(result),
        }
        # json.dumps defaults (ensure_ascii) + indent=2, byte-identical to
        # the files written before the Store existed.
        self._store.write_text(_entry_key(url, profile), json.dumps(entry, indent=2), "application/json")

    def lookup_many(
        self, url: str, body: str, profile: str = "program"
    ) -> list[ProgramExtractionResult] | None:
        """The list-valued counterpart to :meth:`lookup`, for
        ``program_page_multi`` sources (ticket 006 exception revision).

        Same URL + content-hash keying as :meth:`lookup`; returns
        ``None`` for no entry, a stale ``schema_version``, or a changed
        content hash -- identical miss conditions, applied to the
        list-shaped entry :meth:`store_many` writes.
        """
        entry = self._store.read_json(_entry_key(url, profile))
        if entry is None:
            return None
        if entry.get("schema_version") != _CACHE_SCHEMA_VERSION:
            return None
        if entry.get("content_hash") != content_hash(body):
            return None
        results = entry.get("results")
        if results is None:
            return None
        return [_result_from_jsonable(r) for r in results]

    def store_many(
        self,
        url: str,
        body: str,
        results: list[ProgramExtractionResult],
        profile: str = "program",
    ) -> None:
        """The list-valued counterpart to :meth:`store`, for
        ``program_page_multi`` sources (ticket 006 exception revision).

        Writes a JSON list (``"results"``) instead of a single object
        (``"result"``) under the same URL-hashed cache file
        :meth:`store` would use for a ``program_page``/``program_listing``
        source -- safe by construction, since a real URL is only ever
        registered as one adapter type.
        """
        entry = {
            "schema_version": _CACHE_SCHEMA_VERSION,
            "content_hash": content_hash(body),
            "results": [_result_to_jsonable(r) for r in results],
        }
        # json.dumps defaults (ensure_ascii) + indent=2, byte-identical to
        # the files written before the Store existed.
        self._store.write_text(_entry_key(url, profile), json.dumps(entry, indent=2), "application/json")
