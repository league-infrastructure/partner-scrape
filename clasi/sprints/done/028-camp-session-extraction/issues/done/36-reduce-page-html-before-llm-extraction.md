---
status: done
sprint: 028
tickets:
- 028-001
- 028-002
---

# Reduce page HTML to text before LLM extraction

## Description

Sprint 027's program-page extractor sends `raw.body` to the LLM
verbatim, with no HTML-to-text reduction step. Two verified failures
came out of that during sprint 027:

- **sdfoundation.org** — every page probed measured 840KB-965KB of raw
  HTML (site-wide template bloat, not one bad page). The registered
  SD Foundation Community Scholarship source raised
  `anthropic.BadRequestError: prompt is too long: 600199 tokens >
  200000 maximum` and had to be registered `enabled = false`
  (`registry/sources/sd-foundation-community-scholarship.toml`).
- **www.rmtlacademy.org** (a UCSD Summer Program Finder card, 612KB)
  hit the same limit. Ticket 027-006 made the per-card LLM call
  fail-open so one oversized card no longer aborts a whole listing
  source, but the card itself still yields nothing.

Sprints 029 (competition pages) and 030 (educator program pages) reuse
the same extraction path, so this will keep recurring — and every
oversized page we *do* fit is paying for boilerplate tokens.

## Proposed fix

A reduction step between fetch and the LLM call in
`partner_scrape/adapters/program_page.py` (`_extract_one_program` /
`_extract_many_programs`): strip script/style/nav/footer, collapse to
readable text, and cap length with a documented truncation strategy
that keeps the main content region. Reuse whatever the existing
`extract/` module already does for this if it fits, rather than adding
a second HTML-reduction path.

Re-enable `sd-foundation-community-scholarship` once it lands, and
re-check the UCSD cards that currently extract nothing.

## Verification

- Unit: a saved 900KB fixture page reduces below the model's context
  limit and still yields the correct program fields via
  `FixtureProgramLLMClient`.
- The SD Foundation source is `enabled = true` and live-verified.
