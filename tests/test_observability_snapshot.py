"""Unit tests for `partner_scrape.observability.snapshot` (ticket
004-002): missing-file baseline, and a save/load round-trip through a
real `tmp_path` file.
"""

from __future__ import annotations

from datetime import datetime, timezone

from partner_scrape.observability.snapshot import load_snapshot, save_snapshot
from partner_scrape.observability.yield_report import SourceYield, YieldReport

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
        report = YieldReport(sources=[source], generated_at=NOW)

        save_snapshot(path, report)
        loaded = load_snapshot(path)

        assert loaded == {"acme": {"found": 3, "slugs": ["event-a", "event-b"]}}

    def test_round_trips_multiple_sources(self, tmp_path):
        path = tmp_path / "yield-history.json"
        report = YieldReport(
            sources=[
                _source("acme", found=3, slugs=frozenset({"a"})),
                _source("beta", found=0, slugs=frozenset()),
            ],
            generated_at=NOW,
        )

        save_snapshot(path, report)
        loaded = load_snapshot(path)

        assert loaded == {
            "acme": {"found": 3, "slugs": ["a"]},
            "beta": {"found": 0, "slugs": []},
        }

    def test_save_creates_missing_parent_directories(self, tmp_path):
        path = tmp_path / "nested" / "dir" / "yield-history.json"
        report = YieldReport(sources=[], generated_at=NOW)

        save_snapshot(path, report)

        assert path.exists()
        assert load_snapshot(path) == {}

    def test_save_overwrites_an_existing_file_rather_than_appending(self, tmp_path):
        path = tmp_path / "yield-history.json"
        save_snapshot(
            path,
            YieldReport(sources=[_source("acme", found=1, slugs=frozenset({"a"}))], generated_at=NOW),
        )

        save_snapshot(
            path,
            YieldReport(sources=[_source("beta", found=2, slugs=frozenset({"b"}))], generated_at=NOW),
        )

        assert load_snapshot(path) == {"beta": {"found": 2, "slugs": ["b"]}}
