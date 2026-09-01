"""`export_teams()`: the Teams pipeline's single publish entry point.

Publishes already-acquired `Team` records (`teams.sources.*` this
ticket; `teams.merge`/`teams.geo` in tickets 011-003/011-004) as
`teams.json`, filtered (nothing to filter here -- teams are undated, so
there is no current/upcoming gate), serialized, and written -- like
`export/writer.py`'s `opportunities.json`/`scrape-meta.json`, but a
*second*, independent contract, per sprint 011's Design Rationale
("`Team` is a new, separate model, not a widened `Opportunity`").

Sprint 017 (ticket 001) and sprint 020 (ticket 005, issue 60) each added
a further write target for this same payload -- first the sibling
`stem-ecosystem` checkout's `public/data/teams.json`, then
partner-scrape's own `own_data_dir` -- reaching "one publish, three
paths." Sprint 025 (ticket 004, issue 21 / stop-writing-to-
stem-ecosystem-checkout.md) removes both `stem-ecosystem`-checkout
writes (`src/data/teams.json` and `public/data/teams.json`):
partner-scrape no longer writes into a sibling checkout at all, for any
export. `own_data_dir` (`config.get_own_data_dir()`, `<repo_root>/data`
by default) is now this function's sole write target -- "one publish,
one path." Mirrors `export/writer.py`'s `export_opportunities()` and
`export/ads.py`'s `export_ads()`, sprint 020 tickets 003/004, which
still write only their own third target the same way.

## The `teams.json` data contract

```json
{
  "meta": {
    "generated": "2026-08-28T04:13:41Z",
    "total": 152,
    "by_league": {"FTC": 152},
    "out_of_region": 6,
    "by_location_precision": {"none": 152},
    "credential_failures": []
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
of this project. `credential_failures` (sprint 023 ticket 002) is the
active counterpart to `by_league`'s passive omission signal above: an
always-present, sorted, de-duplicated list of league codes (e.g.
`["FRC", "VEX"]`) whose acquisition source failed on a credential
error this run -- `[]` on a clean run, never an absent key -- so a
downstream consumer (e.g. the stem-ecosystem peer's cross-check, issue
62) does not have to already know to check `by_league` for a missing
key in a dict with no declared complete key set to notice a structural
credential outage.

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

A missing or unwritable `own_data_dir` fails loudly, matching
`export_opportunities`'s contract exactly -- "fail loudly, do not
silently skip the export."

## One publish, one path

`own_data_dir` (sprint 020 ticket 005) is created if missing
(`Path.mkdir(parents=True, exist_ok=True)`) before the write -- a fresh
partner-scrape clone is not guaranteed to have a `data/` directory yet.
This is now this function's only write target (sprint 025 ticket 004
removed the two `stem-ecosystem`-checkout writes this section used to
describe -- see the module docstring's own history of that removal).
"""

from __future__ import annotations

import json
import re
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from partner_scrape.config import get_own_data_dir
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

#: Matches the leading run of ASCII digits in a team number string, e.g.
#: the ``"90210"`` in ``"90210A"`` or the whole of ``"1622"``.
_LEADING_DIGITS_RE = re.compile(r"^(\d+)")


def _natural_number_key(number: Any) -> tuple[int, str]:
    """Sprint 016 ticket 005: a natural-sort key for `Team.number`, now
    `str` (VEX designations are alphanumeric, e.g. `"90210A"`).

    Returns `(leading_digit_run_as_int, full_string)` -- sorting by this
    tuple orders purely-numeric values numerically, exactly as the old
    bare-int comparison did (`"99"` sorts before `"100"`, not the
    lexicographic `"100"` before `"99"` a naive string sort would
    produce), while alphanumeric siblings sharing the same leading digit
    run (`"90210A"`/`"90210B"`) sort adjacently, ordered by the full
    string as a tiebreaker.

    Accepts `Any`, not just `str`: `Team.number` is a plain, untyped
    field (matching `Team.league`'s existing convention -- see
    `model.py`'s docstring), and `str(number)` coerces safely whether a
    caller's `Team` happens to carry a real `int` (unmigrated legacy
    data) or the now-standard `str`. A value with no leading digit at
    all (e.g. an empty string) sorts first (`0`), tie-broken by the
    string itself.
    """
    text = str(number)
    match = _LEADING_DIGITS_RE.match(text)
    leading = int(match.group(1)) if match else 0
    return (leading, text)


def to_json_dict(team: Team) -> dict[str, Any]:
    """Project `team` onto exactly `TEAMS_SCHEMA_FIELDS`."""
    return {name: getattr(team, name) for name in TEAMS_SCHEMA_FIELDS}


def _now_iso() -> str:
    """Current UTC time, matching `export/writer.py`'s `_now_iso()`
    format exactly -- one timestamp convention across every export in
    this project, even though `teams/` is a structurally separate
    subsystem with no import of `export/writer.py`'s implementation."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_meta(
    teams: list[Team], credential_failures: list[str] | None = None
) -> dict[str, Any]:
    """Coverage/data-quality envelope for `teams`. `by_league` and
    `by_location_precision` are built as plain `dict`s (insertion order
    of first appearance) rather than pre-seeded from `model.League`/
    `LocationPrecision`'s full value sets -- a league or precision with
    zero teams this run simply doesn't appear, which is itself a
    meaningful, visible signal (e.g. a `TBA_KEY`-missing run's `meta`
    has no `"FRC"` key in `by_league` at all, once ticket 011-003 adds
    TBA).

    Sprint 023 ticket 002: `credential_failures` is the *active*
    counterpart to that passive `by_league`-omission signal -- issue
    62's own text calls a missing dict key "a much weaker guarantee
    than an active alert." Always present in the returned dict (never
    an absent key a consumer has to know to check for), as the sorted,
    de-duplicated list of league codes passed in, or `[]` when `None`/
    empty (a clean run). Sorting/deduping happens here, not at the
    caller, so every caller -- `export_teams()`'s production path and
    any direct test of this function -- gets the same normalized shape
    regardless of what order or how many times a league appears in
    whatever was passed in.
    """
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
        "credential_failures": sorted(set(credential_failures)) if credential_failures else [],
    }


def export_teams(
    teams: Iterable[Team],
    *,
    dry_run: bool = False,
    own_data_dir: str | Path | None = None,
    credential_failures: Iterable[str] = (),
) -> dict[str, Any]:
    """Serialize and write `teams` into `teams.json`, once, into
    partner-scrape's own `own_data_dir` (sprint 020 ticket 005; sole
    write target since sprint 025 ticket 004 removed the two
    `stem-ecosystem`-checkout writes this function used to also make).

    Args:
        teams: acquired `Team` records (`teams.pipeline.run_teams()`'s
            typical caller-supplied input) -- no current/upcoming
            filter is applied (teams are undated) and no
            slug-uniqueness pass is needed (`team_id` is already unique
            by construction, see `teams/model.py`).
        dry_run: when `True`, compute and return the would-be-written
            payload without touching disk (`own_data_dir` is not
            written).
        own_data_dir: path to partner-scrape's own pipeline-output
            directory. Defaults to `Config.get_own_data_dir()`
            (`<repo_root>/data`) when `None`. This directory is created
            automatically if missing. Tests should always pass an
            explicit `tmp_path` here, never rely on the default.
        credential_failures: sprint 023 ticket 002 -- league codes
            (e.g. `["FRC", "VEX"]`) whose acquisition source failed on
            a credential error this run (`teams.pipeline.run_teams()`'s
            own collection, threaded straight through). Defaults to
            `()` so every existing call site that omits it keeps
            working unchanged and gets a clean-run `[]` in
            `meta.credential_failures`. Sorted and de-duplicated by
            `_build_meta()`, not here -- see that function's own
            docstring.

    Returns:
        The `{"meta": ..., "teams": [...]}` payload that was (or, for
        `dry_run`, would have been) written to `own_data_dir`.

    Raises:
        RuntimeError: `own_data_dir` is not writable (e.g. it is
            occupied by a non-directory file, or has a read-only
            parent). Never silently skips the write.
    """
    resolved_own_data_dir = Path(own_data_dir) if own_data_dir is not None else get_own_data_dir()

    team_list = list(teams)
    # Sprint 016 ticket 005: t.number widened from int to str (VEX
    # designations are alphanumeric) -- a bare (t.league, t.number)
    # tuple would now sort lexicographically ("100" before "99") for
    # every existing FTC/FRC/FLL number too, not just VEX's. See
    # _natural_number_key's own docstring.
    team_list.sort(key=lambda t: (t.league, *_natural_number_key(t.number)))

    payload: dict[str, Any] = {
        "meta": _build_meta(team_list, list(credential_failures)),
        "teams": [to_json_dict(t) for t in team_list],
    }

    if dry_run:
        return payload

    serialized = json.dumps(payload, indent=1, ensure_ascii=False)

    # Sprint 020 ticket 005 (issue 60), sole write target since sprint
    # 025 ticket 004 removed this function's two `stem-ecosystem`-
    # checkout writes: the payload, written into partner-scrape's own
    # data/ directory. own_data_dir is created if missing. Mirrors
    # export/writer.py's and export/ads.py's own third write path
    # (sprint 020 tickets 003/004).
    own_teams_path = resolved_own_data_dir / "teams.json"

    try:
        resolved_own_data_dir.mkdir(parents=True, exist_ok=True)
        own_teams_path.write_text(serialized, encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(
            f"Cannot write teams export to {resolved_own_data_dir}: {exc}. "
            "Check that own_data_dir is writable."
        ) from exc

    return payload
