---
id: '002'
title: 'Card date: weekday prefix and weekend distinction'
status: open
use-cases: [SUC-002]
depends-on: []
github-issue: ''
issue: 25-card-date-weekday-and-weekend-distinction.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Card date: weekday prefix and weekend distinction

## Description

Issue 25: the opportunity card date currently shows only the date (`formatDate()` in
`site/src/lib/helpers.ts` produces e.g. `"July 22, 2026"`), with no weekday and no way to spot a
weekend program at a glance. Add the abbreviated weekday to the formatted date, and give
weekend (Sat/Sun) dates a subtle-but-visible visual distinction from weekday dates.

`formatDate()` is the single source of every date string the site renders (`formatDateRange()`,
used by the detail page, calls it internally) — see `sprint.md` Architecture > Design Rationale
("`formatDate()`'s weekday addition applies everywhere it's already called, including the detail
page"). Changing it here intentionally changes the detail page's date range display too; that is
correct, not scope creep — see Impact on Existing Components in `sprint.md`.

## Implementation Plan

### Approach

- In `helpers.ts`, update `formatDate()` to prepend an abbreviated weekday (e.g. `"Wed, Jul 22"`)
  using `Intl.DateTimeFormat`/`toLocaleDateString`'s `weekday: 'short'` option alongside the
  existing `month`/`day`/`year` options — resolve the weekday from the same local wall-clock
  convention already used elsewhere in the site (matching the Calendar's `dayKey()` day-bucketing
  and ticket 001's midnight-detection approach), not a naive UTC read, so a date carrying a
  `-07:00` offset resolves to the correct San Diego calendar day.
- Add a small weekend predicate (e.g. `isWeekend(dateStr)`) next to `formatDate()`, returning
  `true` for Sat/Sun in the same local-wall-clock convention.
- In `OpportunityCard.astro`, pass the weekend result through as a `data-weekend="true"`
  attribute (or a `.weekend` class) on `.opp-card-date`, and add a corresponding `global.css`
  rule for a subtle-but-visible treatment (e.g. a slightly different color/weight or a small
  accent dot) — not a loud badge.
- Per the Design Rationale, do **not** add a second, card-only date formatter — `formatDate()`
  is changed directly so every current caller (including the detail page's `formatDateRange()`)
  picks up the weekday automatically.
- Undated opportunities are unaffected: `formatDate()` already returns `"Ongoing"` for a null/
  invalid `dateStr` before any weekday logic runs.

### Files to Modify

- `site/src/lib/helpers.ts` — `formatDate()` (weekday prefix), new weekend predicate.
- `site/src/components/OpportunityCard.astro` — `.opp-card-date` gains the weekend
  data-attribute/class.
- `site/src/styles/global.css` — new weekend-date styling rule.
- (Verify, don't necessarily change) `site/src/pages/opportunities/[slug].astro` — confirm its
  `formatDateRange()`-driven date display reads correctly with the new weekday prefix; apply the
  same weekend distinction there too if it reads well, per issue 25's own suggestion for
  consistency (left to this ticket's judgment, not mandated).

### Testing Plan

- No JS test framework in `site/`; verify manually: a card's date shows the weekday prefix; a
  Saturday/Sunday date is visibly (but subtly) distinguished from a weekday date; an undated
  opportunity still shows "Ongoing"; a timezone-offset date resolves to the correct local weekday
  (spot-check against a known date/day-of-week).
- `uv run pytest` unaffected (no Python files touched).

### Documentation Updates

None required.

## Acceptance Criteria

- [ ] Card dates show an abbreviated weekday (Mon–Sun) prefix, e.g. "Wed, Jul 22".
- [ ] Weekend dates (Sat/Sun) carry a visibly different, but subtle, treatment from weekday
      dates.
- [ ] Timezone-bearing date strings resolve to the correct local wall-clock weekday, consistent
      with the calendar's day bucketing.
- [ ] Undated opportunities still show "Ongoing" (unchanged).
- [ ] The detail page's date range (`formatDateRange()`) also shows the weekday prefix
      (intentional consequence of changing `formatDate()` directly, not a separate scope item).
- [ ] `npm run build` succeeds.

## Testing

- **Existing tests to run**: none (no JS test framework); `uv run pytest` unaffected.
- **New tests to write**: none applicable; verified by manual visual check plus a successful
  build, per the sprint's Test Strategy.
- **Verification command**: `npm run build`
