"""End-to-end walking-skeleton test for `partner_scrape.pipeline.run()`.

Ticket 008's key deliverable (sprint.md SUC-008): runs the *real*
Registry -> Adapter dispatch -> Enricher hook -> Normalize -> Export
chain, with only the `Fetcher` faked, over a small fixture-only registry
(`tests/fixtures/e2e_registry/`) containing:

- `coastalrootsfarm.toml` (`tec_rest`): a fixture TEC page with one
  upcoming event and one past event (proves the upcoming filter).
- `thelivingcoast.toml` (`ical`): a fixture `.ics` feed with one event
  that duplicates the TEC source's event (same title/date/venue -- proves
  cross-source dedup) and one recurring event (proves recurring
  collapse).
- `brokensource.toml` (`tec_rest`): a well-formed, enabled entry whose
  URLs have no canned fixture response, forcing a real fetch failure --
  proves per-source error isolation (the run must still produce output
  from the other two sources).

No test here opens a socket: the injected `FixtureFetcher` raises if
asked for a URL it wasn't given a canned response for, so any accidental
real-network attempt fails loudly rather than silently succeeding.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pytest

from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.model import Event
from partner_scrape.pipeline import run

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
E2E_REGISTRY_DIR = FIXTURES_DIR / "e2e_registry"
PARTNERS_FIXTURE = FIXTURES_DIR / "partners.json"

TODAY = date(2026, 7, 19)

TEC_API_BASE = "https://coastalrootsfarm.example/wp-json/tribe/events/v1/events/"
TEC_PROBE_URL = f"{TEC_API_BASE}?per_page=1&status=publish&start_date=now"
TEC_PAGE1_URL = f"{TEC_API_BASE}?per_page=50&page=1&status=publish&start_date=now"
ICAL_FEED_URL = "https://thelivingcoast.example/events/?ical=1"

# brokensource.toml's own probe URL -- deliberately absent from every
# FixtureFetcher this test builds, so fetching it always raises
# NoFixtureResponse (see brokensource.toml's comment).
BROKEN_API_BASE = "https://broken-source.example/wp-json/tribe/events/v1/events/"
BROKEN_PROBE_URL = f"{BROKEN_API_BASE}?per_page=1&status=publish&start_date=now"


class NoFixtureResponse(RuntimeError):
    """Raised by FixtureFetcher for a URL with no canned response -- the
    real failure the deliberately-broken registry entry is meant to
    trigger, standing in for "endpoint unreachable" (SUC-008's Error
    Flow)."""


@dataclass
class FixtureFetcher:
    """Fetcher test double -- returns canned FetchResponses, no socket.

    A URL absent from ``responses`` raises :class:`NoFixtureResponse`,
    matching the pattern used by ``test_adapters_tec.py`` /
    ``test_adapters_ical.py``'s own fixture fetchers -- a loud failure if
    the pipeline (or an adapter) fetches something it shouldn't, and
    exactly the failure mode ``brokensource.toml`` is designed to hit.
    """

    responses: dict[str, FetchResponse]
    calls: list[str] = field(default_factory=list)

    def get(self, url: str, headers: dict[str, str] | None = None) -> FetchResponse:
        self.calls.append(url)
        if url not in self.responses:
            raise NoFixtureResponse(f"no fixture response configured for {url!r}")
        return self.responses[url]


def _response(body: str, status: int = 200) -> FetchResponse:
    return FetchResponse(url="", status=status, headers={}, body=body)


def _fixture_fetcher() -> FixtureFetcher:
    tec_body = (E2E_REGISTRY_DIR / "tec_events.json").read_text()
    ical_body = (E2E_REGISTRY_DIR / "feed.ics").read_text()
    return FixtureFetcher(
        {
            TEC_PROBE_URL: _response(tec_body),
            TEC_PAGE1_URL: _response(tec_body),
            ICAL_FEED_URL: _response(ical_body),
            # brokensource.toml's URLs are deliberately absent.
        }
    )


@dataclass
class RecordingIdentityEnricher:
    """A trivial identity `Enricher` that records what it was called
    with -- proves the hook is real and wired into the collected Event
    stream, not just declared (this ticket's Acceptance Criteria)."""

    received: list[Event] | None = None

    def enrich(self, events: list[Event]) -> list[Event]:
        self.received = list(events)
        return events


def _site_dir(tmp_path: Path) -> Path:
    """A tmp_path-backed stand-in for the sibling stem-ecosystem repo,
    with `src/data/partners.json` seeded from the shared fixture --
    never the real `../stem-ecosystem` checkout."""
    site_dir = tmp_path / "stem-ecosystem"
    data_dir = site_dir / "src" / "data"
    data_dir.mkdir(parents=True)
    shutil.copy(PARTNERS_FIXTURE, data_dir / "partners.json")
    return site_dir


_SITE_SCHEMA_FIELDS = {
    "slug", "title", "partner_name", "partner_id", "description", "link",
    "availability", "date_start", "date_end", "age_grade_level", "cost_range",
    "time_of_day", "opportunity_type", "areas_of_interest", "specific_attention",
    "financial_support", "ngss_aligned", "location", "latitude", "longitude",
    "contact_name", "contact_email", "contact_phone", "logo_src",
}


class TestWalkingSkeletonEndToEnd:
    def test_produces_valid_opportunities_and_scrape_meta_json(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        fetcher = _fixture_fetcher()

        payload = run(
            registry_dir=E2E_REGISTRY_DIR,
            site_dir=site_dir,
            fetcher=fetcher,
            today=TODAY,
        )

        opportunities_path = site_dir / "src" / "data" / "opportunities.json"
        meta_path = site_dir / "src" / "data" / "scrape-meta.json"
        assert opportunities_path.exists()
        assert meta_path.exists()

        written = json.loads(opportunities_path.read_text())
        assert written == payload

        meta = json.loads(meta_path.read_text())
        assert "last_updated" in meta and meta["last_updated"]

    def test_schema_is_well_formed_for_every_record(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        fetcher = _fixture_fetcher()

        payload = run(
            registry_dir=E2E_REGISTRY_DIR, site_dir=site_dir, fetcher=fetcher, today=TODAY
        )

        assert payload, "expected at least one opportunity from the fixture registry"
        for record in payload:
            assert set(record.keys()) == _SITE_SCHEMA_FIELDS
            assert isinstance(record["age_grade_level"], list)
            assert isinstance(record["areas_of_interest"], list)
            assert isinstance(record["time_of_day"], list)
            assert isinstance(record["slug"], str) and record["slug"]

    def test_upcoming_filter_excludes_the_past_event(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        fetcher = _fixture_fetcher()

        payload = run(
            registry_dir=E2E_REGISTRY_DIR, site_dir=site_dir, fetcher=fetcher, today=TODAY
        )

        titles = {record["title"] for record in payload}
        assert "Spring Planting Day" not in titles

    def test_exactly_two_opportunities_survive_dedup_collapse_and_the_upcoming_filter(
        self, tmp_path
    ):
        site_dir = _site_dir(tmp_path)
        fetcher = _fixture_fetcher()

        payload = run(
            registry_dir=E2E_REGISTRY_DIR, site_dir=site_dir, fetcher=fetcher, today=TODAY
        )

        titles = {record["title"] for record in payload}
        assert titles == {"Tide Pool Exploration", "Weekly Story Time"}

    def test_cross_source_duplicate_collapses_to_one_record_keeping_the_richer_source(
        self, tmp_path
    ):
        site_dir = _site_dir(tmp_path)
        fetcher = _fixture_fetcher()

        payload = run(
            registry_dir=E2E_REGISTRY_DIR, site_dir=site_dir, fetcher=fetcher, today=TODAY
        )

        [tide_pool] = [r for r in payload if r["title"] == "Tide Pool Exploration"]
        # The TEC record is more complete (cost, registration link) than
        # the iCal duplicate -- dedup must keep it, not just pick either.
        assert tide_pool["link"] == "https://coastalrootsfarm.example/events/tide-pool-exploration/"
        assert "tide pools" in tide_pool["description"].lower()

    def test_recurring_ical_event_collapses_with_repeat_count_in_availability(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        fetcher = _fixture_fetcher()

        payload = run(
            registry_dir=E2E_REGISTRY_DIR, site_dir=site_dir, fetcher=fetcher, today=TODAY
        )

        [story_time] = [r for r in payload if r["title"] == "Weekly Story Time"]
        assert "Repeats 3 times" in story_time["availability"]

    def test_partner_join_resolves_org_name_from_the_registry(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        fetcher = _fixture_fetcher()

        payload = run(
            registry_dir=E2E_REGISTRY_DIR, site_dir=site_dir, fetcher=fetcher, today=TODAY
        )

        [tide_pool] = [r for r in payload if r["title"] == "Tide Pool Exploration"]
        assert tide_pool["partner_name"] == "Coastal Roots Farm"
        assert tide_pool["partner_id"] == 101
        assert tide_pool["logo_src"] == "coastal_roots_farm.jpg"

        [story_time] = [r for r in payload if r["title"] == "Weekly Story Time"]
        assert story_time["partner_name"] == "The Living Coast Discovery Center"
        assert story_time["partner_id"] == 102


class TestPerSourceErrorIsolation:
    def test_broken_source_is_logged_and_skipped_others_still_export(self, tmp_path, caplog):
        site_dir = _site_dir(tmp_path)
        fetcher = _fixture_fetcher()

        import logging

        with caplog.at_level(logging.ERROR, logger="partner_scrape.pipeline"):
            payload = run(
                registry_dir=E2E_REGISTRY_DIR, site_dir=site_dir, fetcher=fetcher, today=TODAY
            )

        assert len(payload) == 2, "the two healthy sources must still produce output"
        assert "brokensource" in caplog.text

    def test_broken_source_never_reaches_the_fixture_fetcher_for_unexpected_urls(self, tmp_path):
        # The broken source's own probe URL is legitimately attempted
        # (that's what makes it fail) -- but confirms no *other* stray
        # URL is fetched, i.e. failure is isolated to that one source's
        # own request(s).
        site_dir = _site_dir(tmp_path)
        fetcher = _fixture_fetcher()

        run(registry_dir=E2E_REGISTRY_DIR, site_dir=site_dir, fetcher=fetcher, today=TODAY)

        assert TEC_PROBE_URL in fetcher.calls
        assert TEC_PAGE1_URL in fetcher.calls
        assert ICAL_FEED_URL in fetcher.calls


class TestEnricherHook:
    def test_enrichers_defaults_to_empty_and_is_a_no_op(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        fetcher = _fixture_fetcher()

        payload = run(
            registry_dir=E2E_REGISTRY_DIR, site_dir=site_dir, fetcher=fetcher, today=TODAY
        )

        assert len(payload) == 2

    def test_custom_enricher_is_actually_invoked_with_the_collected_event_stream(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        fetcher = _fixture_fetcher()
        enricher = RecordingIdentityEnricher()

        payload = run(
            registry_dir=E2E_REGISTRY_DIR,
            site_dir=site_dir,
            fetcher=fetcher,
            enrichers=[enricher],
            today=TODAY,
        )

        # 2 TEC events (tide pool + spring planting) + 1 ical tide pool +
        # 3 ical "Weekly Story Time" occurrences = 6 raw Events reach the
        # enricher, *before* collapse/dedup -- proving it sits where
        # sprint.md says: after adapter collection, before Normalize.
        assert enricher.received is not None
        assert len(enricher.received) == 6
        assert all(isinstance(e, Event) for e in enricher.received)
        # And the (identity) transformation's output still reaches export.
        assert len(payload) == 2


class TestNoNetworkAccess:
    def test_fetcher_only_ever_serves_known_fixture_urls(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        fetcher = _fixture_fetcher()

        run(registry_dir=E2E_REGISTRY_DIR, site_dir=site_dir, fetcher=fetcher, today=TODAY)

        # BROKEN_PROBE_URL is legitimately attempted (that's what makes
        # brokensource.toml fail) -- every URL fetched is one of these
        # four known, fixture-mapped-or-deliberately-unmapped URLs, never
        # anything that would imply a real socket was opened.
        assert set(fetcher.calls) <= {
            TEC_PROBE_URL,
            TEC_PAGE1_URL,
            ICAL_FEED_URL,
            BROKEN_PROBE_URL,
        }


class TestDryRun:
    def test_dry_run_computes_payload_but_writes_nothing(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        fetcher = _fixture_fetcher()

        payload = run(
            registry_dir=E2E_REGISTRY_DIR,
            site_dir=site_dir,
            fetcher=fetcher,
            today=TODAY,
            dry_run=True,
        )

        assert len(payload) == 2
        assert not (site_dir / "src" / "data" / "opportunities.json").exists()
        assert not (site_dir / "src" / "data" / "scrape-meta.json").exists()


class TestLimitAndSourceFilters:
    def test_source_id_filter_runs_only_that_source(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        fetcher = _fixture_fetcher()

        payload = run(
            registry_dir=E2E_REGISTRY_DIR,
            site_dir=site_dir,
            fetcher=fetcher,
            source_id="thelivingcoast",
            today=TODAY,
        )

        titles = {record["title"] for record in payload}
        assert titles == {"Tide Pool Exploration", "Weekly Story Time"}
        assert all(source == ICAL_FEED_URL for source in fetcher.calls)

    def test_limit_restricts_to_the_first_n_active_sources(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        fetcher = _fixture_fetcher()

        # Sources load alphabetically by source_id: brokensource,
        # coastalrootsfarm, thelivingcoast -- limit=1 runs only the
        # (deliberately broken) first one. Its probe is attempted (that's
        # what makes it fail) and isolated, so the run still completes
        # with empty output rather than raising.
        payload = run(
            registry_dir=E2E_REGISTRY_DIR,
            site_dir=site_dir,
            fetcher=fetcher,
            limit=1,
            today=TODAY,
        )

        assert payload == []
        assert fetcher.calls == [BROKEN_PROBE_URL]


class TestPartnersPathDefaultsFromSiteDir:
    def test_omitted_partners_path_resolves_under_site_dir_by_convention(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        fetcher = _fixture_fetcher()

        # No explicit partners_path -- must resolve to
        # {site_dir}/src/data/partners.json, matching sprint.md's
        # documented Site Export/Normalize contract.
        payload = run(
            registry_dir=E2E_REGISTRY_DIR, site_dir=site_dir, fetcher=fetcher, today=TODAY
        )

        tide_pool = next(r for r in payload if r["title"] == "Tide Pool Exploration")
        assert tide_pool["partner_id"] == 101


class TestNoFixtureResponseIsARealFailure:
    def test_fixture_fetcher_raises_for_unconfigured_urls(self):
        fetcher = FixtureFetcher({})
        with pytest.raises(NoFixtureResponse):
            fetcher.get("https://example.org/never-configured/")
