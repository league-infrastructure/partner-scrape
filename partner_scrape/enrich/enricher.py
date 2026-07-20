"""`LLMEnricher`: `pipeline.Enricher`'s first real implementation.

See sprint.md's Architecture > LLM Enricher, SUC-011 (recover fields and
classify an Event via LLM enrichment) and SUC-012 (gate irrelevant
events out of the export via the relevance verdict). Fulfills
`pipeline.Enricher`'s deferred seam (`pipeline.py`'s `Enricher` Protocol)
with zero changes to `pipeline.py` -- exactly the seam sprint 001 paid
for.

Per-Event flow (SUC-011's Main Flow):
0. `kind="internship"` Events (sprint 006 ticket 005, SUC-005) bypass
   this entire flow: no cache lookup, no `LLMClient` call, no field
   mutation -- the Event is appended to the survivors list unchanged.
   An internship arrives already classified/gated deterministically by
   `adapters/ats_filters.py`, and this module's LLM prompt is written
   specifically around a "STEM learning opportunity for K-12 youth"
   framing that could misjudge legitimate job-posting text as
   adult-only and silently drop it -- see sprint.md's Design Rationale.
1. Compute the Event's `identity_key()` and check the `EnrichmentCache`.
2. Cache hit (same content hash) -> reapply the cached `EnrichmentResult`
   to the Event via `Event.set(...)`, no LLM call (cost control).
3. Cache miss or changed content -> call the injected `LLMClient`, apply
   the result, write a fresh cache entry.
4. LLM call raises (malformed response, network/API failure -- any
   exception the call raises, not only `LLMEnrichmentError`; see
   sprint.md's Design Rationale "on any LLM/API failure the Enricher
   fails open") -> log a warning, fall back to `normalize.taxonomy`'s
   keyword derivation, mark `relevant=True`, and do **not** write a
   cache entry (so the next run retries the LLM rather than caching a
   degraded result).
5. Filter the returned list: exclude any Event with `relevant=False`
   (SUC-012's gate). One Event's gating/error never affects any other
   Event in the same batch -- each is handled independently, matching
   `pipeline.py`'s own per-source isolation convention.

Bounded-concurrency fast-follow (sprint.md's Open Question 6: a full
corpus refresh made ~100 minutes of pure sequential LLM latency): the
LLM calls themselves -- the only slow, independent-per-Event step --
run in a `ThreadPoolExecutor`, everything else stays sequential on the
main thread:

1. SEQUENTIAL pass over ``events`` in order: internship bypass (kind 0
   above, no LLM/cache touch at all), cache hits (applied immediately,
   no LLM call), or a "miss" collected for the concurrent pass. This
   pass does all cache reads -- reads are safe to keep on the main
   thread and this keeps `EnrichmentCache.lookup` single-threaded too.
2. CONCURRENT pass: every miss's `llm_client.enrich_event()` call is
   submitted to a `ThreadPoolExecutor(max_workers=self.max_workers)`.
   Each call only reads its own Event and returns a fresh
   `EnrichmentResult` (or raises) -- no shared mutable state crosses
   threads except each future's own return value/exception.
3. SEQUENTIAL apply pass, back on the main thread, iterating the
   misses in their *original* order (not completion order): apply the
   result (or the fail-open taxonomy fallback, same as before) via
   `Event.set(...)`, and call `EnrichmentCache.store()` -- cache writes
   stay strictly single-threaded to avoid file races, matching
   `EnrichmentCache`'s one-JSON-file-per-Event on-disk layout.
4. The relevance gate is then applied once, over the full input
   ``events`` list in its original order -- so the returned list's
   order and membership are identical to the fully-sequential
   implementation for any given input; concurrency only changes how
   fast the LLM calls happen, never the result. `max_workers=1` behaves
   identically to the old strictly-sequential code path.
"""

from __future__ import annotations

import concurrent.futures
import logging

from partner_scrape.enrich.cache import EnrichmentCache
from partner_scrape.enrich.llm_client import EnrichmentResult, LLMClient
from partner_scrape.model import Event
from partner_scrape.normalize.taxonomy import (
    build_taxonomy_text,
    derive_age_grade_level,
    derive_areas_of_interest,
    derive_time_of_day,
    map_cost,
)

logger = logging.getLogger(__name__)

#: Default `max_workers` for the concurrent LLM-call pass (see
#: `LLMEnricher.__init__`). Bounds how many `llm_client.enrich_event()`
#: calls run in flight at once -- high enough to cut a full-corpus
#: refresh's wall-clock time down substantially, low enough not to
#: hammer the Anthropic API with an unbounded burst of concurrent
#: requests from one process.
DEFAULT_MAX_WORKERS = 8

#: Provenance `source` recorded for fields set from a real or
#: cache-reapplied LLM enrichment result -- matches SUC-011's
#: acceptance criterion ("the returned Event has that date set with
#: source='llm_enrichment'").
LLM_SOURCE = "llm_enrichment"

#: Provenance `source` recorded for the fail-open keyword-classification
#: fallback (sprint.md Design Rationale: "on any LLM/API failure ...
#: fall back to taxonomy.py's keyword classification").
FALLBACK_SOURCE = "taxonomy_fallback"

#: Confidence recorded for LLM-derived fields. Lower than a
#: deterministic structured-API extraction's 1.0 (e.g.
#: `adapters/tec.py`'s `CONFIDENCE`) or the extraction ladder's top rung
#: (`extract/ladder.py`'s `CONFIDENCE_JSON_LD = 1.0`): an LLM call is an
#: inference over text, not a direct structured read.
LLM_CONFIDENCE = 0.7

#: Confidence recorded for the fail-open keyword-classification
#: fallback. Lower than `LLM_CONFIDENCE`, near the low end of
#: `extract/ladder.py`'s confidence tiers (its weakest rung,
#: `CONFIDENCE_BODY_REGEX`, is 0.2): a keyword match is a coarser signal
#: than either a direct extraction or a real LLM classification.
FALLBACK_CONFIDENCE = 0.3

#: `Event` fields an `EnrichmentResult` may *recover*. Applied only when
#: the corresponding `EnrichmentResult` attribute is not `None` -- `None`
#: means "the LLM did not recover this field" (see `EnrichmentResult`'s
#: docstring), distinct from a genuinely-recovered empty value.
_RECOVERABLE_FIELDS = ("start", "end", "all_day", "location", "cost", "registration_url")

#: `Event` fields an `EnrichmentResult` always produces (classification +
#: the relevance verdict) -- applied unconditionally.
_CLASSIFICATION_FIELDS = ("areas_of_interest", "age_grade_level", "cost_range", "time_of_day")


def _apply_result(event: Event, result: EnrichmentResult, *, source: str, confidence: float) -> None:
    """Write every field of ``result`` onto ``event`` via `Event.set(...)`."""
    for field_name in _RECOVERABLE_FIELDS:
        value = getattr(result, field_name)
        if value is not None:
            event.set(field_name, value, source=source, confidence=confidence)
    for field_name in _CLASSIFICATION_FIELDS:
        event.set(field_name, getattr(result, field_name), source=source, confidence=confidence)
    event.set("relevant", result.relevant, source=source, confidence=confidence)
    event.set("relevance_reason", result.relevance_reason, source=source, confidence=confidence)


def _fallback_result(event: Event) -> EnrichmentResult:
    """Build a fail-open `EnrichmentResult` from `normalize.taxonomy`'s
    pure keyword-derivation functions.

    No recovered fields (a keyword pass over existing text cannot
    recover dates/location/cost the way an LLM call can -- only
    classification is attempted), classification derived from the
    Event's own current text/fields, and `relevant=True` unconditionally
    (fail-open, sprint.md's Design Rationale: a systemic LLM outage must
    not silently empty the site).
    """
    text = build_taxonomy_text(event.title, event.description, event.categories, event.tags)
    return EnrichmentResult(
        areas_of_interest=derive_areas_of_interest(text),
        age_grade_level=derive_age_grade_level(text),
        cost_range=map_cost(event.cost),
        time_of_day=derive_time_of_day(event.start, event.all_day),
        relevant=True,
        relevance_reason="",
    )


class LLMEnricher:
    """`pipeline.Enricher`'s first real implementation: a cache-aware LLM
    classification pass over the collected Event stream that also gates
    not-relevant Events out of its returned list (SUC-011, SUC-012).

    `llm_client` and `cache` are both injected constructor arguments,
    matching sprint 001's `Fetcher` dependency-injection convention:
    production code passes `LLMEnricher(AnthropicLLMClient(),
    EnrichmentCache())`; tests pass `FixtureLLMClient`/an
    `EnrichmentCache(cache_dir=tmp_path)`, never touching a socket or the
    real `SCRAPE_CACHE_DIR`.

    `max_workers` bounds the `ThreadPoolExecutor` used for the
    concurrent LLM-call pass (see the module docstring's numbered
    steps) -- defaults to `DEFAULT_MAX_WORKERS`. `max_workers=1` is a
    valid, fully-supported setting: it behaves identically to the old
    strictly-sequential implementation, just still going through the
    executor machinery.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        cache: EnrichmentCache,
        max_workers: int = DEFAULT_MAX_WORKERS,
    ) -> None:
        self.llm_client = llm_client
        self.cache = cache
        self.max_workers = max_workers

    def enrich(self, events: list[Event]) -> list[Event]:
        """Enrich and relevance-gate ``events`` (fulfills `pipeline.Enricher`).

        Returns every Event except those verdicted `relevant=False` --
        see this module's docstring for the full per-Event flow and its
        SEQUENTIAL / CONCURRENT / SEQUENTIAL structure.
        """
        # --- Pass 1 (sequential): internship bypass, cache hits applied
        # in place, everything else collected as a "miss" needing an LLM
        # call. `misses` preserves `events`' relative order.
        misses: list[Event] = []
        for event in events:
            if event.kind == "internship":
                # Relevance Gate bypass (sprint 006 ticket 005, SUC-005):
                # already classified/gated deterministically by
                # adapters/ats_filters.py at acquisition time. Never
                # re-judged, never dropped here, and -- skip-LLM is the
                # preferred, cheaper option over "call but never
                # gate-drop" -- never even sent to the LLM: no cache
                # lookup, no `llm_client.enrich_event()` call, no
                # `_apply_result()` call, no field or field_provenance
                # mutation. Every other `kind` keeps the exact behavior
                # below, unchanged.
                continue

            cached_result = self.cache.lookup(event)
            if cached_result is not None:
                _apply_result(event, cached_result, source=LLM_SOURCE, confidence=LLM_CONFIDENCE)
            else:
                misses.append(event)

        # --- Pass 2 (concurrent): one `llm_client.enrich_event()` call
        # per miss, run across a bounded thread pool. Each future's
        # result/exception is recorded by index -- no other shared
        # mutable state crosses threads here.
        results: list[EnrichmentResult | None] = [None] * len(misses)
        errors: list[BaseException | None] = [None] * len(misses)
        if misses:
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_index = {
                    executor.submit(self.llm_client.enrich_event, event): index
                    for index, event in enumerate(misses)
                }
                for future in concurrent.futures.as_completed(future_to_index):
                    index = future_to_index[future]
                    try:
                        results[index] = future.result()
                    except Exception as exc:
                        errors[index] = exc

        # --- Pass 3 (sequential apply, back on the main thread): walk
        # `misses` in their *original* order (not completion order) so
        # behavior never depends on which LLM call happened to finish
        # first. `cache.store()` only ever runs here, single-threaded.
        for index, event in enumerate(misses):
            error = errors[index]
            if error is not None:
                # Fail open (sprint.md Design Rationale): any LLM/API
                # failure -- malformed response, network error, or
                # anything else the call raises -- degrades to the
                # keyword fallback rather than dropping the Event or
                # failing the run. No cache entry is written, so the
                # next run retries the LLM instead of caching a
                # degraded result.
                logger.warning(
                    "LLM enrichment failed for event %r (source_id=%r); falling back to "
                    "keyword classification and marking relevant=True",
                    event.title,
                    event.source_id,
                    exc_info=error,
                )
                _apply_result(
                    event,
                    _fallback_result(event),
                    source=FALLBACK_SOURCE,
                    confidence=FALLBACK_CONFIDENCE,
                )
            else:
                result = results[index]
                assert result is not None  # no error -> future.result() succeeded
                _apply_result(event, result, source=LLM_SOURCE, confidence=LLM_CONFIDENCE)
                self.cache.store(event, result)

        # Relevance Gate (SUC-012), applied once over the full input in
        # its original order -- identical membership/order to the fully
        # sequential implementation regardless of `max_workers`.
        return [event for event in events if event.relevant is not False]
