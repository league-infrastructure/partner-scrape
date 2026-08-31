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
#: table, plus `image_src` (sprint 008 ticket 008, issue 19). `Opportunity
#: .sources` is deliberately absent -- it is normalize's own cross-source
#: bookkeeping, not part of the site contract.
_EXPECTED_SITE_FIELDS = {
    "slug", "title", "partner_name", "partner_id", "description", "link",
    "availability", "date_start", "date_end", "age_grade_level", "cost_range",
    "time_of_day", "opportunity_type", "areas_of_interest", "specific_attention",
    "financial_support", "ngss_aligned", "location", "latitude", "longitude",
    "contact_name", "contact_email", "contact_phone", "logo_src", "eligibility",
    "image_src",
}


def _site_dir(tmp_path: Path) -> Path:
    """A tmp_path-backed stand-in for the sibling stem-ecosystem repo,
    with `src/data` pre-created (matching a real checkout's layout)."""
    site_dir = tmp_path / "stem-ecosystem"
    (site_dir / "src" / "data").mkdir(parents=True)
    return site_dir


def _opportunity(
    slug: str = "farm_tour_20260801",
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
        image_src="",
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


class TestDSTBoundaryPartitioning:
    """Regression for sprint 012 issue 19: `is_current_or_upcoming`
    compares only `date_str[:10]` (the date portion) of `date_start`/
    `date_end`, never the offset suffix (`export/writer.py`, confirmed
    by inspection), so the DST-aware offset fix in `normalize/run.py`'s
    `_iso()` changes no `export/` filtering behavior -- only the
    offset's own correctness. These tests exercise
    `is_current_or_upcoming` directly (no `export_opportunities`/site_dir
    needed) against an `Opportunity` dated exactly on a DST-transition
    boundary date, on each side of `today`, and confirm the partition is
    unaffected by which offset (`-07:00` vs `-08:00`) the string carries.
    """

    def test_record_on_november_fall_back_date_is_current_on_the_boundary_day(self):
        opp = _opportunity(
            date_start="2026-10-01T09:00:00-07:00",
            date_end="2026-11-01T01:30:00-07:00",  # the ambiguous fall-back hour
        )

        assert writer.is_current_or_upcoming(opp, today=date(2026, 11, 1)) is True

    def test_record_on_november_fall_back_date_is_excluded_the_day_after(self):
        opp = _opportunity(
            date_start="2026-10-01T09:00:00-07:00",
            date_end="2026-11-01T01:30:00-07:00",
        )

        assert writer.is_current_or_upcoming(opp, today=date(2026, 11, 2)) is False

    def test_record_on_march_spring_forward_date_is_current_on_the_boundary_day(self):
        opp = _opportunity(
            date_start="2026-02-01T09:00:00-08:00",
            date_end="2026-03-08T02:30:00-08:00",  # the nonexistent spring-forward hour
        )

        assert writer.is_current_or_upcoming(opp, today=date(2026, 3, 8)) is True

    def test_record_on_march_spring_forward_date_is_excluded_the_day_after(self):
        opp = _opportunity(
            date_start="2026-02-01T09:00:00-08:00",
            date_end="2026-03-08T02:30:00-08:00",
        )

        assert writer.is_current_or_upcoming(opp, today=date(2026, 3, 9)) is False


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


class TestDeadlineFirstCurrentUpcomingFilterGeneralization:
    """`DEADLINE_FIRST_TYPES` (sprint 015 ticket 007) generalizes the
    Work-based Learning currency rule to every member of the set, not
    only `WORK_BASED_LEARNING_TYPE` -- these mirror
    `TestInternshipCurrentUpcomingFilter`'s three cases exactly, for
    `opportunity_type="Competitions"`, to prove the rule is genuinely
    shared rather than re-hardcoded for a second string."""

    def test_competitions_no_deadline_with_past_start_is_included(self, tmp_path):
        """Would be wrongly excluded under the ordinary
        `date_end or date_start >= today` rule."""
        site_dir = _site_dir(tmp_path)
        opp = _opportunity(
            date_start="2026-06-19T09:00:00-07:00",  # 30 days before `today` below
            date_end="",
            opportunity_type="Competitions",
        )

        payload = export_opportunities([opp], site_dir=site_dir, today=date(2026, 7, 19))

        assert len(payload) == 1

    def test_competitions_future_deadline_with_past_start_is_included(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        opp = _opportunity(
            date_start="2026-06-19T09:00:00-07:00",
            date_end="2026-08-01T09:00:00-07:00",
            opportunity_type="Competitions",
        )

        payload = export_opportunities([opp], site_dir=site_dir, today=date(2026, 7, 19))

        assert len(payload) == 1

    def test_competitions_past_deadline_is_excluded(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        opp = _opportunity(
            date_start="2026-06-19T09:00:00-07:00",
            date_end="2026-07-01T09:00:00-07:00",
            opportunity_type="Competitions",
        )

        payload = export_opportunities([opp], site_dir=site_dir, today=date(2026, 7, 19))

        assert payload == []


class TestExportSortOrder:
    """`export_opportunities`'s sort key (sprint 015 ticket 007): a
    `DEADLINE_FIRST_TYPES` record sorts by `date_end` (its deadline), not
    the possibly-stale `date_start`; every other record keeps sorting by
    `date_start`, unchanged."""

    def test_deadline_first_record_sorts_by_date_end_not_stale_date_start(self, tmp_path):
        """A winter-posted internship with a later summer deadline must
        sort near other near-term deadlines by that deadline, not get
        pinned to the top of the list by its earlier, stale date_start
        (issue 27's "Dec-Mar deadlines for Jun-Aug programs in winter"
        scenario)."""
        site_dir = _site_dir(tmp_path)
        deadline_first = _opportunity(
            slug="winter_posted_internship",
            title="Winter-Posted Internship",
            date_start="2026-01-01T09:00:00-08:00",
            date_end="2026-06-01T09:00:00-07:00",
            opportunity_type=WORK_BASED_LEARNING_TYPE,
        )
        ordinary = _opportunity(
            slug="spring_event_20260315",
            title="Spring Event",
            date_start="2026-03-15T09:00:00-07:00",
            date_end="",
            opportunity_type="Out-of-school Programs",
        )

        payload = export_opportunities(
            [deadline_first, ordinary], site_dir=site_dir, today=date(2026, 1, 2)
        )

        # `ordinary` sorts by its date_start (March); `deadline_first`
        # sorts by its later date_end (June) rather than its earlier,
        # stale date_start (January) -- so `ordinary` comes first.
        assert [o["title"] for o in payload] == ["Spring Event", "Winter-Posted Internship"]

    def test_non_deadline_first_records_still_sort_by_date_start(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        earlier = _opportunity(
            slug="earlier_event_20260201",
            title="Earlier Event",
            date_start="2026-02-01T09:00:00-08:00",
            date_end="",
        )
        later = _opportunity(
            slug="later_event_20260301",
            title="Later Event",
            date_start="2026-03-01T09:00:00-08:00",
            date_end="",
        )

        payload = export_opportunities(
            [later, earlier], site_dir=site_dir, today=date(2026, 1, 2)
        )

        assert [o["title"] for o in payload] == ["Earlier Event", "Later Event"]


class TestSlugDedup:
    def test_colliding_slugs_get_disambiguating_suffix_neither_dropped(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        a = _opportunity(
            slug="farm_camp_20260801",
            title="Farm Camp Session A",
            date_start="2026-08-01T09:00:00-07:00",
        )
        b = _opportunity(
            slug="farm_camp_20260801",
            title="Farm Camp Session B",
            date_start="2026-08-02T09:00:00-07:00",
        )

        payload = export_opportunities([a, b], site_dir=site_dir, today=date(2026, 7, 19))

        slugs = [o["slug"] for o in payload]
        assert len(payload) == 2
        assert len(set(slugs)) == 2, "colliding slugs must be disambiguated, not dropped"
        assert "farm_camp_20260801" in slugs
        assert "farm_camp_20260801_2" in slugs
        titles = {o["title"] for o in payload}
        assert titles == {"Farm Camp Session A", "Farm Camp Session B"}

    def test_three_way_collision_each_gets_a_distinct_suffix(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        events = [
            _opportunity(
                slug="farm_camp_20260801",
                title=f"Session {i}",
                date_start=f"2026-08-0{i}T09:00:00-07:00",
            )
            for i in (1, 2, 3)
        ]

        payload = export_opportunities(events, site_dir=site_dir, today=date(2026, 7, 19))

        slugs = {o["slug"] for o in payload}
        assert slugs == {
            "farm_camp_20260801",
            "farm_camp_20260801_2",
            "farm_camp_20260801_3",
        }

    def test_slugs_from_different_partners_with_no_link_can_collide_and_still_get_disambiguated(
        self, tmp_path
    ):
        """Reflects the new slug rule directly: `normalize.run()` no
        longer includes an org/partner prefix in the slug (sprint 009
        ticket 002), so two different partners' same-titled, same-day,
        link-less events now arrive at `export_opportunities` with an
        *identical* slug more often than the old truncation-collision
        case did. `_dedupe_slugs` must disambiguate regardless of why
        the slugs collided."""
        site_dir = _site_dir(tmp_path)
        a = _opportunity(
            slug="community_cleanup_20260801",
            title="Community Cleanup",
            partner_name="North Park Alliance",
            date_start="2026-08-01T09:00:00-07:00",
        )
        b = _opportunity(
            slug="community_cleanup_20260801",
            title="Community Cleanup",
            partner_name="South Park Alliance",
            date_start="2026-08-01T09:00:00-07:00",
        )

        payload = export_opportunities([a, b], site_dir=site_dir, today=date(2026, 7, 19))

        slugs = [o["slug"] for o in payload]
        assert len(payload) == 2
        assert len(set(slugs)) == 2
        assert "community_cleanup_20260801" in slugs
        assert "community_cleanup_20260801_2" in slugs


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

    def test_image_src_is_exported_like_logo_src(self, tmp_path):
        """`image_src` (sprint 008 ticket 008, issue 19) is exported
        automatically -- `_SITE_SCHEMA_FIELDS` is derived from
        `fields(Opportunity)`, so no writer.py change is needed for a
        populated value to reach `opportunities.json`."""
        site_dir = _site_dir(tmp_path)
        opp = _opportunity(image_src="a1b2c3d4e5f6a7b8.jpg")

        payload = export_opportunities([opp], site_dir=site_dir, today=date(2026, 7, 19))

        assert payload[0]["image_src"] == "a1b2c3d4e5f6a7b8.jpg"

    def test_eligibility_is_exported_like_financial_support_and_ngss_aligned(self, tmp_path):
        """`eligibility` (sprint 015 ticket 008, issue 27 item 3) is
        exported automatically -- same mechanism as `image_src` above,
        proving no `writer.py` code change was needed, only this
        test-coverage extension, for `SITE_SCHEMA_FIELDS`/`to_json_dict`
        to pick up the new `Opportunity` field."""
        site_dir = _site_dir(tmp_path)
        opp = _opportunity(eligibility="Open only to nine named partner schools")

        payload = export_opportunities([opp], site_dir=site_dir, today=date(2026, 7, 19))

        assert payload[0]["eligibility"] == "Open only to nine named partner schools"

    def test_eligibility_defaults_to_empty_string_when_unset(self, tmp_path):
        """No regression for the ~120 sources that never set
        `taxonomy_defaults.eligibility` -- `Opportunity.eligibility`'s
        own dataclass default (`""`) round-trips through the export
        unchanged."""
        site_dir = _site_dir(tmp_path)
        opp = _opportunity()

        payload = export_opportunities([opp], site_dir=site_dir, today=date(2026, 7, 19))

        assert payload[0]["eligibility"] == ""


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
