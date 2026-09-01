---
id: '002'
title: Deterministic description content gathering
status: open
use-cases:
- SUC-022
depends-on: []
github-issue: ''
issue: 44-team-website-links-and-descriptions.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Deterministic description content gathering

## Description

This ticket builds the first, offline half of description extraction —
mirroring `teams/sponsor_candidates.py`'s role in sponsor extraction
(sprint 013), but adapted to gathering summarizable prose instead of
sponsor-name candidates. Nothing in this ticket calls an LLM or the
network; it works entirely on HTML already fetched by the existing
`teams.scrape.verify_team_websites()` stage.

`teams.description_candidates.gather_description_content(html: str,
page_url: str) -> str` parses one team's already-fetched homepage and
returns a single **bounded** content string suitable for summarization —
never the raw page, never anything close to it. Priority order: the
`<meta name="description">` tag's content if present (the strongest,
most deliberate signal a site author left); the `<title>` tag; then
heading (`h1`-`h3`) and paragraph body text, in document order, until a
fixed character budget is reached. A page with nothing extractable (a
parked-domain placeholder, a pure-JS shell with no server-rendered text,
a single-image homepage) returns an empty string — the same cost-control
gate `sponsor_candidates.gather_sponsor_candidates()`'s empty-list return
already provides for the sponsor pipeline: an empty result here means
ticket 004's orchestration never reaches the cache or the LLM for that
team at all.

**No multi-page crawl.** This ticket operates on the single homepage
HTML already in `fetch_results` — no new fetch, no dedicated "/about"
page discovery. This keeps the sprint's scope tight (see sprint.md's
Scope, Out of Scope) and matches the issue's own framing that the fetch
machinery already exists and should be reused as-is.

**No-email guard, layer 1 of 3.** Before the gathered content is
returned, strip any substring matching an email-address pattern. This is
the first of three independent layers this sprint's design calls for
(the other two — a prompt instruction and a code-level rejection of the
LLM's output — land in tickets 003/004); layering here means a scraped
page's "Contact: coach@school.edu" line never even reaches the LLM's
input, regardless of what the model would have done with it.

## Acceptance Criteria

- [ ] `gather_description_content(html, page_url)` returns content that
      includes a page's `<meta name="description">` tag content when
      present.
- [ ] A page with no meta description but a title and headings still
      returns usable bounded content (title/heading/body text).
- [ ] A page whose body text contains an email address in prose (e.g.
      "Contact us at team1234@school.org for more info") returns content
      with that address stripped — a dedicated, explicit test for this,
      not incidental coverage.
- [ ] A page with no extractable content (parked-domain placeholder,
      pure-JS shell) returns an empty string.
- [ ] Malformed/unparseable HTML returns an empty string with a logged
      warning, never raises — matching
      `sponsor_candidates.gather_sponsor_candidates()`'s existing
      precedent exactly.
- [ ] The returned content never exceeds a documented, named character
      cap (a module-level constant, mirroring
      `sponsor_candidates.MAX_CANDIDATES`'s convention of a single named
      constant, not a magic number).
- [ ] Fixtures are captured from or representative of real team-site HTML
      shapes, not hand-authored approximations — matching this project's
      own sprint 011 ticket-011-003 lesson (already on record: a
      hand-authored fixture silently passed every unit test while the
      real pipeline had a real defect).

## Implementation Plan

**Approach**: New module, `partner_scrape/teams/description_candidates.py`,
using `lxml.html` for parsing (matching
`sponsor_candidates.py`'s/`extract/ladder.py`'s/`discovery/hub_scan.py`'s
existing dependency and convention — no new parsing library). Zero
imports from `fetch/`, `enrich/`, `adapters/`, or the `anthropic` SDK —
this module is offline and LLM-free by construction, matching
`sponsor_candidates.py`'s own stated invariant.

**Files to create/modify**:
- `partner_scrape/teams/description_candidates.py` (new) —
  `gather_description_content()`, a module-level `MAX_CONTENT_CHARS`
  constant, and a local email-address regex used for the layer-1 strip.
- `tests/teams/test_description_candidates.py` (new) — fixture-driven
  tests per Acceptance Criteria, mirroring
  `tests/teams/test_sponsor_candidates.py`'s structure.
- `tests/fixtures/teams/` — new small HTML fixture files (meta
  description present, meta description absent but headings present, an
  email embedded in body prose, no extractable content).

**Testing plan**: see Acceptance Criteria. Entirely hermetic — no
network, no LLM, no cache. Fixtures should be captured from real,
representative team-site HTML where feasible (matching this ticket's own
stated lesson), not fabricated from scratch.

**Documentation updates**: module docstring explaining the mirror-not-
import relationship to `sponsor_candidates.py`, the bounded-content
contract, and the layer-1 no-email scrub — matching the level of detail
`sponsor_candidates.py`'s own docstring sets.

## Testing

- **Existing tests to run**: `uv run pytest tests/teams/` (confirm no
  regression to sibling modules).
- **New tests to write**: `tests/teams/test_description_candidates.py`
  per Acceptance Criteria above.
- **Verification command**: `uv run pytest`
