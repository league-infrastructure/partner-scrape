---
id: '002'
title: 'Ops reactivation: Playwright install, headless dispatch fix, and weekly cron'
status: in-progress
use-cases:
- SUC-004
- SUC-005
depends-on: []
github-issue: ''
issue: 23-ops-playwright-cron-and-browser-fetch.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Ops reactivation: Playwright install, headless dispatch fix, and weekly cron

## Description

Turn on operational machinery that already exists but is switched off:
install the optional `playwright` dependency where it's needed (dev,
CI, the scheduled workflow), re-enable the weekly cron in
`.github/workflows/scheduled-run.yml`, and flag known JS-rendered/
403-blocked sources `acquisition_policy.fetch_strategy = "headless"`.

This ticket ALSO fixes a real concurrency gap in `fetch/headless.py`'s
`PlaywrightFetcher`, found during this sprint's architecture
self-review, not the original issue text: `PlaywrightFetcher` shares a
single browser page across every headless-flagged source with no
synchronization, and Playwright's own sync API additionally expects a
consistent driving thread. This has been safe only because exactly one
source (`sandiego-air-space.toml`) has ever used `fetch_strategy =
"headless"` — flagging ~10 more (this ticket's own point) makes
concurrent, multi-threaded headless dispatch a near-certainty under
`pipeline.py`'s existing 8-worker source-level concurrency, which is a
correctness hazard (silently misattributed content, or a Playwright
thread-affinity error), not just a crash risk. **This fix must land and
be verified before flagging more than one or two sources headless** —
see `sprint.md`'s Architecture section and `design/fetch-DESIGN.md` /
`design/DESIGN.md` for the full design and rationale.

The PAT provisioning step documented in `docs/deploy/
scheduled-run.md` (sprint 004) remains operator-only and out of this
ticket's scope. This ticket does everything else code-side.

## Acceptance Criteria

- [ ] `uv sync --extra headless` succeeds in dev and CI (workflow's
      dependency-install step updated).
- [ ] `pipeline.run()` dispatches every `headless`-strategy source
      through a new, dedicated single-worker `ThreadPoolExecutor`,
      separate from the main (default 8-worker) executor used for
      `static`-strategy sources. Static-strategy source concurrency is
      unaffected.
- [ ] `PlaywrightFetcher.get()` holds an instance-owned
      `threading.Lock` for its duration (page construction through
      `content()`) as defense in depth.
- [ ] `PlaywrightNotInstalledError`'s existing behavior (actionable
      message when `playwright` is missing) is unchanged.
- [ ] Fixture test: two threads calling `.get()` on one
      `PlaywrightFetcher` instance concurrently never interleave —
      proven by an instrumented fixture `page_factory` (e.g. an
      artificial delay plus a call-order/ownership assertion), not
      merely by the lock's presence.
- [ ] Fixture test: `pipeline.run()` with 2+ active sources flagged
      `headless` dispatches every one of them via the same worker
      thread (asserted via `threading.current_thread()` recorded
      inside a fixture `page_factory`).
- [ ] `fetch/headless.py`'s existing fixture tests keep passing whether
      or not `playwright` is actually importable in the test
      environment (deferred-import discipline unchanged).
- [ ] `.github/workflows/scheduled-run.yml`'s `schedule:` cron trigger
      is uncommented.
- [ ] `docs/deploy/scheduled-run.md` updated: the code-side prerequisite
      (merging the uncommented workflow) is now satisfied by this
      sprint; only the PAT provisioning steps remain for an operator.
- [ ] The 9 Wix partner sources, plus other known-blocked sources
      already registered (aquarium.ucsd.edu, Gateway Galaxy webstores,
      ActiveNet REST, zoo.sandiegozoo.org kids-programs, Chula Vista/
      National City library sites, North County city rec sites,
      Mathnasium, AoPS — whichever are already registered TOMLs), get
      `acquisition_policy.fetch_strategy = "headless"`.
- [ ] Live validation (pre-close, not a committed test): `uv sync
      --extra headless` succeeds; a real fetch against one
      newly-flagged Wix source returns non-empty rendered HTML; a live
      run with 2+ headless sources active completes with no
      cross-attributed content and no Playwright/thread-related error;
      a `workflow_dispatch` run of the updated workflow completes and
      the job summary shows a per-source yield report.
- [ ] Full test suite stays green.

## Testing

- **Existing tests to run**: full suite (`uv run pytest`), particularly
  `tests/fetch/test_headless.py` (or its current equivalent) and any
  `pipeline.py` dispatch tests — both must keep passing with
  `playwright` uninstalled in the default test environment.
- **New tests to write**: the two concurrency fixture tests in
  Acceptance Criteria above. Both use fixture `page_factory`/`Fetcher`
  doubles — no real browser, no network, in the committed suite.
- **Verification command**: `uv run pytest`, plus the required live
  validation steps listed above (not pytest — run manually/via the
  actual CLI and `gh workflow run`, and record the outcome in this
  ticket or the sprint's closing notes before it moves to done).

## Implementation Plan

**Approach**: Three independent pieces — dependency installation, a
concurrency-safety fix, and cron activation — landed together because
the concurrency fix is a hard prerequisite for the dependency/data
changes to be safe, and the cron change is low-risk and naturally
bundled with "turn the ops machinery on."

**Files to modify**:
- `.github/workflows/scheduled-run.yml` — uncomment `schedule:`; add
  `--extra headless` to the `uv sync` step.
- `docs/deploy/scheduled-run.md` — update step 1's framing.
- `partner_scrape/pipeline.py` — add a second, single-worker
  `ThreadPoolExecutor` (or equivalent single-worker dispatch
  mechanism) for `headless`-strategy sources; route `_run_one_source`
  calls for those sources through it instead of the main executor.
- `partner_scrape/fetch/headless.py` — add `threading.Lock` to
  `PlaywrightFetcher`, held for the duration of `.get()`.
- `partner_scrape/registry/sources/*.toml` — `fetch_strategy =
  "headless"` on known-blocked, already-registered sources (see
  Acceptance Criteria's list; only flag sources that already exist as
  TOML files — registering a genuinely new source belongs to ticket
  004 or a future sprint, not this ticket).

**Testing plan**: see Testing above.

**Documentation updates**: This ticket implements
`design/fetch-DESIGN.md` and `design/DESIGN.md`'s (root overview)
sprint 014 sections, already written during planning. If
implementation reveals the planned design needs adjustment (e.g. the
dedicated-executor mechanism turns out to need a different shape),
update those overlay files in place and note the revision, per the
`architecture-authoring` skill's in-place revision convention.

**Sequencing note**: land and verify the concurrency fix (dedicated
executor + lock, both fixture-tested) *before* flagging more than one
or two sources headless in the same commit, so a failing concurrency
test is caught before it's masked by "only one source is flagged
anyway." The full flag-out to all known-blocked sources can follow
once the fix is proven.
