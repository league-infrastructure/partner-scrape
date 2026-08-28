"""`export_teams()`: the Teams pipeline's single publish entry point.

Publishes already-acquired `Team` records (`teams.sources.*` this
ticket; `teams.merge`/`teams.geo` in tickets 011-003/011-004) into the
sibling `stem-ecosystem` repo's data contract as
`{site_dir}/src/data/teams.json` -- a *second*, independent contract
from `export/writer.py`'s `opportunities.json`/`scrape-meta.json`, per
sprint 011's Design Rationale ("`Team` is a new, separate model, not a
widened `Opportunity`"). This module does not re-derive or re-map any
field -- like `export/writer.py`, its job is filter (nothing to filter
here -- teams are undated, so there is no current/upcoming gate),
serialize, write.

## The `teams.json` data contract

```json
{
  "meta": {
    "generated": "2026-08-28T04:13:41Z",
    "total": 152,
    "by_league": {"FTC": 152},
    "out_of_region": 6,
    "by_location_precision": {"none": 152}
  },
  "teams": [ {"team_id": "ftc-1622", "league": "FTC", ...}, ... ]
}
```

`meta` is deliberately not a bare sibling of `scrape-meta.json` -- it
travels *inside* `teams.json` itself (one file, self-describing),
carrying its own `generated` timestamp so a `teams` run's freshness is
never confused with the opportunities export's (see the two hard
invariants below). `by_league` and `by_location_precision` exist so
coverage and data-quality gaps (an unresolved location, a league with
no active source this run) are visible in the artifact itself, not
just in a log line -- the same "a partial result ships, the gap is
reported" principle `docs/design/design.md` Sec.5 states for the rest
of this project.

## Two hard invariants

This module **never** writes or touches `opportunities.json` or
`scrape-meta.json` -- those are `export/writer.py`'s exclusive outputs.
`scrape-meta.json` in particular carries the *opportunities* export's
last-refreshed timestamp; a `teams` run overwriting it would make the
site falsely claim opportunities were just refreshed when only teams
were. `teams.json` carries its own freshness signal in `meta.generated`
instead. Both invariants are covered by a dedicated regression test
(`tests/teams/test_export.py`) asserting the two files are
byte-identical before and after a `teams` run.

A missing or unwritable `site_dir` (or its `src/data` subdirectory)
fails loudly, matching `export_opportunities`'s contract exactly --
"fail loudly, do not silently skip the export."
"""

from __future__ import annotations

import json
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from partner_scrape.config import get_site_dir
from partner_scrape.teams.model import Team

#: The exact field set written to `teams.json`, minus `sources` --
#: `Team.sources` is this subsystem's own cross-source-acquisition
#: bookkeeping (which acquisition source(s) contributed a record,
#: e.g. `["ftcscout"]`), the same role `Opportunity.sources` plays for
#: `export/writer.py`'s `SITE_SCHEMA_FIELDS` -- and is dropped from the
#: published contract for the identical reason: it has no counterpart
#: in the site's schema. Derived from the dataclass fields rather than
#: hand-listed so it can never drift from `Team` itself as later
#: tickets (merge, geocoding) add fields.
TEAMS_SCHEMA_FIELDS: tuple[str, ...] = tuple(f.name for f in fields(Team) if f.name != "sources")


def to_json_dict(team: Team) -> dict[str, Any]:
    """Project `team` onto exactly `TEAMS_SCHEMA_FIELDS`."""
    return {name: getattr(team, name) for name in TEAMS_SCHEMA_FIELDS}


def _now_iso() -> str:
    """Current UTC time, matching `export/writer.py`'s `_now_iso()`
    format exactly -- one timestamp convention across every export in
    this project, even though `teams/` is a structurally separate
    subsystem with no import of `export/writer.py`'s implementation."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_meta(teams: list[Team]) -> dict[str, Any]:
    """Coverage/data-quality envelope for `teams`. `by_league` and
    `by_location_precision` are built as plain `dict`s (insertion order
    of first appearance) rather than pre-seeded from `model.League`/
    `LocationPrecision`'s full value sets -- a league or precision with
    zero teams this run simply doesn't appear, which is itself a
    meaningful, visible signal (e.g. a `TBA_KEY`-missing run's `meta`
    has no `"FRC"` key in `by_league` at all, once ticket 011-003 adds
    TBA)."""
    by_league: dict[str, int] = {}
    by_location_precision: dict[str, int] = {}
    out_of_region = 0
    for team in teams:
        by_league[team.league] = by_league.get(team.league, 0) + 1
        by_location_precision[team.location_precision] = (
            by_location_precision.get(team.location_precision, 0) + 1
        )
        if not team.in_region:
            out_of_region += 1

    return {
        "generated": _now_iso(),
        "total": len(teams),
        "by_league": by_league,
        "out_of_region": out_of_region,
        "by_location_precision": by_location_precision,
    }


def export_teams(
    teams: Iterable[Team],
    site_dir: str | Path | None = None,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Serialize and write `teams` into `site_dir`'s `teams.json`.

    Args:
        teams: acquired `Team` records (`teams.pipeline.run_teams()`'s
            typical caller-supplied input) -- no current/upcoming
            filter is applied (teams are undated) and no
            slug-uniqueness pass is needed (`team_id` is already unique
            by construction, see `teams/model.py`).
        site_dir: path to the sibling `stem-ecosystem` checkout.
            Defaults to `Config.get_site_dir()` when `None`. Tests
            should always pass an explicit `tmp_path` here, never rely
            on the default.
        dry_run: when `True`, compute and return the would-be-written
            payload without touching disk.

    Returns:
        The `{"meta": ..., "teams": [...]}` payload that was (or, for
        `dry_run`, would have been) written.

    Raises:
        RuntimeError: `site_dir`'s `src/data` subdirectory does not
            exist or is not writable. Never silently skips the write.
    """
    resolved_site_dir = Path(site_dir) if site_dir is not None else get_site_dir()

    team_list = list(teams)
    team_list.sort(key=lambda t: (t.league, t.number))

    payload: dict[str, Any] = {
        "meta": _build_meta(team_list),
        "teams": [to_json_dict(t) for t in team_list],
    }

    if dry_run:
        return payload

    data_dir = resolved_site_dir / "src" / "data"
    teams_path = data_dir / "teams.json"

    try:
        teams_path.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(
            f"Cannot write teams export to {data_dir}: {exc}. Check that "
            f"site_dir ({resolved_site_dir}) exists and its src/data "
            "subdirectory is writable."
        ) from exc

    return payload
