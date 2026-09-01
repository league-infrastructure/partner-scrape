"""Deterministic description content gathering (``teams.description_candidates``).

Sprint 021 ticket 002: the first, offline half of description extraction --
mirroring ``teams.sponsor_candidates``'s role in sponsor extraction
(sprint 013) in shape only, **never by import** (sprint.md's Architecture:
description extraction "mirrors sponsor extraction's module shape ...
never imports it"). Where sponsor extraction gathers a bounded *list* of
raw candidate names for an LLM to classify from, this module gathers a
single bounded *prose* string for an LLM to summarize -- SUC-022's Main
Flow, adapted from SUC-003's.

:func:`gather_description_content` reduces one fetched page's HTML to a
short, bounded content string -- never the whole page, never a judgment
about what the team "is." That narrowing (turning this text into an
actual sentence) is ticket 003/004's job: ``description_llm.py``'s
client is constrained to *summarizing* exactly this string, never
generating from open context (mirroring ``sponsor_llm.py``'s
classify-don't-generate contract, adapted to summarize-don't-generate).

**Priority order, per SUC-022's Main Flow step 2**: the
``<meta name="description">`` tag's ``content`` attribute (the
strongest, most deliberate signal a site author left -- if a team
explicitly wrote a one-line summary of themselves, nothing gathered
afterward should crowd it out); the ``<title>`` tag; then every
``<h1>``-``<h3>`` heading and ``<p>`` paragraph's text, in document
order. These are concatenated as independent pieces (not a fallback
chain -- a page with both a meta description *and* headings surfaces
all of it, per SUC-022's own Acceptance Criteria wording "returns
content that includes it") and the combined string is hard-capped at
:data:`MAX_CONTENT_CHARS`. A page contributing none of the above (a
parked-domain placeholder, a pure-JS shell with no server-rendered text,
a single-image homepage) returns ``""`` -- the same cost-control gate
``sponsor_candidates.gather_sponsor_candidates()``'s empty-list return
already provides for the sponsor pipeline: ticket 004's orchestration
never reaches the cache or the LLM for a team whose gathered content is
empty (SUC-022's Postconditions).

**No multi-page crawl.** This function parses one already-fetched
homepage's HTML -- the same ``fetch_results`` entry
``verify_team_websites()``/``extract_sponsors()`` already produce and
consume (sprint.md's Design Rationale: "no second fetch"). No dedicated
"/about" page discovery, no sitemap walk -- out of this sprint's Scope.

**No-email guard, layer 1 of 3** (sprint.md's Design Rationale, "the
no-email guard is layered three ways"). Before the gathered content is
returned, every email-address-shaped substring is stripped
(:func:`_strip_emails`, using :data:`_EMAIL_RE`). This is the first of
three independent layers this sprint's design calls for -- a prompt
instruction (ticket 003) and a code-level rejection of the LLM's raw
output (ticket 004) are the other two -- so a scraped page's
"Contact: coach@school.edu" line never even reaches the LLM's input,
regardless of what the model would have done with it.
:data:`_EMAIL_RE` is an independent copy of
``tests/teams/test_export.py``'s own ``_EMAIL_PATTERN`` (same pattern,
kept duplicated rather than imported -- production code must never
depend on test code) so every layer of the guard rejects the same shape
of string.

Uses ``lxml`` for HTML parsing, matching ``sponsor_candidates.py``'s/
``extract/ladder.py``'s/``discovery/hub_scan.py``'s existing convention
and dependency. Malformed/unparseable HTML returns ``""`` with a logged
warning, never raises -- the same precedent all three of those modules
already establish for their own ``lxml.html.fromstring`` calls.

**Zero imports from ``fetch/``, ``enrich/``, ``adapters/``, or the
``anthropic`` SDK** -- this module is offline and LLM-free by
construction (sprint.md's "teams/ has zero edges into enrich/,
adapters/, normalize.run(), or pipeline.run()" invariant, restated for
this sprint's new modules); the only non-stdlib import is ``lxml.html``
itself.
"""

from __future__ import annotations

import logging
import re

from lxml import html as lxml_html
from lxml.html import HtmlElement

logger = logging.getLogger(__name__)

#: The maximum length, in characters, of the content string
#: :func:`gather_description_content` returns -- a short, bounded
#: excerpt suitable as LLM summarization input, never the whole page.
#: Comfortably fits a meta description, a title, and several real
#: paragraphs (this ticket's own fixtures) while staying far short of a
#: full homepage's text. Documented here as the one place this number
#: is set, mirroring ``sponsor_candidates.MAX_CANDIDATES``'s convention
#: of a single named constant, not a magic number.
MAX_CONTENT_CHARS = 2000

#: Matches an email address anywhere in gathered text -- layer 1 of the
#: sprint's three-layer no-email guard (see the module docstring). An
#: independent copy of ``tests/teams/test_export.py``'s own
#: ``_EMAIL_PATTERN``, not an import of it (test code must never be a
#: runtime dependency of production code) -- kept textually identical so
#: every layer of the guard, and its own regression test, reject the
#: same shape of string.
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

_WHITESPACE_RE = re.compile(r"\s+")

#: Heading tags contributing to the body-text pass, per SUC-022's Main
#: Flow ("heading (h1-h3) ... text").
_HEADING_TAGS = frozenset({"h1", "h2", "h3"})

#: Every tag whose own text contributes to the body-text pass -- the
#: heading tags above, plus paragraphs (SUC-022's Main Flow: "heading
#: ... and body text"). Deliberately narrow: only these tags' *own*
#: rendered text is collected, so boilerplate living in a ``<script>``,
#: ``<style>``, or bare ``<div>`` never contributes (there is no
#: separate exclusion list to maintain -- anything not in this set is
#: silently never a source).
_BODY_TEXT_TAGS = _HEADING_TAGS | frozenset({"p"})


def _clean(text: str) -> str:
    """Collapse internal whitespace (newlines/tabs from HTML formatting)
    and strip the ends -- matches ``sponsor_candidates._clean``'s own
    behavior, kept as an independent copy for the same "never import
    across these mirrored modules" reason the module docstring states.
    """
    return _WHITESPACE_RE.sub(" ", text).strip()


def _strip_emails(text: str) -> str:
    """Layer 1 of 3 of the no-email guard (module docstring): remove
    every email-address-shaped substring from ``text``, then re-collapse
    the whitespace a removed address leaves behind.
    """
    stripped = _EMAIL_RE.sub("", text)
    return _clean(stripped)


def _meta_description(tree: HtmlElement) -> str:
    """The first ``<meta name="description" content="...">`` tag's
    (cleaned, non-empty) content found anywhere in ``tree``, or ``""``
    if none exists -- matches a real browser's own "first wins" behavior
    for a duplicated meta tag, the same convention :func:`_title` uses
    below for a duplicated ``<title>``.
    """
    for meta in tree.iter("meta"):
        name = (meta.get("name") or "").strip().lower()
        if name != "description":
            continue
        content = _clean(meta.get("content") or "")
        if content:
            return content
    return ""


def _title(tree: HtmlElement) -> str:
    """The first non-empty ``<title>`` tag's text found anywhere in
    ``tree``. A real captured page in this ticket's own fixture corpus
    (``sponsor_page_gearup12499_heading.html``, reused here) has *two*
    ``<title>`` tags in its ``<head>`` -- picking the first, matching how
    a real browser resolves the duplicate, rather than raising or
    concatenating both.
    """
    for title_el in tree.iter("title"):
        text = _clean(title_el.text_content() or "")
        if text:
            return text
    return ""


def _body_text_pieces(tree: HtmlElement) -> list[str]:
    """Every ``<h1>``-``<h3>`` and ``<p>`` element's own text, in
    document order, each cleaned and de-blanked -- SUC-022's Main Flow's
    final priority tier. Scoped to ``<body>`` when one exists (falling
    back to the whole tree for a bare, wrapper-less fragment) purely to
    avoid re-collecting a ``<head>``-only tag; heading/paragraph tags
    never legitimately appear in ``<head>`` regardless.
    """
    pieces: list[str] = []
    body = tree.find(".//body")
    root = body if body is not None else tree
    for el in root.iter():
        if not isinstance(el.tag, str) or el.tag.lower() not in _BODY_TEXT_TAGS:
            continue
        text = _clean(el.text_content() or "")
        if text:
            pieces.append(text)
    return pieces


def gather_description_content(html: str, page_url: str) -> str:
    """Gather a single, bounded, summarizable content string from one
    fetched team homepage.

    Three signals are gathered, in the priority order SUC-022's Main
    Flow specifies, and concatenated (not chained as a fallback -- a
    page carrying all three contributes all three, per this function's
    own Acceptance Criteria: "returns content that includes" the meta
    description "when present," not "returns only" it):

    1. :func:`_meta_description` -- the ``<meta name="description">``
       tag's content, the strongest signal a site author deliberately
       left.
    2. :func:`_title` -- the ``<title>`` tag's text.
    3. :func:`_body_text_pieces` -- every ``<h1>``-``<h3>``/``<p>``
       element's own text, in document order.

    The joined result is passed through :func:`_strip_emails` (layer 1
    of the module docstring's three-layer no-email guard) *before* the
    :data:`MAX_CONTENT_CHARS` cap is applied -- stripping first, capping
    second, so a hard character cut can never leave a truncated,
    partially-stripped email fragment behind (the cap only ever removes
    already-clean trailing text, never creates a new email-shaped
    substring).

    A page contributing none of the three signals -- a parked-domain
    placeholder, a pure-JS shell with no server-rendered text, a
    single-image homepage -- returns ``""``, which is the cost-control
    gate that keeps ticket 004's orchestration from ever reaching the
    cache or the LLM for that team's page at all (SUC-022's
    Postconditions).

    Malformed/unparseable HTML returns ``""`` with a logged warning,
    never raises -- matching ``sponsor_candidates.gather_sponsor_candidates()``'s
    own ``lxml.html.fromstring`` precedent exactly (SUC-022's Error Flows).
    """
    try:
        tree = lxml_html.fromstring(html)
    except Exception:
        logger.warning("Could not parse HTML for %s; no description content gathered", page_url)
        return ""

    pieces: list[str] = []

    meta_desc = _meta_description(tree)
    if meta_desc:
        pieces.append(meta_desc)

    title = _title(tree)
    if title:
        pieces.append(title)

    pieces.extend(_body_text_pieces(tree))

    content = _strip_emails(" ".join(pieces))
    return content[:MAX_CONTENT_CHARS]
