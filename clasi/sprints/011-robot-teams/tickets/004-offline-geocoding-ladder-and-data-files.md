---
id: '004'
title: Offline geocoding ladder and data files
status: open
use-cases:
- SUC-003
depends-on:
- '003'
github-issue: ''
issue: robot-teams-scrape-locate-and-publish-san-diego-first-teams.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Offline geocoding ladder and data files

## Description

Build the seven-rung, fully offline location-resolution ladder — this
is the issue's increment 3, and the increment that actually delivers
the sprint's stated goal of *knowing where the teams are*, not just
who they are. Commits the CDE public-school and NCES private-school
directory data files, the ZIP/city centroid tables, and
`school-overrides.toml`. Adds `dev/refresh_school_directories.py` for
the yearly manual refresh. Extends `teams.pipeline.run_teams()` to
geocode every merged team before export. Implements SUC-003.

**Never an LLM guess, at any point in this ticket.** A wrong pin is
worse than no pin. A team that exhausts all seven rungs gets
`location_precision: none`.

## Acceptance Criteria

- [ ] `partner_scrape/teams/data/sd-schools-public.tsv` — the CDE
      public-school directory, filtered to active San Diego County
      rows with coordinates (~924 rows expected per the issue's live
      measurement; reject `Virtual` rows, prefer `StatusType ==
      "Active"`).
- [ ] `partner_scrape/teams/data/sd-schools-private.tsv` — NCES EDGE
      private-school geocodes, San Diego County, **unioning the
      2021-22 and 2023-24 survey vintages** (a school present in one
      vintage but not the other, e.g. Pacific Ridge School, must not be
      lost).
- [ ] `partner_scrape/teams/data/zip-centroids.toml` and
      `partner_scrape/teams/data/city-centroids.toml` — static centroid
      tables for the ZIP and city rungs.
- [ ] `partner_scrape/teams/data/school-overrides.toml` — hand
      corrections, consulted first (highest-precision rung).
- [ ] `partner_scrape/teams/geo.py` implements the ladder in this exact
      order, each rung stamping `location_precision`: (1) overrides →
      `school`; (2) CDE+NCES exact normalized match, city-filtered when
      ambiguous → `school`; (3) token-set match, Jaccard ≥ 0.60 within
      city → `school`; (4) token-set match, Jaccard ≥ 0.80 county-wide
      → `school`; (5) ZIP centroid from `postal_code` → `zip`; (6) city
      centroid → `city`; (7) no match → `location_precision: none`,
      coordinates left blank.
- [ ] City strings are normalized before matching (`"La Jolla "`,
      `"carlsbad"`, `"san diego"` must not be treated as distinct
      cities).
- [ ] A fuzzy match scoring below 0.85 sets `needs_review: true` rather
      than publishing silently; `matched_name` is recorded on every
      resolved team.
- [ ] Geocoding cache is keyed **per resolved school, not per team**
      (verified: a fixture with multiple teams at the same school hits
      the CDE/NCES matcher once, not once per team); negative matches
      are cached too.
- [ ] An out-of-county team (e.g. a fixture Ensenada or San Clemente
      record) is stamped `in_region = false` and still appears in
      export output — never dropped — with a count in `meta`.
- [ ] `geo.py` performs zero network calls — enforced by a test that
      runs it with no `Fetcher`/network fixture available at all (not
      merely an unused one).
- [ ] `dev/refresh_school_directories.py` exists, is runnable standalone
      (not imported by the pipeline), and documents the yearly manual
      CDE + NCES refresh procedure in its own docstring/header comment.
- [ ] `teams.pipeline.run_teams()` geocodes every team after merge,
      before export.

## Implementation Plan

**Approach**: Build the matcher bottom-up — exact-normalized match
first (cheapest, highest confidence), then the two token-set tiers,
since later tickets and future refreshes will tune thresholds and it's
easier to reason about one tier at a time. Reuse
`normalize.partners.normalize_org_name`-style normalization logic
*conventions* (lowercase, strip punctuation, collapse whitespace) for
city/school-name normalization, but do not import that function itself
— it is scoped to organization names, not places; write a small,
separately-named normalizer local to `geo.py`. Cache resolution results
in-memory per `run_teams()` call, keyed by normalized school name
(hit) or normalized team-organization string (negative-cache key for
unresolvable org-named teams) — per the issue's explicit note that 94
school-named teams collapse to ~58 distinct campuses, so per-team
caching would do ~40% redundant matching work.

**Files to create**:
- `partner_scrape/teams/geo.py`
- `partner_scrape/teams/data/sd-schools-public.tsv`
- `partner_scrape/teams/data/sd-schools-private.tsv`
- `partner_scrape/teams/data/zip-centroids.toml`
- `partner_scrape/teams/data/city-centroids.toml`
- `partner_scrape/teams/data/school-overrides.toml`
- `dev/refresh_school_directories.py`

**Files to modify**:
- `partner_scrape/teams/pipeline.py` — add the geocode step.
- `partner_scrape/teams/DESIGN.md` — extend with `geo.py`'s design
  (already drafted in `design/new-subsystem/teams-DESIGN.md`; verify
  against the actual matcher thresholds/behavior you implement).

## Documentation

Extend `partner_scrape/teams/DESIGN.md` with the ladder's exact rung
order, the caching strategy, and the `needs_review`/`in_region`
semantics — this is the module most worth documenting precisely, since
"why is this team here" needs a string answer (`matched_name`) rather
than a guess.

## Testing

- **Existing tests to run**: `uv run pytest`.
- **New tests to write** (`tests/teams/test_geo.py`), covering — per
  `sprint.md`'s Test Strategy — at minimum:
  - An exact CDE public-school match.
  - An NCES private-school miss (a school in the private-school fixture
    that has no matching public-school row).
  - A `Family/Community` team resolving to city precision.
  - Dirty city strings (`"La Jolla "`, `"carlsbad"`) normalizing
    correctly.
  - An out-of-county team: `in_region = false`, still present in
    output.
  - A sub-0.85 fuzzy match: `needs_review: true`.
  - Per-school (not per-team) cache hit counting.
  - Zero network calls, asserted structurally.
- **Verification command**: `uv run pytest tests/teams/ && uv run
  pytest`
