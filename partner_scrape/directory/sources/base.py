"""The pluggable ``PlaceSource`` contract -- parallel to, and
structurally disjoint from, ``teams.sources.base.TeamSource`` and
``adapters.base.Adapter``.

``sources/static_roster.py`` (this ticket) implements
``discover -> fetch -> extract``, the same three-method shape
``TeamSource``/``Adapter`` use -- reusing that mental model is
deliberate (see ``teams/sources/base.py``'s own docstring, which this
module's rationale mirrors exactly for ``Place`` in place of ``Team``).

What is **not** reused is ``adapters.base`` or ``teams.sources.base``
themselves. This module (and every module in ``directory/sources/``)
must never import anything from ``partner_scrape.adapters.base`` or
``partner_scrape.teams.sources.base`` -- a structural safety guarantee,
not a style preference: a place source reachable from
``adapters.base.ADAPTERS`` would become reachable from
``pipeline.run()``, which would hand a ``Place`` object to
``normalize.run()`` -- a type it does not expect -- and crash.
``PlaceSource`` is its own ``Protocol`` with no import relationship to
either, so that failure mode cannot occur even by accident.
``tests/directory/test_sources_base.py`` asserts this boundary
directly, following ``tests/teams/test_sources_base.py``'s own
forbidden-import-scan precedent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol

from partner_scrape.directory.model import Place
from partner_scrape.fetch import Fetcher
from partner_scrape.registry.schema import SourceConfig


@dataclass
class PlaceRef:
    """A reference to one fetchable unit of source content.

    Parallel to ``teams.sources.base.TeamRef``. This ticket's
    ``static_roster.py`` source returns exactly one ``PlaceRef`` (the
    committed roster file); a future live source, if one is ever added,
    might return several.
    """

    url: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class RawPlaceResponse:
    """One fetched, not-yet-interpreted unit of raw source content.

    Parallel to ``teams.sources.base.RawTeamResponse``. Carries the
    ``ref`` it came from so ``extract()`` can log which request a
    malformed body belonged to.
    """

    ref: PlaceRef
    status: int
    body: str


class PlaceSource(Protocol):
    """Injectable per-source strategy: discover -> fetch -> extract.

    Every method takes the ``Fetcher``/``SourceConfig`` it needs as an
    explicit argument rather than storing them on the instance, matching
    ``teams.sources.base.TeamSource``'s convention -- source instances
    are constructed fresh per run, so there is no instance state to
    inject into.
    """

    def discover(self, source: SourceConfig, fetcher: Fetcher) -> Iterable[PlaceRef]:
        """Resolve ``source`` into the set of fetchable ``PlaceRef``s."""
        ...

    def fetch(self, ref: PlaceRef, fetcher: Fetcher) -> RawPlaceResponse:
        """Retrieve one ``PlaceRef``'s raw content via the injected ``fetcher``."""
        ...

    def extract(self, raw: RawPlaceResponse, source: SourceConfig) -> Iterable[Place]:
        """Map one raw response into zero or more ``Place`` records.

        Implementations must isolate per-record failures: one malformed
        record in an otherwise good response is logged and skipped, not
        raised -- matching every other ``*Source.extract()``'s
        convention in this codebase.
        """
        ...


def run(source: SourceConfig, place_source: PlaceSource, fetcher: Fetcher) -> list[Place]:
    """Chain discover -> fetch -> extract for one ``PlaceSource``.

    Parallel to ``teams.sources.base.run()``, but takes the
    ``PlaceSource`` as an explicit argument rather than dispatching
    through a registry -- ``directory.pipeline.run_directory()`` is the
    intended caller once more than one source exists to sequence.
    """
    refs = list(place_source.discover(source, fetcher))

    places: list[Place] = []
    for ref in refs:
        raw = place_source.fetch(ref, fetcher)
        places.extend(place_source.extract(raw, source))
    return places
