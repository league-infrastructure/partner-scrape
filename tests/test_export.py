"""Tests for partner_scrape.export.writer: the Site Export entry point.

Every test passes an explicit `today` -- no test relies on the real
system clock (see writer.py's module docstring and sprint.md's Test
Strategy: "no live HTTP ... ever").

Sprint 020 ticket 003 added a second, similarly-defaulting `own_data_dir`
parameter to `export_opportunities()`, alongside an original write into
a sibling `stem-ecosystem` checkout's `site_dir`. Sprint 025 ticket 003
removed that `site_dir` write (and the parameter itself) entirely --
`own_data_dir` is now the function's sole write target. Every test in
this file that used to pass an explicit `tmp_path`-backed `site_dir`
now either drops it (when the test only cares about the returned
payload) or passes an explicit `tmp_path`-backed `own_data_dir` and
inspects that instead (when the test cares about what's on disk). The
module-level `_own_data_dir_default` autouse fixture below pins
`own_data_dir`'s *default* resolution to a throwaway directory for
every test in this file, so a test that never passes `own_data_dir`
explicitly still can't reach this repo's real `data/` directory
(mirrors `test_cli.py`'s `_cache_dir` autouse fixture, which pins
`SITE_DIR` the same way for the same reason).
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
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


@pytest.fixture(autouse=True)
def _own_data_dir_default(tmp_path_factory, monkeypatch):
    """Pin `writer.get_own_data_dir()`'s resolution to a throwaway
    directory for every test in this file (sprint 020 ticket 003).

    `own_data_dir` resolves via a `config` accessor when omitted --
    `config.get_own_data_dir()` always returns this repo's real `data/`
    directory (`DEFAULT_OWN_DATA_DIR` is "not overridable via
    environment variable" by design). A test that never passes
    `own_data_dir` explicitly would otherwise auto-create and write
    real files into this repo's actual `data/` directory on every test
    run -- contradicting sprint.md's Test Strategy ("Hermetic
    throughout ... tests pass an explicit tmp_path, never the real
    default").

    Deliberately resolved via `tmp_path_factory` (a directory outside
    the current test's own `tmp_path` tree), not `tmp_path` itself --
    `TestOwnDataDirIsolation.test_writes_only_under_the_given_own_data_dir`
    asserts the *exact* set of files written under `tmp_path`, so this
    default must land outside that tree or it would inflate that count.
    Resolved once per test (not inside the lambda) so every call to
    `get_own_data_dir()` within a single test returns the same path,
    matching real usage.
    """
    fake_own_data_dir = tmp_path_factory.mktemp("own-data-default")
    monkeypatch.setattr(writer, "get_own_data_dir", lambda: fake_own_data_dir)


class TestCurrentUpcomingFilter:
    def test_end_date_before_today_is_excluded(self):
        opp = _opportunity(
            date_start="2026-07-01T09:00:00-07:00",
            date_end="2026-07-18T09:00:00-07:00",
        )

        payload = export_opportunities([opp], today=date(2026, 7, 19))

        assert payload == []

    def test_start_date_before_today_with_no_end_date_is_excluded(self):
        opp = _opportunity(date_start="2026-07-18T09:00:00-07:00", date_end="")

        payload = export_opportunities([opp], today=date(2026, 7, 19))

        assert payload == []

    def test_undated_opportunity_is_excluded(self):
        opp = _opportunity(date_start="", date_end="")

        payload = export_opportunities([opp], today=date(2026, 7, 19))

        assert payload == []

    def test_end_date_today_is_included(self):
        opp = _opportunity(
            date_start="2026-07-01T09:00:00-07:00",
            date_end="2026-07-19T09:00:00-07:00",
        )

        payload = export_opportunities([opp], today=date(2026, 7, 19))

        assert len(payload) == 1

    def test_end_date_after_today_is_included(self):
        opp = _opportunity(
            date_start="2026-07-01T09:00:00-07:00",
            date_end="2026-08-01T09:00:00-07:00",
        )

        payload = export_opportunities([opp], today=date(2026, 7, 19))

        assert len(payload) == 1

    def test_start_date_today_or_later_with_no_end_date_is_included(self):
        opp = _opportunity(date_start="2026-07-19T09:00:00-07:00", date_end="")

        payload = export_opportunities([opp], today=date(2026, 7, 19))

        assert len(payload) == 1

    def test_mixed_past_and_upcoming_only_upcoming_survive(self):
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

        payload = export_opportunities([past, upcoming], today=date(2026, 7, 19))

        assert [o["title"] for o in payload] == ["Upcoming Event"]


class TestDSTBoundaryPartitioning:
    """Regression for sprint 012 issue 19: `is_current_or_upcoming`
    compares only `date_str[:10]` (the date portion) of `date_start`/
    `date_end`, never the offset suffix (`export/writer.py`, confirmed
    by inspection), so the DST-aware offset fix in `normalize/run.py`'s
    `_iso()` changes no `export/` filtering behavior -- only the
    offset's own correctness. These tests exercise
    `is_current_or_upcoming` directly (no `export_opportunities`/
    own_data_dir needed) against an `Opportunity` dated exactly on a
    DST-transition boundary date, on each side of `today`, and confirm
    the partition is unaffected by which offset (`-07:00` vs `-08:00`)
    the string carries.
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

    def test_no_deadline_internship_with_past_start_is_included(self):
        """Would be wrongly excluded under the pre-ticket
        `date_end or date_start >= today` rule."""
        opp = _opportunity(
            date_start="2026-06-19T09:00:00-07:00",  # 30 days before `today` below
            date_end="",
            opportunity_type=WORK_BASED_LEARNING_TYPE,
        )

        payload = export_opportunities([opp], today=date(2026, 7, 19))

        assert len(payload) == 1

    def test_future_deadline_internship_is_included(self):
        opp = _opportunity(
            date_start="2026-06-19T09:00:00-07:00",
            date_end="2026-08-01T09:00:00-07:00",
            opportunity_type=WORK_BASED_LEARNING_TYPE,
        )

        payload = export_opportunities([opp], today=date(2026, 7, 19))

        assert len(payload) == 1

    def test_past_deadline_internship_is_excluded(self):
        opp = _opportunity(
            date_start="2026-06-19T09:00:00-07:00",
            date_end="2026-07-01T09:00:00-07:00",
            opportunity_type=WORK_BASED_LEARNING_TYPE,
        )

        payload = export_opportunities([opp], today=date(2026, 7, 19))

        assert payload == []

    def test_ordinary_event_with_past_start_and_no_end_is_still_excluded(self):
        """Guards against a partition bug that accidentally applies the
        internship rule to `opportunity_type="Out-of-school Programs"`
        (the default) too -- must keep matching
        `TestCurrentUpcomingFilter`'s equivalent, non-internship case."""
        opp = _opportunity(
            date_start="2026-06-19T09:00:00-07:00",
            date_end="",
            opportunity_type="Out-of-school Programs",
        )

        payload = export_opportunities([opp], today=date(2026, 7, 19))

        assert payload == []


class TestDeadlineFirstCurrentUpcomingFilterGeneralization:
    """`DEADLINE_FIRST_TYPES` (sprint 015 ticket 007) generalizes the
    Work-based Learning currency rule to every member of the set, not
    only `WORK_BASED_LEARNING_TYPE` -- these mirror
    `TestInternshipCurrentUpcomingFilter`'s three cases exactly, for
    `opportunity_type="Competitions"`, to prove the rule is genuinely
    shared rather than re-hardcoded for a second string."""

    def test_competitions_no_deadline_with_past_start_is_included(self):
        """Would be wrongly excluded under the ordinary
        `date_end or date_start >= today` rule."""
        opp = _opportunity(
            date_start="2026-06-19T09:00:00-07:00",  # 30 days before `today` below
            date_end="",
            opportunity_type="Competitions",
        )

        payload = export_opportunities([opp], today=date(2026, 7, 19))

        assert len(payload) == 1

    def test_competitions_future_deadline_with_past_start_is_included(self):
        opp = _opportunity(
            date_start="2026-06-19T09:00:00-07:00",
            date_end="2026-08-01T09:00:00-07:00",
            opportunity_type="Competitions",
        )

        payload = export_opportunities([opp], today=date(2026, 7, 19))

        assert len(payload) == 1

    def test_competitions_past_deadline_is_excluded(self):
        opp = _opportunity(
            date_start="2026-06-19T09:00:00-07:00",
            date_end="2026-07-01T09:00:00-07:00",
            opportunity_type="Competitions",
        )

        payload = export_opportunities([opp], today=date(2026, 7, 19))

        assert payload == []

    def test_competitions_no_deadline_with_far_past_start_is_excluded(self):
        """Regression for issue 61 / sprint 020 ticket 001: reproduces the
        exact reported record shape -- "2nd Innovation in Women's Health
        Pitch Competition" (`opportunity_type="Competitions"`, `date_start`
        2024-12-01, no `date_end`), ~595 days before this test's `today`,
        comfortably past `_DEADLINE_FIRST_STALE_POSTING_DAYS` (365). Before
        this ticket's fix, the no-deadline-still-open rule had no upper
        bound and this record exported as perpetually current."""
        opp = _opportunity(
            title="2nd Innovation in Women's Health Pitch Competition",
            date_start="2024-12-01T09:00:00-08:00",
            date_end="",
            opportunity_type="Competitions",
        )

        payload = export_opportunities([opp], today=date(2026, 7, 19))

        assert payload == []

    def test_competitions_no_deadline_start_exactly_at_staleness_boundary_is_included(
        self,
    ):
        """`date_start` exactly `_DEADLINE_FIRST_STALE_POSTING_DAYS` (365)
        days before `today` is still within the window (`>=` cutoff, not
        `>`)."""
        opp = _opportunity(
            date_start="2025-07-19T09:00:00-07:00",  # exactly 365 days before today below
            date_end="",
            opportunity_type="Competitions",
        )

        payload = export_opportunities([opp], today=date(2026, 7, 19))

        assert len(payload) == 1

    def test_competitions_no_deadline_start_one_day_past_staleness_boundary_is_excluded(
        self,
    ):
        """`date_start` one day older than the 365-day window falls
        outside it."""
        opp = _opportunity(
            date_start="2025-07-18T09:00:00-07:00",  # 366 days before today below
            date_end="",
            opportunity_type="Competitions",
        )

        payload = export_opportunities([opp], today=date(2026, 7, 19))

        assert payload == []


class TestFundingOpportunitiesDeadlineFirst:
    """(Sprint 027, issue 28 item 4, SUC-035) `DEADLINE_FIRST_TYPES` gains
    a third member, `"Funding Opportunities"`, for the SD Foundation
    Community Scholarship (`kind="program"`) -- proves the extension
    reaches `export/writer.py` with no code change there, since
    `is_current_or_upcoming()` already branches on `DEADLINE_FIRST_TYPES`
    membership generically."""

    def test_funding_opportunities_future_deadline_is_kept_current(self):
        opp = _opportunity(
            date_start="2026-06-19T09:00:00-07:00",
            date_end="2026-12-01T00:00:00-08:00",
            opportunity_type="Funding Opportunities",
        )

        payload = export_opportunities([opp], today=date(2026, 9, 1))

        assert len(payload) == 1

    def test_funding_opportunities_past_deadline_is_excluded(self):
        opp = _opportunity(
            date_start="2026-01-01T09:00:00-08:00",
            date_end="2026-08-01T00:00:00-07:00",
            opportunity_type="Funding Opportunities",
        )

        payload = export_opportunities([opp], today=date(2026, 9, 1))

        assert payload == []


class TestExportSortOrder:
    """`export_opportunities`'s sort key (sprint 015 ticket 007): a
    `DEADLINE_FIRST_TYPES` record sorts by `date_end` (its deadline), not
    the possibly-stale `date_start`; every other record keeps sorting by
    `date_start`, unchanged."""

    def test_deadline_first_record_sorts_by_date_end_not_stale_date_start(self):
        """A winter-posted internship with a later summer deadline must
        sort near other near-term deadlines by that deadline, not get
        pinned to the top of the list by its earlier, stale date_start
        (issue 27's "Dec-Mar deadlines for Jun-Aug programs in winter"
        scenario)."""
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

        payload = export_opportunities([deadline_first, ordinary], today=date(2026, 1, 2))

        # `ordinary` sorts by its date_start (March); `deadline_first`
        # sorts by its later date_end (June) rather than its earlier,
        # stale date_start (January) -- so `ordinary` comes first.
        assert [o["title"] for o in payload] == ["Spring Event", "Winter-Posted Internship"]

    def test_non_deadline_first_records_still_sort_by_date_start(self):
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

        payload = export_opportunities([later, earlier], today=date(2026, 1, 2))

        assert [o["title"] for o in payload] == ["Earlier Event", "Later Event"]


class TestSlugDedup:
    def test_colliding_slugs_get_disambiguating_suffix_neither_dropped(self):
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

        payload = export_opportunities([a, b], today=date(2026, 7, 19))

        slugs = [o["slug"] for o in payload]
        assert len(payload) == 2
        assert len(set(slugs)) == 2, "colliding slugs must be disambiguated, not dropped"
        assert "farm_camp_20260801" in slugs
        assert "farm_camp_20260801_2" in slugs
        titles = {o["title"] for o in payload}
        assert titles == {"Farm Camp Session A", "Farm Camp Session B"}

    def test_three_way_collision_each_gets_a_distinct_suffix(self):
        events = [
            _opportunity(
                slug="farm_camp_20260801",
                title=f"Session {i}",
                date_start=f"2026-08-0{i}T09:00:00-07:00",
            )
            for i in (1, 2, 3)
        ]

        payload = export_opportunities(events, today=date(2026, 7, 19))

        slugs = {o["slug"] for o in payload}
        assert slugs == {
            "farm_camp_20260801",
            "farm_camp_20260801_2",
            "farm_camp_20260801_3",
        }

    def test_slugs_from_different_partners_with_no_link_can_collide_and_still_get_disambiguated(
        self,
    ):
        """Reflects the new slug rule directly: `normalize.run()` no
        longer includes an org/partner prefix in the slug (sprint 009
        ticket 002), so two different partners' same-titled, same-day,
        link-less events now arrive at `export_opportunities` with an
        *identical* slug more often than the old truncation-collision
        case did. `_dedupe_slugs` must disambiguate regardless of why
        the slugs collided."""
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

        payload = export_opportunities([a, b], today=date(2026, 7, 19))

        slugs = [o["slug"] for o in payload]
        assert len(payload) == 2
        assert len(set(slugs)) == 2
        assert "community_cleanup_20260801" in slugs
        assert "community_cleanup_20260801_2" in slugs


class TestSiteSchemaShape:
    def test_written_json_has_exact_site_schema_field_set(self, tmp_path):
        own_data_dir = tmp_path / "own-data"
        opp = _opportunity(sources=frozenset({"tec_source", "wp_source"}))

        payload = export_opportunities([opp], today=date(2026, 7, 19), own_data_dir=own_data_dir)

        assert len(payload) == 1
        assert set(payload[0].keys()) == _EXPECTED_SITE_FIELDS
        assert "sources" not in payload[0]

        written = json.loads((own_data_dir / "opportunities.json").read_text())
        assert len(written) == 1
        assert set(written[0].keys()) == _EXPECTED_SITE_FIELDS

    def test_partner_id_none_serializes_to_null(self, tmp_path):
        own_data_dir = tmp_path / "own-data"
        opp = _opportunity(partner_id=None)

        export_opportunities([opp], today=date(2026, 7, 19), own_data_dir=own_data_dir)

        written = json.loads((own_data_dir / "opportunities.json").read_text())
        assert written[0]["partner_id"] is None

    def test_field_types_match_spec_lists_stay_lists_strings_stay_strings(self, tmp_path):
        own_data_dir = tmp_path / "own-data"
        opp = _opportunity(
            age_grade_level=["Family"],
            areas_of_interest=["Biology / LifeSciences"],
            time_of_day=["Morning"],
        )

        export_opportunities([opp], today=date(2026, 7, 19), own_data_dir=own_data_dir)

        written = json.loads((own_data_dir / "opportunities.json").read_text())[0]
        assert isinstance(written["age_grade_level"], list)
        assert isinstance(written["areas_of_interest"], list)
        assert isinstance(written["time_of_day"], list)
        assert isinstance(written["slug"], str)
        assert isinstance(written["title"], str)

    def test_image_src_is_exported_like_logo_src(self):
        """`image_src` (sprint 008 ticket 008, issue 19) is exported
        automatically -- `_SITE_SCHEMA_FIELDS` is derived from
        `fields(Opportunity)`, so no writer.py change is needed for a
        populated value to reach `opportunities.json`."""
        opp = _opportunity(image_src="a1b2c3d4e5f6a7b8.jpg")

        payload = export_opportunities([opp], today=date(2026, 7, 19))

        assert payload[0]["image_src"] == "a1b2c3d4e5f6a7b8.jpg"

    def test_eligibility_is_exported_like_financial_support_and_ngss_aligned(self):
        """`eligibility` (sprint 015 ticket 008, issue 27 item 3) is
        exported automatically -- same mechanism as `image_src` above,
        proving no `writer.py` code change was needed, only this
        test-coverage extension, for `SITE_SCHEMA_FIELDS`/`to_json_dict`
        to pick up the new `Opportunity` field."""
        opp = _opportunity(eligibility="Open only to nine named partner schools")

        payload = export_opportunities([opp], today=date(2026, 7, 19))

        assert payload[0]["eligibility"] == "Open only to nine named partner schools"

    def test_eligibility_defaults_to_empty_string_when_unset(self):
        """No regression for the ~120 sources that never set
        `taxonomy_defaults.eligibility` -- `Opportunity.eligibility`'s
        own dataclass default (`""`) round-trips through the export
        unchanged."""
        opp = _opportunity()

        payload = export_opportunities([opp], today=date(2026, 7, 19))

        assert payload[0]["eligibility"] == ""


class TestScrapeMeta:
    def test_last_updated_changes_between_runs(self, tmp_path, monkeypatch):
        own_data_dir = tmp_path / "own-data"
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

        export_opportunities([_opportunity()], today=date(2026, 7, 19), own_data_dir=own_data_dir)
        first = json.loads((own_data_dir / "scrape-meta.json").read_text())

        export_opportunities([_opportunity()], today=date(2026, 7, 19), own_data_dir=own_data_dir)
        second = json.loads((own_data_dir / "scrape-meta.json").read_text())

        assert first["last_updated"] == "2026-07-19T12:00:00Z"
        assert second["last_updated"] == "2026-07-19T12:05:00Z"
        assert first["last_updated"] != second["last_updated"]

    def test_last_updated_written_even_when_opportunity_set_is_unchanged(
        self, tmp_path, monkeypatch
    ):
        own_data_dir = tmp_path / "own-data"
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

        export_opportunities(
            [same_opportunity], today=date(2026, 7, 19), own_data_dir=own_data_dir
        )
        first_opps = (own_data_dir / "opportunities.json").read_text()
        first_meta = json.loads((own_data_dir / "scrape-meta.json").read_text())

        export_opportunities(
            [same_opportunity], today=date(2026, 7, 19), own_data_dir=own_data_dir
        )
        second_opps = (own_data_dir / "opportunities.json").read_text()
        second_meta = json.loads((own_data_dir / "scrape-meta.json").read_text())

        assert first_opps == second_opps
        assert first_meta["last_updated"] != second_meta["last_updated"]


class TestScrapeMetaRegions:
    """Sprint 033, issue 34: `scrape-meta.json` gains a `"regions"` key
    -- a per-region count over the exported current/upcoming payload,
    computed from `Opportunity.region` (already finished, not
    re-derived)."""

    def test_regions_key_counts_by_region(self, tmp_path):
        own_data_dir = tmp_path / "own-data"
        opportunities = [
            _opportunity(slug="a", region="South Bay"),
            _opportunity(slug="b", region="South Bay"),
            _opportunity(slug="c", region="East County"),
            _opportunity(slug="d", region=""),
        ]

        export_opportunities(
            opportunities, today=date(2026, 7, 19), own_data_dir=own_data_dir
        )

        meta = json.loads((own_data_dir / "scrape-meta.json").read_text())
        assert meta["regions"] == {"South Bay": 2, "East County": 1, "unclassified": 1}

    def test_unclassified_bucket_for_empty_region_not_dropped(self, tmp_path):
        own_data_dir = tmp_path / "own-data"
        opportunities = [_opportunity(slug="a", region="")]

        export_opportunities(
            opportunities, today=date(2026, 7, 19), own_data_dir=own_data_dir
        )

        meta = json.loads((own_data_dir / "scrape-meta.json").read_text())
        assert meta["regions"] == {"unclassified": 1}

    def test_regions_only_counts_current_upcoming_opportunities(self, tmp_path):
        own_data_dir = tmp_path / "own-data"
        current = _opportunity(
            slug="current", region="South Bay", date_start="2026-07-19T09:00:00-07:00"
        )
        past = _opportunity(
            slug="past", region="East County", date_start="2026-01-01T09:00:00-07:00"
        )

        export_opportunities(
            [current, past], today=date(2026, 7, 19), own_data_dir=own_data_dir
        )

        meta = json.loads((own_data_dir / "scrape-meta.json").read_text())
        assert meta["regions"] == {"South Bay": 1}

    def test_last_updated_key_unaffected_by_the_regions_addition(self, tmp_path):
        own_data_dir = tmp_path / "own-data"

        export_opportunities(
            [_opportunity(region="South Bay")], today=date(2026, 7, 19), own_data_dir=own_data_dir
        )

        meta = json.loads((own_data_dir / "scrape-meta.json").read_text())
        assert "last_updated" in meta
        assert isinstance(meta["last_updated"], str)


class TestDryRun:
    def test_dry_run_writes_nothing_but_returns_the_payload(self):
        opp = _opportunity()

        payload = export_opportunities([opp], today=date(2026, 7, 19), dry_run=True)

        assert len(payload) == 1

    def test_dry_run_payload_matches_non_dry_run_payload(self):
        opp = _opportunity()

        dry_payload = export_opportunities([opp], today=date(2026, 7, 19), dry_run=True)
        real_payload = export_opportunities([opp], today=date(2026, 7, 19))

        assert dry_payload == real_payload

    def test_dry_run_computes_without_error_for_region_bearing_opportunities(self, tmp_path):
        """Sprint 033, issue 34: `region` (an internal, non-schema field)
        must not break `dry_run` -- no `scrape-meta.json`/`"regions"`
        computation is exposed by `dry_run`'s return value today (it
        stays the opportunities-only payload, unchanged), but computing
        it must not raise, and no file is written."""
        own_data_dir = tmp_path / "own-data"
        opportunities = [
            _opportunity(slug="a", region="South Bay"),
            _opportunity(slug="b", region=""),
        ]

        payload = export_opportunities(
            opportunities, today=date(2026, 7, 19), dry_run=True, own_data_dir=own_data_dir
        )

        assert len(payload) == 2
        assert "region" not in payload[0]
        assert not (own_data_dir / "scrape-meta.json").exists()


class TestOwnDataDirIsolation:
    """Sprint 025 ticket 003 (issue 21, "stop writing to the
    stem-ecosystem checkout"): `export_opportunities()` no longer
    accepts a `site_dir` parameter and never writes into a sibling
    `stem-ecosystem` checkout's `src/data/` -- `own_data_dir` is the
    sole write target. Inverts this class's pre-ticket
    `test_writes_only_under_the_given_site_dir` (which asserted the
    `site_dir` write happened) into a proof that no such write happens,
    alongside the equivalent isolation proof for `own_data_dir` itself.
    """

    def test_writes_only_under_the_given_own_data_dir(self, tmp_path):
        own_data_dir = tmp_path / "own-data"
        opp = _opportunity()

        export_opportunities([opp], today=date(2026, 7, 19), own_data_dir=own_data_dir)

        assert (own_data_dir / "opportunities.json").exists()
        assert (own_data_dir / "scrape-meta.json").exists()
        # Nothing written anywhere else under tmp_path.
        written_files = sorted(p for p in tmp_path.rglob("*") if p.is_file())
        assert written_files == sorted(
            [
                own_data_dir / "opportunities.json",
                own_data_dir / "scrape-meta.json",
            ]
        )

    def test_no_site_dir_shaped_write_occurs_anywhere(self, tmp_path):
        """Direct inversion of the pre-ticket `site_dir` write proof: a
        `src/data/opportunities.json`/`scrape-meta.json` pair -- the
        removed `site_dir` write's exact old shape -- must never be
        created, confirmed even when a directory that happens to look
        like an old `site_dir` checkout already exists under
        `tmp_path`."""
        stale_site_dir_lookalike = tmp_path / "stem-ecosystem"
        (stale_site_dir_lookalike / "src" / "data").mkdir(parents=True)
        own_data_dir = tmp_path / "own-data"

        export_opportunities(
            [_opportunity()], today=date(2026, 7, 19), own_data_dir=own_data_dir
        )

        assert not (stale_site_dir_lookalike / "src" / "data" / "opportunities.json").exists()
        assert not (stale_site_dir_lookalike / "src" / "data" / "scrape-meta.json").exists()


class TestOwnDataDirErrors:
    """Sprint 025 ticket 003: with the `site_dir` write removed,
    `own_data_dir`'s own failure path -- previously untested because a
    `site_dir` failure always propagated first (see this module's old
    "The two write targets are not symmetric" docstring section, now
    removed) -- is the only failure path `export_opportunities` has
    left, and gets its own direct test."""

    def test_own_data_dir_occupied_by_a_file_raises_a_clear_error(self, tmp_path):
        # own_data_dir itself is a plain file, not a directory --
        # `Path.mkdir(parents=True, exist_ok=True)` cannot succeed here
        # even with exist_ok=True (that only forgives an *existing
        # directory*, not an existing file) -- simulates an
        # unwritable/broken own_data_dir without relying on OS
        # permission bits (which root can bypass in some CI sandboxes).
        own_data_dir = tmp_path / "own-data"
        own_data_dir.write_text("not a directory")

        with pytest.raises(RuntimeError, match="own_data_dir"):
            export_opportunities(
                [_opportunity()], today=date(2026, 7, 19), own_data_dir=own_data_dir
            )


class TestOwnDataDirPublish:
    """Sprint 020 ticket 003 (issue 60) added this write path -- the
    same payload and `scrape-meta.json` timestamp written into
    partner-scrape's own `data/` directory via `config.get_own_data_dir()`.
    Sprint 025 ticket 003 removed the sibling `stem-ecosystem` write this
    used to run alongside (see `TestOwnDataDirIsolation` above for the
    isolation/inversion proof) -- `own_data_dir` is now this function's
    only write target, and these tests cover its own defaulting,
    auto-creation, and dry_run behavior in isolation.
    """

    def test_omitted_own_data_dir_resolves_via_config_get_own_data_dir(
        self, tmp_path, monkeypatch
    ):
        fake_own_data_dir = tmp_path / "fake-own-data"
        monkeypatch.setattr(writer, "get_own_data_dir", lambda: fake_own_data_dir)

        export_opportunities([_opportunity()], today=date(2026, 7, 19))

        assert (fake_own_data_dir / "opportunities.json").exists()
        assert (fake_own_data_dir / "scrape-meta.json").exists()

    def test_missing_own_data_dir_is_created_automatically_never_raises(self, tmp_path):
        own_data_dir = tmp_path / "does-not-exist-yet" / "nested"
        assert not own_data_dir.exists()

        export_opportunities(
            [_opportunity()], today=date(2026, 7, 19), own_data_dir=own_data_dir
        )

        assert (own_data_dir / "opportunities.json").exists()
        assert (own_data_dir / "scrape-meta.json").exists()

    def test_dry_run_writes_nothing_to_own_data_dir(self, tmp_path):
        own_data_dir = tmp_path / "own-data"

        payload = export_opportunities(
            [_opportunity()], today=date(2026, 7, 19), own_data_dir=own_data_dir, dry_run=True
        )

        assert len(payload) == 1
        assert not own_data_dir.exists()
