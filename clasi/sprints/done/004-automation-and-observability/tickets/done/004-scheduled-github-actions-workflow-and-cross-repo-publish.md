---
id: '004'
title: Scheduled GitHub Actions workflow and cross-repo publish
status: done
use-cases:
- SUC-017
depends-on:
- '003'
github-issue: ''
issue: 07-self-updating-scheduled-loop.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Scheduled GitHub Actions workflow and cross-repo publish

## Description

New `.github/workflows/scheduled-run.yml` in this repo (`partner-scrape`),
implementing issue 07's automation-home decision (GitHub Actions, over
the League's Docker host — see sprint.md's Design Rationale) and cross-
repo publish, on top of ticket 003's CLI (which by now prints a yield
report and writes `yield-history.json` by default):

1. Triggers: `on: schedule` (weekly cron) and `on: workflow_dispatch`
   (manual, for activation/testing).
2. Checkout: this repo (default path) and, via `actions/checkout` with
   `token: ${{ secrets.SITE_REPO_TOKEN }}`, `stem-ecosystem` into a named
   path under `$GITHUB_WORKSPACE` — passed explicitly to the CLI as
   `--site-dir`, not relied on via the CLI's `../stem-ecosystem`/
   `$SITE_DIR` default (CI's checkout layout isn't a sibling directory).
3. Install this project's dependencies (no `headless` extra needed —
   verified: no current registry source uses `fetch_strategy =
   "headless"`).
4. Set `SCRAPE_CACHE_DIR` to a runner-local path (e.g.
   `${{ runner.temp }}/scrape-cache`) — **not**
   `config/prod/public.env`'s value, which is a local Mac path that does
   not exist on a hosted runner.
5. An `actions/cache` step restoring/saving only
   `${SCRAPE_CACHE_DIR}/enrichment_cache/` (a stable cache key, not
   content-derived) across scheduled runs — this is the fix this
   sprint's own architecture self-review caught: without it, every
   scheduled run would silently re-pay full LLM enrichment cost for
   every event, not just new/changed ones, because
   `EnrichmentCache` also persists under `SCRAPE_CACHE_DIR`. The raw-
   HTML mirror portion of `SCRAPE_CACHE_DIR` is deliberately **not**
   cached — a weekly refresh should re-fetch fresh content.
6. Inject `ANTHROPIC_API_KEY` and `SITE_REPO_TOKEN` from GitHub Actions
   secrets into the job environment (`${{ secrets.* }}` only — never a
   literal value in the file).
7. Run the `partner-scrape` CLI with explicit `--site-dir` (from step 2).
8. Append the CLI's printed yield report to `$GITHUB_STEP_SUMMARY`.
9. `git add`/`commit`/`push` the checked-out `stem-ecosystem` tree's
   changed files to `master` — skipped (no commit, no push) when
   `git diff --quiet` reports no changes, so an unchanged run never
   produces an empty commit or a spurious `deploy.yml` trigger.
   `stem-ecosystem`'s own `deploy.yml` is not modified — its existing
   `on: push: branches: ['master']` trigger already fires on this push.

Also write a short runbook (e.g. `docs/deploy/scheduled-run.md`)
documenting the operator activation steps — this ticket **produces** the
runbook and the workflow file; it does not perform the activation:

- Create a fine-grained GitHub PAT scoped to `stem-ecosystem` only, with
  `contents: write` permission (nothing broader).
- Add it to `config/prod/secrets.env` as `SITE_REPO_TOKEN`, then
  `dotconfig save` to re-encrypt.
- `dotconfig gh-push -d prod --actions --repo
  league-infrastructure/partner-scrape --dry-run` first, then without
  `--dry-run`, to push both `ANTHROPIC_API_KEY` and `SITE_REPO_TOKEN` to
  this repo's Actions secrets.
- Verify both secrets appear under this repo's Settings → Secrets and
  Variables → Actions.
- Trigger the workflow once manually via `workflow_dispatch` and confirm
  a real end-to-end run before trusting the weekly cron.
- Note PAT rotation: re-run the same `dotconfig save` + `gh-push` steps
  when GitHub expires the fine-grained PAT.

Per this sprint's constraints, no step of *implementing* this ticket
runs `dotconfig gh-push` for real, triggers the workflow, or pushes a
commit to `stem-ecosystem` — those are the runbook's documented operator
steps, performed after this sprint closes.

## Acceptance Criteria

- [x] `scheduled-run.yml` defines both a weekly `schedule` trigger and a
      `workflow_dispatch` trigger, and is YAML-valid.
- [x] No secret value appears anywhere in the workflow file — only
      `${{ secrets.ANTHROPIC_API_KEY }}` / `${{ secrets.SITE_REPO_TOKEN }}`
      references.
- [x] `SCRAPE_CACHE_DIR` is set to a runner-local path in the workflow,
      never inherited from `config/prod/public.env`.
- [x] An `actions/cache` step scopes to
      `${SCRAPE_CACHE_DIR}/enrichment_cache/` only — not the whole
      `SCRAPE_CACHE_DIR`.
- [x] `stem-ecosystem` is checked out with an explicit auth token and an
      explicit path passed to `--site-dir` — no reliance on CLI path
      defaults.
- [x] The commit/push step is a verified no-op when the run produces no
      change to the checked-out tree (documented, e.g. via
      `git diff --quiet ... || (commit && push)` or equivalent).
- [x] The rendered yield report is appended to `$GITHUB_STEP_SUMMARY`.
- [x] `docs/deploy/scheduled-run.md` (or equivalent) documents every
      operator activation step above, with no secret value included.
- [x] No secret was pushed, no commit made to `stem-ecosystem`, and the
      workflow was not triggered, in the course of implementing this
      ticket — confirmed in the ticket's own notes, not just implied.

## Implementation Notes

- `.github/workflows/scheduled-run.yml` (new): `on: schedule` (weekly,
  `0 13 * * 1`) + `on: workflow_dispatch: {}`. Checks out
  `partner-scrape` (default `GITHUB_TOKEN`, read-only) and, via
  `actions/checkout` with `token: ${{ secrets.SITE_REPO_TOKEN }}`,
  `stem-ecosystem` into an explicit `path: stem-ecosystem` sibling under
  `$GITHUB_WORKSPACE` (not a bare-default checkout). Installs deps with
  `astral-sh/setup-uv` + `uv sync --locked` (no `headless` extra, per
  sprint.md's verified "no active source uses fetch_strategy=headless").
  `SCRAPE_CACHE_DIR` is set via `$GITHUB_ENV` to
  `${{ runner.temp }}/scrape-cache` (a step-level, not top-level, `env:`
  assignment — the `runner` context is not available in workflow- or
  job-level `env:` blocks per GitHub's own context-availability rules,
  only in step-level `env`/`with`/`run`). The CLI runs with an explicit
  `--site-dir "${{ github.workspace }}/stem-ecosystem"` — no reliance on
  `../stem-ecosystem`/`$SITE_DIR` defaults, which don't hold under CI's
  checkout layout.
- **Cache mechanics deviation, documented, not silent**: the ticket text
  says "a stable cache key, not content-derived." A literal single fixed
  key (e.g. `actions/cache@v4` with `key: enrichment-cache` unchanged
  every run) has a real correctness gap: `actions/cache` only *saves* on
  a cache-key miss — a fully static key restores once, then never saves
  again, so every enrichment result added after the very first cached
  run would silently stop being cached, one release short of the exact
  "silently re-pay full LLM cost" failure mode this sprint's own
  self-review already caught once for the coarser
  whole-`SCRAPE_CACHE_DIR` case. Implemented instead as the standard
  `actions/cache/restore` + `actions/cache/save` split: restore via
  `restore-keys: enrichment-cache-` (prefix match, gets the most recent
  prior run's cache), save via a run-ID-suffixed key
  (`enrichment-cache-${{ github.run_id }}`) so every run's newly-cached
  entries are always persisted forward. The key is still not
  content-derived (a run ID is an identity, not a content hash) — same
  "stable, not content-derived" intent the ticket asks for, implemented
  so it actually keeps working past the second run. Both steps scope
  only to `${SCRAPE_CACHE_DIR}/enrichment_cache/`, never the raw-HTML
  mirror portion.
- The CLI's full stdout (the `"partner-scrape: wrote N
  opportunities..."` line plus the rendered yield report — no `-v`
  logging noise, since `-v` isn't passed) is `tee`'d to a temp file and
  appended, fenced, to `$GITHUB_STEP_SUMMARY` in an `if: always()` step,
  so a failed run's partial/absent report doesn't hide the failure.
- Publish step: `git add -A` (required, not `git diff --quiet` alone —
  an untracked brand-new file, e.g. the very first `yield-history.json`,
  is invisible to a plain unstaged diff) then
  `git diff --cached --quiet || (commit && push origin HEAD:master)`,
  exactly the no-op-on-unchanged behavior the AC asks for.
- `concurrency: { group: scheduled-run, cancel-in-progress: false }`
  added (small, in-scope CI-config addition) so a manual
  `workflow_dispatch` and the weekly cron can never race into two
  concurrent cross-repo publishes.
- `docs/deploy/scheduled-run.md` (new): full operator runbook — merge to
  `master` first (GitHub only evaluates `schedule` triggers on the
  default branch, noted explicitly since it's easy to miss), create the
  fine-grained PAT (`stem-ecosystem` only, `contents: write` only),
  `dotconfig save` + `dotconfig gh-push -d prod --actions --repo
  league-infrastructure/partner-scrape` (`--dry-run` first, exact
  commands from sprint.md), verify both secret names via GitHub UI or
  `gh api .../actions/secrets`, trigger one real `workflow_dispatch` run
  before trusting the cron, and PAT-rotation notes. No secret value
  appears in the runbook.
- **Validation performed**: `python3 -c "import yaml;
  yaml.safe_load(open('.github/workflows/scheduled-run.yml'))"` parses
  cleanly (the top-level key printing as the Python boolean `True`
  instead of the string `'on'` is `PyYAML`'s well-known YAML-1.1
  bare-word boolean coercion of `on:` — a parser quirk, not a workflow
  defect; GitHub's own Actions parser reads it correctly as the literal
  key `on`). `actionlint` (available in this environment, schema-aware
  for GitHub Actions specifically) was also run against the file:
  **zero findings, exit code 0**.
- **No secret/deploy confirmation**: no step of implementing this ticket
  ran `dotconfig gh-push`, `dotconfig save`, or any command that could
  transmit a secret value; no PAT was created; no `git push` was
  executed against `stem-ecosystem` (or anywhere outside this repo's own
  ticket-file/workflow-file commit below); the workflow was not
  triggered (no `gh workflow run`, no manual dispatch via the GitHub
  UI). Verified via `grep -n "secrets\." .github/workflows/scheduled-run.yml`
  (only the two expected `${{ secrets.* }}` references) and a
  secret-literal-pattern grep across both new files (no matches).
- No Python files were touched — `uv run pytest` run as the ticket's own
  specified sanity check: **431 passed**, same count as the pre-ticket
  baseline (also 431), confirming this ticket introduced no accidental
  Python regressions.

## Testing

- **Existing tests to run**: none touched (no `.py` files change) —
  run `uv run pytest` once as a sanity check that this ticket introduced
  no accidental Python changes.
- **New tests to write**: none required for the workflow YAML itself
  (config, not code, per sprint.md's Test Strategy) — if a YAML/GitHub-
  Actions linter (e.g. `actionlint`) is available in this environment,
  run it against `scheduled-run.yml` and note the result in this
  ticket; otherwise validate with a plain YAML parse
  (`python -c "import yaml; yaml.safe_load(open('.github/workflows/scheduled-run.yml'))"`).
- **Verification command**: `uv run pytest`
