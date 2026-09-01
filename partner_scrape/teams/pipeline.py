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

Sprint 013 ticket 001 adds the next stage, immediately after
`apply_website_overrides()` and before `export_teams()`:
`teams.scrape.verify_team_websites()`, which fetches every team's
(corrected, enlarged) `website` through this same `fetcher` parameter,
robots-checked first (`fetch.is_allowed()`, matching
`discovery/hub_scan.py::scan_hub()`'s per-page pattern), and sets
`Team.website_status` to `"confirmed"`/`"unverified"`/`"none"`. Unlike
`merge_teams()`/`geocode_teams()`/`apply_website_overrides()`, this
stage's own per-team fetch failures are already isolated *inside*
`verify_team_websites()` itself (never raising for one team's dead
link or robots disallow), so `run_teams()` does not additionally wrap
this call in a try/except either -- the one case this stage can still
raise for is a `Fetcher`-level bug, which is exactly as fatal here as
it would be for any other stage. Its returned `dict[team_id, html]` is
kept as a local variable (`fetch_results`, deliberately never assigned
to any `Team` field or `run_teams()`'s own return value -- see
`teams.scrape`'s own module docstring) for `teams.sponsor_extract.
extract_sponsors()` to consume.

Sprint 013 ticket 005 adds the next stage, immediately after
`verify_team_websites()` and before `export_teams()`:
`teams.sponsor_extract.extract_sponsors()`, which consumes
`fetch_results` (never assigned to a `Team` field, as above) to gather
candidates, classify them via the injectable `llm_client`, validate/
denylist-guard the result, and merge surviving names into
`Team.sponsors`/`Team.sponsor_provenance`. `llm_client`/`sponsor_cache`
are new `run_teams()` parameters, defaulting to a real
`AnthropicSponsorLLMClient()`/`SponsorCache()` when omitted -- the same
default-to-production convention `fetcher` already follows -- but
constructed lazily, only when this stage actually runs, so a
`--no-sponsors` run never touches the `anthropic` SDK at all. Like
`verify_team_websites()`, `extract_sponsors()` isolates its own
per-team failures internally (fail-open, SUC-004's Error Flows), so no
additional try/except wraps this call either.

Ticket 005's reopening adds one more stage, immediately after the
`extract_sponsors()`/`--no-sponsors` branch above and before
`export_teams()`: `teams.sponsor_canonical.canonicalize_sponsors()`,
which mutates the full `Team[]` in place so the same real company is
published under one consistent display name everywhere it is
mentioned, not just within one team's own `sponsors` list -- see that
module's own docstring for why a per-team merge (`extract_sponsors()`'s
own step 6) can never catch a company two *different* teams' own
structured records happen to spell differently. Runs unconditionally,
even under `--no-sponsors`, since a purely-structured sponsor list
still needs this cross-team pass. Like `merge_teams()`/`geocode_teams()`
above, it is not wrapped in its own try/except -- it never raises for
any input it can receive here.

Sprint 016 ticket 005 adds a fourth entry, `"robotevents"` (VEX
Robotics Competition, CA Region 4 -- see `sources/robotevents.py`'s own
module docstring). Like TBA, its `discover()` raises on any probe
failure (missing/invalid `ROBOTEVENTS_KEY` included) rather than
degrading gracefully, so this loop's existing per-source
`try`/`except` isolates it identically -- no VEX-specific case needed
here either.

Sprint 021 ticket 004 adds one more stage, immediately after
`canonicalize_sponsors()` and before `export_teams()`:
`teams.description_extract.extract_descriptions()`, which reuses the
same `fetch_results` dict `extract_sponsors()` already consumes (no
second fetch) to gather a bounded content string per confirmed team
page (`teams.description_candidates.gather_description_content()`),
summarize it via the injectable `description_llm_client` (never
generating from open context -- only summarizing the already-gathered,
bounded text), validate the raw response against a no-email guard and a
length cap, and publish `Team.description`/`description_status`/
`description_provenance`/`description_fetched_at`. `description_llm_client`/
`description_cache` are new `run_teams()` parameters, defaulting to a
real `AnthropicDescriptionLLMClient()`/`DescriptionCache()` when
omitted -- the same default-to-production convention `llm_client`/
`sponsor_cache` already follow for sponsor extraction -- but
constructed lazily, only when this stage actually runs, so a
`--no-descriptions` run never touches the `anthropic` SDK at all. Like
`extract_sponsors()`, `extract_descriptions()` isolates its own
per-team failures internally (fail-open, SUC-023's Error Flows), so no
additional try/except wraps this call either.

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

Sprint 023 ticket 001 adds a second alerting convention alongside
`_check_sunset_seasons()`'s pre-flight one, this time inside the
per-source loop itself: a source whose acquisition raises
`config.CredentialError` (a missing/invalid `TBA_KEY`/
`ROBOTEVENTS_KEY`, or a live 401 -- see that class's own docstring)
still gets the exact same per-source `logger.exception()` ERROR log
every other failure gets, unchanged, but is additionally recorded;
once the per-source loop finishes, exactly one aggregate
`logger.warning()` names every league/source that failed on a
credential error, mirroring `_check_sunset_seasons()`'s own "never
more than one log call regardless of how many are affected"
convention. The point (issue 62) is telling a structural, recurring
credential outage -- one an operator must fix, that will keep
recurring on every run until they do -- apart from a one-off scrape
hiccup that is indistinguishable from it today, without loosening the
per-source isolation this loop already gives every failure: a
credential failure still degrades, never aborts, the run -- this
ticket only adds a *second*, additional signal on top of the existing
isolation, it does not change the isolation itself. `_SOURCE_LEAGUES`
below is this addition's own private `adapter_type -> League` lookup,
matching `_TEAM_SOURCES`'s existing "private lookup local to the one
caller that needs it" convention, not a new public registry.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from pathlib import Path
from typing import Any

from partner_scrape.config import CredentialError
from partner_scrape.fetch import Fetcher, PoliteFetcher
from partner_scrape.registry.loader import load_active_sources
from partner_scrape.registry.schema import SourceConfig
from partner_scrape.teams.description_cache import DescriptionCache
from partner_scrape.teams.description_extract import extract_descriptions
from partner_scrape.teams.description_llm import (
    AnthropicDescriptionLLMClient,
    DescriptionLLMClient,
)
from partner_scrape.teams.export import export_teams
from partner_scrape.teams.geo import geocode_teams
from partner_scrape.teams.merge import merge_teams
from partner_scrape.teams.model import Team
from partner_scrape.teams.scrape import verify_team_websites
from partner_scrape.teams.sources.base import TeamSource, run as run_team_source
from partner_scrape.teams.sources.ftcscout import FTCScoutSource
from partner_scrape.teams.sources.robotevents import VexTeamSource
from partner_scrape.teams.sources.static_roster import StaticRosterSource
from partner_scrape.teams.sources.tba import TBASource
from partner_scrape.teams.sponsor_cache import SponsorCache
from partner_scrape.teams.sponsor_canonical import canonicalize_sponsors
from partner_scrape.teams.sponsor_extract import extract_sponsors
from partner_scrape.teams.sponsor_llm import AnthropicSponsorLLMClient, SponsorLLMClient
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
    "robotevents": VexTeamSource(),
}

#: `adapter_type` -> `League` (`teams/model.py`'s `League` docstring) --
#: sprint 023 ticket 001's own private lookup, matching `_TEAM_SOURCES`'s
#: "private lookup local to the one caller that needs it" convention
#: exactly, not a new public registry. Used only by `run_teams()`'s
#: per-source loop below to name which league a `CredentialError`
#: failure belongs to in the aggregate alert -- see this module's own
#: docstring.
_SOURCE_LEAGUES: dict[str, str] = {
    "ftcscout": "FTC",
    "tba": "FRC",
    "static_roster": "FLL",
    "robotevents": "VEX",
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
    llm_client: SponsorLLMClient | None = None,
    sponsor_cache: SponsorCache | None = None,
    no_sponsors: bool = False,
    description_llm_client: DescriptionLLMClient | None = None,
    description_cache: DescriptionCache | None = None,
    no_descriptions: bool = False,
    today: date | None = None,
) -> dict[str, Any]:
    """Run the Teams pipeline end-to-end: Team Registry -> `TeamSource`(s)
    -> `merge_teams()` -> `geocode_teams()` -> `apply_website_overrides()`
    -> `verify_team_websites()` -> `extract_sponsors()` ->
    `canonicalize_sponsors()` -> `extract_descriptions()` ->
    `export_teams()`.

    Sprint 023 ticket 001: a source whose acquisition raises
    `config.CredentialError` is still isolated by the per-source
    `try`/`except` below exactly like any other failure -- logged at
    ERROR with a traceback, skipped, run continues -- but is
    additionally recorded, and once every source has run, exactly one
    aggregate `logger.warning()` names every affected league/source.
    No new parameter here: the alert is unconditional whenever a
    credential failure occurs, mirroring `_check_sunset_seasons()`'s
    own no-opt-out design.

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
        llm_client: the injectable `SponsorLLMClient`
            `extract_sponsors()` (sprint 013 ticket 005) classifies
            sponsor candidates through. Defaults to a real
            `AnthropicSponsorLLMClient()` when omitted -- the same
            default-to-production convention `fetcher` already follows
            -- constructed lazily, only when sponsor extraction actually
            has at least one confirmed page to look at (`no_sponsors`
            is `False` and `verify_team_websites()` produced a non-empty
            `fetch_results`), so a `--no-sponsors` run and every test
            that only cares about acquisition/merge/geocoding never
            touch the `anthropic` SDK at all. Tests that do exercise
            sponsor extraction inject a `FixtureSponsorLLMClient` here.
        sponsor_cache: the `SponsorCache` `extract_sponsors()` looks up
            and stores classification results in. Defaults to a real
            `SponsorCache()` (the real configured cache directory) when
            omitted, constructed lazily for the same reason as
            `llm_client` above. Tests should always pass an explicit
            `tmp_path`-based `SponsorCache` here.
        no_sponsors: when `True`, skip `extract_sponsors()` entirely --
            the CLI's `--no-sponsors` flag. `verify_team_websites()`
            always runs regardless (SUC-001's cheap, certain half is
            unconditional); only sponsor classification (the
            uncertain, `ANTHROPIC_API_KEY`-dependent, Anthropic-API-cost
            half) is skippable.
        description_llm_client: the injectable `DescriptionLLMClient`
            `extract_descriptions()` (sprint 021 ticket 004) summarizes
            gathered team-website content through. Defaults to a real
            `AnthropicDescriptionLLMClient()` when omitted -- the same
            default-to-production convention `llm_client` already
            follows for sponsor extraction -- constructed lazily, only
            when description extraction actually has at least one
            confirmed page to look at (`no_descriptions` is `False` and
            `verify_team_websites()` produced a non-empty
            `fetch_results`), so a `--no-descriptions` run and every
            test that only cares about acquisition/merge/geocoding/
            sponsor extraction never touches the `anthropic` SDK for
            this stage at all. Tests that do exercise description
            extraction inject a `FixtureDescriptionLLMClient` here.
        description_cache: the `DescriptionCache` `extract_descriptions()`
            looks up and stores summarization results in. Defaults to a
            real `DescriptionCache()` (the real configured cache
            directory) when omitted, constructed lazily for the same
            reason as `description_llm_client` above. Tests should
            always pass an explicit `tmp_path`-based `DescriptionCache`
            here.
        no_descriptions: when `True`, skip `extract_descriptions()`
            entirely -- the CLI's `--no-descriptions` flag.
            `verify_team_websites()`/`extract_sponsors()` always run
            regardless; only description summarization (the uncertain,
            `ANTHROPIC_API_KEY`-dependent, Anthropic-API-cost half) is
            skippable.
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

    # Sprint 023 ticket 001: recorded here, one entry per source whose
    # acquisition raised config.CredentialError -- (source_id,
    # adapter_type, league, message) -- and consumed once, after the
    # loop below, to log exactly one aggregate warning. See this
    # module's own docstring.
    credential_failures: list[tuple[str, str, str, str]] = []

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
        except CredentialError as exc:
            # Sprint 023 ticket 001: same per-source ERROR + traceback
            # log as the plain-Exception branch below, unchanged -- a
            # credential failure is still isolated exactly like any
            # other failure, never fatal to the rest of the run. The
            # only addition is recording it here so the aggregate
            # warning after this loop can name it specifically; issue
            # 62's complaint was never "we don't log it," it's that a
            # structural, recurring credential outage looks identical,
            # in both the log and teams.json, to a one-off scrape
            # hiccup or a genuine empty result.
            logger.exception(
                "Team source %r (adapter_type=%r) failed; skipping it, "
                "run continues with the remaining sources",
                source_config.source_id,
                source_config.adapter_type,
            )
            league = _SOURCE_LEAGUES.get(source_config.adapter_type, source_config.adapter_type)
            credential_failures.append(
                (source_config.source_id, source_config.adapter_type, league, str(exc))
            )
            continue
        except Exception:
            # Per-source error isolation, matching pipeline.run()'s own
            # SUC-008 contract: one broken source is logged and
            # skipped, never fatal to the rest of the run. This is what
            # lets ticket 011-003's TBA outage handling (Migration
            # Concerns: "a missing TBA_KEY degrades to FTC-only
            # teams.json") fall straight out of this loop with no
            # further change here. config.CredentialError is caught
            # above, before this branch, so it never reaches here --
            # everything else (a transient/one-off failure) still does.
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

    # Sprint 023 ticket 001: exactly one aggregate warning for the whole
    # run if any source above failed on a credential error -- never more
    # than one log call, matching _check_sunset_seasons()'s own
    # convention -- and none at all when zero credential failures
    # occurred. This is a second, additional signal on top of the
    # per-source ERROR logs already emitted above; it does not change
    # per-source isolation (every failed source was already skipped,
    # the run already continued).
    if credential_failures:
        logger.warning(
            "%d team source(s) failed on a credential error -- this is "
            "structural and will recur on every run until an operator "
            "fixes the credential (unlike a transient scrape failure): "
            "%s. See config.CredentialError's own docstring.",
            len(credential_failures),
            ", ".join(
                f"{league} ({source_id!r}, adapter_type={adapter_type!r}): {message}"
                for source_id, adapter_type, league, message in credential_failures
            ),
        )

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
    # verify_team_websites() so that stage sees the corrected, enlarged
    # website set.
    teams = apply_website_overrides(teams, data_dir=website_data_dir)

    # Sprint 013 ticket 001: fetch and classify every team's (now
    # corrected, enlarged) website, once over the full team list, same
    # "operate on the whole list once" shape as the three stages above.
    # Unlike those three, this stage isolates its own per-team fetch
    # failures internally (see teams.scrape's own docstring) -- a dead
    # link or robots disallow for one team never raises out of
    # verify_team_websites(), so no additional try/except is needed
    # here. The returned dict is a plain local variable, never assigned
    # to any Team field or this function's return value (see this
    # module's own docstring) -- teams.sponsor_extract.extract_sponsors()
    # is its consumer, immediately below.
    fetch_results = verify_team_websites(teams, active_fetcher)

    # Sprint 013 ticket 005: the final new stage. --no-sponsors skips it
    # entirely. llm_client/sponsor_cache are constructed lazily, only
    # here, and only when there is at least one confirmed page to look
    # at -- an empty fetch_results means extract_sponsors() would do
    # nothing for any team regardless (its own per-team loop skips a
    # team absent from fetch_results before any cache/LLM touch), so
    # skipping construction here too means a run with no confirmed
    # website (or --no-sponsors) never touches the anthropic SDK or
    # requires a configured cache directory. Like verify_team_websites()
    # immediately above, extract_sponsors() isolates its own per-team
    # failures internally (fail-open, SUC-004's Error Flows), so no
    # additional try/except wraps this call either.
    if no_sponsors:
        logger.info("Sponsor extraction skipped (--no-sponsors)")
    elif not fetch_results:
        logger.info("Sponsor extraction skipped (no confirmed team pages fetched)")
    else:
        active_llm_client = llm_client if llm_client is not None else AnthropicSponsorLLMClient()
        active_sponsor_cache = sponsor_cache if sponsor_cache is not None else SponsorCache()
        extract_sponsors(teams, fetch_results, active_llm_client, active_sponsor_cache)

    # Sprint 013 ticket 005 (reopened): corpus-wide sponsor-name
    # canonicalization, after extract_sponsors() (or --no-sponsors) and
    # before export_teams(). Unlike extract_sponsors(), this runs
    # unconditionally, even under --no-sponsors -- a purely-structured
    # sponsor list still needs cross-team canonicalization, since the
    # same real company is routinely reported under different raw
    # spellings by different teams' own structured records (e.g.
    # "QualComm" vs. "Qualcomm" vs. "Qualcomm Inc"), which no per-team
    # dedup, however good, can ever see. See sponsor_canonical.py's own
    # module docstring for the full rationale. Never raises for any
    # input it can receive here (matches merge_teams()/geocode_teams()'s
    # own "not wrapped in its own try/except" convention above).
    canonicalize_sponsors(teams)

    # Sprint 021 ticket 004: the final new stage. --no-descriptions
    # skips it entirely. description_llm_client/description_cache are
    # constructed lazily, only here, and only when there is at least
    # one confirmed page to look at -- an empty fetch_results means
    # extract_descriptions() would do nothing for any team regardless
    # (its own per-team loop skips a team absent from fetch_results
    # before any cache/LLM touch), so skipping construction here too
    # means a run with no confirmed website (or --no-descriptions)
    # never touches the anthropic SDK or requires a configured cache
    # directory. Like extract_sponsors() above, extract_descriptions()
    # isolates its own per-team failures internally (fail-open,
    # SUC-023's Error Flows), so no additional try/except wraps this
    # call either.
    if no_descriptions:
        logger.info("Description extraction skipped (--no-descriptions)")
    elif not fetch_results:
        logger.info("Description extraction skipped (no confirmed team pages fetched)")
    else:
        active_description_llm_client = (
            description_llm_client
            if description_llm_client is not None
            else AnthropicDescriptionLLMClient()
        )
        active_description_cache = (
            description_cache if description_cache is not None else DescriptionCache()
        )
        extract_descriptions(
            teams, fetch_results, active_description_llm_client, active_description_cache
        )

    return export_teams(teams, site_dir=site_dir, dry_run=dry_run)
