"""Deterministic sponsor candidate extraction (``teams.sponsor_candidates``).

Sprint 013 ticket 003: the first, offline half of sponsor extraction.
There is no schema.org vocabulary for sponsorship, so
``extract/ladder.py``'s confidence-ranked ladder does not apply here --
sponsors have to be found heuristically. On a real robotics team site
they are typically a footer logo wall (``<img>`` ``alt``/``title`` text
or an outbound link to the sponsor's own domain), or a heading like
"Sponsors"/"Our Partners"/"Thank you to our sponsors" followed by a
list or grid of the same.

:func:`gather_sponsor_candidates` reduces one fetched page's HTML to a
short, bounded list of raw candidate *strings* -- never a whole page,
never a judgment about which candidate is a real sponsor. That
narrowing is sprint 013 ticket 004/005's job: an LLM call classifies
(selects from, never generates beyond) this candidate list, and
``sponsor_extract.py`` rejects, in code, any name the LLM returns that
is not verbatim in this function's own output. **This module is that
safety boundary's foundation** -- fabricating an unseen company is
structurally impossible downstream only because this pass never
invents a name either, it only lifts strings that were actually present
on the page (sprint.md's Design Rationale, "the deterministic
candidate-gathering pass is the actual security boundary, the LLM only
narrows within it").

Being the safety boundary cuts both ways: generous enough that a real
sponsor's name survives (a false negative here is unrecoverable -- nothing
downstream can find a name this pass never gathered), precise enough
that the list stays reviewable and the LLM stage isn't buried in noise.
A small, deterministic denylist (CMS/hosting vendors, aggregators/the
program itself, social platforms/generic utilities, nav boilerplate --
see :data:`_DENYLIST_TEXT`/:data:`_DENYLIST_DOMAINS`) drops the false
positives that are obvious without any page-specific context (the
team's own organization name is *not* one of these -- this function
never receives it, and excluding it is ticket 004's
``classify_sponsors()`` prompt's job instead, per SUC-004's Main Flow).

**Heading detection is intentionally broader than semantic ``<h1>``-
``<h6>`` tags.** A real, live-captured page fetched while building this
ticket (``ftc3650.org``, one of this module's own test fixtures) marks
its sponsor section with ``<p class="kicker">Sponsors</p>`` -- a
component-library convention with no semantic heading tag at all, not a
contrived edge case. Any element (except an interactive/non-container
tag -- ``<a>``, ``<img>``, ``<nav>``, ``<script>``, etc., see
:data:`_NEVER_HEADING_TAGS`) whose own rendered text is short (at most
:data:`_HEADING_TEXT_MAX_LEN` characters -- long enough for "Team
Spyder Thanks our Diamond and Platinum Sponsors" (54 chars), a real
fixture heading, short enough that a page's full body text can never
pass) and matches ``/sponsor|partner|thank/i`` is treated as a heading
trigger. An element nested anywhere inside a ``<nav>`` is never a
trigger, regardless of tag -- a "Our Sponsors" navigation link/list-item
pointing at a dedicated sponsors page is a menu entry, not a sponsor
name (and its own text, if it were an outbound link, would already be
filtered by the same-domain/denylist checks below; excluding it as a
*heading trigger* additionally keeps a nav's unrelated sibling menu
items out of the following-block scan entirely).

Uses ``lxml`` for HTML parsing, matching ``extract/ladder.py``'s and
``discovery/hub_scan.py``'s existing convention and dependency.
Malformed/unparseable HTML returns ``[]`` with a logged warning, never
raises -- the same precedent both of those modules already establish
for their own ``lxml.html.fromstring`` calls.

**Zero imports from ``fetch/``, ``enrich/``, ``adapters/``, or the
``anthropic`` SDK** -- this module is offline and LLM-free by
construction (sprint.md's "teams/ has zero edges into enrich/,
adapters/, normalize.run(), or pipeline.run()" invariant); the only
non-stdlib import is ``lxml.html`` itself.
"""

from __future__ import annotations

import logging
import re
from typing import Iterable
from urllib.parse import urljoin, urlparse

from lxml import html as lxml_html
from lxml.html import HtmlElement

logger = logging.getLogger(__name__)

#: The maximum number of candidates :func:`gather_sponsor_candidates`
#: returns for one page -- a short, bounded list, never the whole page.
#: Per the ticket's own instruction ("cap the result (e.g. 40
#: candidates)"); documented here as the one place this number is set.
MAX_CANDIDATES = 40

#: Matches a heading/label announcing a sponsor section in any of the
#: phrasings real team sites use ("Sponsors", "Our Partners", "Thank
#: You to Our Sponsors", "Thank you to our current sponsors.").
_SPONSOR_HEADING_RE = re.compile(r"sponsor|partner|thank", re.IGNORECASE)

#: A heading trigger's own rendered text must be no longer than this to
#: be treated as a short, label-like heading rather than a body-text
#: paragraph that happens to mention "sponsor" in passing. Comfortably
#: covers every real heading found while building this ticket's
#: fixtures (the longest, "Team Spyder Thanks our Diamond and Platinum
#: Sponsors", is 54 characters) while excluding ordinary prose.
_HEADING_TEXT_MAX_LEN = 60

#: Inline text-formatting tags a heading trigger's own text is allowed
#: to contain without disqualifying it (see :func:`_is_heading_trigger`).
#: Any other descendant tag -- ``<a>``, ``<img>``, ``<div>``,
#: ``<section>``, ``<p>``, ``<ul>``... -- means the candidate element is
#: a *container* wrapping real content, not a short label, and must not
#: be treated as a heading trigger (see that function's docstring for
#: why this matters: a container's aggregate text can still be short
#: when the container's real content is markup-heavy but text-light,
#: e.g. a logo wall of bare ``<img>`` tags with no ``alt`` text).
_INLINE_TEXT_TAGS = frozenset({"em", "strong", "b", "i", "span", "br", "small", "mark", "u"})

#: Genuine semantic heading tags -- the only tags :func:`_following_block`
#: treats as a hard stop when walking a heading trigger's following
#: siblings (see that function's docstring for why a non-semantic
#: trigger, e.g. a sibling "kicker"/subtitle paragraph that also
#: happens to match the sponsor regex, must *not* stop the walk).
_HEADING_STOP_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})

#: Tags that can never themselves be treated as a heading trigger, even
#: if their own text matches :data:`_SPONSOR_HEADING_RE` and is short
#: enough -- interactive/non-container elements (a link, an image, a
#: nav landmark, document metadata, form controls) whose text is either
#: candidate content itself (``a``/``img``) or navigation/boilerplate,
#: never a section label to scan the following content of.
_NEVER_HEADING_TAGS = frozenset(
    {
        "a",
        "img",
        "nav",
        "footer",
        "script",
        "style",
        "head",
        "title",
        "meta",
        "link",
        "iframe",
        "svg",
        "button",
        "input",
        "select",
        "option",
        "textarea",
        "noscript",
    }
)

#: CMS/hosting/site-builder vendor names -- never a sponsor, always the
#: platform the team's own site happens to be built on.
_DENYLIST_TEXT_CMS = {
    "wix",
    "weebly",
    "squarespace",
    "wordpress",
    "godaddy",
    "google sites",
    "canva",
    "blogspot",
    "hostinger",
}

#: The program itself and third-party aggregators of it -- always
#: present on a team site's page (nav links, footer credits, "powered
#: by" badges), never a sponsor.
_DENYLIST_TEXT_AGGREGATOR = {
    "first",
    "first inspires",
    "first robotics",
    "first robotics competition",
    "first tech challenge",
    "ftc",
    "frc",
    "fll",
    "the blue alliance",
    "tba",
    "ftcscout",
    "robotevents",
    "chief delphi",
}

#: Social platforms and generic donation/utility services -- real
#: companies, but never *this project's* notion of a sponsor when found
#: as a bare platform name (a team's actual corporate sponsor is
#: recovered by its own name/domain elsewhere on the page, not by the
#: social network it happens to post updates on).
_DENYLIST_TEXT_SOCIAL = {
    "facebook",
    "instagram",
    "youtube",
    "twitter",
    "x",
    "tiktok",
    "linkedin",
    "github",
    "paypal",
    "gofundme",
    "donorschoose",
    "donorschoose.org",
    "amazon smile",
    "amazonsmile",
}

#: Navigation and boilerplate text -- link/heading labels that are
#: structural furniture on nearly every site, never a company name.
_DENYLIST_TEXT_NAV = {
    "home",
    "contact",
    "contact us",
    "donate",
    "login",
    "log in",
    "sign in",
    "about",
    "about us",
    "menu",
    "search",
    "sponsors",
    "our sponsors",
    "sponsor us",
    "sponsorship",
    "sponsor",
    "partners",
    "our partners",
    "partner",
    "thank you",
    "become a sponsor",
}

#: The full text denylist, casefolded for comparison -- every candidate
#: string (heading-block or footer sourced alike) is checked against
#: this set before it can survive into the returned list. See the
#: module docstring for why this deterministic guard exists alongside,
#: not instead of, ticket 005's LLM classification and verbatim check.
_DENYLIST_TEXT = (
    _DENYLIST_TEXT_CMS | _DENYLIST_TEXT_AGGREGATOR | _DENYLIST_TEXT_SOCIAL | _DENYLIST_TEXT_NAV
)

#: Domains matching the same four categories above, checked against an
#: outbound footer/heading-block link's hostname (www-stripped,
#: lowercased) independently of the link's visible text.
_DENYLIST_DOMAINS = {
    # CMS/hosting/builder vendors
    "wix.com",
    "weebly.com",
    "squarespace.com",
    "wordpress.com",
    "godaddy.com",
    "sites.google.com",
    "canva.com",
    "blogspot.com",
    "hostinger.com",
    # Aggregators and the program itself
    "firstinspires.org",
    "thebluealliance.com",
    "ftcscout.org",
    "robotevents.com",
    "chiefdelphi.com",
    # Social platforms and generic utilities
    "facebook.com",
    "instagram.com",
    "youtube.com",
    "youtu.be",
    "twitter.com",
    "x.com",
    "tiktok.com",
    "linkedin.com",
    "github.com",
    "paypal.com",
    "gofundme.com",
    "donorschoose.org",
    "smile.amazon.com",
}

_WHITESPACE_RE = re.compile(r"\s+")


def _clean(text: str) -> str:
    """Collapse internal whitespace (newlines/tabs from HTML formatting)
    and strip the ends. Deliberately does *not* lowercase or strip
    punctuation -- the returned string must stay a verbatim, on-page
    display string, because ticket 005 validates the LLM's chosen
    sponsor names against this exact list.
    """
    return _WHITESPACE_RE.sub(" ", text).strip()


def _own_host(page_url: str) -> str:
    """``page_url``'s hostname, lowercased and with a leading ``www.``
    stripped -- the team's own site, excluded from outbound-link
    gathering and checked directly in the denylist (see
    :func:`_is_denylisted`).
    """
    host = (urlparse(page_url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _is_denylisted(candidate: str, own_host: str) -> bool:
    """Whether ``candidate`` (already :func:`_clean`-ed) is the team's
    own hostname or matches the text/domain denylist -- checked once,
    uniformly, over every candidate regardless of whether it came from
    an ``alt``/``title`` attribute, link text, or a link's hostname.
    """
    key = candidate.casefold()
    if not key:
        return True
    stripped = key[4:] if key.startswith("www.") else key
    if stripped == own_host:
        return True
    if key in _DENYLIST_TEXT:
        return True
    if stripped in _DENYLIST_DOMAINS:
        return True
    return False


def _following_block(heading: HtmlElement) -> list[HtmlElement]:
    """The element(s) immediately following ``heading`` that make up its
    "block" -- the sibling content a caption/label heading actually
    introduces.

    Walks ``heading``'s own following siblings within its immediate
    parent; if there are none (the heading is its parent's last child --
    common when a heading-wrapper element is itself wrapped alongside a
    separate content sibling one level up), climbs to the parent and
    retries from there. Once a non-empty following-sibling run is found,
    collects it up to (but not including) the next **genuine semantic**
    heading tag (:data:`_HEADING_STOP_TAGS`) -- deliberately *not* the
    same broadened definition used to detect ``heading`` itself, because
    a real captured page (this ticket's ``ftc3650.org`` fixture) places
    a second, non-semantic sponsor-regex match (a "Thank you to our
    current sponsors." subtitle paragraph) as an immediate sibling of
    the actual "Sponsors" label, one step before the real content
    (the logo row) -- stopping there would discard the content this
    function exists to find.
    """
    node: HtmlElement = heading
    while True:
        parent = node.getparent()
        if parent is None:
            return []
        siblings = [el for el in parent if isinstance(el.tag, str)]
        try:
            idx = siblings.index(node)
        except ValueError:
            return []
        rest = siblings[idx + 1 :]
        if rest:
            block: list[HtmlElement] = []
            for sibling in rest:
                if sibling.tag.lower() in _HEADING_STOP_TAGS:
                    break
                block.append(sibling)
            return block
        node = parent


def _is_heading_trigger(el: HtmlElement) -> bool:
    """Whether ``el`` is a sponsor-heading trigger: not one of
    :data:`_NEVER_HEADING_TAGS`, not nested inside a ``<nav>`` landmark
    (a "Our Sponsors" menu entry is navigation, not a section label --
    see the module docstring), contains no descendant element other
    than plain inline text formatting (:data:`_INLINE_TEXT_TAGS` -- see
    that set's docstring for why a *container* must never qualify, only
    a genuinely short label), and its own rendered text is short
    (:data:`_HEADING_TEXT_MAX_LEN`) and matches
    :data:`_SPONSOR_HEADING_RE`.
    """
    if not isinstance(el.tag, str) or el.tag.lower() in _NEVER_HEADING_TAGS:
        return False
    for descendant in el.iterdescendants():
        if isinstance(descendant.tag, str) and descendant.tag.lower() not in _INLINE_TEXT_TAGS:
            return False
    for ancestor in el.iterancestors():
        if isinstance(ancestor.tag, str) and ancestor.tag.lower() == "nav":
            return False
    text = (el.text_content() or "").strip()
    if not text or len(text) > _HEADING_TEXT_MAX_LEN:
        return False
    return bool(_SPONSOR_HEADING_RE.search(text))


def _collect(elements: Iterable[HtmlElement], page_url: str) -> list[str]:
    """Raw (uncleaned, un-denylisted) candidate strings from every
    ``<img>`` (``alt``/``title``) and outbound ``<a href>`` (link
    text/hostname) found in or under any element in ``elements``.

    An anchor whose resolved absolute URL is not ``http``/``https``, or
    whose hostname matches the page's own (``page_url``'s), contributes
    nothing -- only an *outbound* link's text/hostname is a sponsor
    signal (the ticket's own framing: "outbound links to the sponsor's
    own domain"); an internal navigation link is never a sponsor.
    """
    own_host = _own_host(page_url)
    found: list[str] = []
    for root in elements:
        for img in root.iter("img"):
            alt = (img.get("alt") or "").strip()
            title = (img.get("title") or "").strip()
            if alt:
                found.append(alt)
            if title and title.casefold() != alt.casefold():
                found.append(title)

        for anchor in root.iter("a"):
            href = (anchor.get("href") or "").strip()
            if not href:
                continue
            absolute = urljoin(page_url, href)
            parsed = urlparse(absolute)
            if parsed.scheme not in ("http", "https"):
                continue
            host = (parsed.hostname or "").lower()
            host = host[4:] if host.startswith("www.") else host
            if not host or host == own_host:
                continue
            text = (anchor.text_content() or "").strip()
            if text:
                found.append(text)
            found.append(host)
    return found


def gather_sponsor_candidates(html: str, page_url: str) -> list[str]:
    """Gather raw sponsor-name candidate strings from one fetched page.

    Two independent signals are collected, matching SUC-003's Main Flow:

    1. Every heading trigger (see :func:`_is_heading_trigger`, and the
       module docstring for why this is broader than ``<h1>``-``<h6>``)
       contributes its :func:`_following_block`'s ``<img>``
       ``alt``/``title`` text and outbound ``<a>`` link text/hostname.
    2. Every ``<footer>`` element on the page (wherever it appears, with
       or without a nearby matching heading) independently contributes
       the same signals from its own full subtree.

    Candidates are then, in discovery order: whitespace-cleaned
    (:func:`_clean`), checked against the team's own hostname and the
    CMS/aggregator/social/nav-boilerplate denylist
    (:func:`_is_denylisted`), deduplicated case-insensitively, and
    capped at :data:`MAX_CANDIDATES`.

    A page with no matching heading and no ``<footer>`` signal -- the
    normal case for most team pages -- returns ``[]``, which is the
    cost-control gate that keeps ticket 004/005's LLM stage from ever
    being called on a page with nothing to look at.

    Malformed/unparseable HTML returns ``[]`` with a logged warning,
    never raises -- matching ``extract/ladder.py``'s and
    ``discovery/hub_scan.py``'s own ``lxml.html.fromstring`` precedent.
    """
    try:
        tree = lxml_html.fromstring(html)
    except Exception:
        logger.warning("Could not parse HTML for %s; no sponsor candidates gathered", page_url)
        return []

    raw: list[str] = []

    for el in tree.iter():
        if _is_heading_trigger(el):
            raw.extend(_collect(_following_block(el), page_url))

    for footer in tree.iter("footer"):
        raw.extend(_collect([footer], page_url))

    own_host = _own_host(page_url)
    candidates: list[str] = []
    seen: set[str] = set()
    for item in raw:
        cleaned = _clean(item)
        if not cleaned or _is_denylisted(cleaned, own_host):
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        candidates.append(cleaned)
        if len(candidates) >= MAX_CANDIDATES:
            break

    return candidates
