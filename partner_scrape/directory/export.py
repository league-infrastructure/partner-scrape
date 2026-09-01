"""`export_directory()`: the Directory pipeline's `places.json`/
`clubs.json` publish entry point.

Publishes already-acquired `Place` records
(`directory.sources.static_roster`, ticket 018-007) into the sibling
`stem-ecosystem` repo's data contract as `{site_dir}/src/data/
places.json`, plus (sprint 017's "one publish, two paths" convention,
already established for `teams.json`) `{site_dir}/public/data/
places.json` -- a *third*, independent data contract alongside
`export/writer.py`'s `opportunities.json` and `teams/export.py`'s
`teams.json`. Ticket 018-008 (Clubs) extends the same function with an
optional `clubs` argument that, when given, additionally publishes
already-acquired `Club` records (`directory.sources.
hack_club_static_roster`) as a *fourth*, independent data contract,
`clubs.json`, at the same two paths. This module does not re-derive or
re-map any field for either record type -- like `teams/export.py`, its
job is sort, serialize, write; there is no current/upcoming filter
(both Places and Clubs are undated) and no slug-uniqueness pass
(`place_id`/`club_id` are already unique by construction -- see
`directory/DESIGN.md`'s Notes and `directory/model.py`'s docstrings).

Sprint 020 (ticket 006, issue 60): both `places.json` and (when
`clubs is not None`) `clubs.json` gain a *third* write target, into
partner-scrape's own `own_data_dir` (`config.get_own_data_dir()`,
`<repo_root>/data` by default) -- "one publish, three paths" now,
mirroring `teams/export.py`'s `export_teams()` (ticket 005) and
`export/writer.py`'s/`export/ads.py`'s own third write paths (tickets
003/004). Each own-repo write reuses the already-serialized
`places.json`/`clubs.json` string built for the `SITE_DIR` copies, so
no target can ever drift from another.

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
call site/test that calls `export_directory(places, site_dir=...)`
with no `clubs` argument unchanged: no `clubs.json` is written, exactly
as before this ticket. Passing `clubs=[]` (a real, empty list -- what
`directory.pipeline.run_directory()` passes when no `Club` source
acquired anything, e.g. under `--source places-sd`) *does* write a
`clubs.json` with `"total": 0` -- a legitimate "the clubs pipeline ran
and found nothing this time" result, distinct from "the clubs pipeline
was never asked to run" (`clubs=None`).

## Two hard invariants

This module **never** writes or touches `opportunities.json`,
`scrape-meta.json`, or `teams.json` -- those are `export/writer.py`'s
and `teams/export.py`'s exclusive outputs. Both invariants are covered
by a dedicated regression test (`tests/directory/test_export.py`)
asserting those three files are byte-identical before and after a
`directory` run, matching `tests/teams/test_export.py`'s own
`TestHardInvariants` precedent.

A missing or unwritable `site_dir` (or its `src/data` subdirectory), or
an unwritable `own_data_dir`, fails loudly, matching `export_teams`'s
and `export_opportunities`'s contract exactly -- "fail loudly, do not
silently skip the export." The `places.json` write (all three paths --
`src/data`, then `public/data`, then `own_data_dir`, in that order) is
attempted, and must fully succeed, before the `clubs.json` write (when
`clubs is not None`) begins -- a `clubs.json` failure never leaves
`places.json` half written, and a `places.json` failure at *any* of its
three targets raises before `clubs.json` is ever touched. Within
`clubs.json`'s own write, the same "src/data, then public/data, then
own_data_dir" ordering applies -- its own-repo write is only reached
once its `src/data` and `public/data` writes have both succeeded.
`public/data` and `own_data_dir` are each created automatically
(`Path.mkdir(parents=True, exist_ok=True)`) if missing, matching
`teams/export.py`'s identical "not guaranteed to exist yet" rationale
for both targets; `src/data` is not -- a missing `src/data` is always a
loud failure, never auto-created.
"""

from __future__ import annotations

import json
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from partner_scrape.config import get_own_data_dir, get_site_dir
from partner_scrape.directory.model import Club, Place

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


def export_directory(
    places: Iterable[Place],
    site_dir: str | Path | None = None,
    *,
    clubs: Iterable[Club] | None = None,
    dry_run: bool = False,
    own_data_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Serialize and write `places` into `places.json` -- three times:
    once to the build-time `src/data/places.json` Astro input, once to
    the publicly-served `public/data/places.json` (sprint 017's
    convention, already established for `teams.json`), and once into
    partner-scrape's own `own_data_dir` (sprint 020 ticket 006), all
    from the single payload built below -- see `teams/export.py`'s own
    docstring for the full "one publish, three paths" rationale, reused
    unmodified here. When `clubs` is given (ticket 018-008), also
    serializes and writes `clubs.json` at the same three paths, from
    its own independent `{"meta": ..., "clubs": [...]}` document -- see
    this module's own docstring for the full `clubs.json` data contract
    and why `clubs` defaults to `None` rather than an empty list.

    Args:
        places: acquired `Place` records
            (`directory.pipeline.run_directory()`'s typical
            caller-supplied input) -- no current/upcoming filter is
            applied (places are undated) and no slug-uniqueness pass is
            needed (`place_id` is already unique by construction, see
            `directory/model.py`).
        site_dir: path to the sibling `stem-ecosystem` checkout.
            Defaults to `Config.get_site_dir()` when `None`. Tests
            should always pass an explicit `tmp_path` here, never rely
            on the default.
        clubs: acquired `Club` records
            (`directory.pipeline.run_directory()`'s typical
            caller-supplied input). `None` (the default) means "do not
            touch `clubs.json` at all" -- ticket 007's own call sites
            and tests omit this argument and see no behavior change.
            An explicit (possibly empty) list writes `clubs.json`. Same
            "no filter, no slug-uniqueness pass needed" properties as
            `places` above.
        dry_run: when `True`, compute and return the would-be-written
            payload without touching disk (none of the three locations
            is written, for either file).
        own_data_dir: path to partner-scrape's own pipeline-output
            directory. Defaults to `Config.get_own_data_dir()`
            (`<repo_root>/data`) when `None`. Like `public/data`, this
            directory is created automatically if missing. Tests should
            always pass an explicit `tmp_path` here, never rely on the
            default, matching `site_dir`'s own test convention.

    Returns:
        A dict with `payload["meta"]`/`payload["places"]` set to the
        places.json content that was (or, for `dry_run`, would have
        been) written -- unchanged from ticket 007's own contract. When
        `clubs is not None`, also carries `payload["clubs_meta"]`/
        `payload["clubs"]` for the clubs.json content. Both files, when
        written, are identical at their `src/data`, `public/data`, and
        `own_data_dir` copies.

    Raises:
        RuntimeError: `site_dir`'s `src/data` subdirectory does not
            exist or is not writable, `site_dir`'s `public/data` target
            is not writable, or `own_data_dir` is not writable, for
            either `places.json` or (when `clubs is not None`)
            `clubs.json`. Never silently skips a write. All three of
            `places.json`'s writes (`src/data`, then `public/data`,
            then `own_data_dir`, in that order) complete before any
            `clubs.json` write is attempted -- matches `export_teams`'s
            exact "src/data before public/data before own_data_dir"
            ordering contract, extended here to "places.json (all three
            targets) before clubs.json". `clubs.json`'s own three
            writes follow the identical `src/data` -> `public/data` ->
            `own_data_dir` order.
    """
    resolved_site_dir = Path(site_dir) if site_dir is not None else get_site_dir()
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

    if dry_run:
        return payload

    # Serialized from a places-only view, not `payload` itself --
    # `payload` may also carry `clubs_meta`/`clubs` (added above when
    # `clubs is not None`), which must never leak into `places.json`.
    places_payload = {"meta": payload["meta"], "places": payload["places"]}
    serialized = json.dumps(places_payload, indent=1, ensure_ascii=False)

    data_dir = resolved_site_dir / "src" / "data"
    places_path = data_dir / "places.json"

    try:
        places_path.write_text(serialized, encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(
            f"Cannot write places export to {data_dir}: {exc}. Check that "
            f"site_dir ({resolved_site_dir}) exists and its src/data "
            "subdirectory is writable."
        ) from exc

    public_data_dir = resolved_site_dir / "public" / "data"
    public_places_path = public_data_dir / "places.json"

    try:
        public_data_dir.mkdir(parents=True, exist_ok=True)
        public_places_path.write_text(serialized, encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(
            f"Cannot write places export to {public_data_dir}: {exc}. Check "
            f"that site_dir ({resolved_site_dir})'s public/data path is "
            "writable."
        ) from exc

    # Sprint 020 ticket 006 (issue 60): the same payload, written a
    # third time into partner-scrape's own data/ directory -- reusing
    # `serialized` computed above rather than re-serializing, so the
    # three copies can never drift. Always last: only reached once both
    # SITE_DIR writes above have succeeded. Only once this write also
    # succeeds is clubs.json touched at all (see the `if club_payload
    # is not None` block below).
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

        clubs_path = data_dir / "clubs.json"
        try:
            clubs_path.write_text(serialized_clubs, encoding="utf-8")
        except OSError as exc:
            raise RuntimeError(
                f"Cannot write clubs export to {data_dir}: {exc}. Check that "
                f"site_dir ({resolved_site_dir}) exists and its src/data "
                "subdirectory is writable."
            ) from exc

        public_clubs_path = public_data_dir / "clubs.json"
        try:
            public_data_dir.mkdir(parents=True, exist_ok=True)
            public_clubs_path.write_text(serialized_clubs, encoding="utf-8")
        except OSError as exc:
            raise RuntimeError(
                f"Cannot write clubs export to {public_data_dir}: {exc}. Check "
                f"that site_dir ({resolved_site_dir})'s public/data path is "
                "writable."
            ) from exc

        # Sprint 020 ticket 006: clubs.json's own third write, into the
        # same own_data_dir -- reached only once clubs.json's own
        # src/data and public/data writes above have both succeeded,
        # mirroring places.json's own three-target ordering above.
        own_clubs_path = resolved_own_data_dir / "clubs.json"
        try:
            resolved_own_data_dir.mkdir(parents=True, exist_ok=True)
            own_clubs_path.write_text(serialized_clubs, encoding="utf-8")
        except OSError as exc:
            raise RuntimeError(
                f"Cannot write clubs export to {resolved_own_data_dir}: {exc}. "
                "Check that own_data_dir is writable."
            ) from exc

    return payload
