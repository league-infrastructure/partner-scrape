"""Tests for dev/backfill_missing_images.py's --prune mode (and a
regression check that the existing check-only default is unaffected).

dev/ is a standalone-script directory (no __init__.py, never imported
by runtime code -- see the script's own docstring), so it is loaded
here via importlib rather than a normal package import. Every test
builds its own fixture data directory under tmp_path -- never against
the real repo data/ tree (see the get_own_data_dir() hazard noted in
sprint 037's ticket 001).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parent.parent.parent / "dev" / "backfill_missing_images.py"
_spec = importlib.util.spec_from_file_location("backfill_missing_images", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
backfill_missing_images = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = backfill_missing_images
_spec.loader.exec_module(backfill_missing_images)


def _make_data_dir(tmp_path: Path) -> Path:
    """Build a fixture data dir with one opportunity-referenced image,
    one partner-referenced image, and two orphaned images.
    """
    data_dir = tmp_path / "data"
    images_dir = data_dir / "images" / "opportunities"
    images_dir.mkdir(parents=True)

    for name in ("opp-ref.jpg", "partner-ref.jpg", "orphan-1.jpg", "orphan-2.jpg"):
        (images_dir / name).write_bytes(b"fake-image-bytes")

    (data_dir / "opportunities.json").write_text(
        json.dumps([{"id": "o1", "image_src": "opp-ref.jpg"}]),
        encoding="utf-8",
    )

    partner_dir = data_dir / "partners" / "acme"
    partner_dir.mkdir(parents=True)
    (partner_dir / "events.json").write_text(
        json.dumps({"events": [{"id": "e1", "image_src": "partner-ref.jpg"}]}),
        encoding="utf-8",
    )
    (partner_dir / "past-events.json").write_text(
        json.dumps({"events": []}),
        encoding="utf-8",
    )

    return data_dir


def test_prune_dry_run_reports_without_deleting(tmp_path: Path) -> None:
    data_dir = _make_data_dir(tmp_path)
    images_dir = data_dir / "images" / "opportunities"

    orphaned = backfill_missing_images.prune(data_dir, dry_run=True)

    assert orphaned == ["orphan-1.jpg", "orphan-2.jpg"]
    # Nothing was actually deleted.
    assert {p.name for p in images_dir.glob("*")} == {
        "opp-ref.jpg",
        "partner-ref.jpg",
        "orphan-1.jpg",
        "orphan-2.jpg",
    }


def test_prune_deletes_exactly_the_orphaned_set(tmp_path: Path) -> None:
    data_dir = _make_data_dir(tmp_path)
    images_dir = data_dir / "images" / "opportunities"

    orphaned = backfill_missing_images.prune(data_dir, dry_run=False)

    assert orphaned == ["orphan-1.jpg", "orphan-2.jpg"]
    remaining = {p.name for p in images_dir.glob("*")}
    assert remaining == {"opp-ref.jpg", "partner-ref.jpg"}


def test_prune_with_nothing_orphaned_deletes_nothing(tmp_path: Path) -> None:
    data_dir = _make_data_dir(tmp_path)
    images_dir = data_dir / "images" / "opportunities"
    # Remove the orphans up front so referenced == existing.
    (images_dir / "orphan-1.jpg").unlink()
    (images_dir / "orphan-2.jpg").unlink()

    orphaned = backfill_missing_images.prune(data_dir, dry_run=False)

    assert orphaned == []
    assert {p.name for p in images_dir.glob("*")} == {"opp-ref.jpg", "partner-ref.jpg"}


def test_check_only_default_unaffected_by_prune_flag(tmp_path: Path) -> None:
    """The existing check-only behavior (no --prune, no --source-dir)
    must report 0 missing when everything referenced is present,
    regardless of orphaned files sitting alongside them.
    """
    data_dir = _make_data_dir(tmp_path)

    missing_partners, missing_opportunities = backfill_missing_images.check(data_dir, heading="Before:")

    assert missing_partners == set()
    assert missing_opportunities == set()


def test_check_reports_missing_when_referenced_file_absent(tmp_path: Path) -> None:
    data_dir = _make_data_dir(tmp_path)
    (data_dir / "images" / "opportunities" / "opp-ref.jpg").unlink()

    missing_partners, missing_opportunities = backfill_missing_images.check(data_dir, heading="Before:")

    assert missing_partners == set()
    assert missing_opportunities == {"opp-ref.jpg"}


def test_main_prune_dry_run_exits_zero_and_deletes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_dir = _make_data_dir(tmp_path)
    images_dir = data_dir / "images" / "opportunities"

    monkeypatch.setattr(
        sys,
        "argv",
        ["backfill_missing_images.py", "--data-dir", str(data_dir), "--prune", "--dry-run"],
    )

    exit_code = backfill_missing_images.main()

    assert exit_code == 0
    assert {p.name for p in images_dir.glob("*")} == {
        "opp-ref.jpg",
        "partner-ref.jpg",
        "orphan-1.jpg",
        "orphan-2.jpg",
    }


def test_main_prune_deletes_orphans_and_reports_zero_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = _make_data_dir(tmp_path)
    images_dir = data_dir / "images" / "opportunities"

    monkeypatch.setattr(
        sys,
        "argv",
        ["backfill_missing_images.py", "--data-dir", str(data_dir), "--prune"],
    )

    exit_code = backfill_missing_images.main()

    assert exit_code == 0
    assert {p.name for p in images_dir.glob("*")} == {"opp-ref.jpg", "partner-ref.jpg"}
