---
id: '004'
title: RobotEvents API config plumbing and events adapter
status: done
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

- [x] `config.get_robotevents_api_key()` reads `ROBOTEVENTS_KEY`,
      strips surrounding quotes, and raises `RuntimeError` with a
      clear message if unset/empty — matching
      `get_tba_api_key()`'s exact contract and docstring conventions.
- [x] `config.get_robotevents_url()` reads `ROBOTEVENTS_URL` if set,
      else returns a sensible default (RobotEvents API v2's real base
      URL, confirmed live during this ticket) — matching
      `get_tba_url()`'s contract.
      **Annotation:** not confirmed via a live authenticated probe
      (no `ROBOTEVENTS_KEY` available — every documented v2 endpoint
      requires the Bearer token, so there was no unauthenticated live
      call to run instead). Confirmed instead against RobotEvents' own
      published OpenAPI schema, via the `baseUrl` the actively
      -maintained open-source `robotevents` npm client
      (https://github.com/brenapp/robotevents) is generated against
      and constructs its client with. See `config.py`'s
      `DEFAULT_ROBOTEVENTS_URL` docstring.
- [x] `adapters/robotevents.py` implements the `Adapter` protocol
      (`discover`, `fetch(ref, fetcher, source)`, `extract`), uses
      `acquisition_kwargs(source)` on every `fetcher.get()` call
      (matching every other structured adapter since sprint 015
      ticket 003), and is registered in `adapters/__init__.py`'s
      `ADAPTERS` dict as `"robotevents"`.
- [x] `extract()` maps each RobotEvents event record to a canonical
      `Event` (title, start/end, location, registration_url at
      minimum; `CONFIDENCE = 1.0`), with per-record error isolation
      (a malformed record is logged and skipped, matching every other
      structured adapter's convention — not this ticket's own new
      pattern).
- [x] A missing/invalid `ROBOTEVENTS_KEY` (or an API auth failure) is
      isolated by `pipeline.run()`'s existing per-source isolation —
      it is caught, logged, and skips only this source; it must not be
      allowed to propagate and abort the run. Add a fixture test
      proving this explicitly, matching `sources/tba.py`'s equivalent
      isolation contract on the teams side.
- [x] `registry/sources/robotevents-vex-sd.toml` is registered
      (`adapter_type = "robotevents"`, `enabled = true`) regardless of
      whether a live token is available during this ticket's
      execution — mirroring `frc-sd.toml`'s TBA precedent, not
      withheld the way sprint 014/015 withheld a feed that returned
      zero at dry-run time (this is a credential-availability gap, not
      a broken endpoint).
- [x] `ROBOTEVENTS_KEY` is added to `config/prod/secrets.env` (SOPS,
      matching `TBA_KEY`'s existing entry) and documented in
      `config.py`'s docstring the same way `TBA_KEY`'s provisioning gap
      is documented — an operator step, not something this ticket can
      complete end-to-end without the stakeholder's RobotEvents
      account.
      **Annotation:** the SOPS *entry* itself is deferred — there is
      no real token value to encrypt (no RobotEvents account exists
      for this project yet), and hand-writing a placeholder into a
      SOPS-encrypted file would misrepresent it as a real provisioned
      secret and break the file's MAC. What this ticket *can* and does
      complete: `config.py`'s `ROBOTEVENTS_API_KEY_ENV_VAR` docstring
      documents the gap and the exact provisioning steps (account →
      token → `sops`-encrypted `secrets.env` entry), and
      `registry/sources/robotevents-vex-sd.toml`'s header comment
      repeats those steps for an operator to action. See this ticket's
      Notes.
- [x] If a live `ROBOTEVENTS_KEY` is available during this ticket's
      execution, `partner-scrape --dry-run --no-enrich --source
      robotevents-vex-sd` is run and its non-zero result recorded in
      this ticket's Notes. If no token is available, this is recorded
      as deferred (not a failure) in Notes, and the ticket still moves
      to `done` — the missing credential does not block sprint close,
      per `sprint.md`'s explicit constraint.
      **Annotation:** deferred — no `ROBOTEVENTS_KEY` was available in
      any of the shell environment, `.env`, or `config/`'s assembled
      secrets during this ticket's execution (verified directly, see
      Notes). Not attempted; not blocking.
- [x] Full test suite stays green (1541+ passed, all new coverage
      hermetic). **1599 passed** (was 1555 at ticket start; +44 new
      tests: 6 in `tests/test_config.py`, 38 in the new
      `tests/test_adapters_robotevents.py`).

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

## Notes (ticket 004 completion, 2026-08-30)

**Token reality, verified directly.** `ROBOTEVENTS_KEY` is absent from
the shell environment, the repo's `.env`, and every layer under
`config/` on this checkout — confirmed by grep before writing any code,
not assumed. No RobotEvents account exists for this project yet. Every
piece of this ticket that could be built and hermetically tested
without a token was; the two items that genuinely require one (a live
`/events` probe, a real SOPS-encrypted secret value) are deferred per
`sprint.md`'s explicit "does not block sprint close" constraint, not
skipped silently — see the annotated AC boxes above.

**Endpoint shape sourcing.** With no token, no authenticated live call
was possible against `robotevents.com/api/v2` (confirmed: even
`/programs`, hoped to be an unauthenticated-readable probe per the
Implementation Plan, 404s without a token). The exact `/events`
request/response shape (`meta`/`data` envelope, `season`/`program`/
`location` field structure, the `Authorization: Bearer` scheme, and the
real base URL) was instead confirmed against RobotEvents' own published
OpenAPI schema, via the actively-maintained open-source `robotevents`
npm client (https://github.com/brenapp/robotevents, MIT, generated
directly from that schema) — its `src/utils/client.ts`
(`baseUrl: "https://www.robotevents.com/api/v2"`), `src/generated/
robotevents.ts` (the full OpenAPI-derived type definitions, including
`event_getEvents`'s exact query parameters — `season[]`, `region`,
`level[]`, `eventTypes[]`, `page`, `per_page`; confirmed there is no
`program[]` filter), and `src/wrappers/Event.ts` (confirmed the public
event page is `https://www.robotevents.com/{sku}.html`). Documented in
`adapters/robotevents.py`'s own module docstring and `config.py`'s
`DEFAULT_ROBOTEVENTS_URL` docstring; flagged for live re-verification
the first time a token exists.

**Adapter implemented exactly as designed.** `adapters/robotevents.py`
follows `tec_rest`/`localist`'s probe-then-paginate `discover()` shape
(`per_page=1` probe reads `meta.last_page`) with `leaguesync`'s Bearer-
auth convention. One deliberate deviation from `localist`'s graceful
probe-failure degrade: a `401` probe response raises `RuntimeError`
immediately (matching `teams/sources/tba.py`'s explicit-401-raise
precedent), since an auth failure is not a transient hiccup and must
reach `pipeline.run()`'s per-source isolation, not silently degrade to
"zero events." A missing/empty `ROBOTEVENTS_KEY` raises even earlier,
inside `_auth_headers()`, before any request is attempted — same
mechanism as `teams/sources/tba.py`. No season-ID guessing was needed:
`/events` has no `program[]` filter (RobotEvents only hosts VEX-family
programs) and this adapter scopes its query via `region`/`eventTypes[]`
(`["tournament"]` default) plus a `start` date filter defaulting to
"today," not via `season_ids` (optional, unset in the committed TOML —
RobotEvents' season IDs are opaque integers with no derivable pattern
and no token was available to look the current ones up via `/seasons`).

**Config plumbing** (`config.py`) is a line-for-line mirror of
`get_tba_api_key()`/`get_tba_url()`: `ROBOTEVENTS_API_KEY_ENV_VAR`,
`ROBOTEVENTS_URL_ENV_VAR`, `DEFAULT_ROBOTEVENTS_URL`,
`get_robotevents_api_key()` (quote-stripping, `RuntimeError` on unset/
empty), `get_robotevents_url()`.

**Registration** (`registry/sources/robotevents-vex-sd.toml`,
`adapter_type = "robotevents"`, `enabled = true`) follows `frc-sd.toml`'s
TBA precedent exactly — registered unconditionally, not withheld for
lacking a live-verified non-zero dry-run, since the gap is credential
availability, not a broken endpoint. `respect_robots = false` (a keyed
REST API, not a scraped site, matching `leaguesync.toml`'s identical
reasoning). The TOML's header comment documents the operator
provisioning steps (RobotEvents account → API key → SOPS
`config/prod/secrets.env`/`config/dev/secrets.env` entry) and flags
that `region = "CA"` is this ticket's best-available guess at
RobotEvents' own `region` query semantics, not live-confirmed.

**`config/prod/secrets.env`/`config/dev/secrets.env` were not
modified.** No `ROBOTEVENTS_KEY` entry was added — there is no real
token value to encrypt, and both files are SOPS-encrypted with a MAC
covering their contents; hand-writing a placeholder would misrepresent
it as a real provisioned secret and corrupt that MAC. This is a
genuine, single, precise deviation from the Implementation Plan's
"Files to create/modify" list, made deliberately per this ticket's own
task briefing ("Operator-step reality," verified live before any code
was written) rather than discovered as a surprise mid-ticket. The
provisioning step is fully documented (`config.py`'s
`ROBOTEVENTS_API_KEY_ENV_VAR` docstring, the TOML's header comment) so
an operator can complete it directly with `sops -e` once a RobotEvents
account exists.

**Tests** (`tests/test_config.py`'s new `TestRobotEventsApiKey`/
`TestRobotEventsUrl`, and the new `tests/test_adapters_robotevents.py`,
built from `tests/fixtures/robotevents/`'s hand-authored — not
live-captured — fixture JSON): field mapping across a two-page `/events`
result spanning all three RobotEvents-hosted programs in scope (V5RC,
VIQRC, ADC); auth-header and `acquisition_kwargs()` threading on both
the probe and every page fetch; pagination probe/degrade behavior;
malformed-record isolation (empty `name`, a non-dict array element, an
unparseable `start` date); query-URL construction (percent-encoded
`season[]`/`eventTypes[]` array params, `region`/`start` omitted when
falsy); the `start` default-to-today fallback (via a monkeypatched
`date` class, matching `tests/test_export.py`'s `FakeDateTime`
convention); and, directly answering this ticket's own explicit ask, a
`TestMissingOrInvalidTokenIsolation` class proving both a missing key
and a `401` response raise `RuntimeError` out of `discover()` *and*
propagate uncaught out of `adapters.run()` (the exact call
`pipeline.py`'s `_run_one_source` wraps), plus one full
`pipeline.run()` end-to-end test (`TestPipelineRunSurvivesAMissingToken`,
mirroring `tests/teams/test_pipeline.py`'s `TestTbaFailureIsolation`)
proving a real run over a tmp-path registry with this source (missing
token) alongside a healthy `leaguesync` source completes without
raising and reports both outcomes correctly via the `Reporter` hook.

**Test count**: 1555 → 1599 (+44: 6 in `test_config.py`, 38 in
`test_adapters_robotevents.py`). Full suite green.

**Deviations from the plan**: (1) `config/prod/secrets.env`/
`config/dev/secrets.env` not modified — see above, pre-flagged in this
ticket's own task briefing, not a surprise. (2) `season_ids` config
support was added to the adapter (optional, unused by the committed
TOML) beyond the plan's literal text, to keep the design honest about
RobotEvents' real filtering options without requiring an unconfirmed
guess at season ID values — a strict subset of "filterable by season/
region" already named in the issue and sprint.md's Problem statement,
not new scope.
