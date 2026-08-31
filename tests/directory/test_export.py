"""Tests for partner_scrape.directory.export: the places.json/clubs.json
publish step.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from partner_scrape.directory.export import (
    CLUBS_SCHEMA_FIELDS,
    PLACES_SCHEMA_FIELDS,
    club_to_json_dict,
    export_directory,
    to_json_dict,
)
from partner_scrape.directory.model import Club, Place


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
    def test_payload_has_meta_and_places_keys(self, tmp_path):
        site = _make_site(tmp_path)

        payload = export_directory([_make_place()], site_dir=site)

        assert set(payload.keys()) == {"meta", "places"}
        assert isinstance(payload["places"], list)
        assert len(payload["places"]) == 1

    def test_meta_carries_generated_total_by_category_and_by_location_precision(self, tmp_path):
        site = _make_site(tmp_path)
        places = [
            _make_place(place_id="a", name="A", category="makerspace"),
            _make_place(place_id="b", name="B", category="makerspace", location_precision="zip"),
            _make_place(place_id="c", name="C", category="observatory"),
        ]

        payload = export_directory(places, site_dir=site)
        meta = payload["meta"]

        assert meta["total"] == 3
        assert meta["by_category"] == {"makerspace": 2, "observatory": 1}
        assert meta["by_location_precision"] == {"address": 2, "zip": 1}
        assert meta["generated"]

    def test_places_sorted_by_category_then_name(self, tmp_path):
        site = _make_site(tmp_path)
        places = [
            _make_place(place_id="z", name="Zebra Place", category="observatory"),
            _make_place(place_id="a", name="Apple Place", category="makerspace"),
            _make_place(place_id="b", name="Banana Place", category="makerspace"),
        ]

        payload = export_directory(places, site_dir=site)
        ordered_ids = [p["place_id"] for p in payload["places"]]

        assert ordered_ids == ["a", "b", "z"]

    def test_places_are_written_to_disk_at_the_documented_path(self, tmp_path):
        site = _make_site(tmp_path)

        export_directory([_make_place()], site_dir=site)

        written = json.loads((site / "src" / "data" / "places.json").read_text())
        assert written["meta"]["total"] == 1
        assert written["places"][0]["place_id"] == "sdpl-idea-lab-central"


class TestDryRun:
    def test_dry_run_computes_the_payload_without_writing(self, tmp_path):
        site = _make_site(tmp_path)

        payload = export_directory([_make_place()], site_dir=site, dry_run=True)

        assert payload["meta"]["total"] == 1
        assert not (site / "src" / "data" / "places.json").exists()
        assert not (site / "public" / "data" / "places.json").exists()

    def test_dry_run_never_touches_a_nonexistent_site_dir(self, tmp_path):
        absent = tmp_path / "not-checked-out"

        payload = export_directory([_make_place()], site_dir=absent, dry_run=True)

        assert payload["meta"]["total"] == 1
        assert not absent.exists()


class TestUnwritableSiteDirFailsLoudly:
    def test_missing_src_data_raises_runtime_error(self, tmp_path):
        site = tmp_path / "no-data-dir"
        site.mkdir()

        with pytest.raises(RuntimeError, match="Cannot write places export"):
            export_directory([_make_place()], site_dir=site)


class TestPublicDataPublish:
    def test_public_data_places_json_is_byte_identical_to_src_data(self, tmp_path):
        site = _make_site(tmp_path)

        export_directory([_make_place()], site_dir=site)

        src_text = (site / "src" / "data" / "places.json").read_text()
        public_text = (site / "public" / "data" / "places.json").read_text()
        assert public_text == src_text
        assert json.loads(public_text) == json.loads(src_text)

    def test_public_data_directory_is_created_when_absent(self, tmp_path):
        site = _make_site(tmp_path)
        assert not (site / "public").exists()

        export_directory([_make_place()], site_dir=site)

        public_places_path = site / "public" / "data" / "places.json"
        assert public_places_path.exists()

    def test_public_data_directory_is_reused_when_already_present(self, tmp_path):
        site = _make_site(tmp_path)
        existing_public_data = site / "public" / "data"
        existing_public_data.mkdir(parents=True)
        (existing_public_data / "teams.json").write_text("{}")

        export_directory([_make_place()], site_dir=site)

        # The existing sibling file is left alone -- this write only
        # ever adds places.json.
        assert (existing_public_data / "teams.json").read_text() == "{}"
        assert (existing_public_data / "places.json").exists()

    def test_unwritable_public_data_path_raises_runtime_error(self, tmp_path):
        site = _make_site(tmp_path)
        public_dir = site / "public"
        public_dir.mkdir()
        (public_dir / "data").write_text("not a directory")

        with pytest.raises(RuntimeError, match="Cannot write places export"):
            export_directory([_make_place()], site_dir=site)

    def test_src_data_failure_is_raised_before_public_data_is_touched(self, tmp_path):
        site = tmp_path / "no-data-dir"
        site.mkdir()

        with pytest.raises(RuntimeError, match="Cannot write places export"):
            export_directory([_make_place()], site_dir=site)

        assert not (site / "public").exists()


class TestHardInvariants:
    """A `directory` run never writes or touches
    `opportunities.json`/`scrape-meta.json`/`teams.json` -- those are
    `export/writer.py`'s and `teams/export.py`'s exclusive outputs."""

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

        export_directory([_make_place()], site_dir=site)

        data_dir = site / "src" / "data"
        assert (data_dir / "opportunities.json").read_text() == opportunities_body
        assert (data_dir / "scrape-meta.json").read_text() == scrape_meta_body
        assert (data_dir / "teams.json").read_text() == teams_body

    def test_no_such_file_is_created_when_absent(self, tmp_path):
        data_dir = tmp_path / "src" / "data"
        data_dir.mkdir(parents=True)

        export_directory([_make_place()], site_dir=tmp_path)

        assert not (data_dir / "opportunities.json").exists()
        assert not (data_dir / "scrape-meta.json").exists()
        assert not (data_dir / "teams.json").exists()
        assert (data_dir / "places.json").exists()


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
        site = _make_site(tmp_path)

        export_directory([_make_place()], site_dir=site)

        assert not (site / "src" / "data" / "clubs.json").exists()
        assert not (site / "public" / "data" / "clubs.json").exists()

    def test_payload_has_no_clubs_keys_when_clubs_is_omitted(self, tmp_path):
        site = _make_site(tmp_path)

        payload = export_directory([_make_place()], site_dir=site)

        assert "clubs" not in payload
        assert "clubs_meta" not in payload
        assert set(payload.keys()) == {"meta", "places"}

    def test_an_explicit_empty_club_list_does_write_clubs_json(self, tmp_path):
        # Distinct from omitting `clubs` entirely -- a real (if empty)
        # acquisition result is a legitimate "clubs pipeline ran and
        # found nothing", not "clubs pipeline was never asked to run".
        site = _make_site(tmp_path)

        export_directory([_make_place()], site_dir=site, clubs=[])

        assert (site / "src" / "data" / "clubs.json").exists()
        written = json.loads((site / "src" / "data" / "clubs.json").read_text())
        assert written == {
            "meta": written["meta"],
            "clubs": [],
        }
        assert written["meta"]["total"] == 0


class TestClubsPayloadShape:
    def test_payload_carries_clubs_meta_and_clubs_keys_without_disturbing_places_keys(
        self, tmp_path
    ):
        site = _make_site(tmp_path)

        payload = export_directory([_make_place()], site_dir=site, clubs=[_make_club()])

        assert set(payload.keys()) == {"meta", "places", "clubs_meta", "clubs"}
        assert payload["meta"]["total"] == 1
        assert len(payload["places"]) == 1
        assert payload["clubs_meta"]["total"] == 1
        assert len(payload["clubs"]) == 1

    def test_clubs_meta_carries_generated_total_by_club_type_and_by_location_precision(
        self, tmp_path
    ):
        site = _make_site(tmp_path)
        clubs = [
            _make_club(club_id="a", name="A", club_type="hack-club"),
            _make_club(
                club_id="b", name="B", club_type="hack-club", location_precision="zip"
            ),
        ]

        payload = export_directory([_make_place()], site_dir=site, clubs=clubs)
        meta = payload["clubs_meta"]

        assert meta["total"] == 2
        assert meta["by_club_type"] == {"hack-club": 2}
        assert meta["by_location_precision"] == {"school": 1, "zip": 1}
        assert meta["generated"]

    def test_clubs_sorted_by_club_type_then_name(self, tmp_path):
        site = _make_site(tmp_path)
        clubs = [
            _make_club(club_id="z", name="Zebra Club"),
            _make_club(club_id="a", name="Apple Club"),
            _make_club(club_id="b", name="Banana Club"),
        ]

        payload = export_directory([_make_place()], site_dir=site, clubs=clubs)
        ordered_ids = [c["club_id"] for c in payload["clubs"]]

        assert ordered_ids == ["a", "b", "z"]

    def test_clubs_are_written_to_disk_at_the_documented_path(self, tmp_path):
        site = _make_site(tmp_path)

        export_directory([_make_place()], site_dir=site, clubs=[_make_club()])

        written = json.loads((site / "src" / "data" / "clubs.json").read_text())
        assert written["meta"]["total"] == 1
        assert written["clubs"][0]["club_id"] == "hack-club-university-city-high"

    def test_clubs_json_is_a_genuinely_separate_document_from_places_json(self, tmp_path):
        # clubs.json must never carry a places.json-shaped payload (or
        # vice versa) -- each is independently self-describing.
        site = _make_site(tmp_path)

        export_directory([_make_place()], site_dir=site, clubs=[_make_club()])

        places_written = json.loads((site / "src" / "data" / "places.json").read_text())
        clubs_written = json.loads((site / "src" / "data" / "clubs.json").read_text())

        assert set(places_written.keys()) == {"meta", "places"}
        assert set(clubs_written.keys()) == {"meta", "clubs"}


class TestClubsDryRun:
    def test_dry_run_computes_the_clubs_payload_without_writing(self, tmp_path):
        site = _make_site(tmp_path)

        payload = export_directory(
            [_make_place()], site_dir=site, clubs=[_make_club()], dry_run=True
        )

        assert payload["clubs_meta"]["total"] == 1
        assert not (site / "src" / "data" / "clubs.json").exists()
        assert not (site / "public" / "data" / "clubs.json").exists()
        # Places stays untouched too, matching TestDryRun's own
        # existing places.json assertions.
        assert not (site / "src" / "data" / "places.json").exists()


class TestClubsUnwritableSiteDirFailsLoudly:
    def test_missing_src_data_raises_runtime_error_before_ever_reaching_clubs(self, tmp_path):
        site = tmp_path / "no-data-dir"
        site.mkdir()

        with pytest.raises(RuntimeError, match="Cannot write places export"):
            export_directory([_make_place()], site_dir=site, clubs=[_make_club()])

        # places.json's own failure raises before clubs.json is ever
        # attempted -- "places.json before clubs.json" ordering.
        assert not (site / "src" / "data" / "clubs.json").exists()

    def test_unwritable_public_data_path_for_clubs_raises_runtime_error(self, tmp_path):
        site = _make_site(tmp_path)
        public_dir = site / "public"
        public_dir.mkdir()
        (public_dir / "data").write_text("not a directory")

        with pytest.raises(RuntimeError, match="Cannot write"):
            export_directory([_make_place()], site_dir=site, clubs=[_make_club()])


class TestClubsPublicDataPublish:
    def test_public_data_clubs_json_is_byte_identical_to_src_data(self, tmp_path):
        site = _make_site(tmp_path)

        export_directory([_make_place()], site_dir=site, clubs=[_make_club()])

        src_text = (site / "src" / "data" / "clubs.json").read_text()
        public_text = (site / "public" / "data" / "clubs.json").read_text()
        assert public_text == src_text
        assert json.loads(public_text) == json.loads(src_text)


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

        export_directory([_make_place()], site_dir=site, clubs=[_make_club()])

        data_dir = site / "src" / "data"
        assert (data_dir / "opportunities.json").read_text() == opportunities_body
        assert (data_dir / "scrape-meta.json").read_text() == scrape_meta_body
        assert (data_dir / "teams.json").read_text() == teams_body
