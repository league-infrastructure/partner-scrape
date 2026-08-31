"""`mirror_site_data` keeps extra site checkouts in step with an export."""

from __future__ import annotations

import json

import pytest

from partner_scrape.export.mirror import (
    IMAGES_SUBPATH,
    MIRRORED_DATA_FILES,
    PUBLIC_DATA_SUBPATH,
    mirror_site_data,
)


def _make_site(root, *, data: dict[str, str] | None = None, images=(), public_data=None):
    """Build a minimal site checkout: src/data plus opportunity images
    and (sprint 009, ticket 005) an optional public/data/ tree.

    ``public_data`` maps a path *relative to* `public/data/` (e.g.
    ``"partners.json"`` or ``"partners/coastal_roots_farm/events.json"``)
    to its text content, mirroring how `publish.project()` actually lays
    the tree out.
    """
    data_dir = root / "src" / "data"
    data_dir.mkdir(parents=True)
    for name, body in (data or {}).items():
        (data_dir / name).write_text(body)
    if images:
        image_dir = root / IMAGES_SUBPATH
        image_dir.mkdir(parents=True)
        for name, body in images:
            (image_dir / name).write_text(body)
    if public_data:
        public_data_dir = root / PUBLIC_DATA_SUBPATH
        for relative_name, body in public_data.items():
            path = public_data_dir / relative_name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body)
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
        public_data={
            "partners.json": json.dumps({"partners": [{"slug": "coastal-roots-farm"}]}),
            "partners/coastal-roots-farm/events.json": json.dumps({"events": []}),
            "partners/coastal-roots-farm/past-events.json": json.dumps({"events": []}),
        },
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

    Sprint 009 (ticket 005): `publish.project()` also writes a
    *generated* `public/data/partners.json` -- a different file, at a
    different path, with the identical basename. This is the regression
    test that the two are never confused: the curated `src/data/`
    roster stays exactly as the target had it, while the generated
    `public/data/` one is mirrored from the primary normally, right
    alongside it.
    """
    target = _make_site(
        tmp_path / "beta",
        data={"partners.json": json.dumps(["beta roster"])},
    )

    mirror_site_data(primary, [target])

    assert json.loads((target / "src" / "data" / "partners.json").read_text()) == [
        "beta roster"
    ]
    assert json.loads((target / PUBLIC_DATA_SUBPATH / "partners.json").read_text()) == {
        "partners": [{"slug": "coastal-roots-farm"}]
    }


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


# ---------------------------------------------------------------------
# Sprint 009 (ticket 005): recursively mirroring publish.project()'s
# public/data/ tree, alongside the existing flat-file/image copies.
# ---------------------------------------------------------------------


def test_public_data_tree_reaches_a_target_with_no_existing_tree(primary, tmp_path):
    target = _make_site(tmp_path / "beta", data={})

    mirror_site_data(primary, [target])

    assert json.loads((target / PUBLIC_DATA_SUBPATH / "partners.json").read_text()) == {
        "partners": [{"slug": "coastal-roots-farm"}]
    }
    assert json.loads(
        (
            target
            / PUBLIC_DATA_SUBPATH
            / "partners"
            / "coastal-roots-farm"
            / "events.json"
        ).read_text()
    ) == {"events": []}
    assert json.loads(
        (
            target
            / PUBLIC_DATA_SUBPATH
            / "partners"
            / "coastal-roots-farm"
            / "past-events.json"
        ).read_text()
    ) == {"events": []}


def test_public_data_byte_identical_file_is_not_rewritten(primary, tmp_path):
    """Same size/mtime skip check `_mirror_images` already uses,
    generalized to the recursive tree copy."""
    target = _make_site(tmp_path / "beta", data={})
    target_file = target / PUBLIC_DATA_SUBPATH / "partners.json"
    target_file.parent.mkdir(parents=True)
    source_text = (primary / PUBLIC_DATA_SUBPATH / "partners.json").read_text()
    # Same length as the primary's file, different content -- proves the
    # skip check is genuinely size-based and the target file is left
    # completely untouched rather than merely "ending up equal".
    stand_in = "x" * len(source_text)
    assert stand_in != source_text
    target_file.write_text(stand_in)

    mirror_site_data(primary, [target])

    assert target_file.read_text() == stand_in


def test_stale_public_data_partner_directory_is_kept(primary, tmp_path):
    """Additive, matching `_mirror_images`'s existing precedent: a
    target checkout that has not rebuilt yet may still be serving a
    partner page this run's projection no longer produces (e.g. a
    partner dropped from the curated roster) -- deleting that directory
    would break the page for a savings of only disk space."""
    target = _make_site(
        tmp_path / "beta",
        data={},
        public_data={"partners/dropped-partner/events.json": json.dumps({"events": ["stale"]})},
    )

    mirror_site_data(primary, [target])

    assert json.loads(
        (target / PUBLIC_DATA_SUBPATH / "partners" / "dropped-partner" / "events.json").read_text()
    ) == {"events": ["stale"]}
    # And the fresh tree still landed alongside it.
    assert (target / PUBLIC_DATA_SUBPATH / "partners.json").exists()


def test_a_missing_checkout_skips_the_public_data_tree_too(primary, tmp_path):
    absent = tmp_path / "not-checked-out"

    assert mirror_site_data(primary, [absent]) == []
    assert not absent.exists()


def test_a_target_missing_src_data_does_not_receive_the_public_data_tree(primary, tmp_path):
    """A target missing src/data/ entirely is still skipped with a
    warning, unchanged from today's existing behavior -- the public/data/
    copy is not attempted for it (introduces no new failure mode)."""
    no_src_data = tmp_path / "beta"
    no_src_data.mkdir()

    assert mirror_site_data(primary, [no_src_data]) == []
    assert not (no_src_data / PUBLIC_DATA_SUBPATH).exists()


def test_missing_primary_public_data_tree_is_not_an_error(tmp_path):
    """The primary has not run publish.project() yet (no public/data/ at
    all) -- the flat-file/image mirror must still succeed."""
    primary_without_publish = _make_site(
        tmp_path / "stem-ecosystem",
        data={"opportunities.json": json.dumps([{"title": "Fresh"}])},
    )
    target = _make_site(tmp_path / "beta", data={})

    assert mirror_site_data(primary_without_publish, [target]) == [target.resolve()]
    assert not (target / PUBLIC_DATA_SUBPATH).exists()
    assert json.loads((target / "src" / "data" / "opportunities.json").read_text()) == [
        {"title": "Fresh"}
    ]


def test_dry_run_writes_nothing_for_the_public_data_tree(primary, tmp_path):
    target = _make_site(tmp_path / "beta", data={})

    assert mirror_site_data(primary, [target], dry_run=True) == [target.resolve()]

    assert not (target / PUBLIC_DATA_SUBPATH).exists()


def test_several_targets_all_receive_the_public_data_tree(primary, tmp_path):
    targets = [_make_site(tmp_path / f"site-{i}", data={}) for i in range(3)]

    mirror_site_data(primary, targets)

    for target in targets:
        assert (target / PUBLIC_DATA_SUBPATH / "partners.json").exists()


# ---------------------------------------------------------------------
# Sprint 011 (ticket 002): teams.json joins MIRRORED_DATA_FILES,
# reusing the exact same flat-file copy mechanism as opportunities.json/
# scrape-meta.json/ads.json -- no new copy logic to test, just that the
# allowlist entry is present and honored.
# ---------------------------------------------------------------------


def test_mirrored_data_files_includes_teams_json():
    assert "teams.json" in MIRRORED_DATA_FILES


def test_teams_json_reaches_the_target_when_present(tmp_path):
    primary = _make_site(
        tmp_path / "stem-ecosystem",
        data={"teams.json": json.dumps({"meta": {"total": 1}, "teams": [{"team_id": "ftc-1"}]})},
    )
    target = _make_site(tmp_path / "beta", data={})

    mirror_site_data(primary, [target])

    mirrored = json.loads((target / "src" / "data" / "teams.json").read_text())
    assert mirrored == {"meta": {"total": 1}, "teams": [{"team_id": "ftc-1"}]}


def test_a_missing_teams_json_on_the_primary_is_not_an_error(tmp_path):
    """Mirrors `ads.json`'s existing precedent: a source file that
    simply doesn't exist yet (no `teams` run has ever happened in this
    checkout) is skipped, not fatal -- the rest of the mirror still
    succeeds."""
    primary = _make_site(tmp_path / "stem-ecosystem", data={})
    target = _make_site(tmp_path / "beta", data={})

    assert mirror_site_data(primary, [target]) == [target.resolve()]
    assert not (target / "src" / "data" / "teams.json").exists()


def test_teams_json_is_not_written_under_dry_run(tmp_path):
    primary = _make_site(
        tmp_path / "stem-ecosystem",
        data={"teams.json": json.dumps({"meta": {"total": 0}, "teams": []})},
    )
    target = _make_site(tmp_path / "beta", data={})

    mirror_site_data(primary, [target], dry_run=True)

    assert not (target / "src" / "data" / "teams.json").exists()


# ---------------------------------------------------------------------
# Sprint 018 (ticket 007): places.json joins MIRRORED_DATA_FILES,
# reusing the exact same flat-file copy mechanism as
# opportunities.json/scrape-meta.json/ads.json/teams.json -- no new
# copy logic to test, just that the allowlist entry is present and
# honored.
# ---------------------------------------------------------------------


def test_mirrored_data_files_includes_places_json():
    assert "places.json" in MIRRORED_DATA_FILES


def test_places_json_reaches_the_target_when_present(tmp_path):
    primary = _make_site(
        tmp_path / "stem-ecosystem",
        data={
            "places.json": json.dumps(
                {"meta": {"total": 1}, "places": [{"place_id": "sdpl-idea-lab-central"}]}
            )
        },
    )
    target = _make_site(tmp_path / "beta", data={})

    mirror_site_data(primary, [target])

    mirrored = json.loads((target / "src" / "data" / "places.json").read_text())
    assert mirrored == {"meta": {"total": 1}, "places": [{"place_id": "sdpl-idea-lab-central"}]}


def test_a_missing_places_json_on_the_primary_is_not_an_error(tmp_path):
    """Mirrors `teams.json`'s existing precedent: a source file that
    simply doesn't exist yet (no `directory` run has ever happened in
    this checkout) is skipped, not fatal -- the rest of the mirror
    still succeeds."""
    primary = _make_site(tmp_path / "stem-ecosystem", data={})
    target = _make_site(tmp_path / "beta", data={})

    assert mirror_site_data(primary, [target]) == [target.resolve()]
    assert not (target / "src" / "data" / "places.json").exists()


def test_places_json_is_not_written_under_dry_run(tmp_path):
    primary = _make_site(
        tmp_path / "stem-ecosystem",
        data={"places.json": json.dumps({"meta": {"total": 0}, "places": []})},
    )
    target = _make_site(tmp_path / "beta", data={})

    mirror_site_data(primary, [target], dry_run=True)

    assert not (target / "src" / "data" / "places.json").exists()


# ---------------------------------------------------------------------
# Sprint 018 (ticket 008): clubs.json joins MIRRORED_DATA_FILES too,
# reusing the exact same flat-file copy mechanism -- no new copy logic
# to test, just that the allowlist entry is present and honored.
# Mirrors places.json's own test shape immediately above exactly.
# ---------------------------------------------------------------------


def test_mirrored_data_files_includes_clubs_json():
    assert "clubs.json" in MIRRORED_DATA_FILES


def test_clubs_json_reaches_the_target_when_present(tmp_path):
    primary = _make_site(
        tmp_path / "stem-ecosystem",
        data={
            "clubs.json": json.dumps(
                {"meta": {"total": 1}, "clubs": [{"club_id": "hack-club-university-city-high"}]}
            )
        },
    )
    target = _make_site(tmp_path / "beta", data={})

    mirror_site_data(primary, [target])

    mirrored = json.loads((target / "src" / "data" / "clubs.json").read_text())
    assert mirrored == {
        "meta": {"total": 1},
        "clubs": [{"club_id": "hack-club-university-city-high"}],
    }


def test_a_missing_clubs_json_on_the_primary_is_not_an_error(tmp_path):
    """Mirrors `places.json`'s existing precedent: a source file that
    simply doesn't exist yet (no `directory` run has ever happened in
    this checkout) is skipped, not fatal -- the rest of the mirror
    still succeeds."""
    primary = _make_site(tmp_path / "stem-ecosystem", data={})
    target = _make_site(tmp_path / "beta", data={})

    assert mirror_site_data(primary, [target]) == [target.resolve()]
    assert not (target / "src" / "data" / "clubs.json").exists()


def test_clubs_json_is_not_written_under_dry_run(tmp_path):
    primary = _make_site(
        tmp_path / "stem-ecosystem",
        data={"clubs.json": json.dumps({"meta": {"total": 0}, "clubs": []})},
    )
    target = _make_site(tmp_path / "beta", data={})

    mirror_site_data(primary, [target], dry_run=True)

    assert not (target / "src" / "data" / "clubs.json").exists()
