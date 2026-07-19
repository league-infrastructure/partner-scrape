"""Tests for partner_scrape.export.writer: the Site Export entry point.

Every test passes an explicit `today` and an explicit `site_dir` under
`tmp_path` -- no test relies on the real system clock or writes to the
real sibling `stem-ecosystem` checkout (see writer.py's module
docstring and sprint.md's Test Strategy: "no live HTTP ... ever").
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from partner_scrape.export import writer
from partner_scrape.export.writer import export_opportunities
from partner_scrape.normalize.run import WORK_BASED_LEARNING_TYPE, Opportunity

#: The exact field set documented in
#: stem-ecosystem/docs/site-implementation-spec.md's Opportunities
#: table. `Opportunity.sources` is deliberately absent -- it is
#: normalize's own cross-source bookkeeping, not part of the site
#: contract.
_EXPECTED_SITE_FIELDS = {
    "slug", "title", "partner_name", "partner_id", "description", "link",
    "availability", "date_start", "date_end", "age_grade_level", "cost_range",
    "time_of_day", "opportunity_type", "areas_of_interest", "specific_attention",
    "financial_support", "ngss_aligned", "location", "latitude", "longitude",
    "contact_name", "contact_email", "contact_phone", "logo_src",
}


def _site_dir(tmp_path: Path) -> Path:
    """A tmp_path-backed stand-in for the sibling stem-ecosystem repo,
    with `src/data` pre-created (matching a real checkout's layout)."""
    site_dir = tmp_path / "stem-ecosystem"
    (site_dir / "src" / "data").mkdir(parents=True)
    return site_dir


def _opportunity(
    slug: str = "coastal_roots_farm_farm_tour_20260801",
    title: str = "Farm Tour",
    date_start: str = "2026-08-01T09:00:00-07:00",
    date_end: str = "",
    partner_id: int | None = None,
    sources: frozenset[str] = frozenset({"coastalrootsfarm"}),
    **overrides: Any,
) -> Opportunity:
    fields: dict[str, Any] = dict(
        slug=slug,
        title=title,
        partner_name="Coastal Roots Farm",
        partner_id=partner_id,
        description="",
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
        sources=sources,
    )
    fields.update(overrides)
    return Opportunity(**fields)


class TestCurrentUpcomingFilter:
    def test_end_date_before_today_is_excluded(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        opp = _opportunity(
            date_start="2026-07-01T09:00:00-07:00",
            date_end="2026-07-18T09:00:00-07:00",
        )

        payload = export_opportunities([opp], site_dir=site_dir, today=date(2026, 7, 19))

        assert payload == []

    def test_start_date_before_today_with_no_end_date_is_excluded(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        opp = _opportunity(date_start="2026-07-18T09:00:00-07:00", date_end="")

        payload = export_opportunities([opp], site_dir=site_dir, today=date(2026, 7, 19))

        assert payload == []

    def test_undated_opportunity_is_excluded(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        opp = _opportunity(date_start="", date_end="")

        payload = export_opportunities([opp], site_dir=site_dir, today=date(2026, 7, 19))

        assert payload == []

    def test_end_date_today_is_included(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        opp = _opportunity(
            date_start="2026-07-01T09:00:00-07:00",
            date_end="2026-07-19T09:00:00-07:00",
        )

        payload = export_opportunities([opp], site_dir=site_dir, today=date(2026, 7, 19))

        assert len(payload) == 1

    def test_end_date_after_today_is_included(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        opp = _opportunity(
            date_start="2026-07-01T09:00:00-07:00",
            date_end="2026-08-01T09:00:00-07:00",
        )

        payload = export_opportunities([opp], site_dir=site_dir, today=date(2026, 7, 19))

        assert len(payload) == 1

    def test_start_date_today_or_later_with_no_end_date_is_included(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        opp = _opportunity(date_start="2026-07-19T09:00:00-07:00", date_end="")

        payload = export_opportunities([opp], site_dir=site_dir, today=date(2026, 7, 19))

        assert len(payload) == 1

    def test_mixed_past_and_upcoming_only_upcoming_survive(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        past = _opportunity(
            slug="past_event_20260101",
            title="Past Event",
            date_start="2026-01-01T09:00:00-07:00",
            date_end="",
        )
        upcoming = _opportunity(
            slug="upcoming_event_20260801",
            title="Upcoming Event",
            date_start="2026-08-01T09:00:00-07:00",
            date_end="",
        )

        payload = export_opportunities(
            [past, upcoming], site_dir=site_dir, today=date(2026, 7, 19)
        )

        assert [o["title"] for o in payload] == ["Upcoming Event"]


class TestInternshipCurrentUpcomingFilter:
    """`opportunity_type == "Work-based Learning"` records get a
    non-event-shaped current/upcoming rule (sprint.md Design Rationale,
    SUC-004): `date_start` is the posting-observed date and routinely in
    the past, so it must not drive expiry the way it does for an
    ordinary event."""

    def test_no_deadline_internship_with_past_start_is_included(self, tmp_path):
        """Would be wrongly excluded under the pre-ticket
        `date_end or date_start >= today` rule."""
        site_dir = _site_dir(tmp_path)
        opp = _opportunity(
            date_start="2026-06-19T09:00:00-07:00",  # 30 days before `today` below
            date_end="",
            opportunity_type=WORK_BASED_LEARNING_TYPE,
        )

        payload = export_opportunities([opp], site_dir=site_dir, today=date(2026, 7, 19))

        assert len(payload) == 1

    def test_future_deadline_internship_is_included(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        opp = _opportunity(
            date_start="2026-06-19T09:00:00-07:00",
            date_end="2026-08-01T09:00:00-07:00",
            opportunity_type=WORK_BASED_LEARNING_TYPE,
        )

        payload = export_opportunities([opp], site_dir=site_dir, today=date(2026, 7, 19))

        assert len(payload) == 1

    def test_past_deadline_internship_is_excluded(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        opp = _opportunity(
            date_start="2026-06-19T09:00:00-07:00",
            date_end="2026-07-01T09:00:00-07:00",
            opportunity_type=WORK_BASED_LEARNING_TYPE,
        )

        payload = export_opportunities([opp], site_dir=site_dir, today=date(2026, 7, 19))

        assert payload == []

    def test_ordinary_event_with_past_start_and_no_end_is_still_excluded(self, tmp_path):
        """Guards against a partition bug that accidentally applies the
        internship rule to `opportunity_type="Out-of-school Programs"`
        (the default) too -- must keep matching
        `TestCurrentUpcomingFilter`'s equivalent, non-internship case."""
        site_dir = _site_dir(tmp_path)
        opp = _opportunity(
            date_start="2026-06-19T09:00:00-07:00",
            date_end="",
            opportunity_type="Out-of-school Programs",
        )

        payload = export_opportunities([opp], site_dir=site_dir, today=date(2026, 7, 19))

        assert payload == []


class TestSlugDedup:
    def test_colliding_slugs_get_disambiguating_suffix_neither_dropped(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        a = _opportunity(
            slug="crf_farm_camp_20260801",
            title="Farm Camp Session A",
            date_start="2026-08-01T09:00:00-07:00",
        )
        b = _opportunity(
            slug="crf_farm_camp_20260801",
            title="Farm Camp Session B",
            date_start="2026-08-02T09:00:00-07:00",
        )

        payload = export_opportunities([a, b], site_dir=site_dir, today=date(2026, 7, 19))

        slugs = [o["slug"] for o in payload]
        assert len(payload) == 2
        assert len(set(slugs)) == 2, "colliding slugs must be disambiguated, not dropped"
        assert "crf_farm_camp_20260801" in slugs
        assert "crf_farm_camp_20260801_2" in slugs
        titles = {o["title"] for o in payload}
        assert titles == {"Farm Camp Session A", "Farm Camp Session B"}

    def test_three_way_collision_each_gets_a_distinct_suffix(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        events = [
            _opportunity(
                slug="crf_farm_camp_20260801",
                title=f"Session {i}",
                date_start=f"2026-08-0{i}T09:00:00-07:00",
            )
            for i in (1, 2, 3)
        ]

        payload = export_opportunities(events, site_dir=site_dir, today=date(2026, 7, 19))

        slugs = {o["slug"] for o in payload}
        assert slugs == {
            "crf_farm_camp_20260801",
            "crf_farm_camp_20260801_2",
            "crf_farm_camp_20260801_3",
        }


class TestSiteSchemaShape:
    def test_written_json_has_exact_site_schema_field_set(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        opp = _opportunity(sources=frozenset({"tec_source", "wp_source"}))

        payload = export_opportunities([opp], site_dir=site_dir, today=date(2026, 7, 19))

        assert len(payload) == 1
        assert set(payload[0].keys()) == _EXPECTED_SITE_FIELDS
        assert "sources" not in payload[0]

        written = json.loads((site_dir / "src" / "data" / "opportunities.json").read_text())
        assert len(written) == 1
        assert set(written[0].keys()) == _EXPECTED_SITE_FIELDS

    def test_partner_id_none_serializes_to_null(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        opp = _opportunity(partner_id=None)

        export_opportunities([opp], site_dir=site_dir, today=date(2026, 7, 19))

        written = json.loads((site_dir / "src" / "data" / "opportunities.json").read_text())
        assert written[0]["partner_id"] is None

    def test_field_types_match_spec_lists_stay_lists_strings_stay_strings(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        opp = _opportunity(
            age_grade_level=["Family"],
            areas_of_interest=["Biology / LifeSciences"],
            time_of_day=["Morning"],
        )

        export_opportunities([opp], site_dir=site_dir, today=date(2026, 7, 19))

        written = json.loads((site_dir / "src" / "data" / "opportunities.json").read_text())[0]
        assert isinstance(written["age_grade_level"], list)
        assert isinstance(written["areas_of_interest"], list)
        assert isinstance(written["time_of_day"], list)
        assert isinstance(written["slug"], str)
        assert isinstance(written["title"], str)


class TestScrapeMeta:
    def test_last_updated_changes_between_runs(self, tmp_path, monkeypatch):
        site_dir = _site_dir(tmp_path)
        stamps = iter(
            [
                datetime(2026, 7, 19, 12, 0, 0, tzinfo=timezone.utc),
                datetime(2026, 7, 19, 12, 5, 0, tzinfo=timezone.utc),
            ]
        )

        class FakeDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return next(stamps)

        monkeypatch.setattr(writer, "datetime", FakeDateTime)

        export_opportunities([_opportunity()], site_dir=site_dir, today=date(2026, 7, 19))
        first = json.loads((site_dir / "src" / "data" / "scrape-meta.json").read_text())

        export_opportunities([_opportunity()], site_dir=site_dir, today=date(2026, 7, 19))
        second = json.loads((site_dir / "src" / "data" / "scrape-meta.json").read_text())

        assert first["last_updated"] == "2026-07-19T12:00:00Z"
        assert second["last_updated"] == "2026-07-19T12:05:00Z"
        assert first["last_updated"] != second["last_updated"]

    def test_last_updated_written_even_when_opportunity_set_is_unchanged(
        self, tmp_path, monkeypatch
    ):
        site_dir = _site_dir(tmp_path)
        stamps = iter(
            [
                datetime(2026, 7, 19, 9, 0, 0, tzinfo=timezone.utc),
                datetime(2026, 7, 19, 10, 0, 0, tzinfo=timezone.utc),
            ]
        )

        class FakeDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return next(stamps)

        monkeypatch.setattr(writer, "datetime", FakeDateTime)
        same_opportunity = _opportunity()

        export_opportunities([same_opportunity], site_dir=site_dir, today=date(2026, 7, 19))
        first_opps = (site_dir / "src" / "data" / "opportunities.json").read_text()
        first_meta = json.loads((site_dir / "src" / "data" / "scrape-meta.json").read_text())

        export_opportunities([same_opportunity], site_dir=site_dir, today=date(2026, 7, 19))
        second_opps = (site_dir / "src" / "data" / "opportunities.json").read_text()
        second_meta = json.loads((site_dir / "src" / "data" / "scrape-meta.json").read_text())

        assert first_opps == second_opps
        assert first_meta["last_updated"] != second_meta["last_updated"]


class TestDryRun:
    def test_dry_run_writes_nothing_but_returns_the_payload(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        opp = _opportunity()

        payload = export_opportunities(
            [opp], site_dir=site_dir, today=date(2026, 7, 19), dry_run=True
        )

        assert len(payload) == 1
        assert not (site_dir / "src" / "data" / "opportunities.json").exists()
        assert not (site_dir / "src" / "data" / "scrape-meta.json").exists()

    def test_dry_run_payload_matches_non_dry_run_payload(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        opp = _opportunity()

        dry_payload = export_opportunities(
            [opp], site_dir=site_dir, today=date(2026, 7, 19), dry_run=True
        )
        real_payload = export_opportunities([opp], site_dir=site_dir, today=date(2026, 7, 19))

        assert dry_payload == real_payload


class TestTargetDirIsolation:
    def test_writes_only_under_the_given_site_dir(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        opp = _opportunity()

        export_opportunities([opp], site_dir=site_dir, today=date(2026, 7, 19))

        assert (site_dir / "src" / "data" / "opportunities.json").exists()
        assert (site_dir / "src" / "data" / "scrape-meta.json").exists()
        # Nothing written anywhere else under tmp_path.
        written_files = sorted(p for p in tmp_path.rglob("*") if p.is_file())
        assert written_files == sorted(
            [
                site_dir / "src" / "data" / "opportunities.json",
                site_dir / "src" / "data" / "scrape-meta.json",
            ]
        )

    def test_explicit_site_dir_never_consults_config_default(self, tmp_path, monkeypatch):
        site_dir = _site_dir(tmp_path)

        def _boom():
            raise AssertionError("get_site_dir() must not be called when site_dir is explicit")

        monkeypatch.setattr(writer, "get_site_dir", _boom)

        export_opportunities([_opportunity()], site_dir=site_dir, today=date(2026, 7, 19))

    def test_omitted_site_dir_resolves_via_config_get_site_dir(self, tmp_path, monkeypatch):
        fake_site_dir = _site_dir(tmp_path)
        monkeypatch.setattr(writer, "get_site_dir", lambda: fake_site_dir)

        export_opportunities([_opportunity()], today=date(2026, 7, 19))

        assert (fake_site_dir / "src" / "data" / "opportunities.json").exists()


class TestSiteDirErrors:
    def test_missing_site_dir_raises_a_clear_error(self, tmp_path):
        missing = tmp_path / "does-not-exist"

        with pytest.raises(RuntimeError, match="site_dir"):
            export_opportunities([_opportunity()], site_dir=missing, today=date(2026, 7, 19))

    def test_missing_site_dir_writes_nothing(self, tmp_path):
        missing = tmp_path / "does-not-exist"

        with pytest.raises(RuntimeError):
            export_opportunities([_opportunity()], site_dir=missing, today=date(2026, 7, 19))

        assert not missing.exists()

    def test_data_path_occupied_by_a_file_raises_a_clear_error(self, tmp_path):
        site_dir = tmp_path / "stem-ecosystem"
        (site_dir / "src").mkdir(parents=True)
        # `src/data` is a plain file here, not a directory -- simulates an
        # unwritable/broken site checkout without relying on OS
        # permission bits (which root can bypass in some CI sandboxes).
        (site_dir / "src" / "data").write_text("not a directory")

        with pytest.raises(RuntimeError, match="site_dir"):
            export_opportunities([_opportunity()], site_dir=site_dir, today=date(2026, 7, 19))
