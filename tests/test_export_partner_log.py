"""Tests for partner_scrape.export.partner_log: the persistent,
per-partner, append-only accumulation layer (sprint 009 ticket 003,
issue 15).

Every test passes an explicit `log_dir`/`partners_path` under
`tmp_path` -- no test relies on `config.get_scrape_cache_dir()` /
`config.get_site_dir()`'s real defaults or writes to a real checkout,
matching writer.py's own test-file convention.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from partner_scrape.export import partner_log
from partner_scrape.export.partner_log import published_content_hash, record
from partner_scrape.normalize.run import Opportunity

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
PARTNERS_PATH = FIXTURES_DIR / "partners.json"


def _opportunity(
    slug: str = "farm_tour_20260801",
    title: str = "Farm Tour",
    date_start: str = "2026-08-01T09:00:00-07:00",
    date_end: str = "",
    partner_name: str = "Coastal Roots Farm",
    partner_id: int | None = 101,
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
        opportunity_type="Out-of-school Programs",
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


def _log_lines(jsonl_path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]


class TestPublishedContentHash:
    def test_identical_published_fields_hash_identically(self):
        a = _opportunity()
        b = _opportunity()
        assert published_content_hash(a) == published_content_hash(b)

    def test_different_title_changes_the_hash(self):
        a = _opportunity(title="Farm Tour")
        b = _opportunity(title="Farm Tour, Extended")
        assert published_content_hash(a) != published_content_hash(b)

    def test_bookkeeping_field_changes_do_not_affect_the_hash(self):
        """`slug`, `sources`, `partner_name`/`partner_id`, and the other
        identity/bookkeeping fields are explicitly excluded (SUC-005
        Main Flow step 2) -- only the published-schema fields matter."""
        a = _opportunity(
            slug="farm_tour_20260801",
            sources=frozenset({"source_a"}),
            partner_name="Coastal Roots Farm",
            partner_id=101,
        )
        b = _opportunity(
            slug="a_completely_different_slug",
            sources=frozenset({"source_b", "source_c"}),
            partner_name="A Different Partner Name",
            partner_id=999,
        )
        assert published_content_hash(a) == published_content_hash(b)


class TestDirectoryLayout:
    def test_partner_json_and_jsonl_created_under_partner_slug_dir(self, tmp_path):
        log_dir = tmp_path / "partner_log"
        opp = _opportunity()

        record([opp], log_dir=log_dir, partners_path=PARTNERS_PATH)

        partner_dir = log_dir / "coastal_roots_farm"
        assert (partner_dir / "partner.json").exists()
        assert (partner_dir / "opportunities.jsonl").exists()

    def test_partner_json_matches_curated_record(self, tmp_path):
        log_dir = tmp_path / "partner_log"
        opp = _opportunity()

        record([opp], log_dir=log_dir, partners_path=PARTNERS_PATH)

        written = json.loads((log_dir / "coastal_roots_farm" / "partner.json").read_text())
        assert written["id"] == 101
        assert written["name"] == "Coastal Roots Farm"

    def test_jsonl_line_contains_slug_content_hash_and_sources_as_list(self, tmp_path):
        log_dir = tmp_path / "partner_log"
        opp = _opportunity(sources=frozenset({"source_a", "source_b"}))

        record([opp], log_dir=log_dir, partners_path=PARTNERS_PATH)

        lines = _log_lines(log_dir / "coastal_roots_farm" / "opportunities.jsonl")
        assert len(lines) == 1
        entry = lines[0]
        assert entry["slug"] == opp.slug
        assert entry["content_hash"] == published_content_hash(opp)
        assert entry["sources"] == ["source_a", "source_b"]
        assert isinstance(entry["sources"], list)

    def test_different_partners_get_separate_directories(self, tmp_path):
        log_dir = tmp_path / "partner_log"
        a = _opportunity(
            slug="farm_tour_20260801", partner_name="Coastal Roots Farm", partner_id=101
        )
        b = _opportunity(
            slug="beach_walk_20260802",
            title="Beach Walk",
            partner_name="Ocean Connectors",
            partner_id=103,
            date_start="2026-08-02T09:00:00-07:00",
        )

        record([a, b], log_dir=log_dir, partners_path=PARTNERS_PATH)

        assert (log_dir / "coastal_roots_farm" / "opportunities.jsonl").exists()
        assert (log_dir / "ocean_connectors" / "opportunities.jsonl").exists()
        assert len(_log_lines(log_dir / "coastal_roots_farm" / "opportunities.jsonl")) == 1
        assert len(_log_lines(log_dir / "ocean_connectors" / "opportunities.jsonl")) == 1


class TestAppendSkipDecisionTable:
    def test_new_slug_appends(self, tmp_path):
        log_dir = tmp_path / "partner_log"
        opp = _opportunity()

        record([opp], log_dir=log_dir, partners_path=PARTNERS_PATH)

        lines = _log_lines(log_dir / "coastal_roots_farm" / "opportunities.jsonl")
        assert len(lines) == 1

    def test_same_slug_same_hash_is_skipped_no_write(self, tmp_path):
        log_dir = tmp_path / "partner_log"
        jsonl_path = log_dir / "coastal_roots_farm" / "opportunities.jsonl"
        opp = _opportunity()

        record([opp], log_dir=log_dir, partners_path=PARTNERS_PATH)
        before_bytes = jsonl_path.read_bytes()
        before_mtime = jsonl_path.stat().st_mtime_ns

        record([opp], log_dir=log_dir, partners_path=PARTNERS_PATH)

        after_bytes = jsonl_path.read_bytes()
        assert after_bytes == before_bytes, "file content must be byte-identical when nothing new"
        assert jsonl_path.stat().st_mtime_ns == before_mtime, "unchanged file must not be rewritten"
        assert len(_log_lines(jsonl_path)) == 1

    def test_same_slug_different_hash_appends_new_line_old_line_still_present(self, tmp_path):
        log_dir = tmp_path / "partner_log"
        jsonl_path = log_dir / "coastal_roots_farm" / "opportunities.jsonl"
        original = _opportunity(title="Farm Tour")
        changed = _opportunity(title="Farm Tour (Updated Time)")
        assert original.slug == changed.slug  # same identity, different content

        record([original], log_dir=log_dir, partners_path=PARTNERS_PATH)
        first_line = jsonl_path.read_text(encoding="utf-8")

        record([changed], log_dir=log_dir, partners_path=PARTNERS_PATH)

        lines = _log_lines(jsonl_path)
        assert len(lines) == 2
        titles = {entry["title"] for entry in lines}
        assert titles == {"Farm Tour", "Farm Tour (Updated Time)"}
        # The original line's exact bytes are still present, unmodified.
        assert first_line.strip() in jsonl_path.read_text(encoding="utf-8")


class TestStrictAppendOnly:
    def test_second_call_never_rewrites_or_removes_existing_lines(self, tmp_path):
        log_dir = tmp_path / "partner_log"
        jsonl_path = log_dir / "coastal_roots_farm" / "opportunities.jsonl"
        first = _opportunity(slug="event_a", title="Event A")
        second = _opportunity(slug="event_b", title="Event B", date_start="2026-08-02T09:00:00-07:00")

        record([first], log_dir=log_dir, partners_path=PARTNERS_PATH)
        lines_before = jsonl_path.read_text(encoding="utf-8").splitlines()

        record([second], log_dir=log_dir, partners_path=PARTNERS_PATH)
        lines_after = jsonl_path.read_text(encoding="utf-8").splitlines()

        assert lines_before[0] == lines_after[0], "prior line must be byte-identical, not rewritten"
        assert len(lines_after) == 2


class TestIdempotency:
    def test_running_the_same_payload_through_twice_does_not_grow_the_log(self, tmp_path):
        """The log's whole value is one record per (slug, content) pair
        across runs, not one per run -- re-scraping the same events must
        never duplicate them."""
        log_dir = tmp_path / "partner_log"
        jsonl_path = log_dir / "coastal_roots_farm" / "opportunities.jsonl"
        opportunities = [
            _opportunity(slug="event_a", title="Event A"),
            _opportunity(slug="event_b", title="Event B", date_start="2026-08-02T09:00:00-07:00"),
        ]

        record(opportunities, log_dir=log_dir, partners_path=PARTNERS_PATH)
        assert len(_log_lines(jsonl_path)) == 2

        record(opportunities, log_dir=log_dir, partners_path=PARTNERS_PATH)
        record(opportunities, log_dir=log_dir, partners_path=PARTNERS_PATH)
        record(opportunities, log_dir=log_dir, partners_path=PARTNERS_PATH)

        assert len(_log_lines(jsonl_path)) == 2, "log must not grow when input is unchanged"

    def test_within_one_run_duplicate_opportunities_do_not_double_append(self, tmp_path):
        log_dir = tmp_path / "partner_log"
        jsonl_path = log_dir / "coastal_roots_farm" / "opportunities.jsonl"
        opp = _opportunity()

        record([opp, opp, opp], log_dir=log_dir, partners_path=PARTNERS_PATH)

        assert len(_log_lines(jsonl_path)) == 1


class TestDryRun:
    def test_dry_run_writes_nothing_to_disk(self, tmp_path):
        log_dir = tmp_path / "partner_log"
        opp = _opportunity()

        record([opp], log_dir=log_dir, partners_path=PARTNERS_PATH, dry_run=True)

        assert not log_dir.exists()

    def test_dry_run_does_not_create_the_log_dir_at_all(self, tmp_path):
        log_dir = tmp_path / "partner_log"
        opps = [
            _opportunity(slug="event_a"),
            _opportunity(
                slug="event_b", partner_name="Ocean Connectors", partner_id=103, title="Beach Walk"
            ),
        ]

        record(opps, log_dir=log_dir, partners_path=PARTNERS_PATH, dry_run=True)

        assert not log_dir.exists()


class TestUnmatchedPartner:
    def test_unmatched_partner_still_accumulates_keyed_by_slugify_org_name(self, tmp_path):
        log_dir = tmp_path / "partner_log"
        opp = _opportunity(
            partner_name="Some Org Not In The Fixture", partner_id=None, slug="mystery_event"
        )

        record([opp], log_dir=log_dir, partners_path=PARTNERS_PATH)

        partner_dir = log_dir / "some_org_not_in_the_fixture"
        assert (partner_dir / "opportunities.jsonl").exists()
        assert len(_log_lines(partner_dir / "opportunities.jsonl")) == 1

    def test_unmatched_partner_json_keeps_the_org_name(self, tmp_path):
        log_dir = tmp_path / "partner_log"
        opp = _opportunity(
            partner_name="Some Org Not In The Fixture", partner_id=None, slug="mystery_event"
        )

        record([opp], log_dir=log_dir, partners_path=PARTNERS_PATH)

        written = json.loads(
            (log_dir / "some_org_not_in_the_fixture" / "partner.json").read_text()
        )
        assert written["name"] == "Some Org Not In The Fixture"
        assert written["id"] is None


class TestPartnerJsonRefresh:
    def test_partner_json_is_refreshed_even_when_no_new_opportunity_line_is_added(self, tmp_path):
        log_dir = tmp_path / "partner_log"
        partners_path = tmp_path / "partners.json"
        partners_path.write_text(
            json.dumps([{"id": 101, "name": "Coastal Roots Farm", "location": "Old Location"}])
        )
        opp = _opportunity()

        record([opp], log_dir=log_dir, partners_path=partners_path)

        partners_path.write_text(
            json.dumps([{"id": 101, "name": "Coastal Roots Farm", "location": "New Location"}])
        )
        record([opp], log_dir=log_dir, partners_path=partners_path)

        written = json.loads((log_dir / "coastal_roots_farm" / "partner.json").read_text())
        assert written["location"] == "New Location"


class TestUnwritableTarget:
    def test_unwritable_log_dir_raises_runtime_error(self, tmp_path):
        log_dir = tmp_path / "partner_log"
        # Occupy the partner's directory path with a file, so `mkdir`
        # underneath it fails -- mirrors writer.py's own
        # `test_data_path_occupied_by_a_file_raises_a_clear_error`.
        log_dir.mkdir()
        (log_dir / "coastal_roots_farm").write_text("not a directory")
        opp = _opportunity()

        with pytest.raises(RuntimeError, match="partner log"):
            record([opp], log_dir=log_dir, partners_path=PARTNERS_PATH)


class TestConfigDefaults:
    def test_omitted_log_dir_resolves_via_config_get_scrape_cache_dir(self, tmp_path, monkeypatch):
        fake_cache_dir = tmp_path / "cache"
        monkeypatch.setattr(partner_log, "get_scrape_cache_dir", lambda: fake_cache_dir)

        record([_opportunity()], partners_path=PARTNERS_PATH)

        assert (fake_cache_dir / "partner_log" / "coastal_roots_farm" / "partner.json").exists()

    def test_omitted_partners_path_resolves_via_config_get_site_dir(self, tmp_path, monkeypatch):
        fake_site_dir = tmp_path / "stem-ecosystem"
        (fake_site_dir / "src" / "data").mkdir(parents=True)
        (fake_site_dir / "src" / "data" / "partners.json").write_text(
            json.dumps([{"id": 101, "name": "Coastal Roots Farm"}])
        )
        monkeypatch.setattr(partner_log, "get_site_dir", lambda: fake_site_dir)
        log_dir = tmp_path / "partner_log"

        record([_opportunity()], log_dir=log_dir)

        written = json.loads((log_dir / "coastal_roots_farm" / "partner.json").read_text())
        assert written["id"] == 101


class TestGrowthOverManyRuns:
    def test_log_length_tracks_distinct_content_not_run_count(self, tmp_path):
        """Documents the accumulation-layer's growth contract: N runs
        against the same unchanged event set produce one line, not N;
        a genuinely new-or-changed event across those same N runs adds
        exactly one line per distinct (slug, content_hash) pair, never
        one per run."""
        log_dir = tmp_path / "partner_log"
        jsonl_path = log_dir / "coastal_roots_farm" / "opportunities.jsonl"
        steady = _opportunity(slug="recurring_event", title="Recurring Event")

        for _ in range(5):
            record([steady], log_dir=log_dir, partners_path=PARTNERS_PATH)
        assert len(_log_lines(jsonl_path)) == 1

        changed = _opportunity(slug="recurring_event", title="Recurring Event (rescheduled)")
        record([changed], log_dir=log_dir, partners_path=PARTNERS_PATH)
        for _ in range(5):
            record([changed], log_dir=log_dir, partners_path=PARTNERS_PATH)

        assert len(_log_lines(jsonl_path)) == 2
