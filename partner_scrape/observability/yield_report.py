"""Yield Tracking: `SourceYield`/`YieldReport` + pure comparison/threshold
logic (sprint.md's Architecture > Yield Tracking, issue 08).

Turns one run's raw per-source `Event`s and final `Opportunity` list,
plus the previous run's persisted snapshot, into per-source
found/dated/new/dropped counts, deltas, and zero-yield/cliff alert
flags. `found`/`dated` are derived here from the raw `Event` list
`pipeline.Reporter.record_source()` receives -- not computed by
`pipeline.py` -- and `new`/`dropped` from the final opportunity list's
`.sources` attribution, matched by slug against the previous snapshot's
per-source slug sets. No I/O, no knowledge of `pipeline.py`: pure
data-in, data-out, which is what makes this hermetically testable
(sprint.md's Test Strategy).

Opportunities are accepted as `list[Any]` and read via `getattr(...,
"slug"/"sources")`, mirroring `pipeline.Reporter.record_opportunities`'s
own `list[Any]` signature -- this module never imports
`normalize.run.Opportunity`, so it stays decoupled from every module
`pipeline.py` itself is decoupled from (sprint.md's Dependency
direction check).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from partner_scrape.model import Event

#: Proportional found-count drop (previous run -> this run) that
#: triggers a cliff alert. Provisional per sprint.md's Open Questions
#: ("a reasonable starting default, not a value with strong evidence
#: behind it yet ... revisit once a few real scheduled runs establish
#: what normal week-to-week variance actually looks like per source")
#: -- a plain module constant, tunable without any architecture change.
CLIFF_DROP_THRESHOLD = 0.5


@dataclass
class SourceRecord:
    """One source's raw this-run facts, as `YieldReporter` (reporter.py)
    accumulates them from `pipeline.Reporter.record_source(...)` calls.

    ``events`` is the source's real, unmodified `list[Event]` on
    success, or `[]` on an isolated adapter failure -- matching
    `pipeline.Reporter.record_source`'s own two call branches. ``error``
    distinguishes the two: `None` for a clean run (including a clean run
    that genuinely found nothing), the caught exception when the
    adapter raised.
    """

    source_id: str
    org_name: str
    events: list[Event] = field(default_factory=list)
    error: Exception | None = None


@dataclass
class SourceYield:
    """One source's this-run yield: raw counts, delta vs. the previous
    run's snapshot (if any), and alert state.

    ``previous_found``/``delta`` are `None` when this source has no
    entry in the previous snapshot (first-ever run for that source) --
    an expected baseline, not an error (sprint.md's Migration Concerns
    > "First-run behavior"). ``slugs`` is this run's opportunity-slug
    set for this source -- what `snapshot.save_snapshot` persists as
    next run's comparison baseline.
    """

    source_id: str
    org_name: str
    found: int
    dated: int
    new: int
    dropped: int
    slugs: frozenset[str]
    previous_found: int | None
    delta: int | None
    error: Exception | None
    zero_yield: bool
    cliff: bool

    @property
    def has_alert(self) -> bool:
        return self.zero_yield or self.cliff


@dataclass
class YieldReport:
    """One run's full yield report: every reported source's
    `SourceYield`, plus a generated timestamp."""

    sources: list[SourceYield]
    generated_at: datetime

    @property
    def alerts(self) -> list[SourceYield]:
        """Every source currently flagged zero-yield or cliff, in the
        same order they appear in `sources` -- what `render.render_text`
        surfaces ahead of the per-source detail lines."""
        return [source for source in self.sources if source.has_alert]


def _dated_count(events: list[Event]) -> int:
    return sum(1 for event in events if getattr(event, "start", None) is not None)


def _opportunity_slugs_by_source(opportunities: list[Any]) -> dict[str, set[str]]:
    """Group ``opportunities`` (duck-typed: any object with ``.slug``
    and ``.sources``) by each contributing ``source_id`` -- the
    post-dedup, post-enrichment, site-visible attribution `new`/
    `dropped` are computed from, distinct from raw per-source `found`."""
    by_source: dict[str, set[str]] = {}
    for opportunity in opportunities:
        slug = getattr(opportunity, "slug", None)
        if not slug:
            continue
        for source_id in getattr(opportunity, "sources", ()) or ():
            by_source.setdefault(source_id, set()).add(slug)
    return by_source


def _compute_source_yield(
    record: SourceRecord,
    slugs: set[str],
    previous_entry: dict[str, Any] | None,
) -> SourceYield:
    found = len(record.events)
    dated = _dated_count(record.events)

    previous_slugs = set(previous_entry["slugs"]) if previous_entry else set()
    new = len(slugs - previous_slugs)
    dropped = len(previous_slugs - slugs)

    previous_found = previous_entry["found"] if previous_entry else None
    delta = found - previous_found if previous_found is not None else None

    zero_yield = False
    cliff = False
    # Alerts require a real previous-snapshot entry for this source
    # with a positive found count -- no entry means "first-ever run"
    # (an expected baseline, not a regression), and a previous found of
    # 0 means there is nothing to regress *from* (also avoids a
    # division by zero below).
    if previous_found is not None and previous_found > 0:
        if found == 0:
            zero_yield = True
        else:
            drop_ratio = (previous_found - found) / previous_found
            cliff = drop_ratio > CLIFF_DROP_THRESHOLD

    return SourceYield(
        source_id=record.source_id,
        org_name=record.org_name,
        found=found,
        dated=dated,
        new=new,
        dropped=dropped,
        slugs=frozenset(slugs),
        previous_found=previous_found,
        delta=delta,
        error=record.error,
        zero_yield=zero_yield,
        cliff=cliff,
    )


def compute_yield_report(
    source_records: list[SourceRecord],
    opportunities: list[Any],
    previous_snapshot: dict[str, Any] | None = None,
    *,
    now: datetime | None = None,
) -> YieldReport:
    """Compute a `YieldReport` from one run's raw per-source facts.

    Args:
        source_records: one `SourceRecord` per source reported this run
            (`YieldReporter`'s accumulated `record_source(...)` calls).
        opportunities: the final normalized opportunity list
            (`YieldReporter`'s single `record_opportunities(...)` call),
            duck-typed on ``.slug``/``.sources``.
        previous_snapshot: the previous run's snapshot, as returned by
            `snapshot.load_snapshot` (`{}` for a first-ever run --
            `load_snapshot` itself never raises on a missing file).
        now: the report's `generated_at` timestamp. Defaults to
            `datetime.now(timezone.utc)`; tests should pass an explicit
            value for determinism.

    Returns:
        A `YieldReport` with one `SourceYield` per `source_records`
        entry, in the same order.
    """
    previous_snapshot = previous_snapshot or {}
    slugs_by_source = _opportunity_slugs_by_source(opportunities)
    sources = [
        _compute_source_yield(
            record,
            slugs_by_source.get(record.source_id, set()),
            previous_snapshot.get(record.source_id),
        )
        for record in source_records
    ]
    return YieldReport(
        sources=sources,
        generated_at=now if now is not None else datetime.now(timezone.utc),
    )
