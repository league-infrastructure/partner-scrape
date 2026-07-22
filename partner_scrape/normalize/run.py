"""`normalize.run()`: the Normalize & Dedup module's single entry point.

Maps canonical Events -> deduplicated, taxonomy-tagged `Opportunity`
records (sprint.md Architecture > Normalize & Dedup, SUC-005/SUC-006).
Named `run.py`, not `pipeline.py`, to avoid colliding with the
top-level `partner_scrape/pipeline.py` ticket 008 builds.

Pipeline order: collapse recurring instances first (shrinks what
cross-source dedup has to compare), then cross-source dedup, then map
each surviving :class:`~partner_scrape.normalize.instance.Instance` to
an `Opportunity` (taxonomy derivation + partner join) last. That order
-- rather than the ticket's suggested "map then collapse then dedup" --
is deliberate: collapse.py/dedup.py's "highest-confidence/most-complete"
selection needs `Event.field_provenance`'s per-field confidence, which
does not survive the mapping into `Opportunity` (which has no
per-field confidence concept). Doing the confidence-aware selection
first, on Events, and mapping only the survivors, is what makes that
selection possible at all. See collapse.py's and dedup.py's module
docstrings for the rest of the ordering rationale.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Iterable

from partner_scrape.model import Event
from partner_scrape.normalize.collapse import collapse_recurring
from partner_scrape.normalize.dedup import dedup_cross_source
from partner_scrape.normalize.instance import Instance
from partner_scrape.normalize.partners import find_partner, load_partners
from partner_scrape.normalize.taxonomy import (
    build_taxonomy_text,
    classify_opportunity_type,
    derive_age_grade_level,
    derive_areas_of_interest,
    derive_time_of_day,
    map_cost,
)

#: Every source this sprint is calendar-style (sprint.md Open Question
#: 3) -- matches `dev/export_site.py`'s hardcoded default. No keyword
#: rule derives this field this sprint (issue 04, sprint 2+).
DEFAULT_OPPORTUNITY_TYPE = "Out-of-school Programs"

#: The site's existing `opportunity_type` enum value
#: (`stem-ecosystem/docs/site-implementation-spec.md`) reused, unmodified,
#: as the internship discriminator (sprint 006 Design Rationale: "reuse
#: the existing opportunity_type field ... instead of adding a new
#: field"). Exported so `export/writer.py` can key its current/upcoming
#: branch on the same constant rather than a duplicated string literal.
WORK_BASED_LEARNING_TYPE = "Work-based Learning"

#: TZ offset embedded on naive display-only ISO datetimes so the site
#: shows the correct San Diego calendar day -- matches
#: `dev/export_site.py`'s `TZ`. Every adapter this sprint produces naive
#: `datetime`s (no adapter sets `tzinfo`), so this is applied whenever
#: `Event.start`/`.end` lack one; a future tz-aware source's own offset
#: is left untouched.
_TZ_OFFSET = "-07:00"

_SLUG_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_SLUG_STRIP_RE = re.compile(r"^_+|_+$")


@dataclass
class Opportunity:
    """The site's opportunity record (`stem-ecosystem/docs/site-implementation-spec.md`).

    Every field through `image_src` is part of the site's JSON contract
    (ticket 007 writes exactly these, matching
    `dev/export_site.py`'s `build_opportunity` output shape). `image_src`
    (sprint 008 ticket 008, issue 19) follows the exact same convention
    `logo_src` already established: a pre-resolved local filename (empty
    string when absent), never a remote URL -- by the time the site
    consumes `opportunities.json`, any image it references has already
    been downloaded and self-hosted by the Event Image Downloader
    (`export/images.py`), never hotlinked at request time. `sources`
    is this module's own bookkeeping -- the full set of `source_id`s a
    cross-source-merged record was seen on (SUC-006's "the set of
    contributing sources is recorded on the record, not silently
    dropped" acceptance criterion) -- and is not part of the site
    schema; ticket 007 decides whether/how to carry or drop it when
    writing `opportunities.json`.
    """

    slug: str
    title: str
    partner_name: str
    partner_id: int | None
    description: str
    link: str
    availability: str
    date_start: str
    date_end: str
    age_grade_level: list[str]
    cost_range: str
    time_of_day: list[str]
    opportunity_type: str
    areas_of_interest: list[str]
    specific_attention: list[str]
    financial_support: str
    ngss_aligned: str
    location: str
    latitude: str
    longitude: str
    contact_name: str
    contact_email: str
    contact_phone: str
    logo_src: str
    image_src: str = ""
    sources: frozenset[str] = field(default_factory=frozenset)


def _slugify(text: str) -> str:
    return _SLUG_STRIP_RE.sub("", _SLUG_NON_ALNUM_RE.sub("_", text.lower()))


def _iso(dt: datetime | None) -> str:
    """Format a `datetime` as ISO 8601, embedding `_TZ_OFFSET` if naive; `""` if unset."""
    if dt is None:
        return ""
    if dt.tzinfo is not None:
        return dt.isoformat()
    return dt.isoformat() + _TZ_OFFSET


def _availability(instance: Instance) -> str:
    """"Repeats N times through <date>" when `instance` collapsed more than one
    occurrence; `""` otherwise (SUC-006's recurring-collapse acceptance criterion)."""
    if instance.repeat_count > 1 and instance.last_seen is not None:
        return f"Repeats {instance.repeat_count} times through {instance.last_seen.isoformat()}"
    return ""


def _internship_availability(event: Event) -> str:
    """"Apply by <date>" when `event.end` (the application deadline) is set;
    "Rolling -- apply anytime" otherwise (sprint.md Design Rationale: reuse
    `date_start`/`date_end`/`availability` with redefined internship-specific
    meaning -- most ATS postings expose no reliable deadline, so "still
    present in the feed" is itself the "still open" signal, not a date)."""
    if event.end is not None:
        return f"Apply by {event.end.date().isoformat()}"
    return "Rolling — apply anytime"


def _date_slug_part(instance: Instance) -> str:
    event = instance.event
    if event.start is not None:
        return event.start.date().isoformat().replace("-", "")
    if instance.last_seen is not None:
        return instance.last_seen.isoformat().replace("-", "")
    return "undated"


def _to_opportunity(
    instance: Instance,
    partners_by_norm: dict[str, dict[str, Any]],
    org_name: str,
    image_resolver: Callable[[str], str] | None = None,
) -> Opportunity:
    event = instance.event
    partner = find_partner(org_name, partners_by_norm) or {}
    partner_name = partner.get("name") or org_name

    text = build_taxonomy_text(event.title, event.description, event.categories, event.tags)

    slug = (
        f"{_slugify(org_name)[:40]}_{_slugify(event.title)[:60]}_{_date_slug_part(instance)}"
    )

    latitude = str(event.latitude) if event.latitude is not None else str(partner.get("latitude", ""))
    longitude = str(event.longitude) if event.longitude is not None else str(partner.get("longitude", ""))

    # Prefer an Event's own LLM-set classification fields (sprint 002,
    # issue 04) over taxonomy.py's keyword fallback, checked
    # independently per field via field_provenance -- an Event can have
    # an LLM-set cost_range but no LLM-set areas_of_interest and get the
    # LLM value for one, the keyword-derived value for the other. Four
    # explicit branches, not a loop-driven helper: two different
    # fallback shapes (list[str] vs str) for exactly four call sites
    # isn't worth abstracting (sprint.md's speculative-generality
    # guidance).
    areas_of_interest = (
        event.areas_of_interest
        if "areas_of_interest" in event.field_provenance
        else derive_areas_of_interest(text)
    )
    age_grade_level = (
        event.age_grade_level
        if "age_grade_level" in event.field_provenance
        else derive_age_grade_level(text)
    )
    cost_range = (
        event.cost_range if "cost_range" in event.field_provenance else map_cost(event.cost)
    )
    time_of_day = (
        event.time_of_day
        if "time_of_day" in event.field_provenance
        else derive_time_of_day(event.start, event.all_day)
    )

    is_internship = event.kind == "internship"
    availability = _internship_availability(event) if is_internship else _availability(instance)
    # Internships force Work-based Learning by kind; everything else is
    # classified from its own text rather than blindly stamped with the
    # default (which flattened every event into "Out-of-school Programs"
    # and left 7 of the site's 8 type filters permanently empty).
    opportunity_type = (
        WORK_BASED_LEARNING_TYPE if is_internship else classify_opportunity_type(event.title)
    )

    # Event Image Downloader (sprint 008 ticket 008, issue 19 scraper
    # half): `image_resolver` is a plain injected callable, not an
    # import of `export.images.EventImageDownloader` -- this keeps
    # `normalize` free of any dependency on `export`, matching
    # sprint.md's documented one-way module-dependency direction
    # (Export depends on Normalize, never the reverse). `pipeline.run()`
    # wires the real `EventImageDownloader.download` in; tests and any
    # caller that omits it get today's exact behavior (`image_src` stays
    # "", SUC-008's Alternate Flow) with zero network access attempted.
    image_src = image_resolver(event.image_url) if image_resolver and event.image_url else ""

    return Opportunity(
        slug=slug,
        title=event.title,
        partner_name=partner_name,
        partner_id=partner.get("id"),
        description=event.description,
        link=event.registration_url or event.url,
        availability=availability,
        date_start=_iso(event.start),
        date_end=_iso(event.end),
        age_grade_level=age_grade_level,
        cost_range=cost_range,
        time_of_day=time_of_day,
        opportunity_type=opportunity_type,
        areas_of_interest=areas_of_interest,
        specific_attention=[],
        financial_support="No",
        ngss_aligned="No",
        location=event.location or partner.get("location", ""),
        latitude=latitude,
        longitude=longitude,
        contact_name="",
        contact_email="",
        contact_phone="",
        logo_src=partner.get("logo_src", ""),
        image_src=image_src,
        sources=instance.sources,
    )


def run(
    events: Iterable[Event],
    partners_path: str | Path,
    source_org_names: dict[str, str] | None = None,
    today: date | None = None,
    image_resolver: Callable[[str], str] | None = None,
) -> list[Opportunity]:
    """Normalize ``events`` into deduplicated, taxonomy-tagged Opportunities.

    Args:
        events: canonical Events from any number of adapters/sources.
        partners_path: path to the site's `partners.json` (read-only).
        source_org_names: optional `source_id -> org_name` map, used
            only for the partner-name join. The canonical `Event` (ticket
            001's model, not extended by this ticket) carries no
            organization-name field, only `source_id` -- so a caller
            that has the Source Registry in hand (ticket 008's Pipeline,
            which loads the registry to dispatch sources in the first
            place) can pass `{source.source_id: source.org_name for
            source in sources}` through here. When a `source_id` is
            absent from the map (including when the map itself is
            omitted, as in this module's own unit tests), the
            `source_id` is used as the org name; it usually won't match
            a `partners.json` entry, which is fine -- SUC-005's
            documented error flow is "no match -> keep the org name,
            leave partner_id unset, do not fail the record."
        image_resolver: optional `image_url -> local filename` callable
            (sprint 008 ticket 008, issue 19), called once per surviving
            `Event` that has a non-empty `image_url` to populate
            `Opportunity.image_src`. Defaults to `None`, which leaves
            `image_src` `""` for every record (today's exact pre-ticket-008
            behavior) with zero network access attempted -- the production
            caller (`pipeline.run()`) passes a real
            `export.images.EventImageDownloader.download` bound method;
            this module never imports `export` itself (see
            `_to_opportunity`'s comment for why).

    Returns:
        One `Opportunity` per surviving, deduplicated/collapsed record.
    """
    source_org_names = source_org_names or {}
    today = today or date.today()
    partners_by_norm = load_partners(partners_path)

    # Enforce a single datetime convention before any date comparison.
    # Adapters are supposed to emit naive, San-Diego-wall-clock datetimes
    # (the iCal adapter documents this), but some structured-API adapters
    # (BiblioCommons, Lever) emit timezone-aware datetimes. Mixing naive
    # and aware datetimes makes collapse_recurring/dedup's min()/max()
    # raise "can't compare offset-naive and offset-aware datetimes", which
    # crashes the whole run. Coerce every aware datetime to naive here, in
    # one place, so no single adapter's tz-awareness can break the pipeline.
    for event in events:
        if event.start is not None and event.start.tzinfo is not None:
            event.start = event.start.replace(tzinfo=None)
        if event.end is not None and event.end.tzinfo is not None:
            event.end = event.end.replace(tzinfo=None)

    internship_events: list[Event] = []
    other_events: list[Event] = []
    for event in events:
        (internship_events if event.kind == "internship" else other_events).append(event)

    collapsed = collapse_recurring(other_events, today)
    deduped = dedup_cross_source(collapsed)

    # kind="internship" Events bypass both collapse_recurring and
    # dedup_cross_source entirely (sprint.md Design Rationale:
    # "kind='internship' Events bypass both collapse_recurring and
    # dedup_cross_source") -- both stages' identity assumptions (same
    # source+title recurs; same title+date+venue across sources is the
    # same real-world event) don't hold for distinct job requisitions,
    # so each internship Event is wrapped 1:1 into its own Instance
    # instead of being routed through either stage.
    internship_instances = [
        Instance(
            event=event,
            sources=frozenset({event.source_id}),
            repeat_count=1,
            last_seen=(event.start.date() if event.start is not None else None),
        )
        for event in internship_events
    ]

    all_instances = deduped + internship_instances

    opportunities: list[Opportunity] = []
    for instance in all_instances:
        org_name = source_org_names.get(instance.event.source_id, instance.event.source_id)
        opportunities.append(
            _to_opportunity(instance, partners_by_norm, org_name, image_resolver)
        )
    return opportunities
