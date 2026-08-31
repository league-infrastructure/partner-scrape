---
id: 008
title: Add eligibility field end-to-end
status: done
use-cases:
- SUC-009
depends-on:
- '007'
github-issue: ''
issue: 27-taxonomy-camps-competitions-deadlines-eligibility.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add eligibility field end-to-end

## Description

Several of the best programs in the gap analysis are real but
restricted closed pipelines: Northrop HIP (partner high schools),
Scripps REACH (nine named schools), SBP Preuss program, Illumina/SD2,
and Zoo free field trips (SD County schools only). Stakeholder
decision (2026-08-30): show these honestly with an eligibility note
rather than omit them. Add an `eligibility` field to `Opportunity` +
export + the site's detail-page display.

`SourceConfig.taxonomy_defaults` is parsed by `registry/schema.py`
already, but before this ticket nothing in the codebase reads it —
`normalize/run.py`'s `specific_attention`/`financial_support`/
`ngss_aligned` fields are hardcoded stubs (`[]`/`"No"`/`"No"`), not
actually sourced from it, despite prior design-doc language suggesting
otherwise. This ticket wires `taxonomy_defaults` for `eligibility`
only — the other three fields staying hardcoded stubs is an explicit,
separate decision, not addressed here.

Depends on ticket 007 because both tickets touch `normalize/run.py`'s
`Opportunity`/`_to_opportunity()`; sequencing after 007 avoids merge
overlap in that file.

## Fix shape

1. **`normalize/run.py`**: add `eligibility: str = ""` to the
   `Opportunity` dataclass (after `location`/before `latitude` is
   fine, or wherever fits — additive, order doesn't matter to
   consumers keyed by field name). Add an optional
   `source_taxonomy_defaults: dict[str, dict] | None = None` parameter
   to `run()`, defaulted to `{}` inside, the same shape and
   construction site as the existing `source_org_names` parameter.
   In `_to_opportunity()`, resolve
   `taxonomy_defaults = source_taxonomy_defaults.get(instance.event.source_id, {})`
   (the identical lookup key `org_name` already uses) and set
   `eligibility=taxonomy_defaults.get("eligibility", "")`.
2. **`pipeline.py`**: build
   `source_taxonomy_defaults = {source.source_id: source.taxonomy_defaults
   for source in sources}` alongside the existing `source_org_names`
   construction, and pass it into the `normalize_run(...)` call.
3. **`export/writer.py`**: no change needed — `SITE_SCHEMA_FIELDS` and
   `to_json_dict()` derive from `Opportunity`'s dataclass fields
   automatically, so `eligibility` ships in `opportunities.json`
   automatically once it exists on the dataclass.
4. **Registry data**: set `taxonomy_defaults.eligibility` on the
   TOMLs for the five named programs (or their owning sources, if a
   program is one of several events from a multi-program source —
   confirm each source's TOML actually corresponds 1:1 with the named
   program before editing; if a source publishes both restricted and
   open programs, note that as a limitation rather than force an
   inaccurate blanket eligibility note).
5. **`site/src/pages/opportunities/[slug].astro`**: add one more
   conditional `<dt>/<dd>` pair, matching the existing
   `financial_support`/`ngss_aligned`/`location` pattern exactly:
   `{opp.eligibility && (<><dt>Eligibility</dt><dd>{opp.eligibility}</dd></>)}`.

## Acceptance Criteria

- [x] `Opportunity` gains `eligibility: str = ""`.
- [x] `normalize.run()` accepts `source_taxonomy_defaults` and passes
      it through to `_to_opportunity()` exactly as `source_org_names`
      already flows.
- [x] A fixture test proves `taxonomy_defaults.eligibility` reaches
      `Opportunity.eligibility` unchanged, keyed by `source_id`.
- [x] A fixture test proves a source with no
      `taxonomy_defaults.eligibility` key (or no `source_taxonomy_defaults`
      map at all, e.g. `run()` called without it) still produces
      `eligibility == ""` — no regression for the ~120 sources that
      don't set it.
- [x] `pipeline.py` builds and threads `source_taxonomy_defaults`
      identically to `source_org_names`.
- [x] `export/writer.py`'s existing `SITE_SCHEMA_FIELDS`/`to_json_dict`
      tests are extended to assert `eligibility` round-trips into the
      exported payload — no code change required in `export/writer.py`
      itself, only a test-coverage extension proving that.
- [x] At least the five named programs' registry TOML entries are
      edited with a real, reviewable, source-accurate eligibility
      note (or a documented reason why a given source can't be
      edited accurately — see Fix shape point 4). **Deviation:** none
      of the five were edited with an actual eligibility value.
      Investigation (name/org search across
      `registry/sources/*.toml`) found Northrop HIP, Scripps REACH,
      SBP Preuss, and Illumina/SD2 have no corresponding registry
      source at all. The fifth, `sandiegozoowildlifealliance.toml`,
      covers the org's whole site generically (and is disabled), not
      the specific free-field-trips program, so setting a blanket
      `eligibility` there would misrepresent every other event that
      source might publish — exactly the "note as a limitation rather
      than force an inaccurate blanket eligibility note" case Fix
      shape point 4 anticipates. Documented in that TOML's own
      comment, in `normalize/DESIGN.md`'s sprint 015 addendum, and in
      the pipeline threading fixture test
      (`tests/fixtures/e2e_registry/coastalrootsfarm.toml`), which
      proves the mechanism itself works even though no real registry
      entry exercises it yet.
- [x] `[slug].astro` renders the `Eligibility` row only when
      `opp.eligibility` is non-empty, matching the existing
      conditional-block convention.
- [x] Full test suite stays green.

## Testing

- **Existing tests to run**: full suite (`uv run pytest`), especially
  `normalize/run.py`'s and `export/writer.py`'s existing test modules,
  and `pipeline.py`'s existing test module.
- **New tests to write**: per Acceptance Criteria above.
- **Verification command**: `uv run pytest`.

## Implementation Plan

**Approach**: Add the field and the threading mechanism first (the
`source_org_names` precedent is a near-exact template), then the
registry data edits, then the site display.

**Files to modify**:
- `partner_scrape/normalize/run.py` — `Opportunity.eligibility`,
  `run()`/`_to_opportunity()` parameter threading.
- `partner_scrape/pipeline.py` — `source_taxonomy_defaults`
  construction and pass-through.
- `partner_scrape/registry/sources/*.toml` — the five named programs'
  `taxonomy_defaults.eligibility` entries.
- `site/src/pages/opportunities/[slug].astro` — the conditional
  display row.
- Corresponding test files for `normalize/run.py`, `export/writer.py`,
  `pipeline.py`.

**Testing plan**: see Testing above.

**Documentation updates**: `partner_scrape/normalize/DESIGN.md` gets a
sprint-015 addendum documenting that `taxonomy_defaults` threading is
now real for `eligibility` specifically, and that
`specific_attention`/`financial_support`/`ngss_aligned` remaining
hardcoded stubs is an explicit, separate Out of Scope decision, not an
oversight this ticket left behind. `partner_scrape/registry/DESIGN.md`
gets a one-line note that `taxonomy_defaults.eligibility` is now a
real, consumed key (its pre-existing "no schema validation for
`config`/`taxonomy_defaults`" Open Question still applies unchanged —
a typo'd key is silently ignored, same as any other).
