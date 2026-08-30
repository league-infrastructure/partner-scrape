---
id: '006'
title: Ingest discovered team websites and repair bad URLs
status: done
use-cases:
- SUC-005
depends-on: []
github-issue: ''
issue: 21-scrape-team-sites-for-sponsors.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Ingest discovered team websites and repair bad URLs

## Description

Sprint 013 was planned assuming only the 53 team websites already present
in the export (all FRC, from TBA's structured field). Since planning, a
web-search discovery pass (three parallel search agents over the 225
teams whose upstream source carried no website; every candidate required
two independent on-page signals plus a successful fetch) found **31 new
websites and 21 social-only teams**, and the team-lead independently
re-fetched and confirmed all 31 (HTTP 200) on 2026-08-29. That result is
committed as this sprint's research artifact:
`clasi/sprints/013-team-website-surfacing-and-sponsor-extraction/research/discovered-websites.json`
— read its `meta` block for the full method, coverage (223 of 225
teams; `ftc-23676`/`ftc-32210` not reached), and caveats before writing
code.

Separately, measuring the *existing* 53 TBA-sourced websites against the
live `site/src/data/teams.json` found two data-quality defects already
shipping:

- **4 teams carry `http://www.firstinspires.org/` as `website`**
  (`frc-3486`, `frc-4139`, `frc-4919`, `frc-5884`) — TBA's own program
  homepage, copied into the per-team field by mistake, not that team's
  site. Never that team's real page; must not be published as one.
- **7 teams carry a malformed triple-slash URL** (`http:///host...`
  instead of `http://host...`) — `frc-2029`, `frc-2658`, `frc-3341`,
  `frc-3965`, `frc-5025`, `frc-5477`, `frc-6695`. Repairing the missing
  slash recovers 4 live sites (`www.team2658.org`, `westviewrobotics.com`,
  `team5025.com`, `www.nubotx.com`); the other 3 domains
  (`www.neotechrobotics.org`, `TEAM3965.org`, `www.alphaknights.net`) are
  dead. This ticket repairs the URL string generically for all 7 — it
  does not need to know in advance which of the 7 are alive; ticket
  013-001's live fetch (which runs after this ticket, see Sequencing
  below) is what actually separates the 4 recoverable sites from the 3
  dead ones, exactly as it already does for every other declared
  website.

**This ticket is the ingestion/repair stage that must run before ticket
013-001** (`Fetch and verify team websites`) so that ticket fetches the
full, corrected set — 53 cleaned TBA sites plus up to 31 newly
discovered ones — rather than the smaller, partly-broken set the
original plan assumed.

### What this ticket builds

1. **A committed data file**, `partner_scrape/teams/data/discovered-websites.toml`,
   in the same spirit as `teams/data/school-overrides.toml`: curated,
   human-verified input, read offline at runtime, **never** a live
   search invoked from the pipeline. Transcribed directly from the
   research file's `websites` (31 entries) and `social_only` (21
   entries) lists — every `website`/`social` value must match the
   research file verbatim; this ticket does not re-derive or re-verify
   them. Keyed by `Team.team_id` (already a stable, unique identifier —
   no `normalize_school_name`-style header transform needed, unlike
   `school-overrides.toml`). Shape:

   ```toml
   # Websites and social links discovered by agent-assisted web search
   # (2026-08-29) for teams whose upstream source (FTCScout/TBA) reported
   # none. Derived verbatim from the sprint 013 research artifact:
   # clasi/sprints/013-team-website-surfacing-and-sponsor-extraction/
   # research/discovered-websites.json -- see that file's `meta` block
   # for method/coverage/caveats. Curated input, read offline at
   # runtime -- never a live search from the pipeline.
   #
   # `website` is present only for the 31 discovered-website entries
   # (absent for the 21 social-only teams). `social` is always present
   # (may be empty). This file carries NO confidence/verification
   # field and none is consulted at runtime: teams.scrape.
   # verify_team_websites() (ticket 013-001) is the sole, uniform
   # source of truth for confirmed/unverified, for every team
   # regardless of how confidently its website was discovered -- see
   # website_overrides.py's own module docstring.

   ["ftc-1622"]
   website = "https://teamspyder.org"
   social = ["https://www.instagram.com/spyder1622", "https://www.youtube.com/@spyder1622"]

   ["frc-6659"]
   social = ["https://www.instagram.com/ehs.robotics"]
   ```

2. **`partner_scrape/teams/website_overrides.py`** (new module):
   `apply_website_overrides(teams: list[Team], data_dir: str | Path |
   None = None) -> list[Team]`. Mutates and returns `teams` (matching
   `merge_teams()`/`geocode_teams()`'s shape — operate on the full list
   once, in place). Four responsibilities, in this order:
   a. **Generic cleanup**, applied to every team's *existing* `website`
      regardless of source or whether it appears in the overlay file:
      clear it to `""` if its host is `firstinspires.org` or
      `www.firstinspires.org` (`urllib.parse.urlsplit`, not a substring
      match — must not misfire on a real team domain that merely
      contains "firstinspires" as a substring); repair
      `^(https?):///` to `\1://` (the triple-slash defect) via a plain
      `re.sub`.
   b. **Overlay application**: for a team whose `website` is still empty
      after (a), if the overlay data has a `website` for that
      `team_id`, set it.
   c. **Social ingestion**: for any team_id present in the overlay data
      (website or social-only entry alike), set `Team.social` from its
      `social` list. Teams absent from the overlay keep the dataclass
      default (`[]`).
   d. **Never sets or touches `Team.website_status`**, for any team,
      regardless of the overlay entry's original research confidence
      (`strong` or `weak` — that field is not even carried into the
      runtime TOML; see (1) above). `website_status` stays exactly
      `verify_team_websites()`'s (ticket 013-001's) responsibility,
      uniformly. This is the mechanism, not a special case, by which a
      `weak`-confidence discovered entry lands as `unverified` rather
      than being pre-confirmed: it is never marked anything by this
      ticket, so it is exactly as unverified as every other declared
      website until ticket 013-001's live fetch actually classifies it.
   The data-file loader mirrors — never imports — `teams/geo.py`'s
   `_load_overrides`/`_require_file` shape (`tomllib`, raises a local
   `_DataFileError`-equivalent loudly at load time on a missing or
   malformed file — a build-time defect, not a per-record failure to
   isolate, same rationale as `geo.py`'s `SchoolIndex`).
   **Uniqueness guard**: while loading `websites` entries, build a
   `(host, path) -> team_id` map (via `urllib.parse.urlsplit`, comparing
   `slugify(f"{netloc}{path}")` from `partner_scrape.model.slugify` —
   reused, not reimplemented) and raise if two different `team_id`s
   claim the identical `(host, path)` pair. **Must compare host+path,
   never host alone** — the research file's own caveats note
   `carlsbaded.org` and `sites.google.com` each legitimately host more
   than one team at distinct paths; a host-only check would wrongly
   flag those as collisions.
3. **`partner_scrape/teams/model.py`**: new field `social: list[str] =
   field(default_factory=list)`, placed with the existing `website`/
   `website_status`/`organization_website` group, documented inline the
   same way. Purely additive — flows into `TEAMS_SCHEMA_FIELDS` via its
   existing `dataclasses.fields()` derivation with no `export.py`
   change, same pattern as `org_key`/`sibling_team_ids`/`latitude`/
   `longitude` in sprint 011 and `sponsor_provenance` elsewhere in this
   sprint.
4. **`partner_scrape/teams/pipeline.py`**: `run_teams()` calls
   `apply_website_overrides(teams, data_dir=website_data_dir)`
   immediately after `geocode_teams()` and before `export_teams()`, and
   gains a new `website_data_dir: str | Path | None = None` parameter
   (mirroring `geo_data_dir`'s existing convention exactly — defaults to
   the real committed `teams/data/` directory, tests pass an explicit
   fixture directory). Add a docstring note, matching this module's
   existing "Ticket NNN adds..." history convention, flagging that
   ticket 013-001's `verify_team_websites()` call must be sequenced
   *after* this stage so it fetches the corrected, enlarged website set.

### Sequencing (read before touching ticket 013-001)

This ticket must execute, and be merged, **before** ticket 013-001. Per
this sprint's constraint against modifying the content of the five
already-planned tickets, ticket 013-001's own file is not edited by this
ticket-writing pass — instead, **ticket 013-001's `depends-on`
frontmatter field is changed from `[]` to `['006']`** (a single-field
frontmatter edit, not a content change) so the sprint's normal
dependency-ordered execution actually enforces the sequencing this
ticket's own correctness requires — see this ticket's own Acceptance
Criteria and `sprint.md`'s `## Tickets` table for the resulting order.

### Constraints (carried from sprint.md and this issue)

- `partner_scrape/teams/` keeps its zero-import invariant into
  `enrich/`, `adapters/`, or `pipeline.run()`. This ticket's one new
  cross-boundary edge — `partner_scrape.model.slugify` — is not one of
  those four forbidden targets; note it explicitly in the module
  docstring as the first edge from `teams/` to the top-level
  `partner_scrape.model` module (a pure, dependency-free string
  utility, the same shape of reuse `teams/merge.py` already established
  for `normalize.partners.normalize_org_name`).
- No second normalizer or slugifier: URL/host comparisons reuse
  `partner_scrape.model.slugify()`; if any organization-name comparison
  is ever needed here, reuse `normalize.partners.normalize_org_name` —
  do not write new equivalents of either.
- Uniqueness is checked on host + path, never host alone (see above).
- The export privacy test (no email-address pattern anywhere in
  `teams.json`) must still pass with the new `social` field and the
  enlarged `website` set in the export.

## Acceptance Criteria

- [x] `partner_scrape/teams/data/discovered-websites.toml` exists,
      transcribed verbatim from `research/discovered-websites.json`'s
      `websites` and `social_only` lists (team_id, `website` where
      present, `social` list) — no fabricated or hand-invented entries.
- [x] `partner_scrape/teams/website_overrides.py` exists with
      `apply_website_overrides(teams: list[Team], data_dir: str | Path
      | None = None) -> list[Team]`, doing exactly the four things
      listed in Description, in order, and idempotent (calling it twice
      produces the same result).
- [x] A team whose `website` is `http://www.firstinspires.org/` (or the
      `www.`-less form) has it cleared to `""`.
- [x] A team whose `website` is `http:///host...` (triple slash) has it
      repaired to `http://host...`, generically, for any host —
      verified against all 7 real malformed values listed in
      Description (fixture-derived from the live `teams.json`, not
      hand-invented).
- [x] A team with an existing non-empty (post-cleanup) `website` is
      never overwritten by the overlay, even if the overlay also has an
      entry for that `team_id`.
- [x] A team with no existing website and a `website` entry in the
      overlay gets `Team.website` set from the overlay.
- [x] A team present only in the overlay's social-only list gets
      `Team.social` populated with no `Team.website` change.
- [x] `Team.website_status` is left exactly at its dataclass default
      (`""`) for every team this stage touches, including both
      `strong`- and (the 3) `weak`-confidence overlay entries alike —
      this stage never sets it, proven by a direct test, not just by
      the absence of code that would.
- [x] The `(host, path)` uniqueness guard raises on two different
      `team_id`s claiming an identical `(host, path)` pair, and does
      **not** raise for two different teams sharing only a host at
      distinct paths (`carlsbaded.org`, `sites.google.com` — real cases
      from the research file).
- [x] `Team.social: list[str]` (default `[]`) is added to
      `partner_scrape/teams/model.py` and appears in
      `TEAMS_SCHEMA_FIELDS` with no `export.py` change required.
- [x] `teams.pipeline.run_teams()` calls `apply_website_overrides()`
      after `geocode_teams()` and before `export_teams()`, and accepts
      a new `website_data_dir` parameter.
- [x] Ticket 013-001's frontmatter `depends-on` is changed from `[]` to
      `['006']` (the only edit made to that ticket file). (Already in
      place before this ticket's implementation pass — verified via
      `read_artifact_frontmatter`, not re-edited.)
- [x] `sprint.md`'s `## Tickets` table lists this ticket ahead of
      013-001 in execution order. (Already in place before this
      ticket's implementation pass.)
- [x] `partner_scrape/teams/` still has zero imports from `enrich/`,
      `adapters/`, or `pipeline.run()` (existing regression test, if
      any covers this — see Testing). `website_overrides.py` imports
      only `re`, `tomllib`, `dataclasses`, `pathlib`, `urllib.parse`,
      `partner_scrape.model`, and `partner_scrape.teams.model`.

## Testing

- **Existing tests to run**: `uv run pytest tests/teams/` — must stay
  green with no modification to any existing test file. Also re-run the
  existing export privacy test (no email-address pattern anywhere in
  `teams.json`) against output that now includes `Team.social` and the
  enlarged `website` set.
- **New tests to write** (`tests/teams/test_website_overrides.py`),
  fixtures derived from real data, never hand-authored:
  - A small fixture TOML (`tests/fixtures/teams/discovered_websites_sample.toml`)
    containing a representative subset copied verbatim from
    `research/discovered-websites.json` — at least one `strong`-confidence
    website entry, all 3 `weak`-confidence entries (`ftc-6226`,
    `ftc-14968`, `ftc-18755`), one social-only entry, and the
    `carlsbaded.org`/`sites.google.com` host-sharing pair.
  - `firstinspires.org` cleanup: a fixture `Team` with `website =
    "http://www.firstinspires.org/"` (the real value shared by
    `frc-3486`/`frc-4139`/`frc-4919`/`frc-5884`) is cleared.
  - Triple-slash repair: fixture `Team`s built from the 7 real malformed
    values in Description are each repaired correctly.
  - Overlay application only when `website` is empty: a fixture `Team`
    with a pre-existing `website` and a matching overlay entry keeps its
    original value.
  - Social-only ingestion sets `Team.social`, leaves `Team.website`
    unchanged (empty).
  - `website_status` regression: after `apply_website_overrides()`
    runs, every affected `Team.website_status` is still `""`, for both
    a `strong`- and a `weak`-confidence fixture entry.
  - Uniqueness guard: a fixture overlay with two different `team_id`s
    both pointing at the exact same `(host, path)` raises; a fixture
    with two different `team_id`s sharing a host but distinct paths
    (mirroring `carlsbaded.org`/`sites.google.com`) does not raise and
    both teams keep their own website.
  - A team_id absent from the overlay and with no existing website
    stays `website=""`, `social=[]`.
  - Missing/malformed data file raises loudly at load time (matching
    `teams/geo.py`'s `SchoolIndex` convention), never silently produces
    an empty overlay.
- **Live validation**: run `partner-scrape teams --dry-run -v` against
  the real, live registry and confirm the log/return payload shows the
  enlarged website count (up to 84: 53 cleaned existing + up to 31
  discovered) and the new social-only count, before ticket 013-001 runs
  its own live fetch against this enlarged set.
- **Verification command**: `uv run pytest`, followed by the live
  `--dry-run -v` check above.
