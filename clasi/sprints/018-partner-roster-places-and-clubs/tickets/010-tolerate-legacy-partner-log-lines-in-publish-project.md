---
id: '010'
title: Tolerate legacy partner-log lines in publish.project()
status: in-progress
use-cases: []
depends-on: []
github-issue: ''
issue: 45-publish-legacy-jsonl-tolerance.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Tolerate legacy partner-log lines in publish.project()

## Description

`partner_scrape/export/publish.py`'s `_to_opportunity()` reconstructs an
`Opportunity` from a persisted `.jsonl` line by dict-subscripting every
current `Opportunity` dataclass field name out of the stored entry
(`kwargs: dict[str, Any] = {name: entry[name] for name in
_OPPORTUNITY_FIELD_NAMES}`, `publish.py:132`). The per-partner log
(`export/partner_log.py`) is strictly append-only and never migrated:
any line recorded before a given field existed on `Opportunity` lacks
that key. `eligibility` was added to `Opportunity` in sprint 015
(`b0570aa`), so every log line recorded before that sprint now raises
`KeyError('eligibility')` when `publish.project()` collapses and
reconstructs it — which is every line, since the store predates sprint
015. Root-caused in sprint 018 ticket 001 (see that ticket's Notes for
the full reproduction and traceback); ticket 001 made the failure loud
(wrapped the `cli.py` call in try/except, logged, non-zero exit) but
deliberately left `_to_opportunity()` itself unfixed, out of its file
scope. Consequence: `publish.project()` has failed on every run since
sprint 015 merged, and `public/data/` (the partner roster + per-partner
event files issue 15's `llms.txt` contract advertises) has been
silently stale until ticket 001's exit-code fix made it loud, and stays
functionally broken until this ticket lands.

The `.jsonl` log's entire append-only design assumes old lines stay
readable as the schema grows (see `export/DESIGN.md`'s "append-only"
invariant) — tolerating a missing key on reconstruction restores an
already-intended property, not a new behavior.

## Acceptance Criteria

- [x] `_to_opportunity()` defaults any field missing from a persisted
      log `entry` from `Opportunity`'s own dataclass field defaults
      (`dataclasses.fields(Opportunity)` — already imported as
      `_OPPORTUNITY_FIELD_NAMES`'s source), by iterating dataclass
      fields generically. No per-field special case for `eligibility`
      or any other single field name — the fix must equally tolerate a
      *future* field addition with no code change here.
- [x] A field present in `entry` is used verbatim (current behavior,
      unchanged); only an absent field falls back to the dataclass
      default. A field whose dataclass default is itself required
      (no `default`/`default_factory` — i.e. `Opportunity`'s
      non-defaulted fields) is never actually missing in practice for
      any real log line, since `partner_log.record()` always writes
      every field that existed on `Opportunity` at record time; this AC
      only needs to hold for fields added *after* a line was written.
- [x] Regression test: a fixture `.jsonl` line built from a real
      pre-sprint-015 shape (missing `eligibility`) reconstructs via
      `_to_opportunity()` without raising, and the resulting
      `Opportunity.eligibility` equals the dataclass default (`""`).
- [x] Regression test: a fixture `.jsonl` line missing several newer
      fields at once (not just `eligibility`) reconstructs correctly,
      each missing field taking its dataclass default.
- [x] Regression test: `publish.project()` run end-to-end (via
      `tmp_path` fixtures, not the real store) over a partner log
      containing a mix of legacy (missing-field) and current-schema
      lines succeeds and produces correct output for both eras of line.
- [x] Live verification: run `publish.project()` (or the `uv run
      partner-scrape` path that calls it) against this repo's real
      accumulated `partner_log/` store and confirm it completes without
      raising and regenerates `public/data/` — the same store ticket
      001's Notes used to reproduce the original `KeyError`. Record the
      command run and its outcome in this ticket's Notes.
- [x] Full test suite stays green (`uv run pytest`).

## Testing

- **Existing tests to run**: `uv run pytest`, in particular any
  existing `tests/` coverage of `export/publish.py` (`_to_opportunity`,
  `_collapse_last_line_wins`, `project`) and `export/partner_log.py`,
  to confirm no regression to current-schema (non-legacy) reconstruction.
- **New tests to write**: the four regression tests in Acceptance
  Criteria — one missing-single-field fixture line, one
  missing-several-fields fixture line, one mixed-era `project()`
  end-to-end run, and (implicitly covered by the mixed-era test) a
  same-partner log containing both a legacy and a current-schema line
  collapsing correctly via `_collapse_last_line_wins`'s existing
  last-line-wins logic.
- **Verification command**: `uv run pytest`, plus the live verification
  step in Acceptance Criteria (a real `publish.project()` invocation
  against this repo's actual `partner_log/` store, confirming
  `public/data/` regenerates and the process exits cleanly).

## Implementation Plan

**Approach**: Systematic, narrow fix confined to `_to_opportunity()`'s
reconstruction logic. Replace the current dict-comprehension's plain
`entry[name]` subscript with a lookup that iterates
`dataclasses.fields(Opportunity)` (already available via the module's
existing `fields` import and `_OPPORTUNITY_FIELD_NAMES` derivation) and
falls back to each field's own `default`/`default_factory` when `name`
is absent from `entry`, rather than hardcoding `eligibility`'s specific
default. Keep the existing `sources` list→`frozenset` round-trip
unchanged (it already assumes `entry["sources"]` is present — legacy
lines predate the `sources` field's own introduction only insofar as
that field already existed when the log was first written; if a fixture
shows `sources` can also be legacy-missing, default it via the same
generic mechanism rather than a special case). Do not touch
`_collapse_last_line_wins`, `_split_current_and_past`, `project()`'s
outer structure, or anything in `cli.py` (ticket 001 already fixed the
caller-side wiring there) — this ticket's scope is `_to_opportunity()`
and its direct test coverage only.

**Files to modify**:
- `partner_scrape/export/publish.py` — `_to_opportunity()`'s
  field-reconstruction logic.
- `tests/` (wherever existing `export/publish.py` tests live, following
  this codebase's existing per-module test-file convention) — new
  regression tests per Acceptance Criteria.

**Testing plan**: see Testing above.

**Documentation updates**: none anticipated — `export/DESIGN.md` already
documents the append-only log's tolerance-for-drift intent; this ticket
restores actual conformance to that documented intent rather than
changing the intent itself. If implementation reveals `DESIGN.md`
understated this gap, add a brief note to its Open Questions or
Constraints section, but only to describe what was actually found.

## Notes

**Fix.** `_to_opportunity()` (`partner_scrape/export/publish.py`) no
longer builds its `kwargs` dict with a plain `entry[name]` subscript
over a fixed field-name tuple. It now iterates
`dataclasses.fields(Opportunity)` directly: a field present in `entry`
is used verbatim (unchanged); a field absent from `entry` falls back to
`field.default` when set, else `field.default_factory()` when set (this
is what `sources` — `default_factory=frozenset` — would hit, though no
real line is actually missing it); a field with neither (a
non-defaulted `Opportunity` field) still subscripts `entry[name]`
directly, so a truly-impossible-in-practice case still raises the same
`KeyError` naming the field, rather than inventing a value the
dataclass itself declares required. No field name (`eligibility` or
otherwise) is special-cased anywhere in the new code — a future field
addition needs no change here, satisfying the ticket's core constraint.
The now-dead `_OPPORTUNITY_FIELD_NAMES` module constant (only ever used
by the old subscript comprehension) was removed rather than left
unused.

**Tests added** (`tests/test_export_publish.py`,
`TestLegacyLogLineTolerance`): (1) a fixture entry built from a real
`partner_log._to_log_dict()` output with `eligibility` deleted
reconstructs via `_to_opportunity()` without raising, and
`Opportunity.eligibility == ""`; (2) the same, with `eligibility`,
`image_src`, and `sources` all deleted at once, each field landing on
its own dataclass default (`sources == frozenset()`); (3) an end-to-end
`publish.project()` run (`tmp_path` fixtures) over one partner's log
containing both a hand-written legacy line (missing `eligibility`,
written directly to disk since `record()` can't produce a legacy line
itself) and a current-schema line appended via the real
`partner_log.record()` — confirms both events publish correctly, the
legacy line's `eligibility` defaults to `""`, and the current line's own
`eligibility` value ("Grades 6-8") survives untouched. Full suite:
1889 passed (baseline 1886 + 3 new tests), `uv run pytest -q`.

**Live verification (AC6), against the real store.** Before fixing,
temporarily `git stash`ed just `partner_scrape/export/publish.py` back
to its pre-fix state and called `publish.project()` (`dry_run=True`, to
guarantee no write regardless) directly against this repo's real
accumulated store —
`log_dir=/Volumes/Cache/stem-ecosystem/partner_log` (per
`config/prod/public.env`'s `SCRAPE_CACHE_DIR`),
`site_dir=/Volumes/Proj/proj/league-projects/infrastructure/stem-ecosystem`
(the default sibling checkout), `partners_path={site_dir}/src/data/partners.json`.
Result: `KeyError: 'eligibility'`, reproducing ticket 001's Notes
traceback exactly, off the live store (not a fixture). `git stash pop`
restored the fix, then the identical call was re-run for real
(`dry_run` omitted, i.e. `False`):

```
Before fix (dry_run=True): REPRODUCED FAILURE: KeyError 'eligibility'
After fix:                 SUCCESS: {'partner_count': 153, 'current_event_count': 304, 'past_event_count': 916}
```

`{site_dir}/public/data/partners.json`'s `generated_at` advanced to the
run's own timestamp (`2026-08-31T19:11:09Z`) and `partner_count: 153`
matches the curated roster's length; 144 per-partner directories were
written under `public/data/partners/` (153 curated partners collapse to
144 unique slugs — 9 curated names collide pairwise via `slugify`, e.g.
two roster entries both named "Ocean Connectors"; this is pre-existing
`project()`/curated-roster behavior, unrelated to this ticket's field-
reconstruction fix, and left untouched — out of this ticket's file
scope). This is the first successful `publish.project()` run against
this store since sprint 015 merged; `public/data/` now reflects current
accumulated data (1220 total opportunities across current + past)
instead of staying silently stale.

Note on the ticket's "211-partner roster" figure (Description/live-
verification prose): the real curated roster is currently 153 partners,
not 211 — that number was this ticket's/issue's estimate, not a hard
target, and does not affect this fix; whatever the curated roster's
actual size, `project()` now publishes it without raising.
