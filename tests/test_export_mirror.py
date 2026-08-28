"""`mirror_site_data` keeps extra site checkouts in step with an export."""

from __future__ import annotations

import json

import pytest

from partner_scrape.export.mirror import IMAGES_SUBPATH, mirror_site_data


def _make_site(root, *, data: dict[str, str] | None = None, images=()):
    """Build a minimal site checkout: src/data plus opportunity images."""
    data_dir = root / "src" / "data"
    data_dir.mkdir(parents=True)
    for name, body in (data or {}).items():
        (data_dir / name).write_text(body)
    if images:
        image_dir = root / IMAGES_SUBPATH
        image_dir.mkdir(parents=True)
        for name, body in images:
            (image_dir / name).write_text(body)
    return root


@pytest.fixture
def primary(tmp_path):
    return _make_site(
        tmp_path / "stem-ecosystem",
        data={
            "opportunities.json": json.dumps([{"title": "Fresh"}]),
            "scrape-meta.json": json.dumps({"last_updated": "2026-08-28T04:13:41Z"}),
            "ads.json": json.dumps([]),
            "partners.json": json.dumps(["production roster"]),
        },
        images=[("event-a.jpg", "AAA")],
    )


def test_generated_files_reach_the_target(primary, tmp_path):
    target = _make_site(
        tmp_path / "beta",
        data={"opportunities.json": json.dumps([{"title": "Stale"}])},
    )

    assert mirror_site_data(primary, [target]) == [target.resolve()]

    data_dir = target / "src" / "data"
    assert json.loads((data_dir / "opportunities.json").read_text()) == [{"title": "Fresh"}]
    assert json.loads((data_dir / "scrape-meta.json").read_text())["last_updated"]
    assert (data_dir / "ads.json").is_file()


def test_curated_partners_json_is_never_overwritten(primary, tmp_path):
    """partners.json is a per-checkout *input*, not export output.

    The pipeline reads it to build the partner roster, and the two
    checkouts legitimately carry different ones -- copying production's
    over the beta site's would silently swap that roster.
    """
    target = _make_site(
        tmp_path / "beta",
        data={"partners.json": json.dumps(["beta roster"])},
    )

    mirror_site_data(primary, [target])

    assert json.loads((target / "src" / "data" / "partners.json").read_text()) == [
        "beta roster"
    ]


def test_images_are_copied_so_the_json_is_not_left_dangling(primary, tmp_path):
    target = _make_site(tmp_path / "beta", data={})

    mirror_site_data(primary, [target])

    assert (target / IMAGES_SUBPATH / "event-a.jpg").read_text() == "AAA"


def test_existing_target_images_are_kept(primary, tmp_path):
    """Mirroring is additive: an image this export dropped may still be
    referenced by a target page that has not been rebuilt."""
    target = _make_site(tmp_path / "beta", data={}, images=[("older.jpg", "OLD")])

    mirror_site_data(primary, [target])

    assert (target / IMAGES_SUBPATH / "older.jpg").read_text() == "OLD"
    assert (target / IMAGES_SUBPATH / "event-a.jpg").read_text() == "AAA"


def test_the_primary_is_skipped_when_passed_as_a_target(primary):
    assert mirror_site_data(primary, [primary]) == []


def test_a_missing_checkout_is_skipped_not_fatal(primary, tmp_path):
    """Not every machine has both repos; a scrape that already succeeded
    must not fail at the mirror step."""
    absent = tmp_path / "not-checked-out"

    assert mirror_site_data(primary, [absent]) == []
    assert not absent.exists()


def test_dry_run_writes_nothing(primary, tmp_path):
    target = _make_site(
        tmp_path / "beta",
        data={"opportunities.json": json.dumps([{"title": "Stale"}])},
    )

    assert mirror_site_data(primary, [target], dry_run=True) == [target.resolve()]

    assert json.loads((target / "src" / "data" / "opportunities.json").read_text()) == [
        {"title": "Stale"}
    ]


def test_several_targets_all_receive_the_export(primary, tmp_path):
    targets = [_make_site(tmp_path / f"site-{i}", data={}) for i in range(3)]

    assert mirror_site_data(primary, targets) == [t.resolve() for t in targets]

    for target in targets:
        assert json.loads((target / "src" / "data" / "opportunities.json").read_text()) == [
            {"title": "Fresh"}
        ]
