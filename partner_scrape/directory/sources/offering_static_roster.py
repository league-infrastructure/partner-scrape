"""The Offerings static roster source
(``directory.sources.offering_static_roster``) -- sprint 030's mechanism
ticket (001), serving both issue 14 Strategy B (volunteer org profiles)
and issue 33 part 2 (free/Title I school-program records).

Offerings are curated, slow-changing standing records, not a live feed
-- issue 35's original "Do NOT design live scrapers for either
directory" instruction and sprint 030's own sprint.md Architecture both
extend the FLL/Places/Hack-Club ``static_roster`` precedent
(``teams/sources/static_roster.py``, ``directory/sources/
static_roster.py``): a committed data file, hand-researched, never
fetched over the network. This module reuses that precedent's *shape*
(``discover()`` resolves a local file path, ``fetch()`` reads it off
disk, ``extract()`` never touches the injected ``Fetcher``) for a new,
hand-authored curated dataset -- ``directory/data/offerings.toml``, not
a derivative of any third-party export.

**TOML, not TSV, matching ``places.toml``'s own precedent.** An
``Offering`` carries substantially more fields than a flat delimited
table renders cleanly (identity, description, eligibility, a typed
``age_minimum``, how-to-book, link-out, status, a provenance-adjacent
``related_partner_id``, ...) -- the same "too many fields for a flat
table" reasoning ``sources/static_roster.py``'s own docstring gives for
``places.toml``, not ``hack-club-sd.tsv``'s narrower shape. An array of
TOML tables (``[[offering]]``) is the fit.

**This ticket (001) ships the mechanism with a small fixture-sized
roster only.** ``directory/data/offerings.toml`` carries 1-2
placeholder rows sufficient to prove discover -> fetch -> extract ->
pipeline dispatch -> export end to end -- the real curated rosters
(six volunteer org profiles, seven free/Title I school-program records)
are tickets 002 and 003's job, not this one (see sprint.md's Tickets
table).
"""

from __future__ import annotations

import logging
import tomllib
from pathlib import Path
from typing import Any, Iterable

from partner_scrape.directory.model import Offering, VALID_OFFERING_STATUSES, VALID_OFFERING_TYPES
from partner_scrape.directory.sources.base import OfferingRef, RawOfferingResponse
from partner_scrape.fetch import Fetcher
from partner_scrape.registry.schema import SourceConfig

logger = logging.getLogger(__name__)

#: This source's provenance name, recorded on every Offering it
#: produces (``Offering.sources``) -- matches ``sources/
#: static_roster.py``'s ``SOURCE_NAME`` convention exactly. (Sprint 032
#: ticket 001 moved ``sources/club_static_roster.py`` to a
#: per-registry-entry provenance value instead of a module-level
#: constant like this one -- see that module's own docstring.)
SOURCE_NAME = "offering_static_roster"

#: This module's own data directory -- `directory/data/`, matching
#: `sources/static_roster.py`'s `DEFAULT_DATA_DIR` convention. Never
#: overridden in production; tests pass an explicit `roster_path` (via
#: a fixture `SourceConfig`) instead of touching the real committed
#: roster.
DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

#: The real, committed curated offerings roster.
DEFAULT_ROSTER_PATH = DEFAULT_DATA_DIR / "offerings.toml"


def _extract_one(entry: dict[str, Any]) -> Offering:
    """Map one ``[[offering]]`` TOML table into an `Offering`.

    Raises:
        ValueError: the entry has no usable ``offering_id``/``org_name``/
            ``title``, an unrecognized ``offering_type``, or an
            unrecognized ``status`` -- left uncaught here so the caller
            (`extract()`) can isolate it as a whole-entry failure,
            matching every other structured source's convention (see
            `sources/static_roster.py`'s own `_extract_one`).
    """
    offering_id = str(entry.get("offering_id") or "").strip()
    org_name = str(entry.get("org_name") or "").strip()
    title = str(entry.get("title") or "").strip()
    if not offering_id or not org_name or not title:
        raise ValueError(
            "offering roster entry has no usable offering_id, org_name, or title"
        )

    offering_type = str(entry.get("offering_type") or "").strip()
    if offering_type not in VALID_OFFERING_TYPES:
        raise ValueError(
            f"offering roster entry has an unrecognized offering_type: {offering_type!r}"
        )

    status = str(entry.get("status") or "active").strip()
    if status not in VALID_OFFERING_STATUSES:
        raise ValueError(f"offering roster entry has an unrecognized status: {status!r}")

    status_note = str(entry.get("status_note") or "").strip()
    if status != "active" and not status_note:
        raise ValueError(
            f"offering roster entry {offering_id!r} has status {status!r} but no status_note"
        )

    raw_age_minimum = entry.get("age_minimum")
    age_minimum = int(raw_age_minimum) if raw_age_minimum is not None else None

    raw_partner_id = entry.get("related_partner_id")
    related_partner_id = int(raw_partner_id) if raw_partner_id is not None else None

    return Offering(
        offering_id=offering_id,
        org_name=org_name,
        title=title,
        offering_type=offering_type,
        description=str(entry.get("description") or "").strip(),
        eligibility=str(entry.get("eligibility") or "").strip(),
        age_minimum=age_minimum,
        how_to_book=str(entry.get("how_to_book") or "").strip(),
        link_url=str(entry.get("link_url") or "").strip(),
        last_verified=str(entry.get("last_verified") or "").strip(),
        status=status,
        status_note=status_note,
        related_partner_id=related_partner_id,
        sources=[SOURCE_NAME],
    )


class OfferingStaticRosterSource:
    """`OfferingSource` for the committed, curated offerings roster
    file.

    A "source" in name and protocol shape only -- there is no
    acquisition step to isolate a failure from, only a local file read.
    See this module's own docstring for the full rationale.
    """

    def discover(self, source: SourceConfig, fetcher: Fetcher) -> list[OfferingRef]:
        """Return a single `OfferingRef` pointing at the committed
        roster file -- a local filesystem path, never an HTTP URL.

        `SourceConfig.config["roster_path"]` (set in `directory/
        registry/offerings-sd.toml`) is resolved relative to
        `DEFAULT_DATA_DIR` (`directory/data/`) when it is not already
        an absolute path, matching `sources/static_roster.py`'s exact
        convention. Falls back to `DEFAULT_ROSTER_PATH` when
        `roster_path` is omitted entirely.
        """
        configured = source.config.get("roster_path")
        if configured:
            roster_path = Path(configured)
            if not roster_path.is_absolute():
                roster_path = DEFAULT_DATA_DIR / roster_path
        else:
            roster_path = DEFAULT_ROSTER_PATH
        return [OfferingRef(url=str(roster_path))]

    def fetch(self, ref: OfferingRef, fetcher: Fetcher) -> RawOfferingResponse:
        """Read `ref.url` straight off disk -- `fetcher` is accepted
        (the `OfferingSource` protocol shape is fixed) but never
        called.

        A missing or unreadable roster file raises `OSError` (typically
        `FileNotFoundError`) here, uncaught -- a missing committed data
        file is a build-time defect, isolated by
        `directory.pipeline.run_directory()`'s existing per-source
        try/except the same way any `OfferingSource` acquisition
        failure always is, not a per-record failure to log and skip.
        """
        body = Path(ref.url).read_text(encoding="utf-8")
        return RawOfferingResponse(ref=ref, status=200, body=body)

    def extract(self, raw: RawOfferingResponse, source: SourceConfig) -> Iterable[Offering]:
        try:
            data = tomllib.loads(raw.body)
        except tomllib.TOMLDecodeError as exc:
            # A whole-file parse failure is a build-time defect (the
            # committed roster itself is malformed), not a per-record
            # condition to isolate -- matches sources/static_roster.py's
            # own convention for the identical failure mode.
            raise ValueError(
                f"Malformed offerings roster TOML at {raw.ref.url}: {exc}"
            ) from exc

        offerings: list[Offering] = []
        for entry in data.get("offering", []):
            try:
                offerings.append(_extract_one(entry))
            except (ValueError, TypeError) as exc:
                logger.warning(
                    "Skipping malformed offering roster entry on %s: %s", raw.ref.url, exc
                )
        return offerings
