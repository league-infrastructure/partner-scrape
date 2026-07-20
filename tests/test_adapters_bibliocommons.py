"""Tests for partner_scrape.adapters.bibliocommons: the BiblioCommons adapter.

Every test drives the adapter through a fixture Fetcher returning
recorded/synthesized BiblioCommons gateway API JSON
(tests/fixtures/bibliocommons/) -- no test here opens a real network
socket, per this project's Adapter Framework test convention (see
test_adapters_tec.py/test_adapters_localist.py).

``events_page1.json`` was shaped from a real, live-captured
``gateway.bibliocommons.com/v2/libraries/sdcl/events`` response
(2026-07-19) -- see bibliocommons.py's module docstring for the full
investigation. It exercises: a timed event with every optional field
populated, a bare-date (all-day) event, a legitimately-recurring pair
that share a ``seriesId`` but have distinct ids/dates (proving they are
*not* collapsed away), a malformed record with no title (per-record
isolation), and a sparse record with no location/image/categories/
audience/program. It also repeats one id at the end of ``items`` to
exercise the within-page defensive dedup. Its two adult-audience events
("Digital Literacy and Tech Support", "Tai Chi Exercise Class") also
carry a second "Family" ``audienceIds`` entry, added alongside their
original adult one -- not because that reflects a real BiblioCommons
record, but so both keep surviving the youth/family audience
pre-filter (see bibliocommons.py's YOUTH_FAMILY_AUDIENCE_KEYWORDS)
while these tests exercise unrelated behavior (all-day detection,
recurring-occurrence dedup). ``TestAudiencePrefilter`` below, backed by
``events_audience_mix.json``, is the dedicated test of the filter
itself, including a genuinely adult-only (filtered) event.

``events_feature_unavailable.json`` reproduces, verbatim, the real
HTTP 403 body live-observed from San Diego Public Library's BiblioCommons
subdomain (``sandiego``) -- confirming the adapter's existing non-200
handling degrades this real "feature not available" source to zero
events without raising.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pytest

from partner_scrape.adapters import run
from partner_scrape.adapters.base import EventRef, RawResponse
from partner_scrape.adapters.bibliocommons import (
    KEEP_IF_UNKNOWN_AUDIENCE,
    PAGE_SIZE,
    YOUTH_FAMILY_AUDIENCE_KEYWORDS,
    BiblioCommonsAdapter,
    is_youth_family_audience,
)
from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.model import Provenance
from partner_scrape.registry.schema import SourceConfig

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "bibliocommons"

SUBDOMAIN = "fixturelib"
API_BASE = f"https://gateway.bibliocommons.com/v2/libraries/{SUBDOMAIN}/events"
PAGE1_URL = f"{API_BASE}?page=1&limit={PAGE_SIZE}"
PAGE2_URL = f"{API_BASE}?page=2&limit={PAGE_SIZE}"
#: discover()'s probe reuses the *real* configured limit (see
#: bibliocommons.py's discover() docstring for why) -- for the default
#: PAGE_SIZE, the probe request and page 1's real request are the same
#: URL. Aliased for readability at call sites that mean "the probe".
PROBE_URL = PAGE1_URL


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text()


def _response(body: str, status: int = 200) -> FetchResponse:
    return FetchResponse(url="", status=status, headers={}, body=body)


@dataclass
class FixtureFetcher:
    """Fetcher test double -- returns canned FetchResponses, no socket.

    A URL absent from ``responses`` raises ``KeyError`` -- a loud
    failure if the adapter under test fetches something it shouldn't.
    """

    responses: dict[str, FetchResponse]
    calls: list[str] = field(default_factory=list)

    def get(self, url: str, headers: dict[str, str] | None = None) -> FetchResponse:
        self.calls.append(url)
        return self.responses[url]


def _source(**config_overrides) -> SourceConfig:
    config = {"subdomain": SUBDOMAIN, **config_overrides}
    return SourceConfig(
        source_id="fixture_org",
        org_name="Fixture Library",
        adapter_type="bibliocommons",
        config=config,
    )


def _two_page_fetcher() -> FixtureFetcher:
    page1_body = _read_fixture("events_page1.json")
    return FixtureFetcher(
        {
            # The probe (limit=1) only needs a parseable
            # events.pagination.pages -- reusing page1's body is fine,
            # its pages value (2) is what discover() actually reads.
            PROBE_URL: _response(page1_body),
            PAGE1_URL: _response(page1_body),
            PAGE2_URL: _response(_read_fixture("events_page2.json")),
        }
    )


class TestFieldMapping:
    def test_valid_timed_event_maps_all_documented_fields(self):
        events = run(_source(), _two_page_fetcher())

        lab = next(e for e in events if e.title == "Tide Pool STEAM Lab")
        assert lab.start == datetime(2026, 8, 10, 14, 0, 0)
        assert lab.end == datetime(2026, 8, 10, 15, 30, 0)
        assert lab.all_day is False
        assert lab.location == "Lemon Grove, Community Room"
        assert lab.description == "Hands-on tide pool exploration for kids."
        assert (
            lab.registration_url == "https://fixturelib.bibliocommons.com/events/evt001"
        )
        assert (
            lab.image_url
            == "https://fixturelib.bibliocommons.com/events/uploads/images/full/abc/tidepool.jpg"
        )
        assert lab.categories == ["STEAM"]
        assert lab.age_grade_level == ["Kids"]
        assert lab.tags == ["Summer at Your Library"]
        assert lab.kind == "event"
        assert lab.source_id == "fixture_org"
        assert lab.external_id == "evt001"
        assert lab.cost == ""

    def test_every_field_the_adapter_sets_has_bibliocommons_provenance_at_full_confidence(self):
        events = run(_source(), _two_page_fetcher())

        lab = next(e for e in events if e.title == "Tide Pool STEAM Lab")
        assert lab.field_provenance
        for prov in lab.field_provenance.values():
            assert prov == Provenance(source="bibliocommons", confidence=1.0)

    def test_bare_date_event_is_treated_as_all_day(self):
        events = run(_source(), _two_page_fetcher())

        tech = next(e for e in events if e.title == "Digital Literacy and Tech Support")
        assert tech.start == datetime(2026, 12, 3, 0, 0, 0)
        assert tech.end == datetime(2026, 12, 3, 0, 0, 0)
        assert tech.all_day is True
        assert tech.location == "Fallbrook"
        assert tech.categories == ["Computers and Technology"]
        # audienceIds carries both "Adults" and "Family" -- the latter
        # is what keeps this event past the youth/family audience
        # pre-filter (see TestAudiencePrefilter / bibliocommons.py's
        # YOUTH_FAMILY_AUDIENCE_KEYWORDS); both resolved names are
        # still recorded on age_grade_level.
        assert tech.age_grade_level == ["Adults", "Family"]

    def test_sparse_event_leaves_optional_fields_unset(self):
        events = run(_source(), _two_page_fetcher())

        sparse = next(e for e in events if e.title == "Members Meeting")
        assert sparse.location == ""
        assert sparse.image_url == ""
        assert sparse.categories == []
        assert sparse.age_grade_level == []
        assert sparse.tags == []
        assert "location" not in sparse.field_provenance
        assert "description" not in sparse.field_provenance
        assert "image_url" not in sparse.field_provenance
        assert "categories" not in sparse.field_provenance
        # registration_url and all_day are always set (constructed / derived).
        assert sparse.registration_url == "https://fixturelib.bibliocommons.com/events/evt005"
        assert sparse.all_day is False


class TestRecurringOccurrencesAreNotCollapsed:
    """Distinct future occurrences of one series must both survive.

    Unlike Localist's same-id-repeated-per-day quirk, BiblioCommons
    gives every occurrence a distinct id -- see bibliocommons.py's
    module docstring. Both Tai Chi occurrences (different ids, different
    dates, same seriesId) must appear as two separate Events.
    """

    def test_two_distinct_occurrences_of_the_same_series_both_appear(self):
        events = run(_source(), _two_page_fetcher())

        tai_chi = [e for e in events if e.title == "Tai Chi Exercise Class"]
        assert len(tai_chi) == 2
        assert {e.external_id for e in tai_chi} == {"evt003a", "evt003b"}
        assert {e.start for e in tai_chi} == {
            datetime(2026, 10, 29, 12, 0, 0),
            datetime(2026, 12, 29, 12, 0, 0),
        }


class TestWithinPageDedup:
    def test_repeated_id_in_items_list_yields_exactly_one_event(self):
        # events_page1.json's items list repeats "evt001" as its last
        # entry -- the defensive seen_ids guard (module docstring) must
        # collapse it to one Event, not two.
        adapter = BiblioCommonsAdapter()
        raw = RawResponse(
            ref=EventRef(url=PAGE1_URL), status=200, body=_read_fixture("events_page1.json")
        )

        events = list(adapter.extract(raw, _source()))

        assert sum(1 for e in events if e.external_id == "evt001") == 1


class TestPagination:
    def test_probe_and_both_pages_are_fetched_in_order_until_exhausted(self):
        fetcher = _two_page_fetcher()

        run(_source(), fetcher)

        assert fetcher.calls == [PROBE_URL, PAGE1_URL, PAGE2_URL]

    def test_single_page_when_pages_is_one(self):
        body = _read_fixture("events_empty.json")
        fetcher = FixtureFetcher({PROBE_URL: _response(body), PAGE1_URL: _response(body)})

        events = run(_source(), fetcher)

        assert events == []
        assert fetcher.calls == [PROBE_URL, PAGE1_URL]

    def test_custom_limit_config_changes_the_query_url(self):
        # The probe reuses the *real* configured limit (10 here, not
        # PAGE_SIZE) -- see discover()'s docstring -- so both the probe
        # and page 1's real fetch hit this same limit=10 URL.
        custom_source = _source(limit=10)
        page1_url = f"{API_BASE}?page=1&limit=10"
        body = _read_fixture("events_empty.json")
        fetcher = FixtureFetcher({page1_url: _response(body)})

        events = run(custom_source, fetcher)

        assert events == []
        assert fetcher.calls == [page1_url, page1_url]

    def test_total_unique_events_across_both_pages(self):
        events = run(_source(), _two_page_fetcher())

        titles = sorted(e.title for e in events)
        assert titles == [
            "Digital Literacy and Tech Support",
            "Members Meeting",
            "Storytime with Ms. Dana",
            "Tai Chi Exercise Class",
            "Tai Chi Exercise Class",
            "Tide Pool STEAM Lab",
        ]


class TestMalformedRecordIsolation:
    def test_missing_title_record_is_skipped_rest_of_page_survives(self):
        events = run(_source(), _two_page_fetcher())

        titles = {e.title for e in events}
        assert "" not in titles
        assert {"Tide Pool STEAM Lab", "Digital Literacy and Tech Support"} <= titles


class TestEmptyResponse:
    def test_empty_events_list_yields_zero_events_and_no_exception(self):
        body = _read_fixture("events_empty.json")
        fetcher = FixtureFetcher({PROBE_URL: _response(body), PAGE1_URL: _response(body)})

        events = run(_source(), fetcher)

        assert events == []


class TestKindDefault:
    def test_kind_defaults_to_event_for_every_emitted_record(self):
        events = run(_source(), _two_page_fetcher())

        assert events  # sanity: fixtures did produce events
        assert all(e.kind == "event" for e in events)


class TestExtractRobustness:
    def test_non_200_page_status_returns_no_events_without_raising(self):
        adapter = BiblioCommonsAdapter()
        raw = RawResponse(ref=EventRef(url=PAGE1_URL), status=500, body="")

        assert list(adapter.extract(raw, _source())) == []

    def test_unparseable_json_body_returns_no_events_without_raising(self):
        adapter = BiblioCommonsAdapter()
        raw = RawResponse(ref=EventRef(url=PAGE1_URL), status=200, body="not json {")

        assert list(adapter.extract(raw, _source())) == []

    def test_unexpected_json_shape_returns_no_events_without_raising(self):
        adapter = BiblioCommonsAdapter()
        raw = RawResponse(ref=EventRef(url=PAGE1_URL), status=200, body="[]")

        assert list(adapter.extract(raw, _source())) == []


class TestSourceWithEventsFeatureUnavailable:
    """Reproduces San Diego Public Library's real, live-confirmed state.

    The gateway API returns HTTP 403 with an ``{"error": ...}`` body for
    ``sandiego`` (SDPL's subdomain) -- see bibliocommons.py's module
    docstring. The adapter's existing non-200 handling already copes
    with this correctly: discover() degrades to a single page, and
    extract() on that one page yields zero events without raising.
    """

    def test_probe_403_degrades_to_a_single_page(self):
        body = _read_fixture("events_feature_unavailable.json")
        fetcher = FixtureFetcher({PROBE_URL: _response(body, status=403)})
        adapter = BiblioCommonsAdapter()

        refs = adapter.discover(_source(), fetcher)

        assert [r.url for r in refs] == [PAGE1_URL]

    def test_full_run_yields_zero_events_without_raising(self):
        body = _read_fixture("events_feature_unavailable.json")
        fetcher = FixtureFetcher(
            {
                PROBE_URL: _response(body, status=403),
                PAGE1_URL: _response(body, status=403),
            }
        )

        events = run(_source(), fetcher)

        assert events == []


class TestDiscoverProbeFailureHandling:
    def test_probe_non_200_status_degrades_to_a_single_page(self):
        fetcher = FixtureFetcher({PROBE_URL: _response("", status=500)})
        adapter = BiblioCommonsAdapter()

        refs = adapter.discover(_source(), fetcher)

        assert [r.url for r in refs] == [PAGE1_URL]

    def test_probe_unparseable_json_degrades_to_a_single_page(self):
        fetcher = FixtureFetcher({PROBE_URL: _response("not json")})
        adapter = BiblioCommonsAdapter()

        refs = adapter.discover(_source(), fetcher)

        assert [r.url for r in refs] == [PAGE1_URL]

    def test_probe_missing_pagination_key_degrades_to_a_single_page(self):
        fetcher = FixtureFetcher({PROBE_URL: _response('{"events": {}}')})
        adapter = BiblioCommonsAdapter()

        refs = adapter.discover(_source(), fetcher)

        assert [r.url for r in refs] == [PAGE1_URL]


class TestIsYouthFamilyAudience:
    """Direct unit tests of the pure predicate -- no Fetcher, no Event.

    Mirrors ``test_adapters_ats_filters.py``'s table-driven style for
    its analogous pure-function predicates.
    """

    @pytest.mark.parametrize(
        "audience_names",
        [
            ["Kids"],
            ["Teens"],
            ["Birth to Five"],
            ["Family"],
            ["Tweens"],
            ["Babies"],
            ["Toddler Time"],
            ["Preschool Storytime"],
            ["Pre-K Readiness"],
            ["School Age (6-11)"],
            ["All Ages"],
            ["4th Grade Book Club"],
            ["Children's Programs"],
            ["Adults", "Kids"],  # any match is enough
        ],
    )
    def test_positive_audience_names_match(self, audience_names):
        assert is_youth_family_audience(audience_names) is True

    @pytest.mark.parametrize(
        "audience_names",
        [
            ["Adults"],
            ["Older Adults 55+"],
            ["Seniors"],
            [],
        ],
    )
    def test_negative_audience_names_do_not_match(self, audience_names):
        assert is_youth_family_audience(audience_names) is False

    def test_matching_is_case_insensitive(self):
        assert is_youth_family_audience(["KIDS"]) is True
        assert is_youth_family_audience(["kids"]) is True

    def test_keep_if_unknown_default_is_true(self):
        # Documents the module's default -- extract()'s
        # _passes_audience_prefilter relies on this constant being True
        # so absent audience data keeps (not drops) an event.
        assert KEEP_IF_UNKNOWN_AUDIENCE is True

    def test_keyword_set_is_lowercase(self):
        # is_youth_family_audience lowercases the *name* it matches
        # against, not the keyword list -- the keywords themselves must
        # already be lowercase or a keyword could fail to match its own
        # mixed-case self.
        assert all(keyword == keyword.lower() for keyword in YOUTH_FAMILY_AUDIENCE_KEYWORDS)


class TestAudiencePrefilter:
    """The deterministic YOUTH/FAMILY audience pre-filter, end to end
    through ``extract()`` -- see bibliocommons.py's
    YOUTH_FAMILY_AUDIENCE_KEYWORDS / KEEP_IF_UNKNOWN_AUDIENCE /
    AUDIENCE_PREFILTER_CONFIG_KEY.

    ``events_audience_mix.json`` mixes four records: a family event
    (kept -- matches "family"), an adult-only event (filtered -- no
    youth/family audience at all), an event with no audience data
    whatsoever (kept, per keep-if-unknown), and a teen event (kept --
    matches "teen").
    """

    def _fetcher(self) -> FixtureFetcher:
        body = _read_fixture("events_audience_mix.json")
        return FixtureFetcher({PROBE_URL: _response(body), PAGE1_URL: _response(body)})

    def test_only_youth_family_and_unknown_audience_events_survive(self):
        events = run(_source(), self._fetcher())

        titles = {e.title for e in events}
        assert titles == {"Family STEM Night", "Board Meeting", "Teen Anime Club"}
        assert "Wine Tasting for Grown-Ups" not in titles

    def test_filtered_adult_only_event_never_becomes_an_event(self):
        events = run(_source(), self._fetcher())

        assert all(e.external_id != "evt102" for e in events)

    def test_config_override_disables_the_prefilter(self):
        # audience_prefilter=False is the documented per-source escape
        # hatch -- every fetched record becomes an Event, including the
        # adult-only one that is normally filtered.
        events = run(_source(audience_prefilter=False), self._fetcher())

        titles = {e.title for e in events}
        assert titles == {
            "Family STEM Night",
            "Wine Tasting for Grown-Ups",
            "Board Meeting",
            "Teen Anime Club",
        }
