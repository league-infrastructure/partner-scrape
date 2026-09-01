---
id: '004'
title: Description extraction orchestration and pipeline wiring
status: done
use-cases:
- SUC-023
depends-on:
- '003'
github-issue: ''
issue: 44-team-website-links-and-descriptions.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Description extraction orchestration and pipeline wiring

## Description

This ticket wires everything tickets 002 and 003 built into one
per-team pipeline stage, adds the four new `Team` fields, and sequences
the new stage into `run_teams()` — mirroring
`teams/sponsor_extract.py`'s role and `teams/pipeline.py`'s ticket-005
wiring from sprint 013, exactly.

`teams.description_extract.extract_descriptions(teams, fetch_results,
llm_client, cache, *, clock=...) -> None` runs once per team with an
entry in `fetch_results` (the same dict `teams.scrape.
verify_team_websites()` already produces and
`teams.sponsor_extract.extract_sponsors()` already consumes — no second
fetch): gather content (ticket 002's
`gather_description_content()`; an empty result skips straight to the
next team, matching `sponsor_extract.py`'s own candidate-list cost-
control gate) → cache lookup → summarize on a miss → validate → publish.

**No-email guard, layer 3 of 3.** Whatever the LLM returns is checked,
in code, against an email-address pattern before it can be published —
the final backstop on top of ticket 002's gathering-time scrub (layer 1)
and ticket 003's prompt instruction (layer 2). A match means the result
is dropped and logged exactly like an empty result — `description`
stays empty, `description_status = "unavailable"`, never published. This
mirrors `sponsor_extract.py`'s own `_is_denylisted()` role: a
deterministic, code-level check that does not trust the LLM's compliance
with its own instructions alone. A response exceeding a documented
maximum length is rejected the same way, mirroring
`sponsor_extract._MAX_SPONSOR_NAME_LENGTH`'s own defense-in-depth
precedent.

**Four new `Team` fields** (added in this ticket, matching how
`sponsor_provenance` itself was added in sprint 013's own orchestration
ticket, 005, not an earlier one):
- `description: str = ""`
- `description_status: str = "none"` — one of `"generated"`
  (summarized successfully), `"unavailable"` (a confirmed fetch existed
  but gathering found nothing usable, or extraction failed and fell
  back per the fail-open contract below), `"none"` (no confirmed fetch
  to extract from at all — mirrors `website_status`'s own `"none"`
  vocabulary for "nothing attempted").
- `description_provenance: str = ""` — `"team_website"` when
  `description_status == "generated"`, else `""`.
- `description_fetched_at: str = ""` — ISO-8601 UTC timestamp of
  generation (via an injectable `clock` parameter, matching
  `EnrichmentCache`/`SponsorCache`'s own testable-clock convention),
  empty when no description was generated.

These are deliberately **independent of `Team.website_status`** — a
stem-ecosystem peer's planning-time refinement: `website_status` keeps
answering "was the site reachable" (the existing dead-link-guard
concern, unchanged by this ticket); `description_status` answers "did
we find anything worth showing," a genuinely different, separately-true
fact (a reachable site can still have nothing extractable). Do not
collapse the two into one signal.

`teams/pipeline.py`'s `run_teams()` gains one new stage, sequenced after
`canonicalize_sponsors()` and before `export_teams()`, plus new
`description_llm_client`/`description_cache`/`no_descriptions`
parameters — lazily constructed exactly like `llm_client`/
`sponsor_cache`/`no_sponsors` already are (never touching the
`anthropic` SDK when `no_descriptions` is set or `fetch_results` is
empty). `cli.py` gains a `--no-descriptions` flag on the `teams`
subcommand, threaded into `_run_teams()` exactly like `--no-sponsors`.
`teams/export.py` needs **no code change** — `TEAMS_SCHEMA_FIELDS`
already derives from `dataclasses.fields(Team)`, so the four new fields
publish automatically.

## Acceptance Criteria

- [x] `Team` carries the four new fields described above, with the
      stated defaults.
- [x] `extract_descriptions()` sets all four fields correctly on a
      successful summarization: `description` non-empty,
      `description_status == "generated"`,
      `description_provenance == "team_website"`,
      `description_fetched_at` a non-empty ISO timestamp.
- [x] A fixture LLM response containing an email address is rejected —
      `description` stays empty, `description_status == "unavailable"`,
      logged, never published. This is a dedicated, explicit test (the
      issue's own required "explicit guard/test" for the no-email
      invariant), not incidental coverage.
- [x] An empty LLM response (nothing substantive to summarize) yields
      `description_status == "unavailable"`, never `"generated"` with an
      empty string.
- [x] A team with no `fetch_results` entry (never `website_status ==
      "confirmed"`) never reaches this flow — `description_status`
      stays at its dataclass default, `"none"`.
- [x] A cache/LLM failure (network error, malformed response, missing
      `ANTHROPIC_API_KEY`) is caught per team, logged, and leaves that
      team's four description fields at their defaults — never aborts
      extraction for any other team (fail-open, matching
      `sponsor_extract.py`'s and `enrich/`'s convention).
- [x] A cache hit (same team, same content hash) makes zero LLM calls.
- [x] `run_teams(..., no_descriptions=True)` skips this stage entirely
      while `verify_team_websites()`/`extract_sponsors()` still run —
      mirroring the existing `--no-sponsors` wiring test exactly.
- [x] `AnthropicDescriptionLLMClient()`/`DescriptionCache()`
      default-construct without raising when `run_teams()` is called
      with neither injected, in a scenario where no confirmed page has
      gatherable content — proving that path never touches the real
      Anthropic SDK, mirroring the existing sponsor default-construction
      test.
- [x] `cli.py`'s `teams` subcommand gains `--no-descriptions`, threaded
      into `run_teams()`.
- [x] `tests/teams/test_export.py`'s `_real_fixture_teams()` helper is
      extended to also run one team's fetched page through
      `extract_descriptions()` (fixture LLM client, no network) — the
      same extension pattern sprint 013 ticket 005 already applied for
      sponsor extraction — so `TestNoEmailInExport`'s existing
      whole-payload email-pattern sweep is exercised against output that
      includes a generated `description`, not just roster/sponsor
      fields. A new sanity test (mirroring
      `TestSponsorExtractionFixtureIsWired`) proves this fixture path is
      actually producing a description, not silently vacuous.
- [x] A required pre-close live run: `partner-scrape teams --dry-run -v`
      against the real, live registry, with the resulting
      `description_status` distribution recorded in this ticket's Notes,
      and a human sample of a handful of generated descriptions checked
      for fabrication or leaked contact info before this sprint closes
      — mirroring sprint 013's own required pre-close sponsor-sampling
      step.
- [x] Full existing test suite stays green; no test writes into this
      repo's real `data/` directory (reuse/extend the existing
      `_own_data_dir_default` autouse fixture pattern in
      `tests/teams/test_export.py`, don't reinvent it).

## Implementation Plan

**Approach**: New module `partner_scrape/teams/description_extract.py`
orchestrating tickets 002/003's building blocks, structurally parallel
to `sponsor_extract.py`. Modify `teams/model.py` (four new fields),
`teams/pipeline.py` (new stage + new `run_teams()` parameters, lazy
construction), `cli.py` (new flag). No change to `teams/export.py`.

**Files to create/modify**:
- `partner_scrape/teams/description_extract.py` (new) —
  `extract_descriptions()`, the email-guard/length-guard checks, fail-
  open per-team error handling.
- `partner_scrape/teams/model.py` — add
  `description`/`description_status`/`description_provenance`/
  `description_fetched_at` fields with docstring comments matching this
  file's existing per-field documentation density (see
  `sponsor_provenance`'s own comment block for the level of detail
  expected).
- `partner_scrape/teams/pipeline.py` — sequence the new stage; add
  `description_llm_client`/`description_cache`/`no_descriptions`
  parameters to `run_teams()`, docstring updated to describe the new
  stage matching the existing per-ticket docstring-history convention
  this module already follows.
- `partner_scrape/cli.py` — `--no-descriptions` flag on the `teams`
  subcommand parser; threaded into `_run_teams()`.
- `tests/teams/test_description_extract.py` (new) — mirrors
  `tests/teams/test_sponsor_extract.py`'s structure.
- `tests/teams/test_pipeline.py` — new wiring tests mirroring
  `TestSponsorExtractionWiring`/`TestCanonicalizeSponsorsWiring`.
- `tests/teams/test_export.py` — extend `_real_fixture_teams()`; add a
  `TestDescriptionExtractionFixtureIsWired`-style sanity test.
- `partner_scrape/teams/DESIGN.md` — add a paragraph documenting this
  sprint's addition, matching the file's existing per-sprint narrative
  convention (see its sprint 013 paragraph for the expected level of
  detail).

**Testing plan**: see Acceptance Criteria above.

**Documentation updates**: `teams/DESIGN.md` (as above);
`description_extract.py`'s own module docstring documenting the
three-layer no-email guard and the fail-open contract.

## Testing

- **Existing tests to run**: `uv run pytest tests/teams/`, full
  `uv run pytest` before closing.
- **New tests to write**: `tests/teams/test_description_extract.py`,
  new cases in `tests/teams/test_pipeline.py` and
  `tests/teams/test_export.py`, per Acceptance Criteria above.
- **Verification command**: `uv run pytest`, plus the required
  `partner-scrape teams --dry-run -v` live run (recorded in Notes, not
  an automated test).

## Notes

**Implementation.** New `partner_scrape/teams/description_extract.py`
(`extract_descriptions()`), mirroring `sponsor_extract.py`'s shape
exactly: gather content (ticket 002) → cache lookup (ticket 003) →
summarize on a miss → no-email guard (layer 3 of 3, a duplicated,
independent copy of the same email regex `description_candidates.py`/
`tests/teams/test_export.py` already use) + a length guard → publish.
Four new `Team` fields (`description`/`description_status`/
`description_provenance`/`description_fetched_at`) added to
`teams/model.py`, deliberately independent of `website_status` per
sprint.md's Design Rationale. `run_teams()` gained
`description_llm_client`/`description_cache`/`no_descriptions`
parameters and a new stage after `canonicalize_sponsors()`, lazily
constructing `AnthropicDescriptionLLMClient()`/`DescriptionCache()`
only when `no_descriptions` is unset and `fetch_results` is non-empty
— exactly mirroring the sponsor stage. `cli.py` gained
`--no-descriptions`. `teams/export.py` needed no change.
`teams/DESIGN.md` gained one narrative paragraph (Orientation) plus a
`BUILT (sprint 021, ...)` block, covering both this ticket and ticket
001's audit conclusion (no DESIGN.md update had landed for sprint 021
yet).

**Three-state `description_status` design decision.** The ticket's
Description and Acceptance Criteria text has a real tension: the
Description enumerates `"unavailable"` as covering both "gathering
found nothing usable" *and* "extraction failed and fell back," while
one Acceptance Criteria bullet says a cache/LLM failure "leaves that
team's four description fields at their defaults." I resolved this by
treating `"none"` as strictly "this stage never even looked at this
team" (no `fetch_results` entry) and `"unavailable"` as the outcome for
*every* case where a team was attempted but nothing publishable
resulted — empty gathered content, an empty LLM response, a guard
rejection, or a caught exception. This keeps `description_status`
actually able to answer "did we find anything worth showing" for every
team whose site was reachable, matching the field's own stated purpose;
the AC's "at their defaults" is satisfied for the other three fields
(`description`/`description_provenance`/`description_fetched_at`
genuinely stay at `""`), just not for `description_status` reverting to
`"none"`. Flagging this explicitly as a judgment call rather than
silently picking one reading.

**Hidden compatibility fix (found via hermetic-suite verification, not
assumed).** Running the full suite with `SCRAPE_CACHE_DIR`/
`ANTHROPIC_API_KEY` explicitly unset (`env -u SCRAPE_CACHE_DIR -u
ANTHROPIC_API_KEY uv run pytest`) surfaced that this ticket's new
unconditional-unless-`no_descriptions` lazy construction affects every
*pre-existing* `run_teams()` call with a non-empty `fetch_results`, not
just this ticket's own new tests -- exactly the same class of risk
sprint 013 ticket 005 first introduced for sponsors. Five pre-existing/
new tests needed a `no_descriptions=True` (or, for two of this ticket's
own new tests, `no_sponsors=True`) addition to stay hermetic:
`TestSponsorExtractionWiring`'s two wiring tests,
`TestWebsiteOverlayToVerificationWiring`'s overlay test, and this
ticket's own two `TestDescriptionExtractionWiring` tests that inject
only one side's fixture client. One of these
(`test_llm_client_and_sponsor_cache_default_to_real_implementations_when_omitted`)
was **silently making a real, billed Anthropic API call** before the
fix -- it "passed" (fail-open swallows the exception path, and its own
assertions never check `description_status`), but its `<p>Nothing
sponsor-shaped here.</p>` fixture page is genuinely description-shaped
content, and this session's ambient `ANTHROPIC_API_KEY` meant the call
was real, not just attempted-and-refused. Fixed by adding
`no_descriptions=True` there too. All five fixes are minimal,
compatibility-only additions to existing test call sites -- no
production-code or test-assertion behavior change beyond that.

**Full test suite** (hermetic: `env -u SCRAPE_CACHE_DIR -u
ANTHROPIC_API_KEY uv run pytest`): `tests/teams/` → 504 passed;
full repo suite → 1906 passed. No regressions. Confirmed no `data/`
directory was created and `git status --porcelain -- data/` stayed
empty throughout.

**Required pre-close live run — `SCRAPE_CACHE_DIR=$(grep
'^SCRAPE_CACHE_DIR=' config/prod/public.env | cut -d= -f2-) uv run
partner-scrape teams --dry-run -v`, 2026-08-31**, against the real,
live Team Registry, real `PoliteFetcher`, real Anthropic API calls
(Haiku), `--dry-run` so nothing was written. `TBA_KEY`/`ROBOTEVENTS_KEY`
were not set in this session (same reason ticket 001's own Notes
record: no assembled `.env` loaded, only the non-secret
`SCRAPE_CACHE_DIR` was sourced per the dispatch instructions'
explicit precedent) -- `frc-sd`/`vex-sd` were caught by `run_teams()`'s
existing per-source isolation and skipped, exactly the designed
"missing key degrades gracefully" contract, not a defect. Sources that
ran: `ftc-sd` (152 teams) + `fll-sd` (48 teams) = 200 teams total,
unchanged from ticket 001's own run.

`website_status`: 29 confirmed, 0 unverified, 171 none (matches ticket
001's own recorded distribution exactly, as expected -- this ticket
made no change to that stage).

**`description_status` distribution (the required number)**, from
`teams.description_extract`'s own aggregate log line:

    Description extraction: 29 team(s) with description-shaped page
    content processed, 24 generated, 5 had nothing publishable, 0 failed

All 29 confirmed teams had gatherable content (none skipped at the
empty-content gate before reaching "processed"). Of the 5
"unavailable": 4 had a genuinely empty LLM response (verified via the
persisted `DescriptionCache` entries under
`{SCRAPE_CACHE_DIR}/description_extraction_cache/` -- `ftc-9837`,
`ftc-6226`, `ftc-14968`, `ftc-30556`, each cached `"description": ""`),
and 1 (`ftc-11212`, "The Clueless") was rejected by the length guard --
see the defect below. `description_status` therefore split
24 `"generated"` / 5 `"unavailable"` / 171 `"none"` across the 200
published teams. No `no_descriptions`/`no_sponsors` skip involved --
both extraction stages ran for real.

**Defect found and fixed: length guard calibrated too tightly.** The
live run logged: `Description for team ftc-11212 (The Clueless)
exceeded the maximum length (546 > 500 characters); rejecting, never
publishing`. Inspecting the persisted cache entry (no second live LLM
call needed) showed the full 546-character description; cross-checking
every factual claim in it against the team's own live website
(`https://www.thecluelessftc.org/`, fetched read-only for this review)
confirmed every single detail -- founding year, member count, school
count, world records, World Championship qualifications, Inspire Award
count, and all four named community programs with their exact
figures -- was accurate and present on the real page. This was a false
rejection of genuine content, not a hallucination: my initial
`_MAX_DESCRIPTION_LENGTH = 500` guess (chosen before any live data)
was too tight for a team with an unusually large number of distinct
real programs to describe. Fixed by raising the constant to 800 (still
well under the 2000-character input bound, so it remains a meaningful
guard against the model echoing back most/all of the gathered content),
documented the live-data rationale in the constant's own docstring, and
added a dedicated regression test
(`test_a_real_genuine_long_description_observed_live_is_not_rejected`
in `tests/teams/test_description_extract.py`) using the exact
546-character text captured live, mirroring
`sponsor_extract.py`'s own `_MAX_SPONSOR_NAME_LENGTH`-tuned-from-a-
live-run precedent. Scope was kept to this one constant; no other code
changed as a result of the live run.

**Fabrication/leak sample (6 of the 24 generated descriptions,
inspected via the persisted cache -- no second live LLM call).**
Automated sweep first: the same email-address regex used elsewhere in
this project found zero matches across all 29 cached raw LLM responses
(generated and rejected alike) -- confirms the no-email guard's
layers held for the whole live batch, not just the manually-sampled
subset. Manual cross-check against each team's real live website
(read-only fetch, not an LLM call) for 6 of the 24 `"generated"`
descriptions:

- `ftc-11212` The Clueless (546 chars, the one flagged above) --
  every specific fact (founding year, member/school counts, world
  records, 4 named programs with exact figures) confirmed present and
  accurate on the real site.
- `ftc-9049` Robopuffs -- "empower... women... bridge the gender gap
  in S.T.E.M." confirmed verbatim/near-verbatim on the real page.
- `ftc-11128` Inspiration Robotics -- founding year (2011), location,
  competitions (RoboBoat/RoboSub/RobotX), and member age range all
  confirmed on the real page.
- `ftc-18755` Vikings Robotics -- school, FRC program, 2009 founding
  year, 6-week build season, and inclusive-community mission all
  confirmed on the real page.
- `ftc-1622` Team Spyder -- school (Poway High), FRC+FTC programs, and
  the specific "Poway High students, homeschool students, ... 8th
  grade students" membership description confirmed on the real page.
- `ftc-23251` Triple Fault Robotics -- the short (57-char) "team of
  makers from San Diego" summary is a plain, unremarkable restatement
  with nothing specific enough to independently fact-check beyond
  location, which matches the team's registry-known city.

**Assessment: no fabrication, no leaked contact info found** across
either the automated sweep (all 29) or the manual sample (6 of 24,
spanning the shortest, longest, and several mid-length generated
descriptions). The one real defect found (length-guard calibration)
was fixed within this ticket's own scope, as instructed.
