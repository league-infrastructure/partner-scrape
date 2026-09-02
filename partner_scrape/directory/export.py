"""`export_directory()`: the Directory pipeline's `places.json`/
`clubs.json`/`offerings.json` publish entry point.

Publishes already-acquired `Place` records
(`directory.sources.static_roster`, ticket 018-007) as `places.json` --
an independent data contract alongside `export/writer.py`'s
`opportunities.json` and `teams/export.py`'s `teams.json`. Ticket
018-008 (Clubs) extends the same function with an optional `clubs`
argument that, when given, additionally publishes already-acquired
`Club` records (`directory.sources.hack_club_static_roster`) as a
*second*, independent data contract, `clubs.json`. Sprint 030 ticket
001 (Offerings) extends the same function again with an optional
`offerings` argument that, when given, additionally publishes
already-acquired `Offering` records
(`directory.sources.offering_static_roster`) as a *third*, independent
data contract, `offerings.json`. This module does not re-derive or
re-map any field for any record type -- like `teams/export.py`, its job
is sort, serialize, write; there is no current/upcoming filter (Places,
Clubs, and Offerings are all undated) and no slug-uniqueness pass
(`place_id`/`club_id`/`offering_id` are already unique by construction
-- see `directory/DESIGN.md`'s Notes and `directory/model.py`'s
docstrings).

Sprint 017 first gave both files a sibling `stem-ecosystem` checkout
write target (`{site_dir}/src/data/` and `{site_dir}/public/data/`),
and sprint 020 (ticket 006, issue 60) added a third write target for
each, into partner-scrape's own `own_data_dir`
(`config.get_own_data_dir()`, `<repo_root>/data` by default) -- "one
publish, three paths" per file. Sprint 025 (ticket 005, issue 21 /
stop-writing-to-stem-ecosystem-checkout.md) removes both
`stem-ecosystem`-checkout writes for both files: `export_directory()`
no longer writes into a sibling checkout at all. `own_data_dir` is now
each file's sole write target -- "one publish, one path" -- mirroring
`teams/export.py`'s `export_teams()` (sprint 025 ticket 004) and
`export/writer.py`'s/`export/ads.py`'s own already-single write targets
(sprint 020 tickets 003/004). Unlike Teams, `directory/pipeline.py`'s
`run_directory()` keeps its own `site_dir` parameter --
`_check_related_partner_references()` still reads `{site_dir}/src/data/
partners.json` for the `related_partner_id` join-integrity check, a
real, independent use that has nothing to do with this function's
write; only the forwarding of `site_dir` into this function's call was
removed (see that module's own docstring).

## The `places.json` data contract

```json
{
  "meta": {
    "generated": "2026-08-31T04:13:41Z",
    "total": 19,
    "by_category": {"makerspace": 3, "planetarium": 2, ...},
    "by_location_precision": {"address": 18, "zip": 1}
  },
  "places": [ {"place_id": "sdpl-idea-lab-central", ...}, ... ]
}
```

`meta` travels *inside* `places.json` itself, the same self-describing
shape `teams.json` already established -- see that module's own
docstring for why (a `places` run's freshness must never be confused
with the opportunities or teams export's own).

## The `clubs.json` data contract (ticket 018-008)

```json
{
  "meta": {
    "generated": "2026-08-31T04:13:41Z",
    "total": 4,
    "by_club_type": {"hack-club": 4},
    "by_location_precision": {"school": 4}
  },
  "clubs": [ {"club_id": "hack-club-university-city-high", ...}, ... ]
}
```

Same self-describing-`meta`-travels-inside-the-file shape as
`places.json`, deliberately its own independent document rather than
nested inside `places.json` -- a `clubs` run's freshness/count must
never be confused with the places export's own, the identical
reasoning `places.json`'s own docstring section above gives for not
sharing `teams.json`'s `meta`.

**`export_directory()`'s returned `dict` stays backward compatible
with ticket 007's shape.** `payload["meta"]`/`payload["places"]` are
unchanged (still the places-only view ticket 007's own tests assert
against); the clubs view is added under new, separately-named
`payload["clubs_meta"]`/`payload["clubs"]` keys rather than nesting a
second `"meta"` inside the same flat dict (which would collide with
the places one). `clubs.json` itself is written from a genuinely
separate `{"meta": ..., "clubs": [...]}` document built internally,
not from those flat top-level keys -- the flat keys exist only for a
caller inspecting the returned payload in Python.

**`clubs` defaults to `None`, meaning "do not touch `clubs.json` at
all"** -- not "write an empty one." This preserves every ticket-007
call site/test that calls `export_directory(places)` with no `clubs`
argument unchanged: no `clubs.json` is written, exactly as before this
ticket. Passing `clubs=[]` (a real, empty list -- what
`directory.pipeline.run_directory()` passes when no `Club` source
acquired anything, e.g. under `--source places-sd`) *does* write a
`clubs.json` with `"total": 0` -- a legitimate "the clubs pipeline ran
and found nothing this time" result, distinct from "the clubs pipeline
was never asked to run" (`clubs=None`).

## The `offerings.json` data contract (sprint 030 ticket 001)

```json
{
  "meta": {
    "generated": "2026-09-02T04:13:41Z",
    "total": 13,
    "by_offering_type": {"volunteer": 6, "free_program": 7}
  },
  "offerings": [ {"offering_id": "fleet-science-center-volunteer", ...}, ... ]
}
```

Same self-describing-`meta`-travels-inside-the-file shape as
`places.json`/`clubs.json`, deliberately its own independent document
rather than nested inside either -- an `offerings` run's freshness/
count must never be confused with the places or clubs export's own,
the identical reasoning `places.json`'s own docstring section above
gives for not sharing `teams.json`'s `meta`. Unlike `places.json`'s/
`clubs.json`'s `by_location_precision` breakdown, there is no
`by_location_precision` here -- `Offering` carries no location fields
at all (see `directory/model.py`'s `Offering` docstring).

**`offerings` defaults to `None`, meaning "do not touch
`offerings.json` at all"** -- the identical contract `clubs` already
established, extended to a third file. Every pre-sprint-030 call site/
test that calls `export_directory(places)` (or
`export_directory(places, clubs=...)`) with no `offerings` argument is
unchanged: no `offerings.json` is written. Passing `offerings=[]` (a
real, empty list -- what `directory.pipeline.run_directory()` passes
when no `Offering` source acquired anything) *does* write an
`offerings.json` with `"total": 0`, the same "ran and found nothing"
vs. "never asked to run" distinction `clubs=[]` vs. `clubs=None`
already draws.

## Two hard invariants

This module **never** writes or touches `opportunities.json`,
`scrape-meta.json`, or `teams.json` -- those are `export/writer.py`'s
and `teams/export.py`'s exclusive outputs. Both invariants are covered
by a dedicated regression test (`tests/directory/test_export.py`)
asserting those three files are byte-identical before and after a
`directory` run, matching `tests/teams/test_export.py`'s own
`TestHardInvariants` precedent -- extended by sprint 030 ticket 001 to
also assert `offerings.json` is untouched when `offerings=None`.

A missing or unwritable `own_data_dir` fails loudly, matching
`export_teams`'s and `export_opportunities`'s contract exactly -- "fail
loudly, do not silently skip the export." This is now each file's
*only* write target (sprint 025 ticket 005 removed the two
`stem-ecosystem`-checkout writes this section used to also describe --
see the module docstring's own history of that removal above); the
`places.json` write is attempted, and must fully succeed, before the
`clubs.json` write (when `clubs is not None`) begins, and the
`clubs.json` write (when attempted) completes before the
`offerings.json` write (when `offerings is not None`) begins -- a
later file's failure never leaves an earlier one half written, and an
earlier file's write failure raises before any later file is ever
touched, the same "places before clubs" ordering principle as before,
now extended to "places before clubs before offerings." `own_data_dir`
is created automatically (`Path.mkdir(parents=True, exist_ok=True)`) if
missing, matching `teams/export.py`'s identical "not guaranteed to
exist yet" rationale.
"""

from __future__ import annotations

import json
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from partner_scrape.config import get_own_data_dir
from partner_scrape.directory.model import Club, Offering, Place

#: The exact field set written to `places.json`, minus `sources` --
#: `Place.sources` is this subsystem's own cross-source-acquisition
#: bookkeeping, the same role `Team.sources` plays for `teams.json`
#: (dropped there for the identical reason: no counterpart in the
#: site's schema). Derived from the dataclass fields rather than
#: hand-listed so it can never drift from `Place` itself, matching
#: `teams/export.py`'s `TEAMS_SCHEMA_FIELDS` convention exactly.
PLACES_SCHEMA_FIELDS: tuple[str, ...] = tuple(
    f.name for f in fields(Place) if f.name != "sources"
)

#: The exact field set written to `clubs.json`, minus `sources` -- same
#: rationale and derivation as `PLACES_SCHEMA_FIELDS` above, for `Club`
#: instead of `Place`. Ticket 018-008's own addition.
CLUBS_SCHEMA_FIELDS: tuple[str, ...] = tuple(
    f.name for f in fields(Club) if f.name != "sources"
)

#: The exact field set written to `offerings.json`, minus `sources` --
#: same rationale and derivation as `PLACES_SCHEMA_FIELDS`/
#: `CLUBS_SCHEMA_FIELDS` above, for `Offering` instead of `Place`/
#: `Club`. Sprint 030 ticket 001's own addition.
OFFERINGS_SCHEMA_FIELDS: tuple[str, ...] = tuple(
    f.name for f in fields(Offering) if f.name != "sources"
)


def _now_iso() -> str:
    """Current UTC time, matching `teams/export.py`'s `_now_iso()` (and,
    transitively, `export/writer.py`'s) format exactly -- one timestamp
    convention across every export in this project, even though
    `directory/` is a structurally separate subsystem with no import of
    either implementation."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_json_dict(place: Place) -> dict[str, Any]:
    """Project `place` onto exactly `PLACES_SCHEMA_FIELDS`."""
    return {name: getattr(place, name) for name in PLACES_SCHEMA_FIELDS}


def club_to_json_dict(club: Club) -> dict[str, Any]:
    """Project `club` onto exactly `CLUBS_SCHEMA_FIELDS`. Parallel to
    `to_json_dict()` above, kept a separate function rather than one
    generalized over both record types for the same reason
    `directory/sources/base.py`'s `run()`/`run_club_source()` are kept
    separate: correct, unambiguous typing over deduplicating a
    one-line function body."""
    return {name: getattr(club, name) for name in CLUBS_SCHEMA_FIELDS}


def offering_to_json_dict(offering: Offering) -> dict[str, Any]:
    """Project `offering` onto exactly `OFFERINGS_SCHEMA_FIELDS`.
    Parallel to `to_json_dict()`/`club_to_json_dict()` above, same
    "kept separate for correct, unambiguous typing" rationale. Sprint
    030 ticket 001's own addition."""
    return {name: getattr(offering, name) for name in OFFERINGS_SCHEMA_FIELDS}


def _build_meta(places: list[Place]) -> dict[str, Any]:
    """Coverage/data-quality envelope for `places`. `by_category` and
    `by_location_precision` are built as plain `dict`s (insertion order
    of first appearance) rather than pre-seeded from `model.Category`/
    `LocationPrecision`'s full value sets -- a category with zero
    places this run simply doesn't appear, matching
    `teams/export.py`'s `_build_meta`'s own "a partial result ships,
    the gap is visible in the artifact itself" convention."""
    by_category: dict[str, int] = {}
    by_location_precision: dict[str, int] = {}
    for place in places:
        by_category[place.category] = by_category.get(place.category, 0) + 1
        by_location_precision[place.location_precision] = (
            by_location_precision.get(place.location_precision, 0) + 1
        )

    return {
        "generated": _now_iso(),
        "total": len(places),
        "by_category": by_category,
        "by_location_precision": by_location_precision,
    }


def _build_club_meta(clubs: list[Club]) -> dict[str, Any]:
    """Coverage/data-quality envelope for `clubs`. Parallel to
    `_build_meta()` above, `by_club_type` in place of `by_category` --
    same "partial result ships, the gap is visible in the artifact
    itself" convention, same plain-`dict`-of-first-appearance
    construction."""
    by_club_type: dict[str, int] = {}
    by_location_precision: dict[str, int] = {}
    for club in clubs:
        by_club_type[club.club_type] = by_club_type.get(club.club_type, 0) + 1
        by_location_precision[club.location_precision] = (
            by_location_precision.get(club.location_precision, 0) + 1
        )

    return {
        "generated": _now_iso(),
        "total": len(clubs),
        "by_club_type": by_club_type,
        "by_location_precision": by_location_precision,
    }


def _build_offering_meta(offerings: list[Offering]) -> dict[str, Any]:
    """Coverage/data-quality envelope for `offerings`. Parallel to
    `_build_meta()`/`_build_club_meta()` above, `by_offering_type` in
    place of `by_category`/`by_club_type` -- same "partial result
    ships, the gap is visible in the artifact itself" convention, same
    plain-`dict`-of-first-appearance construction. No
    `by_location_precision` breakdown -- `Offering` carries no location
    fields at all (see `directory/model.py`'s `Offering` docstring).
    Sprint 030 ticket 001's own addition."""
    by_offering_type: dict[str, int] = {}
    for offering in offerings:
        by_offering_type[offering.offering_type] = by_offering_type.get(offering.offering_type, 0) + 1

    return {
        "generated": _now_iso(),
        "total": len(offerings),
        "by_offering_type": by_offering_type,
    }


def export_directory(
    places: Iterable[Place],
    *,
    clubs: Iterable[Club] | None = None,
    offerings: Iterable[Offering] | None = None,
    dry_run: bool = False,
    own_data_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Serialize and write `places` into `places.json`, once, into
    partner-scrape's own `own_data_dir` (sprint 020 ticket 006; sole
    write target since sprint 025 ticket 005 removed the two
    `stem-ecosystem`-checkout writes this function used to also make).
    When `clubs` is given (ticket 018-008), also serializes and writes
    `clubs.json` the same way, from its own independent
    `{"meta": ..., "clubs": [...]}` document. When `offerings` is given
    (sprint 030 ticket 001), also serializes and writes `offerings.json`
    the same way again, from its own independent
    `{"meta": ..., "offerings": [...]}` document -- see this module's
    own docstring for the full `offerings.json` data contract and why
    `offerings`, like `clubs`, defaults to `None` rather than an empty
    list.

    Args:
        places: acquired `Place` records
            (`directory.pipeline.run_directory()`'s typical
            caller-supplied input) -- no current/upcoming filter is
            applied (places are undated) and no slug-uniqueness pass is
            needed (`place_id` is already unique by construction, see
            `directory/model.py`).
        clubs: acquired `Club` records
            (`directory.pipeline.run_directory()`'s typical
            caller-supplied input). `None` (the default) means "do not
            touch `clubs.json` at all" -- ticket 007's own call sites
            and tests omit this argument and see no behavior change.
            An explicit (possibly empty) list writes `clubs.json`. Same
            "no filter, no slug-uniqueness pass needed" properties as
            `places` above.
        offerings: acquired `Offering` records
            (`directory.pipeline.run_directory()`'s typical
            caller-supplied input). `None` (the default) means "do not
            touch `offerings.json` at all" -- every pre-sprint-030 call
            site/test omits this argument and sees no behavior change.
            An explicit (possibly empty) list writes `offerings.json`.
            Same "no filter, no slug-uniqueness pass needed" properties
            as `places`/`clubs` above (`offering_id` is already unique
            by construction).
        dry_run: when `True`, compute and return the would-be-written
            payload without touching disk (`own_data_dir` is not
            written, for any of the three files).
        own_data_dir: path to partner-scrape's own pipeline-output
            directory. Defaults to `Config.get_own_data_dir()`
            (`<repo_root>/data`) when `None`. This directory is created
            automatically if missing. Tests should always pass an
            explicit `tmp_path` here, never rely on the default.

    Returns:
        A dict with `payload["meta"]`/`payload["places"]` set to the
        places.json content that was (or, for `dry_run`, would have
        been) written -- unchanged from ticket 007's own contract. When
        `clubs is not None`, also carries `payload["clubs_meta"]`/
        `payload["clubs"]` for the clubs.json content. When `offerings
        is not None`, also carries `payload["offerings_meta"]`/
        `payload["offerings"]` for the offerings.json content.

    Raises:
        RuntimeError: `own_data_dir` is not writable, for `places.json`,
            (when `clubs is not None`) `clubs.json`, or (when
            `offerings is not None`) `offerings.json`. Never silently
            skips a write. `places.json`'s write completes before any
            `clubs.json` write is attempted, and `clubs.json`'s write
            (when attempted) completes before any `offerings.json`
            write is attempted -- matches `export_teams`'s own
            `own_data_dir`-write contract, extended here to
            "places.json before clubs.json before offerings.json".
    """
    resolved_own_data_dir = Path(own_data_dir) if own_data_dir is not None else get_own_data_dir()

    place_list = sorted(list(places), key=lambda p: (p.category, p.name))

    payload: dict[str, Any] = {
        "meta": _build_meta(place_list),
        "places": [to_json_dict(p) for p in place_list],
    }

    club_payload: dict[str, Any] | None = None
    if clubs is not None:
        club_list = sorted(list(clubs), key=lambda c: (c.club_type, c.name))
        club_payload = {
            "meta": _build_club_meta(club_list),
            "clubs": [club_to_json_dict(c) for c in club_list],
        }
        payload["clubs_meta"] = club_payload["meta"]
        payload["clubs"] = club_payload["clubs"]

    offering_payload: dict[str, Any] | None = None
    if offerings is not None:
        # Sorted by (offering_type, org_name, title): the closest
        # analog to places.json's/clubs.json's own (type, name)
        # convention available on this model -- Offering has no single
        # "name" field (it splits org_name/title, see directory/
        # model.py's Offering docstring), so org_name (the operating
        # org, the more Place.name/Club.name-like half) is the primary
        # sort key with title as a stable tiebreaker for the (rare)
        # case of two offerings from the same org.
        offering_list = sorted(
            list(offerings), key=lambda o: (o.offering_type, o.org_name, o.title)
        )
        offering_payload = {
            "meta": _build_offering_meta(offering_list),
            "offerings": [offering_to_json_dict(o) for o in offering_list],
        }
        payload["offerings_meta"] = offering_payload["meta"]
        payload["offerings"] = offering_payload["offerings"]

    if dry_run:
        return payload

    # Serialized from a places-only view, not `payload` itself --
    # `payload` may also carry `clubs_meta`/`clubs`/`offerings_meta`/
    # `offerings` (added above when given), which must never leak into
    # `places.json`.
    places_payload = {"meta": payload["meta"], "places": payload["places"]}
    serialized = json.dumps(places_payload, indent=1, ensure_ascii=False)

    # Sprint 020 ticket 006 (issue 60), sole write target since sprint
    # 025 ticket 005 removed this function's two `stem-ecosystem`-
    # checkout writes: the payload, written into partner-scrape's own
    # data/ directory. own_data_dir is created if missing. Only once
    # this write succeeds is clubs.json touched at all (see the `if
    # club_payload is not None` block below).
    own_places_path = resolved_own_data_dir / "places.json"

    try:
        resolved_own_data_dir.mkdir(parents=True, exist_ok=True)
        own_places_path.write_text(serialized, encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(
            f"Cannot write places export to {resolved_own_data_dir}: {exc}. "
            "Check that own_data_dir is writable."
        ) from exc

    if club_payload is not None:
        serialized_clubs = json.dumps(club_payload, indent=1, ensure_ascii=False)

        # Same sole write target as places.json above, reached only
        # once places.json's own write has succeeded -- mirrors
        # places.json's own ordering guarantee above.
        own_clubs_path = resolved_own_data_dir / "clubs.json"
        try:
            resolved_own_data_dir.mkdir(parents=True, exist_ok=True)
            own_clubs_path.write_text(serialized_clubs, encoding="utf-8")
        except OSError as exc:
            raise RuntimeError(
                f"Cannot write clubs export to {resolved_own_data_dir}: {exc}. "
                "Check that own_data_dir is writable."
            ) from exc

    if offering_payload is not None:
        serialized_offerings = json.dumps(offering_payload, indent=1, ensure_ascii=False)

        # Same sole write target as places.json/clubs.json above,
        # reached only once places.json's own write has succeeded --
        # "places.json before clubs.json before offerings.json"
        # ordering. Deliberately not additionally gated on
        # `club_payload is not None` -- offerings.json's own write must
        # succeed or fail independently of whether clubs was even
        # given, matching clubs=None/offerings=[...] being a legitimate
        # combination (run_directory() always passes a real, if
        # possibly empty, `clubs` list, but a caller driving
        # export_directory() directly is free to pass offerings without
        # clubs).
        own_offerings_path = resolved_own_data_dir / "offerings.json"
        try:
            resolved_own_data_dir.mkdir(parents=True, exist_ok=True)
            own_offerings_path.write_text(serialized_offerings, encoding="utf-8")
        except OSError as exc:
            raise RuntimeError(
                f"Cannot write offerings export to {resolved_own_data_dir}: {exc}. "
                "Check that own_data_dir is writable."
            ) from exc

    return payload
