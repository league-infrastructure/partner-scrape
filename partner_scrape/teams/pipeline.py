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

Ticket 011-003 (this ticket) adds the `"tba"` entry below plus a
`merge_teams()` call after every source has run and before export --
cross-league organizational identity (`teams.merge`) has to see the
full, combined `Team[]` from every source, so it cannot run inside the
per-source loop. The per-source try/except this module already had
(ticket 011-002) needed no change to give TBA the same isolation
Migration Concerns calls for (a missing/401 `TBA_KEY` degrades to
FTC-only output, never fails the whole run): `sources/tba.py`'s
`discover()` raises on a credential/probe failure by design (see its
own module docstring), and this loop already treats any `Exception`
from `run_team_source()` as "log and skip this source," regardless of
which source raised it.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from partner_scrape.fetch import Fetcher, PoliteFetcher
from partner_scrape.registry.loader import load_active_sources
from partner_scrape.teams.export import export_teams
from partner_scrape.teams.merge import merge_teams
from partner_scrape.teams.model import Team
from partner_scrape.teams.sources.base import TeamSource, run as run_team_source
from partner_scrape.teams.sources.ftcscout import FTCScoutSource
from partner_scrape.teams.sources.tba import TBASource

logger = logging.getLogger(__name__)

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
}


def run_teams(
    *,
    registry_dir: str | Path | None = None,
    source: str | None = None,
    site_dir: str | Path | None = None,
    fetcher: Fetcher | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run the Teams pipeline end-to-end: Team Registry -> `TeamSource`(s)
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

    Returns:
        `export_teams()`'s `{"meta": ..., "teams": [...]}` payload,
        passed through unchanged.
    """
    sources = load_active_sources(
        Path(registry_dir) if registry_dir is not None else DEFAULT_TEAMS_REGISTRY_DIR
    )

    if source is not None:
        sources = [s for s in sources if s.adapter_type == source]

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

    return export_teams(teams, site_dir=site_dir, dry_run=dry_run)
