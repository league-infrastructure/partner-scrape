"""The WordPress REST API adapter.

Per sprint.md's Open Question 2, no production target site is confirmed
for this adapter this sprint (only TEC has one) -- it is built
generically against the documented ``/wp-json/wp/v2/{post_type}``
collection shape and fixture-tested, with live registry entries deferred
to sprint 2.

WP REST's generic posts/pages endpoints carry no structured event
date/venue field the way TEC's API does, so this adapter never sets
``start``/``location`` -- see ``_extract_one``. That makes this
adapter's ``Event``s lower-quality than TEC's *by design*, and per this
ticket's Description that should be visible in *which* fields carry
provenance, not in an artificially lowered confidence number: every
field this adapter does set is exactly what WP REST returned, so it
uses :data:`CONFIDENCE` (1.0), same as TEC.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Iterable

from partner_scrape.adapters.base import EventRef, RawResponse
from partner_scrape.fetch import Fetcher
from partner_scrape.model import Event
from partner_scrape.registry.schema import SourceConfig

logger = logging.getLogger(__name__)

#: This adapter's provenance source name, recorded on every field it sets.
SOURCE_NAME = "wp_rest"

#: Every field this adapter sets (title/description/url) is exactly what
#: WP REST returned -- a structured, first-party field, same trust tier
#: as TEC's. See module docstring for why this isn't lowered to reflect
#: the fields this adapter *can't* set.
CONFIDENCE = 1.0

#: WP REST's own per_page ceiling (core rejects larger values). A source
#: with more posts/pages than this would need real pagination -- out of
#: scope this sprint per the ticket (no confirmed live target site to
#: size that against yet).
PAGE_SIZE = 100

#: Collection endpoints queried when a source's config doesn't specify
#: ``post_types`` -- just posts, the common case. A source can opt into
#: pages too via ``config.post_types = ["posts", "pages"]``.
DEFAULT_POST_TYPES = ("posts",)

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_HTML_ENTITIES = {
    "&amp;": "&",
    "&lt;": "<",
    "&gt;": ">",
    "&#8217;": "'",
    "&#8220;": '"',
    "&#8221;": '"',
    "&nbsp;": " ",
    "&#8211;": "-",
}


def _strip_html(text: str) -> str:
    """Strip HTML tags and decode the common entities WP-rendered fields use.

    Duplicated from ``tec.py`` rather than shared: this sprint has no
    shared-utils module, and two small, independent adapters each owning
    their own copy is cheaper than introducing one for two callers.
    """
    stripped = _TAG_RE.sub(" ", text)
    stripped = _WHITESPACE_RE.sub(" ", stripped).strip()
    for entity, replacement in _HTML_ENTITIES.items():
        stripped = stripped.replace(entity, replacement)
    return stripped


def _post_type_url(api_base: str, post_type: str) -> str:
    """Build one WP REST collection URL for ``post_type`` (e.g. ``posts``)."""
    return f"{api_base.rstrip('/')}/wp-json/wp/v2/{post_type}?per_page={PAGE_SIZE}"


def _extract_one(raw_post: dict[str, Any], source: SourceConfig) -> Event:
    """Map one raw WP REST post/page record into a canonical ``Event``.

    Raises:
        ValueError: the record has no usable title.

    Caught by the caller (``extract()``) as a per-record skip, matching
    ``tec.py``'s per-record error isolation.

    Deliberately never sets ``start`` or ``location`` -- see module
    docstring.
    """
    title = _strip_html((raw_post.get("title") or {}).get("rendered") or "")
    if not title:
        raise ValueError("post record has no title")

    event = Event(kind="event", source_id=source.source_id)
    event.external_id = str(raw_post.get("id") or "")

    event.set("title", title, source=SOURCE_NAME, confidence=CONFIDENCE)

    link = (raw_post.get("link") or "").strip()
    if link:
        event.set("url", link, source=SOURCE_NAME, confidence=CONFIDENCE)

    # Prefer the excerpt (already a description-length summary); fall
    # back to the full rendered content when no excerpt was published.
    excerpt = _strip_html((raw_post.get("excerpt") or {}).get("rendered") or "")
    content = _strip_html((raw_post.get("content") or {}).get("rendered") or "")
    description = excerpt or content
    if description:
        event.set("description", description, source=SOURCE_NAME, confidence=CONFIDENCE)

    return event


class WordPressRestAdapter:
    """``Adapter`` for a generic WordPress REST API (``wp_rest``)."""

    def discover(self, source: SourceConfig, fetcher: Fetcher) -> list[EventRef]:
        """One ``EventRef`` per configured ``post_types`` collection.

        No pagination beyond WP's own ``per_page`` ceiling -- see
        :data:`PAGE_SIZE`.
        """
        api_base = source.config["api_base"]
        post_types = source.config.get("post_types") or list(DEFAULT_POST_TYPES)
        return [EventRef(url=_post_type_url(api_base, post_type)) for post_type in post_types]

    def fetch(self, ref: EventRef, fetcher: Fetcher) -> RawResponse:
        response = fetcher.get(ref.url)
        return RawResponse(ref=ref, status=response.status, body=response.body)

    def extract(self, raw: RawResponse, source: SourceConfig) -> Iterable[Event]:
        if raw.status != 200:
            logger.warning(
                "WP REST fetch %s returned status %s; skipping", raw.ref.url, raw.status
            )
            return []

        try:
            data = json.loads(raw.body)
        except json.JSONDecodeError:
            logger.warning("WP REST response %s was unparseable JSON; skipping", raw.ref.url)
            return []

        if not isinstance(data, list):
            logger.warning(
                "WP REST response %s was not a JSON array of posts; skipping", raw.ref.url
            )
            return []

        events: list[Event] = []
        for raw_post in data:
            try:
                events.append(_extract_one(raw_post, source))
            except (ValueError, TypeError, AttributeError) as exc:
                logger.warning(
                    "Skipping malformed WP REST post record on %s: %s", raw.ref.url, exc
                )
        return events
