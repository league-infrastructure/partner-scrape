"""`export_opportunities()`: the Site Export module's single entry point.

Publishes already-normalized `Opportunity` records (produced by
`partner_scrape.normalize.run`, ticket 006) into the sibling
`stem-ecosystem` repo's data contract (sprint.md Architecture > Site
Export, SUC-007). This module does not re-derive or re-map any field --
its only responsibilities are:

1. Filter to current + upcoming records (historical data never ships).
2. A defensive slug-uniqueness pass (normalize already dedupes by
   title+date+venue, but distinct records can still collide on the
   truncated slug -- e.g. same org+title on nearby dates truncated the
   same way).
3. Serialize exactly the site schema's field set -- dropping
   `Opportunity.sources`, which is normalize's own cross-source
   bookkeeping and not part of `stem-ecosystem/docs/site-implementation
   -spec.md`'s Opportunities table.
4. Write `src/data/opportunities.json` and `src/data/scrape-meta.json`
   into the site repo, matching `dev/export_site.py`'s existing
   behavior and file shapes exactly so the site consumes them
   unchanged.

A missing or unwritable `site_dir` (or its `src/data` subdirectory)
fails loudly -- SUC-007's explicit error flow is "fail loudly, do not
silently skip the export."
"""

from __future__ import annotations

import json
from dataclasses import fields
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from partner_scrape.config import get_site_dir
from partner_scrape.normalize.run import WORK_BASED_LEARNING_TYPE, Opportunity

#: The exact field set written to `opportunities.json` -- every
#: `Opportunity` field except `sources`, which is normalize's internal
#: bookkeeping (the set of contributing `source_id`s) and has no
#: counterpart in the site's schema. Derived from the dataclass fields
#: rather than hand-listed so it can never drift from `Opportunity`
#: itself.
_SITE_SCHEMA_FIELDS: tuple[str, ...] = tuple(
    f.name for f in fields(Opportunity) if f.name != "sources"
)


def _is_current_or_upcoming(opportunity: Opportunity, today: date) -> bool:
    """True if `opportunity`'s end date, or start date if no end date, is
    today or later (SUC-007 main flow step 1). Undated records (neither
    `date_start` nor `date_end` set) are excluded -- matching
    `dev/export_site.py`'s equivalent string comparison, an unset date
    can never be judged "today or later".

    `opportunity_type == "Work-based Learning"` (internship) records get
    a different rule (sprint 006 Design Rationale, SUC-004): `date_start`
    is redefined as the posting-observed date, which is routinely in the
    past for a still-open, no-deadline internship -- the ordinary
    `date_end or date_start >= today` rule would wrongly expire it. Such
    a record is current if `date_end` (the application deadline) is
    unset or still in the future; every other `opportunity_type` keeps
    the exact rule above, unchanged.
    """
    if opportunity.opportunity_type == WORK_BASED_LEARNING_TYPE:
        if not opportunity.date_end:
            return True
        return date.fromisoformat(opportunity.date_end[:10]) >= today

    date_str = opportunity.date_end or opportunity.date_start
    if not date_str:
        return False
    return date.fromisoformat(date_str[:10]) >= today


def _to_json_dict(opportunity: Opportunity) -> dict[str, Any]:
    """Project `opportunity` onto exactly `_SITE_SCHEMA_FIELDS` -- this is
    where `sources` (and any other future non-schema field) is dropped."""
    return {name: getattr(opportunity, name) for name in _SITE_SCHEMA_FIELDS}


def _dedupe_slugs(payload: list[dict[str, Any]]) -> None:
    """Disambiguate colliding `slug`s in place with a numeric suffix,
    matching `dev/export_site.py`'s `seen`-dict approach. Neither
    colliding record is dropped -- only the later one's slug changes."""
    seen: dict[str, int] = {}
    for record in payload:
        slug = record["slug"]
        if slug in seen:
            seen[slug] += 1
            record["slug"] = f"{slug}_{seen[slug]}"
        else:
            seen[slug] = 1


def _now_iso() -> str:
    """Current UTC time as the `scrape-meta.json` timestamp format,
    matching `dev/export_site.py`'s `datetime.now(timezone.utc)...`
    formatting exactly."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def export_opportunities(
    opportunities: Iterable[Opportunity],
    site_dir: str | Path | None = None,
    *,
    today: date | None = None,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Filter, dedupe, and write `opportunities` into `site_dir`'s data contract.

    Args:
        opportunities: normalized, deduplicated `Opportunity` records
            (typically `normalize.run()`'s output).
        site_dir: path to the sibling `stem-ecosystem` checkout. Defaults
            to `Config.get_site_dir()` (`../stem-ecosystem`) when `None`
            -- ticket 008's CLI wires a `--site-dir` override onto this
            parameter. Tests should always pass an explicit `tmp_path`
            here, never rely on the default, so runs never touch the
            real site repo.
        today: the reference date for the current/upcoming filter.
            Defaults to `date.today()`. Tests should pass an explicit
            value for determinism.
        dry_run: when `True`, compute and return the would-be-written
            payload without touching disk.

    Returns:
        The list of opportunity dicts that were (or, for `dry_run`,
        would have been) written, in the exact shape and field set
        written to `opportunities.json`.

    Raises:
        RuntimeError: `site_dir`'s `src/data` subdirectory does not
            exist or is not writable. Never silently skips the write.
    """
    resolved_site_dir = Path(site_dir) if site_dir is not None else get_site_dir()
    reference_date = today if today is not None else date.today()

    current = [o for o in opportunities if _is_current_or_upcoming(o, reference_date)]
    current.sort(key=lambda o: o.date_start)

    payload = [_to_json_dict(o) for o in current]
    _dedupe_slugs(payload)

    if dry_run:
        return payload

    data_dir = resolved_site_dir / "src" / "data"
    opportunities_path = data_dir / "opportunities.json"
    meta_path = data_dir / "scrape-meta.json"

    try:
        opportunities_path.write_text(
            json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8"
        )
        meta_path.write_text(json.dumps({"last_updated": _now_iso()}), encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(
            f"Cannot write site export to {data_dir}: {exc}. Check that "
            f"site_dir ({resolved_site_dir}) exists and its src/data "
            "subdirectory is writable."
        ) from exc

    return payload
