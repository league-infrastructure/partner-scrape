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

- [x] `uv sync --extra headless` succeeds in dev and CI (workflow's
      dependency-install step updated).
- [x] `pipeline.run()` dispatches every `headless`-strategy source
      through a new, dedicated single-worker `ThreadPoolExecutor`,
      separate from the main (default 8-worker) executor used for
      `static`-strategy sources. Static-strategy source concurrency is
      unaffected.
- [x] `PlaywrightFetcher.get()` holds an instance-owned
      `threading.Lock` for its duration (page construction through
      `content()`) as defense in depth.
- [x] `PlaywrightNotInstalledError`'s existing behavior (actionable
      message when `playwright` is missing) is unchanged.
- [x] Fixture test: two threads calling `.get()` on one
      `PlaywrightFetcher` instance concurrently never interleave —
      proven by an instrumented fixture `page_factory` (e.g. an
      artificial delay plus a call-order/ownership assertion), not
      merely by the lock's presence.
- [x] Fixture test: `pipeline.run()` with 2+ active sources flagged
      `headless` dispatches every one of them via the same worker
      thread (asserted via `threading.current_thread()` recorded
      inside a fixture `page_factory`).
- [x] `fetch/headless.py`'s existing fixture tests keep passing whether
      or not `playwright` is actually importable in the test
      environment (deferred-import discipline unchanged).
- [x] `.github/workflows/scheduled-run.yml`'s `schedule:` cron trigger
      is uncommented.
- [x] `docs/deploy/scheduled-run.md` updated: the code-side prerequisite
      (merging the uncommented workflow) is now satisfied by this
      sprint; only the PAT provisioning steps remain for an operator.
- [x] The 9 Wix partner sources, plus other known-blocked sources
      already registered (aquarium.ucsd.edu, Gateway Galaxy webstores,
      ActiveNet REST, zoo.sandiegozoo.org kids-programs, Chula Vista/
      National City library sites, North County city rec sites,
      Mathnasium, AoPS — whichever are already registered TOMLs), get
      `acquisition_policy.fetch_strategy = "headless"`. **Live-verified
      (2026-08-30), not assumed** — see "Live Validation Results"
      below for how the exact set was determined and why it is 9, not
      the originally-listed longer category set.
- [x] Live validation (pre-close, not a committed test): `uv sync
      --extra headless` succeeds; a real fetch against one
      newly-flagged Wix source returns non-empty rendered HTML; a live
      run with 2+ headless sources active completes with no
      cross-attributed content and no Playwright/thread-related error;
      a `workflow_dispatch` run of the updated workflow completes and
      the job summary shows a per-source yield report. **All 4 clauses
      resolved: clauses 1–3 done and re-confirmed after the
      `wait_until` fix below (team-lead ruling); clause 4
      (`workflow_dispatch` against the real repo) is code-complete and
      satisfied-by-documentation, deferred to an operator alongside
      the pre-existing PAT-provisioning step it depends on — see
      "Live Validation Results" below.**
- [x] Full test suite stays green.

## Live Validation Results (2026-08-30)

Performed from this session (real `playwright` + Chromium installed
locally; no network access to trigger GitHub Actions). Item 2 was
re-run a second time after the `wait_until` fix below, per team-lead
ruling on the first pass's findings.

1. **`uv sync --extra headless` succeeds** — confirmed locally
   (installed `playwright==1.61.0`, `greenlet`, `pyee`; `uv.lock`
   unchanged, already covered the extra). `uv run playwright install
   chromium` also run locally so the browser binary is present, not
   just the package.
2. **A real fetch against a newly-flagged Wix source returns non-empty
   rendered HTML — confirmed, after a same-ticket fix.** Identifying
   the "9 Wix partner sources" required live platform-fingerprinting
   (issue 23's own text names categories, not TOML files or a stable
   list): probed all 86 currently-registered `generic_html`/
   `listing_html` sources' `site_url`s for a `<meta name="generator"
   content="Wix.com Website Builder"/>` tag / `static.wixstatic.com`
   asset references. Exactly 8 matched — `climate-science-alliance`,
   `escondido-creek-conservancy`, `gsdsef`, `lajollalibrary`, `sdrvc`,
   `techadventurecamp`, `titanbot`, `xplorstem` — plus
   `sandiego-cv-aopsacademy` (AoPS, confirmed separately: a real fetch
   of its rendered page returns ~540KB of markup but under 500
   characters of real visible text, all nav/footer, no program content
   — a client-rendered JS shell, matching issue 23's "AoPS" bullet).
   That is 9 sources total, all now flagged headless. (`sandiego-gov`
   also matched a naive "wix" substring check but was a **false
   positive** on closer inspection — its CSP header lists
   `static.wixstatic.com` among ~80 allowed third-party asset hosts;
   the site itself is the city's own large Drupal CMS, not Wix — not
   flagged.) None of issue 23's other named categories (aquarium.ucsd.edu,
   Gateway Galaxy webstores, ActiveNet REST, zoo.sandiegozoo.org
   kids-programs, Chula Vista/National City library sites, North
   County city rec sites, Mathnasium) correspond to any
   currently-registered TOML — confirmed by a registry-wide grep —
   so, per this ticket's own scope note ("only flag sources that
   already exist as TOML files"), nothing to flag for them; they
   remain candidates for ticket 003 (triage) or a future registration
   ticket.

   **First pass** found fetching each of the 8 confirmed Wix sources'
   real homepage through `PlaywrightFetcher.get()` as originally
   shipped (15s `wait_until="networkidle"`) raised `TimeoutError` for
   all 8 — these Wix sites keep a persistent background connection
   open indefinitely (analytics/chat widget), so the network never
   truly idles. The *content* was never the problem: the same URLs
   fetched with `wait_until="load"` instead consistently returned
   full, real rendered text in under 1s each.

   **Team-lead ruling**: this is in scope for this ticket — a global
   default-strategy change is not the "per-source timeout/retry
   tuning" the ticket's own Design Rationale rejected (that rejection
   was about a *new*, per-source config surface, not correcting the
   one shared default every source already uses identically), and
   ticket 003's zero-yield triage depends on headless fetching
   actually working. **Fixed**: `PlaywrightFetcher.get()` now passes
   `wait_until="load"` instead of `"networkidle"`
   (`partner_scrape/fetch/headless.py`); `NETWORK_IDLE_TIMEOUT_MS`
   (the timeout bound) is unchanged, and no new config/override
   surface was added. `tests/test_fetch_headless.py`'s
   `test_applies_bounded_network_idle_wait` (renamed
   `test_applies_bounded_load_wait_strategy`) updated to assert
   `wait_until == "load"`.

   **Re-validated live, post-fix**, through the exact production
   construction path (`pipeline._build_default_headless_fetcher()` —
   the same `PoliteFetcher`-wrapped `PlaywrightFetcher` `pipeline.py`
   builds in production, robots.txt + cache included, no fixtures):
   `gsdsef.org`, `xplorstem.com`, and `sdrvc.org` (3 of the 8
   newly-flagged Wix sites) each returned HTTP 200 with 1MB+ of real
   rendered HTML (thousands of characters of real visible nav/program
   text — "HOME ABOUT Calendar and Schedule GSDSEF/ISEF Rules and
   Regulations..." for `gsdsef.org`, similarly for the other two — not
   an empty shell) through `PlaywrightFetcher.get()` unchanged from
   what ships. Also re-ran the same 3 sources through a real
   `pipeline.run(dry_run=True, max_source_workers=8)` against their
   actual registry TOMLs: all 3 dispatched cleanly on the same
   dedicated worker thread, no errors — though their *adapter-level*
   event count was still 0, because `discovery/sitemap.py` (a separate,
   pre-existing module outside this ticket's scope) found no
   parseable sitemap for any of the 3 and has no listing-page-crawl
   fallback for `generic_html` sources — a `discovery/`-layer gap,
   not a headless-fetch gap; squarely ticket 003's triage territory.
   `sandiego-cv-aopsacademy` (the one non-Wix flagged source) was
   already unaffected by the original strategy — its lighter JS shell
   reached `networkidle` inside 15s either way — and remains
   unaffected by this change (still 200, ~75K characters of real
   visible text).
3. **A live run with 2+ headless sources active completes with no
   cross-attributed content and no Playwright/thread-related error —
   confirmed.** A real `pipeline.run(dry_run=True, max_source_workers=8)`
   against a 2-source registry (`gsdsef`, `sandiego-cv-aopsacademy`,
   both real TOMLs, real `PlaywrightFetcher`, real Chromium — no
   fixtures) completed cleanly; both sources' calls landed on the same
   worker thread (`ThreadPoolExecutor-0_0` in the log) and neither
   produced the other's content. Separately, and more tellingly: two
   raw Python threads calling `.get()` on one shared `PlaywrightFetcher`
   for two different real Wix URLs (**deliberately bypassing
   `pipeline.py`'s dispatch**, i.e. recreating the pre-fix hazard on
   purpose) reproduced Playwright's own real thread-affinity failure —
   `"cannot switch to a different thread (which happens to have
   exited)"` — confirming the hazard `fetch/DESIGN.md`'s Constraints
   section predicts is real, not just theoretical, and confirming why
   the dispatch-level fix (not the lock alone) is load-bearing.
4. **A `workflow_dispatch` run of the updated workflow completes and
   the job summary shows a per-source yield report — satisfied by
   documentation, not performed; operator-only, same as PAT
   provisioning.** The code side is complete:
   `.github/workflows/scheduled-run.yml`'s `schedule:` trigger is
   uncommented, the dependency-install step installs `playwright`
   (`--extra headless`) and its Chromium binary, and the job summary
   step (pre-existing, unmodified) already appends the per-source
   yield report on every run, scheduled or dispatched. Actually
   triggering a `workflow_dispatch` run against the real repo requires
   `SITE_REPO_TOKEN` (the same fine-grained PAT
   `docs/deploy/scheduled-run.md` already reserves for an operator to
   provision, steps 2–4) — the "Verify SITE_REPO_TOKEN is configured"
   step fails fast otherwise, by design. This clause is therefore in
   the same category as PAT provisioning itself: code-complete,
   explicitly deferred to the operator's post-merge run (runbook step
   5), not a gap in this ticket's own deliverable.

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
