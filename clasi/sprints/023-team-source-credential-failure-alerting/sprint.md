---
id: '023'
title: Team Source Credential Failure Alerting
status: executing
branch: sprint/023-team-source-credential-failure-alerting
use-cases:
- SUC-027
issues:
- 62-missing-source-credential-degrades-silently-past-cli-exit-code.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 023: Team Source Credential Failure Alerting

## Goals

1. Make a missing/invalid `TBA_KEY` or `ROBOTEVENTS_KEY` an *actively
   surfaced* condition, not something an operator has to reason their
   way to from log traceback text or `teams.json`'s `by_league`
   key-absence — issue 62, filed after this exact gap was independently
   rediscovered twice in one night (sprint 021's own live-verification
   undercount and a stem-ecosystem peer's cross-check of published
   `teams.json`).
2. Distinguish, concretely and by exception type (not message-text
   guessing), a *credential* failure (missing key, or a 401 with a key
   present) from every other per-source failure mode and from a
   genuine, exception-free zero-teams result — these need different
   operator responses and currently look identical in both the log and
   the published artifact.

## Problem

`teams/pipeline.py`'s `run_teams()` wraps each active source's
acquisition in `try/except Exception: logger.exception(...); continue`
(ticket 011-002, extended by 011-003/016-005 to cover TBA/RobotEvents).
This is deliberate, correct per-source isolation — a bad HTML page, a
flaky network blip, or one org's site being briefly down should never
take the rest of a `teams` run down with it. But a missing/invalid
`TBA_KEY`/`ROBOTEVENTS_KEY` is not that kind of failure: it is
structural (an operator has to act) and will recur on *every single
run* until fixed, not just this one. Today it produces the exact same
"logged at ERROR with a traceback, then continue" signature as a
one-off scrape hiccup, `main()` still returns exit code 0, and
`teams.json` carries no explicit signal — only the passive, easy-to-miss
absence of a league's key from `meta.by_league` (`export.py`'s own
docstring already anticipated this: "a `TBA_KEY`-missing run's `meta`
has no `"FRC"` key in `by_league` at all"). Two independent people
reasoned their way to "an entire league was never attempted" from that
indirect evidence in one night; nothing in the pipeline told them
directly.

Verified against the current code (not assumed from the issue's own
framing — see Design Rationale for where that framing needed
correcting): `config.get_tba_api_key()`/`get_robotevents_api_key()`
raise a bare `RuntimeError` when the env var is unset, and
`TBASource.discover()`/`VexTeamSource.discover()` each raise a bare
`RuntimeError` for a 401 *and* for every other probe failure (non-200
status, unparseable JSON, an invalid page count). All of these are
`RuntimeError`, distinguished today only by free-text message content
("check TBA_KEY"/"check ROBOTEVENTS_KEY" substrings) — not by exception
identity. `run_teams()`'s per-source loop has no way to ask "was this
specifically a credential problem?" without either fragile string
matching or a real exception type to catch.

## Solution

Introduce a small, typed `CredentialError(RuntimeError)` in
`config.py` (already imported everywhere this matters), have the two
credential-specific raise sites in each source's `discover()`/
`_auth_headers()` chain use it, and give `run_teams()`'s per-source
loop a second `except CredentialError` branch (checked before the
existing generic `except Exception`) that accumulates which league(s)
failed this way. After the loop, if any credential failures occurred,
log exactly one loud, aggregate `logger.warning` naming every affected
league and source — mirroring the *shape* of
`observability/yield_report.py`'s `zero_yield`/`cliff` alert (loud,
first, not buried in per-source detail) without importing
`observability/` itself (see Design Rationale for why that import
would be both a new, unprecedented cross-subsystem edge and a poor
mechanistic fit). Every other per-source failure mode keeps today's
existing behavior exactly — logged, isolated, no new alert — since
per-source isolation is already the *right* design for transient
failures (issue 62's own Cause section agrees); this sprint only adds
a second, louder layer for the one failure mode that is not transient.

Also add an explicit `credential_failures` key to
`teams/export.py`'s `_build_meta()` payload, threaded through from
`run_teams()`, so the one artifact that actually gets published and
consumed downstream (`teams.json`, three write targets) carries an
unambiguous, always-present signal — not just the log line, which only
whoever captured that run's log will ever see.

`main()`'s exit code is deliberately left unchanged (still 0). See
Design Rationale for why this sprint resolves issue 62's open exit-code
question as logging/payload-only.

## Success Criteria

1. A fixture run where a registered team source's credential-reading
   path raises `CredentialError` produces exactly one aggregate
   `logger.warning` naming that league, and the run still completes
   (`teams.json` still gets published with every other source's
   teams) — matching today's degrade-gracefully behavior, just no
   longer silent about *why*.
2. A fixture run where a source completes normally with zero teams
   (no exception at all) does not fire the new alert.
3. A fixture run where a source raises a non-credential `RuntimeError`
   (e.g. a bad HTML page) does not fire the new alert either — proving
   the new alert is specific to `CredentialError`, not a broadened
   catch-all.
4. `teams.json`'s `meta.credential_failures` lists the affected
   league(s) on a credential-failure run and is an empty list on a
   clean run — in both `dry_run` and real-write paths.
5. A required pre-close live run against this machine's real
   credential state is recorded with real numbers (this project's
   established sprints 020-022 convention), confirming the new alert
   neither fires spuriously on a healthy run nor silently passes a
   genuinely broken one.
6. Full existing test suite stays green; every new test is hermetic
   (fixture-based, no real network/API calls).

## Scope

### In Scope

- A new `CredentialError(RuntimeError)` exception type, and updating
  `tba.py`/`robotevents.py`/`config.py`'s existing credential-failure
  raise sites to use it.
- A loud, aggregate, run-scoped alert in `teams/pipeline.py`'s
  `run_teams()`, naming every league whose source failed on a
  credential problem this run.
- An explicit `credential_failures` key in `teams/export.py`'s
  `_build_meta()` payload (issue 62's own text flags the existing
  `by_league`-absence signal as too weak on its own).
- Hermetic fixture tests for both, plus a required pre-close live run
  against this machine's real credential state.

### Out of Scope

- Any exit-code change to `main()`/`_run_teams()` — see Design
  Rationale for why this sprint resolves the issue's open question as
  logging-only.
- `partner_scrape.pipeline.run()` (the Opportunities pipeline) and
  `config.get_leaguesync_api_key()` — issue 62 is scoped to
  `teams/pipeline.py` only; the Opportunities pipeline already has its
  own, structurally separate `zero_yield`/`cliff` mechanism
  (`observability/yield_report.py`), unaffected by this sprint.
  Extending credential-specific detection to `leaguesync` is a
  candidate for a future issue, not this one.
- `ROBOTEVENTS_KEY` provisioning itself (sprint 016 already flagged
  this as a pending operator step) — this sprint is about the *signal*
  when a key is missing, not about acquiring the key.
- Any change to `_check_sunset_seasons()` — it stays an independent
  pre-flight advisory, untouched.

## Test Strategy

Hermetic and fixture-driven throughout, matching this project's
established `tests/teams/test_pipeline.py` convention — no real
network/API calls. The existing `TestTbaFailureIsolation`/
`TestRobotEventsFailureIsolation` classes already exercise a
`TBA_KEY`-missing case, a TBA-401 case, a `ROBOTEVENTS_KEY`-missing
case, and a RobotEvents-401 case end-to-end against the real committed
registry; ticket 001 extends those same four scenarios with
`caplog`-based assertions for the new aggregate warning rather than
inventing a parallel fixture set. A companion, explicitly
non-credential case (a source that completes with a genuine empty
result, and a source whose fetch raises a plain `RuntimeError` unrelated
to credentials — `test_unrecognized_adapter_type_does_not_raise_and_
yields_zero_teams`'s existing "erroring source" fixture is the natural
base for the latter) proves the new alert does not fire for either.
Ticket 002's `meta.credential_failures` assertions extend
`tests/teams/test_export.py` with both a credential-failure case and a
clean-run case (`[]`).

A required pre-close live run (`uv run partner-scrape teams`, or
equivalent, against this machine's real `.env`) is recorded as
supplementary evidence per this project's sprints 020-022 convention —
not a substitute for the fixture tests, confirmation that the real
current credential state produces the expected real output.

## Architecture

**Sizing: Substantial — by module count, not by new composition.**
This sprint touches five existing modules (`config.py`, `tba.py`,
`robotevents.py`, `teams/pipeline.py`, `teams/export.py`), which alone
crosses the "3+ modules touched" substantial-tier signal. It does
**not** introduce a new cross-module dependency, a dependency-direction
change, or a new subsystem — every touched module already imports (or
is imported by) every other module this sprint changes; the change
only adds a new exception subtype flowing through those pre-existing
edges and one new field in an already-existing payload. This is the
same shape sprint 020 (also substantial-by-module-count, also no new
composition between modules) documented, and the same conclusion
applies: **no component or dependency diagram is included** — five
already-connected modules exchanging a slightly richer signal is not
clarified by a picture a written module list doesn't already say, and
no data model (`Team`) or entity relationship changes at all, so no
ERD either.

### Architecture Overview

**What Changed**

- **`config.py`**: adds `CredentialError(RuntimeError)`, a marker
  subclass with no new behavior of its own. `get_tba_api_key()`/
  `get_robotevents_api_key()`'s existing "env var unset" raise changes
  class (`RuntimeError` → `CredentialError`) — message text unchanged.
- **`teams/sources/tba.py`**: `TBASource.discover()`'s `response.status
  == 401` branch raises `config.CredentialError` instead of
  `RuntimeError` — message text unchanged. Every other raise in
  `discover()` (non-200 non-401, unparseable JSON, invalid
  `max_team_page`) stays plain `RuntimeError`: those are probe/protocol
  failures, not credential failures, and conflating them would
  misdirect an operator to check a key that was never the problem.
- **`teams/sources/robotevents.py`**: `VexTeamSource.discover()`'s 401
  branch gets the identical treatment, for the identical reason
  (mirrors `tba.py`'s exact isolation contract, per that module's own
  docstring precedent).
- **`teams/pipeline.py`**: `run_teams()`'s per-source loop gains a
  `except CredentialError` branch (checked before the existing
  `except Exception`), a small private `_SOURCE_LEAGUES: dict[str,
  str]` lookup (`adapter_type -> League`, the same "private lookup
  local to the one caller that needs it" shape `_TEAM_SOURCES` already
  established — not a second public registry), and, once the loop
  finishes, exactly one aggregate `logger.warning` if any credential
  failures were collected — matching `_check_sunset_seasons()`'s
  existing "never more than one log call regardless of how many are
  affected" convention. `_check_sunset_seasons()` itself is untouched.
- **`teams/export.py`**: `_build_meta()` gains a new
  `credential_failures: list[str]` parameter/key (sorted, unique league
  codes; `[]` on a clean run), threaded through `export_teams()`'s new
  optional `credential_failures` parameter (default `()`, so every
  existing caller — currently only `run_teams()` — keeps working
  unchanged). The module docstring's documented JSON contract example
  is updated to show the new key.

**Why**

`teams/pipeline.py`'s per-source isolation is correct for transient
failures but was, until now, structurally unable to tell a persistent,
operator-actionable credential problem apart from a one-off scrape
hiccup or a genuine empty result — all three looked identical (an
`Exception`, logged, run continues). A typed exception lets the loop
ask the one question that actually matters operationally ("is this
going to keep happening every run until someone fixes a key?") without
guessing at message text, and a second, louder log call plus an
explicit payload field gives that answer to both a human reading the
run log and a downstream consumer reading `teams.json` — the two
channels this issue's own two rediscoveries actually used.

**Impact on Existing Components**

- `TeamSource` (`sources/base.py`)'s `Protocol` shape is unchanged — no
  new method, no new required attribute. `CredentialError` is raised
  from inside existing `discover()`/`_auth_headers()` bodies, not a
  new contract point.
- Every existing `except RuntimeError`/`except Exception` catch
  anywhere in the codebase keeps working unmodified — `CredentialError`
  *is a* `RuntimeError`, so this is purely additive at the type level.
- `_build_meta()`'s existing keys (`generated`, `total`, `by_league`,
  `out_of_region`, `by_location_precision`) are unchanged; the new key
  is additive only.
- No change to `FTCScoutSource`/`StaticRosterSource` — neither reads a
  credential today, so neither can raise `CredentialError`.

**Migration Concerns**

- `teams.json`'s documented JSON contract gains one field
  (`meta.credential_failures`). Purely additive — no existing key
  removed or renamed, so any consumer reading known keys is unaffected;
  a consumer that enumerates `meta`'s key set strictly (none currently
  known in this repo or the sibling `stem-ecosystem` site as far as
  this sprint's own research found) would see one new key appear.
- No data migration: `Team`'s dataclass shape is unchanged, and
  `teams.json`'s three write targets (`export.py`'s own documented "one
  publish, three paths") all get the new key from the same single
  `_build_meta()` call, so all three stay in sync automatically.
- No deployment sequencing concern: this is a same-process, same-run
  change with no persisted state format to migrate (unlike
  `observability/yield_report.py`'s snapshot file, this sprint adds no
  new on-disk history).

### Design Rationale

**Decision: a dedicated `CredentialError(RuntimeError)` type, not
message-substring matching.**
*Context*: issue 62's own Proposed Fix section asserted "`tba.py`/
`robotevents.py` already raise a specific, identifiable exception
shape for the missing/invalid-key case... that specificity is
available to check for, not something that needs inventing." Verified
against the actual code, not assumed: both raise a bare `RuntimeError`
for *every* `discover()` failure mode — missing key (via
`_auth_headers()`), a 401, a non-200 status, unparseable JSON, and an
invalid page count all raise the identical exception class, message
text being the only thing that differs. The issue's framing overstated
what already exists; this sprint corrects that and builds the real
distinguishing mechanism.
*Alternatives considered*: (a) match on a message substring (e.g.
`"TBA_KEY"`/`"ROBOTEVENTS_KEY"` in `str(exc)`) inside `run_teams()`'s
except block; (b) leave it as-is and rely on the ERROR-level traceback
text alone (the status quo issue 62 is about).
*Why this choice*: message-substring matching is brittle — a future
wording change in `tba.py`/`robotevents.py`'s raise messages would
silently break detection with no test pointing at the real cause — and
is not meaningfully more hermetic-testable than a typed exception in
the spirit of this project's existing fixture conventions (issue 62's
own Verification section literally asks for "a `TeamSource`... raising
the credential-missing exception shape," implying a fixture constructs
one deliberately, not greps a string). A dedicated type is a five-line
change with zero new imports (every call site already imports
`config`) and gives `except CredentialError` an unambiguous,
type-checked catch — matching how `observability/yield_report.py`'s
own `SourceRecord.error: Exception | None` is already a typed field,
not a log-scraped string, for the analogous "did this source error"
question in the Opportunities pipeline.
*Consequences*: two raise-site class changes in `config.py`, one each
in `tba.py`/`robotevents.py` — all backward compatible (`CredentialError
is-a RuntimeError`). Every other `discover()` raise site deliberately
stays plain `RuntimeError`, so a non-credential probe failure (a bad
JSON body, an outage) is never misreported as a credential problem.

**Decision: logging + payload signal, no new exit code.**
*Context*: issue 62 explicitly leaves this open — "a silent degrade
that logs loudly but still exits 0 may be sufficient once the alert
itself is loud enough; don't assume exit-code plumbing is required."
*Alternatives considered*: a distinct non-zero exit code (e.g. `2`) for
"completed with a credential alert," separate from issue 47's exit-1
hard-failure path for `main()`'s `run` command.
*Why this choice*: (1) nothing in this project currently consumes the
`teams` subcommand's exit code programmatically — both of tonight's
rediscoveries came from a human/peer session reading live-verification
output and cross-checking published `teams.json`, not a script keyed
on `$?`; a new exit code with no present consumer adds a contract with
no immediate payoff. (2) `_run_teams()` (cli.py) is a structurally
separate handler from `main()`'s `run` command path (cli.py's own
module docstring: "never calls `run`/`pipeline.run()`") — inventing a
parallel exit-code contract for it, on top of issue 47's still-fresh
exit-1 contract for the *other* command, is a bigger design surface
than this issue asks for and risks confusing the two. (3) The
`meta.credential_failures` payload addition already gives the one
consumer that actually reads `teams.json` programmatically (the
stem-ecosystem cross-check, tonight's second rediscovery) a precise,
structured signal at the exact place it already looks.
*Consequences*: an operator or script polling only `$?` after a `teams`
run still sees 0 even when a league's credential is broken. Judged
acceptable: the loud log line and the always-present payload key
together close the "silently indistinguishable" gap this issue is
actually about, without speculatively building an exit-code contract
nothing yet consumes. Revisit if a future cron/CI wrapper starts
checking `teams` run exit codes specifically.

**Decision: extend `_build_meta()`'s payload with an explicit
`credential_failures` key.**
*Context*: `by_league` key-absence is, per issue 62's own text, "a
genuine passive signal" but "requires a consumer to already know to
check for a missing key in a dict that has no declared complete key
set" — exactly the manual reasoning tonight's second rediscovery had to
do.
*Alternatives considered*: logging-only, no payload change.
*Why this choice*: the log line is only visible to whoever captures
that specific run's log; `teams.json` is the artifact that actually
ships (three write targets). A consumer that already has to open
`teams.json` gets an unambiguous, always-present field instead of an
absence-based inference. Small, additive, non-breaking (one new key,
one new optional parameter with a safe empty-tuple default) —
proportionate to the gap, unlike exit-code plumbing.
*Consequences*: see Migration Concerns above.

**Decision: mirror `zero_yield`'s *shape*, do not import
`observability/`.**
*Context*: issue 62's Proposed Fix explicitly suggests "mirroring
`zero_yield`'s shape." Verified: `teams/` imports nothing from
`observability/` anywhere today (grepped the whole subsystem), and
`teams/DESIGN.md`'s own established precedent for this subsystem is "no
shared extraction code beyond protocol shape" — `SD_COUNTY_CITIES` is
literally duplicated between `tba.py`/`robotevents.py` rather than
imported (each module's own docstring says so explicitly), and
`teams/export.py`'s `_now_iso()` docstring goes out of its way to note
it matches `export/writer.py`'s format "even though `teams/` is a
structurally separate subsystem with no import of `export/writer.py`'s
implementation." `sponsor_llm.py`/`description_llm.py` follow the
identical pattern all sprint: teams-local implementations that echo an
existing convention's shape, never importing the other subsystem's
module.
*Alternatives considered*: import `observability.yield_report`'s
`SourceRecord`/alert-flag machinery directly into `teams/pipeline.py`.
*Why rejected*: (1) it would be the first import ever from `teams/`
into `observability/`, a new cross-subsystem edge this project has
deliberately avoided everywhere else in `teams/`'s history. (2) The
mechanism does not even transfer cleanly — verified `yield_report.py`'s
`zero_yield` is a *regression* detector requiring a persisted
previous-run snapshot (`SourceYield.zero_yield` only sets when
`previous_found is not None and previous_found > 0 and found == 0`
this run); `teams/pipeline.py` has no snapshot/history mechanism at
all, and a credential failure is knowable synchronously, within the
same run, from the exception itself — importing history-comparison
machinery to detect something that needs no history would be
over-engineering, not reuse. What is actually worth mirroring is the
*shape* (a purpose-built, run-scoped, loud-and-first alert
distinguishing error from legitimate-zero), not the literal
implementation.
*Consequences*: the new alert logic is a few lines added directly to
`run_teams()` plus the `CredentialError` type in `config.py` — no new
module, no new file, no new subsystem dependency edge.

**Decision: `_check_sunset_seasons()` stays untouched and independent
of the new alert.**
*Context*: sunset staleness and credential failure are different
conditions that can coincidentally co-occur for the same league.
*Why*: sunset is a pre-flight advisory about a declared config value
(`sunset_season`), evaluated once regardless of whether the source's
fetch later succeeds, fails, or fails specifically on credentials — it
already has its own independent single-`logger.warning`-per-run
contract and needs no new information from this sprint. Keeping the
two mechanisms structurally separate (two independent log calls, never
merged into one combined message) keeps each individually easy to
reason about; the new credential alert is a second instance of the
same "one `logger.warning` call per distinct concern" pattern
`_check_sunset_seasons()` already established, not a change to the
first.

### Migration Concerns

See Migration Concerns under Architecture Overview above.

## Use Cases

### SUC-027: Operator or downstream consumer learns a team source failed on a credential problem this run
Parent: UC-011 (Robot Teams acquisition)

- **Actor**: The pipeline operator (reading a run's log), and any
  downstream consumer of published `teams.json` (e.g. the
  stem-ecosystem site build/cross-check).
- **Preconditions**: A `teams` run is in progress; at least one active
  Team Registry source's `adapter_type` maps to a credential-reading
  `TeamSource` (`tba` or `robotevents`).
- **Main Flow** (log alert, ticket 001):
  1. `run_teams()` dispatches each active source in turn.
  2. A source's `discover()` (directly, or via `_auth_headers()`)
     raises `CredentialError` — the key is missing, or present but
     rejected with a 401.
  3. The per-source loop logs the existing per-source ERROR +
     traceback (unchanged from today) and records which league this
     source was responsible for, then continues with the remaining
     sources.
  4. Once every active source has been dispatched, `run_teams()` logs
     exactly one aggregate `logger.warning` naming every league that
     failed on a credential problem this run.
  5. The run completes and publishes `teams.json` with every other
     source's teams, exactly as it does today.
- **Alternate Flow** (payload signal, ticket 002):
  1. Continuing from Main Flow step 4, `run_teams()` passes the
     collected credential-failed league list into `export_teams()`.
  2. `_build_meta()` writes it into `teams.json`'s `meta` as
     `credential_failures` (sorted, unique league codes; `[]` when
     none failed this way).
  3. A downstream consumer reading `teams.json` checks this key
     directly, with no need to infer anything from `by_league`'s
     absence.
- **Postconditions**: The credential failure is visible in the run log
  (loud, aggregate, distinguishable from a per-source ERROR traceback
  alone) and in the published artifact (`meta.credential_failures`),
  without changing the run's completion behavior or exit code.
- **Error Flows**:
  - A source that completes with a genuine empty result (no exception)
    never enters this flow at all — no alert, no `meta.credential_failures`
    entry; the existing passive `by_league`-absence-or-zero-count
    signal is the only (and, per this sprint's Design Rationale,
    sufficient) signal for that case.
  - A source whose `discover()`/`fetch()`/`extract()` raises a
    non-`CredentialError` exception (a transient network/probe/parse
    failure) is logged and isolated exactly as it is today — no new
    alert, no `meta.credential_failures` entry — since per-source
    isolation is already the correct response to a transient failure.
- **Acceptance Criteria**:
  - [ ] A fixture source raising `CredentialError` (missing-key case)
        produces the aggregate warning, naming the correct league.
  - [ ] A fixture source raising `CredentialError` (401-with-key-present
        case) produces the aggregate warning, naming the correct league.
  - [ ] A fixture source completing with zero teams (no exception) does
        not produce the aggregate warning.
  - [ ] A fixture source raising a non-credential `RuntimeError` does
        not produce the aggregate warning.
  - [ ] `teams.json`'s `meta.credential_failures` lists the correct
        league(s) on a credential-failure run and is `[]` on a clean
        run, in both `dry_run=True` and real-write paths.
  - [ ] A required pre-close live run against this machine's real
        credential state is recorded with real numbers.

## GitHub Issues

None filed for this sprint's tickets directly — tracked via CLASI
issue `62-missing-source-credential-degrades-silently-past-cli-exit-code.md`.

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [x] Sprint planning document is complete (sprint.md, including its
      Architecture and Use Cases sections)
- [ ] Architecture review passed (or skipped, for changes with no
      architectural impact)
- [ ] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Depends On |
|---|-------|------------|
| 001 | Add `CredentialError` and an aggregate credential-failure alert to `run_teams()` | — |
| 002 | Add `credential_failures` to `teams.json`'s `meta` payload | 001 |

Tickets execute serially in the order listed.
