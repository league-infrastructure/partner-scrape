---
id: '004'
title: RobotEvents API config plumbing and events adapter
status: in-progress
use-cases:
- SUC-006
- SUC-008
depends-on: []
github-issue: ''
issue: 26-robotevents-adapter-vex-and-drones.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# RobotEvents API config plumbing and events adapter

## Description

VEX Robotics Competition (CA Region 4: San Diego/Imperial, V5RC +
VIQRC, roughly a dozen local tournaments per season plus two ~96-team
regional championships) and the Aerial Drone Competition (same
RobotEvents platform, RECF + partner Robolink) are entirely absent from
the opportunity pipeline today. `robotevents.com` 403s a plain fetch;
RobotEvents API v2 (`/events`, `/seasons`, `/programs`, filterable by
season/region/level) is the only viable path, gated by a free bearer
token from a RobotEvents account.

This ticket builds two independent pieces: (1) `config.py` accessors
for the token/base URL, mirroring `get_tba_api_key()`/`get_tba_url()`
exactly (see `config.py`'s existing `TBA_API_KEY_ENV_VAR`/
`TBA_URL_ENV_VAR` pattern — same doc conventions, same
quote-stripping, same `RuntimeError` on missing/empty key); and (2) a
new `adapters/robotevents.py` structured-API adapter (same
`discover → fetch → extract` shape as `tec_rest`/`localist`, CONFIDENCE
1.0) that pulls RobotEvents' spectator-open tournament events for CA
Region 4 into the Opportunity pipeline as ordinary `Event`s. No
`enrich/llm_client.py` or prompt change is needed or in scope —
`Competitions` already exists as an LLM-classifiable `opportunity_type`
value (sprint 015); a RobotEvents tournament event is expected to
classify into it via the existing, unmodified prompt
(`PROMPT_VERSION` stays 2).

Per `sprint.md`'s Success Criteria and Migration Concerns: this ticket
must not hard-block on `ROBOTEVENTS_KEY` being present in the executing
environment. Build and hermetically test the adapter regardless;
register the source TOML unconditionally (matching `frc-sd.toml`'s TBA
precedent — a registered-but-uncredentialed source degrades gracefully
via existing per-source isolation, it is not withheld); live-verify a
non-zero dry-run only if a token happens to be available.

## Acceptance Criteria

- [ ] `config.get_robotevents_api_key()` reads `ROBOTEVENTS_KEY`,
      strips surrounding quotes, and raises `RuntimeError` with a
      clear message if unset/empty — matching
      `get_tba_api_key()`'s exact contract and docstring conventions.
- [ ] `config.get_robotevents_url()` reads `ROBOTEVENTS_URL` if set,
      else returns a sensible default (RobotEvents API v2's real base
      URL, confirmed live during this ticket) — matching
      `get_tba_url()`'s contract.
- [ ] `adapters/robotevents.py` implements the `Adapter` protocol
      (`discover`, `fetch(ref, fetcher, source)`, `extract`), uses
      `acquisition_kwargs(source)` on every `fetcher.get()` call
      (matching every other structured adapter since sprint 015
      ticket 003), and is registered in `adapters/__init__.py`'s
      `ADAPTERS` dict as `"robotevents"`.
- [ ] `extract()` maps each RobotEvents event record to a canonical
      `Event` (title, start/end, location, registration_url at
      minimum; `CONFIDENCE = 1.0`), with per-record error isolation
      (a malformed record is logged and skipped, matching every other
      structured adapter's convention — not this ticket's own new
      pattern).
- [ ] A missing/invalid `ROBOTEVENTS_KEY` (or an API auth failure) is
      isolated by `pipeline.run()`'s existing per-source isolation —
      it is caught, logged, and skips only this source; it must not be
      allowed to propagate and abort the run. Add a fixture test
      proving this explicitly, matching `sources/tba.py`'s equivalent
      isolation contract on the teams side.
- [ ] `registry/sources/robotevents-vex-sd.toml` is registered
      (`adapter_type = "robotevents"`, `enabled = true`) regardless of
      whether a live token is available during this ticket's
      execution — mirroring `frc-sd.toml`'s TBA precedent, not
      withheld the way sprint 014/015 withheld a feed that returned
      zero at dry-run time (this is a credential-availability gap, not
      a broken endpoint).
- [ ] `ROBOTEVENTS_KEY` is added to `config/prod/secrets.env` (SOPS,
      matching `TBA_KEY`'s existing entry) and documented in
      `config.py`'s docstring the same way `TBA_KEY`'s provisioning gap
      is documented — an operator step, not something this ticket can
      complete end-to-end without the stakeholder's RobotEvents
      account.
- [ ] If a live `ROBOTEVENTS_KEY` is available during this ticket's
      execution, `partner-scrape --dry-run --no-enrich --source
      robotevents-vex-sd` is run and its non-zero result recorded in
      this ticket's Notes. If no token is available, this is recorded
      as deferred (not a failure) in Notes, and the ticket still moves
      to `done` — the missing credential does not block sprint close,
      per `sprint.md`'s explicit constraint.
- [ ] Full test suite stays green (1541+ passed, all new coverage
      hermetic).

## Testing

- **Existing tests to run**: `uv run pytest`, especially the adapter
  registration/dispatch tests in `adapters/__init__.py`'s test module.
- **New tests to write**: fixture `/events` (and `/seasons`/`/programs`
  if `discover()`'s probe needs them) JSON responses, malformed-record
  isolation fixtures (matching `tec_rest`/`localist`'s convention),
  and a missing-token isolation fixture proving `pipeline.run()`
  survives the failure.
- **Verification command**: `uv run pytest`, plus the conditional live
  dry-run above (not pytest) if a token is available.

## Implementation Plan

**Approach**: Config accessors first (small, mechanical, directly
mirrors an existing pattern), then the adapter itself, built and
tested fixture-first against RobotEvents API v2's real, documented
shape (confirmed live where a probe is cheap and doesn't need the
token — e.g. `/programs`, if publicly readable — otherwise fixture-only
until a token is available).

**Files to create/modify**:
- `partner_scrape/config.py` — `ROBOTEVENTS_API_KEY_ENV_VAR`,
  `ROBOTEVENTS_URL_ENV_VAR`, `get_robotevents_api_key()`,
  `get_robotevents_url()`.
- `partner_scrape/adapters/robotevents.py` (new).
- `partner_scrape/adapters/__init__.py` — register `"robotevents"`.
- `partner_scrape/registry/sources/robotevents-vex-sd.toml` (new).
- `config/prod/secrets.env`, `config/dev/secrets.env` — `ROBOTEVENTS_KEY`
  entry.

**Testing plan**: see Testing above.

**Documentation updates**: `partner_scrape/adapters/DESIGN.md` gains a
new `robotevents` entry in its adapter-family table plus a sprint-016
paragraph (matching `leaguesync`'s auth-header documentation
convention); `partner_scrape/registry/DESIGN.md` gets a one-line note
recording the new source.
