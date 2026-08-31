---
id: '003'
title: Address-aware venue canonicalization for cross-source dedup
status: done
use-cases:
- SUC-004
- SUC-005
depends-on: []
github-issue: ''
issue: 39-venue-canonicalization-for-cross-source-dedup.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Address-aware venue canonicalization for cross-source dedup

## Description

Sprint 015 ticket 004 re-measured Balboa Park ↔ Fleet live after fixing
the empty-`Event.location` gap: still 0 cross-source collapses. Root
cause is now precise:
`dedup.cross_source_identity()`'s venue component is
`normalize_title(event.location)`, which only lowercases, strips
punctuation, and collapses whitespace — it does no address-level
canonicalization, so
`"Fleet Science Center, 1875 El Prado, San Diego, CA"` (Balboa Park's
TEC record for the same event) and
`"1875 El Prado, San Diego, CA 92101"` (Fleet's own `default_location`)
normalize to two different strings for the same physical address.

This ticket adds a new `dedup.normalize_venue(location: str) -> str`
helper, used only by `cross_source_identity()`'s third tuple component,
per `sprint.md`'s Architecture > Design Rationale ("Venue
canonicalization is a conservative token-match, not a general address
parser, and lives in `dedup.py`, not `model.py`" — read that section
before implementing; it also documents the exact reasoning for why the
function requires a comma-delimited "street, city, state zip" shape and
falls back to today's `normalize_title` behavior otherwise, which is
the precise contract this ticket must implement, not a looser
approximation of it).

## Acceptance Criteria

- [x] `dedup.normalize_venue(location: str) -> str` splits `location`
      on commas and looks for a segment whose stripped text matches
      `^\d+\s+\S` (a leading street number followed by a street name);
      if found, that segment alone — normalized via
      `model.normalize_title`'s existing
      lowercase/strip-punctuation/collapse-whitespace rule — is
      returned as the venue token.
- [x] If no comma-delimited segment matches that shape (including a
      location string with no comma at all), `normalize_venue()`
      returns `normalize_title(location)` unchanged — today's exact
      behavior. A comma-less string must never be treated as a single
      street-address segment even if it starts with a digit (this
      would risk swallowing city/state/ZIP text into the token).
- [x] `dedup.cross_source_identity()`'s third tuple component uses
      `normalize_venue(event.location)` instead of
      `normalize_title(event.location)`.
- [x] A fixture pair built directly from the recorded Balboa
      Park/Fleet strings (`"Fleet Science Center, 1875 El Prado, San
      Diego, CA"` / `"1875 El Prado, San Diego, CA 92101"`) produces
      the same `normalize_venue()` output and collapses under
      `dedup_cross_source()` given matching title+date.
- [x] A negative fixture pair sharing a street name but a different
      street number (e.g. `"1875 El Prado, San Diego, CA"` vs.
      `"1889 El Prado, San Diego, CA"` — two real, different Balboa
      Park buildings) does **not** collapse.
- [x] A negative fixture pair with no detectable street-address shape
      on either side (e.g. two purely name-based venue strings, or a
      comma-less address) reproduces exactly today's
      `normalize_title`-only outcome — proving the fallback path, not
      just the new path.
- [x] The live Balboa Park ↔ Fleet re-measurement (the same script
      sprint 014/015 ticket 004 used) is re-run post-fix and its
      collapse count recorded in this ticket's Notes, whatever it is —
      per that ticket's established "record the result either way"
      convention.
- [x] Full test suite stays green (1541+ passed).

## Notes (ticket 003 completion, 2026-08-30)

**Fix implemented exactly as designed.** `partner_scrape/normalize/dedup.py`
gains `normalize_venue(location: str) -> str` and a module-level
`_STREET_SEGMENT_RE = re.compile(r"^\d+\s+\S")`. `location.split(",")`
runs only when `"," in location`; each stripped segment is tested
against `_STREET_SEGMENT_RE`, and the first match is returned
`normalize_title`-normalized. Any other case (no comma at all, or a
comma-delimited string where no segment starts with a digit) falls
through to `normalize_title(location)` unchanged — the exact
pre-existing behavior. `cross_source_identity()`'s third tuple
component now calls `normalize_venue(event.location)` instead of
`normalize_title(event.location)`; nothing else in that function
changed.

**Unit tests** (`TestNormalizeVenue` in `tests/test_normalize_dedup.py`):
the recorded Balboa Park/Fleet pair both reduce to `"1875 el prado"`;
`"1875 El Prado, San Diego, CA"` vs. `"1889 El Prado, San Diego, CA"`
differ; a comma-less digit-leading string (`"1875 El Prado San Diego CA
92101"`) reproduces `normalize_title()`'s output unchanged (proves the
comma-less guard, not just the fallback in general); a comma-delimited
pair with no digit-leading segment (`"Fleet Science Center, Balboa
Park"`) also reproduces `normalize_title()` unchanged; an empty string
falls back cleanly.

**Integration tests** (`TestDedupCrossSource`): the exact recorded
Balboa Park/Fleet strings, given matching title ("Educator Open
House") and date, collapse to one `Instance` via `dedup_cross_source()`
with both `source_id`s recorded in `.sources`. Two negative fixtures:
different street numbers on the same street (`"1875"` vs. `"1889 El
Prado"`) do not collapse; two purely name-based venues with no comma at
all (`"Fleet Science Center"` vs. `"The Fleet"`) do not collapse,
proving the fallback path reproduces today's outcome rather than just
exercising the new path.

**Full test suite**: 1555 passed (1547 baseline + 8 new fixture tests
in this ticket: 5 `normalize_venue` unit tests, 3 `dedup_cross_source`
integration fixtures). No regressions.

**Live re-measurement** (`balboa-park` + `fleet-science-center`, real
adapters via `adapters.run()` + `normalize.run()` directly, script not
committed, matching sprint 014/015 ticket 004's precedent). Env sourced
via `set -a; source config/prod/public.env; source .env; set +a`.

- `balboa-park`: 162 raw events (`tec_rest`).
- `fleet-science-center`: 10 raw events (`listing_html`,
  `default_location` fallback still firing — every event's location is
  `"1875 El Prado, San Diego, CA 92101"`).
- 172 raw events total → 83 `Opportunity` records after collapse +
  cross-source dedup.
- **The "Educator Open House" (2026-09-24) pair now collapses**: one
  `Opportunity` (`title="Educator Open House"`,
  `date_start="2026-09-24T17:30:00-07:00"`) carries
  `sources = {"balboa-park", "fleet-science-center"}`. This is the
  first cross-source collapse ever measured for this pair (sprint 014
  ticket 004: 0; sprint 015 ticket 004: 0; this ticket: 1).
- Exactly 1 `Opportunity` in this live run carries more than one
  contributing source — the Educator Open House pair is the only
  cross-source collapse in this 8-institution-minus-6 (only the two
  sources under test were run) measurement, consistent with
  `normalize/DESIGN.md`'s already-documented, accepted limitation that
  a hub calendar's *generically*-titled event (e.g. "Member Preview
  Night") still won't merge with an institution's differently-titled
  listing — only a genuine title+date+venue match does, which is
  exactly what "Educator Open House" is.

**`normalize/DESIGN.md`** Open Questions' sprint 014/015 entry is
updated with this ticket's fix and live re-measurement result (see that
file's own diff), closing the loop the sprint 015 addendum left open.

## Testing

- **Existing tests to run**: `uv run pytest`, especially
  `tests/test_normalize_dedup.py` (or equivalent) in full.
- **New tests to write**: `normalize_venue()` unit tests covering the
  match case, the different-street-number negative case, and the
  no-comma/no-match fallback case; a `cross_source_identity()`/
  `dedup_cross_source()` integration fixture using the real recorded
  Balboa Park/Fleet strings.
- **Verification command**: `uv run pytest`. The live re-measurement
  is a script, not a committed test, matching sprint 014/015 ticket
  004's own precedent.

## Implementation Plan

**Approach**: One new, narrowly-scoped function plus a one-line change
to `cross_source_identity()`'s existing third component — no change to
`Instance`, `score_event`, `pick_best`, or `dedup_cross_source()`'s
grouping logic itself.

**Files to modify**:
- `partner_scrape/normalize/dedup.py` — `normalize_venue()`,
  `cross_source_identity()`'s venue component.
- The corresponding `normalize` test module — new fixture cases.

**Testing plan**: see Testing above.

**Documentation updates**: `partner_scrape/normalize/DESIGN.md`'s
existing sprint 014/015 Open Questions entry on the Balboa Park venue
mismatch is updated with this sprint's fix and the re-measured
collapse count, closing the loop that entry left open.
