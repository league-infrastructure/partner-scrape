---
id: '001'
title: Fetch and verify team websites
status: open
use-cases: [SUC-001]
depends-on: ['006']
github-issue: ''
issue: 21-scrape-team-sites-for-sponsors.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Fetch and verify team websites

## Description

Issue 21 measured that `website_status` exists on `model.Team` but has
never been written by any code — all 278 teams carry an empty string —
even though 53 teams (all FRC, via TBA) already carry a known `website`
URL nobody has ever fetched. This ticket adds the first stage that
actually looks at a team's page: `partner_scrape/teams/scrape.py`'s
`verify_team_websites(teams, fetcher)`, wired into
`teams.pipeline.run_teams()` immediately after `geocode_teams()` and
before the sponsor-extraction stage tickets 003-005 add.

For each `Team` with a non-empty `website`: check `fetch.is_allowed(url,
fetcher, user_agent)` first (matching `discovery/hub_scan.py::scan_hub()`'s
existing per-page robots-check-then-fetch pattern — do **not** rely on
`PoliteFetcher.get()`'s own internal robots check, which raises
`RobotsDisallowed` rather than letting the loop continue cleanly). If
allowed, fetch via the same `fetcher` parameter `run_teams()` already
threads through to every source (a real `PoliteFetcher` in production —
robots/throttle/cache all apply with zero new plumbing). A 2xx response
sets `Team.website_status = "confirmed"`; anything else (non-2xx,
transport-error status `0`, or a robots disallow) sets/leaves it
`"unverified"` and logs a warning naming the team and the reason. A
`Team` with no `website` gets `"none"`.

**Fetched HTML must never be stored on a `Team` field.**
`teams/export.py`'s `TEAMS_SCHEMA_FIELDS` is derived from
`dataclasses.fields(Team)`, so anything added to the dataclass
auto-publishes to the public `teams.json` — a raw HTML body reaching
that mechanism would leak arbitrary third-party page content (including,
potentially, a coach's personal contact info) into a public data
contract. `verify_team_websites()` must instead **return** a
`dict[team_id, str]` of fetched bodies for `confirmed` teams only, which
`run_teams()` holds as a local variable and will hand to
`teams.sponsor_extract.extract_sponsors()` (ticket 005) — this ticket
does not need to build that consumer, only produce the dict in the right
shape and pass it forward as an unused (or `_ = fetch_results`)
intermediate value if ticket 005 hasn't landed yet in your working
branch.

See `sprint.md`'s SUC-001, Architecture Overview table, and Design
Rationale ("fetched HTML is threaded through `run_teams()` as a local,
non-model dict" and "the website-fetch stage reuses the single `fetcher`
parameter"), and `design/teams-DESIGN.diff.md`'s matching Constraints/
Interfaces entries, for the full approved design.

## Acceptance Criteria

- [ ] `partner_scrape/teams/scrape.py` exists with
      `verify_team_websites(teams: list[Team], fetcher: Fetcher) ->
      dict[str, str]`, mutating `Team.website_status` in place and
      returning fetched bodies keyed by `team_id` for `confirmed` teams
      only.
- [ ] `teams.pipeline.run_teams()` calls it after `geocode_teams()` and
      before `export_teams()`.
- [ ] A 2xx response sets `website_status = "confirmed"`.
- [ ] A non-2xx response, a transport-error status (`0`), or a robots
      disallow sets/leaves `website_status = "unverified"` and logs a
      warning identifying the team and the reason — and never raises out
      of `verify_team_websites()` or affects any other team.
- [ ] A `Team` with an empty `website` gets `website_status = "none"`.
- [ ] `fetch.is_allowed()` is checked before any `fetcher.get()` call for
      a given team's URL (never rely solely on `PoliteFetcher`'s internal
      `RobotsDisallowed` raise).
- [ ] No HTML body is ever assigned to any `Team` field, verified by a
      regression test (see Testing).
- [ ] `opportunities.json`/`scrape-meta.json` remain untouched by a
      `teams` run (existing invariant, unaffected by this ticket —
      re-run the existing byte-identical regression test to confirm).

## Testing

- **Existing tests to run**: `uv run pytest tests/teams/` — must stay
  green with no modification to any existing test file.
- **New tests to write** (`tests/teams/test_scrape.py`):
  - A `FixtureFetcher` double (matching every existing `tests/teams/`
    test double's shape) returning a 2xx for one team's URL sets
    `confirmed` and includes that team's body in the returned dict.
  - A 404/500 and a transport-error (`status=0`) response each set
    `unverified` and log a warning; neither team's body appears in the
    returned dict.
  - An empty `website` sets `none` and is never fetched at all (assert
    the fixture fetcher records no call for that team).
  - A robots.txt disallow (via a `FixtureFetcher`/robots-txt double that
    disallows one specific URL) sets that one team to `unverified`,
    never raises, and does not affect any other team's status in the
    same call.
  - A regression test asserting `dataclasses.fields(Team)` carries no
    field whose value could hold a raw HTML body after a
    `verify_team_websites()` call — i.e., every field's value for a
    fetched team is a short scalar/string/number, not multi-KB page
    content. (A cheap proxy: assert no field value's length exceeds a
    small bound, e.g. 2000 chars, across every field on every `Team`
    after the call.)
- **Live validation** (required before this ticket is considered done,
  per `sprint.md`'s Test Strategy — the full sponsor-related live
  validation is ticket 005's job, but this ticket's own piece should be
  confirmed independently): run `partner-scrape teams --dry-run -v`
  against the real, live registry and confirm the log reports a per-team
  `website_status` outcome for all 53 known FRC URLs, with a sensible
  2xx rate (not 0%, which would indicate a bug in the fetch/robots-check
  wiring rather than genuinely-dead sites).
- **Verification command**: `uv run pytest`, followed by the live
  `--dry-run -v` check above.
