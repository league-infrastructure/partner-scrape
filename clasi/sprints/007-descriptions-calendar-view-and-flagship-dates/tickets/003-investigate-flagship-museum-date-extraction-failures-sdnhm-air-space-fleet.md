---
id: '003'
title: Investigate flagship museum date-extraction failures (SDNHM, Air & Space, Fleet)
status: open
use-cases: [SUC-003]
depends-on: []
github-issue: ''
issue: 14-flagship-museum-date-extraction.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Investigate flagship museum date-extraction failures (SDNHM, Air & Space, Fleet)

## Description

Implements the investigation half of issue
`14-flagship-museum-date-extraction.md` and sprint 007's SUC-003. This
ticket produces a **diagnosis only** — no production code changes are
expected (a throwaway/exploratory script is fine if it helps, but must
not be committed). Ticket 004 (depends on this one) implements the fix.

**Why a separate investigation ticket**: a live, read-only diagnostic
run during sprint planning (2026-07-20, `curl` against the real sites,
no code changes) found that "date extraction fails" is **not one
uniform cause** — see sprint.md's Problem section and Architecture
Design Rationale for full detail. Confirm or refute each hypothesis
below against the actual pipeline behavior (not just raw `curl`) before
ticket 004 picks a fix mechanism.

**Starting hypotheses** (from planning-time diagnostics — confirm these
against real pipeline runs, don't just trust them):

- **Air & Space Museum** (`partner_scrape/registry/sources/sandiego-air-space.toml`,
  `generic_html`): `sitemap.xml`, `sitemap_index.xml`, `sitemap-index.xml`,
  and `wp-sitemap.xml` all returned HTTP 200 with the site's homepage
  HTML (soft-404/catch-all), not real sitemap XML, in a planning-time
  check. `partner_scrape/discovery/sitemap.py`'s root-element validation
  (`_SITEMAP_ROOT_TAGS`, sprint 005 hardening) should reject all of
  these — confirm by running Discovery for this source with logging
  and checking whether it resolves any candidate URLs at all. If it
  resolves zero, this is a Discovery problem, not a ladder problem —
  check whether a real sitemap exists at a non-standard path, or
  whether this source should move to `listing_html` (mirroring
  `fleet-science-center.toml`) off a real `/events`-style page.
- **SDNHM** (`sdnhm.toml`, `generic_html`): its `sitemap.xml` is real
  (892 URLs at planning time) and surfaces `/calendar/...` pages
  matching `discovery/sitemap.py`'s `EVENT_PATH_RE` — consistent with
  the issue's "39 raw events found." A sampled page
  (`/calendar/summer-camp/`) was a program/category landing page (not a
  single dated event instance): no JSON-LD, two bare `<time>` tags of
  unconfirmed attribute format, and body text mixing a genuine upcoming
  date with unrelated older dates. Confirm which ladder rung (if any)
  fires on pages like this via `partner_scrape/extract/ladder.py`'s
  `extract_fields()`, and what value it produces — is the body-regex
  rung (`_extract_body_regex`, first date match within the first 3000
  characters) grabbing a wrong/stale date on this kind of multi-date
  page?
- **Fleet Science Center** (`fleet-science-center.toml`,
  `listing_html`): a sampled page (`/events/camps`) had 20 valid ISO
  `<time datetime="...">` tags with real future dates — which
  `_extract_time_tags` (rung 2) should already parse — contradicting
  this TOML's own comment that Fleet's detail pages "carry no JSON-LD
  or `<time>` markup." Confirm whether this page (and others like it)
  actually exports correctly today, and whether the other ~10
  discovered URLs (e.g. `/events/candlelight-concerts`, which had zero
  `<time>` tags at planning time) are genuinely undated evergreen
  program pages (correctly excluded) or need different handling.

**Method**: run the pipeline per-source with logging
(`uv run partner-scrape --source sdnhm --no-enrich --dry-run -v`,
substituting `sandiego-air-space` / `fleet-science-center`) and inspect
what Discovery resolves and what the ladder extracts. Add temporary
logging/prints as needed; do not leave debug scaffolding in committed
code.

## Acceptance Criteria

- [ ] For each of SDNHM, Air & Space, and Fleet, the "Findings" section
      below is filled in with: what Discovery actually resolves (URL
      count and whether they're real event/instance pages), what the
      ladder actually extracts (which rung fires, what value), and
      which fix mechanism applies — `fetch_strategy = "headless"`
      (JS-rendering hides the date from raw fetch), a Discovery
      config/pattern/adapter-type change (wrong or zero candidate
      URLs), a targeted ladder heuristic fix (wrong rung selection on a
      multi-date page), or "already correct, no fix needed."
- [ ] No production code is committed by this ticket (diagnosis only)
      — any exploratory script used is discarded, not committed.
- [ ] `uv run pytest` still passes (trivially — no production changes
      expected).

## Findings

*(Fill in during execution — one subsection per source. Do not leave
this as a placeholder when marking the ticket done.)*

### SDNHM
- Discovery result:
- Ladder result:
- Recommended fix mechanism:

### Air & Space Museum
- Discovery result:
- Ladder result:
- Recommended fix mechanism:

### Fleet Science Center
- Discovery result:
- Ladder result:
- Recommended fix mechanism:

## Testing

- **Existing tests to run**: `uv run pytest` (full suite, ~845 tests)
  — must still pass since no production code should change.
- **New tests to write**: none (investigation only).
- **Verification command**: `uv run pytest`.
- **Documentation**: the Findings section above *is* this ticket's
  deliverable — ticket 004 reads it directly, so fill it in
  concretely enough (actual counts, actual rung names, actual
  recommendation) that ticket 004 can start without re-investigating.
