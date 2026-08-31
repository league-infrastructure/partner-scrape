---
id: '004'
title: Populate Fleet Event.location and re-measure Balboa Park dedup
status: done
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

- [x] `ListingHtmlAdapter.extract()` sets `Event.location` from
      `source.config.get("default_location", "")` only when the
      extraction ladder left `location` empty — never overriding a
      ladder-recovered value.
- [x] A fixture test proves both branches: ladder recovers a location
      (fallback does not fire) and ladder recovers none (fallback
      fires).
- [x] `fleet-science-center.toml` sets `config.default_location`.
- [x] The Balboa Park ↔ Fleet dedup measurement is re-run live
      post-fix and its collapse count is recorded in this ticket's
      Notes, whatever the result — not silently omitted if still zero.
- [x] No other `listing_html` source's behavior changes (no
      `default_location` key set for any source but Fleet this
      sprint).
- [x] Full test suite stays green; the live re-measurement is a
      diagnosis step, not a committed test.

## Notes (ticket 004 completion, 2026-08-30)

**Fix implemented as designed.** `ListingHtmlAdapter.extract()`
(`partner_scrape/adapters/listing_html.py`) now sets `Event.location`
from `source.config.get("default_location", "")` when, after the
extraction ladder runs, `event.location` is still falsy — never
re-`set()`s a ladder-recovered value. Recorded at a new
`CONFIDENCE_DEFAULT_LOCATION = 1.0` (an operator-curated registry
value, not a ladder guess — trusted at the ladder's own top tier).
`fleet-science-center.toml` sets
`config.default_location = "1875 El Prado, San Diego, CA 92101"`. Only
Fleet's TOML gained the key; `sandiego-air-space.toml` (the only other
`listing_html` source) is untouched and was verified via `grep` to
still have no `default_location` key.

**Live re-measurement** (`balboa-park` + all 7 individually-registered
Balboa Park institutions, real adapters + `normalize.run()` directly,
script not committed). Fleet's `Event.location` is now confirmed
populated on all 10 raw events: `{'1875 El Prado, San Diego, CA
92101'}` — the fallback fires exactly as designed, no longer the
empty-string blocker sprint 014 measured. Full run: `balboa-park` 162,
`fleet-science-center` 10, `sdnhm` 39, `comic-con-museum` 0 (its TEC
endpoint timed out live during this run — transient, unrelated to this
fix), `japanese-friendship-garden` 2, `sandiego-air-space` 10,
`sdautomuseum` 17, `sdmrm` 1 events → 143 total Opportunities.

**Result: still 0 cross-source collapses.** Recorded honestly, per the
"record the result either way" convention. The specific "Educator Open
House" 2026-09-24 case sprint 014 root-caused is still present as two
separate records:

- `balboa-park`: `location = "Fleet Science Center, 1875 El Prado, San
  Diego, CA"`
- `fleet-science-center`: `location = "1875 El Prado, San Diego, CA
  92101"`

**Root cause has shifted, not disappeared.** The empty-vs-populated gap
this ticket targeted is closed — both sides now carry a real,
non-empty venue string for the same physical location. But
`dedup.cross_source_identity()`'s venue component is
`normalize_title(event.location)`, which only lowercases, strips
punctuation, and collapses whitespace (`model.normalize_title`,
confirmed by reading it, not guessed) — it does no address-level
canonicalization. `normalize_title("Fleet Science Center, 1875 El
Prado, San Diego, CA")` = `"fleet science center 1875 el prado san
diego ca"` versus `normalize_title("1875 El Prado, San Diego, CA
92101")` = `"1875 el prado san diego ca 92101"` — different strings
(one carries the org-name prefix and no ZIP, the other the reverse), so
the identity tuple still differs on its third component even though
the title (`"educator open house"`, both sides) and date
(`2026-09-24`, both sides) now match exactly.

**No scope creep into `normalize/` attempted**, per this ticket's own
instruction. Two options were considered and rejected as out of this
ticket's scope: (1) hand-tuning `default_location` to byte-match
Balboa Park's specific TEC venue string — rejected as coupling one
source's config to another source's arbitrary upstream formatting,
fragile the moment either changes, and not a fix any *other*
`listing_html` source with this same gap could reuse; (2) adding
address-level fuzzy/canonical matching to
`dedup.cross_source_identity()` — a real, more general fix, but a
`normalize/` change explicitly out of this ticket's scope. Both are
left for a future sprint if venue-string-format mismatches turn out to
be material at scale — the existing `normalize/DESIGN.md` Open
Questions entry is updated with this finding (see that file's Sprint
015 addendum).

**Full test suite**: 1511 passed (1508 baseline + 3 new fixture tests
in this ticket). No regressions.

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
