# directory

**Owner:** Eric Busboom · **Last reviewed:** 2026-09-02 (sprint 032 ticket 004 — Sea Cadets units roster curated and registered) · **Status:** Places, Clubs (Hack Club chapters + CyberPatriot teams + Civil Air Patrol squadrons + Naval Sea Cadet Corps units; the curated static-roster source generalized to serve any club type), and Offerings (volunteer org profiles + free/Title I school programs) complete; issue 35b's remaining three club types' curated content (tickets 005-007) and issue 33's educator-PD program pages (routed through `adapters/`, not this module — see this doc's sprint 030 Revision) deferred/tracked elsewhere

---

## Revision (2026-09-02 — sprint 032 ticket 004: Sea Cadets units roster curated and registered)

Populates the third of issue 35b's six remaining club types against
the generalized `club_static_roster` source (ticket 001): four
San Diego/North County U.S. Naval Sea Cadet Corps (NSCC) units,
registered via a new `directory/registry/sea-cadets-sd.toml` entry
pointing at a new `directory/data/sea-cadets-sd.tsv` (same ten-column
shape as `hack-club-sd.tsv`). No code change — content-only. Unlike
tickets 002/003, issue 35b named no starting units for this type — all
four were found via this ticket's own research.

**Sources checked** (live-verified 2026-09-02):

- **Escondido Battalion & Training Ship Kit Carson**
  (escondidobattalion.org) — founded 2011, drills two weekend days a
  month during the school year at Escondido Police & Fire HQ, 1163 N.
  Centre City Pkwy, Escondido, CA 92026. Strongest verification of the
  four: a live, working, currently-maintained unit site.
- **Gunfighter Squadron & Training Ship TopGun**
  (sites.google.com/site/gunfightertopgun) — aviation-oriented unit
  formed 1973, based at MCAS Miramar; its own site lists an upcoming
  drill dated August 29, 2026, directly confirming current activity.
- **Michael A. Monsoor Battalion** — construction-battalion-oriented
  unit at Marine Corps Base Camp Pendleton; confirmed active via a
  November 13, 2023 NBC 7 San Diego news report on equipment stolen
  from the unit ("Thief steals gear and uniforms from youth military
  group at Camp Pendleton"). No dedicated unit website found; listed
  on Navy League San Diego's own current youth-programs page
  (navyleague-sd.com/sea-cadets/).
- **Chief MCM-14 Division** — named for the former mine-countermeasures
  ship USS Chief (MCM-14, now homeported in Japan), based at Naval
  Base San Diego; listed on Navy League San Diego's own current
  youth-programs page. **Weakest verification of the four**: no
  independent unit website, no dated recent activity found beyond the
  sponsor listing itself — included on the strength of a live,
  currently-published sponsor page naming it without any inactive/
  defunct indication, not a dedicated source of its own.

**Found but deliberately excluded** (an honest finding, not a gap in
research): **Challenger Division / TS Columbia** and **Coronado
Battalion**, both cited in older secondary sources (a 2019 Cadet-of-
the-Year award for Challenger; general San Diego Sea Cadets
overviews), show clear signs of current inactivity at live-verification
time — Challenger's own domain (`challenger-seacadets.org`) no longer
resolves (DNS failure), and Coronado's own domain
(`coronadoseacadets.org`) serves a broken/mismatched TLS certificate;
independent search results describe on-base Sea Cadet activities at
Naval Amphibious Base Coronado as "currently suspended until further
notice." Recording their prior existence here rather than including
them as active entries follows this module's own "flag it, don't force
it" convention (Helix Charter's own precedent) applied to a whole
entry rather than a single geocoding match.

**Geocoding outcome**: one entry (Escondido Battalion, zip 92026)
resolves at `"zip"` precision — the real, committed
`zip-centroids.toml` covers that code. The other three (Gunfighter
Squadron/MCAS Miramar, Michael Monsoor Battalion/Camp Pendleton, Chief
MCM-14 Division/Naval Base San Diego) have zip codes not present in
that same file, so they fall one rung further to `"city"` precision
(San Diego/Oceanside city centroids) — still a real, non-guessed
ladder rung per sprint.md's Architecture "Geocoding note," never a
fabricated coordinate. `needs_review = False` for all four; no
school-matching rung ever fires (none of these organizations' names
share meaningful tokens with a CDE/NCES school name).

**Test-suite impact**: no new parsing-shape test file — the data
reused `hack-club-sd.tsv`'s exact column shape. A new
`TestRealSeaCadetsGeocoding` class in `test_pipeline.py` (mirroring
ticket 003's own `TestRealCivilAirPatrolGeocoding`) pins the real Sea
Cadets roster's mixed zip/city outcome end-to-end. Full-registry
`clubs_meta.total` assertions across `test_pipeline.py` now expect
`18` (4 Hack Club + 3 CyberPatriot + 7 Civil Air Patrol + 4 Sea
Cadets), not `14`.

## Revision (2026-09-02 — sprint 032 ticket 003: Civil Air Patrol squadrons roster curated and registered)

Populates the second of issue 35b's six remaining club types against
the generalized `club_static_roster` source (ticket 001): San Diego
Group 8's own headquarters plus its six subordinate squadrons (seven
`Club` entries), registered via a new
`directory/registry/civil-air-patrol-sd.toml` entry pointing at a new
`directory/data/civil-air-patrol-sd.tsv` (same ten-column shape as
`hack-club-sd.tsv`). No code change — content-only.

**Sources checked** (live-verified 2026-09-02, not transcribed from
issue 35b's own wording): California Wing's own Group 8 "Find a
Squadron" locator (`group8ca.cap.gov/join-cap/find-a-squadron`) names
six subordinate squadrons; each squadron's own `*.cap.gov` site gives
its current meeting address. Issue 35b named Squadrons 144, 201, and
Group 8 as a starting point — all three found and verified — plus four
more squadrons found via the same live locator: Skyhawk Composite
Squadron 47 (Carlsbad), San Diego Senior Squadron 57 (El Cajon,
Gillespie Field), Fallbrook Senior Squadron 87 (Fallbrook Airpark),
and Escondido Cadet Squadron 714 (Escondido).

**Geocoding outcome — matches sprint.md's own prediction exactly.**
Six of the seven entries (Group 8's own HQ office and five of the six
squadrons) meet at non-school facilities — an Air National Guard base,
a VFW post, airports, an administrative office — and fall through
honestly to `"zip"` precision, `needs_review = False`, per sprint.md's
Architecture "Geocoding note." One genuine exception: **Escondido
Cadet Squadron 714 meets in a classroom on Escondido Charter High
School's own campus**, live-verified via the squadron's own site
(1868 E Valley Pkwy, Classroom F-203 — Escondido Charter High School's
address), so it correctly resolves at `"school"` precision through the
shared ladder's exact CDE match, `needs_review = False` — an honest
match on the real data, not a forced correction and not suppressed to
force the "CAP is non-school" pattern where the real world disagrees.

**Test-suite impact**: no new parsing-shape test file — the data
reused `hack-club-sd.tsv`'s exact column shape. Two more pre-existing
tests turned out to hard-code the "every real Club is school-hosted"
assumption ticket 002 didn't trip (CyberPatriot happens to be entirely
school-hosted too) but this ticket's non-school CAP majority does:
`test_pipeline.py`'s `test_every_real_hack_club_chapter_resolves_to_
school_precision_never_a_guess` (renamed, now scoped to
`club_type in {"hack-club", "cyberpatriot"}`) and
`test_club_dataset_validity.py`'s
`TestRealPipelineGeocodingResolvesEveryChapterHonestly._real_geocoded_clubs()`
(now scoped to `club_type == "hack-club"`, matching that whole
module's own documented scope). A new `TestRealCivilAirPatrolGeocoding`
class in `test_pipeline.py` pins the real CAP roster's own mixed
zip/school outcome end-to-end. Full-registry `clubs_meta.total`
assertions across `test_pipeline.py` now expect `14` (4 Hack Club + 3
CyberPatriot + 7 Civil Air Patrol), not `7`.

## Revision (2026-09-02 — sprint 032 ticket 002: CyberPatriot teams roster curated and registered)

Populates the first of issue 35b's six remaining club types against the
generalized `club_static_roster` source (ticket 001): three San Diego
County CyberPatriot teams, registered via a new
`directory/registry/cyberpatriot-sd.toml` entry pointing at a new
`directory/data/cyberpatriot-sd.tsv` (same ten-column shape as
`hack-club-sd.tsv`). No code change — content-only, exactly as ticket
001's generalization anticipated.

**Sources checked** (live-verified 2026-09-02, not transcribed from
issue 35b's own wording):

- **Del Norte High School** — CyberPatriot XV Open Division National
  Champion ("CyberAegis Tempest," March 2023) and CyberPatriot XVI
  Open Division runner-up/third place ("CyberAegis Triton"/"CyberAegis
  Aegir," 2024), per AFA's own CyberPatriot XV/XVI announcement pages
  and Poway Unified School District's own news article. The program
  operates as "CyberAegis San Diego" (`cyberaegis.tech`), a student-led
  effort spanning Oak Valley Middle School, Design39Campus, and Del
  Norte High School — Del Norte is its home/flagship school, hence
  `host_school`. Not found among CyberPatriot 18's (the current,
  concluded-March-2026 season) national finalists, per AFA's own CP18
  finalist announcement — recorded here on the strength of its
  multi-season finalist/champion history, not a current-season
  placement; a future curation pass should re-check whether the
  program is still active before the next refresh.
- **Scripps Ranch High School** — CyberPatriot 18 (2025-2026 season,
  concluded March 2026) All Service Division **National Champion**,
  Air Force JROTC "Terabyte Falcons" team, per AFA's own CyberPatriot
  18 national finalist announcement — the most current season
  available at curation time.
- **Canyon Crest Academy** — CyberPatriot 18 Open Division national
  finalist (team ":3"), per AFA's own CP18 finalist announcement, the
  San Dieguito Union High School District's own social posts, and the
  team's own "CCA CyberPatriot" site (`sites.google.com/view/cca-cyberpatriot/`).

Also found but **not** included: Scouting America Exploring Posts 2927
and 2928 (San Diego-based "CyberAegis Hydra"/"CyberAegis
Perseus"/"CyberAegis Corvus" teams, CP18 finalists) — excluded because
they are Scouting Explorer posts, not school-hosted clubs with a single
confidently locatable meeting site, unlike this roster's three
school-hosted entries. A future ticket could add them with an
appropriately non-school geocoding expectation (see sprint.md's
Geocoding note) if a stakeholder wants Scouting-sponsored teams
covered too.

**Geocoding outcome**: all three entries resolve at `"school"`
precision through the shared ladder's rung-2 exact CDE match — Del
Norte High, Scripps Ranch High, and Canyon Crest Academy are all exact
normalized-name hits against `sd-schools-public.tsv`, with
`needs_review = False` for all three (no fuzzy rung-3/4 match
involved). No entry required `needs_review` flagging.

**Test-suite impact**: no new parsing-shape test file — the data
reused `hack-club-sd.tsv`'s exact column shape, so existing
registry-loader/dataset-validity coverage applies unchanged (per
sprint.md's Test Strategy). Several existing pipeline/dataset-validity
tests hard-coded assumptions that only ever held while exactly one
`club_static_roster` registry entry existed — a `next(...)` lookup
scoped by `adapter_type` alone, and full-registry `clubs_meta.total`
assertions pinned at `4` — both updated in this ticket:
`test_club_dataset_validity.py`'s and
`test_sources_club_static_roster.py`'s own `_real_source_config()`/
`_real_clubs()` helpers now scope by `source_id == "hack-club-sd"`
(they test the Hack Club roster specifically), and
`test_pipeline.py`'s full-registry club-count assertions now expect
`7` (4 Hack Club + 3 CyberPatriot), matching the real registry's
current content.

## Revision (2026-09-02 — sprint 032 ticket 001: club static-roster source generalized)

Resolves §5's own Open Question ("Should issue 35b's remaining six
club types each get their own `ClubSource` ... reusing `ClubType`'s
Literal (widened) and the existing `_CLUB_SOURCES` dispatch table?")
in favor of the "reuse, don't duplicate" answer that question always
anticipated as the likely one. Two changes, landed together in one
ticket/commit:

1. **`ClubType` widens** from `Literal["hack-club"]` to also include
   `"cyberpatriot"`, `"science-olympiad"`, `"4-h"`,
   `"girls-who-code"`, `"civil-air-patrol"`, and `"sea-cadets"` —
   `VALID_CLUB_TYPES` (already derived via `get_args()`) picks up all
   six with no further change. No new field, no new dataclass — see
   sprint.md's Scope Correction for the "no *new* field/schema, not
   'the Literal never needs another value'" distinction this widening
   makes concrete.
2. **`sources/hack_club_static_roster.py` renamed and generalized to
   `sources/club_static_roster.py`.** The module's `discover()`/
   `fetch()`/`extract()` logic was already generic — nothing in it was
   Hack-Club-specific except the file/class name, the hard-coded
   `SOURCE_NAME` module constant, and the default roster path (naming
   and defaults, not logic). `HackClubStaticRosterSource` becomes
   `ClubStaticRosterSource`; the one real behavioral change is that
   provenance (`Club.sources`) is now derived per registry entry from
   `SourceConfig.source_id` rather than one hard-coded literal, so a
   CyberPatriot or Sea Cadets `Club` never carries the misleading
   string `"hack_club_static_roster"` as its source. `directory/
   pipeline.py`'s `_CLUB_SOURCES` dispatch key and
   `hack-club-sd.toml`'s `adapter_type` both change from
   `"hack_club_static_roster"` to `"club_static_roster"`, landed in the
   same commit so `run_directory()` never sees a dangling dispatch-table
   key for the one existing Hack Club registry entry (see sprint.md's
   Migration Concerns).

**Why one rename rather than six new near-duplicate modules, and why
now rather than deferred further** — see sprint.md's own Design
Rationale (Decision/Context/Alternatives/Consequences) for sprint 032;
not re-derived here beyond the one-line summary: the code was already
general enough, so writing six copies would have been pure
duplication, and leaving the module's own name permanently
Hack-Club-specific would have misdescribed what it now serves.

**This ticket adds no roster content.** The four existing Hack Club
chapters are unchanged in data and geocoding outcome — only their
registry entry's `adapter_type` string and `Club.sources` provenance
value change. Curating and registering the six new club types'
rosters themselves is tickets 002-007's own work, each a data-only
addition (new TSV + new registry entry, `adapter_type =
"club_static_roster"`) requiring no further Python change.

## Revision (2026-09-02 — sprint 030 Offerings standing-entity type)

Issues 33 (educator layer) and 14 (volunteer opportunity discovery)
each need the same underlying thing: an **undated, standing "offering"
record** — an org describes what it offers, who qualifies, and how to
get it, with no event date and no recurrence. Issue 14 Strategy B
(volunteer org profiles: Fleet, SDZWA, Birch, the Nat, ILACSD, San
Diego River Park Foundation) needs org / what-volunteers-do /
**age-minimum** (first-class, per the teen audience) / link-to-portal.
Issue 33 part 2 (free/Title I school programs: Zoo FREE field trips,
the Nat's Museum Access Fund, Living Coast Title 1 + CVESD free
transport, Birch financial aid, Fleet discounted trips/Science to
Go/Family Science Nights, Qualcomm Thinkabit Lab, Biocom Life Science
Station + Innov8Ed) needs org / program / eligibility / how-to-book /
last-verified. Both are exactly the "standing entity, no date, no
recurrence, no relevance gate" shape this module exists to house — see
§1's own argument, made twice already for `Place` and `Club`, now made
a third time. **Design decision: one new model, `Offering`, serving
both,** rather than two separate models or a "volunteer profile" bolted
onto `Place`/`Club`. See §4's new Design entry for the full Design
Rationale (Decision/Context/Alternatives/Consequences).

Issue 33 part 1 (curated educator-PD program pages — UCSD CREATE, SD
Science Project, UCSD Math Project, Code.org regional partner,
CSTA-SD, SDSU CRMSE, Fleet educator workshops, Salk STEM Educators
Summit, Zoo teacher workshops) is **not** an `Offering` — a workshop or
summit has a date, so it is a dated event, not a standing entity. It
routes through `adapters/`'s existing `program_page`/
`program_page_multi`/`program_listing` mechanism (extended with a new
extraction profile) and the existing `Opportunity` model, exactly like
every other program-page source since sprint 027 — see
`adapters/DESIGN.md`'s own sprint 030 Revision section for that half of
this sprint's work. This module is not touched by it at all.

**Package shape addition** (mirrors ticket 018-008's `Club` addition to
ticket 018-007's `Place` package exactly — see §2's tree below for the
now-three-way shape):

```
partner_scrape/directory/
  model.py              + Offering dataclass (OfferingType/
                         OfferingStatus Literals + VALID_OFFERING_*
                         derivations) -- a third flat dataclass in the
                         same file, no shared base with Place/Club
                         (see §4's Design Rationale, extending the
                         existing "no shared base" precedent)
  sources/
    base.py              + OfferingSource protocol + OfferingRef/
                          RawOfferingResponse/run_offering_source() --
                          a third near-identical Protocol, same
                          rationale as Place/Club's own two
    offering_static_roster.py
                          OfferingStaticRosterSource -- reads
                          directory/data/offerings.toml straight off
                          disk, never touches the injected Fetcher,
                          identical shape to static_roster.py /
                          hack_club_static_roster.py
  pipeline.py            run_directory(): registry dispatch extended
                         to a three-way check (_PLACE_SOURCES then
                         _CLUB_SOURCES then _OFFERING_SOURCES per
                         source_config, one combined loop -- see this
                         doc's existing "why one combined loop"
                         Design entry, extended identically) ->
                         **no geocoding stage for Offering** (see
                         Constraints, below -- this is the one
                         structural way an Offering's pipeline
                         handling is NOT a mechanical copy of Club's)
                         -> export_directory()
  export.py              export_directory() gains a third optional
                         `offerings` argument, writing offerings.json
                         to own_data_dir only (sprint 025's "one
                         publish, one path" convention -- see §3's
                         updated data-contract section below), same
                         None-means-"don't touch it" /
                         empty-list-means-"ran, found nothing"
                         contract as `clubs`
  registry/
    offerings-sd.toml     Offering Registry entry, adapter_type =
                          "offering_static_roster" -- same shared
                          registry directory as places-sd.toml/
                          hack-club-sd.toml
  data/
    offerings.toml         the curated dataset: 6 volunteer org
                           profiles (issue 14 Strategy B) + 7 free/
                           Title I school-program records (issue 33
                           part 2), one flat TOML array of tables
                           (`[[offering]]`) -- TOML, not TSV, for the
                           same "too many fields for a flat table"
                           reason places.toml gives (see this doc's
                           existing Design section on that choice)
```

**Why `Offering` carries no location/geocoding fields at all --
unlike both `Place` and `Club`.** A `Place` is a venue you travel to; a
`Club` meets at a real, locatable school. An `Offering` is neither --
it is a program or volunteer role *hosted by* an org whose own location
(if it has a single one worth mapping) is already published via
`site/src/data/partners.json` and, for the small subset that are also
curated `Place`s, `places.toml` itself. Giving `Offering` its own
`latitude`/`longitude`/`location_precision` would mean geocoding the
*same* organization a second time under a different record, using a
different join, for no reader benefit -- a directory-style card linking
out is a "what/who/how," not a "where," page. `directory.pipeline.
run_directory()`'s dispatch therefore has **no fallback/geocoding stage
for Offering at all** (no `_apply_offering_geocoding()` counterpart to
`_apply_geo_fallback()`/`_apply_club_geocoding()`), and no `GeoLadder`
dependency is added for this addition -- a real scope reduction versus
both existing entity types, not an oversight. See §4's Design Rationale
for the full Decision/Alternatives/Consequences write-up, including
what a future sprint would need to add if a stakeholder ever wants
Offerings on a map.

**`age_minimum` is a first-class field, not folded into free-text
`eligibility`.** Issue 14's own instruction: "Note age minimums
explicitly: Fleet 18+, SDZWA 18+, Birch 16+ -- it matters for the teen
audience." A teen-audience filter/sort needs a real, comparable `int |
None`, not a substring match inside a prose eligibility sentence.
`None` means "no individual-volunteer age minimum applies" (every
free/Title-I school-program record: eligibility there is about the
*school*, not an individual's age) -- never a guessed `0`.

**`related_partner_id` reuses `Place`'s existing hand-verified-join
convention exactly**, including this doc's existing join-integrity
test discipline (`tests/directory/test_dataset_validity.py`'s
`TestRelatedPartnerIdJoinIntegrity` gains an `Offering` counterpart
check, or is generalized to check both -- ticket-level implementation
choice, not a new convention). Every non-`None` `Offering.
related_partner_id` in `offerings.toml` is checked by hand against
`site/src/data/partners.json`'s own `id` field at authoring time, same
as `places.toml`'s existing rows.

**`offerings.json` is written from a fourth genuinely independent
`{"meta": ..., "offerings": [...]}` document**, mirroring `clubs.json`'s
own "never nested inside `places.json`" precedent for the identical
reason (an offerings run's freshness/count must never be confused with
the places or clubs export's own). `offerings` defaults to `None`
("do not touch `offerings.json`"), matching `clubs`'s exact contract.

## 1. Purpose

`partner_scrape/directory/` acquires and publishes San Diego's curated,
undated "standing entity" directories — Places (ticket 007: a "where
to go any day" reference of makerspaces, planetariums, observatories,
tide pools, nature centers, and library maker labs) and Clubs (ticket
018-008: Hack Club chapters, this sprint's one proof-of-concept club
type — issue 35b carries the remaining six named club types,
CyberPatriot, Science Olympiad, 4-H, Girls Who Code, Civil Air Patrol,
Sea Cadets, as a future sprint's data-only work). It generalizes the
pattern `teams/` already proved for FIRST robotics teams (sprint
011/012): a standing directory entity has no date, no recurrence, and
no relevance gate, none of which the existing `Opportunity` pipeline's
abstractions are built around. See `teams/DESIGN.md` §1 for the
identical argument made for `Team` — this module is the second (and
third) instance of that same shape, not a new architectural idea.

## 2. Orientation

**Ticket 018-006** extracted the general-purpose parts of `teams/
geo.py`'s seven-rung offline geocoding ladder into a new shared module,
`partner_scrape/geo_ladder.py` (`GeoLadder`), specifically so this
module could depend on it without depending on `teams/` or duplicating
its logic. See that module's own docstring for the full rung-by-rung
description; this document does not re-derive it.

**Ticket 018-007** built the whole `directory/` package and shipped the
full Places directory. **Ticket 018-008 (this ticket)** added the
`Club` model and its one populated type, Hack Club chapters, following
the same package shape:

```
partner_scrape/directory/
  model.py              Place dataclass (Category/Status/LocationPrecision
                         Literals + VALID_* frozenset derivations) and
                         Club dataclass (ClubType/ClubStatus/
                         ClubLocationPrecision Literals + their own
                         VALID_CLUB_* derivations) -- two separate flat
                         dataclasses in one file, no shared base
  sources/
    base.py              PlaceSource protocol (discover/fetch/extract) +
                          PlaceRef/RawPlaceResponse/run(), and ClubSource
                          protocol + ClubRef/RawClubResponse/
                          run_club_source() -- two separate, near-identical
                          Protocols (see §4's "no shared source contract
                          either" rationale)
    static_roster.py      StaticRosterSource (Places) -- reads
                          directory/data/places.toml straight off disk,
                          never touches the injected Fetcher
    hack_club_static_roster.py
                          HackClubStaticRosterSource (Clubs) -- reads
                          directory/data/hack-club-sd.tsv straight off
                          disk, never touches the injected Fetcher
  pipeline.py            run_directory(): Registry -> PlaceSource(s)/
                          ClubSource(s) (one combined dispatch loop,
                          see §4) -> _apply_geo_fallback() (Places,
                          GeoLadder rungs 5-6 only) /
                          _apply_club_geocoding() (Clubs, GeoLadder's
                          *full* ladder including school rungs 1-4) ->
                          export_directory()
  export.py              export_directory(): writes places.json (always)
                          and clubs.json (when `clubs` is given) to both
                          src/data/ and public/data/ (sprint 017's "one
                          publish, two paths" convention, extended to a
                          second file)
  registry/
    places-sd.toml        Place Registry entry, adapter_type = "static_roster"
    hack-club-sd.toml     Club Registry entry, adapter_type =
                          "hack_club_static_roster" -- same shared
                          registry directory as places-sd.toml, not a
                          separate one (see §3)
  data/
    places.toml             the curated 19-place dataset
    hack-club-sd.tsv         the curated 4-chapter Hack Club dataset
    zip-centroids.toml,      committed duplicates of teams/data/'s own
    city-centroids.toml,     files (see "Why directory/data/ duplicates
    school-overrides.toml,   teams/data/" below).
    sd-schools-public.tsv,   Ticket 007 left the school-directory files
    sd-schools-private.tsv   genuinely EMPTY (header rows only) --
                             Places never need them. Ticket 018-008 is
                             the first real consumer: both TSVs now
                             carry a byte-identical copy of teams/data/'s
                             own CDE public / NCES private school
                             directories (796 / 214 lines), since Hack
                             Club chapters are school-hosted.
                             school-overrides.toml stays empty as of
                             this ticket -- every real curated chapter
                             resolves via the ladder's algorithmic rungs
                             2/3, no hand override needed yet (see §2).
```

`cli.py`'s `directory` subcommand (`_add_directory_subcommand`/
`_run_directory`) is unchanged in shape from ticket 007 — no new flag,
no new subcommand — but its printed summary now reports a clubs count
alongside the places count, and `export/mirror.py`'s
`MIRRORED_DATA_FILES` gained `"clubs.json"` alongside ticket 007's own
`"places.json"`. Both are purely additive — no existing `run`/`teams`/
`discover-candidates` flag, default, or printed line changed.

**Places count and category coverage (as of this ticket):** 19 curated
places — 3 makerspaces, 2 planetariums, 2 observatories, 3 tide-pool
sites, 5 nature centers, 4 library maker labs. Every category issue 35
named has at least one entry. 18 of 19 carry a hand-curated,
address-precision coordinate; the 19th (`atlas-labs`, not yet open —
see below) resolves through the shared ladder's ZIP-centroid fallback
to a real, in-bounds coordinate (ZIP 92154 centroid).

**Library maker labs were cross-checked, not assumed.** Ticket
018-003 registered six newly-added city libraries to the partner
roster (Oceanside, Carlsbad, Escondido, Coronado, Chula Vista, National
City) but did not research which of them actually run a maker-lab
program. This ticket did that research directly: Oceanside (Discovery
Lab), Carlsbad (Exploration HUB at Dove Library), Escondido (free 3D
printing + monthly TinkerCAD classes), and Chula Vista (Innovation
Station at the Civic Center branch) all have a confirmed, named
program. No public evidence of a maker-lab program was found for
Coronado or National City as of this ticket — both are correctly
**absent** from `places.toml`, not force-included. If either city
launches one later, add it as a new `[[place]]` entry; do not assume
absence means "not yet researched."

**Atlas Labs is included per issue 35's explicit instruction, marked
`status = "opening"`, never `"open"`.** It is a members-only ($69/mo+)
hardware makerspace at 2293 Verus Street (Otay Mesa), opening January
2027 — confirmed live against its own site. `status_note` carries the
human-readable detail. This is the one entry `_extract_one()`'s
validation actively enforces: any entry with `status != "open"` must
carry a non-empty `status_note`, or the roster fails to parse that
entry (logged and skipped, not silently published without context).

**Clubs count and per-chapter geocoding result (ticket 018-008):**
4 curated Hack Club chapters, exactly the four issue 35 names —
`finder.hackclub.com` was deliberately **not** searched for additional
San Diego chapters this ticket (see `sources/
hack_club_static_roster.py`'s own docstring: the team-lead's Scope for
this ticket rules out an unattended web search as a discovery step,
the same "no unattended web search" discipline the FLL roster's own
precedent already established). Every chapter resolves to `"school"`
precision through the shared `geo_ladder.GeoLadder`'s real
school-matching rungs — never a guess, and never a hand override
(`school-overrides.toml` stays empty):

| Chapter | `host_school` (as curated) | Rung | `matched_name` | `needs_review` |
|---|---|---|---|---|
| University City HS | "University City High School" | 2 (CDE exact) | "University City High" | `false` |
| La Jolla HS | "La Jolla High School" | 2 (CDE exact) | "La Jolla High" | `false` |
| Helix Charter HS | "Helix Charter High School" | 3 (same-city fuzzy, Jaccard ≈0.67) | "Helix High" | **`true`** |
| Mater Dei Catholic HS | "Mater Dei Catholic High School" | 2 (NCES exact) | "Mater Dei Catholic High School" | `false` |

Helix Charter's `needs_review = true` is genuine, real-world residue,
not a bug: the curated `host_school` value ("Helix Charter High
School", the school's own name) does not exactly match CDE's own,
shorter record name ("Helix High"), so the ladder falls through rung 2
to rung 3's same-city (La Mesa) token-set match — Jaccard ≈0.67, above
the 0.60 acceptance threshold but below the 0.85 "confident enough to
skip review" bar. This is presented, not hidden, exactly matching
`teams.geo.SchoolIndex`'s own "flag it, don't silently guess" rule —
see §5's Open Questions for whether a future `school-overrides.toml`
entry should resolve it.

`host_school_website` (mirroring `Team.organization_website`) is
populated for the two San Diego Unified public-school matches
(University City High, La Jolla High) and Helix Charter's own rung-3
match, but stays `""` for Mater Dei Catholic — NCES's private-school
data carries no website column at all, matching
`geo_ladder.LocationMatch.website`'s own documented behavior. No
chapter's own `website`/`meeting_note` is populated this ticket (see
`sources/hack_club_static_roster.py`'s own docstring for why: neither
was confidently verified without the live research this ticket's scope
rules out — left honestly blank, never guessed).

## 3. Constraints and Invariants

- **`directory/` must never import `teams/`, anywhere in the package —
  and the reverse must also never happen.** Sprint 018's Design
  Rationale: importing `teams/` from `directory/` (or vice versa) is
  "a semantically backwards dependency" and risks a future circular
  import. Both modules depend on the shared `geo_ladder.GeoLadder`
  instead. `tests/directory/test_sources_base.py`'s
  `test_no_module_anywhere_under_directory_package_imports_teams` scans
  every `.py` file under `partner_scrape/directory/` via `ast`,
  matching `tests/teams/test_sources_base.py`'s own forbidden-import
  precedent — a future addition to this package that adds the
  forbidden import fails this test too, not just today's code.
- **Never register with `adapters.base.ADAPTERS`.** A place source
  registered there would become reachable from `pipeline.run()`, which
  would hand a `Place` object to `normalize.run()` — a type it does
  not expect — and crash. `PlaceSource` (`sources/base.py`) is its own
  `Protocol` with no import relationship to `adapters.base` at all,
  the identical guarantee `teams.sources.base.TeamSource` already
  established.
- **`sources/static_roster.py` never calls the injected `Fetcher`,
  structurally, not just by convention.** `discover()` returns a
  single `PlaceRef` whose `url` is a local filesystem path;
  `StaticRosterSource.fetch()` reads it via `Path.read_text()` and
  ignores `fetcher` entirely. `tests/directory/
  test_sources_static_roster.py`'s `TestNeverTouchesFetcher` asserts
  this with a `Fetcher` double that raises on any call, run through
  the full `sources.base.run()` chain — the same "runtime-call
  assertion" `teams/sources/static_roster.py`'s own test module uses.
- **Places never route through the shared ladder's organization-name
  school-matching rungs (1-4).** A `Place` has no sponsoring
  organization to match against a school directory — it is a venue,
  not a team. `directory.pipeline._apply_geo_fallback()` calls
  `GeoLadder.resolve_zip()`/`resolve_city()` directly (rungs 5-6 only),
  never `GeoLadder.locate()`, which would attempt the school rungs
  first. This is a deliberate scope narrowing versus `teams.geo.
  SchoolIndex.resolve()`, which does use the full ladder because a
  `Team`'s `organization` field is exactly what the school rungs are
  for.
- **Clubs, by contrast, *do* route through the shared ladder's full
  seven-rung ladder, school-matching rungs included (ticket
  018-008).** `directory.pipeline._apply_club_geocoding()` calls
  `GeoLadder.locate()` (not `resolve_zip()`/`resolve_city()` directly)
  because a `Club.host_school` genuinely is a sponsoring organization
  to match, mirroring `teams.geo.SchoolIndex.resolve()` almost exactly
  -- including copying a school-precision public-school match's
  website onto `Club.host_school_website`, the same role
  `Team.organization_website` plays. This is precisely the reason
  ticket 018-006 extracted `geo_ladder.GeoLadder` as a shared module in
  the first place (see that module's own docstring: "Clubs in
  particular need this: a Hack Club chapter ... is hosted by a real
  school").
- **No place entry's coordinates ever come from a live geocoder.**
  Every `Place.latitude`/`longitude` is either "address" precision
  (hand-curated directly in `places.toml`, verified against the
  venue's own site or a corroborating public source before being
  entered — never passed through a geocoding API) or "zip"/"city"
  precision (the shared ladder's own offline centroid tables) or
  entirely absent (`"none"`, never guessed).
  `tests/directory/test_dataset_validity.py`'s
  `TestNoLiveGeocodedCoordinate` and `tests/directory/
  test_sources_static_roster.py`'s
  `test_no_source_ever_calls_a_live_geocoder` both assert this
  structurally: the static-roster source itself only ever produces
  `"address"` or `"none"`.
- **`related_partner_id` is a deliberate, hand-verified join, never
  auto-derived.** Sprint 018 ticket 007's own instruction: "do not
  attempt an automatic cross-reference join this sprint... hand-copy
  the value." Every non-`None` `related_partner_id` in `places.toml`
  was checked against `site/src/data/partners.json`'s own `id` field
  by hand at authoring time; `tests/directory/test_dataset_validity.py`'s
  `TestRelatedPartnerIdJoinIntegrity` re-verifies every one still
  resolves to a real roster row (the same spot-check discipline ticket
  003's own `TestBatchARegistryJoinIntegrity` established) and spot-
  checks four of them against the expected org name.
- **`clubs.json` exists as of ticket 018-008, written from an
  independent `{"meta": ..., "clubs": [...]}` document, never nested
  inside `places.json`.** `directory/export.py`'s `export_directory()`
  gained an optional `clubs` keyword argument — `None` (the default,
  every ticket-007 call site's existing behavior) means "do not touch
  `clubs.json` at all"; a real (possibly empty) list writes it. See
  that module's own docstring for the full contract, including why the
  returned payload's `clubs_meta`/`clubs` keys are named differently
  from `meta`/`places` rather than colliding with them.
- **`directory` is one CLI subcommand covering both Places and Clubs,
  not two.** Per sprint.md's Open Questions recommendation ("one
  directory command ... mirrors teams"), confirmed by ticket 018-008:
  `run_directory()`'s own dispatch gained a `_CLUB_SOURCES` table
  alongside `_PLACE_SOURCES`, routed through **one combined dispatch
  loop** (not the literal second loop this document's ticket-007
  version anticipated) — see §4's Design section for why a second,
  Place-shaped loop would have logged a spurious warning for every real
  Club registry entry. No new CLI subcommand or flag was added.
- **Both `_apply_geo_fallback()` (Places) and `_apply_club_geocoding()`
  (Clubs) construct their own, separate `GeoLadder` instance when
  needed**, rather than sharing one loaded once per `run_directory()`
  call. A `Club` always needs the ladder (no `Club` ever carries a
  hand-curated coordinate); a `Place` almost never does (one entry,
  `atlas-labs`, as of this ticket). Deliberately not refactored into a
  single shared instance — the double data-file load this costs is
  negligible for this dataset's size (≈1,010 school rows), and keeping
  each fallback function independently testable against ticket 007's
  already-passing tests outweighs the minor duplication. Revisit only
  if `directory/data/`'s school files grow enough for the double-load
  cost to matter.

## 4. Design

**Why `Place` and `Club` are separate flat dataclasses from `Team`
(and from each other), not a shared base class.** See sprint.md's
Design Rationale in full; not re-derived here beyond the one-line
summary already in `directory/model.py`'s own docstring: a `Club` has
membership/program concerns a `Place` doesn't, and vice versa for
hours/category concerns — forcing a shared base would either grow
speculative optional fields on both or under-model one of them.
Field-name duplication (`website`, location fields, `sources`) with
`Team` is accepted, matching the existing `Team`/`Event` precedent —
and ticket 018-008 extends the same acceptance to `Place`/`Club`
themselves, for the identical reason.

**Why `PlaceSource`/`ClubSource` are two separate `Protocol`s in
`sources/base.py`, not one shared source contract (ticket
018-008).** `Place.extract()`/`Club.extract()` return different record
types, so a single generically-typed `Protocol` would either lose real
type-checking or need generic machinery this module's small scope
doesn't justify. Kept as two near-identical, clearly-typed protocols
(`PlaceRef`/`RawPlaceResponse`/`PlaceSource`/`run()` alongside
`ClubRef`/`RawClubResponse`/`ClubSource`/`run_club_source()`) instead —
the same "field-name duplication accepted, no shared base" tradeoff the
paragraph above makes for the record types, extended to their source
contracts for the identical reason.

**Why `run_directory()`'s registry dispatch is one combined loop, not
two separate ones, despite this document's own ticket-007 version
describing "a new `_CLUB_SOURCES` table and acquisition loop" (ticket
018-008).** A literal second `for` loop over the same `sources` list,
copy-pasted from the Place one, would make the *first* (Place) loop log
a spurious "no PlaceSource registered" warning for every real Club
registry entry — its `adapter_type` is never a key in `_PLACE_SOURCES`.
`pipeline.py`'s actual implementation checks `_PLACE_SOURCES` then
`_CLUB_SOURCES` per `source_config` inside one loop, so each registry
entry is dispatched to exactly the table it belongs to, and the
"unregistered" warning fires only when an `adapter_type` is in neither.
`tests/directory/test_pipeline.py`'s
`test_combined_dispatch_never_logs_a_spurious_place_warning_for_a_real_club_entry`
pins this down directly. **Alternative considered:** two literal
separate loops, matching this document's earlier forward-looking
wording exactly — rejected for the spurious-warning reason above; left
to "ticket 007/008's implementation judgment" by the original
Constraints note, which this resolves.

**Why `Club.website` and `Club.host_school_website` are two separate
fields (ticket 018-008), mirroring `Team.website`/
`Team.organization_website` exactly.** A chapter's own site/social
(when curated) and the sponsoring school's own site (copied from a
school-precision `geo_ladder.LocationMatch.website`) are genuinely
different facts with different provenance and different confidence —
collapsing them into one field would misrepresent whichever one didn't
win, and would make it impossible to tell "this chapter has no site of
its own" from "we found the school's site, not the chapter's."
`directory.pipeline._apply_club_geocoding()` is the only stage that
ever sets `host_school_website`; `Club.website` is set only by a
`ClubSource.extract()` (this ticket's roster leaves it blank for all
four chapters — see `sources/hack_club_static_roster.py`'s own
docstring).

**Why TSV, not TOML, for `hack-club-sd.tsv` — unlike Places' TOML
(ticket 018-008).** `places.toml` chose TOML because each `Place`
carries substantially more fields than a flat delimited table renders
cleanly (see the paragraph on `places.toml` below). A `Club` record is
narrower and closer in shape to the FLL roster's own six-column TSV —
`club_id`, `name`, `club_type`, `host_school`, `city`, `postal_code`,
`website`, `meeting_note`, `status`, `status_note` reads comfortably as
a flat table, so `sources/hack_club_static_roster.py` reuses the FLL
precedent's exact shape (`csv.DictReader`, `delimiter="\t"`) rather
than Places' TOML choice. This is a data-format choice, not a
behavioral one — every other convention (never touch `fetcher`,
per-record failure isolation, a local-path ref) is reused unchanged
across both `directory/` sources.

**Why TOML, not TSV, for `places.toml` — unlike the FLL roster's
TSV.** `teams/data/fll-sd-teams.tsv` derives from an upstream export
with a fixed, narrow six-column shape. This dataset has no upstream
export at all — every row was hand-researched from each venue's own
site or a corroborating public source (see `sources/
static_roster.py`'s own docstring for the full accounting, including
the web searches that determined which city libraries actually run a
maker-lab program). Each `Place` carries substantially more fields
than a flat delimited table renders cleanly, and this codebase already
uses TOML for exactly this shape of curated data
(`school-overrides.toml`, `zip-centroids.toml`) — an array of tables
(`[[place]]`) is the better fit. This is a data-format choice, not a
behavioral one; every FLL-precedent behavior (never touch `fetcher`,
per-entry failure isolation, a local-path ref) is reused unchanged.

**Why `directory/data/` duplicates `teams/data/`'s school-directory and
ZIP/city-centroid files instead of pointing at them directly.**
`geo_ladder.GeoLadder`'s constructor requires all five of its data
files (two school TSVs, one overrides TOML, two centroid TOMLs) to
exist under one `data_dir` — there is no way to hand it "just the
centroids." Since `directory/` must never import or reference
`teams/`'s own data path (see Constraints, above — that would recreate
the exact "backwards dependency" sprint 018 rejected, just via a file
path instead of a Python import), `directory/data/` carries its own
committed copy of every file `teams/data/` has. `zip-centroids.toml`/
`city-centroids.toml` were already byte-identical duplicates as of
ticket 007; ticket 018-008 is the school-directory files' own
first-real-use ticket (Places never needed them — see the Constraints
bullet on why), so `sd-schools-public.tsv`/`sd-schools-private.tsv` are
now populated as byte-identical duplicates too (see those files' own
header rows for the "re-copy by hand after a refresh" note this
paragraph's convention already established for the centroid files).
`school-overrides.toml` stays genuinely empty — no hand correction has
been needed for this ticket's four real chapters (see §2's per-chapter
table). **Alternatives considered:** (a) import `teams.geo.
DEFAULT_DATA_DIR` directly — rejected, recreates the forbidden
dependency; (b) move the shared files to a new common location both
`teams/` and `directory/` point at — rejected as out-of-scope (ticket
018-006 already shipped `teams/geo.py`'s `DEFAULT_DATA_DIR` unchanged
at `teams/data/`; relocating it now would relitigate a closed ticket's
decision for a benefit — saving the duplicated, low-churn school/
centroid data's line count — that does not justify reopening it).

**Why `_apply_geo_fallback()`/`_apply_club_geocoding()` each construct
a `GeoLadder` only when at least one record actually needs it.** For
Places, that is exactly one entry (`atlas-labs`) as of this ticket —
every other place already carries a hand-curated, address-precision
coordinate, so a `directory` run whose static roster resolved
everything by hand never pays the ladder's five-data-file loading cost
at all. For Clubs, every real curated chapter needs the pass (no
`Club` ever carries a hand-curated coordinate), so this guard mainly
protects the `--source places-sd`-filtered case where `clubs` is
legitimately empty. `tests/directory/test_pipeline.py`'s
`test_geo_ladder_is_never_constructed_when_nothing_needs_fallback` /
`test_geo_ladder_is_never_constructed_for_an_empty_club_list` both
prove this directly (a nonexistent `data_dir` would make
`GeoLadder(...)` raise if it were ever constructed). See the
Constraints section above for why these two functions each construct
their own `GeoLadder` instance rather than sharing one loaded once.

**Why `export_directory()` sorts Places by `(category, name)` and
Clubs by `(club_type, name)`, rather than `teams/export.py`'s
`(league, natural_number)`.** Neither has a natural numeric ordering
the way a robotics team number does; grouping by category/type (so a
visitor sees "every planetarium together," or "every Hack Club chapter
together," etc.) then alphabetically by name is the natural reading
order for either "where to go any day" or "which clubs meet here"
reference.

**Why `Offering` is one model serving both issue 14 Strategy B
(volunteer org profiles) and issue 33 part 2 (free/Title I school
programs), not two (sprint 030).** *Decision:* a single `Offering`
dataclass with an `offering_type` discriminator (`"volunteer"` |
`"free_program"`). *Context:* both are undated, standing, org-hosted
"here's what we offer and how to get it" records with the same core
shape — org, title, description, eligibility, how-to-book, link-out,
last-verified — differing only in which of those fields a given row
actually populates (`age_minimum` for volunteer rows, a Title-I/grade
eligibility string for free-program rows). *Alternatives considered:*
(a) two separate models (`VolunteerProfile`, `FreeProgram`) — rejected,
this would duplicate the entire field set for a distinction that is
genuinely just one enum value, and would need two registries, two
sources, two export sections, and two site sections for what a reader
experiences as one kind of page ("this org's standing offer"); (b)
extend `Place` with optional volunteer/program fields — rejected, a
`Place` is a locatable venue by definition (see `Place`'s own docstring
and this doc's §4 "why separate dataclasses" precedent) and most
`Offering`s are not venues at all, just a link and a policy. *Why this
choice:* matches this module's own established pattern of "one model
per distinct standing-entity shape, not one model per data source" —
`Place` already serves multiple categories (makerspace, planetarium,
tide-pool, ...) through one model with a `category` discriminator; this
is the identical move applied to a new shape. *Consequences:* a future
third standing-entity "offering" type (a scholarship program, a grant)
fits by adding an `OfferingType` value and a small validation-rule
branch (mirroring `status`/`status_note`'s existing per-status-value
validation), not a new model — the same "kept general enough" property
`Club`'s own Design Rationale already claims for `ClubType`.

**Why `Offering` has no geocoding/location fields at all, the one
structural way it is not a mechanical copy of `Club`'s addition.** See
this doc's Revision section above for the full argument (an `Offering`
is not a place to travel to). *Consequences worth flagging explicitly:*
if a future stakeholder ever wants Offerings plotted on a map (e.g. "show
me volunteer orgs near me"), that is a real, non-trivial follow-up — it
would need either a `related_partner_id`-mediated join to that partner's
already-geocoded location (feasible today, since the join field already
exists) or the same location/`GeoLadder` machinery `Place`/`Club` already
carry (a real model change). Not attempted this sprint; not blocking
either, since `related_partner_id` alone gets a consumer most of the way
there without any code change here.

**Why `Offering.related_partner_id` reuses `Place`'s hand-verified-join
convention rather than inventing a new one.** Same rationale as that
convention's own original justification (sprint 018 ticket 007: "do
not attempt an automatic cross-reference join ... hand-copy the
value") — an `Offering`'s operating org is exactly the kind of fact a
human curating 13 rows can verify by hand faster and more reliably than
building an auto-join would take, and auto-joining organization names
correctly (fuzzy name matching against `partners.json`) is a
non-trivial problem this addition has no need to solve.

## 5. Open Questions

- Should a future sprint give `Offering` a `related_partner_id`-mediated
  location so a consumer can plot volunteer orgs / free-program hosts on
  a map, per this doc's Design Rationale above? Deferred — no
  stakeholder request yet; flagged so the option is visible when one
  arrives.
- Should `Offering`'s `age_minimum` grow a companion `age_maximum` or a
  `commitment_note` (e.g. "6-month minimum," matching Fleet's
  `VolunteerMatters` requirement per issue 14's research) if a future
  curation pass finds more volunteer orgs with structured commitment
  terms beyond a simple minimum age? Left out this sprint — none of the
  six curated volunteer orgs' publicly stated terms needed more than
  `age_minimum` plus free-text `how_to_book` to represent accurately;
  revisit if a future org's terms don't fit.
- Should `directory/data/`'s duplicated ZIP/city-centroid files be
  refreshed automatically alongside `teams/data/`'s own copies (e.g. by
  extending `dev/refresh_school_directories.py` to write both
  locations), rather than "re-copy by hand"? Deferred — the data
  changes rarely (Census ZCTA/CDE school-directory refreshes are
  roughly yearly) and this ticket did not touch `dev/
  refresh_school_directories.py`. Worth revisiting if the two copies
  are ever found to have drifted.
- Should Coronado and National City libraries be re-checked
  periodically for a maker-lab program launch, given they were
  confirmed absent only as of this ticket's research pass (2026-08-31)?
  No monitoring exists for this (curated data is described as
  near-zero-maintenance per sprint.md's Scope) — revisit only if a
  stakeholder reports one has since opened.
- Should `finder.hackclub.com` be researched (by a human, not an
  unattended agent web search) for additional San Diego-area Hack Club
  chapters beyond the four issue 35 named? Deferred by this ticket's
  own scope — a future curation pass can add rows to
  `hack-club-sd.tsv` by hand once someone has actually verified a
  chapter against the live finder, the same discipline this ticket
  already applied to the four it did curate.
- Should Helix Charter High School's `needs_review = true` (rung-3
  same-city fuzzy match, Jaccard ≈0.67, see §2's table) be resolved
  with a `school-overrides.toml` entry once a human has verified the
  coordinate independently? Left as a genuine, honestly-flagged match
  rather than force-resolved this ticket — the ladder's own "flag it,
  don't silently guess" rule is working as intended here, not failing.
- Should `Club.website`/`Club.meeting_note` be populated for the four
  curated chapters in a future pass, once someone has verified a
  per-chapter URL/meeting schedule against `finder.hackclub.com` or the
  school's own site? Both fields exist on the model and the roster's
  own TSV schema; this ticket leaves them blank rather than guess (see
  `sources/club_static_roster.py`'s own docstring).
- ~~Should issue 35b's remaining six club types (CyberPatriot, Science
  Olympiad, 4-H, Girls Who Code, Civil Air Patrol, Sea Cadets) each get
  their own `ClubSource` (e.g. `cyberpatriot_static_roster.py`) reusing
  `ClubType`'s Literal (widened to include the new value) and the
  existing `_CLUB_SOURCES` dispatch table, or would any of them need a
  structurally different source shape (e.g. a live feed, if one is ever
  found)?~~ **Resolved by sprint 032 ticket 001** (see this doc's
  sprint 032 Revision, above): one generalized `ClubStaticRosterSource`
  (`sources/club_static_roster.py`) serves all seven club types
  through the existing `_CLUB_SOURCES` dispatch table, keyed by
  `adapter_type = "club_static_roster"` — no per-type source module.
  Curating each of the six new types' actual roster content is left to
  sprint 032 tickets 002-007, in descending order of how likely a
  public roster exists.
