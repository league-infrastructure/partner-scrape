"""Source-yield observability (issue 08): per-source found/dated/new/
dropped counts, deltas vs. the previous run, zero-yield/cliff alerts,
and plain-text rendering, on top of `pipeline.Reporter`'s hook (ticket
004-001).

See sprint.md's Architecture > Yield Tracking / Report Rendering /
Snapshot I/O / `YieldReporter`. `YieldReporter` (`reporter.py`) is the
concrete class ticket 003's `cli.py` passes as
`pipeline.run(reporter=...)`; it satisfies `pipeline.Reporter`
structurally, with zero import of `partner_scrape.pipeline` anywhere in
this package, and this package imports nothing from `cli.py`,
`export/`, `registry/`, or `adapters/`.
"""

from __future__ import annotations

from partner_scrape.observability.render import render_text
from partner_scrape.observability.reporter import YieldReporter
from partner_scrape.observability.snapshot import load_snapshot, save_snapshot
from partner_scrape.observability.yield_report import (
    CLIFF_DROP_THRESHOLD,
    SourceRecord,
    SourceYield,
    YieldReport,
    compute_yield_report,
)

__all__ = [
    "CLIFF_DROP_THRESHOLD",
    "SourceRecord",
    "SourceYield",
    "YieldReport",
    "YieldReporter",
    "compute_yield_report",
    "load_snapshot",
    "render_text",
    "save_snapshot",
]
