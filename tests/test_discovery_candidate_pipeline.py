"""Tests for partner_scrape.discovery.candidate_pipeline: sequences Hub
Scan through an optional Relevance Gate into the Candidate Review Queue.

Every test drives ``discover_candidates`` through a fixture ``Fetcher``
returning recorded hub-page HTML (``tests/fixtures/hubs/``), a fixture
Source Registry directory (``tests/fixtures/hub_scan_registry/``) for
Hub Scan's own dedup check, and a ``tmp_path``-based candidates
directory -- no test here opens a real network socket or requires
``ANTHROPIC_API_KEY``. ``TestNeverRepublishesHubContent`` is the
central, ticket-required acceptance criterion: the concrete, testable
form of issue 09's "never republish the hub's own data" mandate, one
level up the call chain from ``test_discovery_hub_scan.py``'s own class
of the same name.
"""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from pathlib import Path

from partner_scrape.discovery import candidate_pipeline
from partner_scrape.discovery.candidate_pipeline import discover_candidates
from partner_scrape.discovery.hub_scan import OrgCandidate
from partner_scrape.enrich.cache import EnrichmentCache
from partner_scrape.enrich.enricher import LLMEnricher
from partner_scrape.enrich.llm_client import EnrichmentResult, FixtureLLMClient
from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.registry.candidates import list_candidates
from partner_scrape.registry.hub_schema import HubConfig

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "hubs"
REGISTRY_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "hub_scan_registry"

HUB_ORIGIN = "https://examplehub.org"
CALENDAR_URL = f"{HUB_ORIGIN}/calendar"
ROBOTS_URL = f"{HUB_ORIGIN}/robots.txt"

_ALLOW_ALL_ROBOTS = "User-agent: *\nDisallow:\n"

# The fixture hub page (tests/fixtures/hubs/example_hub.html) surfaces
# exactly these two genuinely-new orgs (see test_discovery_hub_scan.py):
RELEVANT_ORG = "Brand New STEM Org"
NOT_RELEVANT_ORG = "Another New Org"


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text()


def _response(body: str, status: int = 200) -> FetchResponse:
    return FetchResponse(url="", status=status, headers={}, body=body)


@dataclass
class FixtureFetcher:
    """Fetcher test double -- returns canned FetchResponses, no socket.

    A URL absent from ``responses`` raises ``KeyError`` -- a loud
    failure if this call chain fetches something it shouldn't.
    """

    responses: dict[str, FetchResponse]
    calls: list[str] = field(default_factory=list)

    def get(self, url: str, headers: dict[str, str] | None = None) -> FetchResponse:
        self.calls.append(url)
        return self.responses[url]


def _fetcher() -> FixtureFetcher:
    return FixtureFetcher(
        {
            ROBOTS_URL: _response(_ALLOW_ALL_ROBOTS),
            CALENDAR_URL: _response(_read_fixture("example_hub.html")),
        }
    )


def _hub(hub_id: str = "example_hub") -> HubConfig:
    return HubConfig(hub_id=hub_id, hub_name="Example Hub", page_urls=[CALENDAR_URL])


def _relevance_gate(tmp_path: Path, *, relevant_org_names: set[str]) -> LLMEnricher:
    """A real LLMEnricher wired to a FixtureLLMClient keyed by org_name
    (the synthetic Event's title) -- verdicts every candidate in
    ``relevant_org_names`` relevant=True, everything else relevant=False.
    """
    responses = {
        RELEVANT_ORG: EnrichmentResult(relevant=RELEVANT_ORG in relevant_org_names),
        NOT_RELEVANT_ORG: EnrichmentResult(relevant=NOT_RELEVANT_ORG in relevant_org_names),
    }
    return LLMEnricher(FixtureLLMClient(responses=responses), EnrichmentCache(cache_dir=tmp_path))


class TestScansConfiguredHubs:
    def test_candidates_from_every_hub_are_gathered(self, tmp_path):
        written = discover_candidates(
            [_hub()],
            _fetcher(),
            sources_dir=REGISTRY_FIXTURES_DIR,
            candidates_dir=tmp_path,
        )

        org_names = {c.org_name for c in written}
        assert org_names == {RELEVANT_ORG, NOT_RELEVANT_ORG}

    def test_no_hubs_writes_nothing(self, tmp_path):
        written = discover_candidates(
            [], _fetcher(), sources_dir=REGISTRY_FIXTURES_DIR, candidates_dir=tmp_path
        )

        assert written == []
        assert list(tmp_path.glob("*.toml")) == []


class TestNoEnricherSkipsRelevanceGating:
    def test_omitting_enricher_queues_every_deduped_candidate(self, tmp_path):
        written = discover_candidates(
            [_hub()],
            _fetcher(),
            sources_dir=REGISTRY_FIXTURES_DIR,
            candidates_dir=tmp_path,
        )

        org_names = {c.org_name for c in written}
        assert org_names == {RELEVANT_ORG, NOT_RELEVANT_ORG}
        assert len(list_candidates(tmp_path)) == 2


class TestRelevanceGateFiltersCandidates:
    def test_only_relevant_candidates_are_written(self, tmp_path):
        enricher = _relevance_gate(tmp_path, relevant_org_names={RELEVANT_ORG})

        written = discover_candidates(
            [_hub()],
            _fetcher(),
            enricher,
            sources_dir=REGISTRY_FIXTURES_DIR,
            candidates_dir=tmp_path,
        )

        org_names = {c.org_name for c in written}
        assert org_names == {RELEVANT_ORG}

    def test_not_relevant_candidates_are_never_queued_on_disk(self, tmp_path):
        enricher = _relevance_gate(tmp_path, relevant_org_names={RELEVANT_ORG})

        discover_candidates(
            [_hub()],
            _fetcher(),
            enricher,
            sources_dir=REGISTRY_FIXTURES_DIR,
            candidates_dir=tmp_path,
        )

        stub_org_names = {stub.org_name for stub in list_candidates(tmp_path)}
        assert stub_org_names == {RELEVANT_ORG}

    def test_all_candidates_not_relevant_writes_nothing(self, tmp_path):
        enricher = _relevance_gate(tmp_path, relevant_org_names=set())

        written = discover_candidates(
            [_hub()],
            _fetcher(),
            enricher,
            sources_dir=REGISTRY_FIXTURES_DIR,
            candidates_dir=tmp_path,
        )

        assert written == []


class TestDedupAgainstExistingCandidates:
    def test_running_discovery_twice_does_not_duplicate_the_queue(self, tmp_path):
        first = discover_candidates(
            [_hub()], _fetcher(), sources_dir=REGISTRY_FIXTURES_DIR, candidates_dir=tmp_path
        )
        second = discover_candidates(
            [_hub()], _fetcher(), sources_dir=REGISTRY_FIXTURES_DIR, candidates_dir=tmp_path
        )

        assert len(first) == 2
        assert second == []
        assert len(list_candidates(tmp_path)) == 2


class TestNeverRepublishesHubContent:
    """The concrete, testable form of issue 09's "never republish the
    hub's own data" mandate -- this ticket's Central Acceptance
    Criterion (sprint.md's Test Strategy: "Candidate pipeline: asserts
    that running discover_candidates() against a fixture hub never calls
    normalize.run() or export_opportunities() and never writes
    opportunities.json").
    """

    def test_discover_candidates_never_calls_normalize_run(self, monkeypatch, tmp_path):
        # partner_scrape/normalize/__init__.py does
        # `from partner_scrape.normalize.run import run`, which shadows
        # the `run` *submodule* attribute on the `normalize` package with
        # the function itself -- so the function under test (patched
        # here) is what any real caller would actually reach via
        # `normalize.run(...)`.
        import partner_scrape.normalize as normalize_pkg

        def _boom(*args, **kwargs):
            raise AssertionError("discover_candidates must never call normalize.run()")

        monkeypatch.setattr(normalize_pkg, "run", _boom)

        discover_candidates(
            [_hub()], _fetcher(), sources_dir=REGISTRY_FIXTURES_DIR, candidates_dir=tmp_path
        )  # must not raise

    def test_discover_candidates_never_calls_export_opportunities(self, monkeypatch, tmp_path):
        import partner_scrape.export.writer as export_writer

        def _boom(*args, **kwargs):
            raise AssertionError("discover_candidates must never call export_opportunities()")

        monkeypatch.setattr(export_writer, "export_opportunities", _boom)

        discover_candidates(
            [_hub()], _fetcher(), sources_dir=REGISTRY_FIXTURES_DIR, candidates_dir=tmp_path
        )  # must not raise

    def test_discover_candidates_never_writes_opportunities_json(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SCRAPE_CACHE_DIR", str(tmp_path))

        discover_candidates(
            [_hub()],
            _fetcher(),
            sources_dir=REGISTRY_FIXTURES_DIR,
            candidates_dir=tmp_path / "candidates",
        )

        assert not list(tmp_path.rglob("opportunities.json"))

    def test_candidate_pipeline_module_never_imports_pipeline(self):
        # AC: "discovery/candidate_pipeline.py ... does not import
        # anything from pipeline.py" -- parsed via AST rather than a
        # substring search, so the module's own prose (which mentions
        # `pipeline.py`/`pipeline.Enricher` in its docstring, explaining
        # exactly why it doesn't import them) can never produce a false
        # positive or false negative.
        module_path = Path(candidate_pipeline.__file__)
        tree = ast.parse(module_path.read_text())

        imported_modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)

        assert not any(name == "pipeline" or name.endswith(".pipeline") for name in imported_modules)

    def test_candidate_pipeline_module_imports_from_enrich_enricher_family(self):
        # AC: "imports from enrich.enricher (or defines its own local
        # Protocol)" -- this module defines its own local RelevanceGate
        # Protocol (structurally matching LLMEnricher), so the concrete
        # dependency check is: it never imports pipeline.Enricher.
        assert hasattr(candidate_pipeline, "RelevanceGate")

    def test_returned_candidates_carry_no_event_shaped_data(self, tmp_path):
        written = discover_candidates(
            [_hub()], _fetcher(), sources_dir=REGISTRY_FIXTURES_DIR, candidates_dir=tmp_path
        )

        assert written
        for candidate in written:
            assert isinstance(candidate, OrgCandidate)
            assert not hasattr(candidate, "start")
            assert not hasattr(candidate, "field_provenance")


class TestSyntheticEventNeverPersisted:
    def test_synthetic_event_fields_match_the_candidate(self, tmp_path):
        # Indirect proof: a relevance gate that inspects the Event it is
        # handed confirms title/description/source_id are built exactly
        # as sprint.md's Candidate Pipeline row specifies, without this
        # module ever exposing the Event itself.
        seen_titles: list[str] = []
        seen_descriptions: list[str] = []
        seen_source_ids: list[str] = []

        class _RecordingGate:
            def enrich(self, events):
                seen_titles.extend(e.title for e in events)
                seen_descriptions.extend(e.description for e in events)
                seen_source_ids.extend(e.source_id for e in events)
                return events

        discover_candidates(
            [_hub()],
            _fetcher(),
            _RecordingGate(),
            sources_dir=REGISTRY_FIXTURES_DIR,
            candidates_dir=tmp_path,
        )

        assert set(seen_titles) == {RELEVANT_ORG, NOT_RELEVANT_ORG}
        assert all(source_id == "hub:example_hub" for source_id in seen_source_ids)
        assert all(desc for desc in seen_descriptions)
