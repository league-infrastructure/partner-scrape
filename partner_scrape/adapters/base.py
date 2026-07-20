"""The pluggable Adapter contract and dispatch registry.

See sprint.md's Architecture > Adapter Framework: every source is
turned into canonical Events via a per-``adapter_type`` strategy that
implements ``discover -> fetch -> extract``, chained by the generic
:func:`run` below. ``discover()`` is deliberately part of the contract
even though every structured-API adapter this sprint (``tec_rest``, and
``wp_rest``/``ical`` in ticket 005) resolves it trivially against the
source's own endpoint -- this is the seam sprint 2's sitemap-diff and
generic-HTML adapters implement with real "find URLs" logic, without
any change to this module (sprint.md's Deferred Seams).

Registering a new adapter type is a one-line addition to :data:`ADAPTERS`
(done in ``adapters/__init__.py``, e.g. ``ADAPTERS["tec_rest"] =
TecRestAdapter``) -- never a change to :func:`run` or :func:`get_adapter`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol

from partner_scrape.fetch import Fetcher
from partner_scrape.model import Event
from partner_scrape.registry.schema import DEFAULT_MAX_URLS_PER_SOURCE, SourceConfig

logger = logging.getLogger(__name__)


@dataclass
class EventRef:
    """A reference to one fetchable unit of source content.

    For this sprint's structured-API adapters, one ``EventRef`` is one
    page of a paginated API response -- there's no separate "find URLs"
    step, so ``discover()`` just enumerates the pages it already knows
    (or, for TEC, probes for) rather than resolving arbitrary URLs.
    """

    url: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class RawResponse:
    """One fetched, not-yet-interpreted unit of raw source content.

    Carries the ``ref`` it came from (so ``extract()`` can log which
    page a malformed body belonged to) alongside the raw HTTP status and
    body -- interpreting ``body`` (JSON decode, field mapping) is each
    adapter's own ``extract()`` job, not this dataclass's.
    """

    ref: EventRef
    status: int
    body: str


class Adapter(Protocol):
    """Injectable per-``adapter_type`` strategy: discover -> fetch -> extract.

    Every method takes the ``Fetcher``/``SourceConfig`` it needs as an
    explicit argument rather than storing them on the instance -- adapter
    instances are constructed fresh per :func:`run` call from the
    registry, so there is no adapter-instance state to inject into.
    """

    def discover(self, source: SourceConfig, fetcher: Fetcher) -> Iterable[EventRef]:
        """Resolve ``source`` into the set of fetchable ``EventRef``s.

        May itself call ``fetcher`` (e.g. TEC's cheap ``per_page=1``
        probe to learn page count) -- "discovery" for a structured API
        is an API call, not a separate crawl step.
        """
        ...

    def fetch(self, ref: EventRef, fetcher: Fetcher) -> RawResponse:
        """Retrieve one ``EventRef``'s raw content via the injected ``fetcher``."""
        ...

    def extract(self, raw: RawResponse, source: SourceConfig) -> Iterable[Event]:
        """Map one raw response into zero or more canonical Events.

        Implementations must isolate per-record failures: one malformed
        record in an otherwise good response is logged and skipped, not
        raised -- see sprint.md's Adapter Framework and this ticket's
        Description ("Per-record error isolation").
        """
        ...


class UnknownAdapterType(Exception):
    """Raised when a ``SourceConfig.adapter_type`` has no registered Adapter."""


#: Dispatch table from ``SourceConfig.adapter_type`` to the matching
#: ``Adapter`` implementation. Populated by ``adapters/__init__.py``
#: (kept out of this module to avoid a circular import between this base
#: module and each concrete adapter, which imports from it).
ADAPTERS: dict[str, type[Adapter]] = {}


def get_adapter(adapter_type: str) -> Adapter:
    """Instantiate the ``Adapter`` registered for ``adapter_type``.

    Raises:
        UnknownAdapterType: no adapter is registered for this type -- a
            clear, actionable error instead of a bare ``KeyError`` deep
            in dispatch code.
    """
    adapter_cls = ADAPTERS.get(adapter_type)
    if adapter_cls is None:
        known = ", ".join(sorted(ADAPTERS)) or "(none registered)"
        raise UnknownAdapterType(
            f"No adapter registered for adapter_type={adapter_type!r}. "
            f"Known types: {known}"
        )
    return adapter_cls()


def run(source: SourceConfig, fetcher: Fetcher) -> list[Event]:
    """Dispatch ``source`` to its adapter and chain discover -> fetch -> extract.

    This is the "top-level run" sprint.md's Adapter Framework describes:
    generic chaining logic shared by every adapter type. Registering a
    new ``adapter_type`` never requires touching this function -- only
    :data:`ADAPTERS`.

    Per-source URL cap: ``discover()``'s output is truncated to at most
    ``source.acquisition_policy.get("max_urls", DEFAULT_MAX_URLS_PER_SOURCE)``
    refs (registry/schema.py's ``max_urls`` default, ~300) before any of
    them are fetched. This is a generic, adapter-agnostic backstop
    against one pathological source (e.g. a sitemap-derived source whose
    "event" sitemap is actually hundreds of unrelated blog posts)
    dominating a run's wall-clock time -- every ``discover()``
    implementation in this package already returns a plain, eagerly-
    computed ``list[EventRef]`` (never a generator with per-item side
    effects), so materializing it here to measure/truncate its length
    changes nothing about how any adapter's own discovery logic runs.
    Truncation is never silent: a source that exceeds its cap logs
    exactly how many refs it discovered and how many were dropped.

    Raises:
        UnknownAdapterType: ``source.adapter_type`` has no registered
            adapter.
    """
    adapter = get_adapter(source.adapter_type)
    refs = list(adapter.discover(source, fetcher))

    max_urls = source.acquisition_policy.get("max_urls", DEFAULT_MAX_URLS_PER_SOURCE)
    if len(refs) > max_urls:
        dropped = len(refs) - max_urls
        logger.warning(
            "Source %r (adapter_type=%r) discovered %d URL(s), exceeding its "
            "max_urls cap of %d -- fetching only the first %d and dropping %d",
            source.source_id,
            source.adapter_type,
            len(refs),
            max_urls,
            max_urls,
            dropped,
        )
        refs = refs[:max_urls]

    events: list[Event] = []
    for ref in refs:
        raw = adapter.fetch(ref, fetcher)
        events.extend(adapter.extract(raw, source))
    return events
