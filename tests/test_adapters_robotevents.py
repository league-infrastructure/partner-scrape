"""Tests for partner_scrape.adapters.robotevents: RobotEvents API v2
(VEX Robotics Competition / Aerial Drone Competition) events adapter.

``tests/fixtures/robotevents/`` is hand-authored (not live-captured --
no ``ROBOTEVENTS_KEY`` was available during this ticket's execution,
see ``adapters/robotevents.py``'s own module docstring), built directly
from RobotEvents' own published OpenAPI schema (via the open-source
``robotevents`` npm client's generated TypeScript types) rather than a
real response body -- ``events_page1.json``/``events_page2.json`` model
a two-page ``/events`` result across all three RobotEvents-hosted
programs this ticket cares about (V5RC, VIQRC, ADC); the other fixtures
exercise per-record isolation and pagination-probe degradation.

Every test drives the adapter through a fixture ``Fetcher`` returning
these canned bodies -- no test here opens a real network socket, per
this project's established adapter test strategy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from partner_scrape import config
from partner_scrape.adapters import robotevents as robotevents_module
from partner_scrape.adapters import run
from partner_scrape.adapters.base import EventRef, RawResponse
from partner_scrape.adapters.robotevents import (
    DEFAULT_EVENT_TYPES,
    DEFAULT_PER_PAGE,
    RobotEventsAdapter,
    _events_url,
)
from partner_scrape.fetch import DEFAULT_RATE_LIMIT_SECONDS
from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.model import Provenance
from partner_scrape.registry.schema import SourceConfig

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "robotevents"

API_BASE = "https://robotevents.example/api/v2"
REGION = "CA"
START = "2026-08-30"
PER_PAGE = 10
TOKEN = "test-token-abc123"

PROBE_URL = _events_url(API_BASE, [], REGION, DEFAULT_EVENT_TYPES, START, page=1, per_page=1)
PAGE1_URL = _events_url(API_BASE, [], REGION, DEFAULT_EVENT_TYPES, START, page=1, per_page=PER_PAGE)
PAGE2_URL = _events_url(API_BASE, [], REGION, DEFAULT_EVENT_TYPES, START, page=2, per_page=PER_PAGE)


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text()


def _response(body: str, status: int = 200) -> FetchResponse:
    return FetchResponse(url="", status=status, headers={}, body=body)


@dataclass
class FixtureFetcher:
    """Fetcher test double -- returns canned FetchResponses, no socket.

    A URL absent from ``responses`` raises ``KeyError`` -- a loud
    failure if the adapter under test fetches something it shouldn't.
    Records every call's ``headers``/acquisition kwargs too, matching
    ``test_adapters_leaguesync.py``'s/``test_adapters_localist.py``'s
    fixture Fetcher exactly.
    """

    responses: dict[str, FetchResponse]
    calls: list[tuple[str, dict[str, str] | None]] = field(default_factory=list)
    policy_calls: dict[str, tuple[float, bool]] = field(default_factory=dict)

    def get(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        rate_limit_seconds: float = 1.0,
        respect_robots: bool = True,
    ) -> FetchResponse:
        self.calls.append((url, headers))
        self.policy_calls[url] = (rate_limit_seconds, respect_robots)
        return self.responses[url]


def _source(acquisition_policy: dict | None = None, **config_overrides) -> SourceConfig:
    cfg = {
        "api_base": API_BASE,
        "region": REGION,
        "start": START,
        "per_page": PER_PAGE,
        **config_overrides,
    }
    return SourceConfig(
        source_id="fixture_org",
        org_name="Fixture VEX Org",
        adapter_type="robotevents",
        config=cfg,
        acquisition_policy=acquisition_policy or {},
    )


def _two_page_fetcher() -> FixtureFetcher:
    page1_body = _read_fixture("events_page1.json")
    return FixtureFetcher(
        {
            # The probe (per_page=1) only needs a parseable meta.last_page
            # -- reusing page1's body is fine, matching
            # test_adapters_localist.py's identical convention.
            PROBE_URL: _response(page1_body),
            PAGE1_URL: _response(page1_body),
            PAGE2_URL: _response(_read_fixture("events_page2.json")),
        }
    )


@pytest.fixture(autouse=True)
def _robotevents_api_key(monkeypatch):
    """Every test needs a token set by default -- fetch()/discover()
    read it fresh from the environment on every call via
    ``config.get_robotevents_api_key()``. Tests that specifically
    exercise the missing-token path delete it explicitly.
    """
    monkeypatch.setenv("ROBOTEVENTS_KEY", TOKEN)


class TestFieldMapping:
    def test_valid_event_maps_all_documented_fields(self):
        events = run(_source(), _two_page_fetcher())

        v5rc = next(e for e in events if e.title == "CA Region 4 V5RC Signature Event")
        assert v5rc.kind == "event"
        assert v5rc.source_id == "fixture_org"
        assert v5rc.external_id == "54321"
        assert v5rc.start == datetime(2026, 2, 27, 8, 0, 0, tzinfo=timezone(timedelta(hours=-8)))
        assert v5rc.end == datetime(2026, 3, 1, 17, 0, 0, tzinfo=timezone(timedelta(hours=-8)))
        assert v5rc.location == (
            "Town and Country Resort, 500 Hotel Circle N, San Diego, CA 92108"
        )
        assert v5rc.registration_url == "https://www.robotevents.com/RE-VRC-25-1234.html"
        assert v5rc.categories == ["VEX Robotics Competition"]

    def test_second_program_on_same_page_maps_correctly(self):
        events = run(_source(), _two_page_fetcher())

        viqrc = next(e for e in events if e.title == "Sweetwater STEAM VIQRC Tournament")
        assert viqrc.external_id == "54322"
        assert viqrc.location == (
            "Sweetwater High School, 2900 Highland Ave, National City, CA 91950"
        )
        assert viqrc.registration_url == "https://www.robotevents.com/RE-VIQRC-25-5678.html"
        assert viqrc.categories == ["VEX IQ Robotics Competition"]

    def test_second_page_event_maps_correctly(self):
        events = run(_source(), _two_page_fetcher())

        adc = next(e for e in events if e.title == "West Aerial Drone Competition Championship")
        assert adc.external_id == "54323"
        assert adc.location == "Balboa Park Activity Center, 2145 Park Blvd, San Diego, CA 92101"
        assert adc.categories == ["Aerial Drone Competition"]

    def test_every_field_the_adapter_sets_has_robotevents_provenance_at_full_confidence(self):
        events = run(_source(), _two_page_fetcher())

        v5rc = next(e for e in events if e.title == "CA Region 4 V5RC Signature Event")
        assert v5rc.field_provenance
        for prov in v5rc.field_provenance.values():
            assert prov == Provenance(source="robotevents", confidence=1.0)

    def test_total_events_across_both_pages(self):
        events = run(_source(), _two_page_fetcher())

        assert len(events) == 3
        assert {e.external_id for e in events} == {"54321", "54322", "54323"}


class TestKindDefault:
    def test_kind_defaults_to_event_for_every_emitted_record(self):
        events = run(_source(), _two_page_fetcher())

        assert events
        assert all(e.kind == "event" for e in events)


class TestAuthHeader:
    def test_fetch_sends_bearer_token_from_config(self):
        adapter = RobotEventsAdapter()
        fetcher = _two_page_fetcher()

        adapter.fetch(EventRef(url=PAGE1_URL), fetcher, _source())

        assert fetcher.calls == [(PAGE1_URL, {"Authorization": f"Bearer {TOKEN}"})]

    def test_end_to_end_run_sends_the_bearer_header_on_every_fetch(self):
        fetcher = _two_page_fetcher()

        run(_source(), fetcher)

        called_urls_and_headers = dict(fetcher.calls)
        assert called_urls_and_headers[PROBE_URL] == {"Authorization": f"Bearer {TOKEN}"}
        assert called_urls_and_headers[PAGE1_URL] == {"Authorization": f"Bearer {TOKEN}"}
        assert called_urls_and_headers[PAGE2_URL] == {"Authorization": f"Bearer {TOKEN}"}


class TestAcquisitionPolicyThreading:
    def test_probe_and_page_fetches_pass_the_sources_acquisition_policy(self):
        fetcher = _two_page_fetcher()
        source = _source(acquisition_policy={"rate_limit_seconds": 2.5, "respect_robots": False})

        run(source, fetcher)

        assert fetcher.policy_calls[PROBE_URL] == (2.5, False)
        assert fetcher.policy_calls[PAGE2_URL] == (2.5, False)

    def test_source_with_no_acquisition_policy_still_reaches_fetcher_defaults(self):
        fetcher = _two_page_fetcher()

        run(_source(), fetcher)

        assert fetcher.policy_calls[PAGE1_URL] == (DEFAULT_RATE_LIMIT_SECONDS, True)


class TestPagination:
    def test_probe_and_both_pages_are_fetched_in_order_until_exhausted(self):
        fetcher = _two_page_fetcher()

        run(_source(), fetcher)

        assert [url for url, _ in fetcher.calls] == [PROBE_URL, PAGE1_URL, PAGE2_URL]

    def test_single_page_when_last_page_is_one(self):
        body = _read_fixture("events_empty.json")
        fetcher = FixtureFetcher({PROBE_URL: _response(body), PAGE1_URL: _response(body)})

        events = run(_source(), fetcher)

        assert events == []
        assert [url for url, _ in fetcher.calls] == [PROBE_URL, PAGE1_URL]

    def test_custom_per_page_changes_the_page_query_url(self):
        custom_source = _source(per_page=5)
        probe_url = _events_url(API_BASE, [], REGION, DEFAULT_EVENT_TYPES, START, 1, 1)
        page1_url = _events_url(API_BASE, [], REGION, DEFAULT_EVENT_TYPES, START, 1, 5)
        body = _read_fixture("events_empty.json")
        fetcher = FixtureFetcher({probe_url: _response(body), page1_url: _response(body)})

        events = run(custom_source, fetcher)

        assert events == []
        assert [url for url, _ in fetcher.calls] == [probe_url, page1_url]

    def test_season_ids_are_included_as_repeated_query_params(self):
        custom_source = _source(season_ids=[181, 182])
        probe_url = _events_url(API_BASE, [181, 182], REGION, DEFAULT_EVENT_TYPES, START, 1, 1)
        assert "season%5B%5D=181" in probe_url
        assert "season%5B%5D=182" in probe_url

        body = _read_fixture("events_empty.json")
        page1_url = _events_url(API_BASE, [181, 182], REGION, DEFAULT_EVENT_TYPES, START, 1, PER_PAGE)
        fetcher = FixtureFetcher({probe_url: _response(body), page1_url: _response(body)})

        events = run(custom_source, fetcher)

        assert events == []


class TestStartDefault:
    def test_start_defaults_to_todays_date_when_config_omits_it(self, monkeypatch):
        class FakeDate(date):
            @classmethod
            def today(cls):
                return date(2026, 8, 30)

        monkeypatch.setattr(robotevents_module, "date", FakeDate)

        source = SourceConfig(
            source_id="fixture_org",
            org_name="Fixture VEX Org",
            adapter_type="robotevents",
            config={"api_base": API_BASE, "region": REGION},
        )
        adapter = RobotEventsAdapter()
        fetcher = FixtureFetcher({})
        # Only need to inspect the URL discover() builds, not a real
        # fetch -- stub a minimal 401 short-circuit is unnecessary since
        # discover() calls fetcher.get() once for the probe; give it a
        # trivial empty-body 200 so discover() doesn't raise KeyError.
        expected_probe = _events_url(
            API_BASE, [], REGION, DEFAULT_EVENT_TYPES, "2026-08-30", 1, 1
        )
        fetcher.responses[expected_probe] = _response(_read_fixture("events_empty.json"))

        refs = adapter.discover(source, fetcher)

        assert "start=2026-08-30" in refs[0].url


class TestMalformedRecordIsolation:
    def test_no_name_and_non_dict_records_are_skipped_valid_record_survives(self):
        fetcher = FixtureFetcher(
            {
                PROBE_URL: _response(_read_fixture("events_malformed.json")),
                PAGE1_URL: _response(_read_fixture("events_malformed.json")),
            }
        )

        events = run(_source(), fetcher)

        titles = {e.title for e in events}
        assert titles == {"Synthetic Valid VEX Event"}

    def test_unparseable_start_date_isolates_only_that_record(self):
        fetcher = FixtureFetcher(
            {
                PROBE_URL: _response(_read_fixture("events_bad_date.json")),
                PAGE1_URL: _response(_read_fixture("events_bad_date.json")),
            }
        )

        events = run(_source(), fetcher)

        titles = {e.title for e in events}
        assert titles == {"Synthetic Valid VEX Event"}
        assert "Bad Start Date Event" not in titles


class TestEmptyResponse:
    def test_empty_data_list_yields_zero_events_and_no_exception(self):
        body = _read_fixture("events_empty.json")
        fetcher = FixtureFetcher({PROBE_URL: _response(body), PAGE1_URL: _response(body)})

        events = run(_source(), fetcher)

        assert events == []


class TestExtractRobustness:
    def test_non_200_status_returns_no_events_without_raising(self):
        adapter = RobotEventsAdapter()
        raw = RawResponse(ref=EventRef(url=PAGE1_URL), status=500, body="")

        assert list(adapter.extract(raw, _source())) == []

    def test_unparseable_json_body_returns_no_events_without_raising(self):
        adapter = RobotEventsAdapter()
        raw = RawResponse(ref=EventRef(url=PAGE1_URL), status=200, body="not json {")

        assert list(adapter.extract(raw, _source())) == []

    def test_non_dict_json_shape_returns_no_events_without_raising(self):
        adapter = RobotEventsAdapter()
        raw = RawResponse(ref=EventRef(url=PAGE1_URL), status=200, body="[]")

        assert list(adapter.extract(raw, _source())) == []

    def test_missing_data_key_returns_no_events_without_raising(self):
        adapter = RobotEventsAdapter()
        raw = RawResponse(ref=EventRef(url=PAGE1_URL), status=200, body='{"meta": {}}')

        assert list(adapter.extract(raw, _source())) == []


class TestDiscoverProbeFailureHandling:
    def test_probe_non_200_non_401_status_degrades_to_a_single_page(self):
        fetcher = FixtureFetcher({PROBE_URL: _response("", status=500)})
        adapter = RobotEventsAdapter()

        refs = adapter.discover(_source(), fetcher)

        assert [r.url for r in refs] == [PAGE1_URL]

    def test_probe_unparseable_json_degrades_to_a_single_page(self):
        fetcher = FixtureFetcher({PROBE_URL: _response("not json")})
        adapter = RobotEventsAdapter()

        refs = adapter.discover(_source(), fetcher)

        assert [r.url for r in refs] == [PAGE1_URL]


# ---------------------------------------------------------------------
# AC: "A missing/invalid ROBOTEVENTS_KEY (or an API auth failure) is
# isolated by pipeline.run()'s existing per-source isolation -- it is
# caught, logged, and skips only this source; it must not be allowed to
# propagate and abort the run." Matches teams/sources/tba.py's own
# module-level proof (test_sources_tba.py's
# test_missing_key_raises_before_any_fetch / test_401_status_raises):
# both failure modes must raise, uncaught, out of the adapter itself --
# that is what lets pipeline.py's `_run_one_source`'s existing broad
# `except Exception` (already covered generically by
# test_pipeline_e2e.py's brokensource.toml tests) catch it.
# ---------------------------------------------------------------------


class TestMissingOrInvalidTokenIsolation:
    def test_missing_token_raises_runtime_error_before_any_fetch(self, monkeypatch):
        monkeypatch.delenv("ROBOTEVENTS_KEY", raising=False)
        adapter = RobotEventsAdapter()
        fetcher = _two_page_fetcher()  # a real, working fixture fetcher

        with pytest.raises(RuntimeError, match="ROBOTEVENTS_KEY"):
            adapter.discover(_source(), fetcher)

        assert fetcher.calls == []  # never even attempted the probe

    def test_401_probe_status_raises_runtime_error(self):
        fetcher = FixtureFetcher({PROBE_URL: _response("{}", status=401)})
        adapter = RobotEventsAdapter()

        with pytest.raises(RuntimeError, match="401"):
            adapter.discover(_source(), fetcher)

    def test_missing_token_propagates_uncaught_out_of_adapters_run(self, monkeypatch):
        # adapters.run(source, fetcher) is exactly what pipeline.py's
        # `_run_one_source` wraps in its own broad `except Exception` --
        # proving the exception reaches here unmodified proves that
        # existing, already-tested mechanism will catch it in a real
        # pipeline.run() the same way it catches every other source's
        # failure.
        monkeypatch.delenv("ROBOTEVENTS_KEY", raising=False)
        fetcher = FixtureFetcher({})

        with pytest.raises(RuntimeError):
            run(_source(), fetcher)

    def test_invalid_token_401_propagates_uncaught_out_of_adapters_run(self):
        fetcher = FixtureFetcher({PROBE_URL: _response("{}", status=401)})

        with pytest.raises(RuntimeError):
            run(_source(), fetcher)


class TestPipelineRunSurvivesAMissingToken:
    """The end-to-end proof: a real `pipeline.run()` call, over a
    tmp-path registry with this (broken) robotevents source and one
    healthy `leaguesync` source (reusing that adapter's own real
    fixtures -- no new fixture data needed), completes without raising
    and still reports the healthy source's real output. Mirrors
    `tests/teams/test_pipeline.py`'s `TestTbaFailureIsolation` -- the
    exact "equivalent isolation contract on the teams side" this
    ticket's Acceptance Criteria points at, ported to the Opportunity
    pipeline.
    """

    def test_missing_robotevents_key_still_completes_and_reports_the_healthy_source(
        self, tmp_path, monkeypatch
    ):
        import shutil

        from partner_scrape.adapters.leaguesync import CLASSES_SQL, TECH_CLUBS_SQL, _query_url
        from partner_scrape.pipeline import run as run_pipeline

        monkeypatch.delenv("ROBOTEVENTS_KEY", raising=False)
        monkeypatch.setenv("LEAGUESYNC_API_KEY", "healthy-fixture-token")
        monkeypatch.setenv("SCRAPE_CACHE_DIR", str(tmp_path / "scrape_cache"))

        # partner_scrape.normalize's partner join reads
        # {site_dir}/src/data/partners.json unconditionally -- seed it
        # from the shared fixture, matching test_pipeline_e2e.py's own
        # `_site_dir()` helper exactly (not the real stem-ecosystem data).
        site_dir = tmp_path / "site"
        data_dir = site_dir / "src" / "data"
        data_dir.mkdir(parents=True)
        shutil.copy(
            Path(__file__).resolve().parent / "fixtures" / "partners.json",
            data_dir / "partners.json",
        )

        registry_dir = tmp_path / "registry"
        registry_dir.mkdir()
        (registry_dir / "robotevents-vex-sd.toml").write_text(
            'org_name = "Fixture VEX Org"\n'
            'adapter_type = "robotevents"\n'
            "enabled = true\n\n"
            "[config]\n"
            f'api_base = "{API_BASE}"\n'
            f'region = "{REGION}"\n'
            f'start = "{START}"\n'
        )
        (registry_dir / "healthysource.toml").write_text(
            'org_name = "Healthy Fixture Org"\n'
            'adapter_type = "leaguesync"\n'
            "enabled = true\n\n"
            "[config]\n"
            'api_base = "https://healthy.example"\n'
        )

        classes_url = _query_url("https://healthy.example", CLASSES_SQL)
        tech_clubs_url = _query_url("https://healthy.example", TECH_CLUBS_SQL)
        fetcher = FixtureFetcher(
            {classes_url: _response("[]"), tech_clubs_url: _response("[]")}
        )

        by_source: dict[str, tuple[list, Exception | None]] = {}

        class SpyReporter:
            def record_source(self, source_id, org_name, events, error=None):
                by_source[source_id] = (events, error)

            def record_opportunities(self, opportunities):
                pass

        payload = run_pipeline(
            registry_dir=registry_dir,
            site_dir=site_dir,
            fetcher=fetcher,
            reporter=SpyReporter(),
            dry_run=True,
        )

        assert payload == []  # healthy source's SQL fixtures are both empty lists

        re_events, re_error = by_source["robotevents-vex-sd"]
        assert re_events == []
        assert isinstance(re_error, RuntimeError)
        assert "ROBOTEVENTS_KEY" in str(re_error)

        healthy_events, healthy_error = by_source["healthysource"]
        assert healthy_error is None
        assert healthy_events == []  # legitimately empty, not a failure


class TestUrlBuilding:
    def test_query_url_shape_is_correctly_percent_encoded(self):
        url = _events_url(
            "https://robotevents.example/api/v2",
            [181],
            "CA",
            ["tournament"],
            "2026-08-30",
            page=1,
            per_page=50,
        )
        assert url == (
            "https://robotevents.example/api/v2/events?"
            "season%5B%5D=181&region=CA&eventTypes%5B%5D=tournament"
            "&start=2026-08-30&page=1&per_page=50"
        )

    def test_strips_trailing_slash_on_api_base(self):
        url = _events_url(
            "https://robotevents.example/api/v2/", [], "", [], "", page=1, per_page=50
        )
        assert url.startswith("https://robotevents.example/api/v2/events?")

    def test_omits_region_and_start_when_falsy(self):
        url = _events_url(API_BASE, [], "", [], "", page=1, per_page=50)
        assert "region=" not in url
        assert "start=" not in url


class TestApiBaseFallback:
    def test_api_base_falls_back_to_config_default_when_source_omits_it(self, monkeypatch):
        monkeypatch.delenv("ROBOTEVENTS_URL", raising=False)
        source = SourceConfig(
            source_id="fixture_org",
            org_name="Fixture VEX Org",
            adapter_type="robotevents",
            config={},
        )
        adapter = RobotEventsAdapter()
        expected_probe = _events_url(
            config.DEFAULT_ROBOTEVENTS_URL, [], "", DEFAULT_EVENT_TYPES, date.today().isoformat(),
            1, 1,
        )
        fetcher = FixtureFetcher({expected_probe: _response(_read_fixture("events_empty.json"))})

        refs = adapter.discover(source, fetcher)

        assert refs[0].url.startswith(config.DEFAULT_ROBOTEVENTS_URL)


class TestDefaultConstants:
    def test_default_event_types_is_tournament_only(self):
        assert DEFAULT_EVENT_TYPES == ["tournament"]

    def test_default_per_page_is_positive(self):
        assert DEFAULT_PER_PAGE > 0
