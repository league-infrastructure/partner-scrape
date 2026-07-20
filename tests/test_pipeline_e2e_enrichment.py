"""End-to-end discovery + enrichment test (ticket 006).

Extends sprint 001's `test_pipeline_e2e.py` walking-skeleton pattern
with the two capabilities this sprint adds: the `generic_html` adapter
(discover via sitemap diff -> extract via the ladder) and the
`LLMEnricher` (enrich + relevance-gate). Runs the *real*
`partner_scrape.pipeline.run()` -- Registry -> Adapter dispatch ->
`LLMEnricher` -> Normalize -> Export -- against a small fixture-only
registry (`tests/fixtures/registry_generic/`) containing:

- `exampleorg.toml` (`generic_html`): reuses ticket 001/002's own
  sitemap-diff and extraction-ladder fixtures
  (`tests/fixtures/sitemaps/events_sitemap.xml`,
  `tests/fixtures/html/*.html`) -- three pages, one per extraction rung:
  JSON-LD (fully dated), `<time datetime>` (dated), and OpenGraph-only
  (undated -- the gap the LLM Enricher exists to close).
- `robotworks.toml` (`tec_rest`): a sprint-001-style structured source,
  proving both extraction paths reach the same export in one run. Its
  one event's title ("Robotics Workshop") is deliberately distinct from
  every `generic_html` fixture title so cross-source dedup never merges
  them -- that is sprint 001's own e2e test's job, not this file's.

A `FixtureLLMClient`-backed `LLMEnricher` is wired through
`pipeline.run(enrichers=[...])` with one canned response per fixture
event title: "Star Party Night" (the OpenGraph-only, undated page) gets
an LLM-recovered date, every event gets LLM classification, and "Beach
Cleanup" is verdicted not-relevant -- proving the relevance gate drops
it from the final `opportunities.json` while its `generic_html` source
siblings and the structured source's event all survive.

No test here opens a socket (a `FixtureFetcher`, matching
`test_pipeline_e2e.py`'s own, raises for any unconfigured URL) or calls
the real Anthropic API (`FixtureLLMClient` never imports `anthropic`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import pytest

from partner_scrape.enrich.cache import EnrichmentCache
from partner_scrape.enrich.enricher import LLMEnricher
from partner_scrape.enrich.llm_client import EnrichmentResult, FixtureLLMClient
from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.pipeline import run

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
REGISTRY_DIR = FIXTURES_DIR / "registry_generic"
SITEMAP_FIXTURES_DIR = FIXTURES_DIR / "sitemaps"
HTML_FIXTURES_DIR = FIXTURES_DIR / "html"
PARTNERS_FIXTURE = FIXTURES_DIR / "partners.json"

#: Fixed "today" (matches sprint 001's e2e test convention) -- every
#: date assertion below is relative to this, never `date.today()`.
TODAY = date(2026, 7, 19)

SITE_URL = "https://example.org"
ROOT_SITEMAP_URL = f"{SITE_URL}/sitemap_index.xml"

#: The three event URLs tests/fixtures/sitemaps/events_sitemap.xml
#: contains -- ticket 001/002's own fixture, reused as-is.
EVENT_URLS = [
    "https://example.org/events/tide-pool-exploration/",
    "https://example.org/events/beach-cleanup/",
    "https://example.org/events/star-party/",
]

TEC_API_BASE = "https://robotworks.example/wp-json/tribe/events/v1/events/"
TEC_PROBE_URL = f"{TEC_API_BASE}?per_page=50&status=publish&start_date=now"
TEC_PAGE1_URL = f"{TEC_API_BASE}?per_page=50&page=1&status=publish&start_date=now"


class NoFixtureResponse(RuntimeError):
    """Raised by FixtureFetcher for a URL with no canned response -- any
    real network attempt fails loudly rather than silently succeeding."""


@dataclass
class FixtureFetcher:
    """Fetcher test double -- returns canned FetchResponses, no socket."""

    responses: dict[str, FetchResponse]
    calls: list[str] = field(default_factory=list)

    def get(self, url: str, headers: dict[str, str] | None = None) -> FetchResponse:
        self.calls.append(url)
        if url not in self.responses:
            raise NoFixtureResponse(f"no fixture response configured for {url!r}")
        return self.responses[url]


def _read(path: Path) -> str:
    return path.read_text()


def _response(body: str, status: int = 200) -> FetchResponse:
    return FetchResponse(url="", status=status, headers={}, body=body)


def _fixture_fetcher() -> FixtureFetcher:
    tec_body = _read(REGISTRY_DIR / "tec_events.json")
    return FixtureFetcher(
        {
            ROOT_SITEMAP_URL: _response(_read(SITEMAP_FIXTURES_DIR / "events_sitemap.xml")),
            EVENT_URLS[0]: _response(_read(HTML_FIXTURES_DIR / "json_ld_event.html")),
            EVENT_URLS[1]: _response(_read(HTML_FIXTURES_DIR / "time_tag_only.html")),
            EVENT_URLS[2]: _response(_read(HTML_FIXTURES_DIR / "opengraph_only.html")),
            TEC_PROBE_URL: _response(tec_body),
            TEC_PAGE1_URL: _response(tec_body),
        }
    )


def _site_dir(tmp_path: Path) -> Path:
    """A tmp_path-backed stand-in for the sibling stem-ecosystem repo --
    never the real `../stem-ecosystem` checkout."""
    site_dir = tmp_path / "stem-ecosystem"
    data_dir = site_dir / "src" / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "partners.json").write_text(PARTNERS_FIXTURE.read_text())
    return site_dir


#: One canned EnrichmentResult per fixture event title, keyed by
#: FixtureLLMClient's default key_fn (event.title). Every title the
#: registry's two sources can produce must have an entry, or the
#: FixtureLLMClient raises KeyError -- a loud failure if this test's
#: fixture set and the enricher's expectations ever drift apart.
_LLM_RESPONSES: dict[str, EnrichmentResult] = {
    # JSON-LD rung: already fully dated by extraction -- the LLM
    # recovers nothing but classifies and verdicts relevant.
    "Tide Pool Exploration": EnrichmentResult(
        areas_of_interest=["Biology / LifeSciences"],
        age_grade_level=["Grades 6-8"],
        cost_range="Less than $25",
        time_of_day=["Morning"],
        relevant=True,
        relevance_reason="Hands-on marine biology exploration for youth.",
    ),
    # <time datetime> rung: already dated -- verdicted NOT relevant, the
    # one event this test expects gated out of the final export.
    "Beach Cleanup": EnrichmentResult(
        relevant=False,
        relevance_reason="General community volunteering, not a STEM learning opportunity.",
    ),
    # OpenGraph-only rung: no rung recovered a date (adapters/generic_html
    # emits it undated) -- the LLM recovers one here, proving SUC-011's
    # date-recovery acceptance criterion end to end.
    "Star Party Night": EnrichmentResult(
        start=datetime(2026, 8, 22, 20, 0, 0),
        end=datetime(2026, 8, 22, 22, 0, 0),
        areas_of_interest=["Physical Science"],
        age_grade_level=["Family"],
        cost_range="Free",
        time_of_day=["Evening"],
        relevant=True,
        relevance_reason="Astronomy observation event for families.",
    ),
    # The structured (tec_rest) source's one event.
    "Robotics Workshop": EnrichmentResult(
        areas_of_interest=["Engineering", "Coding/Computer Science/Cyber Security"],
        age_grade_level=["Grades 6-8"],
        cost_range="Less than $25",
        time_of_day=["Afternoon"],
        relevant=True,
        relevance_reason="Hands-on robotics building for kids.",
    ),
}


def _llm_enricher(cache_dir: Path) -> tuple[LLMEnricher, FixtureLLMClient]:
    llm_client = FixtureLLMClient(responses=dict(_LLM_RESPONSES))
    cache = EnrichmentCache(cache_dir=cache_dir)
    return LLMEnricher(llm_client, cache), llm_client


@pytest.fixture(autouse=True)
def _scrape_cache_dir(tmp_path, monkeypatch):
    """Point SCRAPE_CACHE_DIR at a tmp_path for every test in this file.

    Sitemap Discovery (`discovery/sitemap.py`) reads
    `config.get_scrape_cache_dir()` directly (not injectable) for its
    per-source `<lastmod>` snapshot -- no test here ever touches the
    real configured cache directory.
    """
    monkeypatch.setenv("SCRAPE_CACHE_DIR", str(tmp_path / "scrape_cache"))
    return tmp_path


class TestDiscoveryExtractEnrichGateExport:
    """The ticket's key deliverable: discovery -> fetch -> extract ->
    enrich (classification + date recovery) -> relevance gate ->
    normalize -> export, in one real `pipeline.run()` call."""

    def test_produces_a_valid_opportunities_json(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        fetcher = _fixture_fetcher()
        enricher, _llm_client = _llm_enricher(tmp_path / "enrichment_cache")

        payload = run(
            registry_dir=REGISTRY_DIR,
            site_dir=site_dir,
            fetcher=fetcher,
            enrichers=[enricher],
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

    def test_generic_html_and_structured_events_both_reach_export(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        fetcher = _fixture_fetcher()
        enricher, _llm_client = _llm_enricher(tmp_path / "enrichment_cache")

        payload = run(
            registry_dir=REGISTRY_DIR,
            site_dir=site_dir,
            fetcher=fetcher,
            enrichers=[enricher],
            today=TODAY,
        )

        titles = {record["title"] for record in payload}
        # "Beach Cleanup" is the one fixture event verdicted not-relevant
        # -- gated out. Every other event, from both sources, survives.
        assert titles == {"Tide Pool Exploration", "Star Party Night", "Robotics Workshop"}

    def test_relevance_gate_drops_the_not_relevant_event_only(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        fetcher = _fixture_fetcher()
        enricher, _llm_client = _llm_enricher(tmp_path / "enrichment_cache")

        payload = run(
            registry_dir=REGISTRY_DIR,
            site_dir=site_dir,
            fetcher=fetcher,
            enrichers=[enricher],
            today=TODAY,
        )

        titles = {record["title"] for record in payload}
        assert "Beach Cleanup" not in titles
        # Its own source's other (relevant) events are unaffected --
        # gating is per-event, not per-source (SUC-012).
        assert "Tide Pool Exploration" in titles
        assert "Star Party Night" in titles

    def test_llm_recovers_the_missing_date_and_it_reaches_export(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        fetcher = _fixture_fetcher()
        enricher, _llm_client = _llm_enricher(tmp_path / "enrichment_cache")

        payload = run(
            registry_dir=REGISTRY_DIR,
            site_dir=site_dir,
            fetcher=fetcher,
            enrichers=[enricher],
            today=TODAY,
        )

        [star_party] = [r for r in payload if r["title"] == "Star Party Night"]
        assert star_party["date_start"].startswith("2026-08-22T20:00:00")
        assert star_party["date_end"].startswith("2026-08-22T22:00:00")

    def test_llm_classification_is_applied_to_surviving_events(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        fetcher = _fixture_fetcher()
        enricher, _llm_client = _llm_enricher(tmp_path / "enrichment_cache")

        payload = run(
            registry_dir=REGISTRY_DIR,
            site_dir=site_dir,
            fetcher=fetcher,
            enrichers=[enricher],
            today=TODAY,
        )

        [tide_pool] = [r for r in payload if r["title"] == "Tide Pool Exploration"]
        assert tide_pool["areas_of_interest"] == ["Biology / LifeSciences"]
        assert tide_pool["age_grade_level"] == ["Grades 6-8"]
        assert tide_pool["cost_range"] == "Less than $25"
        assert tide_pool["time_of_day"] == ["Morning"]

        [robotics] = [r for r in payload if r["title"] == "Robotics Workshop"]
        assert robotics["areas_of_interest"] == [
            "Engineering",
            "Coding/Computer Science/Cyber Security",
        ]

    def test_llm_client_is_called_once_per_collected_event(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        fetcher = _fixture_fetcher()
        enricher, llm_client = _llm_enricher(tmp_path / "enrichment_cache")

        run(
            registry_dir=REGISTRY_DIR,
            site_dir=site_dir,
            fetcher=fetcher,
            enrichers=[enricher],
            today=TODAY,
        )

        # All four collected events (three generic_html + one tec_rest)
        # reach the LLM Client exactly once each -- including the one
        # later gated out (enrichment happens before gating, SUC-011
        # before SUC-012).
        assert {e.title for e in llm_client.calls} == {
            "Tide Pool Exploration",
            "Beach Cleanup",
            "Star Party Night",
            "Robotics Workshop",
        }
        assert len(llm_client.calls) == 4

    def test_no_network_access_every_fetch_is_a_known_fixture_url(self, tmp_path):
        site_dir = _site_dir(tmp_path)
        fetcher = _fixture_fetcher()
        enricher, _llm_client = _llm_enricher(tmp_path / "enrichment_cache")

        run(
            registry_dir=REGISTRY_DIR,
            site_dir=site_dir,
            fetcher=fetcher,
            enrichers=[enricher],
            today=TODAY,
        )

        assert set(fetcher.calls) <= {
            ROOT_SITEMAP_URL,
            *EVENT_URLS,
            TEC_PROBE_URL,
            TEC_PAGE1_URL,
        }
