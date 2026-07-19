---
id: '006'
title: Normalize, cross-source dedup, and recurring collapse
status: done
use-cases:
- SUC-005
- SUC-006
depends-on:
- '004'
github-issue: ''
issue: 05-normalize-dedup-site-export.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Normalize, cross-source dedup, and recurring collapse

## Description

Build the Normalize & Dedup module (sprint architecture): turn a list
of canonical `Event`s into a deduplicated list of site-schema
`Opportunity` records. This is the seam issue 05 identifies as
increasingly important as coverage grows — dedup can no longer be
within-org-by-slug once the same real-world event might be pulled from
more than one source.

Scope:
- **Field mapping/derivation**: map `Event` → `Opportunity` (the
  site's schema, per `stem-ecosystem/docs/site-implementation-spec.md`
  and matching `dev/export_site.py`'s existing behavior). Derive
  `areas_of_interest`, `age_grade_level`, `time_of_day`, `cost_range`
  via keyword rules — port `dev/export_site.py`'s `AREA_KEYWORDS`,
  `AGE_KEYWORDS`, `map_cost`, `map_time_of_day` into
  `partner_scrape/normalize/taxonomy.py`, reimplemented cleanly against
  the canonical `Event` shape (no LLM this sprint — that's issue 04).
- **Partner join**: normalize org name and look up against the site's
  `partners.json` (external, read-only — this module does not own or
  modify that file) for `partner_id`/logo/geo. No match → keep the org
  name, leave `partner_id` unset, do not fail the record.
- **Cross-source dedup**: identity = normalized(title) + date + venue,
  computed *across* organizations (not the acquisition identity from
  ticket 001, which is per-source). When two or more Events share this
  identity, keep the highest-confidence/most-complete instance's field
  values and record the full set of sources it was seen on.
- **Recurring collapse**: same-(org, title) Events collapse into one
  record spanning first-to-last date, noting the repeat count in
  `availability` (port the logic from `dev/export_site.py`'s
  `collapse_recurring`).
- A single entry point, `normalize.run(events, partners_path) ->
  list[Opportunity]`, that ticket 008's Pipeline calls.

## Acceptance Criteria

- [x] `normalize.run()` maps every input `Event` to an `Opportunity`
      with all site-schema fields present (empty string/list for
      genuinely unknown values — never a missing key).
- [x] `areas_of_interest`/`age_grade_level`/`time_of_day`/`cost_range`
      are derived via the ported keyword rules; behavior matches
      `dev/export_site.py`'s rules on the same inputs (spot-checked,
      not required to be byte-identical).
- [x] An `Event` from an org matching a fixture `partners.json` entry
      (by normalized name) gets `partner_id`/logo/geo populated; an
      unmatched org still produces a valid `Opportunity` with
      `partner_id` unset.
- [x] Two `Event`s from different `source_id`s sharing normalized
      title+date+venue collapse to one `Opportunity`, retaining the
      higher-confidence field values; the set of contributing sources
      is recorded on the record (not silently dropped).
- [x] Two `Event`s sharing only a title (different date or venue) are
      NOT collapsed — remain two separate `Opportunity` records.
- [x] N same-(org, title) recurring `Event`s collapse to one
      `Opportunity` spanning first-to-last date, with `availability`
      containing "Repeats N times through \<date\>".

## Implementation Plan

### Approach

Split into small, independently testable functions rather than one
large `run()`: `taxonomy.py` (pure functions: text → tags), `dedup.py`
(cross-source identity grouping + merge-by-confidence), `collapse.py`
(recurring-instance grouping), `partners.py` (load + normalized-name
join), and `run.py` wiring them in sequence (map → collapse-recurring →
cross-source-dedup → partner-join, or whichever order proves cleanest
once field-mapping is in place — order collapse before cross-source
dedup, since collapsing recurring instances first reduces the set
cross-source dedup has to compare). Test each function against
hand-built `Event`/`Opportunity` fixtures rather than only through the
full pipeline, so a failure points at the specific stage.

### Files to Create/Modify

- `partner_scrape/normalize/__init__.py`
- `partner_scrape/normalize/taxonomy.py`
- `partner_scrape/normalize/dedup.py`
- `partner_scrape/normalize/collapse.py`
- `partner_scrape/normalize/partners.py`
- `partner_scrape/normalize/run.py` (the `normalize.run()` entry point
  — named `run.py`, not `pipeline.py`, to avoid colliding with the
  top-level `partner_scrape/pipeline.py` built in ticket 008)
- `tests/test_normalize_taxonomy.py`
- `tests/test_normalize_dedup.py`
- `tests/test_normalize_collapse.py`
- `tests/test_normalize_partners.py`
- `tests/fixtures/partners.json` (a small, synthetic partners fixture —
  NOT the real `stem-ecosystem` repo's file, so these tests don't
  depend on a sibling checkout existing)

### Documentation Updates

None required this ticket.

### Implementation Notes (deviations from the plan above)

- **Pipeline order is collapse → cross-source-dedup → map, not
  map-first.** The plan's suggested "map → collapse-recurring →
  cross-source-dedup → partner-join" order was evaluated and rejected:
  "highest-confidence/most-complete instance" selection (both stages)
  needs `Event.field_provenance`'s per-field confidence, which does not
  survive the mapping into `Opportunity` (no per-field confidence
  concept there). Collapse and dedup therefore both operate on
  canonical `Event`s (via one small `Instance` bookkeeping wrapper),
  and only the survivors are mapped to `Opportunity` last. This matches
  the ticket's own permission to use "whichever order proves cleanest
  once field-mapping is in place."
- **One extra internal file**: `partner_scrape/normalize/instance.py`,
  a small frozen `Instance` dataclass (`event`, `sources`,
  `repeat_count`, `last_seen`) threaded through collapse → dedup → the
  mapping step, so repeat-count and contributing-source bookkeeping
  doesn't require touching `Event` or `Opportunity`. Not in the
  ticket's original Files to Create/Modify list; added because
  collapse.py and dedup.py both need it and neither can import the
  other (collapse calls dedup's scoring helpers) without a cycle.
- **`Opportunity` gains one field beyond the site schema**: `sources:
  frozenset[str]`, the contributing `source_id`s a cross-source-merged
  record was seen on — satisfies the acceptance criterion that this set
  be "recorded on the record, not silently dropped." It is documented
  as not part of the site JSON contract; ticket 007 (Site Export)
  decides whether/how to carry or drop it when writing
  `opportunities.json`.
- **`normalize.run()` signature gained an optional third parameter**:
  `source_org_names: dict[str, str] | None = None`, a `source_id ->
  org_name` map. The canonical `Event` (ticket 001's model, frozen per
  that ticket's own convention — see `adapters/tec.py`'s docstring on
  why `organizer` wasn't added) carries no organization-name field,
  only `source_id`; the human-readable org name needed for the
  `partners.json` join by normalized name only exists on
  `SourceConfig.org_name` in the Source Registry. Rather than extend
  `Event` or have Normalize depend on the Registry module (sprint.md's
  Component diagram shows neither edge), `run()` accepts this map from
  whichever caller already has the registry in hand — ticket 008's
  Pipeline, which loads the registry to dispatch sources in the first
  place, can pass `{s.source_id: s.org_name for s in sources}`. When a
  `source_id` is absent from the map (including when the map itself is
  omitted, as in this ticket's own unit tests), `source_id` is used as
  the org name — it usually won't match `partners.json`, which is fine
  per SUC-005's documented error flow ("no match → keep the org name,
  leave partner_id unset, do not fail the record"). Flagging for
  ticket 008: real `tec_rest`/`wp_rest`/`ical` adapter output will only
  get partner matches once ticket 008's Pipeline actually supplies this
  map — that's expected, not a bug in this ticket's own (hand-built
  fixture) tests.

## Testing

- **Existing tests to run**: `uv run pytest` (tickets 001-004's
  suites — this ticket consumes the `Event` model and, for realistic
  test fixtures, the shape the TEC adapter actually produces).
- **New tests to write**: as listed in Files to Create/Modify, one test
  file per normalize sub-module, covering every acceptance criterion
  above including the "NOT collapsed" negative case.
- **Verification command**: `uv run pytest`
