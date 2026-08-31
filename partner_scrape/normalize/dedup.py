"""Cross-source dedup: merge Instances representing the same real-world event.

Cross-source identity ("is this the same event as one from another org")
is deliberately coarser than `model.py`'s acquisition `identity_key()`
("have we already seen this exact record from this source") -- see that
function's module docstring. Identity here is normalized(title) + date +
normalized(venue), computed *across* `source_id`s so a physically
identical event that two different organizations both list gets merged
into one record (sprint.md Architecture > Normalize & Dedup, SUC-006).

Operates on :class:`~partner_scrape.normalize.instance.Instance` (i.e.
runs after collapse.py, not directly on raw Events) -- see run.py's
module docstring for why: collapsing each org's own recurring instances
first shrinks the set this stage has to compare, and threading `Instance`
through both stages means the winning record's `sources` set can be
unioned once collapse.py has already established each instance's own
per-org source.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from typing import Iterable

from partner_scrape.model import Event, normalize_title
from partner_scrape.normalize.instance import Instance

#: normalized(title), event date, normalized(venue) -- the cross-source
#: dedup identity (sprint.md: "identity = normalized(title) + date +
#: venue, computed across organizations").
CrossSourceIdentity = tuple[str, date | None, str]

#: A comma-delimited segment shaped like a street address: a leading
#: street number followed by a street name (sprint 016 ticket 003 /
#: sprint.md Architecture > Design Rationale). Deliberately narrow --
#: matches only the "<number> <name>" shape, not a general address
#: grammar.
_STREET_SEGMENT_RE = re.compile(r"^\d+\s+\S")


def normalize_venue(location: str) -> str:
    """Address-aware venue canonicalization for cross-source venue comparison.

    Splits ``location`` on commas and looks for a segment whose stripped
    text matches a leading street number plus street name
    (``^\\d+\\s+\\S``, e.g. "1875 El Prado"). If found, *that segment
    alone* -- title-normalized via `model.normalize_title` -- becomes
    the venue token, deliberately dropping any org-name prefix (e.g.
    "Fleet Science Center,") and city/state/ZIP suffix segments, so
    "Fleet Science Center, 1875 El Prado, San Diego, CA" and "1875 El
    Prado, San Diego, CA 92101" both reduce to "1875 el prado" despite
    differing org-name prefix and ZIP presence (sprint 016 ticket 003 /
    issue 39's measured Balboa Park / Fleet pair).

    Falls back to `normalize_title(location)` -- today's exact,
    unchanged behavior -- whenever no comma-delimited segment matches
    the street-address shape, which includes a location string with no
    comma at all. A comma-less string is never treated as a single
    street-address segment even if it starts with a digit: matching on
    the whole comma-less string risks swallowing trailing city/state/ZIP
    text into the "venue token," silently reintroducing the exact
    ZIP-suffix mismatch this function exists to strip (see sprint.md
    Architecture > Design Rationale for the full reasoning). This keeps
    the rule a conservative token-match, not a general address parser --
    it either finds a clear street-address token or it changes nothing.
    """
    if "," in location:
        for segment in location.split(","):
            stripped = segment.strip()
            if _STREET_SEGMENT_RE.match(stripped):
                return normalize_title(stripped)
    return normalize_title(location)


def cross_source_identity(event: Event) -> CrossSourceIdentity:
    """The cross-source dedup identity: normalized(title) + date + normalized(venue).

    Reuses `model.normalize_title` for title text and `normalize_venue`
    (sprint 016 ticket 003) for venue text -- both are "how do we
    recognize the same thing" normalization, but venue additionally
    needs address-level canonicalization so the same physical address
    formatted differently by two sources (org-name prefix vs. ZIP
    suffix) still matches; see `normalize_venue`'s docstring.
    """
    event_date = event.start.date() if event.start is not None else None
    return (normalize_title(event.title), event_date, normalize_venue(event.location))


def score_event(event: Event) -> tuple[float, int]:
    """Score an Event's "highest-confidence/most-complete instance" rank.

    Higher is better: ``(average field-provenance confidence, count of
    populated content fields)``. Confidence is compared first -- a
    lower-confidence-but-more-complete record must not outrank a
    high-confidence terse one; completeness only breaks ties among
    equally-trusted records.
    """
    confidences = [p.confidence for p in event.field_provenance.values()]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    populated = sum(
        1
        for value in (
            event.title,
            event.description,
            event.location,
            event.cost,
            event.registration_url,
            event.image_url,
        )
        if value
    )
    populated += len(event.categories) + len(event.tags)
    if event.start is not None:
        populated += 1
    if event.end is not None:
        populated += 1

    return (avg_confidence, populated)


def pick_best(events: Iterable[Event]) -> Event:
    """Return the highest-:func:`score_event`-ranked Event in ``events``.

    Ties keep the first-encountered instance (``max``'s documented
    tie-breaking behavior), so the result is deterministic given
    deterministic input order.
    """
    return max(events, key=score_event)


def dedup_cross_source(instances: Iterable[Instance]) -> list[Instance]:
    """Merge ``instances`` sharing a :func:`cross_source_identity`.

    Groups across every `source_id` (that is the point of this stage --
    see module docstring), keeps the highest-:func:`score_event`-ranked
    instance's Event as the record of truth, and unions every group
    member's `sources` so the merged set is recorded on the result
    rather than dropped (ticket's acceptance criteria). Instances that
    share only a title but differ in date or venue land in different
    groups and are never merged.
    """
    groups: dict[CrossSourceIdentity, list[Instance]] = defaultdict(list)
    for instance in instances:
        groups[cross_source_identity(instance.event)].append(instance)

    merged: list[Instance] = []
    for group in groups.values():
        best = max(group, key=lambda inst: score_event(inst.event))
        sources: set[str] = set()
        for inst in group:
            sources |= inst.sources
        merged.append(
            Instance(
                event=best.event,
                sources=frozenset(sources),
                repeat_count=best.repeat_count,
                last_seen=best.last_seen,
            )
        )
    return merged
