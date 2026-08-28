---
id: 009
title: Data correctness and complete export
status: done
branch: sprint/009-data-correctness-and-complete-export
use-cases: []
issues:
- 13-classify-opportunity-type-in-enrichment.md
- 15-publish-complete-self-describing-data-export.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 009: Data correctness and complete export

## Goals

Fix a data-correctness bug and then publish the corrected data as a
complete, public export — in that order, because the second issue
publishes the field the first issue fixes.

1. **Classify `opportunity_type` during enrichment** (issue 13). Every
   exported opportunity is currently stamped with the blind default
   `"Out-of-school Programs"` in `normalize/run.py` — the LLM enrichment
   step classifies several other fields but not this one, so 7 of the
   site's 8 type filters (School Programs, Career Connections,
   Work-based Learning, Volunteering, Funding Opportunities, Online,
   Professional Development) are always empty. Add `opportunity_type` to
   `EnrichmentResult` and the LLM prompt using the site's controlled
   vocabulary, map the classified value onto `Opportunity` (keeping the
   existing internships-force-"Work-based Learning" rule), and bump the
   enrichment cache version so already-cached results re-enrich once
   rather than serving stale data with no type.
2. **Publish a complete, self-describing data export** (issue 15). Move
   from today's single flat `opportunities.json` (current+upcoming only,
   overwritten every run — past events are silently lost) to a
   persistent, per-partner storage model: a directory per partner keyed
   by slug, holding that partner's own partner-JSON entry plus an
   append-only `.jsonl` log of opportunities (each line carrying a
   stable `slug` and a `content_hash`, appended only on new-or-changed
   events, never rewritten). A build-time projection step collapses each
   `.jsonl` to one record per slug (last line wins) and generates the
   published `partners.json` (referring out to each partner's files) plus
   each partner's `events.json` (current/upcoming) and a past-events
   file. The result is a public data contract: given `partners.json` +
   each partner's event files, the whole site is reconstructible with no
   other data source.

Sequencing rationale: issue 13 corrects `opportunity_type`; issue 15
then publishes that field as part of the export contract — get the
value right before it becomes public and self-describing. Issue 13 is
small; issue 15 is the substantial piece of this sprint.

Note for detail planning: `docs/design/design.md` (plus per-subsystem
`DESIGN.md`) is being bootstrapped concurrently and `design_docs` is now
`enabled`. This sprint touches `normalize/` and `export/`, both likely
to be documented subsystems by the time this sprint is detail-planned —
expect a `design/` overlay at that point; no overlay is created now.

## Scope

### In Scope

- `normalize/run.py`, `enrich/enricher.py` (or equivalent enrichment
  entry point), and the LLM prompt — add `opportunity_type`
  classification to `EnrichmentResult`, map it onto `Opportunity`
  (issue 13).
- Enrichment cache versioning so existing cached results without
  `opportunity_type` re-enrich once (issue 13).
- A new per-partner directory layout under the data directory (partner
  JSON + append-only opportunities `.jsonl`, keyed by slug) and the
  slug/content-hash identity, dedup, and append rules defined in issue
  15 (unique-link-first, title+date fallback for slug; normalized-field
  hash for content).
- A build/assembly step that projects the `.jsonl` logs into published
  `partners.json` + per-partner `events.json` (current/upcoming) and a
  past-events file (issue 15).
- Reworking `partner_scrape/export/writer.py` to read/write the new
  layout in place of the current single flat
  `src/data/opportunities.json` and add `partners.json` to the
  publishable contract (`ads.json`/`scrape-meta.json` semantics
  unchanged).

### Out of Scope

- The discovery/agent-facing layer that points at this export
  (`llms.txt`, the "how to consume our data" page, the LLM page) — that
  is issue 16, sprint 010, which explicitly depends on this sprint's
  export landing first.
- The partner-facing event-publishing strategy (schema.org JSON-LD,
  `.well-known` pointer, OpenActive, etc.) — issue 17, sprint 010.
- Deciding whether the Astro site itself is refactored to consume the
  new per-partner shape, versus treating it as an additional published
  artifact alongside the existing build input — left as an open question
  in issue 15 for detail planning.
- Final directory/URL layout and reference format inside `partners.json`,
  and how far back "past events" are retained for publication — both
  flagged as open questions in issue 15, to be resolved during detail
  planning, not here.
- Robot teams work (issue `robot-teams-...`) — entirely independent,
  sprint 011.

## Test Strategy

Fixture-based, hermetic, matching the existing suite's convention (905
tests, one module per source module, no network, `uv run pytest`) — no
new pattern is introduced.

- `enrich/llm_client.py`, `enrich/cache.py`, `enrich/enricher.py`,
  `model.py`, `normalize/run.py`: extend each module's existing test
  file with cases for the new `opportunity_type` field — schema
  generation includes it, `FixtureLLMClient` responses can set it,
  cache round-trips it, the cache-version bump forces exactly one
  re-enrichment for a pre-existing entry missing it, and
  `_to_opportunity`'s precedence check (LLM value wins when
  `field_provenance` is set, else `classify_opportunity_type` fallback)
  is asserted the same way the existing `cost_range`/`areas_of_interest`
  precedence tests already are.
- `normalize/run.py`'s slug rework: unit tests for both branches (link
  present → `slugify(link)`; link absent → `slugify(title)` + date), and
  a regression test confirming two different partners' same-day,
  same-titled events no longer collide now that the org prefix is
  dropped (covered by `export/writer.py`'s existing `_dedupe_slugs`
  backstop, asserted directly).
- New `export/partner_log.py`: its own test module — directory layout,
  `partner.json` write, the three-way append/skip/update decision table
  (new slug, same slug + same hash, same slug + different hash), and
  strict append-only behavior (existing lines are never rewritten,
  asserted by content comparison before/after a second write).
- New `export/publish.py`: its own test module — last-line-wins
  collapse over a multi-line `.jsonl` fixture, the current/past split
  (reusing the same `today`-parameterized cases `writer.py`'s existing
  `_is_current_or_upcoming` tests already cover, including the
  Work-based Learning exception), and the join against a fixture
  `partners.json` including an unmatched-partner and a
  zero-events-partner case.
- `export/mirror.py`'s extended recursive copy: a test target checkout
  receiving the `public/data/` tree, including the "target already has
  a byte-identical file" skip case the existing image-mirroring test
  already establishes the pattern for.
- One small integration-style test (`tests/test_partner_export_flow.py`
  or similar) exercising ingest → projection end to end against
  `tmp_path`: two synthetic runs with an unchanged event, a changed
  event, and a newly-appearing event, asserting the published
  `events.json`/`past-events.json` reflect exactly the expected
  last-line-wins state after each run. This is the one test that
  exercises the new modules together rather than in isolation.
- No test requires `ANTHROPIC_API_KEY` or a live LLM call — every LLM
  path is exercised through `FixtureLLMClient`, matching the existing
  suite.

## Architecture

**Substantial** — issue 15 introduces a new persistent per-partner
storage layer (a new data model: append-only per-partner `.jsonl` logs
plus a build-time projection into a new published `public/data/` tree),
touches 3+ modules across three subsystems (`enrich/`, `normalize/`,
`export/`, plus the shared `model.py`), and adds new intra-package
dependencies (a new `export/` module reusing `normalize.partners`'
partner-join and a shared `model.slugify` primitive). Issue 13 alone
would already cross the substantial threshold on its own (it adds a
field to two dataclasses — `Event` and `EnrichmentResult` — a data-model
change) even before issue 15 is considered.

This project has opted into the persistent per-subsystem design-doc set
(`design_docs` enabled), so per the `architecture-authoring` skill's
Mode 2a, the full architecture write-up for a substantial sprint lives
in this sprint's `design/` overlay, not in this section. This section is
the pointer and summary; the overlay is the source of truth tickets are
derived from.

**Overlay documents edited** (`clasi/sprints/009-data-correctness-and-complete-export/design/`):

- `DESIGN.md` — root overview (`partner_scrape/DESIGN.md`): documents the
  new `opportunity_type` field on `Event`, the new shared `slugify()`
  utility on `model.py`, and the new per-partner accumulation/publish
  step in the pipeline-shape diagram.
- `enrich-DESIGN.md` (`partner_scrape/enrich/DESIGN.md`): `opportunity_type`
  joins the classification fields; the enrichment cache gains an
  explicit schema version.
- `normalize-DESIGN.md` (`partner_scrape/normalize/DESIGN.md`):
  `opportunity_type` precedence in `_to_opportunity`; `Opportunity.slug`'s
  algorithm is reworked to the link-first/title+date cross-run identity
  rule, dropping the org-name prefix.
- `export-DESIGN.md` (`partner_scrape/export/DESIGN.md`): two new modules
  (`partner_log.py`, `publish.py`), `writer.py`'s shared helpers promoted
  for reuse, and `mirror.py`'s copy logic extended to a directory tree.
- `store-DESIGN.md` (`partner_scrape/store/DESIGN.md`): notes the new
  `Event.opportunity_type` field's serialization parity in
  `_event_to_dict`/`_event_from_dict`, and explicitly distinguishes the
  unwired `EventStore` (raw, pre-normalization `Event`s, acquisition
  identity) from the new `export/partner_log.py` (finished
  `Opportunity`s, publish identity) so the two are not mistaken for
  overlapping solutions to the same problem.

**What changed, in one paragraph per issue:** Issue 13 threads a new
`opportunity_type` classification through the existing LLM-enrichment
machinery exactly the way `cost_range`/`areas_of_interest`/etc. already
work — new field on `EnrichmentResult` and `Event`, new prompt guidance,
applied via the existing classification-field pass, fallback via
`normalize.taxonomy.classify_opportunity_type` on LLM failure, selected
in `normalize/run.py` via the same `field_provenance`-presence check
every other classification field already uses — plus an explicit cache
schema version so already-cached entries (which predate this field) are
treated as a miss exactly once. Issue 15 adds a new accumulation layer
between "normalize produced this run's Opportunities" and "the site
export" tuple: a per-partner, slug-keyed, append-only `.jsonl` log that
persists every Opportunity ever seen (never overwritten, never pruned)
plus a build-time projection that collapses each log to its latest state
per event, splits current/upcoming from past, and publishes a partner
roster plus per-partner event files as a new, additive `public/data/`
contract — the existing `src/data/opportunities.json` flat export
continues unchanged, so nothing that currently reads it breaks.

**Design Rationale (highlights — full detail, with alternatives
considered, is in the overlay documents):**

- **Per-partner directory keyed by the joined partner identity, not raw
  scraper `source_id`.** An `Opportunity` can carry multiple contributing
  `source_id`s (`Opportunity.sources`, from cross-source dedup) but
  already resolves to exactly one `partner_name`/`partner_id` via the
  existing partner join in `_to_opportunity`. Keying by `source_id`
  would leave that join's result unused and raise an unanswerable
  question (which of several sources "owns" a merged record's persisted
  copy?); keying by the already-resolved partner identity has no such
  ambiguity and reuses code that already exists.
- **`Opportunity.slug`'s algorithm is unified onto the new cross-run
  identity rule** (unique link, else title+date; no org prefix, since
  slugs are now scoped to a partner's own directory) rather than
  maintaining two differently-shaped "slug" concepts under one name.
  `Opportunity.slug` values in `opportunities.json` will differ from
  today's after this ships — a non-issue, since that file is overwritten
  every run and no cross-run slug stability was ever promised. The
  existing `_dedupe_slugs` defensive pass in `writer.py` is kept
  unchanged as the backstop for the (now rarer) cross-partner
  title+date collision case.
- **The new public/data/ tree is additive, not a replacement.** Issue
  15 explicitly poses "replace the Astro build input" vs. "publish an
  additional artifact" as an open question for detail planning; this
  sprint resolves it as additive, because refactoring the Astro site's
  own build is out of this sprint's scope (a separate repo) and nothing
  yet consumes the new contract (issue 16, sprint 010, is what will).
- **The persistent accumulation store is new, not a reuse of the
  unwired `store/event_store.py`.** That store persists raw,
  pre-normalization `Event`s keyed by acquisition identity, for a
  different purpose (skip re-crawling). The new store persists finished,
  post-dedup `Opportunity`s keyed by publish identity, for a different
  purpose (never lose a published event). Forcing one to serve both
  would conflate two identity concepts `normalize/DESIGN.md` already
  says must not be conflated.

**Open Questions carried into implementation** (full list in the
`export-DESIGN.md` overlay): the exact retention policy for
`past-events.json` once real history accumulates (published unbounded
for now — the store starts empty this sprint, so this is not an
immediate problem); the "shared listing page" edge case for link-based
slugs (documented as a known limitation, matching issue 15's own
"Known trade-off" framing, not solved speculatively).

**Judged out of scope:** `normalize/run.py`'s hard-coded `_TZ_OFFSET =
"-07:00"` (the DST bug) touches exported date correctness, which is
this sprint's theme, but it is orthogonal to both issues actually in
scope (it affects `_iso()` formatting, not classification or storage)
and fixing it doesn't unblock either issue 13 or 15. Recommended as a
follow-up issue rather than folded in here — flagged to the team-lead
in this planning session's report rather than silently dropped.

### Migration Concerns

- **Issue 13 forces exactly one full-corpus re-enrichment.** The
  enrichment cache is content-hash-keyed over *input* fields, which
  don't change when `EnrichmentResult`'s *output* shape gains a field —
  without the explicit schema-version bump, existing cache entries would
  either silently omit `opportunity_type` forever or raise on
  deserialization. The version bump makes every pre-existing entry a
  one-time miss. This is real, recurring-pipeline Anthropic API spend
  proportional to the corpus size, incurred once on the first run after
  this ships, not a bug.
- **Issue 15's persistent store starts empty; no backfill.** Today's
  `opportunities.json` was overwritten every run and never retained
  history, so there is nothing to migrate into the new `.jsonl` logs —
  they simply start accumulating from the first run after deployment.
  `past-events.json` will be near-empty for a while; that is the correct
  initial state, not a defect.
- **The legacy `src/data/opportunities.json` export is unchanged and
  keeps shipping every run**, so the current Astro site build is never
  at risk from this sprint even if the new `public/data/` tree has a
  bug — the two paths are independent once `Opportunity` is produced.
- **`export/mirror.py`'s target-checkout contract changes**: it now also
  owns copying a directory tree (`public/data/`), not only a flat
  allowlist of files plus one images directory. Existing mirror targets
  (this repo's own `site/`) need no manual action — the new tree is
  created under `public/data/` on the next mirrored run the same way the
  images directory already is.

## Use Cases

### SUC-001: Classify opportunity_type via LLM enrichment
Parent: UC-005

- **Actor**: Engine
- **Preconditions**: A non-internship Event has been discovered, fetched,
  and extracted, and is not gated out before reaching enrichment.
- **Main Flow**:
  1. `LLMEnricher` sends the Event's known fields to the LLM, which now
     also classifies `opportunity_type` into one of the site's
     controlled-vocabulary values (`Out-of-school Programs`, `Online`,
     `Professional Development / Conferences`, `School Programs`,
     `Career Connections`, `Volunteering`, `Funding Opportunities`).
  2. The result is applied to the Event via `Event.set("opportunity_type",
     ..., source="llm_enrichment", confidence=0.7)`, alongside the other
     classification fields.
- **Postconditions**: The Event carries an LLM-derived `opportunity_type`
  with a `field_provenance` entry.
- **Error Flows**: LLM call fails (any exception) → fall back to
  `normalize.taxonomy.classify_opportunity_type(event.title)`, applied
  with `source="taxonomy_fallback"`, `confidence=0.3` — matching every
  other classification field's existing fail-open behavior.
  `kind="internship"` Events bypass this entirely, unchanged.
- **Acceptance Criteria**:
  - [ ] `EnrichmentResult` and `Event` both gain an `opportunity_type`
        field; `ENRICHMENT_JSON_SCHEMA` includes it automatically
        (generated from the dataclass, per `llm_client.py`'s existing
        convention).
  - [ ] The LLM prompt documents the controlled vocabulary and instructs
        `Out-of-school Programs` as the default when nothing more
        specific applies.
  - [ ] On LLM failure, the fallback uses the existing
        `classify_opportunity_type` (title-only, unchanged rules — no
        `Funding Opportunities` keyword rule is added, preserving that
        function's documented false-positive rationale).

### SUC-002: Apply classified opportunity_type with correct fallback precedence
Parent: UC-005

- **Actor**: Engine
- **Preconditions**: An Event has survived collapse/dedup and is being
  mapped to an `Opportunity`.
- **Main Flow**:
  1. `_to_opportunity` checks whether `"opportunity_type"` is present in
     `event.field_provenance`.
  2. If present (enrichment ran, LLM or fallback), use `event.opportunity_type`.
  3. If absent (`--no-enrich`, or any future path that skips enrichment),
     use `classify_opportunity_type(event.title)` directly, matching
     today's behavior exactly.
  4. Internships remain forced to `Work-based Learning` by `kind`,
     unconditionally, unaffected by any of the above.
- **Postconditions**: Every exported `Opportunity` has an `opportunity_type`
  reflecting the best available classification, not a blind default.
- **Error Flows**: None beyond SUC-001's — this step never fails, it only
  selects between two already-computed values.
- **Acceptance Criteria**:
  - [ ] `_to_opportunity`'s `opportunity_type` selection mirrors the
        existing `cost_range`/`areas_of_interest`/`age_grade_level`/
        `time_of_day` precedence pattern exactly.
  - [ ] `--no-enrich` runs are unaffected: `opportunity_type` still comes
        from `classify_opportunity_type(title)` alone.
  - [ ] A regression test confirms a title like "Bird Walk at Grant Park"
        does not classify as `Funding Opportunities` under either path.

### SUC-003: Re-enrich cached events once after a classification schema change
Parent: UC-005

- **Actor**: Engine
- **Preconditions**: An `EnrichmentCache` entry exists from before
  `opportunity_type` was added to `EnrichmentResult`.
- **Main Flow**:
  1. `EnrichmentCache.lookup` compares the entry's stored schema version
     against the current `_CACHE_SCHEMA_VERSION`.
  2. A mismatch (or a missing version, for pre-existing entries) is
     treated as a cache miss, exactly like a `content_hash` mismatch.
  3. The Event is re-enriched, and the fresh entry is stored at the
     current schema version.
- **Postconditions**: Every Event re-enriches at most once across the
  version bump; subsequent runs cache-hit normally.
- **Error Flows**: None beyond SUC-001's ordinary fail-open path.
- **Acceptance Criteria**:
  - [ ] A cache entry written before this sprint (no `schema_version`
        key, or an older one) is treated as a miss, not a
        deserialization error.
  - [ ] A cache entry written after this sprint round-trips normally on
        the next lookup (no repeated re-enrichment).

### SUC-004: Derive a stable, partner-scoped event identity
Parent: UC-006

- **Actor**: Engine
- **Preconditions**: An Opportunity is being constructed from a
  surviving, deduplicated Event/Instance.
- **Main Flow**:
  1. If the Opportunity's `link` (`registration_url` or `url`) is
     non-empty, the slug is `slugify(link)`.
  2. Otherwise, the slug is `slugify(title) + "_" + <start-date-or-last-seen>`.
  3. No partner/org prefix is included — slugs are scoped to the
     partner's own directory (SUC-005), so the partner is already
     implied.
- **Postconditions**: `Opportunity.slug` is a stable identity that
  survives content edits when a unique link exists, matching issue 15's
  cross-run identity rule.
- **Error Flows**: Two distinct events sharing a link (a shared listing
  page with no per-event URL) or coincidentally identical title+date
  within one partner will collide on this slug — a documented, accepted
  limitation (issue 15's own "Known trade-off"), not silently
  swallowed: `writer.py`'s existing `_dedupe_slugs` pass still catches
  it for the flat legacy export.
- **Acceptance Criteria**:
  - [ ] `slugify()` is a shared function on `model.py`, used by both the
        event slug (here) and the partner slug (SUC-005).
  - [ ] Existing `normalize/run.py` and `export/writer.py` tests are
        updated for the new slug shape; no test asserts the old
        org-prefixed shape.

### SUC-005: Persist scraped opportunities into a per-partner append-only log
Parent: UC-006

- **Actor**: Engine
- **Preconditions**: `normalize.run()` has produced this run's
  `Opportunity` list.
- **Main Flow**:
  1. For each Opportunity, resolve its partner slug (from `partner_id`/
     `partner_name`, via `slugify`) and its event slug (SUC-004).
  2. Compute `published_content_hash(opportunity)` over the published
     schema fields (title, description, dates, location, cost_range,
     opportunity_type, age_grade_level, areas_of_interest, time_of_day,
     link — excluding identity/bookkeeping fields like `slug` and
     `sources`).
  3. Read that partner's existing `opportunities.jsonl` (if any).
  4. Skip if a line with the same `(slug, content_hash)` already exists.
     Append a new line if the slug is new, or if the slug matches but
     the hash differs.
  5. Write/update that partner's `partner.json` from the curated
     partner record.
- **Postconditions**: The partner's `.jsonl` log reflects this run's
  new-or-changed events, with every prior line intact (append-only,
  never rewritten).
- **Error Flows**: A partner with no match in the curated `partners.json`
  keeps its org name, matching `find_partner`'s existing non-fatal
  behavior — its directory still accumulates normally.
- **Acceptance Criteria**:
  - [ ] Re-running with unchanged input writes no new lines.
  - [ ] A changed event (same slug, different content) appends a new
        line; the old line is still present afterward.
  - [ ] A dry run (`--dry-run`) writes nothing to the persistent store,
        matching every other export step's `dry_run` contract.

### SUC-006: Publish a complete per-partner data export
Parent: UC-006

- **Actor**: Engine / Operator
- **Preconditions**: One or more per-partner `.jsonl` logs exist (from
  any number of prior runs, not only the current one).
- **Main Flow**:
  1. For every partner in the curated `partners.json` (all of them, not
     only ones with events), resolve its partner slug.
  2. If that partner has an accumulated log, collapse it to one record
     per event slug (last line wins).
  3. Split into current/upcoming vs. past using the same rule
     `writer.py`'s `_is_current_or_upcoming` already implements
     (including the Work-based Learning exception), reused rather than
     reimplemented.
  4. Write `public/data/partners/<slug>/events.json` and
     `.../past-events.json` for that partner.
  5. Write the top-level `public/data/partners.json`: every curated
     partner's full record plus reference paths to its two event files.
- **Postconditions**: `public/data/partners.json` plus every partner's
  event files together contain everything needed to reconstruct the
  site's opportunity data — no other data source required.
- **Error Flows**: A partner with no accumulated log publishes with
  empty `events.json`/`past-events.json` rather than being omitted —
  every curated partner appears in `partners.json`.
- **Acceptance Criteria**:
  - [ ] A partner absent from every source's registry still appears in
        the published `partners.json`, with empty event lists.
  - [ ] The published per-partner event records use the same field set
        as today's `opportunities.json` entries (`sources` excluded, via
        the same promoted `_SITE_SCHEMA_FIELDS`/`_to_json_dict` helpers
        `writer.py` already uses).
  - [ ] `src/data/opportunities.json` (the legacy export) is written
        unchanged, unaffected by this step.

### SUC-007: Mirror the published data export into extra site checkouts
Parent: UC-007

- **Actor**: Operator (via the scheduled/CLI run)
- **Preconditions**: `publish.project(...)` (SUC-006) has just written a
  fresh `public/data/` tree into the primary `site_dir`.
- **Main Flow**:
  1. `mirror_site_data` copies the existing flat `MIRRORED_DATA_FILES`
     and images directory, as today, plus the entire `public/data/`
     tree, into each configured mirror target.
- **Postconditions**: Every mirrored checkout (e.g. this repo's own
  `site/`) serves the same published data contract as the primary site
  checkout.
- **Error Flows**: A mirror target missing `src/data/` is still skipped
  with a warning, unchanged from today's behavior.
- **Acceptance Criteria**:
  - [ ] A target checkout with no pre-existing `public/data/` directory
        receives the full tree.
  - [ ] A target with an unchanged file already present is not
        rewritten (byte-identical skip, matching the existing image
        mirror's behavior).

### SUC-008: Reconstruct the site's opportunity data from the published contract alone
Parent: UC-012

- **Actor**: Visitor / future automated consumer (issue 16, sprint 010,
  builds the discovery layer that points at this)
- **Preconditions**: `public/data/partners.json` and its referenced
  per-partner files have been published (SUC-006) and are reachable at
  the site's public URL.
- **Main Flow**:
  1. Fetch `public/data/partners.json`.
  2. For each partner of interest, fetch its `events.json` (and
     `past-events.json` if history is wanted) via the reference path
     `partners.json` provides.
  3. Render or otherwise consume the data with no other data source.
- **Postconditions**: The full current opportunity directory (and, if
  wanted, its history) is available from these files alone.
- **Error Flows**: None new — this is a read-only consequence of SUC-006
  publishing correctly.
- **Acceptance Criteria**:
  - [ ] The integration test (Test Strategy) demonstrates this
        end-to-end against a `tmp_path` fixture site directory.

## GitHub Issues

(GitHub issues linked to this sprint's tickets. Format: `owner/repo#N`.)

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [ ] Sprint planning document is complete (sprint.md, including its
      Architecture and Use Cases sections)
- [ ] Architecture review passed (or skipped, for changes with no
      architectural impact)
- [ ] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Depends On |
|---|-------|------------|
| 001 | Classify opportunity_type during LLM enrichment | — |
| 002 | Rework Opportunity.slug to a stable, partner-scoped cross-run identity | 001 |
| 003 | Persist opportunities into a per-partner append-only log | 002 |
| 004 | Build-time projection: publish partners.json and per-partner event files | 003 |
| 005 | Mirror the published data export into extra site checkouts | 004 |

Tickets execute serially in the order listed. 001 (issue 13) lands
first, ahead of every issue-15 ticket, per the sprint's stated
sequencing rationale — the classification fix must be correct before
002-005 build the persistent, harder-to-revise export around it.
