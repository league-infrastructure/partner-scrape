"""Internal bookkeeping wrapper threaded through collapse -> dedup -> mapping.

Not part of any external contract. `Event` (ticket 001's model) is not
modified by this ticket, and `Opportunity` (run.py) only gains what the
site schema documents plus one explicit `sources` field. `Instance` is
how repeat-count and contributing-source bookkeeping travels between
this module's internal stages without touching either of those shapes
-- the same role dev/export_site.py's `_repeat_count` sidecar dict key
played, made an explicit type instead of a magic key.

Lives in its own module (rather than inside collapse.py or dedup.py) so
both of those can import it without creating a collapse<->dedup import
cycle -- collapse.py calls into dedup.py's scoring helpers, so dedup.py
must not import collapse.py back.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from partner_scrape.model import Event


@dataclass(frozen=True)
class Instance:
    """One (possibly already-collapsed/merged) Event plus normalize bookkeeping.

    Attributes:
        event: the representative Event -- its field values are what the
            eventual Opportunity is built from.
        sources: every `source_id` this record was seen on (one entry
            before any cross-source merge, more after dedup.py merges
            duplicates from different sources).
        repeat_count: how many raw recurring instances collapse.py folded
            into `event` (1 if it never recurred).
        last_seen: the last occurrence's date, for the "Repeats N times
            through <date>" availability text -- `None` when no
            occurrence in the group had a usable date.
    """

    event: Event
    sources: frozenset[str]
    repeat_count: int = 1
    last_seen: date | None = None
