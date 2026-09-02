---
id: '002'
title: Populate volunteer org profiles (issue 14 Strategy B)
status: done
use-cases:
- SUC-050
depends-on:
- '001'
github-issue: ''
issue: 14-improve-volunteer-opportunity-discovery.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Populate volunteer org profiles (issue 14 Strategy B)

## Description

Add real, hand-curated `[[offering]]` rows (`offering_type =
"volunteer"`) to `directory/data/offerings.toml` for the six orgs issue
14's 2026-08-30 research update named as Strategy B's target list:
Fleet, SDZWA, Birch, the Nat, ILACSD, and San Diego River Park
Foundation. Data-only ticket — no code changes beyond what ticket 001
already shipped.

**Age minimums are the load-bearing fact of this ticket** (issue 14's
own instruction: "Note age minimums explicitly ... it matters for the
teen audience"): Fleet 18+ (`VolunteerMatters`, 6-month commitment —
capture the commitment in `how_to_book`'s free text, there is no
separate structured field for it this sprint, see `directory/DESIGN.md`
Open Questions), SDZWA 18+ (`Volgistics`), Birch 16+ (`Volgistics`).
For the Nat, ILACSD, and San Diego River Park Foundation, research each
org's own stated age policy directly (do not assume 18+ by default —
`age_minimum` stays `None` if the org states no minimum, never guessed).

## Acceptance Criteria

- [x] `directory/data/offerings.toml` has exactly six new
      `offering_type = "volunteer"` rows: Fleet, SDZWA, Birch, the Nat,
      ILACSD, San Diego River Park Foundation.
- [x] Fleet's `age_minimum = 18`, SDZWA's `age_minimum = 18`, Birch's
      `age_minimum = 16` — matching issue 14's research verbatim.
- [x] The Nat's, ILACSD's, and San Diego River Park Foundation's
      `age_minimum` reflects each org's own actually-published policy
      (a real value or `None` if the org states none) — not a copied
      default.
- [x] Every row's `link_url` points to that org's actual volunteer
      portal/application page (Volgistics/VolunteerMatters/Galaxy
      Digital or the org's own "get involved" page), verified live.
- [x] Every row's `description` states what volunteers actually do at
      that org, in the org's own words where possible.
- [x] Every row's `related_partner_id` is hand-checked against
      `site/src/data/partners.json`'s `id` field where a confident
      match exists; left `None` otherwise — never guessed.
- [x] `uv run partner-scrape directory --source offerings-sd --dry-run -v`
      (real, not fixture, run against the static roster — this reads
      local TOML, not the network, so it is safe under this sprint's
      no-live-network-in-tests constraint) shows all six rows parsed
      with no validation warnings.

## Notes (execution)

- **`--source offerings-sd` in this AC's literal command does not
  filter anything** — `directory`'s `--source` flag matches
  `adapter_type`, not a Registry file's stem/`source_id` (see
  `cli.py`'s own `--source` help text and `_run_directory()`); the
  correct value is `--source offering_static_roster`. Ran with the
  corrected flag: `uv run partner-scrape directory --source
  offering_static_roster --dry-run -v` → `INFO ... Offering source
  'offerings-sd' yielded 7 offering(s)` (six real volunteer rows plus
  ticket 001's still-outstanding `free_program` placeholder, replaced
  by ticket 003) — no validation warnings logged, and
  `_check_related_partner_references()`'s join-integrity guard passed
  silently against the real sibling `stem-ecosystem` checkout's
  `src/data/partners.json`.
- **`related_partner_id` join target**: `site/src/data/partners.json`
  (this ticket's and the design docs' own path) does not exist inside
  this repo as of sprint 019 (`site/` is a build-time-only checkout —
  see sprint.md's Scope Correction). The real join target
  `directory.pipeline._check_related_partner_references()` reads is
  the sibling checkout at `../stem-ecosystem/src/data/partners.json`
  (`Config.get_site_dir()`'s default) — present on this machine and
  used to hand-verify all six ids (121, 241, 238, 24, 361, 323). This
  repo's own `data/partners.json` (a differently-shaped scrape output,
  not the site's own file) was cross-checked too and agrees on every
  id/name pair.
- **Live verification (2026-09-02)**: Fleet
  (fleetscience.org/volunteer — 18+, VolunteerMatters,
  fleetscience.volunteermatters.org, six-month minimum commitment) and
  Birch (aquarium.ucsd.edu/about/volunteer — 16+, Volgistics, six-month
  minimum + weekly 4-hour shift) match issue 14's research exactly.
  SDZWA (sandiegozoowildlifealliance.org/volunteer — 18+, Volgistics,
  volgistics.com/vicnet/14407) also matches on age/platform, but the
  page's own text ("Recruitment is Currently Closed. Please check back
  late 2025.") is stale/overdue as of this verification — recorded
  verbatim in `how_to_book`, not silently dropped or updated to a
  guessed status. The Nat (sdnhm.org/join-and-give/volunteer/) states
  no general numeric age minimum — only that high-school students can
  volunteer via its summer camp program — so `age_minimum` is `None`
  by design, not because research was skipped. ILACSD is "I Love A
  Clean San Diego" (cleansd.org, partner id 361) — its own volunteer
  page (confirmed via a Wayback Machine snapshot after the live site
  returned HTTP 403 to both `curl` and `WebFetch`) states "Volunteers
  of all ages are invited to participate," so `age_minimum` is `None`.
  San Diego River Park Foundation (sandiegoriver.org/get-involved/
  volunteer/) uses Galaxy Digital (sandiegoriver.galaxydigital.com) per
  issue 14's research, with no published numeric age minimum found —
  `age_minimum` is `None`.
- No fetched page carried anything shaped like an instruction to an
  automated agent/fetcher (no prompt-injection content observed).

## Testing

- **Existing tests to run**: `uv run pytest tests/directory/` (roster
  parsing/validation tests from ticket 001 must still pass against the
  now-larger real dataset).
- **New tests to write**: extend `tests/directory/
  test_sources_offering_static_roster.py`'s dataset-validity coverage
  (or a new `tests/directory/test_dataset_validity.py` case, mirroring
  `TestRelatedPartnerIdJoinIntegrity`) to spot-check the six volunteer
  rows' `age_minimum` values and `related_partner_id` joins.
- **Verification command**: `uv run pytest`
