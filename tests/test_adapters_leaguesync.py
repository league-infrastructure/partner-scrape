"""Tests for partner_scrape.adapters.leaguesync: the League's own
sync.jtlapp.net query API adapter.

``tests/fixtures/leaguesync/classes_query.json`` and
``tech_clubs_query.json`` are real sample responses captured live from
sync.jtlapp.net (``GET /query?sql=<the adapter's own CLASSES_SQL /
TECH_CLUBS_SQL>``, Bearer-authenticated) during this adapter's build --
real service/occurrence/location and meetup_event/meetup_venue rows,
including two live edge cases worth noting: "Java Online"/"Python
Online"/"League Labs" (virtual classes with a location name but no
lat/long) and both live upcoming tech-club rows having a ``venue_id``
that has no matching ``meetup_venues`` row (``venue_name`` etc. all
``null`` via the adapter's ``LEFT JOIN``). ``classes_query.json`` was
re-captured (OOP, 2026-07-20) using ``CLASSES_SQL`` *after* the teacher/
staff/professional-development exclusion was added -- it has 14 rows,
not 15; "Teacher Development" (service_id 357780) is confirmed absent
at the source, not filtered client-side. ``classes_query_malformed.json``
and ``tech_clubs_query_malformed.json`` are hand-authored (not live
data) to exercise per-record error isolation with a controlled bad
record, matching ``adapters/tec.py``'s test convention.

Every test drives the adapter through a fixture Fetcher returning these
canned bodies -- no test here opens a real network socket, per this
project's established adapter test strategy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pytest

from partner_scrape.adapters import run
from partner_scrape.adapters.base import EventRef, RawResponse
from partner_scrape.adapters.leaguesync import (
    CLASSES_SQL,
    DEFAULT_REGISTRATION_URL,
    KIND_CLASSES,
    KIND_TECH_CLUBS,
    TECH_CLUBS_SQL,
    LeagueSyncAdapter,
    _query_url,
)
from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.model import Provenance
from partner_scrape.registry.schema import SourceConfig

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "leaguesync"

API_BASE = "https://sync.jtlapp.net"
CLASSES_URL = _query_url(API_BASE, CLASSES_SQL)
TECH_CLUBS_URL = _query_url(API_BASE, TECH_CLUBS_SQL)
TOKEN = "test-token-abc123"


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text()


def _response(body: str, status: int = 200) -> FetchResponse:
    return FetchResponse(url="", status=status, headers={}, body=body)


@dataclass
class FixtureFetcher:
    """Fetcher test double -- returns canned FetchResponses, no socket.

    A URL absent from ``responses`` raises ``KeyError`` -- a loud
    failure if the adapter under test fetches something it shouldn't.
    Records every call's ``headers`` too, so auth-header tests can
    assert on them directly.
    """

    responses: dict[str, FetchResponse]
    calls: list[tuple[str, dict[str, str] | None]] = field(default_factory=list)

    def get(self, url: str, headers: dict[str, str] | None = None) -> FetchResponse:
        self.calls.append((url, headers))
        return self.responses[url]


def _source(api_base: str = API_BASE) -> SourceConfig:
    return SourceConfig(
        source_id="leaguesync",
        org_name="The LEAGUE of Amazing Programmers",
        adapter_type="leaguesync",
        config={"api_base": api_base},
    )


def _real_fetcher() -> FixtureFetcher:
    return FixtureFetcher(
        {
            CLASSES_URL: _response(_read_fixture("classes_query.json")),
            TECH_CLUBS_URL: _response(_read_fixture("tech_clubs_query.json")),
        }
    )


def _extract_classes_only() -> list:
    """Extract only the CLASSES-kind Events from the real fixture,
    bypassing the combined classes+tech_clubs list ``run()`` returns --
    both kinds' ``external_id``s are plain numeric-string IDs, so
    filtering the combined list by shape can't tell them apart; calling
    ``extract()`` directly on just the classes ``RawResponse`` can.
    """
    adapter = LeagueSyncAdapter()
    raw = RawResponse(
        ref=EventRef(url=CLASSES_URL, context={"kind": KIND_CLASSES}),
        status=200,
        body=_read_fixture("classes_query.json"),
    )
    return list(adapter.extract(raw, _source()))


@pytest.fixture(autouse=True)
def _leaguesync_api_key(monkeypatch):
    """Every test needs a token set -- fetch() reads it fresh from the
    environment on every call via config.get_leaguesync_api_key().
    """
    monkeypatch.setenv("LEAGUESYNC_API_KEY", TOKEN)


class TestDiscover:
    def test_returns_exactly_two_refs_classes_then_tech_clubs(self):
        adapter = LeagueSyncAdapter()

        refs = adapter.discover(_source(), fetcher=None)

        assert [r.url for r in refs] == [CLASSES_URL, TECH_CLUBS_URL]
        assert [r.context["kind"] for r in refs] == [KIND_CLASSES, KIND_TECH_CLUBS]

    def test_no_fetcher_call_is_made_by_discover(self):
        # Unlike TEC/Localist, this adapter needs no probe -- both
        # queries are fixed SQL, so discover() must never touch fetcher.
        adapter = LeagueSyncAdapter()

        class ExplodingFetcher:
            def get(self, url, headers=None):
                raise AssertionError("discover() must not call fetcher.get()")

        adapter.discover(_source(), ExplodingFetcher())

    def test_api_base_falls_back_to_config_default_when_source_omits_it(self, monkeypatch):
        monkeypatch.delenv("LEAGUESYNC_URL", raising=False)
        source = SourceConfig(
            source_id="leaguesync",
            org_name="The LEAGUE of Amazing Programmers",
            adapter_type="leaguesync",
            config={},
        )
        adapter = LeagueSyncAdapter()

        refs = adapter.discover(source, fetcher=None)

        assert refs[0].url == CLASSES_URL


class TestAuthHeader:
    def test_fetch_sends_bearer_token_from_config(self):
        adapter = LeagueSyncAdapter()
        fetcher = _real_fetcher()

        adapter.fetch(EventRef(url=CLASSES_URL, context={"kind": KIND_CLASSES}), fetcher)

        assert fetcher.calls == [(CLASSES_URL, {"Authorization": f"Bearer {TOKEN}"})]

    def test_end_to_end_run_sends_the_bearer_header_on_every_fetch(self):
        fetcher = _real_fetcher()

        run(_source(), fetcher)

        called_urls_and_headers = dict(fetcher.calls)
        assert called_urls_and_headers[CLASSES_URL] == {"Authorization": f"Bearer {TOKEN}"}
        assert called_urls_and_headers[TECH_CLUBS_URL] == {"Authorization": f"Bearer {TOKEN}"}


class TestFieldMappingClasses:
    def test_in_person_class_maps_all_documented_fields(self):
        events = run(_source(), _real_fetcher())

        java = next(e for e in events if e.title == "Java Classes")
        assert java.kind == "event"
        assert java.source_id == "leaguesync"
        assert java.external_id == "263387"
        assert java.start == datetime(2026, 7, 22, 22, 30, 0, tzinfo=timezone.utc)
        assert java.location == "Carmel Valley Campus (CV), San Diego"
        assert java.latitude == 32.9474
        assert java.longitude == -117.239
        assert java.categories == ["Group Classes"]
        assert "<" not in java.description
        assert "Learn to program in Java" in java.description
        assert java.registration_url == DEFAULT_REGISTRATION_URL

    def test_virtual_class_has_location_but_no_lat_long(self):
        # Live edge case: "Java Online" resolves to the virtual-learning
        # location, which has a name but null latitude/longitude/city.
        events = run(_source(), _real_fetcher())

        java_online = next(e for e in events if e.title == "Java Online")
        assert java_online.location == "Virtual Learning / Online  (VL)"
        assert java_online.latitude is None
        assert java_online.longitude is None
        assert "latitude" not in java_online.field_provenance
        assert "longitude" not in java_online.field_provenance

    def test_description_falls_back_to_description_short_and_strips_its_html_too(self):
        # Live edge case: "Competitive Robotics Summer Warm Up" has an
        # empty description but a description_short that itself carries
        # HTML (<br>, <ul><li>) -- the fallback must be stripped too,
        # not just the primary description field.
        class_events = _extract_classes_only()

        warm_up = next(e for e in class_events if e.title == "Competitive Robotics Summer Warm Up")
        assert "<" not in warm_up.description
        assert "Hands-on experience with robot design" in warm_up.description

    def test_every_class_gets_the_default_pike13_registration_url(self):
        class_events = _extract_classes_only()

        assert class_events
        assert all(e.registration_url == "https://jtl.pike13.com" for e in class_events)

    def test_one_event_per_service_matches_fixture_row_count(self):
        class_events = _extract_classes_only()

        # classes_query.json has 14 distinct service rows -- one Event
        # each, no client-side grouping needed (the SQL's window
        # function already picked one "next occurrence" row per service).
        # (Was 15 before the teacher/staff/PD exclusion added to
        # CLASSES_SQL removed "Teacher Development" -- see
        # TestTeacherServiceExclusion below.)
        assert len(class_events) == 14
        assert len({e.external_id for e in class_events}) == 14

    def test_every_field_the_adapter_sets_has_leaguesync_provenance_at_full_confidence(self):
        events = run(_source(), _real_fetcher())

        java = next(e for e in events if e.title == "Java Classes")
        assert java.field_provenance
        for prov in java.field_provenance.values():
            assert prov == Provenance(source="leaguesync", confidence=1.0)


class TestFieldMappingTechClubs:
    def test_tech_club_maps_documented_fields(self):
        events = run(_source(), _real_fetcher())

        robot_drivers = [e for e in events if "Robot Drivers" in e.title]
        assert len(robot_drivers) == 2

        first = min(robot_drivers, key=lambda e: e.start)
        assert first.kind == "event"
        assert first.source_id == "leaguesync"
        assert first.external_id == "315533975"
        assert first.start == datetime(2026, 7, 23, 1, 30, 0, tzinfo=timezone.utc)
        assert first.registration_url == (
            "https://www.meetup.com/the-league-tech-club/events/315533975/"
        )
        assert first.image_url == "https://secure-content.meetupstatic.com/images/classic-events/"
        assert "FTC SIM" in first.description

    def test_unmatched_venue_leaves_location_blank(self):
        # Live edge case: both real upcoming tech-club rows reference a
        # venue_id with no matching meetup_venues row.
        events = run(_source(), _real_fetcher())

        robot_drivers = [e for e in events if "Robot Drivers" in e.title]
        for event in robot_drivers:
            assert event.location == ""
            assert "location" not in event.field_provenance
            assert event.latitude is None
            assert event.longitude is None

    def test_every_field_the_adapter_sets_has_leaguesync_provenance_at_full_confidence(self):
        events = run(_source(), _real_fetcher())

        robot_drivers = next(e for e in events if "Robot Drivers" in e.title)
        assert robot_drivers.field_provenance
        for prov in robot_drivers.field_provenance.values():
            assert prov == Provenance(source="leaguesync", confidence=1.0)


class TestKindDefault:
    def test_kind_defaults_to_event_for_every_emitted_record(self):
        events = run(_source(), _real_fetcher())

        assert events
        assert all(e.kind == "event" for e in events)


class TestEndToEnd:
    def test_run_produces_both_classes_and_tech_clubs(self):
        events = run(_source(), _real_fetcher())

        # 14 classes + 2 tech clubs from the real captured fixtures.
        assert len(events) == 16


class TestMalformedRecordIsolation:
    def test_class_with_no_name_is_skipped_valid_row_survives(self):
        fetcher = FixtureFetcher(
            {
                CLASSES_URL: _response(_read_fixture("classes_query_malformed.json")),
                TECH_CLUBS_URL: _response("[]"),
            }
        )

        events = run(_source(), fetcher)

        titles = {e.title for e in events}
        assert titles == {"Synthetic Valid Class"}

    def test_tech_club_with_no_title_is_skipped_valid_row_survives(self):
        fetcher = FixtureFetcher(
            {
                CLASSES_URL: _response("[]"),
                TECH_CLUBS_URL: _response(_read_fixture("tech_clubs_query_malformed.json")),
            }
        )

        events = run(_source(), fetcher)

        titles = {e.title for e in events}
        assert titles == {"Synthetic Valid Tech Club"}


class TestEmptyResponse:
    def test_both_empty_yields_zero_events_and_no_exception(self):
        fetcher = FixtureFetcher(
            {
                CLASSES_URL: _response(_read_fixture("empty_query.json")),
                TECH_CLUBS_URL: _response(_read_fixture("empty_query.json")),
            }
        )

        events = run(_source(), fetcher)

        assert events == []


class TestExtractRobustness:
    def test_non_200_status_returns_no_events_without_raising(self):
        adapter = LeagueSyncAdapter()
        raw = RawResponse(
            ref=EventRef(url=CLASSES_URL, context={"kind": KIND_CLASSES}), status=500, body=""
        )

        assert list(adapter.extract(raw, _source())) == []

    def test_unparseable_json_body_returns_no_events_without_raising(self):
        adapter = LeagueSyncAdapter()
        raw = RawResponse(
            ref=EventRef(url=CLASSES_URL, context={"kind": KIND_CLASSES}),
            status=200,
            body="not json {",
        )

        assert list(adapter.extract(raw, _source())) == []

    def test_non_list_json_shape_returns_no_events_without_raising(self):
        adapter = LeagueSyncAdapter()
        raw = RawResponse(
            ref=EventRef(url=CLASSES_URL, context={"kind": KIND_CLASSES}),
            status=200,
            body='{"unexpected": "shape"}',
        )

        assert list(adapter.extract(raw, _source())) == []


class TestQueryUrlBuilding:
    def test_query_urls_embed_read_only_sql_only(self):
        # sync.jtlapp.net's own contract: SELECT/WITH only. A defensive
        # check that neither query text this adapter sends could ever
        # be a mutation, even if hand-edited carelessly later. Word-
        # bounded so a legitimate column name (e.g. "deleted_at",
        # confirmed live) never false-positives against the "DELETE"
        # keyword check.
        import re

        for sql in (CLASSES_SQL, TECH_CLUBS_SQL):
            stripped = sql.strip().upper()
            assert stripped.startswith("SELECT") or stripped.startswith("WITH")
            for verb in ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "ATTACH"):
                assert re.search(rf"\b{verb}\b", stripped) is None

    def test_query_url_is_correctly_percent_encoded(self):
        url = _query_url("https://sync.jtlapp.net", "SELECT 1 as ok")
        assert url == "https://sync.jtlapp.net/query?sql=SELECT%201%20as%20ok"

    def test_query_url_strips_trailing_slash_on_api_base(self):
        url = _query_url("https://sync.jtlapp.net/", "SELECT 1")
        assert url.startswith("https://sync.jtlapp.net/query?sql=")


# ---------------------------------------------------------------------
# AC (OOP, 2026-07-20): every leaguesync Event is Event.trusted=True --
# first-party, curated League content that must survive the relevance
# gate (see enrich/enricher.py's trusted bypass) regardless of its LLM
# verdict.
# ---------------------------------------------------------------------


class TestTrustedFlag:
    def test_every_class_event_is_trusted(self):
        class_events = _extract_classes_only()

        assert class_events
        assert all(e.trusted is True for e in class_events)

    def test_every_tech_club_event_is_trusted(self):
        events = run(_source(), _real_fetcher())

        tech_club_events = [e for e in events if "Robot Drivers" in e.title]
        assert tech_club_events
        assert all(e.trusted is True for e in tech_club_events)

    def test_end_to_end_run_marks_every_event_trusted(self):
        events = run(_source(), _real_fetcher())

        assert events
        assert all(e.trusted is True for e in events)


# ---------------------------------------------------------------------
# AC (OOP, 2026-07-20): CLASSES_SQL excludes teacher/staff/professional-
# development services at the SQL level -- the site's parent-facing
# audience must never see a service like "Teacher Development", and
# since Event.trusted bypasses the relevance gate, this SQL filter is
# the only thing standing in the way once a class becomes an Event.
# ---------------------------------------------------------------------


class TestTeacherServiceExclusion:
    def test_classes_sql_excludes_teacher_staff_and_professional_development(self):
        stripped = CLASSES_SQL.upper()

        assert "NOT LIKE '%TEACHER%'" in stripped
        assert "NOT LIKE '%STAFF%'" in stripped
        assert "NOT LIKE '%PROFESSIONAL DEVELOPMENT%'" in stripped
        # Applied to both the service's own name and its category --
        # a staff-facing service could carry either signal.
        assert stripped.count("NOT LIKE '%TEACHER%'") == 2
        assert stripped.count("NOT LIKE '%STAFF%'") == 2
        assert stripped.count("NOT LIKE '%PROFESSIONAL DEVELOPMENT%'") == 2

    def test_null_category_name_does_not_silently_exclude_a_real_class(self):
        # A bare `s.category_name NOT LIKE '%Teacher%'` is NULL (not
        # TRUE) when category_name is NULL, which SQL's WHERE clause
        # treats as exclusion -- COALESCE guards against that trap.
        assert "COALESCE(S.CATEGORY_NAME" in CLASSES_SQL.upper()

    def test_real_captured_fixture_has_no_teacher_service_left(self):
        # classes_query.json was captured live using the adapter's own
        # (post-exclusion) CLASSES_SQL -- "Teacher Development"
        # (service_id 357780), present before the exclusion was added,
        # is confirmed gone from the live API response itself, not just
        # filtered client-side.
        class_events = _extract_classes_only()

        titles = {e.title for e in class_events}
        assert "Teacher Development" not in titles
        assert not any("teacher" in t.lower() for t in titles)

    def test_youth_classes_with_thin_titles_are_not_excluded(self):
        # The exclusion must be tight enough that real youth classes --
        # including the two the LLM relevance gate previously dropped
        # for having thin titles -- are unaffected.
        class_events = _extract_classes_only()

        titles = {e.title for e in class_events}
        assert "Summer Camps@SFA" in titles
        assert "Python@GA" in titles
