"""Tests for partner_scrape.export.publish: the build-time projection of
the per-partner accumulation store into the published `public/data/`
tree (sprint 009 ticket 004, issue 15).

Every test passes an explicit `log_dir`/`partners_path`/`site_dir`
under `tmp_path` -- no test relies on `config.get_scrape_cache_dir()` /
`config.get_site_dir()`'s real defaults or writes to a real checkout,
matching `partner_log.py`'s and `writer.py`'s own test-file convention.

Fixtures are built by calling the *real* `partner_log.record()` against
a `tmp_path` log dir rather than hand-writing `.jsonl` lines -- this
exercises `publish.project()` against exactly the on-disk shape
`record()` actually produces, and gets the last-line-wins multi-line
case "for free" by calling `record()` twice with a changed opportunity.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from partner_scrape.export import partner_log, publish, writer
from partner_scrape.export.partner_log import _to_log_dict, published_content_hash
from partner_scrape.export.publish import _to_opportunity, project
from partner_scrape.export.writer import SITE_SCHEMA_FIELDS, export_opportunities
from partner_scrape.normalize.run import WORK_BASED_LEARNING_TYPE, Opportunity

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
PARTNERS_PATH = FIXTURES_DIR / "partners.json"


@pytest.fixture(autouse=True)
def _own_data_dir_default(tmp_path_factory, monkeypatch):
    """Pin `writer.get_own_data_dir()`'s resolution to a throwaway
    directory for every test in this file (sprint 020 ticket 003).

    `export_opportunities()`'s new `own_data_dir` parameter defaults to
    `config.get_own_data_dir()` -- a real repo path with no
    environment-variable override -- when a caller doesn't pass one
    explicitly. `TestLegacyExportUnaffected` below calls the real
    `export_opportunities()` directly without it, which would otherwise
    write real files into this repo's actual `data/` directory on every
    test run. Mirrors `tests/test_export.py`'s identical
    `_own_data_dir_default` fixture, for the same underlying reason.
    """
    fake_own_data_dir = tmp_path_factory.mktemp("own-data-default")
    monkeypatch.setattr(writer, "get_own_data_dir", lambda: fake_own_data_dir)


def _opportunity(
    slug: str = "farm_tour_20260801",
    title: str = "Farm Tour",
    date_start: str = "2026-08-01T09:00:00-07:00",
    date_end: str = "",
    partner_name: str = "Coastal Roots Farm",
    partner_id: int | None = 101,
    opportunity_type: str = "Out-of-school Programs",
    sources: frozenset[str] = frozenset({"coastalrootsfarm"}),
    **overrides: Any,
) -> Opportunity:
    fields: dict[str, Any] = dict(
        slug=slug,
        title=title,
        partner_name=partner_name,
        partner_id=partner_id,
        description="A tour of the farm.",
        link="",
        availability="",
        date_start=date_start,
        date_end=date_end,
        age_grade_level=[],
        cost_range="",
        time_of_day=[],
        opportunity_type=opportunity_type,
        areas_of_interest=[],
        specific_attention=[],
        financial_support="No",
        ngss_aligned="No",
        location="",
        latitude="",
        longitude="",
        contact_name="",
        contact_email="",
        contact_phone="",
        logo_src="",
        image_src="",
        sources=sources,
    )
    fields.update(overrides)
    return Opportunity(**fields)


def _site_dir(tmp_path: Path) -> Path:
    site_dir = tmp_path / "stem-ecosystem"
    site_dir.mkdir()
    return site_dir


def _events_json(site_dir: Path, slug: str) -> dict[str, Any]:
    return json.loads(
        (site_dir / "public" / "data" / "partners" / slug / "events.json").read_text()
    )


def _past_events_json(site_dir: Path, slug: str) -> dict[str, Any]:
    return json.loads(
        (site_dir / "public" / "data" / "partners" / slug / "past-events.json").read_text()
    )


def _partners_json(site_dir: Path) -> dict[str, Any]:
    return json.loads((site_dir / "public" / "data" / "partners.json").read_text())


class TestLastLineWinsCollapse:
    def test_changed_event_publishes_only_the_latest_content(self, tmp_path):
        log_dir = tmp_path / "partner_log"
        site_dir = _site_dir(tmp_path)
        original = _opportunity(title="Farm Tour")
        changed = _opportunity(title="Farm Tour (Updated Time)")
        assert original.slug == changed.slug, "must be the same event identity"

        partner_log.record([original], log_dir=log_dir, partners_path=PARTNERS_PATH)
        partner_log.record([changed], log_dir=log_dir, partners_path=PARTNERS_PATH)
        # Two lines really are on disk for this slug -- otherwise this
        # test would not be exercising the collapse at all.
        lines = (log_dir / "coastal_roots_farm" / "opportunities.jsonl").read_text().splitlines()
        assert len(lines) == 2

        project(site_dir=site_dir, log_dir=log_dir, partners_path=PARTNERS_PATH, today=date(2026, 7, 19))

        events = _events_json(site_dir, "coastal_roots_farm")
        assert events["event_count"] == 1
        assert events["events"][0]["title"] == "Farm Tour (Updated Time)"

    def test_two_distinct_slugs_both_survive_the_collapse(self, tmp_path):
        log_dir = tmp_path / "partner_log"
        site_dir = _site_dir(tmp_path)
        a = _opportunity(slug="event_a", title="Event A")
        b = _opportunity(slug="event_b", title="Event B", date_start="2026-08-02T09:00:00-07:00")

        partner_log.record([a, b], log_dir=log_dir, partners_path=PARTNERS_PATH)
        project(site_dir=site_dir, log_dir=log_dir, partners_path=PARTNERS_PATH, today=date(2026, 7, 19))

        events = _events_json(site_dir, "coastal_roots_farm")
        assert events["event_count"] == 2
        assert {e["title"] for e in events["events"]} == {"Event A", "Event B"}


class TestCurrentPastSplitAgreesWithWriter:
    """Confirms `publish.project()`'s split agrees with `writer.py`'s
    already-tested `is_current_or_upcoming` rule, rather than
    re-asserting that rule's own full case matrix (see `test_export.py`
    `TestCurrentUpcomingFilter`/`TestInternshipCurrentUpcomingFilter`
    for the rule's own exhaustive coverage)."""

    @pytest.mark.parametrize(
        "opportunity_type,date_start,date_end,expected_bucket",
        [
            # Ordinary event, end date in the past -> past.
            ("Out-of-school Programs", "2026-07-01T09:00:00-07:00", "2026-07-18T09:00:00-07:00", "past"),
            # Ordinary event, end date today -> current.
            ("Out-of-school Programs", "2026-07-01T09:00:00-07:00", "2026-07-19T09:00:00-07:00", "current"),
            # Ordinary event, no end date, start date in the past -> past.
            ("Out-of-school Programs", "2026-06-19T09:00:00-07:00", "", "past"),
            # Work-based Learning: no deadline, start far in the past ->
            # current (the internship exception).
            (WORK_BASED_LEARNING_TYPE, "2026-06-19T09:00:00-07:00", "", "current"),
            # Work-based Learning: deadline in the future -> current.
            (WORK_BASED_LEARNING_TYPE, "2026-06-19T09:00:00-07:00", "2026-08-01T09:00:00-07:00", "current"),
            # Work-based Learning: deadline in the past -> past.
            (WORK_BASED_LEARNING_TYPE, "2026-06-19T09:00:00-07:00", "2026-07-01T09:00:00-07:00", "past"),
        ],
    )
    def test_split_matches_expected_bucket(
        self, tmp_path, opportunity_type, date_start, date_end, expected_bucket
    ):
        log_dir = tmp_path / "partner_log"
        site_dir = _site_dir(tmp_path)
        opp = _opportunity(
            opportunity_type=opportunity_type, date_start=date_start, date_end=date_end
        )

        partner_log.record([opp], log_dir=log_dir, partners_path=PARTNERS_PATH)
        project(site_dir=site_dir, log_dir=log_dir, partners_path=PARTNERS_PATH, today=date(2026, 7, 19))

        current = _events_json(site_dir, "coastal_roots_farm")
        past = _past_events_json(site_dir, "coastal_roots_farm")
        if expected_bucket == "current":
            assert current["event_count"] == 1
            assert past["event_count"] == 0
        else:
            assert current["event_count"] == 0
            assert past["event_count"] == 1

    def test_undated_event_is_not_silently_dropped(self, tmp_path):
        """Unlike the legacy flat export (which excludes undated records
        entirely -- see `test_export.py::test_undated_opportunity_is_excluded`),
        the published contract's whole point is that nothing accumulated
        in the persistent log is ever silently lost -- an undated,
        non-internship record still lands in past-events.json rather
        than vanishing."""
        log_dir = tmp_path / "partner_log"
        site_dir = _site_dir(tmp_path)
        opp = _opportunity(date_start="", date_end="")

        partner_log.record([opp], log_dir=log_dir, partners_path=PARTNERS_PATH)
        project(site_dir=site_dir, log_dir=log_dir, partners_path=PARTNERS_PATH, today=date(2026, 7, 19))

        assert _events_json(site_dir, "coastal_roots_farm")["event_count"] == 0
        past = _past_events_json(site_dir, "coastal_roots_farm")
        assert past["event_count"] == 1
        assert past["events"][0]["slug"] == opp.slug


class TestJoinAgainstCuratedPartners:
    def test_every_curated_partner_appears_even_with_no_accumulated_log(self, tmp_path):
        log_dir = tmp_path / "partner_log"
        site_dir = _site_dir(tmp_path)
        # Nothing ever scraped -- log_dir isn't even created.

        summary = project(site_dir=site_dir, log_dir=log_dir, partners_path=PARTNERS_PATH, today=date(2026, 7, 19))

        partners = _partners_json(site_dir)["partners"]
        names = {p["name"] for p in partners}
        assert names == {"Coastal Roots Farm", "The Living Coast Discovery Center", "Ocean Connectors"}
        assert summary["partner_count"] == 3
        assert summary["current_event_count"] == 0
        assert summary["past_event_count"] == 0

    def test_partner_with_no_log_publishes_empty_event_files(self, tmp_path):
        log_dir = tmp_path / "partner_log"
        site_dir = _site_dir(tmp_path)

        project(site_dir=site_dir, log_dir=log_dir, partners_path=PARTNERS_PATH, today=date(2026, 7, 19))

        # "The Living Coast Discovery Center" never had record() called
        # for it -- its directory under log_dir does not exist at all.
        events = _events_json(site_dir, "the_living_coast_discovery_center")
        past = _past_events_json(site_dir, "the_living_coast_discovery_center")
        assert events["events"] == []
        assert past["events"] == []

    def test_partner_with_events_and_partner_without_both_appear_correctly(self, tmp_path):
        log_dir = tmp_path / "partner_log"
        site_dir = _site_dir(tmp_path)
        opp = _opportunity()  # Coastal Roots Farm

        partner_log.record([opp], log_dir=log_dir, partners_path=PARTNERS_PATH)
        project(site_dir=site_dir, log_dir=log_dir, partners_path=PARTNERS_PATH, today=date(2026, 7, 19))

        farm_events = _events_json(site_dir, "coastal_roots_farm")
        assert farm_events["event_count"] == 1

        ocean_events = _events_json(site_dir, "ocean_connectors")
        assert ocean_events["event_count"] == 0

    def test_partners_json_full_curated_record_plus_reference_paths(self, tmp_path):
        log_dir = tmp_path / "partner_log"
        site_dir = _site_dir(tmp_path)

        project(site_dir=site_dir, log_dir=log_dir, partners_path=PARTNERS_PATH, today=date(2026, 7, 19))

        partners = {p["name"]: p for p in _partners_json(site_dir)["partners"]}
        farm = partners["Coastal Roots Farm"]
        # Full curated record survives (every field from fixtures/partners.json).
        assert farm["id"] == 101
        assert farm["organization_type"] == "Afterschool/Out-of-School Time"
        assert farm["location"] == "Encinitas, California"
        assert farm["website"] == "https://example.org/coastal-roots-farm"
        # Reference paths point at this partner's own files, resolvable
        # relative to public/data/.
        assert farm["slug"] == "coastal_roots_farm"
        assert farm["events_url"] == "partners/coastal_roots_farm/events.json"
        assert farm["past_events_url"] == "partners/coastal_roots_farm/past-events.json"
        resolved = (site_dir / "public" / "data" / farm["events_url"]).resolve()
        assert resolved == (site_dir / "public" / "data" / "partners" / "coastal_roots_farm" / "events.json").resolve()
        assert resolved.exists()


class TestPublishedEventFieldSet:
    def test_event_records_use_exactly_the_site_schema_field_set(self, tmp_path):
        log_dir = tmp_path / "partner_log"
        site_dir = _site_dir(tmp_path)
        opp = _opportunity(sources=frozenset({"source_a", "source_b"}))

        partner_log.record([opp], log_dir=log_dir, partners_path=PARTNERS_PATH)
        project(site_dir=site_dir, log_dir=log_dir, partners_path=PARTNERS_PATH, today=date(2026, 7, 19))

        events = _events_json(site_dir, "coastal_roots_farm")["events"]
        assert len(events) == 1
        assert set(events[0].keys()) == set(SITE_SCHEMA_FIELDS)
        assert "sources" not in events[0]


class TestSelfDescribing:
    def test_partners_json_carries_generation_metadata(self, tmp_path):
        log_dir = tmp_path / "partner_log"
        site_dir = _site_dir(tmp_path)

        project(site_dir=site_dir, log_dir=log_dir, partners_path=PARTNERS_PATH, today=date(2026, 7, 19))

        payload = _partners_json(site_dir)
        assert "generated_at" in payload
        assert payload["partner_count"] == 3
        assert isinstance(payload["partners"], list)

    def test_event_files_are_self_describing_without_partners_json_context(self, tmp_path):
        log_dir = tmp_path / "partner_log"
        site_dir = _site_dir(tmp_path)
        partner_log.record([_opportunity()], log_dir=log_dir, partners_path=PARTNERS_PATH)

        project(site_dir=site_dir, log_dir=log_dir, partners_path=PARTNERS_PATH, today=date(2026, 7, 19))

        events = _events_json(site_dir, "coastal_roots_farm")
        assert events["kind"] == "current"
        assert events["partner_slug"] == "coastal_roots_farm"
        assert "generated_at" in events
        assert events["event_count"] == len(events["events"])

        past = _past_events_json(site_dir, "coastal_roots_farm")
        assert past["kind"] == "past"


class TestDryRun:
    def test_dry_run_writes_nothing_to_disk(self, tmp_path):
        log_dir = tmp_path / "partner_log"
        site_dir = _site_dir(tmp_path)
        partner_log.record([_opportunity()], log_dir=log_dir, partners_path=PARTNERS_PATH)

        summary = project(
            site_dir=site_dir,
            log_dir=log_dir,
            partners_path=PARTNERS_PATH,
            today=date(2026, 7, 19),
            dry_run=True,
        )

        assert not (site_dir / "public").exists()
        assert summary["partner_count"] == 3
        assert summary["current_event_count"] == 1

    def test_dry_run_summary_matches_real_run_summary(self, tmp_path):
        log_dir = tmp_path / "partner_log"
        site_dir = _site_dir(tmp_path)
        partner_log.record([_opportunity()], log_dir=log_dir, partners_path=PARTNERS_PATH)

        dry_summary = project(
            site_dir=site_dir, log_dir=log_dir, partners_path=PARTNERS_PATH,
            today=date(2026, 7, 19), dry_run=True,
        )
        real_summary = project(
            site_dir=site_dir, log_dir=log_dir, partners_path=PARTNERS_PATH,
            today=date(2026, 7, 19),
        )

        assert dry_summary == real_summary


class TestLegacyExportUnaffected:
    def test_opportunities_json_is_unaffected_by_project(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        (site_dir / "src" / "data").mkdir(parents=True)
        log_dir = tmp_path / "partner_log"
        opp = _opportunity()
        partner_log.record([opp], log_dir=log_dir, partners_path=PARTNERS_PATH)

        export_opportunities([opp], site_dir=site_dir, today=date(2026, 7, 19))
        before = (site_dir / "src" / "data" / "opportunities.json").read_text()
        before_meta = (site_dir / "src" / "data" / "scrape-meta.json").read_text()

        project(site_dir=site_dir, log_dir=log_dir, partners_path=PARTNERS_PATH, today=date(2026, 7, 19))

        after = (site_dir / "src" / "data" / "opportunities.json").read_text()
        after_meta = (site_dir / "src" / "data" / "scrape-meta.json").read_text()
        assert before == after
        assert before_meta == after_meta
        # And the new tree was written alongside it, additively.
        assert (site_dir / "public" / "data" / "partners.json").exists()


class TestLegacyLogLineTolerance:
    """Sprint 018 ticket 010, issue 45: `_to_opportunity()` reconstructs
    an `Opportunity` from a persisted log line, and the per-partner log
    is strictly append-only (`export/DESIGN.md`) -- a line recorded
    before some field existed on `Opportunity` simply lacks that key.
    `eligibility` (sprint 015 ticket 008) is the concrete field that
    broke every real accumulated line, but these tests build the legacy
    shape by deleting keys from a real `_to_log_dict()` entry rather
    than hand-writing a fixture, so they'd equally catch a regression on
    any other field."""

    def test_line_missing_eligibility_reconstructs_with_the_dataclass_default(self):
        opp = _opportunity()
        entry = _to_log_dict(opp, published_content_hash(opp))
        assert "eligibility" in entry  # sanity: current schema does carry it
        del entry["eligibility"]  # simulate a pre-sprint-015 log line

        reconstructed = _to_opportunity(entry)

        assert reconstructed.eligibility == ""  # Opportunity's own dataclass default
        # Every field still present in `entry` is used verbatim.
        assert reconstructed.slug == opp.slug
        assert reconstructed.title == opp.title
        assert reconstructed.sources == opp.sources

    def test_line_missing_several_newer_fields_reconstructs_with_each_default(self):
        opp = _opportunity()
        entry = _to_log_dict(opp, published_content_hash(opp))
        for name in ("eligibility", "image_src", "sources"):
            del entry[name]

        reconstructed = _to_opportunity(entry)

        assert reconstructed.eligibility == ""
        assert reconstructed.image_src == ""
        assert reconstructed.sources == frozenset()
        # A field still present in `entry` remains unaffected.
        assert reconstructed.slug == opp.slug
        assert reconstructed.title == opp.title

    def test_project_succeeds_over_a_mix_of_legacy_and_current_schema_lines(self, tmp_path):
        log_dir = tmp_path / "partner_log"
        site_dir = _site_dir(tmp_path)

        # A legacy line: pre-sprint-015 shape, missing `eligibility`,
        # written directly to disk -- `record()` only ever writes
        # current-schema lines, so a real legacy line can't be produced
        # by calling it.
        legacy_opp = _opportunity(slug="legacy_event", title="Legacy Event")
        legacy_entry = _to_log_dict(legacy_opp, published_content_hash(legacy_opp))
        del legacy_entry["eligibility"]
        partner_dir = log_dir / "coastal_roots_farm"
        partner_dir.mkdir(parents=True)
        (partner_dir / "opportunities.jsonl").write_text(
            json.dumps(legacy_entry, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        # A current-schema line for a second event at the same partner,
        # appended the real way via `record()`.
        current_opp = _opportunity(
            slug="current_event",
            title="Current Event",
            date_start="2026-08-02T09:00:00-07:00",
            eligibility="Grades 6-8",
        )
        partner_log.record([current_opp], log_dir=log_dir, partners_path=PARTNERS_PATH)
        lines = (partner_dir / "opportunities.jsonl").read_text().splitlines()
        assert len(lines) == 2, "both the legacy and current-schema lines must be on disk"

        summary = project(
            site_dir=site_dir, log_dir=log_dir, partners_path=PARTNERS_PATH, today=date(2026, 7, 19)
        )

        assert summary["partner_count"] == 3
        events = {e["title"]: e for e in _events_json(site_dir, "coastal_roots_farm")["events"]}
        assert set(events) == {"Legacy Event", "Current Event"}
        # The legacy line's missing field defaulted correctly...
        assert events["Legacy Event"]["eligibility"] == ""
        # ...and the current-schema line's own value survived untouched.
        assert events["Current Event"]["eligibility"] == "Grades 6-8"


class TestSiteDirErrors:
    def test_missing_site_dir_raises_a_clear_error(self, tmp_path):
        missing = tmp_path / "does-not-exist"
        log_dir = tmp_path / "partner_log"

        with pytest.raises(RuntimeError, match="site_dir"):
            project(site_dir=missing, log_dir=log_dir, partners_path=PARTNERS_PATH, today=date(2026, 7, 19))

    def test_missing_site_dir_writes_nothing(self, tmp_path):
        missing = tmp_path / "does-not-exist"
        log_dir = tmp_path / "partner_log"

        with pytest.raises(RuntimeError):
            project(site_dir=missing, log_dir=log_dir, partners_path=PARTNERS_PATH, today=date(2026, 7, 19))

        assert not missing.exists()

    def test_public_data_path_occupied_by_a_file_raises_a_clear_error(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        (site_dir / "public").write_text("not a directory")
        log_dir = tmp_path / "partner_log"

        with pytest.raises(RuntimeError, match="site_dir"):
            project(site_dir=site_dir, log_dir=log_dir, partners_path=PARTNERS_PATH, today=date(2026, 7, 19))


class TestConfigDefaults:
    def test_omitted_site_dir_resolves_via_config_get_site_dir(self, tmp_path, monkeypatch):
        fake_site_dir = _site_dir(tmp_path)
        log_dir = tmp_path / "partner_log"
        monkeypatch.setattr(publish, "get_site_dir", lambda: fake_site_dir)

        project(log_dir=log_dir, partners_path=PARTNERS_PATH, today=date(2026, 7, 19))

        assert (fake_site_dir / "public" / "data" / "partners.json").exists()

    def test_omitted_log_dir_resolves_via_config_get_scrape_cache_dir(self, tmp_path, monkeypatch):
        fake_cache_dir = tmp_path / "cache"
        site_dir = _site_dir(tmp_path)
        monkeypatch.setattr(publish, "get_scrape_cache_dir", lambda: fake_cache_dir)

        # No log written under fake_cache_dir/partner_log -- every
        # partner should still publish with empty event lists rather
        # than raising.
        project(site_dir=site_dir, partners_path=PARTNERS_PATH, today=date(2026, 7, 19))

        assert (site_dir / "public" / "data" / "partners.json").exists()

    def test_omitted_partners_path_resolves_via_config_get_site_dir(self, tmp_path, monkeypatch):
        fake_site_dir = _site_dir(tmp_path)
        (fake_site_dir / "src" / "data").mkdir(parents=True)
        (fake_site_dir / "src" / "data" / "partners.json").write_text(
            json.dumps([{"id": 101, "name": "Coastal Roots Farm"}])
        )
        monkeypatch.setattr(publish, "get_site_dir", lambda: fake_site_dir)
        log_dir = tmp_path / "partner_log"

        project(site_dir=fake_site_dir, log_dir=log_dir, today=date(2026, 7, 19))

        partners = _partners_json(fake_site_dir)["partners"]
        assert partners == [
            {
                "id": 101,
                "name": "Coastal Roots Farm",
                "slug": "coastal_roots_farm",
                "events_url": "partners/coastal_roots_farm/events.json",
                "past_events_url": "partners/coastal_roots_farm/past-events.json",
            }
        ]
