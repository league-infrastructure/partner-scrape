# Normalize

**Owner:** Eric Busboom · **Last reviewed:** 2026-08-30 · **Status:** stable

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

**(Sprint 014)** No code in this subsystem changes this sprint. It is included in this
sprint's design overlay because two of its existing, already-tested behaviors are
exercised at meaningfully higher volume and get an explicit sprint-time decision
recorded against them, not a new mechanism: the cross-source dedup that §3's
collapse-then-dedup ordering constraint governs, now matched against a park-wide
institutional calendar (Balboa Park) for the first time; and the no-partner-match display
path in `partners.py`, now hit by roughly 20 newly-registered sources, several without a
`partners.json` entry. See §6.

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

**(Sprint 015, ticket 007, issue 27 item 2)** `DEADLINE_FIRST_TYPES` generalizes the
internship-only special case above to a set: `{WORK_BASED_LEARNING_TYPE, "Competitions"}`.
Both `export/writer.py`'s currency check (`is_current_or_upcoming`) and its export sort
key (`_export_sort_key`) now branch on `opportunity_type in DEADLINE_FIRST_TYPES` instead
of `== WORK_BASED_LEARNING_TYPE`, and `_to_opportunity`'s availability-text derivation
does the same — `_internship_availability` (kept its name; its "Apply by <date>"/"Rolling
— apply anytime" text is not internship-specific in behavior, only in the historical
name) now applies whenever `is_internship or opportunity_type in DEADLINE_FIRST_TYPES`,
computed *after* `opportunity_type` is resolved so the check can see the final,
LLM-or-fallback-classified value. The `is_internship`/`kind` bypass used elsewhere
(collapse, dedup, forced `opportunity_type`) is untouched — this generalization is
availability-text derivation only, one of three call sites (with the currency check and
sort key) reusing one constant instead of three independently hardcoded checks.

Rejected alternative: a new `application_deadline` field, distinct from `date_end`. No
adapter and no LLM-prompt field currently distinguishes a registration/application
deadline from an event's own end date/time for any non-internship record — a new field
would have no real producer this sprint, making it speculative generality. Reusing `end`
is not speculative in the same way: it extends sprint 006's already-shipped
`WORK_BASED_LEARNING_TYPE` convention to one more already-shipped `opportunity_type`
value (`"Competitions"`, added ticket 006 this sprint), not a new mechanism.

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

**(Sprint 015, ticket 006, issue 27)** `OPPORTUNITY_TYPE_KEYWORDS` gains one new rule,
`\bcamps?\b` → `"Camps"` — word-bounded so it cannot fire inside "campus"/"campaign"/
"campfire"/"campground"/"encampment", spot-checked against this project's own fixture
titles (`"Ocean Explorers Camp"`, `"Summer Camp Registration Is Open!"`, `"Farm Camp"`,
`"Camp-o-Saurus"`). `"Competitions"` deliberately gets **no** keyword rule, extending
the same false-positive rationale that already excludes `"Funding Opportunities"`: the
obvious candidate, `competit*` (competition/competitive), matches a real,
already-fixtured title — `test_adapters_leaguesync.py`'s `"Competitive Robotics Summer
Warm Up"` is an ordinary registration-based League *class*, not a competition. Other
candidates considered (`tournament`, `hackathon`) don't appear anywhere in this
codebase's fixtures/adapters to spot-check against, and a bare `fair` is already too
ambiguous — county/health/book fairs, plus `career fair`/`job fair`/`college fair`
already claimed by the Career Connections rule, all share the word. `"Competitions"` is
LLM-only (`enrich/llm_client.py`'s `_OPPORTUNITY_TYPE_VALUES`); the keyword fallback
keeps defaulting ambiguous titles to `DEFAULT_OPPORTUNITY_TYPE`, the safer failure mode
during an LLM outage. See `enrich/DESIGN.md`'s own sprint 015 addendum for the
`PROMPT_VERSION` 1 → 2 bump this pairs with, and `site/src/components/
OpportunityFilters.astro`'s hardcoded facet list (updated by this ticket in this repo;
the sibling `../stem-ecosystem` repo's identical copy is out of this ticket's write
scope).

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
  different events sharing a title, date, and venue will. **(Sprint 014)** Registering
  Balboa Park's park-wide TEC calendar alongside the individual institutions it covers
  (Fleet, Nat, and others already scraped directly) exercises exactly this limitation for
  the first time at meaningful scale: an event Balboa Park titles generically (e.g. "Member
  Preview Night") and the hosting institution titles specifically will not merge, and will
  publish as two `Opportunity` records for one real event. This is accepted, not fixed, this
  sprint — no new dedup mechanism is introduced; a stronger cross-source identity (e.g.
  venue-plus-date-only, or a fuzzy title match) is deferred to a future sprint if the
  duplication turns out to be material in practice. **(Sprint 015 ticket 004, re-measured.)**
  Sprint 014 ticket 004 found a real title+date match this limitation predicted didn't
  actually explain — Balboa Park's and Fleet's own "Educator Open House" (2026-09-24) both
  matched on title *and* date but failed to merge only because `fleet-science-center.toml`'s
  `listing_html` adapter left `Event.location` empty. `adapters/listing_html.py` gained a
  `default_location` registry fallback (see that module's own Sprint 015 addendum) and Fleet
  now carries a real, non-empty venue on every event. Re-measuring live against the same
  8-source set still produced **0 cross-source collapses**, including for this exact
  "Educator Open House" pair — but the mechanism has moved to precisely the
  `normalized_venue` limitation this entry already names: `normalize_title()` only
  lowercases/strips punctuation/collapses whitespace, so Balboa Park's TEC-supplied venue
  string (`"Fleet Science Center, 1875 El Prado, San Diego, CA"`) and Fleet's configured
  `default_location` (`"1875 El Prado, San Diego, CA 92101"`) normalize to two different
  strings for the same physical address (org-name prefix vs. ZIP suffix, formatted
  differently by each source). No `normalize/` code changed this sprint — an address-level
  canonicalization or fuzzy-venue match is the same future-sprint deferral this entry
  already anticipated, now with a concrete, reproducible example instead of a hypothetical
  one. See sprint 015 ticket 004's Notes for the full measurement.
- **(Sprint 014)** `partners.py`'s `find_partner` no-match behavior (keep the org name,
  leave `partner_id` unset — already the tested, non-fatal path) is now exercised by
  design, not just as an edge case: several of this sprint's ~20 newly-registered sources
  (issue 25) have no corresponding `partners.json` entry, and expanding the roster to
  cover them is explicitly out of this sprint's scope (issue 32's job). Those
  organizations' `Opportunity` records display with a bare org name and no logo/partner
  link until issue 32 (or a later sprint) adds them to the roster. This is a deliberate,
  accepted product decision for this sprint, not a defect — see `sprint.md`'s Scope and
  SUC-007.
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
