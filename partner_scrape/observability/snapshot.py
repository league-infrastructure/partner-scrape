"""Snapshot I/O: `load_snapshot`/`save_snapshot` (sprint.md's
Architecture > Snapshot I/O, issue 08).

Loads the previous run's per-source yield snapshot from a Store, and
saves the current run's, as a small JSON file: a flat object keyed by
``source_id``, each value holding that source's most recent run's
``found`` count and the set of opportunity slugs it contributed -- the
minimum needed for the next run's found/dated/new/dropped delta
computation (`yield_report.compute_yield_report`), not an
append-only history (sprint.md's Data Model). Plain
`Store` parameters, no `Config`/env-var coupling -- tests use a
`LocalStore(tmp_path)` directly; *which* Store to use (the data Store,
key `yield-history.json`) is `cli.py`'s job, not this module's. Bucket
versioning on the data prefix, not git, keeps the history of this file.
"""

from __future__ import annotations

import json
from typing import Any

from partner_scrape.observability.yield_report import REGIONS_SNAPSHOT_KEY, YieldReport
from partner_scrape.storage import Store

#: Key of the snapshot in the data Store.
YIELD_HISTORY_KEY = "yield-history.json"


def load_snapshot(store: Store, key: str = YIELD_HISTORY_KEY) -> dict[str, Any]:
    """Load the previous run's snapshot from ``key`` in ``store``.

    Returns an empty dict -- the expected "first run ever" baseline,
    not an error -- when ``key`` does not exist.
    """
    snapshot = store.read_json(key)
    return {} if snapshot is None else snapshot


def save_snapshot(
    store: Store, report: YieldReport, key: str = YIELD_HISTORY_KEY
) -> None:
    """Persist ``report``'s latest per-source ``found`` count and
    opportunity-slug set, plus (sprint 033, issue 34) this run's
    per-region counts, to ``key`` in ``store`` as JSON.

    Overwrites any existing object at ``key`` (this is the latest
    snapshot only, not an append-only history -- bucket versioning on
    the data prefix is the audit log, per sprint.md's Data Model).

    Region counts are written under one reserved top-level key,
    `REGIONS_SNAPSHOT_KEY` (``"__regions__"``) -- collision-safe against
    real `source_id`s, which never use double-underscore wrapping --
    alongside the existing flat per-source entries, so an old snapshot
    file with no such key reads (via `load_snapshot`, unchanged) as "no
    previous region baseline" for every region, the same first-run
    behavior an unseen source already gets.
    """
    snapshot: dict[str, Any] = {
        source.source_id: {"found": source.found, "slugs": sorted(source.slugs)}
        for source in report.sources
    }
    snapshot[REGIONS_SNAPSHOT_KEY] = {
        region.region: {"count": region.count} for region in report.regions
    }
    store.write_text(
        key, json.dumps(snapshot, indent=2, sort_keys=True), "application/json"
    )
