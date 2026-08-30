---
id: '005'
title: Sponsor extraction orchestration and normalization
status: done
use-cases:
- SUC-004
depends-on:
- '001'
- '004'
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

- [x] `Team.sponsor_provenance: dict[str, str]` field added; no
      `export.py` change required for it to publish (confirm
      `TEAMS_SCHEMA_FIELDS` picks it up automatically).
- [x] `sources/ftcscout.py` sets `sponsor_provenance` for every
      structured sponsor it produces.
- [x] `partner_scrape/teams/sponsor_extract.py`'s `extract_sponsors()`
      implements the 7-step flow above, mutating `teams` in place.
- [x] Any name returned by the LLM client that is not verbatim in the
      original candidate list is dropped and logged, never published —
      tested directly with a fixture client that returns an out-of-list
      name.
- [x] "Qualcomm" (structured) and a scraped "Qualcomm Inc." for the
      same team collapse to one entry via the shared canonicalization
      key, keeping the structured display name and `"structured"`
      provenance. **Resolved on reopening (2026-08-30).** The first
      pass correctly left this unchecked: `normalize_org_name` (reused
      verbatim, per this ticket's own "do not write a second
      normalizer" instruction) lowercases/strips punctuation/drops a
      leading "the "/collapses whitespace, but does **not** strip
      corporate suffixes, so `normalize_org_name("Qualcomm Inc.") ==
      "qualcomm inc"`, not `"qualcomm"`, and this exact pair did not
      collapse. Auditing the real, regenerated `teams.json` afterward
      showed the consequence was worse than this one example
      suggested — 130 "distinct" sponsor strings for ~110 real
      companies, with Qualcomm itself split three ways across
      different teams' own structured records — which is what reopened
      the ticket. **Fix, without modifying `normalize_org_name`** (the
      scope boundary holds: it remains the curated partner-directory
      join's own untouched shared key): a new module,
      `partner_scrape/teams/sponsor_canonical.py`, adds
      `canonical_key()` (normalize_org_name + a corporate-suffix strip)
      as the shared match key `sponsor_extract.py::_merge_sponsors`/
      `_is_denylisted` now use instead of calling `normalize_org_name`
      directly, plus a new corpus-wide `canonicalize_sponsors()` pass
      (`run_teams()`, after `extract_sponsors()`, before
      `export_teams()`) that also closes the *cross-team* spelling gap
      no per-team merge could ever see. Directly tested in
      `tests/teams/test_sponsor_extract.py`'s
      `TestPreviouslyKnownLimitationNowResolved` (replacing the old
      `TestKnownNormalizeOrgNameLimitation`, which asserted the former,
      now-fixed behavior) and comprehensively in the new
      `tests/teams/test_sponsor_canonical.py`. Live-verified: 130 raw
      distinct sponsor strings now canonicalize to 110 real companies;
      see "Live verification record" below for the full re-run and
      critical top-20 review.
- [x] A cache hit makes zero LLM calls (verified via
      `FixtureSponsorLLMClient.calls`).
- [x] An LLM call failure (simulated: exception-raising fixture client,
      or a missing `ANTHROPIC_API_KEY`) is caught per-team, logged, and
      leaves that team's `sponsors`/`sponsor_provenance` unchanged from
      whatever structured sources set — verified it never aborts
      `run_teams()` or affects any other team.
- [x] `teams.pipeline.run_teams()` sequences
      `verify_team_websites() -> extract_sponsors() -> export_teams()`
      correctly, with `llm_client`/`sponsor_cache` as new optional
      parameters.
- [x] `cli.py`'s `teams` subcommand gains a `--no-sponsors` flag that
      skips `extract_sponsors()` only; `verify_team_websites()` still
      runs.
- [x] The existing export privacy regression test (no email-address
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

### Live verification record (2026-08-30)

Ran `partner-scrape teams --dry-run -v` against the real, live 278-team
registry (152 FTC + 78 FRC + 48 FLL, matching `teams/DESIGN.md`'s own
measured baseline).

- **Website verification (ticket 001, re-confirmed unchanged by this
  ticket)**: 52 confirmed, 28 unverified, 198 none — 65% of 80 checked
  URLs returned 2xx.
- **Sponsor extraction**: 32 teams had sponsor-shaped page content
  (candidates non-empty); **11 teams gained a new scraped sponsor**; 0
  per-team failures.
- **Distinct-sponsor count**: 87 distinct structured sponsor strings
  (pre-existing baseline, unchanged) → **130 distinct sponsor strings
  total after scraping** (124 by normalized key) — **48 new distinct
  scraped names**.
- **Anthropic usage**: ~32 classification calls (one per team with
  candidates, on the first, cold-cache run) against `claude-haiku-4-5`
  — negligible cost (well under $0.01 at Haiku's per-token pricing for
  this call volume/size). Re-runs after the code fix below were mostly
  cache hits (same team/candidate-hash pairs), so the fix was verified
  without material additional API cost.

**Human sample review (every team that gained a scraped sponsor, not a
subset) — findings:**

1. **One real defect, found and fixed before close.** `frc-5137` ("Iron
   Kodiaks") scraped a full Instagram-caption fragment as if it were a
   sponsor name ("A huge thank you to @generalatomics for hosting Team
   5137 Iron Kodiaks on Wednesday! ... #ironkodiaks #team5137") —
   `sponsor_candidates.py` has no per-candidate length gate (only a
   candidate-*count* cap), and the classification call selected it
   anyway. Fixed in `sponsor_extract.py`'s own denylist step: added
   `_MAX_SPONSOR_NAME_LENGTH = 80` and an `"@"`/`"#"`
   social-caption-marker check (`_looks_like_social_caption`) — the
   marker check was needed because the same embedded post also
   contributed a second, independently-truncated fragment short enough
   to clear the length cap alone. Re-verified live after the fix:
   `frc-5137` now correctly contributes no scraped sponsor.
2. **Two items surfaced for human awareness, not code defects.**
   `frc-1613` ("StARC") scraped "St. Michael School" alongside ~19
   plausible local-business names — this team's structured
   `organization` field is empty (neither upstream source reports one),
   so the denylist's own-organization check has nothing to compare
   against and cannot rule out this being the team's own affiliation.
   Several other scraped names (three `carlsbaded.org`-hosted teams'
   shared sponsor-page footer) are real companies published as ugly,
   filename-derived strings (e.g. `"1280px-Thermo_Fisher_Scientific_logo"`)
   rather than clean names — correct attribution, poor display
   formatting; no cleanup attempted (out of this ticket's "provenance,
   not curation" scope).
3. **No CMS vendor, hosting provider, or the program's own name
   appeared in any scraped list** — the existing ticket 003/004 guards
   (deterministic denylist, verbatim-candidate check, prompt
   exclusions) held up against the live corpus.

Full detail recorded in `teams/DESIGN.md`'s "(Sprint 013) Live-run
sample review" Open Questions entry. Both (1) and (2) of this section's
required pre-close gate are satisfied: the live run was measured and
recorded above, and the human sample review found one real defect
(fixed) and no other obviously-wrong entry.

### Reopening: sponsor-name canonicalization (2026-08-30)

Reopened over the one unchecked acceptance criterion above: the
consequence of `normalize_org_name` not stripping corporate suffixes
was worse than the "Qualcomm"/"Qualcomm Inc." example suggested, once
measured against the real regenerated `teams.json` (57 teams with
sponsors, 130 "distinct" sponsor strings for what is really ~110
companies — Qualcomm, the single most important data point, split
three ways).

**Root cause of the `"&R"` corruption** (`"Solar Turbines, Inc&R"`,
`"Francis Parker School&R"`, `"Caterpillar&R"`): investigated directly
against `tests/fixtures/teams/ftcscout_search.json` — every one of
these strings appears **byte-for-byte identical in FTCScout's own raw
API response**, and `sources/ftcscout.py::_extract_one` does nothing to
a sponsor string beyond `list(sponsors_raw)`. There is no
`html.unescape` or any other decode step anywhere in this project's own
code between the API response and `Team.sponsors` — the corruption is
baked into the data FTCScout's API hands us, not a bug on this side.
(Best reconstruction of *their* bug: `"&R"` sits exactly where a `"®"`
mark would naturally appear, consistent with their own ingestion
mis-decoding and truncating a `&reg;`/`&REG;` entity — not reproducible
or fixable from here.) A fourth real corruption instance,
`"General Atomics Aeronautical Inc.&Classical Academy High School"`
(also verbatim in the same raw fixture), joins two unrelated sponsor
names with a bare, unspaced `"&"`.

**Fix**: `partner_scrape/teams/sponsor_canonical.py` (new module,
inside `teams/`, layered on top of — never modifying —
`normalize.partners.normalize_org_name`, per this ticket's own scope
boundary). `canonical_key()` (`normalize_org_name` + corporate-suffix
stripping) is now the shared match key `sponsor_extract.py`'s
per-team merge uses instead of calling `normalize_org_name` directly.
`canonicalize_sponsors()` is a new corpus-wide pass — local corruption/
formatting cleanup, hostname/filename reconstruction against a
corpus-wide reference of already-clean names (recovering e.g.
`"nordson.com"` → `"Nordson"`, `"1280px-Thermo_Fisher_Scientific_logo"`
→ `"Thermo Fisher Scientific"`, dropping anything it cannot
deterministically recover, e.g. `"te.com"`, `"haascnc.com"`), and
token-prefix clustering (folding `"Francis Parker"` into `"Francis
Parker School"`) — called once by `run_teams()`, after
`extract_sponsors()`/`--no-sponsors` and before `export_teams()`,
unconditionally. See that module's own docstring for the full defect
analysis and design rationale, including what is deliberately **not**
attempted: fuzzy business-relationship clustering of legally-distinct
entities (`"CAT"` vs. `"Caterpillar"`; `"General Atomics Aeronautical"`
vs. `"General Atomics Sciences Education Foundation"` — no
deterministic string transformation connects either pair).

**Live re-verification** (`partner-scrape teams --site-dir site`
against the real 278-team registry, 2026-08-30): website verification
and sponsor-scraping numbers are unchanged from the first pass (52/80
confirmed, 32 teams with sponsor-shaped content, 11 gained a scraped
sponsor, 0 failures) — this fix only touches display-name
canonicalization, not extraction. **The 130 raw distinct sponsor
strings now canonicalize to 110 distinct real companies.** Top 20 by
team count, read critically (cross-checked every entry's crediting
team(s) against their own `organization` field): Qualcomm (22 — one
entry instead of three), Nordson (6), DoD STEM (5), Solar Turbines (4),
BAE Systems (4), Francis Parker School (4 — crediting teams'
`organization` is "D Robotics Education", a genuinely different org,
not a self-affiliation false positive), Viasat (4), Teradata (3),
Thermo Fisher Scientific (3), Millipore Sigma (3), Gene Haas Foundation
(3), RISE (3), Apple (3), DoDea (3), Leidos (2), Robot Planet Ecuador
(2), SAIC (2), PTC (2), AFCEA (2), Carlsbad Educational Foundation (2).
Nothing in the top 20, or in the full 110, is an image filename, a bare
hostname, or a CMS vendor — confirmed programmatically (no remaining
entry matches a filename/hostname/logo-artifact shape) as well as by
inspection. `site/src/data/teams.json` was regenerated from this run
and is committed with this fix.

Scoped tests: `uv run pytest tests/teams/ tests/test_cli_teams.py -q`
— 390 passed (up from 346 at the first pass' close: 42 new tests in
`tests/teams/test_sponsor_canonical.py`, 2 replaced in
`test_sponsor_extract.py`, 1 new pipeline-wiring test).
