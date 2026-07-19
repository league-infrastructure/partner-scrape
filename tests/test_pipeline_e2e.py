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
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import pytest

from partner_scrape.fetch import PlaywrightFetcher, PoliteFetcher, Throttle
from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.model import Event
from partner_scrape.observability import YieldReporter, load_snapshot, save_snapshot
from partner_scrape.pipeline import run

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
E2E_REGISTRY_DIR = FIXTURES_DIR / "e2e_registry"
PARTNERS_FIXTURE = FIXTURES_DIR / "partners.json"

#: Ticket 005 fixture directories -- see this file's bottom two test
#: classes (per-source fetch_strategy selection, and the flagship
#: end-to-end proof).
FETCH_STRATEGY_REGISTRY_DIR = FIXTURES_DIR / "e2e_fetch_strategy"
FLAGSHIP_REGISTRY_DIR = FIXTURES_DIR / "e2e_flagship_registry"
FETCH_FIXTURES_DIR = FIXTURES_DIR / "fetch"

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


@dataclass
class SpyReporter:
    """A spy `Reporter` double -- records every call it receives
    verbatim, no computation -- proving ticket 004-001's two hook call
    sites actually fire, with the right data, over a real
    `pipeline.run()` call (sprint.md SUC-018's own acceptance
    criterion)."""

    source_calls: list[tuple[str, str, list[Event], Exception | None]] = field(
        default_factory=list
    )
    opportunities_calls: list[list[object]] = field(default_factory=list)

    def record_source(self, source_id, org_name, events, error=None):
        self.source_calls.append((source_id, org_name, list(events), error))

    def record_opportunities(self, opportunities):
        self.opportunities_calls.append(list(opportunities))


class TestReporterHook:
    """Ticket 004-001: the `Reporter` hook is exercised the same way
    `Enricher` already is -- a real `pipeline.run()` call over the
    existing `e2e_registry` fixtures (which include `brokensource.toml`,
    the deliberately-failing source), with a spy double asserting both
    call sites fire with correct data."""

    def test_reporter_defaults_to_none_and_is_a_no_op(self, tmp_path):
        # No reporter passed at all -- proves the new parameter is
        # truly additive/optional, same shape as TestEnricherHook's own
        # "defaults to empty and is a no-op" case above.
        site_dir = _site_dir(tmp_path)
        fetcher = _fixture_fetcher()

        payload = run(
            registry_dir=E2E_REGISTRY_DIR, site_dir=site_dir, fetcher=fetcher, today=TODAY
        )

        assert len(payload) == 2

    def test_record_source_called_once_per_active_source_with_correct_data(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        fetcher = _fixture_fetcher()
        spy = SpyReporter()

        run(
            registry_dir=E2E_REGISTRY_DIR,
            site_dir=site_dir,
            fetcher=fetcher,
            reporter=spy,
            today=TODAY,
        )

        # E2E_REGISTRY_DIR has exactly three active sources: brokensource
        # (fails), coastalrootsfarm, thelivingcoast.
        called_source_ids = {source_id for source_id, *_ in spy.source_calls}
        assert called_source_ids == {"brokensource", "coastalrootsfarm", "thelivingcoast"}
        assert len(spy.source_calls) == 3

        by_source = {source_id: (org, events, error) for source_id, org, events, error in spy.source_calls}

        # Success branch: real events, no error.
        coastal_org, coastal_events, coastal_error = by_source["coastalrootsfarm"]
        assert coastal_error is None
        assert coastal_org == "Coastal Roots Farm"
        assert len(coastal_events) == 2  # tide pool + spring planting (see TestEnricherHook)
        assert all(isinstance(e, Event) for e in coastal_events)

        living_org, living_events, living_error = by_source["thelivingcoast"]
        assert living_error is None
        assert len(living_events) == 4  # tide pool dup + 3 recurring story time occurrences

        # Failure-isolation branch: [] + the caught exception, run still
        # continues -- proves the isolated exception is reported, not
        # swallowed silently or allowed to abort the run.
        broken_org, broken_events, broken_error = by_source["brokensource"]
        assert broken_events == []
        assert isinstance(broken_error, Exception)

    def test_record_opportunities_called_once_with_final_opportunity_list(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        fetcher = _fixture_fetcher()
        spy = SpyReporter()

        payload = run(
            registry_dir=E2E_REGISTRY_DIR,
            site_dir=site_dir,
            fetcher=fetcher,
            reporter=spy,
            today=TODAY,
        )

        assert len(spy.opportunities_calls) == 1
        reported_opportunities = spy.opportunities_calls[0]
        # normalize_run()'s own output includes "Spring Planting Day"
        # (a past event) -- export_opportunities()'s current/upcoming
        # filter is what drops it to the final 2-record payload, and
        # that filter runs *after* this hook fires (sprint.md: "before
        # export_opportunities() strips .sources"). So the reported
        # list is a superset of payload's titles, not an exact match.
        payload_titles = {r["title"] for r in payload}
        reported_titles = {opp.title for opp in reported_opportunities}
        assert payload_titles <= reported_titles
        assert "Spring Planting Day" in reported_titles

        # .sources is still present at report time (export strips it
        # only afterward) -- proves the hook fires before the strip.
        for opp in reported_opportunities:
            assert hasattr(opp, "sources")
            assert opp.sources  # non-empty frozenset of contributing source_ids

    def test_a_source_that_raises_still_reports_and_does_not_abort_the_run(self, tmp_path):
        # brokensource.toml is alphabetically first (see
        # TestLimitAndSourceFilters' own comment) -- limit=1 runs only
        # it, isolating the failure-reporting assertion from the two
        # healthy sources entirely.
        site_dir = _site_dir(tmp_path)
        fetcher = _fixture_fetcher()
        spy = SpyReporter()

        payload = run(
            registry_dir=E2E_REGISTRY_DIR,
            site_dir=site_dir,
            fetcher=fetcher,
            reporter=spy,
            limit=1,
            today=TODAY,
        )

        assert payload == []  # run continues, produces empty (valid) output
        assert len(spy.source_calls) == 1
        source_id, _org, events, error = spy.source_calls[0]
        assert source_id == "brokensource"
        assert events == []
        assert isinstance(error, Exception)
        # And record_opportunities still fires exactly once, with an
        # empty list -- the run completed its full sequence, it just
        # had nothing to normalize.
        assert spy.opportunities_calls == [[]]


class TestYieldReporterEndToEnd:
    """Ticket 004-002's own end-to-end acceptance criterion (sprint.md
    SUC-018): a real `YieldReporter` -- not the spy `SpyReporter` above
    -- run twice over the same fixture registry, second run with
    coastalrootsfarm's fixture responses swapped to a real, well-formed
    zero-event TEC page, must flag that source zero-yield in the second
    run's report. This is the exact Fleet/Birch safety net sprint.md's
    Goals section names: a previously-productive source silently going
    to zero must be visible without an operator comparing runs by hand.
    """

    def test_second_run_flags_a_previously_productive_source_as_zero_yield(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        first_now = datetime(2026, 7, 19, 8, 0)
        second_now = datetime(2026, 7, 26, 8, 0)

        # First run: normal fixture responses -- coastalrootsfarm finds
        # its usual 2 events (tide pool + spring planting; see
        # TestReporterHook's own assertion of this count above).
        first_reporter = YieldReporter()
        run(
            registry_dir=E2E_REGISTRY_DIR,
            site_dir=site_dir,
            fetcher=_fixture_fetcher(),
            reporter=first_reporter,
            today=TODAY,
        )
        first_report = first_reporter.report(previous_snapshot={}, now=first_now)

        by_id_1 = {s.source_id: s for s in first_report.sources}
        assert by_id_1["coastalrootsfarm"].found == 2
        assert by_id_1["coastalrootsfarm"].zero_yield is False

        snapshot_path = tmp_path / "yield-history.json"
        save_snapshot(snapshot_path, first_report)

        # Second run: coastalrootsfarm's fixture responses swapped to a
        # real, well-formed zero-event TEC page (not the fetch failure
        # brokensource.toml exercises) -- a genuine "found nothing this
        # week" run, while the other two sources are unchanged.
        empty_tec_body = json.dumps({"total": 0, "total_pages": 0, "events": []})
        second_fetcher = _fixture_fetcher()
        second_fetcher.responses[TEC_PROBE_URL] = _response(empty_tec_body)
        second_fetcher.responses[TEC_PAGE1_URL] = _response(empty_tec_body)

        second_reporter = YieldReporter()
        run(
            registry_dir=E2E_REGISTRY_DIR,
            site_dir=site_dir,
            fetcher=second_fetcher,
            reporter=second_reporter,
            today=TODAY,
        )
        previous_snapshot = load_snapshot(snapshot_path)
        second_report = second_reporter.report(previous_snapshot=previous_snapshot, now=second_now)

        by_id_2 = {s.source_id: s for s in second_report.sources}
        coastal = by_id_2["coastalrootsfarm"]
        assert coastal.found == 0
        assert coastal.previous_found == 2
        assert coastal.zero_yield is True
        # A genuine empty response, not an adapter failure -- distinct
        # from brokensource's error-carrying SourceYield.
        assert coastal.error is None

        # The other two sources are unaffected by coastalrootsfarm's
        # swap -- proves per-source isolation in the report too.
        assert by_id_2["thelivingcoast"].zero_yield is False


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


# =============================================================================
# Ticket 005: per-source fetch_strategy wiring + flagship end-to-end proof
#
# Two concerns, two fixture registries:
#
# 1. Pipeline's per-source Fetcher *selection* mechanics (lazy, at-most-
#    once headless construction; isolation of a headless failure; a
#    pre-existing static source's fetch path staying untouched) --
#    exercised over tests/fixtures/e2e_fetch_strategy/, a small
#    tec_rest-only registry chosen to keep these tests focused purely on
#    Pipeline's own selection logic, decoupled from any particular
#    adapter's discovery mechanics.
# 2. The sprint's own Success Criteria/SUC-016 proof -- Birch Aquarium
#    (localist), Fleet Science Center (listing_html), a pre-existing
#    regression source (tec_rest, static), and a headless-flagged
#    fixture source, all run through one real `pipeline.run()` call --
#    exercised over tests/fixtures/e2e_flagship_registry/.
#
# Both use tec_rest for their headless-flagged fixture source(s) rather
# than generic_html: SUC-015's own Main Flow is explicit that headless
# routing is a Fetch-layer concern, exercised identically "for any
# adapter type" -- tec_rest just needs the fewest fixture URLs to prove
# it, and the real Wix sites this capability targets are explicitly out
# of this sprint's registration scope (sprint.md's Open Question 1).
# =============================================================================

HEADLESS_A_API_BASE = "https://headless-a.example/wp-json/tribe/events/v1/events/"
HEADLESS_A_PROBE_URL = f"{HEADLESS_A_API_BASE}?per_page=1&status=publish&start_date=now"
HEADLESS_A_PAGE1_URL = f"{HEADLESS_A_API_BASE}?per_page=50&page=1&status=publish&start_date=now"

HEADLESS_B_API_BASE = "https://headless-b.example/wp-json/tribe/events/v1/events/"
HEADLESS_B_PROBE_URL = f"{HEADLESS_B_API_BASE}?per_page=1&status=publish&start_date=now"
HEADLESS_B_PAGE1_URL = f"{HEADLESS_B_API_BASE}?per_page=50&page=1&status=publish&start_date=now"

WORKING_API_BASE = "https://workingsource.example/wp-json/tribe/events/v1/events/"
WORKING_PROBE_URL = f"{WORKING_API_BASE}?per_page=1&status=publish&start_date=now"
WORKING_PAGE1_URL = f"{WORKING_API_BASE}?per_page=50&page=1&status=publish&start_date=now"


@dataclass
class _FixtureNavigationResponse:
    """Stand-in for a real Playwright navigation ``Response`` -- the only
    piece of it ``PlaywrightFetcher`` reads is ``status``.

    Mirrors ``test_fetch_headless.py``'s own fixture double; kept as a
    separate, file-local definition rather than importing across test
    files, matching this suite's existing per-file fixture-double
    convention (every other test file in this suite defines its own
    ``FixtureFetcher`` rather than sharing one).
    """

    status: int
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class FixtureHeadlessPage:
    """``HeadlessPage`` test double -- returns canned rendered HTML per
    URL, no real browser process involved. See
    ``partner_scrape.fetch.headless.HeadlessPage`` and
    ``test_fetch_headless.py``'s identically-shaped double.
    """

    pages: dict[str, tuple[int, str]]
    calls: list[dict[str, object]] = field(default_factory=list)
    _current_url: str | None = field(default=None, repr=False)

    def goto(self, url: str, timeout: float | None = None, wait_until: str | None = None):
        self.calls.append({"url": url, "timeout": timeout, "wait_until": wait_until})
        status, _html = self.pages[url]
        self._current_url = url
        return _FixtureNavigationResponse(status=status)

    def content(self) -> str:
        assert self._current_url is not None
        _status, html = self.pages[self._current_url]
        return html


class _CountingHeadlessFactory:
    """Spy ``headless_fetcher_factory``: records how many times Pipeline
    actually invoked it (ticket 005's "constructed at most once per
    run(), only when at least one active source needs it" Acceptance
    Criterion) and returns a fixed fetcher on every call.
    """

    def __init__(self, fetcher: object) -> None:
        self._fetcher = fetcher
        self.call_count = 0

    def __call__(self):
        self.call_count += 1
        return self._fetcher


class TestPerSourceFetchStrategySelectionLaziness:
    """Pipeline reads ``acquisition_policy.get("fetch_strategy",
    "static")`` per source (registry/schema.py's new default, also
    ticket 005) and constructs the headless Fetcher lazily -- never
    eagerly, never more than once per ``run()`` call.
    """

    def test_headless_factory_never_called_when_no_source_is_flagged_headless(self, tmp_path):
        # Reuses sprint 001's own e2e registry (TestWalkingSkeletonEndToEnd's
        # E2E_REGISTRY_DIR) -- every source there predates fetch_strategy
        # entirely, so this also doubles as this ticket's "byte-identical
        # behavior for a pre-existing fixture source" proof: the default
        # Fetcher path runs exactly as it did before this ticket, and the
        # headless construction path is never even touched.
        site_dir = _site_dir(tmp_path)
        fetcher = _fixture_fetcher()
        spy = _CountingHeadlessFactory(FixtureFetcher({}))

        payload = run(
            registry_dir=E2E_REGISTRY_DIR,
            site_dir=site_dir,
            fetcher=fetcher,
            headless_fetcher_factory=spy,
            today=TODAY,
        )

        assert spy.call_count == 0
        # And the run's own (unrelated to this ticket) behavior is
        # completely unaffected -- the same two opportunities as every
        # other test in this file's walking-skeleton class.
        assert len(payload) == 2

    def test_headless_factory_is_called_exactly_once_for_two_headless_sources(self, tmp_path):
        # headless-a.toml and headless-b.toml are the two
        # alphabetically-first source_ids in FETCH_STRATEGY_REGISTRY_DIR
        # (ahead of workingsource.toml) -- limit=2 activates exactly
        # those two, both flagged headless, and nothing else.
        site_dir = _site_dir(tmp_path)
        static_fetcher = FixtureFetcher({})  # must never be touched
        a_body = (FETCH_STRATEGY_REGISTRY_DIR / "headless_a_events.json").read_text()
        b_body = (FETCH_STRATEGY_REGISTRY_DIR / "headless_b_events.json").read_text()
        headless_fetcher = FixtureFetcher(
            {
                HEADLESS_A_PROBE_URL: _response(a_body),
                HEADLESS_A_PAGE1_URL: _response(a_body),
                HEADLESS_B_PROBE_URL: _response(b_body),
                HEADLESS_B_PAGE1_URL: _response(b_body),
            }
        )
        spy = _CountingHeadlessFactory(headless_fetcher)

        payload = run(
            registry_dir=FETCH_STRATEGY_REGISTRY_DIR,
            site_dir=site_dir,
            fetcher=static_fetcher,
            headless_fetcher_factory=spy,
            limit=2,
            today=TODAY,
        )

        assert spy.call_count == 1
        assert static_fetcher.calls == []
        titles = {r["title"] for r in payload}
        assert titles == {"Headless Fixture A Event", "Headless Fixture B Event"}


class TestHeadlessSourceFailureIsolation:
    """SUC-015's Error Flow: ``playwright`` unavailable for a source
    flagged ``headless`` fails only that source's ``adapters.run(...)``
    call -- caught by Pipeline's existing per-source try/except
    (SUC-008), no new error-handling code. Exercises the REAL default
    ``headless_fetcher_factory`` (no factory injected), with the
    deferred ``import playwright`` forced to fail exactly as
    ``test_fetch_headless.py``'s own ``TestPlaywrightNotInstalled``
    does -- proving the production wiring itself, not just a test
    double standing in for it.
    """

    def test_playwright_not_installed_is_isolated_others_still_produce_output(
        self, tmp_path, monkeypatch, caplog
    ):
        import logging

        # PoliteFetcher()'s default cache_dir (built by Pipeline's real
        # `_build_default_headless_fetcher`, since no
        # headless_fetcher_factory is injected below) reads
        # SCRAPE_CACHE_DIR -- point it at a tmp_path so this test never
        # touches the real configured cache directory.
        monkeypatch.setenv("SCRAPE_CACHE_DIR", str(tmp_path / "scrape_cache"))
        # Force the deferred `from playwright.sync_api import
        # sync_playwright` import to fail deterministically, matching
        # test_fetch_headless.py's TestPlaywrightNotInstalled.
        monkeypatch.setitem(sys.modules, "playwright", None)
        monkeypatch.setitem(sys.modules, "playwright.sync_api", None)

        site_dir = _site_dir(tmp_path)
        working_body = (FETCH_STRATEGY_REGISTRY_DIR / "workingsource_events.json").read_text()
        static_fetcher = FixtureFetcher(
            {
                WORKING_PROBE_URL: _response(working_body),
                WORKING_PAGE1_URL: _response(working_body),
            }
        )

        with caplog.at_level(logging.ERROR, logger="partner_scrape.pipeline"):
            payload = run(
                registry_dir=FETCH_STRATEGY_REGISTRY_DIR,
                site_dir=site_dir,
                fetcher=static_fetcher,
                # headless_fetcher_factory omitted -- exercises Pipeline's
                # real default production path.
                today=TODAY,
            )

        # Both headless-flagged sources (headless-a, headless-b) fail --
        # logged, isolated -- while the static-strategy workingsource.toml
        # still produces output.
        titles = {r["title"] for r in payload}
        assert titles == {"Working Source Event"}
        assert "headless-a" in caplog.text
        assert "headless-b" in caplog.text


class TestFlagshipEndToEnd:
    """SUC-016: Birch Aquarium (localist) + Fleet Science Center
    (listing_html) + a pre-existing regression source (tec_rest,
    static) + a headless-flagged fixture source (tec_rest, headless),
    run through the real Pipeline end to end -- discovery -> fetch ->
    extract -> (empty) enrich -> normalize -> export -- asserting both
    flagship organizations' events reach the final opportunities.json-
    shaped output. Entirely offline and without playwright installed:
    the headless-flagged source's Fetcher chain is exercised through
    ticket 001's fixture page_factory double (FixtureHeadlessPage
    above), wrapped by a real PoliteFetcher+PlaywrightFetcher pair --
    never a real browser, never a real socket.
    """

    BIRCH_API_BASE = "https://calendar.fixture.edu/api/2/events"
    BIRCH_GROUP_ID = "49845193640602"
    BIRCH_DAYS = 180
    BIRCH_PROBE_URL = f"{BIRCH_API_BASE}?group_id={BIRCH_GROUP_ID}&days={BIRCH_DAYS}&pp=1&page=1"
    BIRCH_PAGE1_URL = f"{BIRCH_API_BASE}?group_id={BIRCH_GROUP_ID}&days={BIRCH_DAYS}&pp=50&page=1"

    FLEET_SITE_URL = "https://fleetscience.fixture"
    FLEET_LISTING_URL = f"{FLEET_SITE_URL}/events"
    FLEET_DYNAMIC_EARTH_URL = f"{FLEET_SITE_URL}/events/dynamic-earth"
    FLEET_ROBOT_REVOLUTION_URL = f"{FLEET_SITE_URL}/events/robot-revolution"

    COASTAL_API_BASE = "https://coastalrootsfarm.fixture/wp-json/tribe/events/v1/events/"
    COASTAL_PROBE_URL = f"{COASTAL_API_BASE}?per_page=1&status=publish&start_date=now"
    COASTAL_PAGE1_URL = f"{COASTAL_API_BASE}?per_page=50&page=1&status=publish&start_date=now"

    WIX_API_BASE = "https://wix-fixture.example/wp-json/tribe/events/v1/events/"
    WIX_PROBE_URL = f"{WIX_API_BASE}?per_page=1&status=publish&start_date=now"
    WIX_PAGE1_URL = f"{WIX_API_BASE}?per_page=50&page=1&status=publish&start_date=now"
    WIX_ROBOTS_URL = "https://wix-fixture.example/robots.txt"

    def _static_fetcher(self) -> FixtureFetcher:
        birch_body = (FLAGSHIP_REGISTRY_DIR / "birch_events.json").read_text()
        fleet_listing_body = (FLAGSHIP_REGISTRY_DIR / "fleet_listing.html").read_text()
        fleet_dynamic_earth_body = (
            FLAGSHIP_REGISTRY_DIR / "fleet_detail_dynamic_earth.html"
        ).read_text()
        fleet_robot_revolution_body = (
            FLAGSHIP_REGISTRY_DIR / "fleet_detail_robot_revolution.html"
        ).read_text()
        coastal_body = (FLAGSHIP_REGISTRY_DIR / "coastalrootsfarm_events.json").read_text()

        return FixtureFetcher(
            {
                self.BIRCH_PROBE_URL: _response(birch_body),
                self.BIRCH_PAGE1_URL: _response(birch_body),
                self.FLEET_LISTING_URL: _response(fleet_listing_body),
                self.FLEET_DYNAMIC_EARTH_URL: _response(fleet_dynamic_earth_body),
                self.FLEET_ROBOT_REVOLUTION_URL: _response(fleet_robot_revolution_body),
                self.COASTAL_PROBE_URL: _response(coastal_body),
                self.COASTAL_PAGE1_URL: _response(coastal_body),
                # WIX_* URLs deliberately absent -- the headless-flagged
                # source must never be reachable through this (static)
                # Fetcher; see test_headless_source_never_reaches_the_
                # static_fetcher_and_vice_versa below.
            }
        )

    def _headless_page(self) -> FixtureHeadlessPage:
        wix_body = (FLAGSHIP_REGISTRY_DIR / "wix_events.json").read_text()
        robots_body = (FETCH_FIXTURES_DIR / "robots_allow_all.txt").read_text()
        return FixtureHeadlessPage(
            pages={
                self.WIX_ROBOTS_URL: (200, robots_body),
                self.WIX_PROBE_URL: (200, wix_body),
                self.WIX_PAGE1_URL: (200, wix_body),
            }
        )

    def _run(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        static_fetcher = self._static_fetcher()
        headless_page = self._headless_page()
        factory_calls: list[int] = []

        def headless_fetcher_factory():
            factory_calls.append(1)
            # A real PoliteFetcher wrapping a real PlaywrightFetcher --
            # only page_factory is a fixture double -- so this exercises
            # the exact same robots.txt/rate-limit/cache path a real
            # headless fetch would (SUC-015's own acceptance criterion),
            # not a bypass of it. The Throttle's clock/sleep are faked
            # (matching test_fetch_cache.py's own convention) so this
            # test never real-sleeps for per-domain rate limiting.
            return PoliteFetcher(
                cache_dir=tmp_path / "headless_cache",
                fetcher=PlaywrightFetcher(page_factory=lambda: headless_page),
                throttle=Throttle(clock=lambda: 0.0, sleep=lambda seconds: None),
            )

        payload = run(
            registry_dir=FLAGSHIP_REGISTRY_DIR,
            site_dir=site_dir,
            fetcher=static_fetcher,
            headless_fetcher_factory=headless_fetcher_factory,
            today=TODAY,
        )
        return payload, static_fetcher, headless_page, factory_calls

    def test_birch_and_fleet_events_reach_the_final_opportunities_output(self, tmp_path):
        payload, _static_fetcher, _headless_page, factory_calls = self._run(tmp_path)

        partner_names = {r["partner_name"] for r in payload}
        assert "Birch Aquarium at Scripps" in partner_names
        assert "Fleet Science Center" in partner_names

        titles = {r["title"] for r in payload}
        # Birch (localist): id-based dedup within the fetched page
        # collapses the two "Shark Summer" rows to one Event -- SUC-013's
        # own acceptance criterion, reconfirmed here in the full chain.
        assert "Shark Summer" in titles
        assert "Tide Pool Discovery Lab" in titles
        # Fleet (listing_html): both discovered/extracted pages.
        assert "Dynamic Earth" in titles
        assert "Robot Revolution" in titles

        # The headless Fetcher is built lazily, at most once per run().
        assert factory_calls == [1]

    def test_regression_and_headless_sources_also_reach_export(self, tmp_path):
        # Not SUC-016's own required assertion, but this ticket's other
        # two Acceptance Criteria bullets (the pre-existing regression
        # source's fetch path is unaffected; the headless-flagged
        # source's Events survive the same chain) -- proven in the same
        # single real pipeline.run() call as the flagship proof above.
        payload, _static_fetcher, _headless_page, _factory_calls = self._run(tmp_path)

        titles = {r["title"] for r in payload}
        assert "Regenerative Farming Day" in titles
        assert "Wix Fixture Event" in titles

    def test_headless_source_never_reaches_the_static_fetcher_and_vice_versa(self, tmp_path):
        _payload, static_fetcher, headless_page, _factory_calls = self._run(tmp_path)

        assert self.WIX_PROBE_URL not in static_fetcher.calls
        assert self.WIX_PAGE1_URL not in static_fetcher.calls

        navigated = {call["url"] for call in headless_page.calls}
        assert self.WIX_PROBE_URL in navigated
        assert self.BIRCH_PROBE_URL not in navigated
        assert self.FLEET_LISTING_URL not in navigated
        assert self.COASTAL_PROBE_URL not in navigated

    def test_no_network_access_every_static_fetch_is_a_known_fixture_url(self, tmp_path):
        _payload, static_fetcher, _headless_page, _factory_calls = self._run(tmp_path)

        assert set(static_fetcher.calls) <= {
            self.BIRCH_PROBE_URL,
            self.BIRCH_PAGE1_URL,
            self.FLEET_LISTING_URL,
            self.FLEET_DYNAMIC_EARTH_URL,
            self.FLEET_ROBOT_REVOLUTION_URL,
            self.COASTAL_PROBE_URL,
            self.COASTAL_PAGE1_URL,
        }
