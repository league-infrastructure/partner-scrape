"""The generalized curated club static-roster source
(``directory.sources.club_static_roster``) -- one ``ClubSource``
implementation serving any club type, not just Hack Club.

**Sprint 032 ticket 001 generalized this module** from ticket
018-008's Hack-Club-only ``hack_club_static_roster.py``
(``HackClubStaticRosterSource``). The logic was already generic --
``_extract_one()`` reads ``club_type``/``status`` from each TSV row and
validates against the model's own ``VALID_CLUB_TYPES``/
``VALID_CLUB_STATUSES`` rather than hard-coding Hack Club anywhere.
Only the module name, class name, and provenance stamp were
Hack-Club-specific; see ``directory/DESIGN.md``'s sprint 032 Revision
for the full rationale. Any club type registered in
``directory/registry/*.toml`` with ``adapter_type =
"club_static_roster"`` is served by this one module -- issue 35b's six
remaining club types (CyberPatriot, Science Olympiad, 4-H, Girls Who
Code, Civil Air Patrol, Sea Cadets) each need only a new curated TSV
and a new registry entry, no new Python module.

Every club type this module serves is a curated, slow-changing roster,
not a live feed -- issue 35's original instruction ("Do NOT design
live scrapers for either directory") and the FLL ``static_roster``
precedent (``teams/sources/static_roster.py``) both specify a
committed data file, hand-curated, never fetched over the network.
This module places no structural limit on the roster's size or its
club type -- only the registered TSV's own content does.

**TSV, not TOML, unlike the Places roster.** ``directory/data/
places.toml`` chose TOML because each ``Place`` carries substantially
more fields than a flat delimited table renders cleanly (see that
module's own docstring). A ``Club`` record is narrower and closer in
shape to the FLL roster's own six-column TSV
(``teams/data/fll-sd-teams.tsv``) -- ``club_id``, ``name``,
``club_type``, ``host_school``, ``city``, ``postal_code``, ``website``,
``meeting_note``, ``status``, ``status_note`` is a comfortable flat
table, so this module reuses the FLL precedent's exact shape
(``discover()`` resolves a local file path, ``fetch()`` reads it off
disk, ``extract()`` never touches the injected ``Fetcher``,
``csv.DictReader`` with ``delimiter="\\t"``) rather than Places' TOML
choice.

**Provenance (``Club.sources``) is derived per registry entry, not a
single hard-coded literal.** Each registry entry's own
``SourceConfig.source_id`` (e.g. ``"hack-club-sd"``) is stamped onto
every `Club` it produces, so a CyberPatriot roster's provenance never
reads ``"hack_club_static_roster"`` and two different registry entries
always produce two distinguishable `Club.sources` values -- see
``tests/directory/test_sources_club_static_roster.py``'s
``TestProvenance`` for the regression pin.

**Location: this source never geocodes.** Like every other
``*Source.extract()`` in this codebase, this module sets only
``Club.host_school``/``city``/``postal_code`` (the raw signal a
geocoder needs) and leaves ``latitude``/``longitude``/
``location_precision``/``matched_name``/``needs_review``/
``host_school_website`` at their honest ``None``/``"none"``/``""``
defaults. ``directory.pipeline._apply_club_geocoding()`` is the only
stage that ever turns ``host_school`` into a coordinate, running the
shared ``geo_ladder.GeoLadder``'s *full* ladder (including the
school-matching rungs 1-4 this source's ``host_school`` column exists
to feed) -- see that function's own docstring.
"""

from __future__ import annotations

import csv
import io
import logging
from pathlib import Path
from typing import Iterable

from partner_scrape.directory.model import Club, VALID_CLUB_STATUSES, VALID_CLUB_TYPES
from partner_scrape.directory.sources.base import ClubRef, RawClubResponse
from partner_scrape.fetch import Fetcher
from partner_scrape.registry.schema import SourceConfig

logger = logging.getLogger(__name__)

#: This module's own data directory -- `directory/data/`, matching
#: `sources/static_roster.py`'s `DEFAULT_DATA_DIR` convention. Never
#: overridden in production; tests pass an explicit `roster_path` (via
#: a fixture `SourceConfig`) instead of touching the real committed
#: roster.
DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

#: Fallback roster path used only when a registry entry omits
#: `roster_path` entirely -- every real registry entry (Hack Club and
#: every one of issue 35b's six new club types) sets `roster_path`
#: explicitly, so this default only matters for a misconfigured entry.
#: Kept pointed at the original Hack Club roster for backward
#: compatibility with ticket 018-008's existing behavior/tests.
DEFAULT_ROSTER_PATH = DEFAULT_DATA_DIR / "hack-club-sd.tsv"


def _extract_one(row: dict[str, str | None], source_name: str) -> Club:
    """Map one roster TSV row into a `Club`, stamping `source_name`
    (the registering `SourceConfig.source_id`) as this record's
    provenance.

    Raises:
        ValueError: the row has no usable `club_id`/`name`, an
            unrecognized `club_type`, or an unrecognized `status` --
            left uncaught here so the caller (`extract()`) can isolate
            it as a whole-row failure, matching every other structured
            source's convention (see `sources/static_roster.py`'s own
            `_extract_one`).
    """
    club_id = (row.get("club_id") or "").strip()
    name = (row.get("name") or "").strip()
    if not club_id or not name:
        raise ValueError("Club roster row has no usable club_id or name")

    club_type = (row.get("club_type") or "").strip()
    if club_type not in VALID_CLUB_TYPES:
        raise ValueError(f"Club roster row has an unrecognized club_type: {club_type!r}")

    status = (row.get("status") or "active").strip()
    if status not in VALID_CLUB_STATUSES:
        raise ValueError(f"Club roster row has an unrecognized status: {status!r}")

    status_note = (row.get("status_note") or "").strip()
    if status != "active" and not status_note:
        raise ValueError(f"Club roster row {club_id!r} has status {status!r} but no status_note")

    return Club(
        club_id=club_id,
        name=name,
        club_type=club_type,
        host_school=(row.get("host_school") or "").strip(),
        city=(row.get("city") or "").strip(),
        postal_code=(row.get("postal_code") or "").strip(),
        website=(row.get("website") or "").strip(),
        meeting_note=(row.get("meeting_note") or "").strip(),
        status=status,
        status_note=status_note,
        sources=[source_name],
    )


class ClubStaticRosterSource:
    """`ClubSource` for a committed, curated club roster file, any club
    type.

    A "source" in name and protocol shape only -- there is no
    acquisition step to isolate a failure from, only a local file read.
    See this module's own docstring for the full rationale.
    """

    def discover(self, source: SourceConfig, fetcher: Fetcher) -> list[ClubRef]:
        """Return a single `ClubRef` pointing at the committed roster
        file -- a local filesystem path, never an HTTP URL.

        `SourceConfig.config["roster_path"]` (set per registry entry,
        e.g. `directory/registry/hack-club-sd.toml`) is resolved
        relative to `DEFAULT_DATA_DIR` (`directory/data/`) when it is
        not already an absolute path, matching
        `sources/static_roster.py`'s exact convention. Falls back to
        `DEFAULT_ROSTER_PATH` when `roster_path` is omitted entirely.
        """
        configured = source.config.get("roster_path")
        if configured:
            roster_path = Path(configured)
            if not roster_path.is_absolute():
                roster_path = DEFAULT_DATA_DIR / roster_path
        else:
            roster_path = DEFAULT_ROSTER_PATH
        return [ClubRef(url=str(roster_path))]

    def fetch(self, ref: ClubRef, fetcher: Fetcher) -> RawClubResponse:
        """Read `ref.url` straight off disk -- `fetcher` is accepted
        (the `ClubSource` protocol shape is fixed) but never called.

        A missing or unreadable roster file raises `OSError` (typically
        `FileNotFoundError`) here, uncaught -- a missing committed data
        file is a build-time defect, isolated by
        `directory.pipeline.run_directory()`'s existing per-source
        try/except the same way any `ClubSource` acquisition failure
        always is, not a per-record failure to log and skip.
        """
        body = Path(ref.url).read_text(encoding="utf-8")
        return RawClubResponse(ref=ref, status=200, body=body)

    def extract(self, raw: RawClubResponse, source: SourceConfig) -> Iterable[Club]:
        reader = csv.DictReader(io.StringIO(raw.body), delimiter="\t")

        clubs: list[Club] = []
        for row in reader:
            try:
                clubs.append(_extract_one(row, source.source_id))
            except (ValueError, TypeError) as exc:
                logger.warning("Skipping malformed club roster row on %s: %s", raw.ref.url, exc)
        return clubs
