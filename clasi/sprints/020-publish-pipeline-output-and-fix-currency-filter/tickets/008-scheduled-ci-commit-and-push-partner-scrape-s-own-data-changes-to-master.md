---
id: 008
title: 'Scheduled CI: commit and push partner-scrape''s own data/ changes to master'
status: in-progress
use-cases:
- SUC-019
depends-on:
- '003'
- '004'
- '005'
- '006'
- '007'
github-issue: ''
issue: 60-publish-pipeline-output-in-well-known-data-directory.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Scheduled CI: commit and push partner-scrape's own data/ changes to master

## Description

Completes issue 60's "well-known, COMMITTED home" goal for the
dominant real-world execution path: the weekly scheduled run
(`.github/workflows/scheduled-run.yml`). Tickets 002-007 make every
pipeline run locally write into `data/`; this ticket makes the
scheduled CI run also commit and push that change back to
partner-scrape's own `master`, so the weekly cron actually keeps `data/`
current in git without operator intervention (sprint.md Design
Rationale: "the weekly scheduled run, not an occasional local run, is
the dominant real-world producer of fresh pipeline output").

Two changes to `scheduled-run.yml`:

1. **Permission bump**: `permissions.contents` moves from `read` to
   `write`. This grants the default `GITHUB_TOKEN` write access to
   THIS repo only (the one the workflow runs in) — it is unrelated to,
   and does not widen, `SITE_REPO_TOKEN`'s existing cross-repo scope on
   `stem-ecosystem`.
2. **New step**: "Publish refreshed data to partner-scrape's own
   `data/`", added after the existing "Publish refreshed site data to
   stem-ecosystem" step (structurally independent of it — ordered
   after, never blocking or blocked by it). Mirrors that step's exact
   shape, working in the `partner-scrape` checkout instead of
   `stem-ecosystem`:
   ```yaml
   - name: Publish refreshed data to partner-scrape's own data/
     working-directory: partner-scrape
     run: |
       git config user.name "partner-scrape-bot"
       git config user.email "actions@users.noreply.github.com"
       git add data/
       if git diff --cached --quiet; then
         echo "No data changes this run -- nothing to publish."
       else
         git commit -m "chore: scheduled pipeline data refresh"
         git push origin HEAD:master
       fi
   ```
   Note `git add data/`, not `git add -A` — scoped to only the
   directory this sprint's changes actually write into, never picking
   up an unrelated stray file the runner happened to leave behind
   elsewhere in the checkout.

This ticket does not execute or push anything during this sprint's own
ticket execution — the step only takes effect the next time GitHub
Actions actually runs the workflow (`schedule` or `workflow_dispatch`),
which this session's push freeze does not govern (see sprint.md Test
Strategy).

## Acceptance Criteria

- [x] `scheduled-run.yml`'s `permissions.contents` is `write`.
- [x] A new step, ordered after "Publish refreshed site data to
      stem-ecosystem", runs `git add data/` (not `-A`) /
      `git diff --cached --quiet` skip-if-empty / commit / `push origin
      HEAD:master` in the `partner-scrape` working directory, using no
      token beyond the workflow's own default (no new secret
      referenced).
- [x] The existing "Verify SITE_REPO_TOKEN is configured" step and the
      "Publish refreshed site data to stem-ecosystem" step are
      unmodified — this ticket is purely additive to the file.
- [x] `docs/deploy/scheduled-run.md` is updated if it documents the
      permissions model or the publish steps (read it first to confirm
      whether an update is warranted).
- [x] No `git push --force` anywhere in the new step.
- [x] This ticket's own execution does not run `git push` against
      `origin` (workflow YAML changes only, verified by inspection/
      diff review — this is not something a hermetic test can assert).

## Implementation Plan

**Approach**: read the full current `.github/workflows/scheduled-run.yml`
first (already reviewed during sprint planning — see sprint.md
Architecture for the exact existing shape being extended) and
`docs/deploy/scheduled-run.md`, then apply the two changes described
above by direct analogy to the file's own existing
stem-ecosystem-publish step, changing only the working directory, the
`git add` scope, and dropping the cross-repo token/checkout entirely
(this repo's own checkout, done earlier in the job, is already
sufficient — no second `actions/checkout` needed).

**Files to modify**:
- `.github/workflows/scheduled-run.yml`
- `docs/deploy/scheduled-run.md` (if it needs updating — check first)

**Files to create**: none.

## Testing

- **Existing tests to run**: none apply (CI workflow YAML has no
  Python test coverage in this repo); run the full `uv run pytest -q`
  suite anyway to confirm this ticket's file changes (YAML + docs only)
  introduce no regression.
- **New tests to write**: none (not unit-testable). Verify by careful
  inspection against the existing, already-working stem-ecosystem
  step's shape, and by confirming the YAML parses
  (`python -c "import yaml, sys; yaml.safe_load(open('.github/workflows/scheduled-run.yml'))"`
  or equivalent) as a sanity check.
- **Verification command**: `uv run pytest -q`
