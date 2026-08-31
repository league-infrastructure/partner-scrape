"""The seven-rung, fully offline location resolver (``teams.geo``).

This is the module that actually delivers the sprint's stated goal --
*knowing where the teams are* -- and it is deliberately, structurally
offline: **zero network calls, ever.** ``clasi/sprints/011-robot-teams/
issues/robot-teams-scrape-locate-and-publish-san-diego-first-teams.md``
measured live geocoding unreliable before this module was written
(Nominatim/OSM: 62 distinct FTC school names, 25 resolved / 36 did not
-- 41% failure -- plus an HTTP 429 on a second machine's very first
request; the US Census geocoder: 0 matches for a bare school name, it
parses street addresses this project does not have). ``geo.py`` reads
only the committed data files under ``teams/data/`` -- refreshed
yearly, offline-safe, by the standalone ``dev/
refresh_school_directories.py`` (never imported here) -- and never asks
an LLM for a coordinate either: an LLM would emit a *plausible* wrong
value nothing downstream can catch, and a wrong pin is worse than no
pin.

**As of ticket 018-006, the seven-rung ladder itself (normalization,
school matching, ZIP/city centroids, the rung-7 "never guess" rule) is
implemented by the shared, ``Team``-independent
:class:`partner_scrape.geo_ladder.GeoLadder` -- see that module's own
docstring for the full rung-by-rung description.** This module is now
a thin wrapper: :class:`SchoolIndex` subclasses ``GeoLadder`` unchanged
and adds exactly one thing ``GeoLadder`` cannot know about --
``Team``-field stamping (:meth:`SchoolIndex.resolve`), including
setting ``Team.organization_website`` from a school-precision match's
website. The extraction was done so the upcoming ``directory/`` module
(Places, Clubs -- ticket 018-007/008) can share the same ladder
(school-based Hack Club chapters need the CDE/NCES school-matching
rungs too) without depending on ``teams/`` or duplicating this logic's
real, hard-won bug-fix history. Every public name this module exposed
before the extraction (``SchoolIndex``, ``geocode_teams``,
``normalize_school_name``, ``normalize_city_name``, ``DEFAULT_DATA_DIR``)
still lives here, with identical signatures and behavior --
``tests/teams/test_geo.py``'s regression suite and
``tests/teams/test_geo_regression.py``'s byte-identical-output proof
both enforce this.

## The ladder

Highest precision first. Every rung stamps ``Team.location_precision``,
``Team.matched_name`` (so "why is this team here?" always has a string
answer), and, for the two fuzzy rungs, ``Team.needs_review``:

1. ``school-overrides.toml`` -- hand corrections for the residue a
   human has actually verified. -> ``"school"``
2. CDE **and** NCES exact normalized-name match, city-filtered when the
   normalized name is ambiguous across sources/cities. -> ``"school"``
3. Token-set match, Jaccard >= 0.60, restricted to schools in the same
   (normalized) city as the team. -> ``"school"``
4. Token-set match, Jaccard >= 0.80, county-wide (no city restriction).
   -> ``"school"``
5. ZIP centroid, from ``Team.postal_code``. -> ``"zip"``
6. City centroid, from ``Team.city``. -> ``"city"``
7. No match anywhere above -> ``"none"``, coordinates left ``None``.
   **Deliberate, not a bug**: a team that exhausts every rung gets no
   pin at all rather than a fabricated one.

Rungs 3 and 4 are two different *candidate pools* (same-city vs.
county-wide) at two different acceptance thresholds, but
``Team.needs_review`` is set from the actual computed Jaccard score,
not from which rung accepted the match -- a rung-3 match that happens
to score 0.90 is not flagged, and a rung-4 match at exactly 0.80 is.
Below 0.85, ``needs_review = True`` and the match still publishes (per
the issue: a silent guess is worse than a flagged one) -- this is
exactly what would catch a case like "Classical Academy Online"
fuzzy-matching its sponsoring district's building at a 0.70 score
without a human ever ratifying it.

## Caching

A ``SchoolIndex`` is constructed once per ``geocode_teams()``/
``run_teams()`` call and caches rungs 1-4's outcome (a hit *or* a
confirmed miss) keyed by :func:`normalize_school_name` of
``Team.organization`` alone -- not by (organization, city) and not
per-``Team``. This is deliberate: per the issue's own measurement, 94
school-named FTC/FRC teams collapse onto ~58 distinct campuses, so a
per-team cache would repeat ~40% of the matching work for no benefit --
two ``Team`` records with the *same* normalized organization name are,
by construction, teams at the *same* real-world school, so city is only
ever needed to disambiguate the *first* lookup for that name. Negative
outcomes (rungs 1-4 all miss) are cached too, so the ~14 unresolvable
org-named teams (``"D Robotics Education"``, ...) never rescan the full
candidate pool more than once per run. This cache is in-memory and
scoped to one ``SchoolIndex`` instance -- there is no cross-run/disk
persistence (unlike ``enrich/cache.py``'s ``EnrichmentCache``, which
exists to avoid *paying for* a repeated LLM call; nothing here costs
money or meaningfully more wall-clock time on a second run, so a disk
cache would add real complexity -- schema versioning, invalidation --
for no measurable benefit. See ``teams/DESIGN.md``'s Design section for
the fuller comparison). This caching lives in the shared ``GeoLadder``
base class now, not in ``SchoolIndex`` itself.

## Malformed data fails loudly

A missing or unparseable data file raises ``RuntimeError`` out of
``SchoolIndex.__init__``/``geocode_teams()`` -- per SUC-003's Error
Flows, a bad geocoding table is a build-time defect to fix before the
next run, not a per-record failure to log and skip.
"""

from __future__ import annotations

from pathlib import Path

from partner_scrape.geo_ladder import (
    GeoLadder,
    normalize_city_name,
    normalize_school_name,
)
from partner_scrape.teams.model import Team

__all__ = [
    "DEFAULT_DATA_DIR",
    "SchoolIndex",
    "geocode_teams",
    "normalize_city_name",
    "normalize_school_name",
]

#: This module's own data directory -- `teams/data/`, populated by
#: `dev/refresh_school_directories.py` (CDE/NCES/centroids) and by hand
#: (`school-overrides.toml`). Never overridden in production; tests
#: always pass an explicit `data_dir` pointing at a small fixture
#: directory instead of touching these real, ~800+213-row files.
DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data"


class SchoolIndex(GeoLadder):
    """``Team``-specific wrapper around the shared
    :class:`~partner_scrape.geo_ladder.GeoLadder`.

    Adds exactly one thing the caller-independent ``GeoLadder`` cannot
    know about: how to stamp a resolved location onto a ``Team``
    (:meth:`resolve`), including the ``Team``-only behavior of copying
    a school-precision match's website onto ``Team.organization_website``.
    Every other method (`resolve_school`, `resolve_zip`, `resolve_city`,
    `locate`, `match_calls`) is inherited from ``GeoLadder`` unchanged --
    see that module's docstring for the full ladder and caching design.

    Construct one per `geocode_teams()` call (matching
    `teams.merge.merge_teams()`'s "operate on the combined list, once"
    shape) -- never shared across runs.

    Raises:
        RuntimeError: any data file under `data_dir` is missing or
            malformed -- fails loudly at construction, before any
            `Team` is touched.
    """

    def __init__(self, data_dir: Path | None = None) -> None:
        resolved = data_dir if data_dir is not None else DEFAULT_DATA_DIR
        super().__init__(resolved)

    # -- full ladder, one Team --------------------------------------------

    def resolve(self, team: Team) -> None:
        """Run the full seven-rung ladder for ``team``, stamping
        ``latitude``/``longitude``/``location_precision``/
        ``matched_name``/``needs_review``/(on a school match)
        ``organization_website`` in place. Runs uniformly regardless of
        ``team.in_region`` -- an out-of-county team gets the same
        ladder, flagged separately by `sources/*`'s own `in_region`
        field, never special-cased here (see `teams/DESIGN.md`).
        """
        match = self.locate(team.organization, team.city, team.postal_code)
        team.latitude = match.latitude
        team.longitude = match.longitude
        team.location_precision = match.location_precision
        team.matched_name = match.matched_name
        team.needs_review = match.needs_review
        if match.location_precision == "school" and match.website:
            team.organization_website = match.website


def geocode_teams(teams: list[Team], *, data_dir: Path | str | None = None) -> list[Team]:
    """Resolve every `Team` in `teams` through the offline ladder, in
    place; return the same list.

    Structurally parallel to `teams.merge.merge_teams()`: mutates and
    returns its input, called once by `teams.pipeline.run_teams()`
    after `merge_teams()` and before `export_teams()`.

    Args:
        teams: already-merged `Team[]` (order irrelevant to this
            function).
        data_dir: the geocoding data directory. Defaults to
            :data:`DEFAULT_DATA_DIR` (the real committed `teams/data/`)
            when omitted -- tests should always pass an explicit
            fixture directory.

    Raises:
        RuntimeError: a data file under `data_dir` is missing or
            malformed (see `SchoolIndex`).
    """
    index = SchoolIndex(Path(data_dir) if data_dir is not None else None)
    for team in teams:
        index.resolve(team)
    return teams
