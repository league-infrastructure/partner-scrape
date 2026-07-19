"""Tests for partner_scrape.enrich.enricher: LLMEnricher (SUC-011/SUC-012).

Every test drives `LLMEnricher.enrich(...)` through `FixtureLLMClient`
(or a small local LLMClient test double for the fail-open cases) and an
`EnrichmentCache` pointed at a tmp_path -- no test here opens a socket,
requires ANTHROPIC_API_KEY, or touches the real SCRAPE_CACHE_DIR, per
sprint.md's testing policy.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from partner_scrape.enrich.cache import EnrichmentCache
from partner_scrape.enrich.enricher import (
    FALLBACK_SOURCE,
    LLM_SOURCE,
    LLMEnricher,
)
from partner_scrape.enrich.llm_client import EnrichmentResult, FixtureLLMClient, LLMEnrichmentError
from partner_scrape.model import Event
from partner_scrape.normalize.taxonomy import build_taxonomy_text, derive_areas_of_interest


def _event(title: str = "Robotics Night", **overrides: Any) -> Event:
    defaults: dict[str, Any] = dict(
        source_id="fixture_org",
        title=title,
        description="Hands-on robotics coding for kids.",
    )
    defaults.update(overrides)
    return Event(**defaults)


@dataclass
class _RaisingLLMClient:
    """LLMClient test double that always raises -- for the fail-open
    Acceptance Criterion ("a FixtureLLMClient configured to raise").
    `FixtureLLMClient` itself has no built-in "always raise" mode
    (only a KeyError on an unregistered key), so this small local
    double exercises the same failure shape as a malformed real API
    response (LLMEnrichmentError) without touching llm_client.py.
    """

    calls: list[Event] = field(default_factory=list)
    exc: type[Exception] = LLMEnrichmentError

    def enrich_event(self, event: Event) -> EnrichmentResult:
        self.calls.append(event)
        raise self.exc("boom")


@dataclass
class _KeyedLLMClient:
    """Like FixtureLLMClient, but a response entry may be an Exception
    subclass instead of an EnrichmentResult, in which case that
    exception is raised instead of returning a result -- lets one test
    mix relevant/not-relevant/erroring events in a single client.
    """

    responses: dict[str, EnrichmentResult | type[Exception]]
    calls: list[Event] = field(default_factory=list)

    def enrich_event(self, event: Event) -> EnrichmentResult:
        self.calls.append(event)
        outcome = self.responses[event.title]
        if isinstance(outcome, type) and issubclass(outcome, Exception):
            raise outcome("boom")
        return outcome


# ---------------------------------------------------------------------
# AC: missing date recovered, source="llm_enrichment"
# ---------------------------------------------------------------------


class TestRecoversMissingFields:
    def test_missing_date_is_set_with_llm_enrichment_source(self, tmp_path):
        event = _event()
        assert event.start is None
        result = EnrichmentResult(start=datetime(2026, 8, 15, 18, 0, 0), relevant=True)
        llm_client = FixtureLLMClient(responses={"Robotics Night": result})
        enricher = LLMEnricher(llm_client, EnrichmentCache(cache_dir=tmp_path))

        [enriched] = enricher.enrich([event])

        assert enriched.start == datetime(2026, 8, 15, 18, 0, 0)
        assert enriched.field_provenance["start"].source == LLM_SOURCE

    def test_a_field_the_llm_did_not_recover_stays_unset(self, tmp_path):
        event = _event()
        result = EnrichmentResult(start=datetime(2026, 8, 15, 18, 0, 0), location=None, relevant=True)
        llm_client = FixtureLLMClient(responses={"Robotics Night": result})
        enricher = LLMEnricher(llm_client, EnrichmentCache(cache_dir=tmp_path))

        [enriched] = enricher.enrich([event])

        assert enriched.location == ""
        assert "location" not in enriched.field_provenance

    def test_classification_and_relevance_are_always_set(self, tmp_path):
        event = _event()
        result = EnrichmentResult(
            areas_of_interest=["Engineering"],
            age_grade_level=["Grades 6-8"],
            cost_range="Free",
            time_of_day=["Evening"],
            relevant=True,
            relevance_reason="Youth robotics program.",
        )
        llm_client = FixtureLLMClient(responses={"Robotics Night": result})
        enricher = LLMEnricher(llm_client, EnrichmentCache(cache_dir=tmp_path))

        [enriched] = enricher.enrich([event])

        assert enriched.areas_of_interest == ["Engineering"]
        assert enriched.age_grade_level == ["Grades 6-8"]
        assert enriched.cost_range == "Free"
        assert enriched.time_of_day == ["Evening"]
        assert enriched.relevance_reason == "Youth robotics program."
        for f in ("areas_of_interest", "age_grade_level", "cost_range", "time_of_day", "relevant"):
            assert enriched.field_provenance[f].source == LLM_SOURCE


# ---------------------------------------------------------------------
# AC: cache-skip -- second call over identical content makes zero
# additional LLM calls
# ---------------------------------------------------------------------


class TestCacheSkipsUnchangedEvents:
    def test_second_enrich_call_over_same_content_makes_zero_additional_llm_calls(self, tmp_path):
        llm_client = FixtureLLMClient(responses={"Robotics Night": EnrichmentResult(relevant=True)})
        cache = EnrichmentCache(cache_dir=tmp_path)
        enricher = LLMEnricher(llm_client, cache)

        enricher.enrich([_event()])
        enricher.enrich([_event()])  # a fresh Event instance, identical content

        assert len(llm_client.calls) == 1

    def test_cache_hit_still_reapplies_the_cached_result_to_the_event(self, tmp_path):
        result = EnrichmentResult(
            start=datetime(2026, 8, 15, 18, 0, 0), relevant=True, cost_range="Free"
        )
        llm_client = FixtureLLMClient(responses={"Robotics Night": result})
        cache = EnrichmentCache(cache_dir=tmp_path)
        enricher = LLMEnricher(llm_client, cache)

        enricher.enrich([_event()])
        [second] = enricher.enrich([_event()])

        assert second.start == datetime(2026, 8, 15, 18, 0, 0)
        assert second.cost_range == "Free"
        assert second.field_provenance["start"].source == LLM_SOURCE


# ---------------------------------------------------------------------
# AC: changed content triggers a fresh LLM call rather than a stale hit
# ---------------------------------------------------------------------


class TestCacheInvalidatesOnChangedContent:
    def test_changed_description_triggers_a_second_llm_call(self, tmp_path):
        llm_client = FixtureLLMClient(responses={"Robotics Night": EnrichmentResult(relevant=True)})
        cache = EnrichmentCache(cache_dir=tmp_path)
        enricher = LLMEnricher(llm_client, cache)

        enricher.enrich([_event(description="first description")])
        enricher.enrich([_event(description="second, changed description")])

        assert len(llm_client.calls) == 2


# ---------------------------------------------------------------------
# AC: fail-open on LLM failure
# ---------------------------------------------------------------------


class TestFailsOpenOnLlmFailure:
    def test_event_survives_with_taxonomy_fallback_classification_and_relevant_true(
        self, tmp_path, caplog
    ):
        event = _event()
        llm_client = _RaisingLLMClient()
        enricher = LLMEnricher(llm_client, EnrichmentCache(cache_dir=tmp_path))

        with caplog.at_level(logging.WARNING):
            [enriched] = enricher.enrich([event])

        expected_areas = derive_areas_of_interest(
            build_taxonomy_text(event.title, event.description, event.categories, event.tags)
        )
        assert enriched.relevant is True
        assert enriched.areas_of_interest == expected_areas
        assert enriched.field_provenance["relevant"].source == FALLBACK_SOURCE
        assert "LLM enrichment failed" in caplog.text

    def test_no_cache_entry_is_written_when_the_llm_call_fails(self, tmp_path):
        cache = EnrichmentCache(cache_dir=tmp_path)
        enricher = LLMEnricher(_RaisingLLMClient(), cache)

        enricher.enrich([_event()])

        assert cache.lookup(_event()) is None
        assert list((tmp_path / "enrichment_cache").glob("*.json")) == []

    def test_next_run_retries_the_llm_rather_than_reusing_a_failed_attempt(self, tmp_path):
        cache = EnrichmentCache(cache_dir=tmp_path)
        LLMEnricher(_RaisingLLMClient(), cache).enrich([_event()])

        working_client = FixtureLLMClient(responses={"Robotics Night": EnrichmentResult(relevant=True)})
        LLMEnricher(working_client, cache).enrich([_event()])

        assert len(working_client.calls) == 1


# ---------------------------------------------------------------------
# AC: relevance gate excludes relevant=False events from the return value
# ---------------------------------------------------------------------


class TestRelevanceGate:
    def test_not_relevant_event_is_excluded_from_the_returned_list(self, tmp_path):
        event = _event(title="Adult Wine Tasting")
        result = EnrichmentResult(relevant=False, relevance_reason="Adult-only, not for youth.")
        llm_client = FixtureLLMClient(responses={"Adult Wine Tasting": result})
        enricher = LLMEnricher(llm_client, EnrichmentCache(cache_dir=tmp_path))

        survivors = enricher.enrich([event])

        assert survivors == []
        assert event.relevant is False


# ---------------------------------------------------------------------
# AC: mixed batch -- relevant, not-relevant, and erroring events are
# handled independently
# ---------------------------------------------------------------------


class TestMixedBatchIsolation:
    def test_relevant_and_fallback_relevant_events_survive_not_relevant_does_not(self, tmp_path):
        relevant_event = _event(title="Robotics Night")
        not_relevant_event = _event(title="Adult Wine Tasting")
        erroring_event = _event(title="Mystery Program", description="robot coding camp for kids")

        llm_client = _KeyedLLMClient(
            responses={
                "Robotics Night": EnrichmentResult(relevant=True, relevance_reason="stem"),
                "Adult Wine Tasting": EnrichmentResult(relevant=False, relevance_reason="not stem"),
                "Mystery Program": LLMEnrichmentError,
            }
        )
        enricher = LLMEnricher(llm_client, EnrichmentCache(cache_dir=tmp_path))

        survivors = enricher.enrich([relevant_event, not_relevant_event, erroring_event])

        assert [e.title for e in survivors] == ["Robotics Night", "Mystery Program"]
        assert erroring_event.relevant is True
        assert erroring_event.field_provenance["relevant"].source == FALLBACK_SOURCE
        assert relevant_event.field_provenance["relevant"].source == LLM_SOURCE

    def test_one_events_error_does_not_prevent_a_later_events_llm_call(self, tmp_path):
        erroring_event = _event(title="Mystery Program", description="robot coding camp for kids")
        relevant_event = _event(title="Robotics Night")

        llm_client = _KeyedLLMClient(
            responses={
                "Mystery Program": LLMEnrichmentError,
                "Robotics Night": EnrichmentResult(relevant=True),
            }
        )
        enricher = LLMEnricher(llm_client, EnrichmentCache(cache_dir=tmp_path))

        survivors = enricher.enrich([erroring_event, relevant_event])

        assert [e.title for e in survivors] == ["Mystery Program", "Robotics Night"]
        assert len(llm_client.calls) == 2
