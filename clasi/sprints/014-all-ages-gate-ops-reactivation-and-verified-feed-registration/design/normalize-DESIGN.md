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
   filename via the injected `image_resolver`. Sprint 009: the slug is now a stable
   cross-run identity (unique link, else title+date — see Design below), not a
   within-this-export display key, because `export/partner_log.py` needs the same slug
   across separate runs to recognize "same event" for its append-only log.

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
- **(Sprint 012) A naive datetime's export offset is resolved per-date, not
  hard-coded.** `_iso()` previously appended a constant `_TZ_OFFSET = "-07:00"`
  (Pacific Daylight Time) to every naive datetime, which was wrong for the
  roughly four months a year (early November - mid-March) San Diego is on
  Pacific Standard Time (`-08:00`) — a real correctness bug, not a display
  nicety, since the offset is part of the published ISO 8601 string every
  downstream consumer (the site's calendar view, any external agent reading
  `public/data/`) parses. `_iso()` now localizes each naive datetime through
  `zoneinfo.ZoneInfo("America/Los_Angeles")` and reads the resulting offset
  back off it, so `-07:00`/`-08:00` falls out of which side of the DST
  boundary the date lands on, correct for any date including future years
  (IANA's tzdata, not a hand-maintained table, tracks DST rule changes). An
  already-aware datetime's own offset is still left untouched — this rule is
  unchanged.
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
- **`opportunity_type` selection follows the same LLM-wins-when-present pattern as every
  other classification field** (sprint 009): `_to_opportunity` uses `event.opportunity_type`
  when `"opportunity_type" in event.field_provenance` (enrichment ran, LLM or fallback),
  else `classify_opportunity_type(event.title)` directly (enrichment skipped entirely,
  e.g. `--no-enrich`) — mirroring `cost_range`/`areas_of_interest`/`age_grade_level`/
  `time_of_day` exactly. Internships remain forced to `WORK_BASED_LEARNING_TYPE` by `kind`,
  unconditionally, checked before either branch.
- **The event slug is now a cross-run identity, not a within-export display key**
  (sprint 009). Previously `Opportunity.slug` existed only to be unique *within one export
  snapshot* (`org[:40]_title[:60]_date`); it is now also how `export/partner_log.py`
  recognizes "the same event as last run" across separate pipeline invocations, so its
  algorithm changed to the rule `export/DESIGN.md`'s `partner_log.py` needs — see Design
  below. Both uses are still served by one field; there is no second slug concept.

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
fail-open fallback `enrich/` uses when the LLM is unavailable. Sprint 009 adds
`classify_opportunity_type` to that same fail-open role (see `enrich/DESIGN.md`) without
changing its rules: no `"Funding Opportunities"` keyword rule is added, preserving the
existing, deliberate false-positive rationale documented on
`OPPORTUNITY_TYPE_KEYWORDS` — only the LLM path can produce that value; the keyword
fallback keeps defaulting ambiguous titles to `"Out-of-school Programs"`, which is the
safer failure mode during an LLM outage.

**The DST-transition fold convention (sprint 012).** `zoneinfo`-based
localization is unambiguous everywhere except the two hours a year the
local clock itself is ambiguous or nonexistent: the repeated 1am-2am
hour when clocks fall back in November, and the skipped 2am-3am hour
when clocks spring forward in March. Python's `fold` attribute
disambiguates the first case (`fold=0` is the pre-transition,
earlier-UTC occurrence; `fold=1` is the post-transition,
later-UTC occurrence) and `zoneinfo` already applies a documented
convention for the second (a nonexistent local time is treated as if
the transition had not yet happened, i.e. resolved to the pre-transition
offset). `_iso()` adopts `fold`'s own default (`fold=0`, since no
adapter this project has ever produces a `datetime` with `fold` set
explicitly) rather than inventing a second convention on top of it —
every naive datetime in this pipeline already carries `fold=0` by
construction (the dataclass default), so the *practical* behavior is:
an ambiguous November timestamp resolves to its earlier (Daylight Time,
`-07:00`) occurrence, and a nonexistent March timestamp resolves to the
pre-transition (`-08:00`) offset `zoneinfo` itself picks. Both are
edge cases affecting at most one calendar hour, twice a year, for
events whose adapters extract only a date+time, never a UTC instant —
the residual ambiguity (which of two real clock readings a "1:30am"
event meant) is a source-data limitation this fix does not attempt to
resolve beyond picking one documented, tested, consistent answer.

**Why `Opportunity.slug`'s algorithm changed (sprint 009).** The previous algorithm
(`org[:40]_title[:60]_date`, all truncated) existed only to be unique within one export
snapshot, and `export/writer.py` already carries a defensive collision pass because
truncation could still collide — a known, documented limitation. Issue 15 needs something
stronger: an identity that survives *across* runs, so the new per-partner append-only log
(`export/partner_log.py`) can tell "this is the same event, possibly updated" from "this
is a new event." The new rule — `slugify(link)` when a per-event link exists, else
`slugify(title) + date` — is a *different property* (cross-run stability, not just
within-run uniqueness) than the old one, so reworking `Opportunity.slug` in place (rather
than adding a second field) keeps exactly one slug concept instead of two. The org/partner
prefix is dropped because slugs are now computed and stored *inside* a partner-scoped
directory (`export/partner_log.py`'s `<partner-slug>/opportunities.jsonl`) — the partner
is already implied by where the slug lives, so encoding it into the string itself would be
redundant. `export/writer.py`'s existing `_dedupe_slugs` defensive pass is unchanged and
still backstops the flat, cross-partner legacy export against the rarer
title+date collision case.

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
  fallback (sprint 009: `classify_opportunity_type` joins this fallback role, unchanged
  rules).
- **`partners.normalize_org_name`** — pure string normalization, also consumed by
  `discovery.hub_scan` for candidate dedup.
- **`partners.load_partners` / `find_partner`** — read-only partner roster lookup.

### Consumes
- **`Event`, `Provenance`, `normalize_title` (from `model.py`)** — the input record and
  its shared title-normalization rule. See the root `partner_scrape/DESIGN.md`.
- **`model.slugify`** (sprint 009) — the shared text-to-slug primitive `_to_opportunity`
  now uses to build `Opportunity.slug`, promoted to `model.py` because
  `export/partner_log.py` needs the identical function for partner slugs. See the root
  `partner_scrape/DESIGN.md`.
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
  than by carrying a real timezone through the pipeline. **(Resolved, sprint 012)**
  The export-time offset is no longer a hard-coded literal — `_iso()` resolves it per
  datetime via `zoneinfo.ZoneInfo("America/Los_Angeles")`, correct across the DST
  boundary in both directions (see Design, above, for the fold convention on the two
  transition-hour edge cases). The underlying convention itself (coerce to naive at
  ingestion, localize only at export) is unchanged — only the previously-wrong constant
  is fixed.
- Keyword taxonomy rules were ported from an exploration script and spot-checked, not
  validated against a labelled set. Where the LLM and the keyword rules disagree, no
  measurement exists of which is right.
- **(Resolved, sprint 009, with a narrower residual case.)** Slug construction no longer
  truncates and no longer collides within a partner's own directory except in one
  documented edge case: the link-based branch assumes a per-event link is unique to that
  event, not shared by several events on one listing page. If a source's adapter surfaces
  the *listing* page URL as `link` for every event on it (rather than a per-event detail
  URL), those events will collide on the same slug — matching issue 15's own "Known
  trade-off" framing for the title+date fallback, now also possible (rarer) via the link
  branch. Not solved speculatively this sprint; `export/DESIGN.md`'s Open Questions
  tracks it as something to watch once real per-partner logs accumulate.
  `export/writer.py`'s defensive `_dedupe_slugs` pass remains as the backstop for the flat,
  cross-partner legacy export.
- Several `Opportunity` fields the site schema defines (`specific_attention`,
  `financial_support`, `ngss_aligned`, the contact fields) are populated only from
  `taxonomy_defaults` in the registry, if at all. Nothing derives them.
