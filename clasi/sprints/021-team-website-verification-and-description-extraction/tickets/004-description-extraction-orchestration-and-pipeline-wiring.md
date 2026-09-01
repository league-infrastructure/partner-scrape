---
id: '004'
title: Description extraction orchestration and pipeline wiring
status: open
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

- [ ] `Team` carries the four new fields described above, with the
      stated defaults.
- [ ] `extract_descriptions()` sets all four fields correctly on a
      successful summarization: `description` non-empty,
      `description_status == "generated"`,
      `description_provenance == "team_website"`,
      `description_fetched_at` a non-empty ISO timestamp.
- [ ] A fixture LLM response containing an email address is rejected —
      `description` stays empty, `description_status == "unavailable"`,
      logged, never published. This is a dedicated, explicit test (the
      issue's own required "explicit guard/test" for the no-email
      invariant), not incidental coverage.
- [ ] An empty LLM response (nothing substantive to summarize) yields
      `description_status == "unavailable"`, never `"generated"` with an
      empty string.
- [ ] A team with no `fetch_results` entry (never `website_status ==
      "confirmed"`) never reaches this flow — `description_status`
      stays at its dataclass default, `"none"`.
- [ ] A cache/LLM failure (network error, malformed response, missing
      `ANTHROPIC_API_KEY`) is caught per team, logged, and leaves that
      team's four description fields at their defaults — never aborts
      extraction for any other team (fail-open, matching
      `sponsor_extract.py`'s and `enrich/`'s convention).
- [ ] A cache hit (same team, same content hash) makes zero LLM calls.
- [ ] `run_teams(..., no_descriptions=True)` skips this stage entirely
      while `verify_team_websites()`/`extract_sponsors()` still run —
      mirroring the existing `--no-sponsors` wiring test exactly.
- [ ] `AnthropicDescriptionLLMClient()`/`DescriptionCache()`
      default-construct without raising when `run_teams()` is called
      with neither injected, in a scenario where no confirmed page has
      gatherable content — proving that path never touches the real
      Anthropic SDK, mirroring the existing sponsor default-construction
      test.
- [ ] `cli.py`'s `teams` subcommand gains `--no-descriptions`, threaded
      into `run_teams()`.
- [ ] `tests/teams/test_export.py`'s `_real_fixture_teams()` helper is
      extended to also run one team's fetched page through
      `extract_descriptions()` (fixture LLM client, no network) — the
      same extension pattern sprint 013 ticket 005 already applied for
      sponsor extraction — so `TestNoEmailInExport`'s existing
      whole-payload email-pattern sweep is exercised against output that
      includes a generated `description`, not just roster/sponsor
      fields. A new sanity test (mirroring
      `TestSponsorExtractionFixtureIsWired`) proves this fixture path is
      actually producing a description, not silently vacuous.
- [ ] A required pre-close live run: `partner-scrape teams --dry-run -v`
      against the real, live registry, with the resulting
      `description_status` distribution recorded in this ticket's Notes,
      and a human sample of a handful of generated descriptions checked
      for fabrication or leaked contact info before this sprint closes
      — mirroring sprint 013's own required pre-close sponsor-sampling
      step.
- [ ] Full existing test suite stays green; no test writes into this
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
