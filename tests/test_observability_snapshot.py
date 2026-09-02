"""Unit tests for `partner_scrape.observability.snapshot` (ticket
004-002): missing-file baseline, and a save/load round-trip through a
real `tmp_path` file.

Sprint 033 (issue 34) adds the `"__regions__"` reserved-key round-trip
for per-region counts.
"""

from __future__ import annotations

from datetime import datetime, timezone

from partner_scrape.observability.snapshot import load_snapshot, save_snapshot
from partner_scrape.observability.yield_report import RegionYield, SourceYield, YieldReport

NOW = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)


def _source(source_id: str, found: int, slugs: frozenset[str]) -> SourceYield:
    return SourceYield(
        source_id=source_id,
        org_name=f"{source_id} org",
        found=found,
        dated=found,
        new=found,
        dropped=0,
        slugs=slugs,
        previous_found=None,
        delta=None,
        error=None,
        zero_yield=False,
        cliff=False,
    )


def _region(region: str, count: int) -> RegionYield:
    return RegionYield(region=region, count=count, previous_count=None, delta=None, zero=False)


class TestLoadSnapshotMissingFile:
    def test_missing_file_returns_an_empty_dict_not_an_error(self, tmp_path):
        path = tmp_path / "yield-history.json"

        assert load_snapshot(path) == {}

    def test_missing_parent_directory_also_returns_an_empty_dict(self, tmp_path):
        path = tmp_path / "nested" / "does-not-exist" / "yield-history.json"

        assert load_snapshot(path) == {}


class TestSaveLoadRoundTrip:
    def test_round_trips_found_and_slugs_through_a_real_file(self, tmp_path):
        path = tmp_path / "yield-history.json"
        source = _source("acme", found=3, slugs=frozenset({"event-a", "event-b"}))
        report = YieldReport(sources=[source], regions=[], generated_at=NOW)

        save_snapshot(path, report)
        loaded = load_snapshot(path)

        assert loaded == {
            "acme": {"found": 3, "slugs": ["event-a", "event-b"]},
            "__regions__": {},
        }

    def test_round_trips_multiple_sources(self, tmp_path):
        path = tmp_path / "yield-history.json"
        report = YieldReport(
            sources=[
                _source("acme", found=3, slugs=frozenset({"a"})),
                _source("beta", found=0, slugs=frozenset()),
            ],
            regions=[],
            generated_at=NOW,
        )

        save_snapshot(path, report)
        loaded = load_snapshot(path)

        assert loaded == {
            "acme": {"found": 3, "slugs": ["a"]},
            "beta": {"found": 0, "slugs": []},
            "__regions__": {},
        }

    def test_save_creates_missing_parent_directories(self, tmp_path):
        path = tmp_path / "nested" / "dir" / "yield-history.json"
        report = YieldReport(sources=[], regions=[], generated_at=NOW)

        save_snapshot(path, report)

        assert path.exists()
        assert load_snapshot(path) == {"__regions__": {}}

    def test_save_overwrites_an_existing_file_rather_than_appending(self, tmp_path):
        path = tmp_path / "yield-history.json"
        save_snapshot(
            path,
            YieldReport(
                sources=[_source("acme", found=1, slugs=frozenset({"a"}))],
                regions=[],
                generated_at=NOW,
            ),
        )

        save_snapshot(
            path,
            YieldReport(
                sources=[_source("beta", found=2, slugs=frozenset({"b"}))],
                regions=[],
                generated_at=NOW,
            ),
        )

        assert load_snapshot(path) == {"beta": {"found": 2, "slugs": ["b"]}, "__regions__": {}}


class TestRegionSnapshotRoundTrip:
    """Sprint 033, issue 34: region counts persist under the reserved
    `"__regions__"` top-level key, alongside the existing flat
    per-source entries."""

    def test_region_counts_round_trip_under_the_reserved_key(self, tmp_path):
        path = tmp_path / "yield-history.json"
        report = YieldReport(
            sources=[_source("acme", found=1, slugs=frozenset({"a"}))],
            regions=[_region("South Bay", 8), _region("East County", 0)],
            generated_at=NOW,
        )

        save_snapshot(path, report)
        loaded = load_snapshot(path)

        assert loaded["__regions__"] == {"South Bay": {"count": 8}, "East County": {"count": 0}}
        # The per-source entries are unaffected by the reserved key's
        # presence.
        assert loaded["acme"] == {"found": 1, "slugs": ["a"]}

    def test_an_old_snapshot_with_no_regions_key_reads_as_no_baseline(self, tmp_path):
        """A pre-sprint-033 snapshot file (no `"__regions__"` key at
        all) must not error -- `load_snapshot` is unchanged, and reads
        as "no previous region baseline" the same way an unseen source
        already does."""
        path = tmp_path / "yield-history.json"
        path.write_text('{"acme": {"found": 1, "slugs": ["a"]}}')

        loaded = load_snapshot(path)

        assert "__regions__" not in loaded
        assert loaded["acme"] == {"found": 1, "slugs": ["a"]}
