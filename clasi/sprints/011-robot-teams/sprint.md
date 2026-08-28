---
id: '011'
title: Robot teams
status: roadmap
branch: sprint/011-robot-teams
use-cases: []
issues:
- robot-teams-scrape-locate-and-publish-san-diego-first-teams.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 011: Robot teams

## Goals

Build a refreshable pipeline that scrapes, locates, and publishes San
Diego County's ~259 FIRST robotics teams (FTC, FRC, FLL) — a new
category the site currently has nothing for — as a self-contained new
module and site section (issue `robot-teams-scrape-locate-and-publish-
san-diego-first-teams.md`).

A new `partner_scrape/teams/` module (its own model, sources, offline
geocoding, merge, and exporter — deliberately not routed through the
existing `Opportunity` model, since a team is a standing entity with no
date and would be filtered out by the export's current-and-upcoming
logic) pulls live rosters from FTCScout (152 FTC teams, free/no auth)
and The Blue Alliance (59 FRC teams, keyed, already provisioned), locates
each team via a fully offline resolution ladder (CDE + NCES school
directories, then ZIP centroid, then city centroid — never an LLM guess,
per the issue's explicit "never guess" rule), and publishes browsable
`/teams` pages modeled on the existing Opportunities pages.

The issue lays out five increments, to be sequenced as this sprint's
work (exact ticket boundaries are a detail-planning decision, not fixed
here):

1. **Model + FTCScout + export + subcommand** — 152 FTC teams,
   city-level, no credential needed; proves the spine end to end.
2. **TBA source + merge** — adds 59 FRC teams, 43 websites, 49 ZIPs;
   cross-league identity keyed on normalized organization name (not team
   number, since teams number 1622 collides across programs).
3. **Geocoding** — the offline CDE+NCES+ZIP+city resolution ladder, its
   committed data files, and the yearly manual refresh script.
4. **Site pages** — `/teams` index with filters and map, detail pages,
   nav entries in both `Header.astro` and `Footer.astro`.
5. **FLL static roster** — 48 teams from a hand-maintained export,
   marked static with provenance and an end-of-life date (FIRST LEGO
   League's last season is 2026-27). Last, because it's the lowest-value
   piece and the only one with a hard expiry.

This sprint is large and self-contained: it introduces a new
`partner_scrape/teams/` subsystem, a new `Team` data model deliberately
disjoint from `Opportunity`, a new offline geocoding subsystem, and a
new `/teams` site section — independent of sprints 009/010's export and
discovery work, which is why it sits last where it cannot block them.

Note for detail planning: `docs/design/design.md` (plus per-subsystem
`DESIGN.md`) is being bootstrapped concurrently and `design_docs` is now
`enabled`. `partner_scrape/teams/` is an entirely new subsystem — expect
it to receive its own `DESIGN.md` at detail-planning/architecture time,
not merely a `design/` overlay on an existing doc.

## Scope

### In Scope

- New `partner_scrape/teams/` module: `model.py` (`Team` dataclass),
  `sources/{base,ftcscout,tba,static_roster}.py`, `geo.py` (offline
  resolver), `merge.py` (cross-source/cross-league identity),
  `export.py` (writes `teams.json`), `pipeline.py`, per-league
  `registry/*.toml`, and committed geocoding data files (CDE public +
  NCES private school directories, ZIP/city centroid tables,
  `school-overrides.toml`).
- `config.py` additions for `TBA_KEY` / TBA URL, mirroring the existing
  `leaguesync` credential pattern.
- `export/mirror.py`'s `MIRRORED_DATA_FILES` gaining `teams.json`, and a
  new `teams` CLI subcommand (not a flag on `run`, since rosters refresh
  annually and a TBA failure must never poison the opportunities
  export).
- New site components/pages modeled on the existing Opportunities
  section: `TeamCard.astro`, `TeamFilters.astro`,
  `pages/teams/index.astro`, `pages/teams/[slug].astro`, and nav entries
  in `Header.astro` / `Footer.astro`.
- The offline geocoding ladder and its yearly manual refresh script
  (`dev/refresh_school_directories.py`).
- The FLL static roster overlay, imported from `data/robot-teams.json`
  with contact fields stripped and only used as an overlay (never an
  override) on live-sourced fields.
- Deploy follow-up: pushing `TBA_KEY` to GitHub Actions secrets so the
  scheduled run doesn't fail on FRC (flagged in the issue as currently
  missing).

### Out of Scope

- Joining teams to the existing partner directory — the issue found only
  one of 105 distinct team organizations is already a partner, and
  explicitly skips the partner-join; `teams.json` stands alone. The
  inverse finding (104 San Diego schools running robotics teams that
  aren't partners) is a ready-made recruitment list, noted as out of
  scope here.
- An LLM-driven website-discovery search for team websites — the issue
  frames this as a possible follow-on behind an explicit flag, not part
  of the five core increments; deterministic tiers (TBA's `website`
  field, the hand-curated seed with liveness checks, CDE's matched
  `WebSite` as a separate `organization_website` field) ship first.
- Any team `email` field — deliberately omitted per the issue (a parent's
  personal email on a public page is a real risk; omitting the field
  makes leaking one structurally impossible).
- Sprints 009/010's export-publishing and discovery work — independent
  data domains; this sprint does not touch `opportunities.json`,
  `partners.json`, or `scrape-meta.json` (two hard invariants the issue
  calls out explicitly: teams export never touches either file).

## Test Strategy

(Describe the overall testing approach for this sprint: what types of tests,
what areas need coverage, any integration or system-level testing needed.)

## Architecture

(Architecture for this sprint's change, sized to the change — a
one-paragraph note for a trivial sprint, a fuller write-up with
component/data-model detail for a substantial one. May read "N/A —
trivial" when the change has no architectural impact.)

### Architecture Overview

(High-level structure and component relationships, if applicable.)

### Design Rationale

(Significant decisions with alternatives considered and reasoning, if
applicable.)

### Migration Concerns

(Data migration, backward compatibility, deployment sequencing — or
"None" if not applicable.)

## Use Cases

(Use cases sized to the change — may read "N/A — trivial" for small
sprints that don't warrant new or updated use cases.)

### SUC-001: (Title)
Parent: UC-XXX

- **Actor**: (Who)
- **Preconditions**: (What must be true before)
- **Main Flow**:
  1. (Step)
- **Postconditions**: (What is true after)
- **Acceptance Criteria**:
  - [ ] (Criterion)

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

Tickets execute serially in the order listed.
