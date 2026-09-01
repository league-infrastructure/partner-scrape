---
status: done
sprint: '023'
tickets:
- 023-001
- 023-002
---

# A missing source credential (TBA_KEY, ROBOTEVENTS_KEY) degrades past exit code 0 with no active alert

## Description

Rediscovered independently twice in one night (2026-08-31): sprint 021's
live-verification runs and the stem-ecosystem peer's cross-check of
published `teams.json` both had to reason their way to "an entire
league was never attempted" from indirect evidence, because nothing in
the pipeline actively surfaces it. When `TBA_KEY` (FRC, via
`teams/sources/tba.py`) or `ROBOTEVENTS_KEY` (VEX, via
`teams/sources/robotevents.py`) is missing, `teams/pipeline.py`'s
per-source isolation (`run_teams()`'s `try/except Exception: ...
continue` loop, ticket 011-003's design) does exactly what it was built
to do: log the failure (`logger.exception`, so it IS in the log, at
ERROR level with a traceback) and let the rest of the run complete.
`main()` still returns exit code 0. Nothing else in the CLI output, or
in `teams.json` itself, actively flags "an entire registered source
produced zero teams this run" as distinct from "zero teams because none
exist" or "zero teams because the source is legitimately between
seasons" (`_check_sunset_seasons()` already models that last case on
purpose).

`teams/export.py`'s `_build_meta()` docstring already anticipated part
of this: `by_league` is built from insertion order, not pre-seeded from
`model.League`'s full value set, specifically so "a `TBA_KEY`-missing
run's `meta` has no `"FRC"` key in `by_league` at all" is a real,
inspectable signal in the published data. That's a genuine passive
signal — but it requires a consumer to already know to check for a
missing key in a dict that has no declared complete key set, which is a
much weaker guarantee than an active alert. It's exactly the class of
problem `issue 48`'s roster-validation work (sprint 022, in progress)
is about for the partner roster — the same "logged once, then silently
treated as success" shape, just for source credentials instead of
roster rows.

## Cause

Per-source error isolation (`run_teams()`, and `pipeline.run()`'s own
equivalent `_run_one_source` contract) is the right design for
transient, source-specific failures — a bad HTML page, a flaky network
blip, one org's site being briefly down. It's the wrong design, applied
without a second layer, for a *structural* condition like a missing
credential: that failure mode is not transient, will recur on every
single run until an operator acts, and currently produces the exact
same "logged and continued" signature as a one-off scrape hiccup. The
main Opportunity pipeline already has a purpose-built escalation layer
for a related problem — `observability/yield_report.py`'s
`zero_yield`/`cliff` alerts, rendered first in the human-readable report
(`observability/render.py`) specifically so a real regression isn't
buried in per-source detail lines. `teams/pipeline.py` has no
equivalent.

## Proposed fix

Not fully specified here — left for whichever sprint picks this up to
design against the current code, not guessed at in advance. Directions
worth considering:

- A `teams`-pipeline-scoped alert, mirroring `zero_yield`'s shape:
  after the per-source loop in `run_teams()` completes, compare the set
  of sources that raised (or otherwise produced zero teams) against
  `model.League`'s full expected value set, and log one aggregate
  `logger.warning`/`ALERT`-style line naming every league with zero
  teams this run — loud, first, not buried.
- Distinguish, in that alert (and possibly in `_build_meta()`'s own
  payload — an explicit key naming which leagues produced zero teams
  this run, not just their absence from `by_league`), a *credential*
  failure (`TBA_KEY`/`ROBOTEVENTS_KEY` missing or a 401) from a
  *legitimate* zero (an in-season league that genuinely lists no teams,
  or `_check_sunset_seasons()`'s deliberate off-season skip) — these
  need different operator responses and currently look identical.
  `tba.py`/`robotevents.py` already raise a specific, identifiable
  exception shape for the missing/invalid-key case (see their own
  module docstrings) — that specificity is available to check for, not
  something that needs inventing.
- Whether this should also affect `main()`'s exit code (a distinct,
  non-zero code for "completed with a source-level alert," separate
  from the hard-failure exit-1 path issue 47 just restored coverage
  for) is an open design question, not a foregone conclusion — a silent
  degrade that logs loudly but still exits 0 may be sufficient once the
  alert itself is loud enough; don't assume exit-code plumbing is
  required without weighing it against the simpler logging-only fix.

## Verification

A fixture test: a `TeamSource` registered for a league, its `fetch`
raising the credential-missing exception shape `tba.py`/
`robotevents.py` already define, asserting the new alert fires and
names that league — and a companion test proving a genuine
zero-teams-this-league case (not a credential failure) either doesn't
fire the same alert, or fires a distinguishably different one, per
whatever the implementing sprint decides. A live run's actual output
(this machine's real, current credential state) recorded as
supplementary evidence, matching this project's established
live-verification convention — not a substitute for the fixture tests.

## Related

Sprint 011 ticket 003 (the per-source isolation this issue's cause
section describes); sprint 016 (RobotEvents/VEX adapter added;
`ROBOTEVENTS_KEY` provisioning flagged as a still-pending operator step
there, unrelated to this issue's own fix — this issue is about the
*signal* when a key is missing, not about provisioning the key itself);
sprint 004 (`YieldReporter`'s zero-yield/cliff alert pattern, the
closest existing precedent to mirror); issue 48 (sprint 022, in
progress — the same silent-degradation shape, for roster data instead
of source credentials); tonight's two independent rediscoveries
(sprint 021's own live-verification undercount, and the stem-ecosystem
peer's cross-check of published `teams.json`'s per-league
`website_status` breakdown).
