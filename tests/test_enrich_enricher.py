"""Tests for partner_scrape.enrich.enricher: LLMEnricher (SUC-011/SUC-012).

Every test drives `LLMEnricher.enrich(...)` through `FixtureLLMClient`
(or a small local LLMClient test double for the fail-open cases) and an
`EnrichmentCache` pointed at a tmp_path -- no test here opens a socket,
requires ANTHROPIC_API_KEY, or touches the real SCRAPE_CACHE_DIR, per
sprint.md's testing policy.
"""

from __future__ import annotations

import logging
import threading
import time
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


@dataclass
class _LockedFixtureLLMClient(FixtureLLMClient):
    """`FixtureLLMClient` with its `calls` append guarded by a lock.

    `list.append` is already atomic under CPython's GIL, but the
    concurrency tests below assert precisely on `calls` (count,
    membership) from a real `ThreadPoolExecutor`, so guard it
    explicitly rather than lean on a CPython implementation detail --
    the bounded-concurrency ticket's own testing note ("guard the
    calls list with a lock if you assert on it").
    """

    _calls_lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def enrich_event(self, event: Event) -> EnrichmentResult:
        with self._calls_lock:
            self.calls.append(event)
        return self.responses[self.key_fn(event)]


@dataclass
class _LockedKeyedLLMClient(_KeyedLLMClient):
    """`_KeyedLLMClient` with a lock-guarded `calls` append and an
    optional per-title `delays` sleep, so a test can force a specific
    completion order under a real thread pool (e.g. reverse the
    completion order relative to submission order) and still assert
    safely on `calls`.
    """

    delays: dict[str, float] = field(default_factory=dict)
    _calls_lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def enrich_event(self, event: Event) -> EnrichmentResult:
        time.sleep(self.delays.get(event.title, 0.0))
        with self._calls_lock:
            self.calls.append(event)
        outcome = self.responses[event.title]
        if isinstance(outcome, type) and issubclass(outcome, Exception):
            raise outcome("boom")
        return outcome


def _relevant_source(event: Event) -> str | None:
    """The provenance `source` recorded for ``event``'s `relevant`
    field, or ``None`` if it was never set (e.g. an internship bypass).
    """
    provenance = event.field_provenance.get("relevant")
    return provenance.source if provenance is not None else None


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

    def test_second_call_hits_cache_even_when_the_result_recovered_a_field(self, tmp_path):
        # Regression: the enricher must store the cache entry keyed on the
        # Event's PRE-enrichment content. _apply_result mutates the very
        # fields content_hash covers (here it recovers `start`), so storing
        # after apply would hash the post-enrichment Event -- and next run,
        # which hashes the pre-enrichment Event fresh from the adapter,
        # would miss and re-bill the LLM. This is the exact bug that
        # re-billed ~5.5k events on the second full run.
        result = EnrichmentResult(start=datetime(2026, 8, 15, 18, 0, 0), relevant=True)
        llm_client = FixtureLLMClient(responses={"Robotics Night": result})
        enricher = LLMEnricher(llm_client, EnrichmentCache(cache_dir=tmp_path))

        enricher.enrich([_event()])  # start=None -> LLM recovers 2026-08-15
        enricher.enrich([_event()])  # fresh event, start=None again: must hit cache

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
# AC (OOP, 2026-07-20): `event.trusted` Events (e.g. adapters/leaguesync.py's
# first-party League classes) are never dropped by the relevance gate,
# even when the LLM verdicts them `relevant=False` -- but, unlike the
# internship bypass below, they still go through the full enrichment
# pass: cache lookup, LLM call/fallback, and classification fields all
# still apply normally. Only the final gate is bypassed.
# ---------------------------------------------------------------------


class TestTrustedEventsBypassTheRelevanceGate:
    def test_trusted_event_survives_a_not_relevant_verdict(self, tmp_path):
        event = _event(title="Summer Camps@SFA", trusted=True)
        result = EnrichmentResult(
            relevant=False, relevance_reason="Title too thin to classify confidently."
        )
        llm_client = FixtureLLMClient(responses={"Summer Camps@SFA": result})
        enricher = LLMEnricher(llm_client, EnrichmentCache(cache_dir=tmp_path))

        survivors = enricher.enrich([event])

        assert survivors == [event]
        # Still actually enriched/classified -- the verdict is computed
        # and recorded, just never allowed to drop the Event.
        assert event.relevant is False
        assert event.field_provenance["relevant"].source == LLM_SOURCE

    def test_trusted_event_is_still_enriched_not_skipped_like_an_internship(self, tmp_path):
        event = _event(title="Python@GA", trusted=True)
        result = EnrichmentResult(
            relevant=False,
            relevance_reason="not sure",
            areas_of_interest=["Coding/Computer Science/Cyber Security"],
            age_grade_level=["Grades 6-8"],
        )
        llm_client = FixtureLLMClient(responses={"Python@GA": result})
        enricher = LLMEnricher(llm_client, EnrichmentCache(cache_dir=tmp_path))

        survivors = enricher.enrich([event])

        assert survivors == [event]
        assert llm_client.calls == [event]
        assert event.areas_of_interest == ["Coding/Computer Science/Cyber Security"]
        assert event.age_grade_level == ["Grades 6-8"]

    def test_non_trusted_not_relevant_event_is_still_dropped_alongside_a_trusted_one(
        self, tmp_path
    ):
        trusted_event = _event(title="Summer Camps@SFA", trusted=True)
        not_relevant_event = _event(title="Adult Wine Tasting", trusted=False)

        llm_client = _KeyedLLMClient(
            responses={
                "Summer Camps@SFA": EnrichmentResult(relevant=False, relevance_reason="thin title"),
                "Adult Wine Tasting": EnrichmentResult(relevant=False, relevance_reason="not stem"),
            }
        )
        enricher = LLMEnricher(llm_client, EnrichmentCache(cache_dir=tmp_path))

        survivors = enricher.enrich([trusted_event, not_relevant_event])

        assert survivors == [trusted_event]

    def test_trusted_relevant_event_survives_as_normal(self, tmp_path):
        event = _event(title="Java Classes", trusted=True)
        result = EnrichmentResult(relevant=True, relevance_reason="stem")
        llm_client = FixtureLLMClient(responses={"Java Classes": result})
        enricher = LLMEnricher(llm_client, EnrichmentCache(cache_dir=tmp_path))

        survivors = enricher.enrich([event])

        assert survivors == [event]
        assert event.relevant is True


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


# ---------------------------------------------------------------------
# AC (sprint 006 ticket 005, SUC-005): kind="internship" Events bypass
# the relevance gate entirely -- no cache lookup, no LLM call, no field
# mutation, never dropped.
# ---------------------------------------------------------------------


class _SpyCache(EnrichmentCache):
    """`EnrichmentCache` subclass that records every `lookup()`/`store()`
    call, in order, on top of its real (tmp_path-backed) behavior -- lets
    a test assert an internship Event never touches the cache at all,
    not just that it happens to miss.
    """

    def __init__(self, cache_dir):
        super().__init__(cache_dir=cache_dir)
        self.lookup_calls: list[Event] = []
        self.store_calls: list[Event] = []

    def lookup(self, event: Event) -> EnrichmentResult | None:
        self.lookup_calls.append(event)
        return super().lookup(event)

    def store(self, event: Event, result: EnrichmentResult) -> None:
        self.store_calls.append(event)
        super().store(event, result)


class TestInternshipEventsBypassTheRelevanceGate:
    def test_internship_event_passes_through_unchanged_with_zero_llm_calls(self, tmp_path):
        event = _event(title="Software Engineering Intern", kind="internship")
        # Empty responses: any unexpected enrich_event() call raises
        # KeyError and fails the test loudly (ticket 005's Testing note).
        llm_client = FixtureLLMClient(responses={})
        cache = _SpyCache(cache_dir=tmp_path)
        enricher = LLMEnricher(llm_client, cache)

        [survivor] = enricher.enrich([event])

        assert survivor is event
        assert survivor.relevant is None
        assert survivor.field_provenance == {}
        assert llm_client.calls == []
        assert cache.lookup_calls == []
        assert cache.store_calls == []

    def test_internship_event_is_never_dropped_even_if_a_relevance_verdict_would_be_false(
        self, tmp_path
    ):
        # A response keyed to this title *would* gate a kind="event"
        # Event out (see TestRelevanceGate above) -- registering it here
        # and then asserting zero calls proves the bypass never even
        # consults it, so it can never drop this Event.
        event = _event(title="Adult Wine Tasting", kind="internship")
        result = EnrichmentResult(relevant=False, relevance_reason="Adult-only, not for youth.")
        llm_client = FixtureLLMClient(responses={"Adult Wine Tasting": result})
        enricher = LLMEnricher(llm_client, EnrichmentCache(cache_dir=tmp_path))

        survivors = enricher.enrich([event])

        assert survivors == [event]
        assert event.relevant is None
        assert llm_client.calls == []

    def test_mixed_batch_gates_only_event_kind_and_preserves_relative_order(self, tmp_path):
        internship = _event(title="Data Science Intern", kind="internship")
        event = _event(title="Robotics Night")
        result = EnrichmentResult(relevant=True, relevance_reason="stem")
        llm_client = FixtureLLMClient(responses={"Robotics Night": result})
        cache = _SpyCache(cache_dir=tmp_path)
        enricher = LLMEnricher(llm_client, cache)

        survivors = enricher.enrich([internship, event])

        assert [e.title for e in survivors] == ["Data Science Intern", "Robotics Night"]
        assert survivors[0].field_provenance == {}
        assert survivors[1].field_provenance["relevant"].source == LLM_SOURCE
        assert [e.title for e in llm_client.calls] == ["Robotics Night"]
        assert [e.title for e in cache.lookup_calls] == ["Robotics Night"]
        assert [e.title for e in cache.store_calls] == ["Robotics Night"]

    def test_existing_event_kind_relevance_gating_is_unchanged(self, tmp_path):
        # Guards against a regression where the internship branch
        # accidentally short-circuits kind="event"/"program" handling.
        event = _event(title="Adult Wine Tasting")
        result = EnrichmentResult(relevant=False, relevance_reason="Adult-only, not for youth.")
        llm_client = FixtureLLMClient(responses={"Adult Wine Tasting": result})
        enricher = LLMEnricher(llm_client, EnrichmentCache(cache_dir=tmp_path))

        survivors = enricher.enrich([event])

        assert survivors == []
        assert event.relevant is False


# ---------------------------------------------------------------------
# AC (bounded concurrency, ThreadPoolExecutor): the LLM-call pass runs
# across a thread pool but every previously-tested behavior above is
# unaffected. These tests use `max_workers` > 1 (a real thread pool,
# not a trivially-sequential one) and, where timing matters, force
# completion order to *differ* from submission order so a passing test
# proves the Enricher's apply pass -- not incidental completion timing
# -- is what determines the result.
# ---------------------------------------------------------------------


class TestConcurrentOrderPreservation:
    def test_output_order_matches_input_order_even_when_llm_calls_complete_out_of_order(
        self, tmp_path
    ):
        n = 20
        # Shuffle which title lands at which index so nothing here
        # coincides with alphabetical/numeric title order.
        titles = [f"Event {i:02d}" for i in range(n)]
        shuffled_titles = titles[1::2] + titles[0::2]  # deterministic, non-trivial shuffle
        events = [_event(title=shuffled_titles[i]) for i in range(n)]

        # Delay is largest for the *earliest* submitted event and
        # smallest for the last, so completion order is roughly the
        # reverse of submission order under real concurrency.
        delays = {shuffled_titles[i]: (n - i) * 0.005 for i in range(n)}
        responses = {
            title: EnrichmentResult(relevant=True, relevance_reason="stem") for title in shuffled_titles
        }
        llm_client = _LockedKeyedLLMClient(responses=responses, delays=delays)
        enricher = LLMEnricher(llm_client, EnrichmentCache(cache_dir=tmp_path), max_workers=n)

        survivors = enricher.enrich(events)

        assert [e.title for e in survivors] == shuffled_titles
        assert len(llm_client.calls) == n


class TestConcurrentCacheSkipAndExactlyOneCallPerMiss:
    def test_cached_events_are_never_sent_to_the_llm_and_each_miss_is_called_exactly_once(
        self, tmp_path
    ):
        n = 16
        titles = [f"Event {i:02d}" for i in range(n)]
        cached_titles = titles[: n // 2]
        miss_titles = titles[n // 2 :]

        # Pass 1: populate the cache for the first half only.
        cache = EnrichmentCache(cache_dir=tmp_path)
        warm_up_client = _LockedKeyedLLMClient(
            responses={t: EnrichmentResult(relevant=True) for t in cached_titles}
        )
        LLMEnricher(warm_up_client, cache, max_workers=4).enrich(
            [_event(title=t) for t in cached_titles]
        )

        # Pass 2: a fresh batch mixing the now-cached titles (same
        # content -> cache hit) with brand-new titles (misses), run
        # through a *new* client that only has responses registered
        # for the miss titles -- if a cache hit were mistakenly
        # re-sent to the LLM it would raise KeyError inside a worker
        # thread, which the Enricher's fail-open path would silently
        # convert into a fallback result, so this test asserts
        # directly on `calls` rather than relying on that KeyError.
        second_client = _LockedKeyedLLMClient(
            responses={t: EnrichmentResult(relevant=True) for t in miss_titles}
        )
        events = [_event(title=t) for t in titles]  # same content as pass 1 for cached_titles
        enricher = LLMEnricher(second_client, cache, max_workers=8)

        survivors = enricher.enrich(events)

        called_titles = [e.title for e in second_client.calls]
        assert sorted(called_titles) == sorted(miss_titles)
        assert len(called_titles) == len(miss_titles)  # exactly one call per miss, no duplicates
        assert [e.title for e in survivors] == titles


class TestConcurrentPerEventExceptionIsolation:
    def test_one_failing_event_among_many_falls_back_without_affecting_the_others(self, tmp_path):
        n = 10
        titles = [f"Event {i:02d}" for i in range(n)]
        failing_title = titles[n // 2]
        responses: dict[str, Any] = {t: EnrichmentResult(relevant=True) for t in titles}
        responses[failing_title] = LLMEnrichmentError

        events = [_event(title=t) for t in titles]
        llm_client = _LockedKeyedLLMClient(responses=responses)
        enricher = LLMEnricher(llm_client, EnrichmentCache(cache_dir=tmp_path), max_workers=8)

        survivors = enricher.enrich(events)

        # Nothing is dropped (the fallback is always relevant=True too).
        assert [e.title for e in survivors] == titles
        for event in events:
            if event.title == failing_title:
                assert _relevant_source(event) == FALLBACK_SOURCE
            else:
                assert _relevant_source(event) == LLM_SOURCE
        assert len(llm_client.calls) == n


class TestConcurrentRelevanceGateAndInternshipBypass:
    def test_mixed_batch_gates_correctly_and_internship_never_touches_cache_or_llm(self, tmp_path):
        internship = _event(title="Data Science Intern", kind="internship")
        relevant_event = _event(title="Robotics Night")
        not_relevant_event = _event(title="Adult Wine Tasting")
        erroring_event = _event(title="Mystery Program", description="robot coding camp for kids")

        llm_client = _LockedKeyedLLMClient(
            responses={
                "Robotics Night": EnrichmentResult(relevant=True, relevance_reason="stem"),
                "Adult Wine Tasting": EnrichmentResult(relevant=False, relevance_reason="not stem"),
                "Mystery Program": LLMEnrichmentError,
            }
        )
        cache = _SpyCache(cache_dir=tmp_path)
        enricher = LLMEnricher(llm_client, cache, max_workers=8)

        survivors = enricher.enrich(
            [internship, relevant_event, not_relevant_event, erroring_event]
        )

        assert [e.title for e in survivors] == [
            "Data Science Intern",
            "Robotics Night",
            "Mystery Program",
        ]
        assert internship.field_provenance == {}
        assert not_relevant_event.relevant is False
        assert _relevant_source(erroring_event) == FALLBACK_SOURCE
        assert _relevant_source(relevant_event) == LLM_SOURCE
        # Internship never reaches the cache or the LLM client.
        assert all(e.title != "Data Science Intern" for e in cache.lookup_calls)
        assert all(e.title != "Data Science Intern" for e in cache.store_calls)
        assert all(e.title != "Data Science Intern" for e in llm_client.calls)


class TestMaxWorkersConfigurable:
    def test_max_workers_one_produces_identical_results_to_a_real_thread_pool(self, tmp_path):
        def build_scenario() -> tuple[list[Event], dict[str, Any]]:
            events = [
                _event(title="Robotics Night"),
                _event(title="Adult Wine Tasting"),
                _event(title="Mystery Program", description="robot coding camp for kids"),
                _event(title="Data Science Intern", kind="internship"),
            ]
            responses: dict[str, Any] = {
                "Robotics Night": EnrichmentResult(relevant=True, relevance_reason="stem"),
                "Adult Wine Tasting": EnrichmentResult(relevant=False, relevance_reason="not stem"),
                "Mystery Program": LLMEnrichmentError,
            }
            return events, responses

        def snapshot(events: list[Event]) -> list[tuple[str, bool | None, str | None]]:
            return [(e.title, e.relevant, _relevant_source(e)) for e in events]

        outcomes = {}
        for workers in (1, 8):
            events, responses = build_scenario()
            llm_client = _LockedKeyedLLMClient(responses=responses)
            cache = EnrichmentCache(cache_dir=tmp_path / f"cache_{workers}")
            enricher = LLMEnricher(llm_client, cache, max_workers=workers)

            survivors = enricher.enrich(events)

            outcomes[workers] = ([e.title for e in survivors], snapshot(events))

        assert outcomes[1] == outcomes[8]


class TestConcurrentUsesFixtureLLMClient:
    """The concurrency tests above use a locked local double, but
    production code and most of this module's other tests use
    `FixtureLLMClient` directly -- confirm the standard double also
    behaves correctly (and its `calls` list stays intact) when driven
    through a real thread pool.
    """

    def test_fixture_llm_client_under_a_real_thread_pool(self, tmp_path):
        n = 12
        titles = [f"Event {i:02d}" for i in range(n)]
        responses = {t: EnrichmentResult(relevant=True, relevance_reason="stem") for t in titles}
        events = [_event(title=t) for t in titles]
        llm_client = _LockedFixtureLLMClient(responses=responses)
        enricher = LLMEnricher(llm_client, EnrichmentCache(cache_dir=tmp_path), max_workers=6)

        survivors = enricher.enrich(events)

        assert [e.title for e in survivors] == titles
        assert len(llm_client.calls) == n
        assert sorted(e.title for e in llm_client.calls) == titles
