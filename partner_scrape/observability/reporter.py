"""`YieldReporter`: `pipeline.Reporter`'s concrete implementation
(sprint.md's Architecture > `YieldReporter`, issue 08).

Collects each `record_source(...)` call and the one
`record_opportunities(...)` call `pipeline.run(reporter=...)` makes,
then exposes `.report(previous_snapshot)` for the caller (ticket 003's
`cli.py`) to invoke once `run()` returns.

Satisfies `pipeline.Reporter` **structurally** -- this module (and the
rest of this package) imports neither `partner_scrape.pipeline` nor
`partner_scrape.pipeline.Reporter`, matching the verified precedent
that `enrich.enricher.LLMEnricher` satisfies `pipeline.Enricher` the
same way, with zero import-time coupling to `pipeline.py`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from partner_scrape.model import Event
from partner_scrape.observability.yield_report import (
    SourceRecord,
    YieldReport,
    compute_yield_report,
)


class YieldReporter:
    """Accumulates one run's per-source facts for `yield_report`'s
    comparison logic to turn into a `YieldReport`.

    A fresh instance is meant for exactly one `pipeline.run(reporter=
    ...)` call -- construct a new `YieldReporter` per run.
    """

    def __init__(self) -> None:
        self._source_records: list[SourceRecord] = []
        self._opportunities: list[Any] = []

    def record_source(
        self,
        source_id: str,
        org_name: str,
        events: list[Event],
        error: Exception | None = None,
    ) -> None:
        """Fulfills `pipeline.Reporter.record_source`: records this
        source's raw `Event` list (or `[]` + the isolated exception on
        an adapter failure) verbatim, for `yield_report.py`'s
        found/dated derivation."""
        self._source_records.append(SourceRecord(source_id, org_name, list(events), error))

    def record_opportunities(self, opportunities: list[Any]) -> None:
        """Fulfills `pipeline.Reporter.record_opportunities`: records
        the final normalized opportunity list verbatim, for
        `yield_report.py`'s new/dropped derivation (still carrying
        `.sources` at this point, before `export_opportunities()`
        strips it)."""
        self._opportunities = list(opportunities)

    def report(
        self,
        previous_snapshot: dict[str, Any] | None = None,
        *,
        now: datetime | None = None,
    ) -> YieldReport:
        """Compute this run's `YieldReport` against ``previous_snapshot``
        (as returned by `snapshot.load_snapshot`; omit or pass `{}` for
        a first-ever run -- an expected baseline, not an error).

        ``now`` overrides the report's `generated_at` timestamp; tests
        should pass an explicit value for determinism.
        """
        return compute_yield_report(
            self._source_records,
            self._opportunities,
            previous_snapshot,
            now=now,
        )
