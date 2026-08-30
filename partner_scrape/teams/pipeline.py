"""Teams pipeline orchestration: `registry -> TeamSource(s) -> export`.

Structurally parallel to `partner_scrape/pipeline.py`'s `run()` -- this
module's whole job is sequencing, not business logic (see that module's
own docstring for the same self-check): enumerate this subsystem's own
Team Registry (`teams/registry/`, not `partner_scrape/registry/
sources/`), dispatch each active source to its `TeamSource`
implementation via `teams.sources.base.run()`, and hand the accumulated
`Team[]` to `teams.export.export_teams()`. It never imports
`partner_scrape.pipeline` or anything under `partner_scrape.adapters`
-- see `teams/sources/base.py`'s module docstring for why that boundary
is structural, not stylistic.

**No dispatch registry equivalent to `adapters.base.ADAPTERS`.**
`sources.base.run()` takes its `TeamSource` as an explicit argument
rather than looking one up in a shared table (see that module's own
docstring). `_TEAM_SOURCES` below is this module's own private mapping
from a Team Registry entry's `adapter_type` to the `TeamSource`
instance that handles it -- it is not exported, not imported by
anything else, and provides no path back into
`partner_scrape.pipeline.run()`. This is a plain lookup dict local to
the one caller that needs it, not a second `ADAPTERS`-shaped public
extension point.

Ticket 011-003 added the `"tba"` entry below plus a `merge_teams()`
call after every source has run and before export -- cross-league
organizational identity (`teams.merge`) has to see the full, combined
`Team[]` from every source, so it cannot run inside the per-source
loop. The per-source try/except this module already had (ticket
011-002) needed no change to give TBA the same isolation Migration
Concerns calls for (a missing/401 `TBA_KEY` degrades to FTC-only
output, never fails the whole run): `sources/tba.py`'s `discover()`
raises on a credential/probe failure by design (see its own module
docstring), and this loop already treats any `Exception` from
`run_team_source()` as "log and skip this source," regardless of which
source raised it.

Ticket 011-004 adds one more stage after `merge_teams()` and before
`export_teams()`: `teams.geo.geocode_teams()`, the seven-rung offline
location resolver. Like `merge_teams()`, it runs exactly once over the
full merged `Team[]` (not per-source) and is not wrapped in its own
try/except -- a malformed geocoding data file is a build-time defect
`teams.geo.SchoolIndex` raises loudly for (see that module's own
docstring), not a per-record failure to isolate the way a source's
network fetch is.

Sprint 013 ticket 006 adds one more stage, after `geocode_teams()` and
before `export_teams()`: `teams.website_overrides.
apply_website_overrides()`, which cleans junk/malformed values out of
the existing `website` field and applies a committed overlay of
websites/social links discovered by a web-search pass for teams whose
upstream source reported none (see that module's own docstring). It
runs *before* sprint 013's `teams.scrape.verify_team_websites()` (ticket
001, whose `depends-on` now includes ticket 006) so that stage fetches
the corrected, enlarged website set rather than the smaller, partly-
broken one this pipeline originally assumed. Like `merge_teams()`/
`geocode_teams()`, it is not wrapped in its own try/except -- a
malformed overlay data file is a build-time defect
`website_overrides._load_overlay` raises loudly for, not a per-record
failure to isolate.

Sprint 012 adds a third entry, `"static_roster"` (the committed FLL
roster -- see `sources/static_roster.py`'s own module docstring), plus
one new pre-flight check: `_check_sunset_seasons()`, called once per
`run_teams()` call, right after the (possibly `--source`-filtered)
active source list is resolved and before any source runs. It inspects
every active source's `SourceConfig.config.get("sunset_season")` and
logs exactly one `logging.WARNING` for the whole run if `today` (real
`date.today()` by default; tests pass an explicit `today` the same way
`export.export_opportunities()`'s own `today` parameter works) is past
any of their parsed season-end dates -- never more than one log call
regardless of how many sources are stale, and never raises: a sunset
date is a staleness signal for an operator to notice, not a reason to
stop publishing what may still be the best available data (see
`teams/DESIGN.md`'s Constraints).
"""

from __future__ import annotations

import logging
import re
from datetime import date
from pathlib import Path
from typing import Any

from partner_scrape.fetch import Fetcher, PoliteFetcher
from partner_scrape.registry.loader import load_active_sources
from partner_scrape.registry.schema import SourceConfig
from partner_scrape.teams.export import export_teams
from partner_scrape.teams.geo import geocode_teams
from partner_scrape.teams.merge import merge_teams
from partner_scrape.teams.model import Team
from partner_scrape.teams.sources.base import TeamSource, run as run_team_source
from partner_scrape.teams.sources.ftcscout import FTCScoutSource
from partner_scrape.teams.sources.static_roster import StaticRosterSource
from partner_scrape.teams.sources.tba import TBASource
from partner_scrape.teams.website_overrides import apply_website_overrides

logger = logging.getLogger(__name__)

#: Matches a `"YYYY-YY"` sunset-season config value, e.g. `"2026-27"`.
_SUNSET_SEASON_RE = re.compile(r"(\d{4})-(\d{2})")

#: This subsystem's own Team Registry directory -- `teams/registry/`,
#: disjoint from `partner_scrape/registry/sources/` (see
#: `teams/DESIGN.md`'s Constraints and Invariants).
DEFAULT_TEAMS_REGISTRY_DIR = Path(__file__).resolve().parent / "registry"

#: `adapter_type` (a Team Registry TOML file's own field, e.g.
#: `ftc-sd.toml`'s `adapter_type = "ftcscout"`, `frc-sd.toml`'s
#: `adapter_type = "tba"`) -> the `TeamSource` instance that handles
#: it. See this module's own docstring for why this is a private
#: lookup, not an `ADAPTERS`-shaped public registry.
_TEAM_SOURCES: dict[str, TeamSource] = {
    "ftcscout": FTCScoutSource(),
    "tba": TBASource(),
    "static_roster": StaticRosterSource(),
}


def _parse_sunset_season(season: str) -> date | None:
    """Parse a `"YYYY-YY"` sunset-season string into the date its
    season is considered over: June 1 of the second year (e.g.
    `"2026-27"` -> `2027-06-01`) -- an FLL season runs roughly
    September through the following May/June, so "past the season" is
    first meaningfully true once the *next* school year would have
    already started preparing.

    Returns `None` for a value that doesn't match the expected shape
    (defensive: a malformed config value should silently produce no
    warning, not crash a run over a typo in a TOML file).
    """
    match = _SUNSET_SEASON_RE.fullmatch(season.strip())
    if not match:
        return None
    first_year = int(match.group(1))
    suffix = int(match.group(2))
    second_year = (first_year // 100) * 100 + suffix
    if second_year <= first_year:
        second_year += 100
    return date(second_year, 6, 1)


def _check_sunset_seasons(sources: list[SourceConfig], *, today: date | None = None) -> None:
    """Log exactly one `logging.WARNING` if any of `sources` carries a
    `sunset_season` whose parsed end date `today` has passed.

    Never raises and never logs more than once per call, regardless of
    how many active sources are stale -- see this module's own
    docstring for the full rationale. `sources` is the already-resolved
    (and possibly `--source`-filtered) active source list `run_teams()`
    is about to dispatch; a source filtered out of this run's `sources`
    is not checked, matching the operational intent ("only warn about
    what this run is actually touching").
    """
    reference_date = today if today is not None else date.today()

    stale: list[tuple[str, str, date]] = []
    for source_config in sources:
        season = source_config.config.get("sunset_season")
        if not season:
            continue
        end_date = _parse_sunset_season(str(season))
        if end_date is not None and reference_date > end_date:
            stale.append((source_config.source_id, str(season), end_date))

    if stale:
        logger.warning(
            "%d team source(s) past their sunset season -- data may no "
            "longer be refreshable: %s. See teams/DESIGN.md's Open "
            "Questions.",
            len(stale),
            ", ".join(f"{sid!r} ({season}, ended {end})" for sid, season, end in stale),
        )


def run_teams(
    *,
    registry_dir: str | Path | None = None,
    source: str | None = None,
    site_dir: str | Path | None = None,
    fetcher: Fetcher | None = None,
    dry_run: bool = False,
    geo_data_dir: str | Path | None = None,
    website_data_dir: str | Path | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """Run the Teams pipeline end-to-end: Team Registry -> `TeamSource`(s)
    -> `merge_teams()` -> `geocode_teams()` -> `apply_website_overrides()`
    -> `export_teams()`.

    Args:
        registry_dir: Team Registry directory to load sources from.
            Defaults to :data:`DEFAULT_TEAMS_REGISTRY_DIR` (the real
            seed registry, `partner_scrape/teams/registry/`) when
            omitted.
        source: when given, restricts the run to the single acquisition
            source whose `adapter_type` matches (e.g. `"ftcscout"` or
            `"tba"`) -- the CLI's `--source` flag. Unlike
            `pipeline.run()`'s `source_id` filter (which matches a
            registry file's stem), this matches the *kind* of source,
            since a TBA outage needs to be isolated by acquisition
            method, not by which one organization's TOML file it came
            from.
        site_dir: sibling `stem-ecosystem` checkout to write
            `teams.json` into. Defaults to `Config.get_site_dir()` when
            omitted (via `export_teams`). Tests should always pass an
            explicit `tmp_path`-based directory here.
        fetcher: the `Fetcher` every active source retrieves raw
            content through. Defaults to a real `PoliteFetcher()` when
            omitted -- the production path. Tests inject a fixture
            `Fetcher` here so the whole run touches no sockets.
        dry_run: when `True`, compute and return the would-be-written
            export payload without touching disk (`export_teams`
            honors this the same way `export_opportunities` does).
        geo_data_dir: the offline geocoding data directory
            `teams.geo.geocode_teams()` reads. Defaults to
            `teams.geo.DEFAULT_DATA_DIR` (the real committed
            `teams/data/`) when omitted. Tests that need to control
            geocoding outcomes precisely should pass an explicit
            fixture directory here; tests that only care about
            source/merge behavior can safely omit it and exercise the
            real committed data files, matching this module's existing
            "trust the real registry in tests" convention.
        website_data_dir: the directory `teams.website_overrides.
            apply_website_overrides()` reads `discovered-websites.toml`
            from (sprint 013 ticket 006). Defaults to
            `website_overrides.DEFAULT_DATA_DIR` (the real committed
            `teams/data/`) when omitted, mirroring `geo_data_dir`'s
            convention exactly. Tests that need to control the overlay
            precisely should pass an explicit fixture directory here.
        today: the reference date `_check_sunset_seasons()` compares
            every active source's `sunset_season` against. Defaults to
            real `date.today()` when omitted, matching
            `export.export_opportunities()`'s own `today` parameter
            convention. Tests should pass an explicit value for
            determinism.

    Returns:
        `export_teams()`'s `{"meta": ..., "teams": [...]}` payload,
        passed through unchanged.
    """
    sources = load_active_sources(
        Path(registry_dir) if registry_dir is not None else DEFAULT_TEAMS_REGISTRY_DIR
    )

    if source is not None:
        sources = [s for s in sources if s.adapter_type == source]

    # A registry-level pre-flight check, independent of whether any
    # source's acquisition later succeeds or fails -- see this module's
    # own docstring and _check_sunset_seasons()'s.
    _check_sunset_seasons(sources, today=today)

    active_fetcher = fetcher if fetcher is not None else PoliteFetcher()

    teams: list[Team] = []
    for source_config in sources:
        team_source = _TEAM_SOURCES.get(source_config.adapter_type)
        if team_source is None:
            logger.warning(
                "No TeamSource registered for adapter_type %r "
                "(source_id=%r); skipping",
                source_config.adapter_type,
                source_config.source_id,
            )
            continue

        try:
            source_teams = run_team_source(source_config, team_source, active_fetcher)
        except Exception:
            # Per-source error isolation, matching pipeline.run()'s own
            # SUC-008 contract: one broken source is logged and
            # skipped, never fatal to the rest of the run. This is what
            # lets ticket 011-003's TBA outage handling (Migration
            # Concerns: "a missing TBA_KEY degrades to FTC-only
            # teams.json") fall straight out of this loop with no
            # further change here.
            logger.exception(
                "Team source %r (adapter_type=%r) failed; skipping it, "
                "run continues with the remaining sources",
                source_config.source_id,
                source_config.adapter_type,
            )
            continue

        logger.info(
            "Team source %r yielded %d team(s)", source_config.source_id, len(source_teams)
        )
        teams.extend(source_teams)

    # Cross-league organizational identity (teams.merge) needs the
    # full, combined Team[] from every source that succeeded above --
    # it cannot run inside the per-source loop. merge_teams() mutates
    # and returns the same list; it never raises for any input it can
    # receive here (see its own docstring), so it is not wrapped in
    # its own try/except the way each source's acquisition is.
    teams = merge_teams(teams)

    # The offline geocoding ladder (teams.geo) runs once over the full
    # merged Team[], same shape as merge_teams() above and for the same
    # reason -- it is not per-source and not wrapped in its own
    # try/except: a malformed data file is a build-time defect
    # SchoolIndex raises loudly for (see teams/geo.py's own docstring),
    # never a per-record failure to isolate the way a source fetch is.
    teams = geocode_teams(teams, data_dir=geo_data_dir)

    # Sprint 013 ticket 006: clean junk/malformed existing website
    # values and apply the committed discovered-website/social overlay,
    # once over the full merged+geocoded Team[], same shape as
    # merge_teams()/geocode_teams() above and for the same reason -- a
    # malformed overlay data file is a build-time defect
    # apply_website_overrides() raises loudly for, never a per-record
    # failure to isolate. Runs before sprint 013's
    # verify_team_websites() (ticket 001, not yet wired in here) so
    # that stage sees the corrected, enlarged website set.
    teams = apply_website_overrides(teams, data_dir=website_data_dir)

    return export_teams(teams, site_dir=site_dir, dry_run=dry_run)
