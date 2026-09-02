"""The canonical Event record.

Every adapter (ticket 004+) constructs one canonical ``Event`` per
source record, regardless of which structured API it came from. The
shape is a flat dataclass plus a side-car ``field_provenance`` map --
see sprint.md's "Design Rationale" for why a per-field wrapper type
was rejected in favor of this shape: it keeps adapter code ergonomic
(``event.title = "..."``) while still meeting the per-field
provenance/confidence requirement (SUC-004).

This module also owns identity-key derivation: the *acquisition*
identity that answers "have we already seen this exact record from
this source." This is distinct from the cross-source dedup identity
built in ticket 006, which answers "is this the same event as one
from another org" -- a different, coarser question.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal

#: What a source record represents. Every structured adapter this
#: sprint defaults to "event" (see sprint.md Open Question 3); the
#: internship-capable adapter (issue 11) is what will first set the
#: other values.
Kind = Literal["event", "program", "internship"]

#: (Sprint 027) The `Kind` values that get curated-record bypass
#: treatment across the pipeline: `enrich.enricher.LLMEnricher`'s pass-1
#: skip (no cache lookup, no LLM call, no field mutation) and
#: `normalize.run()`'s collapse/dedup bypass (each Event becomes its own
#: 1:1 Instance instead of being routed through `collapse_recurring`/
#: `dedup_cross_source`). Generalizes what was previously a single
#: hardcoded `kind == "internship"` check duplicated at three call sites
#: across two modules -- see `enrich/DESIGN.md` and `normalize/DESIGN.md`'s
#: sprint 027 additions. This is the explicit reuse surface sprints 029
#: (competitions) and 030 (educator programs) build on: registering a
#: source with `program_kind = "program"` gets the same bypass treatment
#: with zero further code change.
PROGRAM_EXTRACTION_KINDS = frozenset({"internship", "program"})

# Identity keys are tuples of these two shapes -- see identity_key().
IdentityKey = tuple[str, str] | tuple[str, str, date | None]

_PUNCT_RE = re.compile(r"[^\w\s]", flags=re.UNICODE)
_WHITESPACE_RE = re.compile(r"\s+")
_SLUG_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_SLUG_STRIP_RE = re.compile(r"^_+|_+$")


def normalize_title(title: str) -> str:
    """Normalize a title for identity/dedup comparisons.

    Lowercases, strips punctuation, and collapses whitespace. Shared
    between this module's identity-key derivation and ticket 006's
    cross-source dedup -- both are "how do we recognize the same
    thing" logic, so the rule lives in one place.
    """
    lowered = title.lower()
    no_punctuation = _PUNCT_RE.sub("", lowered)
    return _WHITESPACE_RE.sub(" ", no_punctuation).strip()


def slugify(text: str) -> str:
    """Turn `text` into a URL-safe slug fragment.

    Lowercases, collapses every run of non-alphanumeric characters into
    a single underscore, and strips leading/trailing underscores.
    Promoted from `normalize/run.py`'s private `_slugify` (sprint 009,
    ticket 002) -- behavior unchanged, just relocated so both the event
    slug (`normalize/run.py`) and the partner slug
    (`export/partner_log.py`, ticket 003) share one primitive. Matches
    `site/src/lib/helpers.ts`'s `slugify()` convention.
    """
    return _SLUG_STRIP_RE.sub("", _SLUG_NON_ALNUM_RE.sub("_", text.lower()))


@dataclass(frozen=True)
class Provenance:
    """Where a single Event field's value came from, and how sure we are."""

    source: str
    confidence: float


@dataclass
class Event:
    """The canonical event/program/internship record.

    Fields are populated directly (``event.title = "..."``) or, when
    provenance/confidence tracking is wanted, via :meth:`set`. Fields
    never touched via ``set`` simply have no entry in
    ``field_provenance`` -- there is no requirement that every field be
    tracked, only that adapters *can* track the ones they extract.
    """

    kind: Kind = "event"

    # Identity fields
    source_id: str = ""
    external_id: str = ""
    url: str = ""

    # Acquisition-trust flag (OOP, 2026-07-20): set by an adapter, never
    # by enrichment, for a source whose records are first-party and
    # curated enough that the LLM relevance gate (enrich/enricher.py)
    # must never drop them outright -- e.g. adapters/leaguesync.py's
    # classes, pulled straight from the League's own booking data.
    # Additive default (False) reproduces every pre-existing adapter's
    # and test's behavior exactly -- only an adapter that opts in by
    # setting it True changes gating behavior at all. Deliberately a
    # plain attribute, not tracked via Event.set()/field_provenance --
    # it is acquisition metadata about the record's source, not a
    # value with its own provenance to record.
    trusted: bool = False

    # Content fields
    title: str = ""
    description: str = ""
    start: datetime | None = None
    end: datetime | None = None
    all_day: bool = False
    location: str = ""
    latitude: float | None = None
    longitude: float | None = None
    cost: str = ""
    registration_url: str = ""
    image_url: str = ""
    categories: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    # LLM-derived classification/relevance fields (sprint 002, issue 04).
    # Additive: default values reproduce sprint 001 behavior exactly (no
    # field_provenance entry until something calls .set() for one of
    # these -- see normalize/run.py's fallback-to-taxonomy.py logic and
    # sprint.md's Design Rationale for why these live directly on Event
    # rather than a separate wrapper type).
    relevant: bool | None = None
    relevance_reason: str = ""
    areas_of_interest: list[str] = field(default_factory=list)
    age_grade_level: list[str] = field(default_factory=list)
    cost_range: str = ""
    time_of_day: list[str] = field(default_factory=list)

    # opportunity_type classification (sprint 009, issue 13): threaded
    # through the exact same LLM-enrichment/field_provenance pattern as
    # the four classification fields above -- see enrich/DESIGN.md and
    # normalize/DESIGN.md's sprint 009 additions. Default "" (not the
    # site's "Out-of-school Programs" bucket) so an untouched Event still
    # reproduces every pre-existing behavior exactly; the site-facing
    # default is applied downstream, in normalize/taxonomy.py and the
    # LLM prompt, never here.
    opportunity_type: str = ""

    # Per-record eligibility note (sprint 027, issue 28): set via
    # Event.set(...) by the program-page extraction adapters for the
    # case a per-*source* SourceConfig.taxonomy_defaults.eligibility
    # default cannot express -- e.g. a listing source whose individual
    # program cards each need a different eligibility note. Additive
    # default "" reproduces every pre-existing adapter's and test's
    # behavior exactly; see normalize/run.py's _to_opportunity() for the
    # field_provenance-presence precedence over source_taxonomy_defaults.
    eligibility: str = ""

    # Side-car provenance/confidence map, keyed by field name.
    field_provenance: dict[str, Provenance] = field(default_factory=dict)

    def set(self, field: str, value: Any, source: str, confidence: float) -> None:
        """Set ``field`` to ``value`` and record its provenance atomically.

        Raises:
            AttributeError: if ``field`` is not a real attribute of
                ``Event`` -- catches adapter typos early rather than
                silently creating a stray provenance entry for a field
                that was never set.
        """
        if not hasattr(self, field):
            raise AttributeError(f"Event has no field {field!r}")
        setattr(self, field, value)
        self.field_provenance[field] = Provenance(source=source, confidence=confidence)

    def identity_key(self) -> IdentityKey:
        """Derive this Event's acquisition identity key.

        ``(source_id, external_id)`` when ``external_id`` is truthy,
        else ``(source_id, normalized_title, start_date)``. This
        answers "have we already seen this exact record from this
        source" -- not the cross-source dedup question ticket 006
        answers.
        """
        return identity_key(self)


def identity_key(event: Event) -> IdentityKey:
    """Derive an Event's acquisition identity key.

    See :meth:`Event.identity_key` -- this free function is the actual
    implementation so it can be reused without an Event instance in
    hand (e.g. by future code that only has raw fields).
    """
    if event.external_id:
        return (event.source_id, event.external_id)
    start_date = event.start.date() if event.start is not None else None
    return (event.source_id, normalize_title(event.title), start_date)


def same_record(a: Event, b: Event) -> bool:
    """Report whether two Events represent the same acquired record.

    Deliberately not full dataclass equality (``==``): two Events with
    the same identity key may still differ in unrelated fields (e.g. a
    re-fetch picked up an updated description), and that must not make
    them "different" for identity purposes.
    """
    return identity_key(a) == identity_key(b)
