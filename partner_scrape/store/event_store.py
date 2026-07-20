"""Event Store: a durable, cross-run table of canonical Events.

This is the foundation for incremental/self-updating scraping: unlike
`enrich/cache.py`'s per-Event enrichment-skip cache (keyed the same way,
but only remembering "did we already enrich this content"), the Event
Store keeps the *canonical Event itself*, accumulated across every run,
so a future run can ask "what do we already know" before re-crawling.

This module deliberately does not decide what "the current dataset"
looks like -- no cross-source dedup, no collapsing, no upcoming-only
filtering. That is `normalize/`'s job (`normalize/collapse.py`,
`normalize/dedup.py`), applied to whatever `all_events()` returns. The
store's only opinions are about *identity* (which row a given Event
belongs to, mirroring `model.Event.identity_key()`) and *lifecycle*
(when a row is stale enough to prune) -- see `prune_past` and
`prune_unseen`.

Rows are keyed by a hash of `Event.identity_key()`, the same
"have we already seen this exact record from this source" identity
`enrich/cache.py` uses, hashed the same way (`_identity_key_filename`'s
approach, mirrored here as `_identity_hash`) since `identity_key()` is a
tuple -- not something SQLite can use as a primary key directly -- and
`external_id` values are not guaranteed to be safe/short strings anyway.

Each row also carries `content_hash` (reusing `enrich.cache.content_hash`
verbatim, not reimplemented, so the two caches' notion of "did the
meaningful content change" never drifts apart) and `first_seen` /
`last_seen` timestamps that track a row's acquisition lifecycle
independently of its content.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

from partner_scrape import config
from partner_scrape.enrich.cache import content_hash
from partner_scrape.model import Event, IdentityKey, Provenance

#: Default filename (under `config.get_scrape_cache_dir()`) for the store's
#: SQLite database when no explicit ``db_path`` is given.
_DEFAULT_DB_FILENAME = "events.db"

#: Sentinel accepted (alongside a real filesystem path) so tests and
#: callers can request an in-memory, non-persistent database.
_MEMORY_DB = ":memory:"

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS events (
    identity TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    data TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL
)
"""


def _identity_hash(identity_key: IdentityKey) -> str:
    """Hash ``identity_key`` into a stable primary-key string.

    Mirrors `enrich/cache.py`'s `_identity_key_filename`: `identity_key()`
    is a tuple, not a string, and its `external_id` variant is not
    guaranteed to be safe to use directly as a SQL key, so the key is
    hashed rather than joined-and-used-as-is.
    """
    canonical = "|".join(str(part) for part in identity_key)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _event_to_dict(event: Event) -> dict[str, Any]:
    """Serialize ``event`` to a JSON-able dict covering every Event field.

    Datetimes become ISO strings; `field_provenance`'s `Provenance`
    values become plain `{"source": ..., "confidence": ...}` dicts. See
    `_event_from_dict` for the inverse.
    """
    return {
        "kind": event.kind,
        "source_id": event.source_id,
        "external_id": event.external_id,
        "url": event.url,
        "title": event.title,
        "description": event.description,
        "start": event.start.isoformat() if event.start is not None else None,
        "end": event.end.isoformat() if event.end is not None else None,
        "all_day": event.all_day,
        "location": event.location,
        "latitude": event.latitude,
        "longitude": event.longitude,
        "cost": event.cost,
        "registration_url": event.registration_url,
        "image_url": event.image_url,
        "categories": list(event.categories),
        "tags": list(event.tags),
        "relevant": event.relevant,
        "relevance_reason": event.relevance_reason,
        "areas_of_interest": list(event.areas_of_interest),
        "age_grade_level": list(event.age_grade_level),
        "cost_range": event.cost_range,
        "time_of_day": list(event.time_of_day),
        "field_provenance": {
            field_name: {"source": prov.source, "confidence": prov.confidence}
            for field_name, prov in event.field_provenance.items()
        },
    }


def _event_from_dict(data: dict[str, Any]) -> Event:
    """Deserialize a dict produced by `_event_to_dict` back into an Event."""
    return Event(
        kind=data["kind"],
        source_id=data["source_id"],
        external_id=data["external_id"],
        url=data["url"],
        title=data["title"],
        description=data["description"],
        start=datetime.fromisoformat(data["start"]) if data["start"] is not None else None,
        end=datetime.fromisoformat(data["end"]) if data["end"] is not None else None,
        all_day=data["all_day"],
        location=data["location"],
        latitude=data["latitude"],
        longitude=data["longitude"],
        cost=data["cost"],
        registration_url=data["registration_url"],
        image_url=data["image_url"],
        categories=list(data["categories"]),
        tags=list(data["tags"]),
        relevant=data["relevant"],
        relevance_reason=data["relevance_reason"],
        areas_of_interest=list(data["areas_of_interest"]),
        age_grade_level=list(data["age_grade_level"]),
        cost_range=data["cost_range"],
        time_of_day=list(data["time_of_day"]),
        field_provenance={
            field_name: Provenance(source=p["source"], confidence=p["confidence"])
            for field_name, p in data["field_provenance"].items()
        },
    )


def _effective_date(data: dict[str, Any]) -> date | None:
    """The date `prune_past` judges a stored row's staleness by.

    ``end`` if the Event had one, else ``start``, else ``None`` (an
    undated Event, which `prune_past` always keeps -- it may acquire a
    date on a later run).
    """
    end_str = data.get("end")
    if end_str is not None:
        return datetime.fromisoformat(end_str).date()
    start_str = data.get("start")
    if start_str is not None:
        return datetime.fromisoformat(start_str).date()
    return None


class EventStore:
    """Durable, cross-run table of canonical Events, keyed by identity.

    ``db_path`` defaults to ``config.get_scrape_cache_dir() / "events.db"``.
    Tests should pass an explicit ``tmp_path``-derived path, or the
    literal string ``":memory:"`` for a non-persistent database -- never
    the real configured cache directory.

    The schema is created (``CREATE TABLE IF NOT EXISTS``) on
    construction, so opening the same ``db_path`` repeatedly -- across
    runs, or across processes, since this is a plain SQLite file -- is
    always safe.
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        if db_path is None:
            db_path = config.get_scrape_cache_dir() / _DEFAULT_DB_FILENAME
        self.db_path = db_path

        if str(db_path) != _MEMORY_DB:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(str(db_path))
        with self._conn:
            self._conn.execute(_SCHEMA_SQL)

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._conn.close()

    def __enter__(self) -> "EventStore":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def upsert(self, events: Iterable[Event], *, seen_at: datetime) -> None:
        """Insert-or-update ``events`` by identity, in one transaction.

        A row that already exists (same `Event.identity_key()`) has its
        `data`/`content_hash`/`last_seen` updated, with `first_seen`
        preserved. A new identity is inserted with
        ``first_seen == last_seen == seen_at``.
        """
        seen_at_iso = seen_at.isoformat()
        with self._conn:
            for event in events:
                identity = _identity_hash(event.identity_key())
                data_json = json.dumps(_event_to_dict(event), sort_keys=True)
                event_content_hash = content_hash(event)

                existing = self._conn.execute(
                    "SELECT 1 FROM events WHERE identity = ?", (identity,)
                ).fetchone()

                if existing is not None:
                    self._conn.execute(
                        """
                        UPDATE events
                        SET source_id = ?, data = ?, content_hash = ?, last_seen = ?
                        WHERE identity = ?
                        """,
                        (event.source_id, data_json, event_content_hash, seen_at_iso, identity),
                    )
                else:
                    self._conn.execute(
                        """
                        INSERT INTO events
                            (identity, source_id, data, content_hash, first_seen, last_seen)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            identity,
                            event.source_id,
                            data_json,
                            event_content_hash,
                            seen_at_iso,
                            seen_at_iso,
                        ),
                    )

    def all_events(self) -> list[Event]:
        """Return every stored Event, deserialized.

        No filtering, collapsing, or dedup -- that is `normalize/`'s
        job, applied downstream to this list.
        """
        rows = self._conn.execute("SELECT data FROM events").fetchall()
        return [_event_from_dict(json.loads(data_json)) for (data_json,) in rows]

    def prune_past(self, today: date) -> int:
        """Delete rows whose event end-or-start date is strictly before ``today``.

        Undated rows (no `start` and no `end`) are always kept -- they
        may acquire a date on a future run. Returns the number of rows
        deleted.
        """
        rows = self._conn.execute("SELECT identity, data FROM events").fetchall()
        stale_identities = [
            identity
            for identity, data_json in rows
            if (effective := _effective_date(json.loads(data_json))) is not None
            and effective < today
        ]
        self._delete_by_identity(stale_identities)
        return len(stale_identities)

    def prune_unseen(self, cutoff: datetime) -> int:
        """Delete rows with ``last_seen < cutoff``.

        Intended for the case where the caller just completed a full
        crawl of a source: any row not touched (via `upsert`) since
        ``cutoff`` was no longer present at the source. Returns the
        number of rows deleted.
        """
        rows = self._conn.execute("SELECT identity, last_seen FROM events").fetchall()
        stale_identities = [
            identity
            for identity, last_seen_iso in rows
            if datetime.fromisoformat(last_seen_iso) < cutoff
        ]
        self._delete_by_identity(stale_identities)
        return len(stale_identities)

    def count(self) -> int:
        """Return the number of stored rows."""
        (row_count,) = self._conn.execute("SELECT COUNT(*) FROM events").fetchone()
        return row_count

    def _delete_by_identity(self, identities: list[str]) -> None:
        if not identities:
            return
        with self._conn:
            self._conn.executemany(
                "DELETE FROM events WHERE identity = ?", [(identity,) for identity in identities]
            )
