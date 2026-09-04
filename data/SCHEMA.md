# `data/` — published output schema

This directory is the **complete, self-contained published output** of the
partner-scrape pipeline: San Diego STEM opportunities, robotics teams, and
curated standing-entity directories. It is the only write target the pipeline
has, and it is committed to git.

If you are an agent reading this to use the data: everything you need is in
this directory. You do not need the source code, the registry, or the
`stem-ecosystem` site repo to interpret any file here.

**Boundary (since sprint 025):** partner-scrape *publishes* to `data/`; it never
writes into the sibling `stem-ecosystem` checkout. Consumers pull from here.
The one thing that flows the other way is the curated partner roster, which
partner-scrape *reads* from `stem-ecosystem/src/data/partners.json` and
re-publishes here as a projection — see `partners.json` below.

---

## File map

| File | Shape | Contents |
|---|---|---|
| `opportunities.json` | bare array | Current + upcoming dated opportunities. **No envelope** — metadata is in `scrape-meta.json`. |
| `scrape-meta.json` | object | `last_updated` (UTC ISO-8601) and `regions` (per-region counts of the exported set). |
| `partners.json` | envelope | `generated_at`, `partner_count`, `partners[]` — the curated roster projected, each with `slug`, `events_url`, `past_events_url`. |
| `partners/<slug>/events.json` | envelope | `generated_at`, `partner_slug`, `kind: "current"`, `event_count`, `events[]`. |
| `partners/<slug>/past-events.json` | envelope | Same, `kind: "past"`. |
| `teams.json` | envelope | `meta` + `teams[]` — FIRST robotics teams (FRC/FTC/FLL, and VEX when credentialed). |
| `places.json` | envelope | `meta` + `places[]` — curated makerspaces, planetariums, observatories, tide pools, nature centers, library maker labs. |
| `clubs.json` | envelope | `meta` + `clubs[]` — curated club chapters/units/teams. |
| `offerings.json` | envelope | `meta` + `offerings[]` — **undated** standing offerings: volunteer profiles and free/Title I school programs. |
| `ads.json` | bare array | League ad slots (`headline`, `body`, `link`, `logo_src`). |
| `yield-history.json` | object | Per-source yield history keyed by `source_id`, plus a `__regions__` key. Operational telemetry, not site content. |
| `images/opportunities/` | files | Event images, content-hashed filenames, resized to 1600px long edge / JPEG q80 on fetch. |

### Dated vs. undated — read this before choosing a file

- **`opportunities.json`** holds things that happen on a **date**. It is
  filtered to current + upcoming only.
- **`offerings.json`** holds things with **no date** — an ongoing volunteer
  program, a bookable free field trip. These never appear in
  `opportunities.json`, and looking for them there will find nothing.
- **`places.json` / `clubs.json`** hold **standing entities** — a physical
  place, a club that exists. Also undated.
- **`partners/<slug>/*.json`** is the **append-only history** per partner:
  `events.json` (current/upcoming) plus `past-events.json` (everything that
  has aged out). `opportunities.json` is a current-only snapshot; the
  per-partner store is the durable record and holds more.

---

## `opportunities.json` — 26 fields

`slug`, `title`, `partner_name`, `partner_id`, `description`, `link`,
`availability`, `date_start`, `date_end`, `age_grade_level`, `cost_range`,
`time_of_day`, `opportunity_type`, `areas_of_interest`, `specific_attention`,
`financial_support`, `ngss_aligned`, `location`, `latitude`, `longitude`,
`contact_name`, `contact_email`, `contact_phone`, `logo_src`, `eligibility`,
`image_src`

The same field set is used for the `events[]` arrays in the per-partner files.

Notes on individual fields:

- `slug` — stable identity, derived from the event URL.
- `partner_id` — joins to `partners.json` `partners[].id`. May be absent when
  the source org is not on the curated roster.
- `date_start` / `date_end` — ISO dates. `date_end` may be empty.
- `availability` — a human-readable string, not an enum. Observed prefixes:
  `Apply by <date>`, `Opens ~<date>`, `Rolling`, `Repeats N times through
  <date>`, or empty. `Opens ~` means the application window has not opened
  yet.
- `latitude` / `longitude` — present on most records but **not all** (352 of
  360 in the current run). Do not assume they exist.
- `image_src` — present on roughly half the records; points into
  `images/opportunities/`. Absent is normal, not an error.
- `contact_*` — almost always empty. The pipeline deliberately does not
  harvest contact details.
- `financial_support`, `ngss_aligned` — currently always `"No"`. Treat as
  not-yet-populated rather than as a meaningful negative.

### Controlled vocabularies

Unlike `teams.json`/`places.json`/`clubs.json`/`offerings.json`, whose
vocabularies are real Python `Literal` types with a drift-proof
`frozenset` derived from them (see "Maintaining this document" for the
`teams.json` drift-guard test), every vocabulary below except
`specific_attention` is only *prompt guidance* given to the Haiku
classifier (`enrich/llm_client.py`) — nothing validates the model's
answer against it on the way out. The lists below are the classifier's
own controlled list, and match what you'll see almost all the time, but
a handful of records in the current corpus carry a value outside it:
`"Artificial Intelligence"` on 1 `areas_of_interest` record, `"Grades
3-5"` on 1 `age_grade_level` record, `"Paid stipend"` and `"Less than
$1000"` on 1 `cost_range` record each, `"Late Morning"` on 2
`time_of_day` records. Treat these lists as "what to expect," not a
hard enum to validate against.

`opportunity_type` (single value):
`Out-of-school Programs`, `Online`, `Professional Development / Conferences`,
`School Programs`, `Career Connections`, `Volunteering`,
`Funding Opportunities`, `Camps`, `Competitions`, `Work-based Learning`

The first nine come from the LLM classifier's controlled list.
`Work-based Learning` is never one of the classifier's own choices:
every event with `kind == "internship"` (set only by the six ATS
adapters — Greenhouse, Lever, SmartRecruiters, Workday, NEOGOV,
Workable) has its `opportunity_type` unconditionally forced to
`Work-based Learning` by `normalize/run.py`, overriding whatever the
classifier said.

`areas_of_interest` (array): `Biology / LifeSciences`,
`Earth Science/Ecology`, `Coding/Computer Science/Cyber Security`,
`Engineering`, `Physical Science`, `Mathematics`, `Chemistry`, `Physics`,
`General Science`

`age_grade_level` (array): `Family`, `Pre-K`, `Grades 9-12`, `Grades 6-8`,
`Adult`

`cost_range` (single): `Free`, `Less than $25`, `Less than $50`,
`Less than $100`, `Less than $200`, `Greater than $200`

`time_of_day` (array — usually one value, occasionally two for a program
that spans both, e.g. `["Morning", "Afternoon"]`, or empty): `Morning`,
`Afternoon`, `Evening`, `All Day`

`specific_attention` (array, sparse): `Programs in Spanish`,
`Programs for students with disabilities`. Keyword-derived rather than
LLM-classified, so unlike the vocabularies above this really is a closed
set — but it is still a floor on what qualifies, never a complete
census — absence does not mean a program lacks that attribute.

**Deadline-first types** — `Competitions`, `Work-based Learning`,
`Funding Opportunities`. For these the application deadline drives currency,
not the event date, and a record with no `date_end` is bounded to 365 days
rather than treated as open forever.

**Region** is derived but is *not* a field on the record. Per-region counts
live in `scrape-meta.json` under `regions`: `Central San Diego`, `East County`,
`North County Coastal`, `North County Inland`, `South Bay`, plus
`unclassified`. Region is inferred from the location string by keyword, so
`unclassified` is common and means "no keyword matched," not "outside the
county."

---

## `teams.json` — 30 fields

`team_id`, `league`, `program`, `number`, `name`, `organization`, `org_type`,
`city`, `postal_code`, `latitude`, `longitude`, `location_precision`,
`in_region`, `matched_name`, `needs_review`, `website`, `website_status`,
`organization_website`, `social`, `description`, `description_status`,
`description_provenance`, `description_fetched_at`, `rookie_year`, `active`,
`last_season`, `sponsors`, `sponsor_provenance`, `org_key`, `sibling_team_ids`

`meta`: `generated`, `total`, `by_league`, `out_of_region`,
`by_location_precision`, `credential_failures`.

- `number` is a **string**, not an integer (teams sort naturally, not
  numerically).
- `org_key` / `sibling_team_ids` link teams that share a host organization.
- **`website_status` and `description_status` are deliberately independent.**
  `website_status` says the site is reachable; `description_status`
  (`generated` / `unavailable` / `none`) says whether there is content worth
  showing. Do not collapse them into one flag — a team can have a live site
  with nothing publishable on it.
- **`meta.credential_failures`** lists leagues that were never attempted
  because an API key was missing. A league in this array has **no data**, which
  is a completely different thing from a league that genuinely has zero teams.
  Always check it before concluding a league is empty. `VEX` is currently
  listed (`ROBOTEVENTS_KEY` is unprovisioned).
- **Sprint 036 ticket 006** added two curated, static-roster-sourced
  `league` codes beyond the pre-sprint-036 robotics set (see
  `teams/DESIGN.md`'s sprint 036 §2/§7 for full detail): `MATHCOUNTS`
  (13 teams — every school that fielded a team at the 2026 San Diego
  Chapter MATHCOUNTS Competition, per cspeef.org's official, dated
  results PDF) and `TARC` (1 team — American Rocketry Challenge; Del
  Norte High School, the only San Diego-area team on
  rocketrychallenge.org's 2026 National Finalists page. **This is a
  national-finalist subset, not a census of San Diego rocketry teams**
  — that page surfaces only the top-100-of-1,107 national cutoff, so
  most actual San Diego-area TARC entrants are not represented). Like
  every other static-roster league (`FLL`, `SCIOLY`, `CYBERPATRIOT`),
  neither `MATHCOUNTS` nor `TARC` can ever appear in
  `meta.credential_failures`. (`teams.json`'s overall shape/count/
  vocabulary is being brought fully up to date across sprint 036's
  whole arc by a follow-on documentation ticket; the count/vocabulary
  notes above are current as of ticket 006 specifically.)

---

## `places.json` — 16 fields

`place_id`, `name`, `category`, `description`, `address`, `city`,
`postal_code`, `latitude`, `longitude`, `location_precision`, `matched_name`,
`needs_review`, `website`, `status`, `status_note`, `related_partner_id`

`category`: `makerspace`, `planetarium`, `observatory`, `tide-pool`,
`nature-center`, `library-maker-lab`.

## `clubs.json` — 16 fields

`club_id`, `name`, `club_type`, `host_school`, `city`, `postal_code`,
`latitude`, `longitude`, `location_precision`, `matched_name`, `needs_review`,
`website`, `host_school_website`, `meeting_note`, `status`, `status_note`

`club_type`: `4-h`, `civil-air-patrol`, `cyberpatriot`, `girls-who-code`,
`hack-club`, `science-olympiad`, `sea-cadets`.

VEX teams are **not** here — they arrive through the RobotEvents adapter and
belong in `teams.json`.

## `offerings.json` — 13 fields

`offering_id`, `org_name`, `title`, `offering_type`, `description`,
`eligibility`, `age_minimum`, `how_to_book`, `link_url`, `last_verified`,
`status`, `status_note`, `related_partner_id`

`offering_type`: `volunteer`, `free_program`.

- **`age_minimum` is a typed integer or `null`**, never prose — it is the
  field to filter on for a teen audience. Several volunteer programs are 18+
  (Fleet, San Diego Zoo Wildlife Alliance) and some are 16+ (Birch). A `null`
  means no numeric minimum was stated, not that there is none.
- `eligibility` and `how_to_book` are the load-bearing free-text fields for
  `free_program` records — that is where Title I rules and lead times live.
- Offerings carry **no location fields at all**, by design: an offering is a
  program run by an already-locatable org, not a place you travel to. Join
  through `related_partner_id` for geography.

---

## Joining across files

- `opportunities.json` `partner_id` → `partners.json` `partners[].id`
- `places.json` / `offerings.json` `related_partner_id` → same
- `partners.json` `partners[].events_url` / `past_events_url` → paths
  relative to this directory
- `teams.json` `org_key` groups sibling teams; `sibling_team_ids` names them
- `yield-history.json` keys are `source_id` values from the registry — useful
  for "did this source stop producing," not for site content

`related_partner_id` is a **hand-verified** join. Where it is unset, it was
deliberately left unset rather than guessed.

---

## Trust and provenance signals

The pipeline is built to be honest about uncertainty rather than to look
complete. Read these before treating any record as ground truth:

- **`needs_review: true`** — a fuzzy match that a human has not confirmed.
  Present on teams, places, and clubs.
- **`location_precision`** — two separate scales, not one shared ranking.
  `places.json` uses `address` > `zip` > `city` > `none` (`address` is a
  hand-curated venue coordinate; a Place has no sponsoring organization
  to run through the school-matching ladder). `teams.json`/`clubs.json`
  use `school` > `zip` > `city` > `none` (`school` is a matched
  sponsoring-organization address; neither Team nor Club is ever
  `"address"`-precision). A `city`-precision coordinate is a city
  centroid, not the actual site. This is expected for entities that meet
  at non-school facilities (Civil Air Patrol squadrons at airfields, 4-H
  clubs at granges); it is not a defect.
- **`status` / `status_note`** — not currently operating looks different per
  file: a place is `open` / `opening` / `closed`; a club is `active` /
  `inactive`; an offering is `active` / `seasonal` / `closed`.
  `status_note` is always non-empty whenever `status` isn't the "normal"
  value. Check before presenting a record as available.
- **`matched_name`** — the directory entry the geocoder matched against, so a
  wrong match is auditable rather than silent.
- **`meta.credential_failures`** (teams) — see above.

Records that could not be verified are omitted or flagged, not padded. A small
count usually means the curated list is genuinely small, not that extraction
failed.

---

## Traps

- `opportunities.json` has **no metadata envelope**. Read `scrape-meta.json`
  for `last_updated`. Every other collection file has a `meta` block.
- **Zero is often correct.** ATS/job-board sources return zero matching
  postings for long stretches by design — that is the labor market, not a
  broken pipeline. Same for seasonal sources out of season.
- **Not every registered source is enabled.** Sources blocked by robots.txt,
  a WAF, or a login wall are registered disabled with a reason. Their absence
  from the data is deliberate.
- `partners.json` here is a **projection**. The curated source of truth is
  `stem-ecosystem/src/data/partners.json`; edits belong there, not here.
- Images are **content-hashed and additive** — a filename never changes
  meaning, and old images are retained because the per-partner history still
  references them.

---

## How this directory is regenerated

Three separate commands. The main pipeline does **not** write the directory
or teams files:

```sh
set -a && . ./.env && set +a     # required: the CLI does not load .env itself
uv run partner-scrape -v         # opportunities, scrape-meta, ads, partners, images
uv run partner-scrape directory  # places, clubs, offerings
uv run partner-scrape teams      # teams
```

`SCRAPE_CACHE_DIR` and `ANTHROPIC_API_KEY` are required; `TBA_KEY` (FRC),
`ROBOTEVENTS_KEY` (VEX), and `LEAGUESYNC_API_KEY` (League classes) each gate
one source and degrade with a typed alert rather than crashing.

---

## Maintaining this document

The field lists above are transcribed from the exporters' own schema
constants, which are the authority:

| Section | Constant |
|---|---|
| `opportunities.json` | `partner_scrape/export/writer.py` → `SITE_SCHEMA_FIELDS` |
| `teams.json` | `partner_scrape/teams/export.py` → `TEAMS_SCHEMA_FIELDS` |
| `places.json` | `partner_scrape/directory/export.py` → `PLACES_SCHEMA_FIELDS` |
| `clubs.json` | `partner_scrape/directory/export.py` → `CLUBS_SCHEMA_FIELDS` |
| `offerings.json` | `partner_scrape/directory/export.py` → `OFFERINGS_SCHEMA_FIELDS` |

Any sprint that changes one of those constants, adds an `opportunity_type` or
other vocabulary value, or adds a published file must update this document in
the same ticket. There is no automated drift guard on this file yet — the
`TEAMS_SCHEMA_FIELDS` drift-guard test from sprint 017 is the pattern to
follow if you add one.

Last verified against a real pipeline run: **2026-09-02** — 360
opportunities, 278 teams, 19 places, 57 clubs, 13 offerings, 211 partners.
