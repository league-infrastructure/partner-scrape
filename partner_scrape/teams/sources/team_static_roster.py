"""The generalized curated STEM-competition-team static-roster source
(``teams.sources.team_static_roster``) -- one ``TeamSource``
implementation serving any non-robotics competition-team type, not a
further overload of FLL's bespoke ``sources/static_roster.py``.

**Sprint 036 ticket 001 adds this module** as the ``teams/``-side
counterpart to ``directory.sources.club_static_roster``'s sprint-032
generalization, mirroring that module's already-proven simple shape
(read columns straight off the row, validate against the model's own
derived valid-value set, no bespoke per-column parsing) rather than
teaching FLL's ``sources/static_roster.py`` to skip its own
FLL-specific dirt (``_parse_area``, the ``Family/Community`` sentinel,
``PROGRAM_BY_RAW``) for non-FLL rows. See ``teams/DESIGN.md``'s sprint
036 Revision for the full Design Rationale (Decision/Context/
Alternatives/Consequences) this docstring summarizes.

Any competition-team type registered in ``teams/registry/*.toml`` with
``adapter_type = "team_static_roster"`` is served by this one module --
ticket 002's Science Olympiad and CyberPatriot migration needs only a
new curated TSV and a new registry entry, no new Python module.

**TSV shape**: ``league``, ``program``, ``number``, ``name``,
``organization``, ``org_type``, ``city``, ``postal_code``, ``website``
-- read straight off each row via ``csv.DictReader`` with
``delimiter="\\t"``, matching ``club_static_roster.py``'s exact reading
convention.

**``number`` holds a stable school-name slug, not a sanctioned numeric
designator, for a competition type with no official team-numbering
registry (Science Olympiad, CyberPatriot).** Unlike FTC/FRC/VEX (each
assigned a real number by their sanctioning body) or FLL (a real
roster-assigned number), Science Olympiad and CyberPatriot have no
central team-numbering authority at all -- a school fields "the Science
Olympiad team," not "Science Olympiad team #4471." This module's
``_extract_one()`` therefore expects ``number`` to already carry a
stable, roster-unique slug (e.g. a school-name slug) in the TSV itself,
and builds ``team_id = f"{league.lower()}-{number}"`` identically to
every other source -- collision-free because school names are unique
within one curated roster, mirroring ``Club.club_id``'s existing slug
convention and the sprint-016 precedent of widening ``number``'s
*semantics* (not its type -- it was already ``str``) to fit a new
source's identifier shape.

**Provenance (``Team.sources``) is derived per registry entry, not a
single hard-coded literal.** Each registry entry's own
``SourceConfig.source_id`` (e.g. ``"science-olympiad-sd"``) is stamped
onto every ``Team`` it produces, mirroring ``club_static_roster.py``'s
identical convention exactly -- see
``tests/teams/test_sources_team_static_roster.py``'s ``TestProvenance``
for the regression pin.

**Location: this source never geocodes.** Like every other
``TeamSource.extract()`` in this subsystem, this module sets only
``Team.organization``/``city``/``postal_code`` (the raw signal
``teams.geo.geocode_teams()``'s offline ladder needs) and leaves
``latitude``/``longitude``/``location_precision``/``matched_name``/
``needs_review``/``organization_website`` at their honest ``None``/
``"none"``/``""`` defaults -- ``teams.geo.geocode_teams()`` is the only
stage that ever turns ``organization`` into a coordinate.

**Never touches the injected ``Fetcher``.** ``discover()`` returns a
single ``TeamRef`` whose ``url`` is a local filesystem path;
``fetch()`` reads it via ``Path.read_text()`` and ignores ``fetcher``
entirely -- there is no acquisition step here to isolate a network
failure from, only a file read, matching
``club_static_roster.py``'s/``sources/static_roster.py``'s identical
convention. ``tests/teams/test_sources_team_static_roster.py``'s
``TestNeverTouchesFetcher`` asserts this with a ``Fetcher`` test double
that raises on any call, run through the full ``sources.base.run()``
chain.
"""

from __future__ import annotations

import csv
import io
import logging
from pathlib import Path
from typing import Iterable

from partner_scrape.fetch import Fetcher
from partner_scrape.registry.schema import SourceConfig
from partner_scrape.teams.model import VALID_LEAGUES, Team
from partner_scrape.teams.sources.base import RawTeamResponse, TeamRef

logger = logging.getLogger(__name__)

#: This module's own data directory -- `teams/data/`, matching
#: `sources/static_roster.py`'s `DEFAULT_DATA_DIR` convention. Never
#: overridden in production; tests pass an explicit `roster_path` (via
#: a fixture `SourceConfig`) instead of touching a real committed
#: roster.
DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

#: Fallback roster path used only when a registry entry omits
#: `roster_path` entirely -- every real registry entry sets
#: `roster_path` explicitly, so this default only matters for a
#: misconfigured entry. Mirrors `club_static_roster.py`'s identical
#: "point at the first real roster this module ever served" fallback
#: convention.
DEFAULT_ROSTER_PATH = DEFAULT_DATA_DIR / "science-olympiad-sd.tsv"


def _extract_one(row: dict[str, str | None], source_name: str) -> Team:
    """Map one roster TSV row into a `Team`, stamping `source_name`
    (the registering `SourceConfig.source_id`) as this record's
    provenance.

    Raises:
        ValueError: the row has no usable `number`/`name`, or an
            unrecognized `league` -- left uncaught here so the caller
            (`extract()`) can isolate it as a whole-row failure,
            matching every other structured source's convention (see
            `directory.sources.club_static_roster._extract_one`).
    """
    number = (row.get("number") or "").strip()
    name = (row.get("name") or "").strip()
    if not number or not name:
        raise ValueError("Team roster row has no usable number or name")

    league = (row.get("league") or "").strip()
    if league not in VALID_LEAGUES:
        raise ValueError(f"Team roster row has an unrecognized league: {league!r}")

    program = (row.get("program") or "").strip()

    return Team(
        team_id=f"{league.lower()}-{number}",
        league=league,
        program=program,
        number=number,
        name=name,
        organization=(row.get("organization") or "").strip(),
        org_type=(row.get("org_type") or "").strip(),
        city=(row.get("city") or "").strip(),
        postal_code=(row.get("postal_code") or "").strip(),
        website=(row.get("website") or "").strip(),
        sources=[source_name],
    )


class TeamStaticRosterSource:
    """`TeamSource` for a committed, curated STEM-competition-team
    roster file, any non-robotics competition type.

    A "source" in name and protocol shape only -- there is no
    acquisition step to isolate a failure from, only a local file read.
    See this module's own docstring for the full rationale.
    """

    def discover(self, source: SourceConfig, fetcher: Fetcher) -> list[TeamRef]:
        """Return a single `TeamRef` pointing at the committed roster
        file -- a local filesystem path, never an HTTP URL.

        `SourceConfig.config["roster_path"]` (set per registry entry)
        is resolved relative to `DEFAULT_DATA_DIR` (`teams/data/`) when
        it is not already an absolute path, matching
        `club_static_roster.py`'s exact convention. Falls back to
        `DEFAULT_ROSTER_PATH` when `roster_path` is omitted entirely.
        """
        configured = source.config.get("roster_path")
        if configured:
            roster_path = Path(configured)
            if not roster_path.is_absolute():
                roster_path = DEFAULT_DATA_DIR / roster_path
        else:
            roster_path = DEFAULT_ROSTER_PATH
        return [TeamRef(url=str(roster_path))]

    def fetch(self, ref: TeamRef, fetcher: Fetcher) -> RawTeamResponse:
        """Read `ref.url` straight off disk -- `fetcher` is accepted
        (the `TeamSource` protocol shape is fixed) but never called.

        A missing or unreadable roster file raises `OSError` (typically
        `FileNotFoundError`) here, uncaught -- a missing committed data
        file is a build-time defect, isolated by
        `teams.pipeline.run_teams()`'s existing per-source try/except
        the same way any `TeamSource` acquisition failure always is,
        not a per-record failure to log and skip.
        """
        body = Path(ref.url).read_text(encoding="utf-8")
        return RawTeamResponse(ref=ref, status=200, body=body)

    def extract(self, raw: RawTeamResponse, source: SourceConfig) -> Iterable[Team]:
        reader = csv.DictReader(io.StringIO(raw.body), delimiter="\t")

        teams: list[Team] = []
        for row in reader:
            try:
                teams.append(_extract_one(row, source.source_id))
            except (ValueError, TypeError) as exc:
                logger.warning("Skipping malformed team roster row on %s: %s", raw.ref.url, exc)
        return teams
