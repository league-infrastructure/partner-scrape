"""The Places static roster source (``directory.sources.static_roster``).

Places are curated, slow-changing "where to go any day" venues, not a
live feed -- issue 35's explicit instruction ("Do NOT design live
scrapers for either directory") and sprint.md's Architecture both
specify the FLL ``static_roster`` precedent (``teams/sources/
static_roster.py``): a committed data file, hand-researched, never
fetched over the network. This module reuses that precedent's *shape*
(``discover()`` resolves a local file path, ``fetch()`` reads it off
disk, ``extract()`` never touches the injected ``Fetcher``) for a new,
hand-authored curated dataset -- ``directory/data/places.toml``, not a
derivative of any third-party export.

**TOML, not TSV, unlike the FLL roster.** ``teams/sources/
static_roster.py`` reads a tab-separated derivative of an upstream
export with a fixed, narrow column set (six columns). This module's
curated dataset has no upstream export to derive from -- every row was
hand-researched (see ``directory/DESIGN.md``'s Notes) -- and each Place
carries substantially more fields (address, category, status, a
provenance-adjacent ``related_partner_id``, ...) than a flat delimited
table renders cleanly. An array of TOML tables (``[[place]]``) is a
better fit for the same reason ``teams/data/school-overrides.toml`` and
``teams/data/zip-centroids.toml`` are already TOML rather than TSV in
this codebase: multi-field, human-edited records, not a wide flat
table. This is a data-format choice, not a behavioral one -- every
other convention (never touch ``fetcher``, per-record failure
isolation, a local-path ``PlaceRef``) matches the FLL precedent
exactly.

**No privacy-stripping layer, unlike the FLL roster.** Every field in
this dataset is already public information about a public venue (a
museum, a library branch, a government-run park) -- there is no
contact-data column to strip the way ``teams/data/fll-sd-teams.tsv``'s
committed derivative had to drop the upstream export's email column
(see that module's own docstring). ``directory/data/places.toml`` is
the *only* copy of this data; it was never derived from a richer
upstream file.

**Location: "address" precision by construction, "zip" fallback for
the one entry with no curated coordinate yet.** Every curated entry
that carries ``latitude``/``longitude`` in the TOML gets
``Place.location_precision = "address"`` directly from this module --
a hand-verified coordinate, never the shared ``geo_ladder.GeoLadder``'s
output (Places are not schools; the ladder's organization-name
matching rungs 1-4 have no meaning here). The one entry that omits
``latitude``/``longitude`` (``atlas-labs`` -- not yet open, no single
confident street-level coordinate to curate) is left at this module's
own honest ``location_precision = "none"`` default; resolving it
through the shared ladder's ZIP/city-centroid rungs is
``directory.pipeline.run_directory()``'s job
(``_apply_geo_fallback``), run once over the full acquired list, the
same "acquisition source never geocodes" separation
``teams/sources/*.py`` already establishes for ``Team``.
"""

from __future__ import annotations

import logging
import tomllib
from pathlib import Path
from typing import Any, Iterable

from partner_scrape.directory.model import Place, VALID_CATEGORIES, VALID_STATUSES
from partner_scrape.directory.sources.base import PlaceRef, RawPlaceResponse
from partner_scrape.fetch import Fetcher
from partner_scrape.registry.schema import SourceConfig

logger = logging.getLogger(__name__)

#: This source's provenance name, recorded on every Place it produces
#: (``Place.sources``) -- matches ``teams/sources/static_roster.py``'s
#: ``SOURCE_NAME`` convention exactly.
SOURCE_NAME = "static_roster"

#: This module's own data directory -- `directory/data/`, matching
#: `teams/sources/static_roster.py`'s `DEFAULT_DATA_DIR` convention.
#: Never overridden in production; tests pass an explicit `roster_path`
#: (via a fixture `SourceConfig`) instead of touching the real
#: committed roster.
DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

#: The real, committed curated places roster.
DEFAULT_ROSTER_PATH = DEFAULT_DATA_DIR / "places.toml"


def _extract_one(entry: dict[str, Any]) -> Place:
    """Map one ``[[place]]`` TOML table into a `Place`.

    Raises:
        ValueError: the entry has no usable ``place_id``/``name``, an
            unrecognized ``category``, or an unrecognized ``status`` --
            left uncaught here so the caller (`extract()`) can isolate
            it as a whole-entry failure, matching every other
            structured source's convention (see
            `teams/sources/ftcscout.py`'s `_extract_one`).
    """
    place_id = str(entry.get("place_id") or "").strip()
    name = str(entry.get("name") or "").strip()
    if not place_id or not name:
        raise ValueError("place roster entry has no usable place_id or name")

    category = str(entry.get("category") or "").strip()
    if category not in VALID_CATEGORIES:
        raise ValueError(f"place roster entry has an unrecognized category: {category!r}")

    status = str(entry.get("status") or "open").strip()
    if status not in VALID_STATUSES:
        raise ValueError(f"place roster entry has an unrecognized status: {status!r}")

    status_note = str(entry.get("status_note") or "").strip()
    if status != "open" and not status_note:
        raise ValueError(
            f"place roster entry {place_id!r} has status {status!r} but no status_note"
        )

    raw_latitude = entry.get("latitude")
    raw_longitude = entry.get("longitude")
    has_curated_coords = raw_latitude is not None and raw_longitude is not None
    latitude = float(raw_latitude) if has_curated_coords else None
    longitude = float(raw_longitude) if has_curated_coords else None

    raw_partner_id = entry.get("related_partner_id")
    related_partner_id = int(raw_partner_id) if raw_partner_id is not None else None

    return Place(
        place_id=place_id,
        name=name,
        category=category,
        description=str(entry.get("description") or "").strip(),
        address=str(entry.get("address") or "").strip(),
        city=str(entry.get("city") or "").strip(),
        postal_code=str(entry.get("postal_code") or "").strip(),
        latitude=latitude,
        longitude=longitude,
        location_precision="address" if has_curated_coords else "none",
        matched_name=name if has_curated_coords else "",
        website=str(entry.get("website") or "").strip(),
        status=status,
        status_note=status_note,
        related_partner_id=related_partner_id,
        sources=[SOURCE_NAME],
    )


class StaticRosterSource:
    """`PlaceSource` for the committed, curated places roster file.

    A "source" in name and protocol shape only -- there is no
    acquisition step to isolate a failure from, only a local file read.
    See this module's own docstring for the full rationale.
    """

    def discover(self, source: SourceConfig, fetcher: Fetcher) -> list[PlaceRef]:
        """Return a single `PlaceRef` pointing at the committed roster
        file -- a local filesystem path, never an HTTP URL.

        `SourceConfig.config["roster_path"]` (set in
        `directory/registry/places-sd.toml`) is resolved relative to
        `DEFAULT_DATA_DIR` (`directory/data/`) when it is not already
        an absolute path, matching
        `teams/sources/static_roster.py`'s exact convention. Falls back
        to `DEFAULT_ROSTER_PATH` when `roster_path` is omitted
        entirely.
        """
        configured = source.config.get("roster_path")
        if configured:
            roster_path = Path(configured)
            if not roster_path.is_absolute():
                roster_path = DEFAULT_DATA_DIR / roster_path
        else:
            roster_path = DEFAULT_ROSTER_PATH
        return [PlaceRef(url=str(roster_path))]

    def fetch(self, ref: PlaceRef, fetcher: Fetcher) -> RawPlaceResponse:
        """Read `ref.url` straight off disk -- `fetcher` is accepted
        (the `PlaceSource` protocol shape is fixed) but never called.

        A missing or unreadable roster file raises `OSError` (typically
        `FileNotFoundError`) here, uncaught -- a missing committed data
        file is a build-time defect, isolated by
        `directory.pipeline.run_directory()`'s existing per-source
        try/except the same way any `PlaceSource` acquisition failure
        always is, not a per-record failure to log and skip.
        """
        body = Path(ref.url).read_text(encoding="utf-8")
        return RawPlaceResponse(ref=ref, status=200, body=body)

    def extract(self, raw: RawPlaceResponse, source: SourceConfig) -> Iterable[Place]:
        try:
            data = tomllib.loads(raw.body)
        except tomllib.TOMLDecodeError as exc:
            # A whole-file parse failure is a build-time defect (the
            # committed roster itself is malformed), not a per-record
            # condition to isolate -- matches geo_ladder.py's
            # "malformed data fails loudly" convention for its own TOML
            # data files.
            raise ValueError(f"Malformed places roster TOML at {raw.ref.url}: {exc}") from exc

        places: list[Place] = []
        for entry in data.get("place", []):
            try:
                places.append(_extract_one(entry))
            except (ValueError, TypeError) as exc:
                logger.warning(
                    "Skipping malformed place roster entry on %s: %s", raw.ref.url, exc
                )
        return places
