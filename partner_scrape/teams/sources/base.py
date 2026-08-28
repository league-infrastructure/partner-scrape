"""The pluggable ``TeamSource`` contract -- parallel to, and
structurally disjoint from, ``adapters.base.Adapter``.

Every team acquisition source (``ftcscout.py`` here; ``tba.py`` in
ticket 011-003) implements ``discover -> fetch -> extract``, the same
three-method shape ``adapters.base.Adapter`` uses for Events -- reusing
that mental model is deliberate (see ``teams/DESIGN.md``'s Design
section, "no shared extraction code" but a shared protocol *shape*).

What is **not** reused is ``adapters.base`` itself. This module (and
every module in ``teams/sources/``) must never import anything from
``partner_scrape.adapters.base``, and no ``TeamSource`` is ever
registered with its ``ADAPTERS`` dispatch table. That boundary is a
structural safety guarantee, not a style preference: a team source
reachable from ``ADAPTERS`` would become reachable from
``pipeline.run()``, which would hand a ``Team`` object to
``normalize.run()`` -- a type it does not expect -- and crash.
``TeamSource`` is a separate ``Protocol`` with no import relationship
to ``Adapter`` at all, so that failure mode cannot occur even by
accident. ``tests/teams/test_sources_base.py`` asserts this boundary
directly by scanning every module in this package for an import of
``partner_scrape.adapters.base``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol

from partner_scrape.fetch import Fetcher
from partner_scrape.registry.schema import SourceConfig
from partner_scrape.teams.model import Team


@dataclass
class TeamRef:
    """A reference to one fetchable unit of source content.

    Parallel to ``adapters.base.EventRef``. For this ticket's FTCScout
    source, one ``TeamRef`` is the single region-search request; a
    richer, paginated source (ticket 011-003's TBA) may return several.
    """

    url: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class RawTeamResponse:
    """One fetched, not-yet-interpreted unit of raw source content.

    Parallel to ``adapters.base.RawResponse``. Carries the ``ref`` it
    came from so ``extract()`` can log which request a malformed body
    belonged to.
    """

    ref: TeamRef
    status: int
    body: str


class TeamSource(Protocol):
    """Injectable per-source strategy: discover -> fetch -> extract.

    Every method takes the ``Fetcher``/``SourceConfig`` it needs as an
    explicit argument rather than storing them on the instance, matching
    ``adapters.base.Adapter``'s convention -- source instances are
    constructed fresh per run, so there is no instance state to inject
    into.
    """

    def discover(self, source: SourceConfig, fetcher: Fetcher) -> Iterable[TeamRef]:
        """Resolve ``source`` into the set of fetchable ``TeamRef``s."""
        ...

    def fetch(self, ref: TeamRef, fetcher: Fetcher) -> RawTeamResponse:
        """Retrieve one ``TeamRef``'s raw content via the injected ``fetcher``."""
        ...

    def extract(self, raw: RawTeamResponse, source: SourceConfig) -> Iterable[Team]:
        """Map one raw response into zero or more ``Team`` records.

        Implementations must isolate per-record failures: one malformed
        record in an otherwise good response is logged and skipped, not
        raised -- matching every ``adapters.Adapter.extract()``'s
        convention.
        """
        ...


def run(source: SourceConfig, team_source: TeamSource, fetcher: Fetcher) -> list[Team]:
    """Chain discover -> fetch -> extract for one ``TeamSource``.

    Parallel to ``adapters.base.run()``, but takes the ``TeamSource`` as
    an explicit argument rather than dispatching through a registry --
    there is no ``teams``-side equivalent of ``adapters.base.ADAPTERS``
    (see this module's docstring for why). Ticket 011-002's
    ``teams.pipeline`` is the intended caller once more than one source
    exists to sequence.
    """
    refs = list(team_source.discover(source, fetcher))

    teams: list[Team] = []
    for ref in refs:
        raw = team_source.fetch(ref, fetcher)
        teams.extend(team_source.extract(raw, source))
    return teams
