---
id: '002'
title: Rework Opportunity.slug to a stable, partner-scoped cross-run identity
status: done
use-cases:
- SUC-004
depends-on:
- '001'
github-issue: ''
issue: 15-publish-complete-self-describing-data-export.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Rework Opportunity.slug to a stable, partner-scoped cross-run identity

## Description

Issue 15's persistent per-partner log (tickets 003+) needs a way to
recognize "this is the same event as last run, possibly updated" across
separate pipeline invocations. Today's `Opportunity.slug`
(`org[:40]_title[:60]_date`, all truncated) was only ever designed to
be unique *within one export snapshot* — `export/writer.py` already
carries a defensive collision pass (`_dedupe_slugs`) because truncation
can still collide, a known, documented limitation.

This ticket reworks `Opportunity.slug`'s algorithm to the cross-run
identity rule issue 15 defines: prefer `slugify(link)` when the
Opportunity's `link` (`registration_url` or `url`) is non-empty (a
per-event link is the strongest identity — it survives content edits);
otherwise `slugify(title) + "_" + <date>`. No org/partner prefix is
included, because slugs are now computed and will be stored *inside* a
partner-scoped directory (ticket 003) — the partner is already implied
by where the slug lives.

This is a genuine behavior change to `Opportunity.slug`'s *values*
(not its presence or type), which is judged safe: `opportunities.json`
is overwritten every run and no cross-run slug stability was ever
promised for it. See `design/normalize-DESIGN.md` for the full
rationale, including the accepted "shared listing page" edge case this
rule does not solve.

## Acceptance Criteria

- [x] A shared `slugify(text: str) -> str` function is promoted to
      `model.py` (moved from `normalize/run.py`'s private `_slugify`,
      behavior unchanged) — the single home for this primitive, reused
      by both the event slug (here) and the partner slug (ticket 003).
- [x] `normalize/run.py`'s `_to_opportunity` slug computation is
      replaced: `slugify(link)` when `link` is non-empty, else
      `slugify(title) + "_" + <event.start.date() or instance.last_seen,
      formatted the same way _date_slug_part already does>`.
- [x] No organization/partner name is included in the new slug.
- [x] `export/writer.py`'s existing `_dedupe_slugs` defensive pass is
      **unchanged** — it remains the backstop for the flat legacy
      export's cross-partner collision case.
- [x] Existing `normalize/run.py` and `export/writer.py` tests are
      updated for the new slug shape; no test asserts the old
      org-prefixed shape.
- [x] A test confirms two different partners' same-titled,
      same-day events (no link) now share the same *slug string*
      pre-dedup (since the org prefix is gone) but are still
      disambiguated in the flat legacy export's output by
      `_dedupe_slugs`'s numeric-suffix pass.

## Implementation Plan

**Approach**: A focused, isolated rework of one function's algorithm
plus a small promotion of a private helper to a shared module. No new
files, no new external behavior beyond the slug values themselves.

**Files to modify**:
- `partner_scrape/model.py` — add the promoted `slugify()` function.
- `partner_scrape/normalize/run.py` — remove the private `_slugify`
  (or delegate it to `model.slugify`, then remove once callers are
  updated); replace the slug construction in `_to_opportunity` with the
  new link-first/title+date rule.

**No files to create.**

## Testing

- **Existing tests to run**: `uv run pytest`, with particular attention
  to `tests/` for `normalize/run.py` and `export/writer.py` (both
  reference concrete slug values in fixtures/assertions today).
- **New tests to write**:
  - `model.py`'s test module (or a new small one if none exists yet):
    `slugify()` unit tests (lowercasing, punctuation stripping,
    whitespace collapse — matching the previous `_slugify`'s behavior
    exactly, just relocated).
  - `normalize/run.py`'s test module: link-present branch produces
    `slugify(link)`; link-absent branch produces `slugify(title) +
    date`; no org prefix in either case.
  - `export/writer.py`'s test module: confirm `_dedupe_slugs` still
    disambiguates a same-slug collision (now more likely to arise from
    the title+date fallback across partners than from truncation).
- **Verification command**: `uv run pytest`

## Documentation updates

None beyond this sprint's `design/normalize-DESIGN.md` and root
`design/DESIGN.md` overlays (already written).
