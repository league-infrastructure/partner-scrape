---
id: '001'
title: Derive specific_attention and region on Opportunity
status: open
use-cases: [SUC-063]
depends-on: []
github-issue: ''
issue: 34-audience-gaps-spanish-regional-accessibility.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Derive specific_attention and region on Opportunity

## Description

The site's own data contract already defines `Opportunity.specific_attention:
string[]` ("Values like `Programs for boys`, `Programs for girls`, `Programs
for students with disabilities`, `Programs in Spanish`, etc." —
`stem-ecosystem/docs/site-implementation-spec.md`), but `normalize/run.py`'s
`_to_opportunity()` has hardcoded it to `[]` since sprint 015 ticket 008. This
ticket makes it a real, derived value for two of the vocabulary's own named
signals — bilingual/Spanish availability and accessibility/sensory-friendly
programming — closing part of issue 34's gap ("nothing is in Spanish,"
"accessibility programming is nearly absent," neither currently *visible* in
the data even where it exists).

It also adds a second, wholly new, **internal** field, `Opportunity.region`,
classifying each record into a coarse San Diego sub-region (South Bay, East
County, North County Coastal, North County Inland, Central San Diego, or `""`
if unclassified) from its already-resolved `location` text. This field is
**not** part of the site schema — same "internal bookkeeping" treatment as
the existing `Opportunity.sources` field — and exists purely to feed ticket
002's regional yield/site-meta measurement. It is the one genuine data-model
change in this sprint.

See `clasi/sprints/033-audience-and-equity-coverage/design/normalize-DESIGN.md`
(the sprint's design overlay) for the full design, including the exact keyword
rule sets and the rejected alternatives (ZIP/lat-long geocoding for region;
title-only matching for specific_attention).

**No `Event` field is added.** Both derivations are pure functions over an
`Event`'s/`Opportunity`'s already-existing text/location fields, computed at
`_to_opportunity()` time — the same shape `derive_areas_of_interest` already
uses, not the `Event.set(...)`-tracked-field pattern `eligibility`/`trusted`
use, since neither value has meaningful per-field provenance to track (it is
a deterministic function of already-provenanced text).

## Acceptance Criteria

- [ ] `normalize/taxonomy.py` gains `SPECIFIC_ATTENTION_KEYWORDS` (a
      `(pattern, label)` rule list) and `derive_specific_attention(text) ->
      list[str]`, following `tag_by_keywords`'s existing shape. Matches
      title + description + categories + tags (the existing
      `build_taxonomy_text()` blob) against:
      - `\bbilingual\b`, `\bnoche de ciencias\b`, `\bsan ysidro stem
        fair\b`, `en español`/`en espanol` → `"Programs in Spanish"`
      - `\bsensory[\s-]?friendly\b`, `\baccessibility mornings\b`,
        `\basd mornings\b` → `"Programs for students with disabilities"`
      No fallback — an unmatched record returns `[]`, matching
      `derive_age_grade_level`'s no-fallback precedent.
- [ ] `normalize/taxonomy.py` gains `REGION_KEYWORDS` and
      `derive_region(location: str) -> str`, ordered specific-before-generic
      (South Bay/East County/North County Coastal/North County Inland city
      names checked before the generic "san diego"/downtown/neighborhood
      patterns that resolve to `"Central San Diego"`). First match wins; no
      match returns `""` (unclassified) — never a forced guess.
- [ ] `normalize/run.py`'s `_to_opportunity()` calls
      `derive_specific_attention(text)` in place of the hardcoded
      `specific_attention=[]` stub, and `derive_region(location)`, storing
      the result on a new `Opportunity.region: str = ""` field (added after
      `sources` in the dataclass, matching its "trailing internal field"
      position).
- [ ] `export/writer.py`'s `SITE_SCHEMA_FIELDS` excludes both `"sources"`
      and `"region"` (`f.name not in ("sources", "region")`), so `region`
      never leaks into `opportunities.json`. Existing tests asserting the
      exact `SITE_SCHEMA_FIELDS`/exported-keys set are updated accordingly
      (`tests/test_export.py`, `tests/test_pipeline_e2e.py`,
      `tests/test_normalize_run.py`, `tests/test_export_partner_log.py` —
      grep for `specific_attention` to find every fixture `Opportunity(...)`
      construction site that needs a `region=` default added).
- [ ] CMOD's `"Bilingual"`-category-tagged events (via the `tec_rest`
      adapter, which already populates `Event.categories` from the TEC API's
      `categories[].name`) export with `"Programs in Spanish"` in
      `specific_attention` — fixture test, not live.
- [ ] A record matching neither keyword set exports `specific_attention=[]`
      and `region=""`, unchanged from today's stub behavior (regression
      check).
- [ ] No `PROMPT_VERSION` bump; nothing in `enrich/` is touched.

## Testing

- **Existing tests to run**: `uv run pytest tests/test_normalize_run.py
  tests/test_export.py tests/test_pipeline_e2e.py
  tests/test_export_partner_log.py tests/test_export_publish.py` plus the
  full suite (`uv run pytest`) — several existing tests assert the literal
  `SITE_SCHEMA_FIELDS` tuple or construct `Opportunity(...)` fixtures with
  every field spelled out; both will need a `region=""` addition, not just
  new tests.
- **New tests to write**: `tests/test_normalize_taxonomy.py` (or wherever
  the existing `derive_areas_of_interest`/`derive_age_grade_level` tests
  live) gets `TestDeriveSpecificAttention` and `TestDeriveRegion` classes,
  one test per keyword rule plus a no-match case for each. A
  `_to_opportunity()`-level integration test confirms both derived values
  land on the built `Opportunity` and that `region` does not appear in
  `to_json_dict()`'s output.
- **Verification command**: `uv run pytest`
