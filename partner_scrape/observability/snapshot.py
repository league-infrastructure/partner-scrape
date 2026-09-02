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

from partner_scrape.observability.yield_report import REGIONS_SNAPSHOT_KEY, YieldReport


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
    opportunity-slug set, plus (sprint 033, issue 34) this run's
    per-region counts, to ``path`` as JSON.

    Overwrites any existing file at ``path`` (this is the latest
    snapshot only, not an append-only history -- git's own commit
    history on the file is the audit log, per sprint.md's Data Model).
    Creates ``path``'s parent directories if they do not already exist.

    Region counts are written under one reserved top-level key,
    `REGIONS_SNAPSHOT_KEY` (``"__regions__"``) -- collision-safe against
    real `source_id`s, which never use double-underscore wrapping --
    alongside the existing flat per-source entries, so an old snapshot
    file with no such key reads (via `load_snapshot`, unchanged) as "no
    previous region baseline" for every region, the same first-run
    behavior an unseen source already gets.
    """
    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    snapshot: dict[str, Any] = {
        source.source_id: {"found": source.found, "slugs": sorted(source.slugs)}
        for source in report.sources
    }
    snapshot[REGIONS_SNAPSHOT_KEY] = {
        region.region: {"count": region.count} for region in report.regions
    }
    resolved.write_text(json.dumps(snapshot, indent=2, sort_keys=True))
