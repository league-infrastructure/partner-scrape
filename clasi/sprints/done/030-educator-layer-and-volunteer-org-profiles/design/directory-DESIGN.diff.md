---
source_file: directory-DESIGN.md
source_hash: e7cc1ee5a2727f8f4e2563a77575e13452350cf4c49ef5bad1a49b62b8ef9a20
---
# Diff: directory-DESIGN.md

Comparison of the sprint overlay copy of `directory-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- directory-DESIGN.md (pristine)
+++ directory-DESIGN.md (current)
@@ -1,8 +1,146 @@
 # directory
 
-**Owner:** Eric Busboom · **Last reviewed:** 2026-08-31 (sprint 018, ticket 008 — Clubs proof of concept shipped) · **Status:** Places and Clubs (Hack Club chapters) complete; issue 35b's remaining six club types deferred to a future sprint
+**Owner:** Eric Busboom · **Last reviewed:** 2026-09-02 (sprint 030 — Offerings standing-entity type added) · **Status:** Places, Clubs (Hack Club chapters), and Offerings (volunteer org profiles + free/Title I school programs) complete; issue 35b's remaining six club types and issue 33's educator-PD program pages (routed through `adapters/`, not this module — see this doc's sprint 030 Revision) deferred/tracked elsewhere
 
 ---
+
+## Revision (2026-09-02 — sprint 030 Offerings standing-entity type)
+
+Issues 33 (educator layer) and 14 (volunteer opportunity discovery)
+each need the same underlying thing: an **undated, standing "offering"
+record** — an org describes what it offers, who qualifies, and how to
+get it, with no event date and no recurrence. Issue 14 Strategy B
+(volunteer org profiles: Fleet, SDZWA, Birch, the Nat, ILACSD, San
+Diego River Park Foundation) needs org / what-volunteers-do /
+**age-minimum** (first-class, per the teen audience) / link-to-portal.
+Issue 33 part 2 (free/Title I school programs: Zoo FREE field trips,
+the Nat's Museum Access Fund, Living Coast Title 1 + CVESD free
+transport, Birch financial aid, Fleet discounted trips/Science to
+Go/Family Science Nights, Qualcomm Thinkabit Lab, Biocom Life Science
+Station + Innov8Ed) needs org / program / eligibility / how-to-book /
+last-verified. Both are exactly the "standing entity, no date, no
+recurrence, no relevance gate" shape this module exists to house — see
+§1's own argument, made twice already for `Place` and `Club`, now made
+a third time. **Design decision: one new model, `Offering`, serving
+both,** rather than two separate models or a "volunteer profile" bolted
+onto `Place`/`Club`. See §4's new Design entry for the full Design
+Rationale (Decision/Context/Alternatives/Consequences).
+
+Issue 33 part 1 (curated educator-PD program pages — UCSD CREATE, SD
+Science Project, UCSD Math Project, Code.org regional partner,
+CSTA-SD, SDSU CRMSE, Fleet educator workshops, Salk STEM Educators
+Summit, Zoo teacher workshops) is **not** an `Offering` — a workshop or
+summit has a date, so it is a dated event, not a standing entity. It
+routes through `adapters/`'s existing `program_page`/
+`program_page_multi`/`program_listing` mechanism (extended with a new
+extraction profile) and the existing `Opportunity` model, exactly like
+every other program-page source since sprint 027 — see
+`adapters/DESIGN.md`'s own sprint 030 Revision section for that half of
+this sprint's work. This module is not touched by it at all.
+
+**Package shape addition** (mirrors ticket 018-008's `Club` addition to
+ticket 018-007's `Place` package exactly — see §2's tree below for the
+now-three-way shape):
+
+```
+partner_scrape/directory/
+  model.py              + Offering dataclass (OfferingType/
+                         OfferingStatus Literals + VALID_OFFERING_*
+                         derivations) -- a third flat dataclass in the
+                         same file, no shared base with Place/Club
+                         (see §4's Design Rationale, extending the
+                         existing "no shared base" precedent)
+  sources/
+    base.py              + OfferingSource protocol + OfferingRef/
+                          RawOfferingResponse/run_offering_source() --
+                          a third near-identical Protocol, same
+                          rationale as Place/Club's own two
+    offering_static_roster.py
+                          OfferingStaticRosterSource -- reads
+                          directory/data/offerings.toml straight off
+                          disk, never touches the injected Fetcher,
+                          identical shape to static_roster.py /
+                          hack_club_static_roster.py
+  pipeline.py            run_directory(): registry dispatch extended
+                         to a three-way check (_PLACE_SOURCES then
+                         _CLUB_SOURCES then _OFFERING_SOURCES per
+                         source_config, one combined loop -- see this
+                         doc's existing "why one combined loop"
+                         Design entry, extended identically) ->
+                         **no geocoding stage for Offering** (see
+                         Constraints, below -- this is the one
+                         structural way an Offering's pipeline
+                         handling is NOT a mechanical copy of Club's)
+                         -> export_directory()
+  export.py              export_directory() gains a third optional
+                         `offerings` argument, writing offerings.json
+                         to own_data_dir only (sprint 025's "one
+                         publish, one path" convention -- see §3's
+                         updated data-contract section below), same
+                         None-means-"don't touch it" /
+                         empty-list-means-"ran, found nothing"
+                         contract as `clubs`
+  registry/
+    offerings-sd.toml     Offering Registry entry, adapter_type =
+                          "offering_static_roster" -- same shared
+                          registry directory as places-sd.toml/
+                          hack-club-sd.toml
+  data/
+    offerings.toml         the curated dataset: 6 volunteer org
+                           profiles (issue 14 Strategy B) + 7 free/
+                           Title I school-program records (issue 33
+                           part 2), one flat TOML array of tables
+                           (`[[offering]]`) -- TOML, not TSV, for the
+                           same "too many fields for a flat table"
+                           reason places.toml gives (see this doc's
+                           existing Design section on that choice)
+```
+
+**Why `Offering` carries no location/geocoding fields at all --
+unlike both `Place` and `Club`.** A `Place` is a venue you travel to; a
+`Club` meets at a real, locatable school. An `Offering` is neither --
+it is a program or volunteer role *hosted by* an org whose own location
+(if it has a single one worth mapping) is already published via
+`site/src/data/partners.json` and, for the small subset that are also
+curated `Place`s, `places.toml` itself. Giving `Offering` its own
+`latitude`/`longitude`/`location_precision` would mean geocoding the
+*same* organization a second time under a different record, using a
+different join, for no reader benefit -- a directory-style card linking
+out is a "what/who/how," not a "where," page. `directory.pipeline.
+run_directory()`'s dispatch therefore has **no fallback/geocoding stage
+for Offering at all** (no `_apply_offering_geocoding()` counterpart to
+`_apply_geo_fallback()`/`_apply_club_geocoding()`), and no `GeoLadder`
+dependency is added for this addition -- a real scope reduction versus
+both existing entity types, not an oversight. See §4's Design Rationale
+for the full Decision/Alternatives/Consequences write-up, including
+what a future sprint would need to add if a stakeholder ever wants
+Offerings on a map.
+
+**`age_minimum` is a first-class field, not folded into free-text
+`eligibility`.** Issue 14's own instruction: "Note age minimums
+explicitly: Fleet 18+, SDZWA 18+, Birch 16+ -- it matters for the teen
+audience." A teen-audience filter/sort needs a real, comparable `int |
+None`, not a substring match inside a prose eligibility sentence.
+`None` means "no individual-volunteer age minimum applies" (every
+free/Title-I school-program record: eligibility there is about the
+*school*, not an individual's age) -- never a guessed `0`.
+
+**`related_partner_id` reuses `Place`'s existing hand-verified-join
+convention exactly**, including this doc's existing join-integrity
+test discipline (`tests/directory/test_dataset_validity.py`'s
+`TestRelatedPartnerIdJoinIntegrity` gains an `Offering` counterpart
+check, or is generalized to check both -- ticket-level implementation
+choice, not a new convention). Every non-`None` `Offering.
+related_partner_id` in `offerings.toml` is checked by hand against
+`site/src/data/partners.json`'s own `id` field at authoring time, same
+as `places.toml`'s existing rows.
+
+**`offerings.json` is written from a fourth genuinely independent
+`{"meta": ..., "offerings": [...]}` document**, mirroring `clubs.json`'s
+own "never nested inside `places.json`" precedent for the identical
+reason (an offerings run's freshness/count must never be confused with
+the places or clubs export's own). `offerings` defaults to `None`
+("do not touch `offerings.json`"), matching `clubs`'s exact contract.
 
 ## 1. Purpose
 
@@ -424,8 +562,74 @@
 order for either "where to go any day" or "which clubs meet here"
 reference.
 
+**Why `Offering` is one model serving both issue 14 Strategy B
+(volunteer org profiles) and issue 33 part 2 (free/Title I school
+programs), not two (sprint 030).** *Decision:* a single `Offering`
+dataclass with an `offering_type` discriminator (`"volunteer"` |
+`"free_program"`). *Context:* both are undated, standing, org-hosted
+"here's what we offer and how to get it" records with the same core
+shape — org, title, description, eligibility, how-to-book, link-out,
+last-verified — differing only in which of those fields a given row
+actually populates (`age_minimum` for volunteer rows, a Title-I/grade
+eligibility string for free-program rows). *Alternatives considered:*
+(a) two separate models (`VolunteerProfile`, `FreeProgram`) — rejected,
+this would duplicate the entire field set for a distinction that is
+genuinely just one enum value, and would need two registries, two
+sources, two export sections, and two site sections for what a reader
+experiences as one kind of page ("this org's standing offer"); (b)
+extend `Place` with optional volunteer/program fields — rejected, a
+`Place` is a locatable venue by definition (see `Place`'s own docstring
+and this doc's §4 "why separate dataclasses" precedent) and most
+`Offering`s are not venues at all, just a link and a policy. *Why this
+choice:* matches this module's own established pattern of "one model
+per distinct standing-entity shape, not one model per data source" —
+`Place` already serves multiple categories (makerspace, planetarium,
+tide-pool, ...) through one model with a `category` discriminator; this
+is the identical move applied to a new shape. *Consequences:* a future
+third standing-entity "offering" type (a scholarship program, a grant)
+fits by adding an `OfferingType` value and a small validation-rule
+branch (mirroring `status`/`status_note`'s existing per-status-value
+validation), not a new model — the same "kept general enough" property
+`Club`'s own Design Rationale already claims for `ClubType`.
+
+**Why `Offering` has no geocoding/location fields at all, the one
+structural way it is not a mechanical copy of `Club`'s addition.** See
+this doc's Revision section above for the full argument (an `Offering`
+is not a place to travel to). *Consequences worth flagging explicitly:*
+if a future stakeholder ever wants Offerings plotted on a map (e.g. "show
+me volunteer orgs near me"), that is a real, non-trivial follow-up — it
+would need either a `related_partner_id`-mediated join to that partner's
+already-geocoded location (feasible today, since the join field already
+exists) or the same location/`GeoLadder` machinery `Place`/`Club` already
+carry (a real model change). Not attempted this sprint; not blocking
+either, since `related_partner_id` alone gets a consumer most of the way
+there without any code change here.
+
+**Why `Offering.related_partner_id` reuses `Place`'s hand-verified-join
+convention rather than inventing a new one.** Same rationale as that
+convention's own original justification (sprint 018 ticket 007: "do
+not attempt an automatic cross-reference join ... hand-copy the
+value") — an `Offering`'s operating org is exactly the kind of fact a
+human curating 13 rows can verify by hand faster and more reliably than
+building an auto-join would take, and auto-joining organization names
+correctly (fuzzy name matching against `partners.json`) is a
+non-trivial problem this addition has no need to solve.
+
 ## 5. Open Questions
 
+- Should a future sprint give `Offering` a `related_partner_id`-mediated
+  location so a consumer can plot volunteer orgs / free-program hosts on
+  a map, per this doc's Design Rationale above? Deferred — no
+  stakeholder request yet; flagged so the option is visible when one
+  arrives.
+- Should `Offering`'s `age_minimum` grow a companion `age_maximum` or a
+  `commitment_note` (e.g. "6-month minimum," matching Fleet's
+  `VolunteerMatters` requirement per issue 14's research) if a future
+  curation pass finds more volunteer orgs with structured commitment
+  terms beyond a simple minimum age? Left out this sprint — none of the
+  six curated volunteer orgs' publicly stated terms needed more than
+  `age_minimum` plus free-text `how_to_book` to represent accurately;
+  revisit if a future org's terms don't fit.
 - Should `directory/data/`'s duplicated ZIP/city-centroid files be
   refreshed automatically alongside `teams/data/`'s own copies (e.g. by
   extending `dev/refresh_school_directories.py` to write both
```
