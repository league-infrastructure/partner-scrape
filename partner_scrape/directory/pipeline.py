"""Directory pipeline orchestration: `Registry -> PlaceSource(s)/
ClubSource(s) -> geo fallback/geocoding -> export`.

Structurally parallel to `teams.pipeline.run_teams()` -- this module's
whole job is sequencing, not business logic (see that module's own
docstring for the same self-check): enumerate this subsystem's own
Registry (`directory/registry/`, not `partner_scrape/registry/
sources/` and not `teams/registry/`), dispatch each active source to
its `PlaceSource` or `ClubSource` implementation via
`directory.sources.base.run()`/`run_club_source()`, resolve location
for both record types through the shared offline geocoding ladder
(`geo_ladder.GeoLadder`, ticket 018-006), and hand the accumulated
`Place[]`/`Club[]` to `directory.export.export_directory()`. It never
imports `partner_scrape.pipeline`, `partner_scrape.adapters`, or
`partner_scrape.teams` -- see `directory/sources/base.py`'s module
docstring for why the `teams`-avoidance boundary in particular is
structural (sprint.md's Design Rationale: importing `teams/` from
`directory/` would be "a semantically backwards dependency").

**Ticket 018-007 wired Places only; ticket 018-008 (this ticket) adds
the analogous `Club`-side dispatch.** `_PLACE_SOURCES`/
`_apply_geo_fallback()` are unchanged from ticket 007. `_CLUB_SOURCES`
and `_apply_club_geocoding()` are this ticket's additions, following
that module's shape rather than importing from it (there is nothing to
import -- `Place` and `Club` are separate flat dataclasses, per
sprint.md's Design Rationale).

**One combined dispatch loop, not two separate ones, despite
`directory/DESIGN.md`'s forward-looking note describing "a new
`_CLUB_SOURCES` table and acquisition loop."** A literal second `for`
loop over the same `sources` list would make the *existing* Place loop
log a spurious "no PlaceSource registered" warning for every real Club
registry entry (its `adapter_type` is never in `_PLACE_SOURCES`) --
implementation judgment ticket 007's own DESIGN.md explicitly left
open ("ticket 007/008's implementation judgment"). One loop that
checks `_PLACE_SOURCES` then `_CLUB_SOURCES` per `source_config`
dispatches each registry entry to exactly the one table it actually
belongs to, and only warns when an `adapter_type` is in neither.
`directory.export.export_directory()` is now called with a real
`clubs` argument; see that module's own docstring for how `clubs.json`
is written alongside `places.json`.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from partner_scrape.config import get_site_dir
from partner_scrape.directory.export import export_directory
from partner_scrape.directory.model import Club, Place
from partner_scrape.directory.sources.base import (
    ClubSource,
    PlaceSource,
    run as run_place_source,
    run_club_source,
)
from partner_scrape.directory.sources.hack_club_static_roster import HackClubStaticRosterSource
from partner_scrape.directory.sources.static_roster import StaticRosterSource
from partner_scrape.fetch import Fetcher, PoliteFetcher
from partner_scrape.geo_ladder import GeoLadder
from partner_scrape.registry.loader import load_active_sources
from partner_scrape.registry.validate_roster import check_partner_references

logger = logging.getLogger(__name__)

#: This subsystem's own Registry directory -- `directory/registry/`,
#: disjoint from the root-level `registry/sources/` and from
#: `teams/registry/` (see `directory/DESIGN.md`'s Constraints). Holds
#: both Place Registry entries (`places-sd.toml`) and, from this
#: ticket, Club Registry entries (`hack-club-sd.toml`) -- one shared
#: registry directory for the whole `directory/` subsystem, per
#: sprint.md's Open Questions recommendation ("one directory command
#: ... mirrors teams"). Named `DEFAULT_PLACES_REGISTRY_DIR` for
#: backward compatibility with ticket 007's existing public name and
#: its tests' imports -- not renamed, to avoid an unrelated diff to a
#: name several tests already import.
DEFAULT_PLACES_REGISTRY_DIR = Path(__file__).resolve().parent / "registry"

#: This module's own offline geocoding data directory --
#: `directory/data/` -- a committed duplicate of `teams/data/`'s
#: ZIP/city-centroid tables, never `teams/data/` itself (see
#: `directory/data/zip-centroids.toml`'s own header for the full "why
#: duplicated, not imported across the teams/directory boundary"
#: rationale). Ticket 007 left `sd-schools-public.tsv`/
#: `sd-schools-private.tsv`/`school-overrides.toml` genuinely empty
#: (Places never route through the ladder's school-matching rungs);
#: this ticket (018-008) is the first real consumer of those files and
#: populates them with a byte-identical copy of `teams/data/`'s own CDE
#: public and NCES private school directories -- Hack Club chapters are
#: school-hosted, so `_apply_club_geocoding()` below needs the real
#: data, not the empty placeholder ticket 007 shipped.
DEFAULT_GEO_DATA_DIR = Path(__file__).resolve().parent / "data"

#: `adapter_type` (a Place Registry TOML file's own field, e.g.
#: `places-sd.toml`'s `adapter_type = "static_roster"`) -> the
#: `PlaceSource` instance that handles it. Private, not exported --
#: mirrors `teams.pipeline._TEAM_SOURCES`'s own "plain lookup local to
#: one function, not a public ADAPTERS-shaped extension point"
#: rationale (see that module's own docstring).
_PLACE_SOURCES: dict[str, PlaceSource] = {
    "static_roster": StaticRosterSource(),
}

#: `adapter_type` (a Club Registry TOML file's own field, e.g.
#: `hack-club-sd.toml`'s `adapter_type = "hack_club_static_roster"`) ->
#: the `ClubSource` instance that handles it. Same "plain lookup, not a
#: public extension point" rationale as `_PLACE_SOURCES` above --
#: ticket 018-008's own addition.
_CLUB_SOURCES: dict[str, ClubSource] = {
    "hack_club_static_roster": HackClubStaticRosterSource(),
}


def _apply_geo_fallback(places: list[Place], *, data_dir: str | Path | None) -> list[Place]:
    """For any `Place` the curated source left with `location_precision
    == "none"` (no hand-curated address-level coordinate), fall back to
    the shared `geo_ladder.GeoLadder`'s ZIP/city-centroid rungs (5-6)
    directly -- never `GeoLadder.locate()`'s organization-name
    school-matching rungs 1-4, which have no meaning for a `Place` (a
    venue is not a school and has no sponsoring organization to match).
    Mutates and returns the same list, matching
    `teams.geo.geocode_teams()`'s "operate on the combined list, once"
    shape.

    Constructs a `GeoLadder` only when at least one `Place` actually
    needs the fallback -- for this ticket's real curated dataset, that
    is a single entry (`atlas-labs`, not yet open) -- so a
    `directory` run whose static roster resolved every place by hand
    never pays the ladder's data-file-loading cost at all.

    A `Place` that exhausts both fallback rungs keeps
    `location_precision == "none"` and no coordinates -- the same
    "never guess" honesty rule `geo_ladder.py` documents for `Team`,
    applied here without ever invoking the ladder's school-matching
    machinery.
    """
    needs_fallback = [p for p in places if p.location_precision == "none"]
    if not needs_fallback:
        return places

    resolved_data_dir = Path(data_dir) if data_dir is not None else DEFAULT_GEO_DATA_DIR
    ladder = GeoLadder(resolved_data_dir)

    for place in needs_fallback:
        zip_coords = ladder.resolve_zip(place.postal_code) if place.postal_code else None
        if zip_coords is not None:
            place.latitude, place.longitude = zip_coords
            place.location_precision = "zip"
            place.matched_name = f"ZIP {place.postal_code.strip()[:5]} centroid"
            continue

        city_coords = ladder.resolve_city(place.city) if place.city else None
        if city_coords is not None:
            place.latitude, place.longitude = city_coords
            place.location_precision = "city"
            place.matched_name = f"{place.city.strip()} (city centroid)"
        # Else: both rungs missed -- location_precision stays "none",
        # coordinates stay None. Deliberate, not a bug.

    return places


def _apply_club_geocoding(clubs: list[Club], *, data_dir: str | Path | None) -> list[Club]:
    """Resolve every `Club`'s location through the shared
    `geo_ladder.GeoLadder`'s *full* seven-rung ladder
    (`GeoLadder.locate()`), keyed on `Club.host_school`/`Club.city`/
    `Club.postal_code` -- unlike `_apply_geo_fallback()`'s Place-only
    ZIP/city-centroid-only shortcut, a `Club` genuinely has a
    sponsoring organization (its host school) to run through the
    ladder's school-matching rungs 1-4, mirroring
    `teams.geo.SchoolIndex.resolve(team)`'s exact stamping convention:
    `latitude`/`longitude`/`location_precision`/`matched_name`/
    `needs_review` are always stamped, and `host_school_website` is
    stamped too, but only on a `location_precision == "school"` match
    that itself carries a website (public schools only -- NCES's
    private-school data has no website column) -- never onto
    `Club.website`, which is the chapter's own site (see
    `directory/model.py`'s `Club` docstring for why those two fields
    are kept separate). Mutates and returns the same list, matching
    `teams.geo.geocode_teams()`'s "operate on the combined list, once"
    shape.

    Constructs a `GeoLadder` only when `clubs` is non-empty -- mirrors
    `_apply_geo_fallback()`'s own "don't pay the load cost for nothing
    to do" guard. Unlike Places (where only one real entry ever needs
    the ladder), every real curated `Club` in this ticket's dataset
    needs this pass -- no `Club` ever carries a hand-curated coordinate
    -- so this guard mainly protects the `--source places-sd`-filtered
    case where `clubs` is legitimately empty.

    A `Club` that exhausts every rung keeps `location_precision ==
    "none"` and no coordinates -- the same "never guess" honesty rule
    `geo_ladder.py` documents, never fabricated here either.
    """
    if not clubs:
        return clubs

    resolved_data_dir = Path(data_dir) if data_dir is not None else DEFAULT_GEO_DATA_DIR
    ladder = GeoLadder(resolved_data_dir)

    for club in clubs:
        match = ladder.locate(club.host_school, club.city, club.postal_code)
        club.latitude = match.latitude
        club.longitude = match.longitude
        club.location_precision = match.location_precision
        club.matched_name = match.matched_name
        club.needs_review = match.needs_review
        if match.location_precision == "school" and match.website:
            club.host_school_website = match.website

    return clubs


def _check_related_partner_references(places: list[Place], *, site_dir: str | Path | None) -> None:
    """Join-integrity guard for `Place.related_partner_id` (issue 48,
    ticket 004): recovers, as real pipeline-level validation, the guard
    `tests/directory/test_dataset_validity.py`'s deleted
    `TestRelatedPartnerIdJoinIntegrity` class used to provide.

    Unlike `partner_scrape.pipeline.run()`'s ticket-003 wiring (an
    *unconditional* `partners.json` read), this is a *conditional* one:
    `directory.pipeline.run_directory()` never read `partners.json`
    before this ticket, and `Place.related_partner_id` is a hand-copied
    value with "no automatic cross-reference join" by original design
    (sprint 018 ticket 007). Building `references` and returning early
    when it is empty means a `directory`-only environment with no
    sibling `stem-ecosystem` checkout's `partners.json` still runs
    cleanly when no `Place` references one -- this is the one
    behavioral difference from ticket 003's unconditional read.

    When at least one reference exists, `site_dir` is resolved
    identically to `export.export_directory()`'s own resolution (`Path
    (site_dir) if site_dir is not None else get_site_dir()`) -- no
    independent, potentially-divergent resolution logic -- and
    `check_partner_references()` is left to raise
    `RosterValidationError` uncaught: a fatal, structural problem, not
    per-source isolated (contrast with `run_directory()`'s own
    try/except-and-continue for a flaky third-party fetch, which a
    hand-copy typo in a curated, ~19-row dataset is not).

    A missing `partners.json` when references exist is re-raised as a
    `RuntimeError` with an actionable message, matching
    `export_directory()`'s and `publish.project()`'s own "site_dir does
    not exist, check --site-dir" message convention -- never a bare,
    unexplained `FileNotFoundError`.
    """
    references = [
        (place.place_id, place.related_partner_id)
        for place in places
        if place.related_partner_id is not None
    ]
    if not references:
        return

    resolved_site_dir = Path(site_dir) if site_dir is not None else get_site_dir()
    partners_path = resolved_site_dir / "src" / "data" / "partners.json"

    try:
        raw_partners = json.loads(partners_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeError(
            f"Cannot read {partners_path} to validate related_partner_id "
            f"references: {exc}. Check --site-dir or SITE_DIR, and that "
            "the sibling site checkout's src/data/partners.json is present."
        ) from exc

    check_partner_references(references, raw_partners)


def run_directory(
    *,
    registry_dir: str | Path | None = None,
    source: str | None = None,
    site_dir: str | Path | None = None,
    fetcher: Fetcher | None = None,
    dry_run: bool = False,
    geo_data_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Run the Directory pipeline end-to-end: Registry -> `PlaceSource`(s)/
    `ClubSource`(s) -> `_apply_geo_fallback()`/`_apply_club_geocoding()`
    -> `export_directory()`.

    Args:
        registry_dir: Registry directory to load sources from (both
            Place Registry and Club Registry entries live side by
            side). Defaults to :data:`DEFAULT_PLACES_REGISTRY_DIR` (the
            real seed registry, `partner_scrape/directory/registry/`)
            when omitted.
        source: when given, restricts the run to the single acquisition
            source whose `adapter_type` matches (e.g.
            `"static_roster"` or `"hack_club_static_roster"`) -- mirrors
            `teams.pipeline.run_teams()`'s own `source` parameter.
        site_dir: sibling `stem-ecosystem` checkout to write
            `places.json`/`clubs.json` into. Defaults to
            `Config.get_site_dir()` when omitted (via
            `export_directory`).
        fetcher: the `Fetcher` every active source retrieves raw
            content through. Defaults to a real `PoliteFetcher()` when
            omitted -- the production path, even though every source
            this subsystem has as of this ticket (`static_roster`,
            `hack_club_static_roster`) never calls it. Tests inject a
            fixture `Fetcher` here so the whole run touches no sockets.
        dry_run: when `True`, compute and return the would-be-written
            export payload without touching disk.
        geo_data_dir: the offline geocoding data directory
            `_apply_geo_fallback()`/`_apply_club_geocoding()` read.
            Defaults to :data:`DEFAULT_GEO_DATA_DIR` (the real
            committed `directory/data/`) when omitted. Tests that need
            to control fallback/geocoding outcomes precisely should
            pass an explicit fixture directory here.

    Returns:
        `export_directory()`'s `{"meta": ..., "places": [...],
        "clubs_meta": ..., "clubs": [...]}` payload, passed through
        unchanged.

    Raises:
        RosterValidationError: at least one `Place` has a non-`None`
            `related_partner_id` and it does not resolve against
            `{resolved site_dir}/src/data/partners.json` (issue 48,
            ticket 004) -- see `_check_related_partner_references()`'s
            own docstring. Never raised when no `Place` in the run sets
            `related_partner_id` at all; `partners.json` is not even
            read in that case.
        RuntimeError: at least one `Place` has a non-`None`
            `related_partner_id` and `partners.json` cannot be read at
            the resolved `site_dir`.
    """
    sources = load_active_sources(
        Path(registry_dir) if registry_dir is not None else DEFAULT_PLACES_REGISTRY_DIR
    )

    if source is not None:
        sources = [s for s in sources if s.adapter_type == source]

    active_fetcher = fetcher if fetcher is not None else PoliteFetcher()

    places: list[Place] = []
    clubs: list[Club] = []
    for source_config in sources:
        # One combined dispatch per registry entry -- checks
        # _PLACE_SOURCES, then _CLUB_SOURCES -- rather than two
        # separate loops over the same `sources` list. See this
        # module's own docstring for why: a second, Place-shaped loop
        # would make the *first* loop's "no PlaceSource registered"
        # warning fire spuriously for every real Club registry entry.
        place_source = _PLACE_SOURCES.get(source_config.adapter_type)
        club_source = _CLUB_SOURCES.get(source_config.adapter_type)

        if place_source is not None:
            try:
                source_places = run_place_source(source_config, place_source, active_fetcher)
            except Exception:
                # Per-source error isolation, matching
                # teams.pipeline.run_teams()'s own convention: one
                # broken source is logged and skipped, never fatal to
                # the rest of the run.
                logger.exception(
                    "Place source %r (adapter_type=%r) failed; skipping it, "
                    "run continues with the remaining sources",
                    source_config.source_id,
                    source_config.adapter_type,
                )
                continue

            logger.info(
                "Place source %r yielded %d place(s)",
                source_config.source_id,
                len(source_places),
            )
            places.extend(source_places)

        elif club_source is not None:
            try:
                source_clubs = run_club_source(source_config, club_source, active_fetcher)
            except Exception:
                # Same per-source error isolation as the Place branch
                # above.
                logger.exception(
                    "Club source %r (adapter_type=%r) failed; skipping it, "
                    "run continues with the remaining sources",
                    source_config.source_id,
                    source_config.adapter_type,
                )
                continue

            logger.info(
                "Club source %r yielded %d club(s)",
                source_config.source_id,
                len(source_clubs),
            )
            clubs.extend(source_clubs)

        else:
            logger.warning(
                "No PlaceSource or ClubSource registered for adapter_type %r "
                "(source_id=%r); skipping",
                source_config.adapter_type,
                source_config.source_id,
            )
            continue

    places = _apply_geo_fallback(places, data_dir=geo_data_dir)
    clubs = _apply_club_geocoding(clubs, data_dir=geo_data_dir)

    # Join-integrity validation (issue 48, ticket 004) -- after the
    # final Place list is settled, before export_directory() writes
    # anything. See _check_related_partner_references()'s own
    # docstring for the full "conditional read, uncaught raise"
    # rationale.
    _check_related_partner_references(places, site_dir=site_dir)

    return export_directory(places, clubs=clubs, site_dir=site_dir, dry_run=dry_run)
