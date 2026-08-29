"""The FLL static roster source (``teams.sources.static_roster``).

First LEGO League has no public API and no third-party aggregator --
probed and confirmed (``firstinspires.org/team-event-search`` exposes
no usable JSON endpoint, 404/405) -- so this source cannot be a live
acquisition the way ``sources/ftcscout.py``/``sources/tba.py`` are. The
only source of San Diego County's 48 FLL teams is a hand-maintained,
dated export in a sibling repo
(``../robot-team-analysis/fll/sd-fll-teams-contact-list.md``), a manual
browser export of the FIRST team search hand-enriched by an analyst on
2026-08-13. This module reads a **committed, already-contact-stripped**
derivative of that export -- ``teams/data/fll-sd-teams.tsv`` -- never
the upstream file itself.

**Privacy is structural, not a filter.** The upstream export carries an
"Email on file" column (6 of 48 rows), plus a "Best contact route"
column that sometimes embeds a physical address or another contact
detail. Neither column -- nor "Confidence" -- was carried into the
committed TSV at all: ``fll-sd-teams.tsv`` has exactly six columns
(``number``, ``name``, ``program``, ``organization``, ``area``,
``district``), none of them a contact field. This module's ``extract()``
therefore never *sees* a contact value to filter out -- a stronger
guarantee than "strip emails at read time" would have been, since a bug
in a filter can leak but a column that was never committed cannot.
Combined with ``teams/model.py``'s structural "no ``email`` field, ever"
invariant, there are two independent layers between any upstream
contact data and a published ``Team``.

**Never touches the injected ``Fetcher``.** ``discover()`` returns a
single ``TeamRef`` whose ``url`` is a local filesystem path (never an
HTTP URL); ``fetch()`` reads that path straight off disk via
``Path.read_text()`` and ignores its ``fetcher`` argument entirely --
there is no acquisition step here to isolate a network failure from,
only a file read. ``tests/teams/test_sources_static_roster.py`` asserts
this with a ``Fetcher`` test double that raises on any call, exercised
through the full ``sources.base.run()`` chain (see that module's own
docstring for why this is a stronger guarantee than an unused-parameter
convention).

**Family/Community mapping, mirroring ``sources/ftcscout.py``.** The
upstream roster marks 32 of 48 teams as having no sponsoring school:
28 pure home teams (``organization`` column reads exactly
``"Family/Community"``) plus 4 sponsor-backed home teams (a corporate
or program sponsor joined to the same marker, e.g. ``"Apple &
Family/Community"``, ``"Qualcomm & Family/Community"`` -- one of the
four, team 29255 "Meeps", carries a bare ``"& Family/Community"`` with
no sponsor name at all, an artifact of the upstream export this module
does not try to repair). Every one of the 32 maps to ``organization=""``
/ ``org_type="family_community"`` -- detected by substring, not exact
match, so the sponsor-prefixed variants land in the same "never group"
bucket ``teams.merge.merge_teams()`` checks (``Team.organization ==
""``) as FTCScout's plain ``"Family/Community"`` sentinel. The sponsor
name itself (Apple, Qualcomm, ...) is discarded, not carried into
``Team.sponsors`` -- that field's existing populators (none, for this
source) are out of this ticket's scope, and inventing a new mapping for
four rows was judged not worth a new field-population path.

**Location: city precision at best, never invented.** Most FLL records
have no school, and the upstream export's own header note says
outright that a home team's area is *"inferred from the corridor
pattern, not published -- treat as a lead, not a confirmed address."*
This module never sets ``Team.latitude``/``longitude``/
``location_precision`` itself -- like every other source, that stays
exclusively ``teams.geo.geocode_teams()``'s job, run unchanged after
this source the same way it runs after FTCScout/TBA. What this module
does do is clean the upstream "Area / Neighborhood" column's real dirt
(bare city, ``"city (zip)"``, a disclaimer parenthetical, and two
distinct multi-site shapes -- see :func:`_parse_area`) into a
``Team.city``/``Team.postal_code`` pair honest to what the source
actually states, so the existing seven-rung ladder's rung-7 "never
guess" rule is the thing that decides precision, not a guess made here.
A row's ``postal_code`` is only ever set from an *unambiguous* single
ZIP -- a multi-site cell reporting two ZIPs (``"92130/75"`` or two bare
5-digit numbers) sets neither, deliberately: guessing which of the two
is correct is exactly the kind of fabricated precision this subsystem
refuses to produce.

**No slug/normalizer duplication.** ``team_id`` is built the same way
every other source builds it (``f"{league.lower()}-{number}"``,
collision-free by construction because the roster's own team numbers
are unique within FLL) -- ``model.slugify()`` is not needed here, the
same conclusion ticket 011-005's site pages reached for ``Team.team_id``
(see ``teams/DESIGN.md``). Cross-league identity linking still runs
through ``teams.merge.merge_teams()``'s existing
``normalize.partners.normalize_org_name`` call, unmodified by this
module -- no new normalizer is written here.

``tests/fixtures/teams/`` carries a small excerpt of the real committed
``fll-sd-teams.tsv`` (not a hand-authored approximation) -- see that
module's own docstring for why, per the sprint 011 ticket-011-003
lesson (a hand-authored fixture drifting from what the real data
actually looks like shipped an undetected defect for a full ticket).
"""

from __future__ import annotations

import csv
import io
import logging
import re
from pathlib import Path
from typing import Iterable

from partner_scrape.fetch import Fetcher
from partner_scrape.registry.schema import SourceConfig
from partner_scrape.teams.model import Team
from partner_scrape.teams.sources.base import RawTeamResponse, TeamRef

logger = logging.getLogger(__name__)

#: This source's provenance name, recorded on every Team it produces
#: (``Team.sources``) -- a Team whose ``sources == ["static_roster"]``
#: is, by construction, a dated snapshot rather than live data (see
#: ``teams/DESIGN.md``'s Design Rationale: this project reuses
#: ``Team.sources`` for provenance rather than adding a new field).
SOURCE_NAME = "static_roster"

#: Short league code -- see ``teams/model.py``'s ``League`` docstring.
LEAGUE = "FLL"

#: Human-readable program names, keyed by the roster TSV's own
#: ``program`` column value (``"Challenge"``/``"Explore"``, the two
#: FLL sub-programs -- 32 and 16 of the 48 real rows respectively).
#: An unrecognized value raises inside :func:`_extract_one`, isolated
#: as a per-row failure by ``extract()`` below, matching every other
#: structured source's convention.
PROGRAM_BY_RAW = {
    "Challenge": "FIRST LEGO League Challenge",
    "Explore": "FIRST LEGO League Explore",
}

#: This module's own data directory -- `teams/data/`, matching
#: `teams/geo.py`'s `DEFAULT_DATA_DIR` convention. Never overridden in
#: production; tests pass an explicit `roster_path` (via a fixture
#: `SourceConfig`) instead of touching the real committed roster.
DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

#: The real, committed, contact-stripped FLL roster -- see this
#: module's own docstring for exactly which upstream columns were
#: dropped and why.
DEFAULT_ROSTER_PATH = DEFAULT_DATA_DIR / "fll-sd-teams.tsv"

#: Substring marker for a home/family team with no sponsoring school.
#: Checked case-insensitively and by *substring*, not exact match, so
#: both the plain upstream sentinel (`"Family/Community"`) and every
#: sponsor-prefixed variant (`"Apple & Family/Community"`, the bare
#: artifact `"& Family/Community"`, ...) land in the same bucket -- see
#: this module's own docstring for the full accounting.
_FAMILY_COMMUNITY_MARKER = "family/community"

#: Matches a trailing parenthetical group at the end of an "Area /
#: Neighborhood" cell, e.g. the `"(92130)"` in `"Carmel Valley
#: (92130)"` or the `"(home team -- not published)"` disclaimer in
#: `"San Diego (home team -- not published)"`.
_TRAILING_PAREN_RE = re.compile(r"\s*\(([^)]*)\)\s*$")

#: A standalone 5-digit ZIP code, word-bounded so it never matches part
#: of a longer digit run.
_STANDALONE_ZIP_RE = re.compile(r"\b\d{5}\b")


def _map_organization(raw: str) -> tuple[str, str]:
    """Map one roster row's "Organization / School" cell to
    `(organization, org_type)`.

    Mirrors `sources/ftcscout.py`'s `Family/Community` sentinel mapping
    (see this module's own docstring) so `teams.merge.merge_teams()`
    never falsely groups unrelated home teams: any cell containing the
    marker, in any position, maps to `("", "family_community")`. A cell
    naming a real school (or schools -- some rows list two or three,
    joined by `"&"`; left as one combined string for `teams.geo.py`'s
    existing fuzzy matcher to do what it can with, not split up here)
    maps to `(cleaned, "school")`. An empty cell (not observed in the
    real 48-row roster, but not assumed impossible) maps to
    `("", "unknown")`, matching `sources/tba.py`'s convention for "no
    organization signal at all".
    """
    cleaned = raw.strip()
    if not cleaned:
        return "", "unknown"
    if _FAMILY_COMMUNITY_MARKER in cleaned.lower():
        return "", "family_community"
    return cleaned, "school"


def _parse_area(raw: str) -> tuple[str, str]:
    """Clean one roster row's "Area / Neighborhood" cell into
    `(city, postal_code)`.

    The upstream column mixes several real shapes (see this module's
    own docstring): a bare disclaimer (`"San Diego (home team -- not
    published)"`), a clean `"city (zip)"` pair, and two different
    multi-site shapes -- `"City / City (zip/zip)"` and `"City zip +
    City zip"` (Autra Academy's two campuses, the one roster row with
    no parenthetical at all). In every case this function takes the
    *first* named place as `city` (documented "dirt to handle", not
    silently resolved) and only ever sets `postal_code` from a single,
    unambiguous 5-digit ZIP -- never from a cell reporting two, since
    guessing which of two ZIPs is correct is exactly the fabricated
    precision `teams.geo.py`'s rung-7 "never guess" rule exists to
    forbid. `teams.geo.geocode_teams()` is the only stage that ever
    turns this pair into a coordinate; this function only cleans the
    raw text.
    """
    text = raw.strip()
    if not text:
        return "", ""

    postal_code = ""
    paren_match = _TRAILING_PAREN_RE.search(text)
    if paren_match:
        paren_content = paren_match.group(1).strip()
        if re.fullmatch(r"\d{5}", paren_content):
            postal_code = paren_content
        # Else: a disclaimer (no digits) or a multi-ZIP shorthand like
        # "92130/75" -- deliberately no fallback ZIP search in this
        # branch. A parenthetical that isn't a single clean 5-digit
        # code is exactly the ambiguous shape this function refuses to
        # guess from.
        remainder = text[: paren_match.start()].strip()
    else:
        remainder = text
        # No parenthetical at all -- the one real shape this covers is
        # "City zip + City zip" (Autra Academy). A single unambiguous
        # standalone ZIP anywhere in the cell is still safe to use;
        # two (the Autra case) is the same "don't guess" situation as
        # the multi-ZIP parenthetical above.
        all_zips = _STANDALONE_ZIP_RE.findall(remainder)
        if len(all_zips) == 1:
            postal_code = all_zips[0]

    # Multi-site cell: take the first named place before "/" or "+".
    first_segment = re.split(r"\s*[/+]\s*", remainder, maxsplit=1)[0]
    city = _STANDALONE_ZIP_RE.sub("", first_segment).strip(" -")

    return city, postal_code


def _extract_one(row: dict[str, str | None]) -> Team:
    """Map one roster TSV row into a `Team`.

    Raises:
        ValueError: the row has no usable `number`/`name`, or an
            unrecognized `program` value -- left uncaught here so the
            caller (`extract()`) can isolate it as a whole-row failure,
            matching every other structured source's convention (see
            `sources/ftcscout.py`'s `_extract_one`).
    """
    number_raw = (row.get("number") or "").strip()
    name = (row.get("name") or "").strip()
    if not number_raw.isdigit() or not name:
        raise ValueError("FLL roster row has no usable number or name")
    number = int(number_raw)

    program_raw = (row.get("program") or "").strip()
    program = PROGRAM_BY_RAW.get(program_raw)
    if program is None:
        raise ValueError(f"FLL roster row has an unrecognized program: {program_raw!r}")

    organization, org_type = _map_organization(row.get("organization") or "")
    city, postal_code = _parse_area(row.get("area") or "")

    return Team(
        team_id=f"{LEAGUE.lower()}-{number}",
        league=LEAGUE,
        program=program,
        number=number,
        name=name,
        organization=organization,
        org_type=org_type,
        city=city,
        postal_code=postal_code,
        sources=[SOURCE_NAME],
    )


class StaticRosterSource:
    """`TeamSource` for the committed, contact-stripped FLL roster file.

    A "source" in name and protocol shape only -- there is no
    acquisition step to isolate a failure from, only a local file read.
    See this module's own docstring for the full privacy and location
    rationale.
    """

    def discover(self, source: SourceConfig, fetcher: Fetcher) -> list[TeamRef]:
        """Return a single `TeamRef` pointing at the committed roster
        file -- a local filesystem path, never an HTTP URL.

        `SourceConfig.config["roster_path"]` (set in
        `teams/registry/fll-sd.toml`) is resolved relative to
        `DEFAULT_DATA_DIR` (`teams/data/`) when it is not already an
        absolute path -- so the registry TOML file itself never needs
        to carry a machine-specific absolute path, matching every other
        registry file's convention of storing small, portable config
        values. Falls back to `DEFAULT_ROSTER_PATH` when
        `roster_path` is omitted entirely.
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
        `FileNotFoundError`) here, uncaught -- per the issue's Error
        Flows, a missing committed data file is a build-time defect,
        isolated by `teams.pipeline.run_teams()`'s existing per-source
        try/except the same way a `TeamSource` acquisition failure
        always is, not a per-record failure to log and skip.
        """
        body = Path(ref.url).read_text(encoding="utf-8")
        return RawTeamResponse(ref=ref, status=200, body=body)

    def extract(self, raw: RawTeamResponse, source: SourceConfig) -> Iterable[Team]:
        reader = csv.DictReader(io.StringIO(raw.body), delimiter="\t")

        teams: list[Team] = []
        for row in reader:
            try:
                teams.append(_extract_one(row))
            except (ValueError, TypeError) as exc:
                logger.warning(
                    "Skipping malformed FLL roster row on %s: %s", raw.ref.url, exc
                )
        return teams
