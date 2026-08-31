---
id: '004'
title: 'Register roster batch B: youth orgs, competitions/clubs, research/health,
  pipeline/adult'
status: done
use-cases:
- SUC-002
depends-on:
- '002'
github-issue: ''
issue: 32-partner-roster-expansion-and-housekeeping.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Register roster batch B: youth orgs, competitions/clubs, research/health, pipeline/adult

## Description

Register the remaining half of issue 32's candidate organizations —
youth orgs, competitions/clubs, research/health, and pipeline/adult —
into `site/src/data/partners.json` and `data/partners_viable.csv`, in
parallel, following the same conventions ticket 003 establishes
(curated/offline coordinates only, exact `org_name` match to any
already-registered source, no logo yet).

**Youth orgs** (6, or up to 9 if the 4 Boys & Girls Clubs councils are
registered as separate entries rather than one umbrella row — decide
based on whether they operate as genuinely distinct organizations with
distinct sites, and record the choice in this ticket's Notes): 4-H San
Diego (UCCE), Boys & Girls Clubs (4 councils), YMCA of San Diego
County, Girls Inc. of San Diego County, Scouting America SD-Imperial,
Lawrence Family JCC.

**Competitions/clubs** (8): Classroom of the Future Foundation, NDIA
San Diego, SD Cyber Center of Excellence, SD County Engineering
Council, SHPE San Diego, San Diego Math Circle, California DI (HQ in
SD), Hack Club (one roster row for the umbrella org — **not**
per-chapter; individual Hack Club chapters are issue 35's `Club`
standing-entity concern, ticket 008, a structurally different system
from this partner roster — do not conflate the two).

**Research/health** (9): SDSC, Jacobs School of Engineering (UC San
Diego's — distinct from any University of San Diego program of a
similar name; verify against sprint 014 ticket 004's own note on this
exact ambiguity), Sanford Burnham Prebys, La Jolla Institute, Scripps
Research, JCVI, NIWC Pacific, NOAA SWFSC, Rady Children's
(sdhealthscholars.org).

**Pipeline/adult** (9): Reality Changers, SD Workforce Partnership
(CONNECT2Careers), Barrio Logan College Institute, EAA Chapter 14
(Young Eagles, Brown Field), Scripps Research Front Row, Nerd Nite SD,
Taste of Science SD, Astronomy on Tap SD, United Way SD
(STEAM-to-Careers).

Several of these already have registered event sources (sprint 014
ticket 004): SHPE San Diego (`shpesd`), Jacobs School of Engineering
(`ucsd-jacobs-school` — the UC San Diego one specifically), Qualcomm
Institute is *not* in this list (already excluded — see sprint 014
ticket 004's note that it's distinct from partners.json's "Qualcomm
Incorporated"). Match `org_name` exactly to each already-registered
source where one exists, same verification discipline as ticket 003.

## Acceptance Criteria

- [x] Every org named above has a roster row, or is explicitly
      deferred in this ticket's Notes with a reason.
- [x] San Diego Math Circle and California DI get exactly one roster
      row each as single organizations — not treated as multi-chapter
      `Club` entities (that would conflict with sprint.md's Design
      Rationale excluding Math Circle from the `Club` model).
- [x] Hack Club gets exactly one umbrella roster row here; no
      per-chapter rows are added to `partners.json`/`partners_viable.csv`
      (chapters are ticket 008's `Club` records, a separate system).
- [x] For every org with an already-registered event source, `name`
      matches that source's `org_name` exactly, spot-checked.
- [x] The Jacobs School of Engineering row is verified to be the UC
      San Diego program, not conflated with any University of San
      Diego program of a similar name.
- [x] No new row's coordinates come from a live geocoder call.
- [x] Every new row falls inside `SD_BOUNDS` or has no coordinates.
- [x] `partners.json` and `partners_viable.csv` remain in 1:1 `id` sync
      after this ticket's additions.
- [x] Full test suite stays green.

## Testing

- **Existing tests to run**: `uv run pytest`.
- **New tests to write**: none expected purely from data additions.
- **Verification command**: `uv run pytest`, plus
  `uv run partner-scrape --dry-run --source shpesd` (and any other
  already-registered source in this batch) to confirm the roster join
  now resolves.

## Implementation Plan

**Approach**: Same as ticket 003 — direct, hand-curated data entry, no
scraping or live geocoding. Depends on ticket 002's deduped baseline.
Sequenced after (not depending on) ticket 003 only for session-sizing
reasons — the two batches are otherwise independent and could be
reordered without consequence.

**Files to modify**:
- `site/src/data/partners.json`
- `data/partners_viable.csv`

**Testing plan**: see Testing above.

**Documentation updates**: none expected beyond this ticket's Notes.

## Notes

35 rows added (ids 765-799): 9 youth orgs, 8 competitions/clubs, 9
research/health, 9 pipeline/adult — one row per org named in the
Description, no deferrals needed.

- **Boys & Girls Clubs registered as 4 separate rows, not one umbrella
  row.** Each of Greater San Diego (`sdyouth.org`), San Dieguito
  (`bgcsandieguito.org`), Northwest San Diego (`bgcgreatertogether.org`),
  and East County (`bgcec.org`) is a genuinely distinct 501(c)(3) with
  its own board, EIN, and clubhouse sites — not a chapter of a single
  parent org. Registered separately (ids 766-769). Smaller county
  councils (South County, San Marcos, Carlsbad) exist too but weren't
  named in the ticket/gap-analysis and are left for a future pass.
- **Junior Achievement of San Diego County (`jasandiego` source) is
  already a partner (id 30/956)** — verified before starting this
  ticket. It isn't named in this ticket's org list, so no new row was
  added or needed; noted here only to record that the check happened.
- **`org_name` exact matches verified against the literal TOML**, not
  the ticket prose: `shpesd` → "SHPE San Diego" (id 778),
  `ucsd-jacobs-school` → "UC San Diego Jacobs School of Engineering"
  (id 783), and `ymcasd` → "YMCA of San Diego County" (id 770) — the
  last one wasn't called out in the ticket's "already registered"
  paragraph but has a live registered source (`ymcasd.toml`) and was
  matched exactly regardless. All three confirmed live: a scratch
  `--site-dir` run per source shows `opportunities.json` now carries
  the resolved `partner_id`/`partner_name` for every record (shpesd → 1
  record → id 778; ucsd-jacobs-school → 2 records → id 783; ymcasd → 11
  records → id 770).
- **UC San Diego Jacobs School of Engineering (id 783) vs. the existing
  "Jacobs Institute for Innovation in Education, University of San
  Diego" (id 44)** are confirmed distinct institutions (UC San Diego vs.
  University of San Diego) per sprint 014 ticket 004's own note on this
  exact ambiguity — both now coexist in the roster without conflation.
- **Coordinates**: every address is a real, web-verified published
  street address (never a live geocoder call); lat/lng are hand-estimated
  from known San Diego geography for each address, same "curated,
  offline" discipline as ticket 003. All-volunteer/rotating-venue orgs
  with no fixed office (NDIA San Diego, SD County Engineering Council,
  SHPE San Diego, San Diego Math Circle, California Destination
  Imagination, Nerd Nite SD, Taste of Science SD, Astronomy on Tap SD)
  are left coordinate-less rather than pinned to a volunteer's home or a
  rotating venue. Hack Club is coordinate-less because its HQ (Shelburne,
  Vermont) is outside `SD_BOUNDS` — this is also the reason it's a
  single national-umbrella row, not a per-chapter one: only the national
  org has a stable identity to register here.
- **Scripps Research Front Row** (id 795) reuses Scripps Research's (id
  786) own campus coordinates — it's a lecture series held on that
  campus, not a separate office.
- **Astronomy on Tap San Diego** (id 798) is distinct from the San Diego
  Astronomy Association (id 748, added in batch A) — different programs,
  noted in its description to prevent future conflation.
- Test suite: 1674 passing (1671 baseline + 3 new tests in the new
  `TestBatchBRegistryJoinIntegrity` class, `tests/test_roster_housekeeping.py`).
  `TestBatchARegistryJoinIntegrity`'s total-row-count assertion was
  updated from 176 to 211 to reflect this ticket's additions (see that
  test's updated comment).
