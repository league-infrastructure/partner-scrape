"""Recurring-instance collapse: merge same-(source, title) Events.

Groups Events by `(source_id, normalized(title))` and folds each group
into one :class:`~partner_scrape.normalize.instance.Instance` spanning
first-to-last date, noting the repeat count (sprint.md Architecture >
Normalize & Dedup, SUC-006; ports `dev/export_site.py`'s
`collapse_recurring`, reimplemented against the canonical Event shape).

`source_id` stands in for "org" here: the Source Registry is one TOML
file per organization (sprint.md's Design Rationale), so a single
adapter run's `source_id` is already a stable per-org key -- no separate
org-name lookup is needed for *this* grouping (unlike the partner join
in run.py, which does need the human-readable name, since it must match
against `partners.json`'s own `name` field).

Runs before cross-source dedup (dedup.py) -- collapsing each org's own
recurring instances first shrinks the set cross-source dedup has to
compare, per the ticket's Approach ("order collapse before cross-source
dedup").
"""

from __future__ import annotations

import copy
from collections import defaultdict
from datetime import date, datetime
from typing import Iterable

from partner_scrape.model import Event, normalize_title
from partner_scrape.normalize.dedup import pick_best
from partner_scrape.normalize.instance import Instance

#: (source_id, normalized title) -- the recurring-collapse grouping key.
RecurringKey = tuple[str, str]


def recurring_key(event: Event) -> RecurringKey:
    """The recurring-collapse grouping key: `(source_id, normalized title)`."""
    return (event.source_id, normalize_title(event.title))


def _span(events: list[Event], today: date) -> tuple[datetime | None, datetime | None]:
    """The span to display for a recurring group: (next-upcoming start, last end).

    ``start`` is the NEXT upcoming occurrence (earliest occurrence whose
    date is ``>= today``), NOT the first-ever occurrence -- so an ongoing
    weekly/monthly series never displays a stale past date (issue 005: a
    class that started months ago but still runs was showing its original
    2025/early-2026 start). ``end`` remains the group's last occurrence.

    Fallbacks: a still-active group with no discrete upcoming occurrence
    (e.g. a single exhibit running start..end where start is past but end
    is future) shows ``today`` -- "available now". A genuinely-past group
    (no occurrence and no end reaching today) keeps its earliest start and
    is dropped downstream by the export's current+upcoming filter.
    """
    starts = [e.start for e in events if e.start is not None]
    ends = [e.end if e.end is not None else e.start for e in events]
    ends = [e for e in ends if e is not None]
    last = max(ends) if ends else None

    upcoming = [s for s in starts if s.date() >= today]
    if upcoming:
        first = min(upcoming)
    elif last is not None and last.date() >= today:
        first = datetime(today.year, today.month, today.day)
    else:
        first = min(starts) if starts else None
    return first, last


def collapse_recurring(events: Iterable[Event], today: date) -> list[Instance]:
    """Collapse same-(source, title) ``events`` into one Instance per group.

    A group of one (no recurrence) still produces an Instance --
    `repeat_count=1` and `last_seen` set from that single event -- so
    callers never need to special-case the non-recurring path.

    The representative Event for each group is the highest-scoring one
    (:func:`~partner_scrape.normalize.dedup.pick_best`, the same
    "highest-confidence/most-complete" ranking cross-source dedup uses),
    with `start`/`end` widened to the group's first-to-last span --
    matching `dev/export_site.py`'s `collapse_recurring`, which likewise
    keeps the most-complete instance's other fields while overriding the
    date range.
    """
    groups: dict[RecurringKey, list[Event]] = defaultdict(list)
    for event in events:
        groups[recurring_key(event)].append(event)

    instances: list[Instance] = []
    for group in groups.values():
        base = pick_best(group)
        first, last = _span(group, today)

        merged_event = copy.deepcopy(base)
        if first is not None:
            merged_event.start = first
        if last is not None:
            merged_event.end = last if last != first else base.end

        instances.append(
            Instance(
                event=merged_event,
                sources=frozenset({base.source_id}),
                repeat_count=len(group),
                last_seen=(last.date() if last is not None else None),
            )
        )
    return instances
