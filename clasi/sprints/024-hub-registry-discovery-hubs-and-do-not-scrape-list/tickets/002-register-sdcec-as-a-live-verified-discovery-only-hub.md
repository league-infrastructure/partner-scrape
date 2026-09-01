---
id: '002'
title: Register SDCEC as a live-verified discovery-only hub
status: in-progress
use-cases:
- SUC-001
depends-on: []
github-issue: ''
issue: 36-hub-registry-discovery-only.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Register SDCEC as a live-verified discovery-only hub

## Description

`registry/hubs/` currently holds only `example-regional-calendar.toml`,
explicitly marked as a non-live template (sprint 005). This ticket adds
the first real hub: SDCEC's (San Diego County Engineering Council)
hand-curated youth STEM program list at
`https://www.sandiegoengineers.org/stem`.

Sprint 024's planning live-verified this candidate on 2026-08-31 (see
`sprint.md`'s Architecture > What Changed):
- `https://www.sandiegoengineers.org/stem` returns HTTP 200.
- **The bare `sandiegoengineers.org` domain (no `www`) fails TLS
  negotiation entirely** — `page_urls` must use the `www.` host, not
  the bare domain.
- `https://www.sandiegoengineers.org/robots.txt` returns HTTP 404 (no
  robots.txt file present). Per `fetch/robots.py`'s existing
  `is_allowed()` contract, any non-200 response is already treated as
  "everything allowed" — this needs no code change, just confirmation
  the existing behavior is correct for this hub.
- No Terms of Service, legal, or usage-restriction link exists anywhere
  on the site (checked both the homepage and the `/stem` page).
- A direct fetch of the `/stem` page found 124 distinct outbound
  (different-domain) links — real lead-generation signal, not a sparse
  or placeholder page.

This is a pure data addition through the existing, unmodified
`HubConfig` schema (`hub_id`, `hub_name`, `page_urls`, `config`) and the
existing `load_hubs()` → `discovery.hub_scan.scan_hub()` →
`candidate_pipeline` → `registry.candidates.write_candidate()` path —
already wired into the `discover-candidates` CLI subcommand
(`cli.py`). No code in any of those modules changes.

**One existing test currently hardcodes the assumption that the real
hub registry has exactly one entry** and will fail the moment this
ticket's TOML file is added:
`tests/test_registry_hub_schema.py::TestRealSeedHubRegistry::test_defaults_to_the_real_hubs_directory_when_no_argument_given`
asserts `{h.hub_id for h in hubs} == {"example-regional-calendar"}`.
Update it to `{"example-regional-calendar", "sdcec-stem"}`. This is a
required part of this ticket, not incidental cleanup — see `sprint.md`'s
Test Strategy.

## Acceptance Criteria

- [x] `partner_scrape/registry/hubs/sdcec-stem.toml` exists with
      `hub_name` set and `page_urls = ["https://www.sandiegoengineers.org/stem"]`
      (the `www.` host — the bare domain does not negotiate TLS).
- [x] The file's header comment documents the 2026-08-31 live
      verification: HTTP 200 on the page, robots.txt 404 (no
      restriction), no ToS found, 124 distinct outbound domains
      observed — mirroring the comment convention already used in
      `registry/sources/balboa-park.toml` and
      `registry/sources/usasciencefestival.toml`.
- [x] `HubConfig.from_toml` parses the new file without raising
      `InvalidHubConfig`.
- [x] `tests/test_registry_hub_schema.py`'s
      `test_defaults_to_the_real_hubs_directory_when_no_argument_given`
      is updated to assert
      `{"example-regional-calendar", "sdcec-stem"}`.
- [x] A live dry run of `discover-candidates` scoped to just this hub
      (e.g. `uv run partner-scrape discover-candidates --hubs-dir <a
      directory containing only sdcec-stem.toml>`, or the real
      `registry/hubs/` directory if the template hub's own dry-run
      behavior is already known-good) completes without error and
      yields at least one `OrgCandidate`/queued stub — matching this
      project's established "verify actual yield live, not just
      reachability" convention from sprints 014-016 (e.g. their
      `found=N new=M`-style verification). Record the actual count
      observed in this ticket's Notes.
- [x] `uv run pytest` passes in full.

## Notes (ticket 002 completion, 2026-08-31)

**Live dry-run result**: ran
`uv run partner-scrape discover-candidates --hubs-dir <tmp dir
containing only sdcec-stem.toml> -v` with the real `AnthropicLLMClient`
relevance gate (`ANTHROPIC_API_KEY` present, no `--no-enrich`) against
the real Candidate Review Queue (`partner_scrape/registry/candidates/`,
previously empty). Output:

```
partner-scrape discover-candidates: scanned 1 hub, queued 241 candidates for review.
```

Full log line from `candidate_pipeline`: "Scanned 1 hub(s): 257
candidate(s) survived relevance gating, 241 written to the review
queue" — the remaining 16 were exact-URL duplicates within the same
page (e.g. repeated "Volunteer" links pointing at the same Google Form
across multiple listed programs), correctly deduped by
`registry/candidates.py`'s existing skip-on-duplicate-URL logic. Exit
code 0, no errors. 241 real `OrgCandidate` stub TOML files were written
to `partner_scrape/registry/candidates/` and are included in this
ticket's commit as the designed, expected output of running this
feature (per this ticket's dispatch instructions — matches how sprints
014-016 committed live feed-verification output).

No code changes were needed anywhere — `HubConfig`, `hub_schema.py`,
`discovery/hub_scan.py`, `discovery/candidate_pipeline.py`,
`registry/candidates.py`, and `cli.py`'s `discover-candidates`
subcommand (including its existing `--hubs-dir` scoping flag) all
worked unmodified. `fetch/robots.py`'s `is_allowed()` correctly treated
the site's HTTP 404 robots.txt as allow-all, as documented in the TOML
header comment and confirmed live by this run (the page was fetched
successfully).

## Implementation Plan

**Approach**: Follow `example-regional-calendar.toml`'s exact file
structure (a leading comment block, `hub_name`, `page_urls`, optional
`[config]`) — this hub needs no scan hints, so `[config]` may be
omitted entirely, matching `hub_schema.py`'s documented default
(`config: dict = field(default_factory=dict)`). Update the one test
assertion named above. Run the live dry-run as a manual verification
step (not added to the automated test suite — see Testing below on
why).

**Files to create**:
- `partner_scrape/registry/hubs/sdcec-stem.toml`

**Files to modify**:
- `tests/test_registry_hub_schema.py` (one assertion, one line)

**Testing plan**:
- Run `uv run pytest tests/test_registry_hub_schema.py -v` — confirm
  `TestRealSeedHubRegistry` passes with the updated two-hub set, and
  that no other test in the file (e.g. the malformed/missing-field
  tests using the fixtures directory) is affected.
- Run `uv run pytest` (full suite) to confirm no regression elsewhere
  (e.g. `tests/test_discovery_hub_scan.py`'s
  `test_omitting_sources_dir_checks_the_real_registry`-style tests that
  touch the real registry directories).
- Perform the live dry-run described in Acceptance Criteria as a
  one-time manual check, not a new automated test — this project's
  hermetic-testing convention keeps live network calls out of
  `tests/` (see `sprint.md`'s Test Strategy); the dry-run's result gets
  recorded in this ticket's Notes instead, the same way sprint
  014-016's feed-registration tickets recorded live yield counts in
  their own ticket Notes rather than as pytest assertions.

**Documentation updates**: None beyond the new TOML file's own header
comment — no `DESIGN.md` change is needed for this ticket (registry's
DESIGN.md already documents `hubs/` as a catalog; adding one file to it
doesn't change that description). Ticket 001 handles the one
`DESIGN.md` cross-reference this sprint adds, for `DO_NOT_SCRAPE.md`.

## Testing

- **Existing tests to run**: `uv run pytest tests/test_registry_hub_schema.py -v`,
  then `uv run pytest` (full suite).
- **New tests to write**: None required — the existing
  `TestRealSeedHubRegistry` class already covers "does the real
  registry parse correctly" generically; only its one hardcoded
  assertion needs updating (see Description/Acceptance Criteria).
- **Verification command**: `uv run pytest`
