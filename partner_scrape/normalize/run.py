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
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from partner_scrape.model import Event
from partner_scrape.normalize.collapse import collapse_recurring
from partner_scrape.normalize.dedup import dedup_cross_source
from partner_scrape.normalize.instance import Instance
from partner_scrape.normalize.partners import find_partner, load_partners
from partner_scrape.normalize.taxonomy import (
    build_taxonomy_text,
    derive_age_grade_level,
    derive_areas_of_interest,
    derive_time_of_day,
    map_cost,
)

#: Every source this sprint is calendar-style (sprint.md Open Question
#: 3) -- matches `dev/export_site.py`'s hardcoded default. No keyword
#: rule derives this field this sprint (issue 04, sprint 2+).
DEFAULT_OPPORTUNITY_TYPE = "Out-of-school Programs"

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

    Every field through `logo_src` is part of the site's JSON contract
    (ticket 007 writes exactly these, matching
    `dev/export_site.py`'s `build_opportunity` output shape). `sources`
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

    return Opportunity(
        slug=slug,
        title=event.title,
        partner_name=partner_name,
        partner_id=partner.get("id"),
        description=event.description,
        link=event.registration_url or event.url,
        availability=_availability(instance),
        date_start=_iso(event.start),
        date_end=_iso(event.end),
        age_grade_level=derive_age_grade_level(text),
        cost_range=map_cost(event.cost),
        time_of_day=derive_time_of_day(event.start, event.all_day),
        opportunity_type=DEFAULT_OPPORTUNITY_TYPE,
        areas_of_interest=derive_areas_of_interest(text),
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
        sources=instance.sources,
    )


def run(
    events: Iterable[Event],
    partners_path: str | Path,
    source_org_names: dict[str, str] | None = None,
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

    Returns:
        One `Opportunity` per surviving, deduplicated/collapsed record.
    """
    source_org_names = source_org_names or {}
    partners_by_norm = load_partners(partners_path)

    collapsed = collapse_recurring(events)
    deduped = dedup_cross_source(collapsed)

    opportunities: list[Opportunity] = []
    for instance in deduped:
        org_name = source_org_names.get(instance.event.source_id, instance.event.source_id)
        opportunities.append(_to_opportunity(instance, partners_by_norm, org_name))
    return opportunities
