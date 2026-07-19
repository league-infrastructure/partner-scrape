"""Hub Scan: lead-generation discovery over one curated external hub.

See sprint.md's Architecture > Hub Scan, SUC-001, and the Design
Rationale ("Hub scanning is structurally separate from the Event/
Opportunity pipeline") -- the stakeholder was emphatic that we are the
aggregator; another aggregator's own records (a hub's own event listing)
must never become our data. This module enforces that structurally, not
just by convention:

- :func:`scan_hub` returns :class:`OrgCandidate` records only -- an org
  name, its *own* site URL, and a snippet of evidence text. It never
  constructs a :class:`partner_scrape.model.Event`.
- It never imports or calls anything in ``partner_scrape.normalize`` or
  ``partner_scrape.export`` -- a hub's own content can structurally never
  reach ``normalize.run()``/``export_opportunities()`` through this
  module, so ``opportunities.json`` can never be written from a hub scan
  no matter what a future caller does.
- The only exception is ``normalize.partners.normalize_org_name``, reused
  read-only for the dedup comparison below -- a pure string-normalization
  helper with no I/O and no Event/Opportunity concept, not a boundary
  this ticket's "never republish" guarantee is about.

This module depends only on ``Fetch & Cache``'s ``Fetcher`` protocol and
``fetch.robots.is_allowed`` (for per-page robots.txt compliance),
``registry.hub_schema.HubConfig``, and the Source Registry's own public
loader (``registry.loader.load_sources``) for the dedup check below --
never the ``Adapter`` protocol, dispatch table, or ``model.Event``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

from lxml import html as lxml_html

from partner_scrape.fetch import DEFAULT_USER_AGENT, Fetcher, is_allowed
from partner_scrape.fetch.cache import domain_of
from partner_scrape.normalize.partners import normalize_org_name
from partner_scrape.registry.hub_schema import HubConfig
from partner_scrape.registry.loader import load_sources

logger = logging.getLogger(__name__)


@dataclass
class OrgCandidate:
    """One organization observed on a hub's page(s), not yet a Source.

    Deliberately carries only lead-generation data -- the org's own
    (candidate) site URL and a snippet of hub-observed evidence text --
    never anything shaped like a real ``Event``. Ticket 004's Candidate
    Pipeline is what turns this into a review-queue stub; this module
    never persists it anywhere.
    """

    org_name: str
    candidate_url: str
    evidence_text: str
    hub_id: str


def _known_domains_and_names(sources_dir: Path | None) -> tuple[set[str], set[str]]:
    """Domains and normalized org names already covered by the Source
    Registry, for the dedup check in :func:`scan_hub`.

    Calls ``registry.load_sources()`` (the Registry's own public loader)
    rather than re-parsing ``registry/sources/*.toml`` directly, per
    sprint.md's Design Quality self-review note on avoiding feature envy
    into the Registry's own concern. Uses ``load_sources`` (not
    ``load_active_sources``) so a disabled source's org is still treated
    as covered -- a disabled source is a data pause, not evidence the org
    itself is unknown.
    """
    domains: set[str] = set()
    names: set[str] = set()
    for source in load_sources(sources_dir):
        names.add(normalize_org_name(source.org_name))
        for key in ("site_url", "api_base"):
            value = source.config.get(key)
            if value:
                domains.add(domain_of(value))
    return domains, names


def _block_text(anchor) -> str:
    """The text of ``anchor``'s containing block element, or the
    anchor's own text if it has no parent -- the "nearby text" evidence
    signal, mirroring ``discovery/listing.py``'s anchor-extraction
    approach of pairing a link with its surrounding context.
    """
    parent = anchor.getparent()
    if parent is None:
        return (anchor.text_content() or "").strip()
    return (parent.text_content() or "").strip()


def _extract_candidates(body: str, page_url: str, hub_id: str) -> list[OrgCandidate]:
    """Extract one :class:`OrgCandidate` per outbound (different-domain)
    ``<a href>`` on ``body``, a page fetched from ``page_url``.

    A link's own visible text is the best-effort ``org_name`` guess (a
    hub page conventionally names the org right in the anchor, e.g.
    "Presented by <a href='...'>Org Name</a>"); its containing block's
    full text is the ``evidence_text``. A link with no usable text (and
    no ``title`` attribute) is skipped -- an unnamed link is not a usable
    lead. Malformed/unparseable HTML yields an empty list (with a logged
    warning) rather than raising, matching ``discovery/listing.py``'s own
    ``lxml.html.fromstring`` error handling.
    """
    try:
        tree = lxml_html.fromstring(body)
    except Exception:
        logger.warning("Hub page %s is not parseable HTML; skipping", page_url)
        return []

    page_domain = domain_of(page_url)
    seen: dict[str, None] = {}
    candidates: list[OrgCandidate] = []

    for anchor in tree.xpath("//a[@href]"):
        href = (anchor.get("href") or "").strip()
        if not href:
            continue
        absolute = urljoin(page_url, href)
        if urlparse(absolute).scheme not in ("http", "https"):
            continue
        link_domain = domain_of(absolute)
        if not link_domain or link_domain == page_domain:
            continue
        if absolute in seen:
            continue
        seen[absolute] = None

        org_name = (anchor.text_content() or "").strip() or (anchor.get("title") or "").strip()
        if not org_name:
            continue

        candidates.append(
            OrgCandidate(
                org_name=org_name,
                candidate_url=absolute,
                evidence_text=_block_text(anchor),
                hub_id=hub_id,
            )
        )
    return candidates


def scan_hub(
    hub: HubConfig,
    fetcher: Fetcher,
    *,
    sources_dir: Path | None = None,
    user_agent: str = DEFAULT_USER_AGENT,
) -> list[OrgCandidate]:
    """Scan ``hub``'s configured page(s) for candidate organizations not
    already covered by the Source Registry.

    For each of ``hub.page_urls``: skip it (logged) if robots.txt
    disallows it for ``user_agent``; otherwise fetch it via ``fetcher``
    and extract every outbound (different-domain) link, with nearby
    evidence text, as a candidate. A non-200 response is logged and
    skipped -- per-page isolation, matching
    ``discovery/listing.py``'s ``discover_via_listing``.

    Every candidate is then filtered against the Source Registry: one
    whose domain or ``normalize_org_name(org_name)`` already matches an
    existing :class:`~partner_scrape.registry.schema.SourceConfig` is
    dropped, never returned. ``sources_dir`` overrides the registry
    directory checked (defaults to the real
    ``registry.loader.DEFAULT_SOURCES_DIR`` when omitted) -- tests pass a
    fixture directory.

    This function produces candidates only: it never filters by
    relevance (ticket 004's job) and never persists anything (also
    ticket 004's job) -- a pure, offline-testable scan. It never
    constructs a ``partner_scrape.model.Event`` and never calls anything
    in ``normalize/`` (besides ``normalize_org_name``) or ``export/`` --
    see this module's docstring.
    """
    known_domains, known_names = _known_domains_and_names(sources_dir)

    raw_candidates: list[OrgCandidate] = []
    for page_url in hub.page_urls:
        if not is_allowed(page_url, fetcher, user_agent):
            logger.info(
                "Hub page %s disallowed by robots.txt for hub %r; skipping",
                page_url,
                hub.hub_id,
            )
            continue

        response = fetcher.get(page_url)
        if response.status != 200:
            logger.warning(
                "Hub page %s for hub %r returned status %s; skipping",
                page_url,
                hub.hub_id,
                response.status,
            )
            continue

        raw_candidates.extend(_extract_candidates(response.body, page_url, hub.hub_id))

    candidates: list[OrgCandidate] = []
    seen_urls: dict[str, None] = {}
    for candidate in raw_candidates:
        if candidate.candidate_url in seen_urls:
            continue
        seen_urls[candidate.candidate_url] = None

        if domain_of(candidate.candidate_url) in known_domains:
            continue
        if normalize_org_name(candidate.org_name) in known_names:
            continue

        candidates.append(candidate)

    return candidates
