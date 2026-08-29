---
id: '005'
title: Sponsor extraction orchestration and normalization
status: open
use-cases: [SUC-004]
depends-on: ['001', '004']
github-issue: ''
issue: 21-scrape-team-sites-for-sponsors.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sponsor extraction orchestration and normalization

## Description

This ticket wires everything tickets 001, 003, and 004 built into one
working pipeline stage, adds the data-model change and structured-source
provenance backfill, and — because this is the sprint's genuinely hard,
uncertain part — carries the required pre-close human validation.

Add `partner_scrape/teams/model.py`'s `sponsor_provenance: dict[str,
str]` field (`display sponsor name -> "structured" | "scraped"`),
purely additive alongside the existing `sponsors: list[str]` (do **not**
restructure `sponsors` into a list of records — every existing
`TeamCard`/detail-page/test consumer already assumes a flat `list[str]`;
see `sprint.md`'s Design Rationale for why a parallel dict was chosen
over a restructure).

Add `partner_scrape/teams/sponsor_extract.py`'s
`extract_sponsors(teams: list[Team], fetch_results: dict[str, str],
llm_client: SponsorLLMClient, cache: SponsorCache) -> None`, run once per
team with an entry in `fetch_results` (ticket 001's output):
1. `candidates = gather_sponsor_candidates(body, team.website)` (ticket
   003). Skip to the next team if empty — no cache lookup, no LLM call.
2. Cache lookup by `(team.team_id, content_hash(candidates))`. On a hit,
   reuse the cached result.
3. On a miss, call `llm_client.classify_sponsors(candidates, context)`
   where `context` carries at least `team.organization` and the page's
   hostname (ticket 004's client uses these to exclude them explicitly).
   Store the result in the cache.
4. **Validate**: any name in the result **not present verbatim** in
   `candidates` is dropped and logged — never trusted. This is the
   structural anti-hallucination guarantee (Design Rationale); it must
   be enforced here in code even though ticket 004's client is already
   prompted not to invent names.
5. Apply a small denylist as defense-in-depth (common CMS/hosting vendor
   names, the team's own `organization`, the page's own hostname) —
   catches anything a permissive classification might still let through.
6. Deduplicate the surviving names against `team.sponsors`' existing
   (structured) entries using `normalize.partners.normalize_org_name` as
   the match key (reused, not reimplemented — this project has exactly
   one sponsor/organization-name normalizer). A normalized key already
   present keeps its structured display name and `"structured"`
   provenance; a new key is appended to `sponsors` with `"scraped"`
   provenance.
7. Wrap steps 2-6 in a per-team `try/except`: any failure (network error,
   malformed LLM response, missing `ANTHROPIC_API_KEY`) is logged and
   leaves that team's `sponsors`/`sponsor_provenance` exactly as the
   structured sources already set them — fail-open, matching `enrich/`'s
   project-wide "fail open, always" convention. It must never abort the
   run for any other team.

Update `partner_scrape/teams/sources/ftcscout.py` to set
`sponsor_provenance = {name: "structured" for name in sponsors}`
alongside its existing `sponsors` assignment, so every pre-existing
structured sponsor carries correct provenance from the start, not just
newly-scraped ones.

Wire `extract_sponsors()` into `teams.pipeline.run_teams()` after
`verify_team_websites()` (ticket 001) and before `export_teams()`. Add
`llm_client`/`sponsor_cache` parameters to `run_teams()` (default to a
real `AnthropicSponsorLLMClient()`/`SponsorCache()` when omitted,
matching `fetcher`'s existing default-to-production convention — tests
inject fixture doubles for both). Add a `--no-sponsors` flag to the
`teams` CLI subcommand (`cli.py`) that skips this stage only —
`verify_team_websites()` always runs, since it is the cheap, certain
half.

See `sprint.md`'s SUC-004, full Architecture section (Component/
Dependency diagrams, all six Design Rationale entries), and
`design/teams-DESIGN.diff.md` for the complete approved design this
ticket implements.

## Acceptance Criteria

- [ ] `Team.sponsor_provenance: dict[str, str]` field added; no
      `export.py` change required for it to publish (confirm
      `TEAMS_SCHEMA_FIELDS` picks it up automatically).
- [ ] `sources/ftcscout.py` sets `sponsor_provenance` for every
      structured sponsor it produces.
- [ ] `partner_scrape/teams/sponsor_extract.py`'s `extract_sponsors()`
      implements the 7-step flow above, mutating `teams` in place.
- [ ] Any name returned by the LLM client that is not verbatim in the
      original candidate list is dropped and logged, never published —
      tested directly with a fixture client that returns an out-of-list
      name.
- [ ] "Qualcomm" (structured) and a scraped "Qualcomm Inc." for the same
      team collapse to one entry via `normalize_org_name`, keeping the
      structured display name and `"structured"` provenance.
- [ ] A cache hit makes zero LLM calls (verified via
      `FixtureSponsorLLMClient.calls`).
- [ ] An LLM call failure (simulated: exception-raising fixture client,
      or a missing `ANTHROPIC_API_KEY`) is caught per-team, logged, and
      leaves that team's `sponsors`/`sponsor_provenance` unchanged from
      whatever structured sources set — verified it never aborts
      `run_teams()` or affects any other team.
- [ ] `teams.pipeline.run_teams()` sequences
      `verify_team_websites() -> extract_sponsors() -> export_teams()`
      correctly, with `llm_client`/`sponsor_cache` as new optional
      parameters.
- [ ] `cli.py`'s `teams` subcommand gains a `--no-sponsors` flag that
      skips `extract_sponsors()` only; `verify_team_websites()` still
      runs.
- [ ] The existing export privacy regression test (no email-address
      pattern anywhere in `teams.json`) passes with sponsor-extraction
      fixtures included in its corpus.

## Testing

- **Existing tests to run**: `uv run pytest tests/teams/` (full suite)
  and the existing `tests/teams/test_export.py` no-email-pattern
  regression test, extended to cover output that now includes
  scraped-page-derived sponsor names.
- **New tests to write** (`tests/teams/test_sponsor_extract.py`):
  - End-to-end fixture test: a candidate list mixing real sponsor names
    with an obvious non-sponsor (the team's own school name, "Wix") —
    only the real sponsors reach `Team.sponsors`.
  - Out-of-list hallucination guard: a `FixtureSponsorLLMClient`
    configured to return a name absent from the candidate list — that
    name is dropped and logged, never published.
  - Structured/scraped dedup: a `Team` with `sponsors=["Qualcomm"]`,
    `sponsor_provenance={"Qualcomm": "structured"}` and a scraped result
    containing "Qualcomm Inc." — result has exactly one "Qualcomm" entry,
    `sponsor_provenance` still `"structured"`.
  - Cache-hit call-counting: identical `(team_id, candidates)` across two
    `extract_sponsors()` calls makes exactly one LLM call, not two.
  - Fail-open: an exception-raising fixture client leaves a team's prior
    `sponsors`/`sponsor_provenance` untouched and does not raise out of
    `extract_sponsors()`; a second, unrelated team in the same call still
    gets processed normally.
  - `tests/teams/test_pipeline.py`: `run_teams()` sequences the two new
    stages correctly with fixture `fetcher`/`llm_client`/`sponsor_cache`;
    `--no-sponsors` (or the equivalent `run_teams(no_sponsors=True)`
    parameter) skips `extract_sponsors()` while `verify_team_websites()`
    still runs.
- **The sprint 011 ticket-011-003 lesson, applied directly (required,
  not optional) — this is this sprint's own stated pre-close gate**: a
  hand-authored fixture that only approximates real page structure is
  exactly the failure mode that historically shipped a defect past a
  fully green suite. Before this ticket (and the sprint) is considered
  done:
  1. Run `partner-scrape teams --dry-run -v` against the real, live
     registry (not fixtures) and record: pages fetched, 2xx rate,
     robots-disallowed count, teams gaining a scraped sponsor, and the
     new distinct-sponsor count.
  2. **A human samples the scraped sponsor output** — at minimum every
     team that gained a sponsor from scraping — and confirms no
     obviously-wrong entry (a CMS vendor, a hosting provider, a school
     district, the site's own domain, the program name itself) shipped.
     Record what was checked and the outcome in the ticket or PR
     description.
  3. Only after both (1) and (2) pass should this ticket, and the
     sprint, be considered ready to close.
- **Verification command**: `uv run pytest`, followed by the live
  `--dry-run -v` run and human sample review described above.
