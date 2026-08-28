---
id: '003'
title: Partner event-publishing strategy page
status: done
use-cases:
- SUC-004
depends-on:
- '001'
github-issue: ''
issue: 17-partner-event-publishing-strategy.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Partner event-publishing strategy page

## Description

Create `site/src/pages/publish-events.astro`, documenting the event
schema (referencing `/data-access`, not restating it) and the A–E
publishing-method menu from issue 17, ordered easiest-adoption-first,
each entry explicitly labeled supported-today (C, the `ical` adapter)
vs. proposed/future (A, B, D, E — no new adapter code ships this sprint,
Design Rationale D4). Implements SUC-004.

## Acceptance Criteria

- [x] `site/src/pages/publish-events.astro` exists at `/publish-events`,
      uses `BaseLayout`.
- [x] States the event field set needed by referencing `/data-access`'s
      documented schema, not re-deriving it independently.
- [x] Documents methods A–E in issue 17's easiest-first order (C, B, A,
      then D/E as stretch), each entry naming which existing
      `adapter_type` it harmonizes with (C → `ical`, the only one of
      A–E registered and working today) or which family a future
      adapter would join (A, B, D, E), and explicitly labeled
      "supported today" (C only) vs. "proposed / not yet built" (A, B,
      D, E). **Implementation note — verified deviation:** direct
      inspection of `partner_scrape/extract/ladder.py` shows the
      JSON-LD `Event` rung (B's mechanism — confidence 1.0, rung 1) was
      shipped in sprint 002 (commit `0a55796`) and is already called by
      both `generic_html` and `listing_html` via `extract_fields()` —
      it is not a future adapter, it needs no new adapter code, and it
      already runs on live registered sources today. The page therefore
      labels B "Works today" alongside C, not "proposed / not yet
      built" as this bullet's parenthetical literally lists it. A, D,
      and E were independently confirmed absent (no `.well-known`,
      `openactive`, or `rpde` string anywhere under `partner_scrape/`;
      no matching entry in the `ADAPTERS` table) and are labeled
      "Proposed — not yet built" as written. See the page's own
      top-of-file comment for the full citation trail.
- [x] Does not claim or imply any new adapter code ships this sprint.
- [x] Page renders correctly under both `just dev` and `just build`.

## Implementation Plan

**Approach**: Source the A–E method descriptions from issue 17's own
text (`clasi/sprints/010-discovery-surfaces/issues/17-partner-event-publishing-strategy.md`,
already detailed and stakeholder-vetted) rather than re-inventing the
framing. Verify each "harmonizes with `adapter_type` X" claim against
the real `partner_scrape/adapters/__init__.py` `ADAPTERS` table
(confirmed during planning: `ical` → `ICalAdapter` is the only
currently-registered type among A–E). Cite the one-line registration
pattern (`ADAPTERS["type"] = SomeAdapter` in `adapters/__init__.py`) as
the concrete mechanism a future adapter would use, without implying it
exists yet.

**Files to create**:
- `site/src/pages/publish-events.astro`

**Files to modify**: none.

## Testing

- **Existing tests to run**: `uv run pytest`.
- **New tests to write**: none — no new production code; the "C →
  `ical` is registered today" claim is a stable, already-tested fact of
  `adapters/__init__.py`, not worth a new drift guard at this scale.
- **Verification command**: `just build` / `just dev`; manual check
  that the page does not overstate what's built, and that the
  `adapter_type` claims match `adapters/__init__.py`.
