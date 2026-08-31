"""`export_directory()`: the Directory pipeline's `places.json` publish
entry point.

Publishes already-acquired `Place` records
(`directory.sources.static_roster` this ticket) into the sibling
`stem-ecosystem` repo's data contract as `{site_dir}/src/data/
places.json`, plus (sprint 017's "one publish, two paths" convention,
already established for `teams.json`) `{site_dir}/public/data/
places.json` -- a *third*, independent data contract alongside
`export/writer.py`'s `opportunities.json` and `teams/export.py`'s
`teams.json`. This module does not re-derive or re-map any field --
like `teams/export.py`, its job is sort, serialize, write; there is no
current/upcoming filter (places are undated) and no slug-uniqueness
pass (`place_id` is already unique by construction -- see
`directory/DESIGN.md`'s Notes and `directory/model.py`'s docstring).

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

## `clubs.json` does not exist yet

Ticket 018-007 (this ticket) builds `directory/export.py`'s shared
scaffolding for ticket 018-008 (Clubs) to reuse, but there is no `Club`
model yet -- `export_directory()` below has no `clubs` parameter at
all, and this module never writes `clubs.json`. This is a deliberate
"absent," not an "empty placeholder": writing an empty `clubs.json`
now would commit to a payload shape (`meta` keys, sort order) before
`Club` exists to inform it, and a consumer checking for the file's
mere presence would see a false "clubs directory is live" signal.
Ticket 018-008 is expected to add its own `export_clubs()` (or extend
this function -- its own implementation judgment), following this
module's shape, when the `Club` model lands.

## Two hard invariants

This module **never** writes or touches `opportunities.json`,
`scrape-meta.json`, or `teams.json` -- those are `export/writer.py`'s
and `teams/export.py`'s exclusive outputs. Both invariants are covered
by a dedicated regression test (`tests/directory/test_export.py`)
asserting those three files are byte-identical before and after a
`directory` run, matching `tests/teams/test_export.py`'s own
`TestHardInvariants` precedent.

A missing or unwritable `site_dir` (or its `src/data` subdirectory)
fails loudly, matching `export_teams`'s and `export_opportunities`'s
contract exactly -- "fail loudly, do not silently skip the export."
"""

from __future__ import annotations

import json
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from partner_scrape.config import get_site_dir
from partner_scrape.directory.model import Place

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


def export_directory(
    places: Iterable[Place],
    site_dir: str | Path | None = None,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Serialize and write `places` into `site_dir`'s `places.json` --
    twice: once to the build-time `src/data/places.json` Astro input,
    once to the publicly-served `public/data/places.json`, both from
    the single payload built below (sprint 017's convention, already
    established for `teams.json` -- see that module's own docstring for
    the full "one publish, two paths" rationale, reused unmodified
    here).

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
        dry_run: when `True`, compute and return the would-be-written
            payload without touching disk (neither location is
            written).

    Returns:
        The `{"meta": ..., "places": [...]}` payload that was (or, for
        `dry_run`, would have been) written -- identical content at
        both write targets.

    Raises:
        RuntimeError: `site_dir`'s `src/data` subdirectory does not
            exist or is not writable, or `site_dir`'s `public/data`
            target is not writable. Never silently skips either write.
            The `src/data` write is attempted first and its
            `RuntimeError` propagates immediately, before `public/data`
            is touched -- matches `export_teams`'s exact ordering
            contract.
    """
    resolved_site_dir = Path(site_dir) if site_dir is not None else get_site_dir()

    place_list = sorted(list(places), key=lambda p: (p.category, p.name))

    payload: dict[str, Any] = {
        "meta": _build_meta(place_list),
        "places": [to_json_dict(p) for p in place_list],
    }

    if dry_run:
        return payload

    serialized = json.dumps(payload, indent=1, ensure_ascii=False)

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

    return payload
