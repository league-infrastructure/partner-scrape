"""Tests for partner_scrape.directory.export: the places.json/clubs.json
publish step.

Sprint 020 ticket 006 adds a third, similarly-defaulting `own_data_dir`
parameter to `export_directory()`. Every test written before that
ticket predates the parameter and never passes it explicitly -- the
module-level `_own_data_dir_default` autouse fixture below pins its
default resolution to a throwaway directory for every test in this
file, so none of them can reach this repo's real `data/` directory
(mirrors `tests/teams/test_export.py`'s identical
`_own_data_dir_default` fixture for `export_teams()`, sprint 020 ticket
005).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from partner_scrape.directory import export
from partner_scrape.directory.export import (
    CLUBS_SCHEMA_FIELDS,
    PLACES_SCHEMA_FIELDS,
    club_to_json_dict,
    export_directory,
    to_json_dict,
)
from partner_scrape.directory.model import Club, Place


@pytest.fixture(autouse=True)
def _own_data_dir_default(tmp_path_factory, monkeypatch):
    """Pin `export.get_own_data_dir()`'s resolution to a throwaway
    directory for every test in this file (sprint 020 ticket 006).

    `own_data_dir` (like `site_dir`) resolves via a `config` accessor
    when omitted, but unlike `site_dir` it has no environment-variable
    override -- `config.get_own_data_dir()` always returns this repo's
    real `data/` directory (`DEFAULT_OWN_DATA_DIR` is "not overridable
    via environment variable" by design). Every test written before
    this ticket predates the `own_data_dir` parameter and so never
    passes it explicitly; without this fixture, each such test's
    non-`dry_run` call would auto-create and write real files into
    this repo's actual `data/` directory on every test run --
    contradicting sprint.md's Test Strategy ("Hermetic throughout ...
    tests pass an explicit tmp_path, never the real default").

    Deliberately resolved via `tmp_path_factory` (a directory outside
    the current test's own `tmp_path` tree), not `tmp_path` itself --
    matches `tests/teams/test_export.py`'s own reasoning: a test
    asserting the exact set of files written under `tmp_path` must not
    have this default land inside that tree.
    """
    fake_own_data_dir = tmp_path_factory.mktemp("own-data-default")
    monkeypatch.setattr(export, "get_own_data_dir", lambda: fake_own_data_dir)


def _make_place(**overrides) -> Place:
    defaults = dict(
        place_id="sdpl-idea-lab-central",
        name="IDEA Lab at San Diego Central Library",
        category="makerspace",
        latitude=32.7089,
        longitude=-117.1542,
        location_precision="address",
        matched_name="IDEA Lab at San Diego Central Library",
        sources=["static_roster"],
    )
    defaults.update(overrides)
    return Place(**defaults)


def _make_club(**overrides) -> Club:
    defaults = dict(
        club_id="hack-club-university-city-high",
        name="Hack Club at University City High School",
        club_type="hack-club",
        host_school="University City High School",
        city="San Diego",
        latitude=32.861197,
        longitude=-117.20954,
        location_precision="school",
        matched_name="University City High",
        sources=["hack_club_static_roster"],
    )
    defaults.update(overrides)
    return Club(**defaults)


def _make_site(root: Path, *, opportunities="[]", scrape_meta="{}", teams="{}") -> Path:
    data_dir = root / "src" / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "opportunities.json").write_text(opportunities)
    (data_dir / "scrape-meta.json").write_text(scrape_meta)
    (data_dir / "teams.json").write_text(teams)
    return root


class TestSchemaFieldSet:
    def test_sources_is_dropped_as_bookkeeping(self):
        assert "sources" not in PLACES_SCHEMA_FIELDS

    def test_every_other_place_field_is_present(self):
        from dataclasses import fields

        expected = {f.name for f in fields(Place) if f.name != "sources"}
        assert set(PLACES_SCHEMA_FIELDS) == expected

    def test_to_json_dict_projects_exactly_the_schema_fields(self):
        place = _make_place()
        result = to_json_dict(place)

        assert set(result.keys()) == set(PLACES_SCHEMA_FIELDS)
        assert "sources" not in result
        assert result["place_id"] == "sdpl-idea-lab-central"


class TestPayloadShape:
    def test_payload_has_meta_and_places_keys(self):
        payload = export_directory([_make_place()])

        assert set(payload.keys()) == {"meta", "places"}
        assert isinstance(payload["places"], list)
        assert len(payload["places"]) == 1

    def test_meta_carries_generated_total_by_category_and_by_location_precision(self):
        places = [
            _make_place(place_id="a", name="A", category="makerspace"),
            _make_place(place_id="b", name="B", category="makerspace", location_precision="zip"),
            _make_place(place_id="c", name="C", category="observatory"),
        ]

        payload = export_directory(places)
        meta = payload["meta"]

        assert meta["total"] == 3
        assert meta["by_category"] == {"makerspace": 2, "observatory": 1}
        assert meta["by_location_precision"] == {"address": 2, "zip": 1}
        assert meta["generated"]

    def test_places_sorted_by_category_then_name(self):
        places = [
            _make_place(place_id="z", name="Zebra Place", category="observatory"),
            _make_place(place_id="a", name="Apple Place", category="makerspace"),
            _make_place(place_id="b", name="Banana Place", category="makerspace"),
        ]

        payload = export_directory(places)
        ordered_ids = [p["place_id"] for p in payload["places"]]

        assert ordered_ids == ["a", "b", "z"]

    def test_places_are_written_to_disk_at_the_documented_path(self, tmp_path):
        # Sprint 025 ticket 005: own_data_dir is now the documented path
        # -- export_directory() no longer writes anywhere under a
        # site_dir.
        own_data_dir = tmp_path / "own-data"

        export_directory([_make_place()], own_data_dir=own_data_dir)

        written = json.loads((own_data_dir / "places.json").read_text())
        assert written["meta"]["total"] == 1
        assert written["places"][0]["place_id"] == "sdpl-idea-lab-central"


class TestDryRun:
    def test_dry_run_computes_the_payload_without_writing(self, tmp_path):
        # Sprint 025 ticket 005: own_data_dir is export_directory()'s
        # only write target now -- this both computes the payload
        # without touching disk and confirms a not-yet-existing target
        # directory is never created under dry_run.
        own_data_dir = tmp_path / "does-not-exist-yet"

        payload = export_directory([_make_place()], own_data_dir=own_data_dir, dry_run=True)

        assert payload["meta"]["total"] == 1
        assert not own_data_dir.exists()


class TestHardInvariants:
    """A `directory` run never writes or touches
    `opportunities.json`/`scrape-meta.json`/`teams.json` -- those are
    `export/writer.py`'s and `teams/export.py`'s exclusive outputs.

    Sprint 025 ticket 005: `export_directory()` no longer accepts a
    `site_dir` at all, so `site`/`tmp_path` below are just ordinary
    directories this call is never even told about -- the strongest
    possible version of "never touches" these files, now structural
    rather than merely tested.
    """

    def test_opportunities_scrape_meta_and_teams_are_byte_identical_after_a_directory_run(
        self, tmp_path
    ):
        opportunities_body = json.dumps([{"title": "Untouched Opportunity"}])
        scrape_meta_body = json.dumps({"last_updated": "2026-01-01T00:00:00Z"})
        teams_body = json.dumps({"meta": {"total": 1}, "teams": []})
        site = _make_site(
            tmp_path,
            opportunities=opportunities_body,
            scrape_meta=scrape_meta_body,
            teams=teams_body,
        )

        export_directory([_make_place()])

        data_dir = site / "src" / "data"
        assert (data_dir / "opportunities.json").read_text() == opportunities_body
        assert (data_dir / "scrape-meta.json").read_text() == scrape_meta_body
        assert (data_dir / "teams.json").read_text() == teams_body

    def test_no_places_json_is_written_under_the_unrelated_site_tree(self, tmp_path):
        # Sprint 025 ticket 005: inverted from this test's pre-ticket
        # form (which asserted places.json *was* written under
        # {site_dir}/src/data/) now that export_directory() has no
        # awareness of site_dir at all -- an ordinary, unrelated
        # directory is never written into.
        data_dir = tmp_path / "src" / "data"
        data_dir.mkdir(parents=True)

        export_directory([_make_place()])

        assert not (data_dir / "opportunities.json").exists()
        assert not (data_dir / "scrape-meta.json").exists()
        assert not (data_dir / "teams.json").exists()
        assert not (data_dir / "places.json").exists()


# ---------------------------------------------------------------------
# Sprint 018 (ticket 008): clubs.json, published from the `clubs`
# keyword argument. Mirrors every places.json test class above, plus a
# few tests specific to the "clubs defaults to None" backward-
# compatibility contract itself.
# ---------------------------------------------------------------------


class TestClubsSchemaFieldSet:
    def test_sources_is_dropped_as_bookkeeping(self):
        assert "sources" not in CLUBS_SCHEMA_FIELDS

    def test_every_other_club_field_is_present(self):
        from dataclasses import fields

        expected = {f.name for f in fields(Club) if f.name != "sources"}
        assert set(CLUBS_SCHEMA_FIELDS) == expected

    def test_club_to_json_dict_projects_exactly_the_schema_fields(self):
        club = _make_club()
        result = club_to_json_dict(club)

        assert set(result.keys()) == set(CLUBS_SCHEMA_FIELDS)
        assert "sources" not in result
        assert result["club_id"] == "hack-club-university-city-high"


class TestClubsDefaultToNoneMeansNoClubsJsonAtAll:
    """Backward compatibility with every ticket-007 call site: omitting
    `clubs` (the default) must never write clubs.json, and must never
    add clubs_meta/clubs to the returned payload -- exactly ticket
    007's own pre-ticket-008 behavior."""

    def test_no_clubs_json_is_written_when_clubs_is_omitted(self, tmp_path):
        own_data_dir = tmp_path / "own-data"

        export_directory([_make_place()], own_data_dir=own_data_dir)

        assert not (own_data_dir / "clubs.json").exists()

    def test_payload_has_no_clubs_keys_when_clubs_is_omitted(self):
        payload = export_directory([_make_place()])

        assert "clubs" not in payload
        assert "clubs_meta" not in payload
        assert set(payload.keys()) == {"meta", "places"}

    def test_an_explicit_empty_club_list_does_write_clubs_json(self, tmp_path):
        # Distinct from omitting `clubs` entirely -- a real (if empty)
        # acquisition result is a legitimate "clubs pipeline ran and
        # found nothing", not "clubs pipeline was never asked to run".
        own_data_dir = tmp_path / "own-data"

        export_directory([_make_place()], clubs=[], own_data_dir=own_data_dir)

        assert (own_data_dir / "clubs.json").exists()
        written = json.loads((own_data_dir / "clubs.json").read_text())
        assert written == {
            "meta": written["meta"],
            "clubs": [],
        }
        assert written["meta"]["total"] == 0


class TestClubsPayloadShape:
    def test_payload_carries_clubs_meta_and_clubs_keys_without_disturbing_places_keys(self):
        payload = export_directory([_make_place()], clubs=[_make_club()])

        assert set(payload.keys()) == {"meta", "places", "clubs_meta", "clubs"}
        assert payload["meta"]["total"] == 1
        assert len(payload["places"]) == 1
        assert payload["clubs_meta"]["total"] == 1
        assert len(payload["clubs"]) == 1

    def test_clubs_meta_carries_generated_total_by_club_type_and_by_location_precision(self):
        clubs = [
            _make_club(club_id="a", name="A", club_type="hack-club"),
            _make_club(
                club_id="b", name="B", club_type="hack-club", location_precision="zip"
            ),
        ]

        payload = export_directory([_make_place()], clubs=clubs)
        meta = payload["clubs_meta"]

        assert meta["total"] == 2
        assert meta["by_club_type"] == {"hack-club": 2}
        assert meta["by_location_precision"] == {"school": 1, "zip": 1}
        assert meta["generated"]

    def test_clubs_sorted_by_club_type_then_name(self):
        clubs = [
            _make_club(club_id="z", name="Zebra Club"),
            _make_club(club_id="a", name="Apple Club"),
            _make_club(club_id="b", name="Banana Club"),
        ]

        payload = export_directory([_make_place()], clubs=clubs)
        ordered_ids = [c["club_id"] for c in payload["clubs"]]

        assert ordered_ids == ["a", "b", "z"]

    def test_clubs_are_written_to_disk_at_the_documented_path(self, tmp_path):
        own_data_dir = tmp_path / "own-data"

        export_directory([_make_place()], clubs=[_make_club()], own_data_dir=own_data_dir)

        written = json.loads((own_data_dir / "clubs.json").read_text())
        assert written["meta"]["total"] == 1
        assert written["clubs"][0]["club_id"] == "hack-club-university-city-high"

    def test_clubs_json_is_a_genuinely_separate_document_from_places_json(self, tmp_path):
        # clubs.json must never carry a places.json-shaped payload (or
        # vice versa) -- each is independently self-describing.
        own_data_dir = tmp_path / "own-data"

        export_directory([_make_place()], clubs=[_make_club()], own_data_dir=own_data_dir)

        places_written = json.loads((own_data_dir / "places.json").read_text())
        clubs_written = json.loads((own_data_dir / "clubs.json").read_text())

        assert set(places_written.keys()) == {"meta", "places"}
        assert set(clubs_written.keys()) == {"meta", "clubs"}


class TestClubsDryRun:
    def test_dry_run_computes_the_clubs_payload_without_writing(self, tmp_path):
        own_data_dir = tmp_path / "own-data"

        payload = export_directory(
            [_make_place()], clubs=[_make_club()], own_data_dir=own_data_dir, dry_run=True
        )

        assert payload["clubs_meta"]["total"] == 1
        assert not own_data_dir.exists()


class TestClubsHardInvariants:
    """A `directory` run with clubs still never writes or touches
    `opportunities.json`/`scrape-meta.json`/`teams.json` -- same
    invariant as TestHardInvariants above, re-checked with `clubs`
    populated this time."""

    def test_opportunities_scrape_meta_and_teams_are_byte_identical_with_clubs_present(
        self, tmp_path
    ):
        opportunities_body = json.dumps([{"title": "Untouched Opportunity"}])
        scrape_meta_body = json.dumps({"last_updated": "2026-01-01T00:00:00Z"})
        teams_body = json.dumps({"meta": {"total": 1}, "teams": []})
        site = _make_site(
            tmp_path,
            opportunities=opportunities_body,
            scrape_meta=scrape_meta_body,
            teams=teams_body,
        )

        export_directory([_make_place()], clubs=[_make_club()])

        data_dir = site / "src" / "data"
        assert (data_dir / "opportunities.json").read_text() == opportunities_body
        assert (data_dir / "scrape-meta.json").read_text() == scrape_meta_body
        assert (data_dir / "teams.json").read_text() == teams_body


# ---------------------------------------------------------------------
# Sprint 020 (ticket 006, issue 60): own_data_dir, into partner-scrape's
# own `data/` directory via `config.get_own_data_dir()` -- since sprint
# 025 ticket 005 removed the two `stem-ecosystem`-checkout writes,
# export_directory()'s only write target for both places.json and
# clubs.json. Mirrors `tests/teams/test_export.py`'s
# `TestOwnDataDirPublish` structure and naming conventions, scoped to
# `places.json`/`clubs.json` (and their "places.json before clubs.json"
# ordering dimension).
# ---------------------------------------------------------------------


class TestOwnDataDirPublish:
    def test_writes_only_under_the_given_own_data_dir(self, tmp_path):
        # Sprint 025 ticket 005: inverted from this test's pre-ticket
        # form (which also asserted src/data and public/data copies
        # under a site_dir) -- export_directory() no longer accepts or
        # writes to a site_dir at all, so the pre-existing site tree
        # below (from _make_site()) is left completely untouched;
        # own_data_dir/places.json and own_data_dir/clubs.json are the
        # only files this call writes anywhere under tmp_path.
        site = _make_site(tmp_path)
        own_data_dir = tmp_path / "own-data"

        export_directory([_make_place()], clubs=[_make_club()], own_data_dir=own_data_dir)

        written_files = sorted(p for p in tmp_path.rglob("*") if p.is_file())
        assert written_files == sorted(
            [
                site / "src" / "data" / "opportunities.json",
                site / "src" / "data" / "scrape-meta.json",
                site / "src" / "data" / "teams.json",
                own_data_dir / "places.json",
                own_data_dir / "clubs.json",
            ]
        )

    def test_omitted_own_data_dir_resolves_via_config_get_own_data_dir(
        self, tmp_path, monkeypatch
    ):
        fake_own_data_dir = tmp_path / "fake-own-data"
        monkeypatch.setattr(export, "get_own_data_dir", lambda: fake_own_data_dir)

        export_directory([_make_place()])

        assert (fake_own_data_dir / "places.json").exists()

    def test_missing_own_data_dir_is_created_automatically_never_raises(self, tmp_path):
        own_data_dir = tmp_path / "does-not-exist-yet" / "nested"
        assert not own_data_dir.exists()

        export_directory([_make_place()], own_data_dir=own_data_dir)

        assert (own_data_dir / "places.json").exists()

    def test_dry_run_writes_nothing_to_own_data_dir(self, tmp_path):
        own_data_dir = tmp_path / "own-data"

        payload = export_directory(
            [_make_place()],
            clubs=[_make_club()],
            own_data_dir=own_data_dir,
            dry_run=True,
        )

        assert payload["meta"]["total"] == 1
        assert payload["clubs_meta"]["total"] == 1
        assert not own_data_dir.exists()

    def test_clubs_none_means_clubs_json_untouched_at_own_data_dir(self, tmp_path):
        # Extends the ticket-007-era "clubs=None means no clubs.json
        # at all" contract to own_data_dir, the sole remaining target.
        own_data_dir = tmp_path / "own-data"

        export_directory([_make_place()], own_data_dir=own_data_dir)

        assert (own_data_dir / "places.json").exists()
        assert not (own_data_dir / "clubs.json").exists()

    def test_an_explicit_empty_club_list_does_write_clubs_json_to_own_data_dir_too(
        self, tmp_path
    ):
        own_data_dir = tmp_path / "own-data"

        export_directory([_make_place()], clubs=[], own_data_dir=own_data_dir)

        written = json.loads((own_data_dir / "clubs.json").read_text())
        assert written["meta"]["total"] == 0

    def test_places_own_data_dir_failure_raises_before_clubs_is_attempted(self, tmp_path):
        # "places.json before clubs.json" ordering, now expressed over
        # the single remaining target: own_data_dir is pre-occupied by
        # a plain file (not a directory), so places.json's write fails
        # -- and clubs.json must never be attempted at all.
        own_data_dir = tmp_path / "own-data"
        own_data_dir.write_text("not a directory")

        with pytest.raises(RuntimeError, match="Cannot write places export"):
            export_directory([_make_place()], clubs=[_make_club()], own_data_dir=own_data_dir)

    def test_clubs_own_data_dir_failure_raises_after_places_already_written(self, tmp_path):
        # The mirrored ordering contract on the clubs.json side:
        # clubs.json's own write is only attempted once places.json's
        # own write has already succeeded. Here own_data_dir/clubs.json
        # is pre-occupied by a directory (not a plain file), so only
        # that specific write fails -- proven by places.json already
        # existing at own_data_dir by the time the RuntimeError is
        # raised.
        own_data_dir = tmp_path / "own-data"
        own_data_dir.mkdir()
        (own_data_dir / "clubs.json").mkdir()

        with pytest.raises(RuntimeError, match="Cannot write clubs export"):
            export_directory([_make_place()], clubs=[_make_club()], own_data_dir=own_data_dir)

        assert (own_data_dir / "places.json").exists()
