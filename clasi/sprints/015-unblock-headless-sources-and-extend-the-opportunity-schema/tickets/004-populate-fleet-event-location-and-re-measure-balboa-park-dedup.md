---
id: '004'
title: Populate Fleet Event.location and re-measure Balboa Park dedup
status: open
use-cases:
- SUC-005
depends-on: []
github-issue: ''
issue: 38-acquisition-policy-threading-and-feed-robots.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Populate Fleet Event.location and re-measure Balboa Park dedup

## Description

Sprint 014 ticket 004 measured zero cross-source collapses between
`balboa-park` (park-wide TEC calendar) and the individually-registered
Balboa Park institutions, and root-caused it precisely: a genuine
title+date match exists (`"Educator Open House"`, both sides dated
2026-09-24), but `fleet-science-center.toml`'s `listing_html` adapter
never populates `Event.location` (empty string on every one of its raw
events), while Balboa Park's TEC record sets
`venue.venue = "Fleet Science Center"`.
`dedup.cross_source_identity()`'s third component
(`normalize_title(event.location)`) therefore differs (`""` vs. `"fleet
science center"`), blocking the merge even on an exact title+date hit.

Fleet's real detail pages carry no per-page venue markup for the
extraction ladder to recover (the venue is constant across every
event: 1875 El Prado) — this is a registry-configuration gap, not an
adapter bug that needs page-level extraction.

## Fix shape

Add a registry-generic fallback to `ListingHtmlAdapter.extract()`: if
the extraction ladder recovered no `location` field for an event, set
it from `source.config.get("default_location", "")`. This is not
Fleet-specific code — any current or future `listing_html` source with
a fixed, undocumented-on-page venue gets the same fix as a one-line
TOML edit (matches `registry/DESIGN.md`'s "onboarding is a data edit"
design point). Set
`fleet-science-center.toml`'s `config.default_location = "1875 El
Prado, San Diego, CA 92101"`.

Then re-run the same live measurement sprint 014 ticket 004 performed
(`balboa-park` alongside every individually-registered Balboa Park
institution, through the real adapters and `normalize.run()` directly)
and record the result, whatever it is — per that ticket's own "record
the result either way" framing.

## Acceptance Criteria

- [ ] `ListingHtmlAdapter.extract()` sets `Event.location` from
      `source.config.get("default_location", "")` only when the
      extraction ladder left `location` empty — never overriding a
      ladder-recovered value.
- [ ] A fixture test proves both branches: ladder recovers a location
      (fallback does not fire) and ladder recovers none (fallback
      fires).
- [ ] `fleet-science-center.toml` sets `config.default_location`.
- [ ] The Balboa Park ↔ Fleet dedup measurement is re-run live
      post-fix and its collapse count is recorded in this ticket's
      Notes, whatever the result — not silently omitted if still zero.
- [ ] No other `listing_html` source's behavior changes (no
      `default_location` key set for any source but Fleet this
      sprint).
- [ ] Full test suite stays green; the live re-measurement is a
      diagnosis step, not a committed test.

## Testing

- **Existing tests to run**: full suite (`uv run pytest`), especially
  `adapters/listing_html.py`'s existing test module.
- **New tests to write**: the two-branch fallback fixture test above.
- **Verification command**: `uv run pytest`. The Balboa Park
  re-measurement uses a live/staged script (matching sprint 014 ticket
  004's own precedent), not pytest.

## Implementation Plan

**Approach**: Small, adapter-generic fallback plus one TOML edit, then
a live re-measurement to close the loop sprint 014 opened.

**Files to modify**:
- `partner_scrape/adapters/listing_html.py` — the fallback.
- `partner_scrape/registry/sources/fleet-science-center.toml` —
  `config.default_location`.
- The corresponding `listing_html` test module — new fixture cases.

**Testing plan**: see Testing above.

**Documentation updates**: `partner_scrape/adapters/DESIGN.md` gets a
short sprint-015 addendum describing the `default_location` fallback
convention; `partner_scrape/normalize/DESIGN.md`'s existing sprint 014
Open Questions entry on the Balboa Park dedup limitation is updated
with this sprint's re-measured result.
