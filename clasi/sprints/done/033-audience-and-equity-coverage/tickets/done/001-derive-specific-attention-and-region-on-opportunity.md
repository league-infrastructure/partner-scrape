---
id: '001'
title: Derive specific_attention and region on Opportunity
status: done
use-cases:
- SUC-063
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

- [x] `normalize/taxonomy.py` gains `SPECIFIC_ATTENTION_KEYWORDS` (a
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
- [x] `normalize/taxonomy.py` gains `REGION_KEYWORDS` and
      `derive_region(location: str) -> str`, ordered specific-before-generic
      (South Bay/East County/North County Coastal/North County Inland city
      names checked before the generic "san diego"/downtown/neighborhood
      patterns that resolve to `"Central San Diego"`). First match wins; no
      match returns `""` (unclassified) — never a forced guess.
- [x] `normalize/run.py`'s `_to_opportunity()` calls
      `derive_specific_attention(text)` in place of the hardcoded
      `specific_attention=[]` stub, and `derive_region(location)`, storing
      the result on a new `Opportunity.region: str = ""` field (added after
      `sources` in the dataclass, matching its "trailing internal field"
      position).
- [x] `export/writer.py`'s `SITE_SCHEMA_FIELDS` excludes both `"sources"`
      and `"region"` (`f.name not in ("sources", "region")`), so `region`
      never leaks into `opportunities.json`. Existing tests asserting the
      exact `SITE_SCHEMA_FIELDS`/exported-keys set are updated accordingly
      (`tests/test_export.py`, `tests/test_pipeline_e2e.py`,
      `tests/test_normalize_run.py`, `tests/test_export_partner_log.py` —
      grep for `specific_attention` to find every fixture `Opportunity(...)`
      construction site that needs a `region=` default added).
- [x] CMOD's `"Bilingual"`-category-tagged events (via the `tec_rest`
      adapter, which already populates `Event.categories` from the TEC API's
      `categories[].name`) export with `"Programs in Spanish"` in
      `specific_attention` — fixture test, not live.
- [x] A record matching neither keyword set exports `specific_attention=[]`
      and `region=""`, unchanged from today's stub behavior (regression
      check).
- [x] No `PROMPT_VERSION` bump; nothing in `enrich/` is touched.

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

## Notes

Live-verified against the real corpus (`pipeline.run(dry_run=True)`, no
`--no-enrich` needed since neither derivation touches enrichment; ran
2026-09-02, `SCRAPE_CACHE_DIR`/`ANTHROPIC_API_KEY` loaded from `.env`,
`dangerouslyDisableSandbox` for outbound network, no disk write since
`dry_run=True`):

- 4235 total `Opportunity` records post-collapse/dedup (1020 of them
  current/upcoming, i.e. actually exported).
- `specific_attention` distribution (all 4235 records): `"Programs in
  Spanish"` 31, `"Programs for students with disabilities"` 4, no tag
  4200.
- Region distribution (all 4235 records): Central San Diego 2210,
  unclassified 1111, North County Coastal 429, North County Inland 221,
  East County 174, South Bay 90. On the exported (current/upcoming)
  1020-record subset: Central San Diego 346, unclassified 223, North
  County Coastal 153, North County Inland 140, East County 117, South
  Bay 41.
- Issue 34's 2026-08-30 baseline ("South Bay has 8 records, East County
  0") is now South Bay 90 / East County 174 (all records) — both moved
  well off zero since the issue was written, from the regional-source
  sprints (A–F) that ran between the issue and this sprint's execution,
  exactly as `sprint.md`'s Problem section anticipated ("measuring
  before that content exists would show a permanently-empty baseline").
  This ticket adds the measurement; it does not itself add sources.
- Accessibility offerings found flagged in the live run: Fleet
  Accessibility Mornings (via both `balboa-park` as "Fleet Accessibility
  Mornings" and `fleet-science-center` directly as "Accessibility
  Mornings" — two records, not cross-source-merged, a known
  `normalize/DESIGN.md` limitation on differently-titled hub-vs-institution
  records) and CMOD's Sensory Friendly Mornings (`visitcmod`). The Nat's
  ASD Mornings did **not** appear anywhere in the live run's
  `specific_attention`-flagged records — confirms issue 34's "only 1 of
  3" framing is now "2 of 3" (Fleet fixed itself/already worked, CMOD
  already worked) with the Nat still missing, feeding directly into
  ticket 003's investigation.
- `Opportunity.region`'s unclassified share (~26% of all records, ~22%
  of exported) matches `normalize/DESIGN.md`'s own documented caveat
  that the keyword-only classification will undercount against the true
  regional distribution — not a defect, an accepted, observable
  limitation.
