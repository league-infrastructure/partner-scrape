---
source_file: normalize-DESIGN.md
source_hash: cea020e93b2d180f6af1258db57e43a65a1049deb561914e79dea461bee3cf4d
---
# Diff: normalize-DESIGN.md

Comparison of the sprint overlay copy of `normalize-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- normalize-DESIGN.md (pristine)
+++ normalize-DESIGN.md (current)
@@ -31,6 +31,23 @@
 program-page extraction adapters emit (`adapters/DESIGN.md`), plus one small, additive
 data-flow completion (`eligibility` gains a second, per-record source). See §4 for the
 four specific changes and their rationale.
+
+**(Sprint 033)** Two additive changes, both pure keyword/text derivations added to
+`taxonomy.py` and consumed by `_to_opportunity()` — no new mechanism, no `Event` field,
+one new internal `Opportunity` field. (1) `specific_attention` — hardcoded to `[]` since
+sprint 015 (see §6) — is now genuinely derived: `derive_specific_attention(text)` matches
+the same `build_taxonomy_text()` blob `areas_of_interest` already uses against a bilingual/
+accessibility keyword rule set, returning zero or more of the site schema's own
+already-documented `specific_attention` values (`"Programs in Spanish"`, `"Programs for
+students with disabilities"`). This is filling in an existing, already-exported stub field
+with real values, not a schema change. (2) `Opportunity` gains one new field, `region: str
+= ""` — internal bookkeeping, excluded from `SITE_SCHEMA_FIELDS` (the same treatment
+`sources` already gets), derived by `derive_region(location)` from the already-resolved
+`location` string via city-keyword matching into a new San Diego sub-region vocabulary
+(South Bay, East County, North County Coastal, North County Inland, Central San Diego, or
+`""` if unclassified) — a vocabulary this sprint invents for internal regional-coverage
+measurement (`observability/DESIGN.md`'s sprint 033 addition), not part of the site schema.
+See §4 for both.
 
 ## 2. Orientation
 
@@ -228,6 +245,40 @@
    existing `today = today or date.today()` — every existing caller/test that omits
    `today` gets `date.today()`, unchanged from before this parameter existed.
 
+**(Sprint 033) `specific_attention` is derived, not stubbed.** `derive_specific_attention
+(text)` follows `derive_areas_of_interest`'s exact shape: a `(pattern, label)` rule list
+(`SPECIFIC_ATTENTION_KEYWORDS`), matched with `tag_by_keywords` against the same taxonomy
+text blob, no fallback (an unmatched record keeps `[]`, matching `derive_age_grade_level`'s
+"no fallback" precedent — a wrong guess is worse than an honest empty list here). Rules are
+deliberately narrow, high-signal keyword matches, not broad ones: `\bbilingual\b`,
+`\bnoche de ciencias\b`, `\bsan ysidro stem fair\b`, `en español`/`en espanol` →
+`"Programs in Spanish"`; `\bsensory[\s-]?friendly\b`, `\baccessibility mornings\b`, `\basd
+mornings\b` → `"Programs for students with disabilities"`. Matched against title +
+description + categories + tags (not title-only) because, unlike `opportunity_type`'s
+false-positive risk from ordinary description prose, these are proper-noun program names
+and specific compound phrases with no plausible false-positive collision in this
+codebase's fixtures — CMOD's own "Bilingual" category tag (already captured verbatim as an
+`Event.categories` entry, per issue 34) is exactly the kind of signal a categories/tags
+match is for, that a title-only match would miss.
+
+**(Sprint 033) `region` is derived, not sourced from any adapter.** `derive_region
+(location)` is a new `(pattern, label)` rule list, `REGION_KEYWORDS`, ordered
+specific-before-generic (South Bay/East County/North County Coastal/North County Inland
+city names checked before the generic "san diego"/downtown/neighborhood patterns that
+resolve to `"Central San Diego"`) — the same false-positive-avoidance ordering
+`OPPORTUNITY_TYPE_KEYWORDS` already uses, since a South Bay or East County address's
+`location` string routinely also contains "San Diego" or "CA" as a state/city suffix.
+First match wins; no match returns `""` (unclassified), never a forced guess — matching
+`derive_age_grade_level`'s no-fallback precedent, not `derive_areas_of_interest`'s
+`DEFAULT_AREA` fallback, because a wrong region assignment corrupts the very regression
+signal this sprint exists to provide, where a wrong area-of-interest tag is a much lower-
+stakes miscategorization. Deliberately city-keyword matching against `location` text, not
+ZIP-centroid or lat/long polygon geometry (`geo_ladder.py`'s ZIP/city centroid tables exist
+for `teams/`/`directory/`'s person/place-matching use case, not for county sub-region
+bucketing, and importing it here would be a new, heavier cross-module dependency for a
+coarse five-bucket classification that a keyword table already does adequately) — see
+Design Rationale.
+
 **Taxonomy is keyword rules, not ML.** `taxonomy.py` ports the pre-existing script's
 `AREA_KEYWORDS` / `AGE_KEYWORDS` / cost / time-of-day rules into pure functions.
 `derive_time_of_day` is the one deliberate reimplementation: it reads `Event.start`'s
@@ -352,12 +403,20 @@
   of these three constants typically need the others) — the shared `{"internship",
   "program"}` kind set; see the root `partner_scrape/DESIGN.md`.
 - **`Opportunity`** — the boundary dataclass between scraper and site. `sources` is
-  internal bookkeeping and is not part of the site schema.
+  internal bookkeeping and is not part of the site schema. **(Sprint 033)** `region` is a
+  second internal-bookkeeping field, also excluded from `SITE_SCHEMA_FIELDS` — see §1/§4.
 - **`taxonomy.derive_areas_of_interest`, `classify_opportunity_type`,
   `derive_age_grade_level`, `map_cost`, `derive_time_of_day`, `build_taxonomy_text`,
   `tag_by_keywords`** — pure classification rules, also consumed by `enrich/` as its
   fallback (sprint 009: `classify_opportunity_type` joins this fallback role, unchanged
   rules).
+- **`taxonomy.derive_specific_attention(text) -> list[str]`, `taxonomy.derive_region
+  (location) -> str`** (sprint 033) — two new pure classification rules, same shape as the
+  ones above. Neither is consumed by `enrich/`'s fallback role (that role exists for
+  `EnrichmentResult`'s recoverable/classification fields specifically; `specific_attention`
+  and `region` are never part of an LLM enrichment call at all this sprint — see
+  `sprint.md`'s Design Rationale for why translation, the one place this sprint touched
+  `enrich/` in an earlier draft, was deferred).
 - **`partners.normalize_org_name`** — pure string normalization, also consumed by
   `discovery.hub_scan` for candidate dedup.
 - **`partners.load_partners` / `find_partner`** — read-only partner roster lookup.
@@ -466,7 +525,33 @@
   source's TOML sets. `eligibility` is now the one exception: it is genuinely sourced from
   `taxonomy_defaults.eligibility` via `source_taxonomy_defaults` (see Design, above). The
   other four fields' stub status is unchanged and is now an explicit, documented Out of
-  Scope decision for this ticket, not an open question.
+  Scope decision for this ticket, not an open question. **(Resolved, sprint 033,
+  `specific_attention` only.)** `specific_attention` is now genuinely derived — see this
+  document's sprint 033 addition (§1, §4) and `derive_specific_attention` in Interfaces
+  below. `financial_support`, `ngss_aligned`, and the contact fields remain hardcoded
+  stubs; deriving them is not this sprint's scope and is unchanged from sprint 015's
+  decision.
+- **(Sprint 033)** The `region` vocabulary (South Bay/East County/North County Coastal/
+  North County Inland/Central San Diego) is a keyword-matched judgment against free-text
+  `location` strings, spot-checked against this sprint's known fixture addresses, not
+  validated against a labelled set — the same caveat the pre-existing keyword taxonomy
+  rules above already carry. A `location` string with no recognizable city name (a bare
+  venue name, a virtual/online record, or a city this sprint's keyword list does not yet
+  cover — e.g. a source located outside San Diego County entirely) classifies as `""`
+  (unclassified) rather than guessed. This means the yield report's/`scrape-meta.json`'s
+  regional counts will always undercount somewhat against the true regional distribution;
+  the unclassified bucket's own size is itself an observable signal of how much the
+  keyword list needs to grow, and is reported alongside the named regions (see
+  `observability/DESIGN.md`'s sprint 033 addition) rather than silently folded into one of
+  them.
+- **(Sprint 033)** No ZIP-code or lat/long-based fallback is used for region
+  classification, only city-name keyword matching against `location` text. A `location`
+  string that carries a ZIP but no recognizable city name (uncommon but possible for a
+  terse address) classifies as unclassified rather than falling back to ZIP lookup. Not
+  built this sprint — see this sprint's Design Rationale for why `geo_ladder.py`'s
+  ZIP/city centroid tables were rejected as overkill for a coarse five-bucket
+  classification; a ZIP-based fallback remains a reasonable future refinement if the
+  unclassified bucket proves large in practice.
 - **(Sprint 027)** `Opportunity` still has no `kind` field, by deliberate scope decision
   (this sprint's Scope explicitly excludes any `Opportunity`/taxonomy schema change).
   This is what forces `DEADLINE_FIRST_TYPES` extension (rather than a `kind`-aware
```
