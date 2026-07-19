"""The Generic HTML Extractor: a fixed priority ladder of field strategies.

See ``sprint.md``'s Architecture > Generic HTML Extractor, SUC-010. Given
one arbitrary event page's raw HTML and its URL, :func:`extract_fields`
tries a fixed sequence of extraction strategies ("rungs") in priority
order -- JSON-LD ``Event`` schema, ``<time datetime>`` elements,
OpenGraph meta tags, an h1/``<title>`` fallback, URL/slug-embedded date
patterns, and body-text date regex -- each rung filling only the
canonical ``Event`` fields still missing from an earlier, higher-trust
rung. The h1/``<title>`` fallback is not one of the five rungs
``sprint.md``'s Description names explicitly, but every rung after
JSON-LD/OpenGraph needs *some* source for ``title`` or the record would
be dropped for having none -- this ports the equivalent step from
``dev/extract_events.py``'s ``extract_generic`` (its step 4) rather than
inventing new behavior.

This module returns field values + a confidence tier per field, never an
``Event`` -- constructing the canonical record is the ``generic_html``
Adapter's job (``adapters/generic_html.py``), not this one's (sprint.md's
Design Rationale on why the Extractor and the Adapter are separate
modules).

Ported from ``dev/extract_events.py``'s proven logic (``extract_json_ld``,
``extract_time_elements``, ``extract_generic``, and the useful
site-agnostic parts of its BiblioCommons/Drupal/title-date extractors) as
ladder strategies in this one module -- not bespoke per-site scripts
(this ticket's Scope). Uses ``lxml`` for HTML parsing, already a
declared ``partner_scrape`` dependency since sprint 001.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any, Callable

from lxml import html as lxml_html
from lxml.html import HtmlElement

logger = logging.getLogger(__name__)

#: Confidence tiers, one per ladder rung, in strictly descending priority
#: order (structured/high -> regex/low, per sprint.md's Architecture).
#: Per-field tuning within a rung is deliberately out of scope -- the
#: ticket's Implementation Plan calls for "tier constants... not
#: per-field tuning."
CONFIDENCE_JSON_LD = 1.0
CONFIDENCE_TIME_TAG = 0.8
CONFIDENCE_OPENGRAPH = 0.6
CONFIDENCE_TITLE_FALLBACK = 0.5
CONFIDENCE_URL_DATE = 0.4
CONFIDENCE_BODY_REGEX = 0.2

#: A ladder rung: given the parsed page and its URL, return whatever
#: canonical ``Event`` fields it can find, unconfident-adjusted -- the
#: caller (:func:`extract_fields`) attaches the rung's confidence tier.
_RungFn = Callable[[HtmlElement, str], dict[str, Any]]

_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
_MONTH_PATTERN = "(" + "|".join(name.capitalize() for name in _MONTHS) + ")"

#: A ``<time datetime="...">`` value is only trusted as a real date if it
#: starts with an ISO ``YYYY-MM-DD`` -- matches
#: ``dev/extract_events.py``'s ``extract_time_elements`` filter.
_TIME_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")

#: URL/slug-embedded ISO date, e.g. ``/events/star-party-2026-04-22/``.
_URL_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")

#: Body-text date regex: an optional weekday prefix, then "Month DD,
#: YYYY" -- the most reliable of ``dev/extract_events.py``'s
#: ``parse_date_text`` patterns (its pattern 1), the only one precise
#: enough to trust at the ladder's lowest confidence tier without a
#: separate year-inference step.
_BODY_DATE_RE = re.compile(
    r"(?:(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+)?"
    + _MONTH_PATTERN
    + r"\s+(\d{1,2})(?:st|nd|rd|th)?,?\s*(\d{4})",
    re.IGNORECASE,
)


def _parse_iso(value: str | None) -> datetime | None:
    """Parse an ISO-ish datetime string (JSON-LD ``startDate``/``endDate``,
    a ``<time datetime>`` attribute). Returns ``None`` on anything absent
    or unparseable rather than raising -- a malformed date on one field
    must not fail the whole rung.
    """
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _json_ld_location(location: Any) -> str:
    """Build a single display string from JSON-LD's ``location`` shape
    (a bare string, or a ``Place`` object with a nested ``address``).
    """
    if isinstance(location, str):
        return location.strip()
    if isinstance(location, dict):
        address = location.get("address")
        parts = [location.get("name", "")]
        if isinstance(address, str):
            parts.append(address)
        elif isinstance(address, dict):
            parts.append(address.get("streetAddress", ""))
            parts.append(address.get("addressLocality", ""))
        return ", ".join(part.strip() for part in parts if part and part.strip())
    return ""


def _json_ld_cost(offers: Any) -> str:
    """Extract a display cost from JSON-LD's ``offers`` shape (a single
    ``Offer`` object, or a list of them -- the first is used).
    """
    if isinstance(offers, dict):
        price = offers.get("price")
    elif isinstance(offers, list) and offers and isinstance(offers[0], dict):
        price = offers[0].get("price")
    else:
        price = None
    return str(price).strip() if price not in (None, "") else ""


def _json_ld_image(image: Any) -> str:
    """Extract an image URL from JSON-LD's ``image`` shape (a bare URL
    string, a list of them, or an ``ImageObject``).
    """
    if isinstance(image, str):
        return image.strip()
    if isinstance(image, list) and image:
        first = image[0]
        if isinstance(first, str):
            return first.strip()
        if isinstance(first, dict):
            return (first.get("url") or "").strip()
    if isinstance(image, dict):
        return (image.get("url") or "").strip()
    return ""


def _find_json_ld_event(tree: HtmlElement) -> dict[str, Any] | None:
    """Find the first JSON-LD ``Event`` object among the page's
    ``<script type="application/ld+json">`` tags.

    Handles a bare object, an array of objects, and an ``@graph``
    wrapper -- the shapes ``dev/extract_events.py``'s ``extract_json_ld``
    and real-world sites actually use. A malformed or non-Event script
    is skipped, not fatal to the rest of the page.
    """
    for script in tree.iter("script"):
        script_type = script.get("type") or ""
        if "ld+json" not in script_type:
            continue
        try:
            data = json.loads(script.text or "")
        except (json.JSONDecodeError, TypeError):
            continue

        candidates = data if isinstance(data, list) else [data]
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            if candidate.get("@type") == "Event":
                return candidate
            graph = candidate.get("@graph")
            if isinstance(graph, list):
                for item in graph:
                    if isinstance(item, dict) and item.get("@type") == "Event":
                        return item
    return None


def _extract_json_ld(tree: HtmlElement, url: str) -> dict[str, Any]:
    """Rung 1: JSON-LD ``Event`` schema -- highest-trust, structured data
    the page author explicitly marked up for machine consumption.
    """
    event = _find_json_ld_event(tree)
    if event is None:
        return {}

    fields: dict[str, Any] = {}

    title = (event.get("name") or "").strip()
    if title:
        fields["title"] = title

    description = (event.get("description") or "").strip()
    if description:
        fields["description"] = description

    start = _parse_iso(event.get("startDate"))
    if start is not None:
        fields["start"] = start

    end = _parse_iso(event.get("endDate"))
    if end is not None:
        fields["end"] = end

    location = _json_ld_location(event.get("location"))
    if location:
        fields["location"] = location

    cost = _json_ld_cost(event.get("offers"))
    if cost:
        fields["cost"] = cost

    image_url = _json_ld_image(event.get("image"))
    if image_url:
        fields["image_url"] = image_url

    return fields


def _extract_time_tags(tree: HtmlElement, url: str) -> dict[str, Any]:
    """Rung 2: ``<time datetime="...">`` elements -- server-rendered ISO
    datetimes with no JSON-LD markup. The first is treated as ``start``,
    a second (if present) as ``end`` -- matches
    ``dev/extract_events.py``'s BiblioCommons extractor convention.
    """
    values: list[datetime] = []
    for el in tree.iter("time"):
        raw_dt = el.get("datetime") or ""
        if not _TIME_DATETIME_RE.match(raw_dt):
            continue
        parsed = _parse_iso(raw_dt)
        if parsed is not None:
            values.append(parsed)

    fields: dict[str, Any] = {}
    if values:
        fields["start"] = values[0]
        if len(values) >= 2:
            fields["end"] = values[1]
    return fields


def _extract_opengraph(tree: HtmlElement, url: str) -> dict[str, Any]:
    """Rung 3: OpenGraph/description meta tags -- reliable for title,
    description, and image, never a date (``article:modified_time`` is
    the page's edit time, not the event's -- ``dev/SCRAPER_GUIDELINES.md``
    #4 explicitly warns against treating it as one).
    """
    fields: dict[str, Any] = {}
    for el in tree.iter("meta"):
        prop = (el.get("property") or el.get("name") or "").lower()
        content = (el.get("content") or "").strip()
        if not content:
            continue
        if prop == "og:title" and "title" not in fields:
            fields["title"] = content
        elif prop in ("og:description", "description") and "description" not in fields:
            fields["description"] = content
        elif prop == "og:image" and "image_url" not in fields:
            fields["image_url"] = content
    return fields


def _extract_title_fallback(tree: HtmlElement, url: str) -> dict[str, Any]:
    """Rung 4: an h1, then the ``<title>`` tag -- the last-resort title
    source a page with no structured markup at all still needs, so the
    URL-date and body-regex rungs below have something to attach a date
    to instead of being dropped for want of a title.
    """
    for h1 in tree.iter("h1"):
        text = h1.text_content().strip()
        if text:
            return {"title": text}

    title_el = tree.find(".//title")
    if title_el is not None:
        text = title_el.text_content().strip()
        if text:
            return {"title": text}

    return {}


def _extract_url_date(tree: HtmlElement, url: str) -> dict[str, Any]:
    """Rung 5: a ``YYYY-MM-DD`` date embedded in the page's own URL/slug,
    e.g. ``/events/star-party-2026-04-22/`` -- reliable when present
    (``dev/SCRAPER_GUIDELINES.md`` #5 rates it 100% accurate) but rare.
    """
    match = _URL_DATE_RE.search(url)
    if not match:
        return {}
    year, month, day = (int(group) for group in match.groups())
    try:
        return {"start": datetime(year, month, day)}
    except ValueError:
        return {}


def _extract_body_regex(tree: HtmlElement, url: str) -> dict[str, Any]:
    """Rung 6 (lowest confidence): a "Month DD, YYYY" date string
    (optionally weekday-prefixed) found in the page's body text --
    matches ``dev/extract_events.py``'s ``parse_date_text`` pattern 1,
    scanning only the first 3000 characters like that module does.
    """
    body = tree.find(".//body")
    if body is None:
        return {}
    text = body.text_content()[:3000]
    match = _BODY_DATE_RE.search(text)
    if not match:
        return {}
    month_name, day, year = match.groups()
    try:
        return {"start": datetime(int(year), _MONTHS[month_name.lower()], int(day))}
    except (ValueError, KeyError):
        return {}


#: The ladder itself: (confidence, rung) pairs in strict priority order.
#: :func:`extract_fields` walks this list top to bottom, only filling
#: fields a higher rung hasn't already supplied.
_LADDER: list[tuple[float, _RungFn]] = [
    (CONFIDENCE_JSON_LD, _extract_json_ld),
    (CONFIDENCE_TIME_TAG, _extract_time_tags),
    (CONFIDENCE_OPENGRAPH, _extract_opengraph),
    (CONFIDENCE_TITLE_FALLBACK, _extract_title_fallback),
    (CONFIDENCE_URL_DATE, _extract_url_date),
    (CONFIDENCE_BODY_REGEX, _extract_body_regex),
]


def extract_fields(html: str, url: str) -> dict[str, tuple[Any, float]]:
    """Run the extraction priority ladder over one HTML page.

    Returns ``{field_name: (value, confidence)}`` for every canonical
    ``Event`` field some rung could recover -- never an ``Event`` itself
    (that's the ``generic_html`` Adapter's job). Each successive rung
    only fills fields still missing from an earlier, higher-confidence
    rung; a field no rung recovered (most commonly ``start``/``end`` on
    a page with no date signal at all) is simply absent from the result,
    not present with a placeholder value.

    Malformed/unparseable HTML yields an empty result (with a logged
    warning) rather than raising -- ``lxml.html.fromstring`` already
    tolerates most real-world markup, so this only triggers on a
    genuinely empty or non-HTML body.
    """
    try:
        tree = lxml_html.fromstring(html)
    except Exception:
        logger.warning("Could not parse HTML for %s; no fields extracted", url)
        return {}

    fields: dict[str, tuple[Any, float]] = {}
    for confidence, rung in _LADDER:
        found = rung(tree, url)
        for name, value in found.items():
            if name in fields:
                continue
            if value in (None, ""):
                continue
            fields[name] = (value, confidence)
    return fields
