"""The pluggable ``PlaceSource``, ``ClubSource``, and ``OfferingSource``
contracts -- parallel to, and structurally disjoint from,
``teams.sources.base.TeamSource`` and ``adapters.base.Adapter``.

``sources/static_roster.py`` (ticket 018-007),
``sources/hack_club_static_roster.py`` (ticket 018-008), and
``sources/offering_static_roster.py`` (sprint 030) each implement
``discover -> fetch -> extract``, the same three-method shape
``TeamSource``/``Adapter`` use -- reusing that mental model is
deliberate (see ``teams/sources/base.py``'s own docstring, which this
module's rationale mirrors exactly for ``Place``/``Club``/``Offering``
in place of ``Team``).

**``PlaceSource``, ``ClubSource``, and ``OfferingSource`` are three
separate ``Protocol``s, not one shared source contract.**
``Place.extract()``, ``Club.extract()``, and ``Offering.extract()``
return different record types, so a single ``Protocol`` typed
generically over "any of the three" would either lose real
type-checking or need a level of generic machinery this module's small
scope does not justify -- kept as three clearly-typed, near-identical
protocols instead, the same "field-name duplication accepted, no
shared base" tradeoff sprint 018's Design Rationale makes for the
``Place``/``Club``/``Offering`` record types themselves
(``directory/model.py``'s own docstring), extended here to the
record-specific source contracts for the identical reason.

What is **not** reused is ``adapters.base`` or ``teams.sources.base``
themselves. This module (and every module in ``directory/sources/``)
must never import anything from ``partner_scrape.adapters.base`` or
``partner_scrape.teams.sources.base`` -- a structural safety guarantee,
not a style preference: a place or club source reachable from
``adapters.base.ADAPTERS`` would become reachable from
``pipeline.run()``, which would hand a ``Place``/``Club`` object to
``normalize.run()`` -- a type it does not expect -- and crash.
``PlaceSource``/``ClubSource`` are their own ``Protocol``s with no
import relationship to either, so that failure mode cannot occur even
by accident. ``tests/directory/test_sources_base.py`` asserts this
boundary directly, following ``tests/teams/test_sources_base.py``'s
own forbidden-import-scan precedent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol

from partner_scrape.directory.model import Club, Offering, Place
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


@dataclass
class ClubRef:
    """A reference to one fetchable unit of source content, for a
    ``ClubSource``.

    Parallel to :class:`PlaceRef` above (and to
    ``teams.sources.base.TeamRef``). This ticket's
    ``sources/hack_club_static_roster.py`` returns exactly one
    ``ClubRef`` (the committed roster file).
    """

    url: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class RawClubResponse:
    """One fetched, not-yet-interpreted unit of raw source content, for
    a ``ClubSource``.

    Parallel to :class:`RawPlaceResponse` above. Carries the ``ref`` it
    came from so ``extract()`` can log which request a malformed body
    belonged to.
    """

    ref: ClubRef
    status: int
    body: str


class ClubSource(Protocol):
    """Injectable per-source strategy for ``Club`` acquisition:
    discover -> fetch -> extract. See :class:`PlaceSource` above and
    this module's own docstring for why this is a second, separately
    typed ``Protocol`` rather than a shared one.
    """

    def discover(self, source: SourceConfig, fetcher: Fetcher) -> Iterable[ClubRef]:
        """Resolve ``source`` into the set of fetchable ``ClubRef``s."""
        ...

    def fetch(self, ref: ClubRef, fetcher: Fetcher) -> RawClubResponse:
        """Retrieve one ``ClubRef``'s raw content via the injected ``fetcher``."""
        ...

    def extract(self, raw: RawClubResponse, source: SourceConfig) -> Iterable[Club]:
        """Map one raw response into zero or more ``Club`` records.

        Implementations must isolate per-record failures: one malformed
        record in an otherwise good response is logged and skipped, not
        raised -- matching every other ``*Source.extract()``'s
        convention in this codebase.
        """
        ...


def run_club_source(source: SourceConfig, club_source: ClubSource, fetcher: Fetcher) -> list[Club]:
    """Chain discover -> fetch -> extract for one ``ClubSource``.

    Parallel to ``run()`` above, but for ``Club`` instead of ``Place``
    -- kept a separate, distinctly-named and distinctly-typed function
    rather than a generic one reused across both record types, so a
    caller (and a type checker) can never confuse "list of Place" with
    "list of Club" through this chaining helper.
    """
    refs = list(club_source.discover(source, fetcher))

    clubs: list[Club] = []
    for ref in refs:
        raw = club_source.fetch(ref, fetcher)
        clubs.extend(club_source.extract(raw, source))
    return clubs


@dataclass
class OfferingRef:
    """A reference to one fetchable unit of source content, for an
    ``OfferingSource``.

    Parallel to :class:`PlaceRef`/:class:`ClubRef` above. This ticket's
    ``sources/offering_static_roster.py`` returns exactly one
    ``OfferingRef`` (the committed roster file) -- sprint 030's own
    addition.
    """

    url: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class RawOfferingResponse:
    """One fetched, not-yet-interpreted unit of raw source content, for
    an ``OfferingSource``.

    Parallel to :class:`RawPlaceResponse`/:class:`RawClubResponse`
    above. Carries the ``ref`` it came from so ``extract()`` can log
    which request a malformed body belonged to.
    """

    ref: OfferingRef
    status: int
    body: str


class OfferingSource(Protocol):
    """Injectable per-source strategy for ``Offering`` acquisition:
    discover -> fetch -> extract. See :class:`PlaceSource`/
    :class:`ClubSource` above and this module's own docstring for why
    this is a third, separately typed ``Protocol`` rather than a shared
    one -- sprint 030's own addition, structurally identical to the
    existing two.
    """

    def discover(self, source: SourceConfig, fetcher: Fetcher) -> Iterable[OfferingRef]:
        """Resolve ``source`` into the set of fetchable ``OfferingRef``s."""
        ...

    def fetch(self, ref: OfferingRef, fetcher: Fetcher) -> RawOfferingResponse:
        """Retrieve one ``OfferingRef``'s raw content via the injected ``fetcher``."""
        ...

    def extract(self, raw: RawOfferingResponse, source: SourceConfig) -> Iterable[Offering]:
        """Map one raw response into zero or more ``Offering`` records.

        Implementations must isolate per-record failures: one malformed
        record in an otherwise good response is logged and skipped, not
        raised -- matching every other ``*Source.extract()``'s
        convention in this codebase.
        """
        ...


def run_offering_source(
    source: SourceConfig, offering_source: OfferingSource, fetcher: Fetcher
) -> list[Offering]:
    """Chain discover -> fetch -> extract for one ``OfferingSource``.

    Parallel to ``run()``/``run_club_source()`` above, but for
    ``Offering`` instead of ``Place``/``Club`` -- same "kept separate
    for correct, unambiguous typing" rationale.
    """
    refs = list(offering_source.discover(source, fetcher))

    offerings: list[Offering] = []
    for ref in refs:
        raw = offering_source.fetch(ref, fetcher)
        offerings.extend(offering_source.extract(raw, source))
    return offerings
