"""Enrichment Cache: identity_key -> (content_hash, EnrichmentResult, enriched_at).

See sprint.md's Architecture > Enrichment Cache, Design Rationale ("the
Enrichment Cache is a new module, not reuse of Fetch & Cache's on-disk
cache"). Tracks which Events have already been enriched at their current
content so unchanged events skip a fresh LLM call -- cost control, per
SUC-011.

Persisted under `SCRAPE_CACHE_DIR`, one JSON file per Event
`identity_key()`, sharded the same way `fetch/cache.py` shards its
per-URL entries (hash the key into a filesystem-safe filename) --
`identity_key()` is a tuple, not a string, and its `external_id` variant
can contain characters that are not safe to use as a filename directly.

This module only stores and retrieves cache entries: it never calls the
LLM and never decides relevance (both `LLMEnricher`'s job, ticket 005's
other module). Content hash is computed over an Event's *enrichable*
fields only -- the fields `llm_client._build_user_prompt` actually reads
(title, description, start, end, all_day, location, cost,
registration_url, categories, tags) -- deliberately not the whole
Event, so unrelated field changes (classification fields this very
cache round-trips, or `field_provenance` bookkeeping) never force
spurious re-enrichment.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from partner_scrape import config
from partner_scrape.enrich.llm_client import EnrichmentResult
from partner_scrape.model import Event, IdentityKey

#: Subdirectory of `SCRAPE_CACHE_DIR` entries are stored under.
_CACHE_SUBDIR = "enrichment_cache"


def content_hash(event: Event) -> str:
    """Compute a stable hash over ``event``'s enrichable fields.

    Only the fields an LLM enrichment call actually reads (mirrors
    `llm_client._build_user_prompt`'s field list) -- not the whole
    Event -- so fields this cache itself round-trips
    (`areas_of_interest`, `relevant`, ...) or unrelated bookkeeping
    (`field_provenance`) never change the hash.
    """
    payload = {
        "title": event.title,
        "description": event.description,
        "start": event.start.isoformat() if event.start is not None else None,
        "end": event.end.isoformat() if event.end is not None else None,
        "all_day": event.all_day,
        "location": event.location,
        "cost": event.cost,
        "registration_url": event.registration_url,
        "categories": event.categories,
        "tags": event.tags,
    }
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _identity_key_filename(identity_key: IdentityKey) -> str:
    """Hash ``identity_key`` into a filesystem-safe cache filename stem.

    ``identity_key()`` is a tuple ((source_id, external_id) or
    (source_id, normalized_title, start_date)) -- not a string, and
    `external_id` values are not guaranteed to be filesystem-safe, so
    (like `fetch/cache.py`'s URL-keyed entries) the key is hashed rather
    than used directly as a path component.
    """
    canonical = "|".join(str(part) for part in identity_key)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _entry_path(cache_dir: Path, identity_key: IdentityKey) -> Path:
    return cache_dir / _CACHE_SUBDIR / f"{_identity_key_filename(identity_key)}.json"


def _result_to_jsonable(result: EnrichmentResult) -> dict[str, Any]:
    data = asdict(result)
    data["start"] = result.start.isoformat() if result.start is not None else None
    data["end"] = result.end.isoformat() if result.end is not None else None
    return data


def _result_from_jsonable(data: dict[str, Any]) -> EnrichmentResult:
    return EnrichmentResult(
        start=datetime.fromisoformat(data["start"]) if data["start"] is not None else None,
        end=datetime.fromisoformat(data["end"]) if data["end"] is not None else None,
        all_day=data["all_day"],
        location=data["location"],
        cost=data["cost"],
        registration_url=data["registration_url"],
        areas_of_interest=data["areas_of_interest"],
        age_grade_level=data["age_grade_level"],
        cost_range=data["cost_range"],
        time_of_day=data["time_of_day"],
        relevant=data["relevant"],
        relevance_reason=data["relevance_reason"],
    )


class EnrichmentCache:
    """Persisted `identity_key -> (content_hash, EnrichmentResult, enriched_at)` map.

    One JSON file per Event `identity_key()` under
    `{cache_dir}/enrichment_cache/`. `cache_dir` defaults to
    `config.get_scrape_cache_dir()` when omitted -- tests always pass an
    explicit `tmp_path` (this module's own tests, and ticket 005's
    `LLMEnricher` tests, never touch the real configured cache
    directory).
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.cache_dir = cache_dir if cache_dir is not None else config.get_scrape_cache_dir()
        self._clock = clock

    def lookup(self, event: Event) -> EnrichmentResult | None:
        """Return the cached `EnrichmentResult` for ``event`` if its
        current content hash matches the cached entry's, else ``None``
        (no cache entry yet, or the Event's enrichable content changed
        since it was cached).
        """
        path = _entry_path(self.cache_dir, event.identity_key())
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            entry = json.load(f)
        if entry["content_hash"] != content_hash(event):
            return None
        return _result_from_jsonable(entry["result"])

    def store(self, event: Event, result: EnrichmentResult) -> None:
        """Write a fresh cache entry for ``event`` at its current content hash."""
        path = _entry_path(self.cache_dir, event.identity_key())
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "content_hash": content_hash(event),
            "result": _result_to_jsonable(result),
            "enriched_at": self._clock().isoformat(),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entry, f, indent=2)
