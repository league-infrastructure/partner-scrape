"""Sponsor Extraction Cache: ``(team_id, content_hash(candidates)) ->
SponsorExtractionResult``.

Sprint 013 ticket 004. Mirrors -- again, duplicating rather than
importing (see ``sponsor_llm.py``'s module docstring for the full
zero-edges-into-``enrich/`` rationale) -- ``enrich/cache.py``'s
``schema_version``-guarded, content-hash-invalidated shape.

Persisted under ``SCRAPE_CACHE_DIR``, one JSON file per
``(team_id, content_hash(candidates))`` pair, hashed together into a
filesystem-safe filename the same way ``enrich/cache.py`` hashes an
Event's ``identity_key()``.

Unlike ``EnrichmentCache`` -- which is keyed by an Event's stable
*identity* and separately compares a freshly-computed content hash
against the stored one to detect staleness -- this cache's key **is**
the candidate list's content hash: a page's unrelated boilerplate
changing (a footer copyright year, an unrelated nav link) never
produces a different ``gather_sponsor_candidates()`` output and so never
changes the key, while an actual change to the *candidate set* produces
a different key outright, which is naturally a cache miss (no file at
that path) rather than a same-file staleness check. This is the
ticket's own stated design: "Keying on the candidate list's content hash
(not the raw page body's) means a page's unrelated boilerplate changing
... never forces a re-classification the candidate set itself didn't
change."

This module only stores and retrieves cache entries: it never calls the
LLM and never decides which candidates are real sponsors (both
``sponsor_extract.py``'s job, ticket 005).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from partner_scrape import config
from partner_scrape.teams.sponsor_llm import SponsorExtractionResult

#: Subdirectory of `SCRAPE_CACHE_DIR` entries are stored under.
_CACHE_SUBDIR = "sponsor_extraction_cache"

#: Bumped whenever `SponsorExtractionResult`'s shape changes, mirroring
#: `enrich/cache.py`'s `_CACHE_SCHEMA_VERSION` precedent (sprint 009
#: issue 13). `content_hash()` covers only the candidate list, so it
#: cannot detect a change to the *stored value's* shape -- a missing or
#: mismatched `schema_version` (including a pre-this-ticket entry with
#: no `schema_version` key at all) is treated as a miss, exactly like a
#: different candidate list, forcing exactly one re-classification per
#: affected entry.
_CACHE_SCHEMA_VERSION = 1


def content_hash(candidates: list[str]) -> str:
    """Compute a stable hash over ``candidates`` -- the exact list
    :meth:`~partner_scrape.teams.sponsor_llm.SponsorLLMClient.classify_sponsors`
    would be called with, and nothing else (not the raw page body, not
    the team's other fields). Order-sensitive: ``candidates`` is already
    a deterministic, discovery-ordered list by construction
    (``gather_sponsor_candidates``'s own contract), so two calls over an
    unchanged page produce an identical hash.
    """
    canonical = json.dumps(list(candidates))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _entry_filename(team_id: str, candidates: list[str]) -> str:
    """Hash ``(team_id, content_hash(candidates))`` into a
    filesystem-safe cache filename stem -- neither component is
    guaranteed filesystem-safe on its own (a candidate string can
    contain arbitrary characters scraped from a web page), so the pair
    is hashed rather than used directly as a path component, mirroring
    `enrich/cache.py`'s `_identity_key_filename` precedent.
    """
    canonical = f"{team_id}|{content_hash(candidates)}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _entry_path(cache_dir: Path, team_id: str, candidates: list[str]) -> Path:
    return cache_dir / _CACHE_SUBDIR / f"{_entry_filename(team_id, candidates)}.json"


def _result_to_jsonable(result: SponsorExtractionResult) -> dict[str, Any]:
    return asdict(result)


def _result_from_jsonable(data: dict[str, Any]) -> SponsorExtractionResult:
    return SponsorExtractionResult(confirmed_sponsors=data["confirmed_sponsors"])


class SponsorCache:
    """Persisted ``(team_id, content_hash(candidates)) ->
    SponsorExtractionResult`` map.

    One JSON file per key under ``{cache_dir}/sponsor_extraction_cache/``.
    ``cache_dir`` defaults to ``config.get_scrape_cache_dir()`` when
    omitted -- tests always pass an explicit ``tmp_path`` (this module's
    own tests, and ticket 005's ``extract_sponsors()`` tests, never touch
    the real configured cache directory).
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.cache_dir = cache_dir if cache_dir is not None else config.get_scrape_cache_dir()
        self._clock = clock

    def lookup(self, team_id: str, candidates: list[str]) -> SponsorExtractionResult | None:
        """Return the cached `SponsorExtractionResult` for
        ``(team_id, candidates)`` if an entry exists at the current
        schema version, else ``None`` -- no entry yet, a different
        candidate list (a different key, so naturally no file), or a
        stale/missing `schema_version`.
        """
        path = _entry_path(self.cache_dir, team_id, candidates)
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            entry = json.load(f)
        if entry.get("schema_version") != _CACHE_SCHEMA_VERSION:
            # Missing key (pre-this-ticket entry) or a stale version --
            # both are a miss, not a deserialization error. Forces
            # exactly one re-classification per affected entry.
            return None
        return _result_from_jsonable(entry["result"])

    def store(self, team_id: str, candidates: list[str], result: SponsorExtractionResult) -> None:
        """Write a fresh cache entry for ``(team_id, candidates)``."""
        path = _entry_path(self.cache_dir, team_id, candidates)
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "schema_version": _CACHE_SCHEMA_VERSION,
            "team_id": team_id,
            "content_hash": content_hash(candidates),
            "result": _result_to_jsonable(result),
            "cached_at": self._clock().isoformat(),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entry, f, indent=2)
