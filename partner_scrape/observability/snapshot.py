"""Snapshot I/O: `load_snapshot`/`save_snapshot` (sprint.md's
Architecture > Snapshot I/O, issue 08).

Loads the previous run's per-source yield snapshot from disk, and
saves the current run's, as a small JSON file: a flat object keyed by
``source_id``, each value holding that source's most recent run's
``found`` count and the set of opportunity slugs it contributed -- the
minimum needed for the next run's found/dated/new/dropped delta
computation (`yield_report.compute_yield_report`), not an
append-only history (sprint.md's Data Model). Plain-path parameters,
no `Config`/env-var coupling -- tests use `tmp_path` directly; *which*
path to use (`{site_dir}/src/data/yield-history.json`) is `cli.py`'s
job (ticket 003), not this module's.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from partner_scrape.observability.yield_report import YieldReport


def load_snapshot(path: str | Path) -> dict[str, Any]:
    """Load the previous run's snapshot from ``path``.

    Returns an empty dict -- the expected "first run ever" baseline,
    not an error -- when ``path`` does not exist.
    """
    resolved = Path(path)
    if not resolved.exists():
        return {}
    return json.loads(resolved.read_text())


def save_snapshot(path: str | Path, report: YieldReport) -> None:
    """Persist ``report``'s latest per-source ``found`` count and
    opportunity-slug set to ``path`` as JSON.

    Overwrites any existing file at ``path`` (this is the latest
    snapshot only, not an append-only history -- git's own commit
    history on the file is the audit log, per sprint.md's Data Model).
    Creates ``path``'s parent directories if they do not already exist.
    """
    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    snapshot = {
        source.source_id: {"found": source.found, "slugs": sorted(source.slugs)}
        for source in report.sources
    }
    resolved.write_text(json.dumps(snapshot, indent=2, sort_keys=True))
