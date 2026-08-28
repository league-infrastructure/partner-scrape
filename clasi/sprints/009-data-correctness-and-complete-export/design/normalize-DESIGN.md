# Normalize

**Owner:** Eric Busboom · **Last reviewed:** 2026-08-28 · **Status:** stable

---

## 1. Purpose

`normalize/` turns a flat stream of canonical `Event`s — many of them duplicates,
recurrences, or partial views of the same real-world thing — into the deduplicated,
taxonomy-tagged `Opportunity` records the site actually publishes. It is a subsystem
because it owns the two hardest judgments in the pipeline: *identity* (which records are
the same thing) and *vocabulary* (which controlled tags apply). Both need
`Event.field_provenance`'s per-field confidence, which no other stage has access to and
which does not survive the mapping to `Opportunity`. It also owns the `Opportunity` shape
itself — the boundary type between the scraper's world and the site's schema.

## 2. Orientation

One entry point: `run.run(events, partners_path, source_org_names=None, today=None,
image_resolver=None) -> list[Opportunity]`. It executes in a fixed order:

1. **Coerce datetimes.** Any timezone-aware `start`/`end` is made naive, in one place.
2. **Split internships out.** `kind="internship"` events bypass both dedup stages.
3. **`collapse_recurring(events, today)`** (`collapse.py`) — group by
   `(source_id, normalized_title)` and fold each group into one `Instance` spanning
   first-to-last date, carrying a repeat count.
4. **`dedup_cross_source(instances)`** (`dedup.py`) — regroup by
   `normalized_title + date + normalized_venue`, *across* `source_id`s, and keep the
   best-scoring record, unioning the contributing `sources`.
5. **Map each survivor to an `Opportunity`** — derive taxonomy tags (`taxonomy.py`), join
   against the site's partner roster (`partners.py`), build a slug, resolve an image
   filename via the injected `image_resolver`.

`instance.py` holds `Instance` — internal bookkeeping (`event`, `sources`,
`repeat_count`, `last_seen`) threaded between stages 3, 4 and 5. `taxonomy.py` is a pure
"text/value in, tags out" layer with no `Event` knowledge.

## 3. Constraints and Invariants

- **Order is collapse → dedup → map, and it cannot be rearranged.** Both selection stages
  need `Event.field_provenance`'s per-field confidence to choose the most complete /
  highest-confidence record. `Opportunity` has no per-field confidence concept, so mapping
  first would destroy the information the selection depends on. Collapsing before
  deduping also shrinks the set cross-source dedup must compare.
- **Two distinct notions of identity exist and must not be conflated.** `model.py`'s
  acquisition `identity_key()` answers "have we seen this exact record from this source?";
  `dedup.cross_source_identity()` answers "is this the same real-world event another org
  also listed?" and is deliberately coarser. Using the acquisition key for cross-source
  merging would never merge anything; using the coarse key for acquisition would collapse
  genuinely distinct records.
- **`dedup.py` must not import `collapse.py`.** `collapse.py` calls into `dedup.py`'s
  scoring helpers. `Instance` lives in its own module precisely so both can import it
  without creating a cycle.
- **`partners.json` is read-only.** It is the site's curated partner roster, an *input*.
  A no-match keeps the org name and leaves `partner_id` unset — `find_partner` returns
  `None` and never raises. Writing to it from here would let the scraper silently mutate
  hand-curated data.
- **`normalize/` never imports `export/`.** This is the codebase's stated one-way
  dependency direction. The image resolver arrives as a plain `Callable[[str], str]`,
  constructed by `pipeline.run()`, specifically so this rule holds — importing
  `EventImageDownloader` directly here would invert it.
- **Timezone coercion happens exactly once, here.** Adapters are supposed to emit naive
  San-Diego-wall-clock datetimes, but several structured-API adapters (BiblioCommons,
  Lever) emit aware ones. Mixing them makes `min()`/`max()` in collapse and dedup raise
  and crashes the entire run. Coercing in one place means no single adapter's
  tz-awareness can break the pipeline; removing it reintroduces a whole-run crash.
- **`kind="internship"` events bypass both collapse and dedup.** Both stages' identity
  assumptions (same title in the same window is a recurrence; same title+date+venue is
  the same event) are wrong for job postings, where near-identical titles are genuinely
  distinct openings.
- **Deliberate non-goal — no date filtering.** Whether a record is current or upcoming is
  `export/`'s judgment. `run()` returns everything that survived deduplication, dated or
  not.
- **`taxonomy.py` functions take plain text and values, never an `Event`.** Building the
  input blob from an `Event` is `run.py`'s job (`build_taxonomy_text`). Passing an `Event`
  in would couple a pure, trivially-testable rule layer to the record shape.

## 4. Design

**`Instance` as the carrier.** The pre-existing exploration script used a magic sidecar
dict key for repeat count. `Instance` makes that an explicit type: it lets repeat-count
and contributing-source bookkeeping travel from collapse through dedup into mapping
without touching either `Event` (owned by `model.py`, unchanged) or `Opportunity` (which
gains only what the site schema documents plus one explicit `sources` field).

**Collapse keys on `source_id`, not org name.** The registry is one TOML file per
organization, so `source_id` is already a stable per-org key. The human-readable name is
only needed later, for the partner join, which must match `partners.json`'s own `name`
field — hence `source_org_names`, a `{source_id: org_name}` map the caller (which already
loaded the registry to dispatch sources) passes through. When a `source_id` is absent
from the map, the `source_id` itself is used; it usually will not match a partner entry,
which is the documented, non-fatal case.

**Dedup scoring.** `score_event` ranks candidates by completeness and per-field
confidence; `pick_best` selects the winner and the `sources` sets are unioned, so an
`Opportunity` records every organization that listed it even though only one record's
field values survive.

**`Opportunity` is the site's schema, not the scraper's.** Its ~24 fields mirror the
`stem-ecosystem` Opportunities table (slug, partner_id, availability, age_grade_level,
cost_range, opportunity_type, areas_of_interest, contact fields, logo/image, …), plus one
non-schema field, `sources`, which is this subsystem's own bookkeeping and which
`export/writer.py` drops on serialization.

**Internships get their own availability rule.** `_internship_availability` and
`WORK_BASED_LEARNING_TYPE` exist because a job posting's `date_start` is the
posting-observed date — routinely in the past for a still-open role — so the ordinary
"ends today or later" rule would expire it immediately. `export/writer.py` implements the
matching filter exception.

**Taxonomy is keyword rules, not ML.** `taxonomy.py` ports the pre-existing script's
`AREA_KEYWORDS` / `AGE_KEYWORDS` / cost / time-of-day rules into pure functions.
`derive_time_of_day` is the one deliberate reimplementation: it reads `Event.start`'s
real `datetime` rather than re-parsing a text time string. These rules are also the
fail-open fallback `enrich/` uses when the LLM is unavailable.

## 5. Interfaces

### Exposes
- **`run(events, partners_path, source_org_names=None, today=None, image_resolver=None)
  -> list[Opportunity]`** — the subsystem's single entry point. Mutates input `Event`s'
  `start`/`end` in place (tz coercion). Never raises for an unmatched partner or an
  undated record. `image_resolver=None` leaves `image_src` empty with zero network
  access.
- **`Opportunity`** — the boundary dataclass between scraper and site. `sources` is
  internal bookkeeping and is not part of the site schema.
- **`taxonomy.derive_areas_of_interest`, `classify_opportunity_type`,
  `derive_age_grade_level`, `map_cost`, `derive_time_of_day`, `build_taxonomy_text`,
  `tag_by_keywords`** — pure classification rules, also consumed by `enrich/` as its
  fallback.
- **`partners.normalize_org_name`** — pure string normalization, also consumed by
  `discovery.hub_scan` for candidate dedup.
- **`partners.load_partners` / `find_partner`** — read-only partner roster lookup.

### Consumes
- **`Event`, `Provenance`, `normalize_title` (from `model.py`)** — the input record and
  its shared title-normalization rule. See the root `partner_scrape/DESIGN.md`.
- **The site's `partners.json`** — read-only, at a path the caller supplies (defaulting to
  `{site_dir}/src/data/partners.json`).
- **An `image_resolver` callable** — supplied by `pipeline.run()`, backed by
  `export.images.EventImageDownloader.download`. Consumed as a bare callable so no import
  edge to `export/` exists. See `export/DESIGN.md`.

## 6. Open Questions / Known Limitations

- Cross-source identity is `normalized_title + date + normalized_venue`. Two orgs
  describing the same event with materially different titles will not merge; two genuinely
  different events sharing a title, date, and venue will.
- The timezone convention is "naive San Diego wall clock", enforced by coercion rather
  than by carrying a real timezone. `_TZ_OFFSET = "-07:00"` is a hard-coded literal, so
  exports are wrong across the DST boundary.
- Keyword taxonomy rules were ported from an exploration script and spot-checked, not
  validated against a labelled set. Where the LLM and the keyword rules disagree, no
  measurement exists of which is right.
- Slug construction truncates, so distinct records can still collide;
  `export/writer.py` carries a defensive uniqueness pass to catch that. The collision is
  better fixed here.
- Several `Opportunity` fields the site schema defines (`specific_attention`,
  `financial_support`, `ngss_aligned`, the contact fields) are populated only from
  `taxonomy_defaults` in the registry, if at all. Nothing derives them.
