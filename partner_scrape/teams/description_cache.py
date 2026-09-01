"""Description Extraction Cache: ``(team_id, content_hash(content)) ->
DescriptionExtractionResult``.

Sprint 021 ticket 003. Mirrors -- again, duplicating rather than
importing (see ``description_llm.py``'s module docstring for the full
zero-edges-into-``enrich/`` rationale, and ``sponsor_cache.py``'s own
docstring for the original statement of it) --
``teams/sponsor_cache.py``'s ``schema_version``-guarded,
content-hash-invalidated shape.

Persisted under ``SCRAPE_CACHE_DIR``, one JSON file per
``(team_id, content_hash(content))`` pair, hashed together into a
filesystem-safe filename the same way ``sponsor_cache.py`` hashes
``(team_id, content_hash(candidates))``.

Keyed on the gathered *content string's* own hash (not the raw page
body's, and not a separately-tracked identity with a staleness compare
like ``EnrichmentCache``'s Event-identity shape) -- a page's unrelated
boilerplate changing (a footer copyright year, an unrelated nav link)
never changes ticket 002's ``gather_description_content()`` output and
so never changes this cache's key, while an actual change to the
*gathered content* produces a different key outright, which is
naturally a cache miss (no file at that path) rather than a same-file
staleness check. This is the ticket's own stated design: "Keying on the
gathered content's own hash (not the raw page body's) means unrelated
page changes (a footer copyright year) never force re-summarization --
identical to ``sponsor_cache.py``'s own stated design."

This module only stores and retrieves cache entries: it never calls the
LLM and never decides what a team's description should say (both
``description_extract.py``'s job, ticket 004).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from partner_scrape import config
from partner_scrape.teams.description_llm import DescriptionExtractionResult

#: Subdirectory of `SCRAPE_CACHE_DIR` entries are stored under.
_CACHE_SUBDIR = "description_extraction_cache"

#: Bumped whenever `DescriptionExtractionResult`'s shape changes,
#: mirroring `sponsor_cache._CACHE_SCHEMA_VERSION`'s precedent (itself
#: mirroring `enrich/cache.py`'s `_CACHE_SCHEMA_VERSION`, sprint 009
#: issue 13). `content_hash()` covers only the gathered content string,
#: so it cannot detect a change to the *stored value's* shape -- a
#: missing or mismatched `schema_version` (including a pre-this-ticket
#: entry with no `schema_version` key at all) is treated as a miss,
#: exactly like a different content string, forcing exactly one
#: re-summarization per affected entry.
_CACHE_SCHEMA_VERSION = 1


def content_hash(content: str) -> str:
    """Compute a stable hash over ``content`` -- the exact string
    :meth:`~partner_scrape.teams.description_llm.DescriptionLLMClient.summarize_description`
    would be called with, and nothing else (not the raw page body, not
    the team's other fields). ``content`` is already a deterministic
    function of a fetched page's HTML (``gather_description_content``'s
    own contract), so two calls over an unchanged page produce an
    identical hash.
    """
    canonical = json.dumps(content)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _entry_filename(team_id: str, content: str) -> str:
    """Hash ``(team_id, content_hash(content))`` into a filesystem-safe
    cache filename stem -- neither component is guaranteed
    filesystem-safe on its own (``content`` can contain arbitrary
    characters scraped from a web page), so the pair is hashed rather
    than used directly as a path component, mirroring
    `sponsor_cache._entry_filename`'s precedent.
    """
    canonical = f"{team_id}|{content_hash(content)}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _entry_path(cache_dir: Path, team_id: str, content: str) -> Path:
    return cache_dir / _CACHE_SUBDIR / f"{_entry_filename(team_id, content)}.json"


def _result_to_jsonable(result: DescriptionExtractionResult) -> dict[str, Any]:
    return asdict(result)


def _result_from_jsonable(data: dict[str, Any]) -> DescriptionExtractionResult:
    return DescriptionExtractionResult(description=data["description"])


class DescriptionCache:
    """Persisted ``(team_id, content_hash(content)) ->
    DescriptionExtractionResult`` map.

    One JSON file per key under
    ``{cache_dir}/description_extraction_cache/``. ``cache_dir``
    defaults to ``config.get_scrape_cache_dir()`` when omitted -- tests
    always pass an explicit ``tmp_path`` (this module's own tests, and
    ticket 004's ``extract_descriptions()`` tests, never touch the real
    configured cache directory).
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.cache_dir = cache_dir if cache_dir is not None else config.get_scrape_cache_dir()
        self._clock = clock

    def lookup(self, team_id: str, content: str) -> DescriptionExtractionResult | None:
        """Return the cached `DescriptionExtractionResult` for
        ``(team_id, content)`` if an entry exists at the current schema
        version, else ``None`` -- no entry yet, different gathered
        content (a different key, so naturally no file), or a
        stale/missing `schema_version`.
        """
        path = _entry_path(self.cache_dir, team_id, content)
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            entry = json.load(f)
        if entry.get("schema_version") != _CACHE_SCHEMA_VERSION:
            # Missing key (pre-this-ticket entry) or a stale version --
            # both are a miss, not a deserialization error. Forces
            # exactly one re-summarization per affected entry.
            return None
        return _result_from_jsonable(entry["result"])

    def store(self, team_id: str, content: str, result: DescriptionExtractionResult) -> None:
        """Write a fresh cache entry for ``(team_id, content)``."""
        path = _entry_path(self.cache_dir, team_id, content)
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "schema_version": _CACHE_SCHEMA_VERSION,
            "team_id": team_id,
            "content_hash": content_hash(content),
            "result": _result_to_jsonable(result),
            "cached_at": self._clock().isoformat(),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entry, f, indent=2)
