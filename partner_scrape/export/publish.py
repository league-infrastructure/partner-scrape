"""`publish.project()`: the build-time projection into the published
`public/data/` tree.

`export/partner_log.py` (ticket 003) accumulates every `Opportunity`
ever seen into a durable, per-partner, append-only `.jsonl` log. That
log is not itself a publishable contract -- it can hold several lines
for the same event (one per content change) and is keyed only by
whatever partners happened to yield opportunities on some past run. This
module turns that accumulated state into issue 15's actual public data
contract: a partner roster (`public/data/partners.json`) plus, per
partner, a current/upcoming events file and a past-events file.

## Self-describing, not just "correct"

Issue 15's whole point is that a consumer needs *no other data source*
to reconstruct the site: no source code, no separately-communicated
schema, no tribal knowledge of file layout. So every published file
here carries a small metadata envelope alongside its data --
`generated_at`, a `partner_count`/`event_count`, and (for partners.json)
each partner's own reference paths to its two event files -- rather
than shipping a bare, unlabeled array and assuming the reader already
knows what it is or where to look next.

## What this module does not do

Reuses `writer.is_current_or_upcoming` for the current/past split and
`writer.SITE_SCHEMA_FIELDS`/`writer.to_json_dict` for the event field
set -- the exact same promoted helpers `export_opportunities` uses, so
the two published contracts (`opportunities.json` and `public/data/`)
can never silently disagree about which events are current or what an
event record contains. This module adds no new judgment on top of
those -- see `export/DESIGN.md`.

## One-way dependency on `partner_log.py`

This module imports exactly one thing from `partner_log.py`: the
`.jsonl` filename constant (`_JSONL_FILENAME`), so the two modules'
notion of "where the log lives" cannot drift apart. It does not import
`partner_log.record` or duplicate its slug-computation logic to
*enumerate* partners -- partners come from the curated `partners.json`
(via `model.slugify`, the same shared primitive), not from listing
`log_dir`'s subdirectories. `partner_log.py` never imports this module
-- the dependency is one-way, matching this subsystem's existing
`mirror.py` -> `writer.py`/`ads.py` convention.

## Read-cost note (not solved here)

`project()` reads and parses *every* partner's full `.jsonl` on every
call -- cost grows with total accumulated history, not with one run's
yield, since `partner_log.py` never prunes. Negligible while the store
is young; flagged in `export/DESIGN.md`'s Open Questions as worth
re-measuring later, not solved speculatively here.
"""

from __future__ import annotations

import json
from dataclasses import MISSING, fields
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from partner_scrape.config import get_scrape_cache_dir, get_site_dir
from partner_scrape.export.partner_log import _JSONL_FILENAME
from partner_scrape.export.writer import SITE_SCHEMA_FIELDS, is_current_or_upcoming, to_json_dict
from partner_scrape.model import slugify
from partner_scrape.normalize.run import Opportunity

#: Subdirectory of `SCRAPE_CACHE_DIR` the accumulation store lives
#: under -- must match `partner_log.py`'s own `_LOG_SUBDIR` exactly,
#: since this is where `project()` reads what `record()` wrote. Kept as
#: a separate constant (rather than importing `partner_log._LOG_SUBDIR`)
#: because a caller-supplied `log_dir` always overrides it in practice;
#: this is only a default.
_LOG_SUBDIR = "partner_log"


def _default_log_dir() -> Path:
    return get_scrape_cache_dir() / _LOG_SUBDIR


def _default_partners_path() -> Path:
    """`{site_dir}/src/data/partners.json` -- matches `partner_log.py`'s
    own default and `pipeline.run()`'s resolution for `normalize.run()`.
    Production callers (`cli.py`) always pass the exact value they
    already resolved for `site_dir`, so this default's independent call
    to `get_site_dir()` cannot disagree with an explicit `--site-dir`.
    """
    return get_site_dir() / "src" / "data" / "partners.json"


def _now_iso() -> str:
    """Current UTC time, matching `writer.py`'s `_now_iso()` format
    exactly -- one timestamp convention across every export this
    subsystem writes."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_jsonl_lines(jsonl_path: Path) -> list[str]:
    if not jsonl_path.exists():
        return []
    text = jsonl_path.read_text(encoding="utf-8")
    return [line for line in text.splitlines() if line.strip()]


def _collapse_last_line_wins(jsonl_path: Path) -> list[dict[str, Any]]:
    """Read `jsonl_path` and collapse to one record per `slug`, the
    later line in file order winning -- `partner_log.record()` always
    appends, never rewrites, so file order is chronological and a plain
    dict overwrite implements "last line wins" exactly."""
    by_slug: dict[str, dict[str, Any]] = {}
    for line in _read_jsonl_lines(jsonl_path):
        entry = json.loads(line)
        by_slug[entry["slug"]] = entry
    return list(by_slug.values())


def _to_opportunity(entry: dict[str, Any]) -> Opportunity:
    """Reconstruct an `Opportunity` from a persisted log line.

    `entry` carries every `Opportunity` field plus `content_hash`
    (`partner_log._to_log_dict`'s shape); only the known dataclass
    fields are pulled across, so `content_hash` is dropped naturally.
    `sources` round-trips list -> `frozenset` -- the inverse of
    `partner_log._to_log_dict`'s `frozenset` -> sorted-list conversion.

    The per-partner `.jsonl` log is strictly append-only and never
    migrated (`export/DESIGN.md`'s append-only invariant): a line
    recorded before some field existed on `Opportunity` simply lacks
    that key. Subscripting `entry` directly for a field it doesn't have
    would raise `KeyError` and break `project()` on every such line --
    every line recorded before sprint 015 added `eligibility`, for
    example. Instead, each field missing from `entry` falls back to
    `Opportunity`'s own dataclass default for that field, discovered
    generically via `dataclasses.fields()` rather than by name -- so a
    field added to `Opportunity` after a line was recorded is tolerated
    automatically, with no special case here to update when the next
    field is added.
    """
    kwargs: dict[str, Any] = {}
    for f in fields(Opportunity):
        if f.name in entry:
            kwargs[f.name] = entry[f.name]
        elif f.default is not MISSING:
            kwargs[f.name] = f.default
        elif f.default_factory is not MISSING:  # type: ignore[misc]
            kwargs[f.name] = f.default_factory()
        else:
            # No dataclass default exists for this field, and it's
            # absent from `entry` too. Not expected for any real log
            # line -- `partner_log.record()` always wrote every field
            # that existed on `Opportunity` at record time, and a
            # non-defaulted field can only be one that existed from the
            # start (dataclass field-ordering requires every defaulted
            # field to follow every non-defaulted one). Subscript
            # `entry` anyway, to raise the same `KeyError` naming this
            # field rather than inventing a value for a field the
            # dataclass itself declares required.
            kwargs[f.name] = entry[f.name]
    kwargs["sources"] = frozenset(kwargs["sources"])
    return Opportunity(**kwargs)


def _split_current_and_past(
    opportunities: list[Opportunity], today: date
) -> tuple[list[Opportunity], list[Opportunity]]:
    """Partition `opportunities` into (current/upcoming, past) using
    `writer.is_current_or_upcoming` as the sole judgment -- every
    collapsed record lands in exactly one of the two lists (this is a
    split, not a filter): nothing accumulated in the persistent log is
    ever silently dropped from the published export, unlike the legacy
    flat `opportunities.json`, which is issue 15's whole point.

    Both lists are sorted by `date_start`, matching
    `export_opportunities`'s own sort key -- no new ordering judgment
    invented here.
    """
    current = [o for o in opportunities if is_current_or_upcoming(o, today)]
    past = [o for o in opportunities if not is_current_or_upcoming(o, today)]
    current.sort(key=lambda o: o.date_start)
    past.sort(key=lambda o: o.date_start)
    return current, past


def _events_payload(kind: str, partner_slug: str, opportunities: list[Opportunity]) -> dict[str, Any]:
    """Wrap `opportunities` (already filtered/sorted) in a small
    self-describing envelope -- `generated_at`/`event_count`/`kind`/
    `partner_slug` alongside the `events` array -- so this file alone
    (with no partners.json context) tells a reader what it is."""
    return {
        "generated_at": _now_iso(),
        "partner_slug": partner_slug,
        "kind": kind,
        "event_count": len(opportunities),
        "events": [to_json_dict(o) for o in opportunities],
    }


def project(
    site_dir: str | Path | None = None,
    *,
    log_dir: str | Path | None = None,
    partners_path: str | Path | None = None,
    today: date | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Project every partner's accumulated `.jsonl` log into the
    published `{site_dir}/public/data/` tree.

    For every partner in the curated `partners_path` (not only ones
    with an accumulated log), resolves its slug (`model.slugify`,
    matching `partner_log.py`'s own resolution) and looks up
    `{log_dir}/<slug>/opportunities.jsonl`. If present, collapses it to
    one record per event slug (last line wins) and splits into current/
    upcoming vs. past (`writer.is_current_or_upcoming`). If absent, that
    partner still appears in `partners.json`, with empty event files.

    Writes:
        - `{site_dir}/public/data/partners.json` -- every curated
          partner's full curated record plus `slug`, `events_url`, and
          `past_events_url` (paths relative to `public/data/`), wrapped
          in a `generated_at`/`partner_count` envelope.
        - `{site_dir}/public/data/partners/<slug>/events.json` and
          `.../past-events.json` per partner -- each an envelope
          (`generated_at`/`kind`/`event_count`) around an `events` array
          using exactly `writer.SITE_SCHEMA_FIELDS` (`sources` excluded,
          matching `opportunities.json`).

    `src/data/opportunities.json` (written by `export_opportunities`)
    is untouched -- this is a purely additive second contract.

    Args:
        site_dir: path to the sibling `stem-ecosystem` checkout.
            Defaults to `config.get_site_dir()` when `None`. Tests
            should always pass an explicit `tmp_path`.
        log_dir: root of the per-partner accumulation store
            (`partner_log.py`'s `log_dir`). Defaults to
            `config.get_scrape_cache_dir() / "partner_log"`.
        partners_path: path to the curated `partners.json` this
            projection joins against. Defaults to
            `{site_dir}/src/data/partners.json` -- note this is
            `src/data/partners.json` (the curated input), a different
            file from the `public/data/partners.json` this function
            writes (see `export/DESIGN.md`'s Open Questions on the
            naming overlap).
        today: reference date for the current/past split. Defaults to
            `date.today()`. Tests should pass an explicit value.
        dry_run: when `True`, compute and return the summary without
            touching disk at all.

    Returns:
        A summary dict: `partner_count`, `current_event_count`,
        `past_event_count`.

    Raises:
        RuntimeError: `site_dir` does not exist, or `public/data`
            cannot be created/written under it (e.g. the path is
            occupied by a file). Never silently skips the write,
            matching `export_opportunities`'s loud-failure contract.
    """
    resolved_site_dir = Path(site_dir) if site_dir is not None else get_site_dir()
    resolved_log_dir = Path(log_dir) if log_dir is not None else _default_log_dir()
    resolved_partners_path = (
        Path(partners_path) if partners_path is not None else _default_partners_path()
    )
    reference_date = today if today is not None else date.today()

    if not resolved_site_dir.is_dir():
        raise RuntimeError(
            f"Cannot write published data export: site_dir "
            f"({resolved_site_dir}) does not exist. Check --site-dir "
            "or SITE_DIR, and that the sibling site checkout is present."
        )

    partners = json.loads(resolved_partners_path.read_text(encoding="utf-8"))

    data_dir = resolved_site_dir / "public" / "data"
    partners_dir = data_dir / "partners"

    published_partners: list[dict[str, Any]] = []
    total_current = 0
    total_past = 0
    per_partner_events: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}

    for partner in partners:
        partner_slug = slugify(partner.get("name", ""))
        jsonl_path = resolved_log_dir / partner_slug / _JSONL_FILENAME

        collapsed = [_to_opportunity(entry) for entry in _collapse_last_line_wins(jsonl_path)]
        current, past = _split_current_and_past(collapsed, reference_date)
        total_current += len(current)
        total_past += len(past)

        per_partner_events[partner_slug] = (
            _events_payload("current", partner_slug, current),
            _events_payload("past", partner_slug, past),
        )

        published_partner = dict(partner)
        published_partner["slug"] = partner_slug
        published_partner["events_url"] = f"partners/{partner_slug}/events.json"
        published_partner["past_events_url"] = f"partners/{partner_slug}/past-events.json"
        published_partners.append(published_partner)

    summary = {
        "partner_count": len(published_partners),
        "current_event_count": total_current,
        "past_event_count": total_past,
    }

    if dry_run:
        return summary

    partners_payload = {
        "generated_at": _now_iso(),
        "partner_count": len(published_partners),
        "partners": published_partners,
    }

    try:
        partners_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "partners.json").write_text(
            json.dumps(partners_payload, indent=1, ensure_ascii=False), encoding="utf-8"
        )
        for partner_slug, (events_payload, past_events_payload) in per_partner_events.items():
            partner_dir = partners_dir / partner_slug
            partner_dir.mkdir(parents=True, exist_ok=True)
            (partner_dir / "events.json").write_text(
                json.dumps(events_payload, indent=1, ensure_ascii=False), encoding="utf-8"
            )
            (partner_dir / "past-events.json").write_text(
                json.dumps(past_events_payload, indent=1, ensure_ascii=False), encoding="utf-8"
            )
    except OSError as exc:
        raise RuntimeError(
            f"Cannot write published data export to {data_dir}: {exc}. Check "
            f"that site_dir ({resolved_site_dir}) exists and its public/data "
            "subdirectory is writable."
        ) from exc

    return summary
