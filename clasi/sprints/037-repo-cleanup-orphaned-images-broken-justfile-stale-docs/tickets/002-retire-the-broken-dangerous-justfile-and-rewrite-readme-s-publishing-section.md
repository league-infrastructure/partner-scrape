---
id: '002'
title: Retire the broken/dangerous justfile and rewrite README's publishing section
status: open
use-cases: []
depends-on: []
github-issue: ''
issue: 48-repo-cleanup-stale-cruft.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Retire the broken/dangerous justfile and rewrite README's publishing section

## Description

The repo-root `justfile` is both broken and dangerous:

- `dev`, `build`, `preview` all `cd site/`, which has not existed in
  this repo since sprint 019 moved the site to `stem-ecosystem`.
- **`pub` runs `git push origin master`** — this repo is under a
  deliberate push freeze — and then dispatches `pages.yml`, which was
  disabled 2026-09-03 when the stakeholder turned off website
  publishing from this repo. `pub` must not survive in any form that
  pushes `master` or dispatches a Pages deploy; a commented-out or
  guarded version is still a landmine for a future `just pub`
  invocation, so it must be removed outright, not neutered.

README's beta-preview section (currently describing the GitHub Pages
workflow and telling the reader to clone `stem-ecosystem` into `site/`
for `just dev`/`just build`) must be rewritten to match reality —
publishing is disabled (workflow `disabled_manually`; the site stays
live serving its last deploy) — and must stay consistent with whatever
this ticket does to the `justfile`. These two changes ship together
specifically so they can't drift out of sync with each other.

## Acceptance Criteria

- [ ] No `justfile` recipe, if a `justfile` still exists at all, runs
      `git push` against `master` or dispatches/watches `pages.yml`
      (`gh workflow run pages.yml`, `gh run watch`, etc.) in any form —
      not commented out, not guarded, not renamed. `pub` is removed
      entirely.
- [ ] `dev`, `build`, `preview` are either removed (the honest default,
      per issue 48, now that this repo does not publish the site) or
      rewritten so a reader cannot run them expecting a working `site/`
      without understanding they need a separate `stem-ecosystem`
      clone — prefer removal unless there's a concrete reason raised
      during implementation to keep a documented manual-clone recipe.
- [ ] If every recipe is removed, the `justfile` itself is deleted
      rather than left as an empty shell — record this choice (and
      which alternative was rejected) either in the ticket or issue 48.
- [ ] `just --list` (if a `justfile` remains) runs clean with no recipe
      pointing at a path that does not exist.
- [ ] README's beta-preview section is rewritten to state plainly that
      GitHub Pages publishing from this repo is disabled
      (`disabled_manually`, 2026-09-03) and that the live site continues
      serving its last deploy; it no longer instructs the reader to
      clone `stem-ecosystem` into `site/` for a local `just dev`/`just
      build` workflow that no longer exists in this repo.
- [ ] README's reference to the `justfile` for local-dev details (if
      any survives) matches what the `justfile` actually contains after
      this ticket — no dangling "see the justfile for details" pointing
      at a recipe that no longer exists.
- [ ] `.github/workflows/pages.yml` itself is untouched (already
      disabled; out of scope per sprint.md) — this ticket only removes
      the repo-local recipe that dispatches it.
- [ ] Full test suite still green; this ticket has no test surface of
      its own (docs/config only), so verification is `just --list` (if
      applicable) plus a read-through of the rewritten README section.

## Implementation Plan

**Approach**: Read the current `justfile` and README beta-preview
section together, then decide in one pass whether to delete the
`justfile` outright or keep a minimal stub — the sprint's Design
Rationale already settled on removing `pub` outright; extend that same
reasoning to `dev`/`build`/`preview` (issue 48 recommends removal as
the "honest default now that this repo does not publish the site").
Rewrite the README section to describe the actual current state:
publishing disabled, site serving its last deploy, no supported local
`just dev` workflow in this repo. Keep the two changes in the same
commit/ticket so they can't drift.

**Files to modify**:
- `justfile` — remove `pub` outright; remove or rewrite `dev`/`build`/
  `preview` and the `site :=`/`pages_url :=` variables and header
  comment accordingly. If nothing useful remains, delete the file.
- `README.md` — rewrite the "Beta preview" section (currently around
  the GitHub Pages / `stem-ecosystem` clone instructions) to match
  reality; keep the surrounding sections (Test, the closing note about
  the retired Scrapy prototype) intact.

**Testing plan**: No automated tests apply (docs/config only). Manual
verification: `just --list` runs clean with no recipe referencing a
nonexistent path (skip if the file is deleted); grep the repo for any
other reference to `just pub`, `just dev`, `just build`, or `just
preview` that would now be stale (e.g. CI docs, other README sections)
and update or remove those too.

**Documentation updates**: README.md's beta-preview section (primary
change). Note in issue 48 (items 2 and 3) what was actually done
(deleted vs. trimmed justfile) and why.

## Testing

- **Existing tests to run**: `uv run pytest` (full suite; no regression
  expected — this ticket touches no test-covered code).
- **New tests to write**: none — docs/config only.
- **Verification command**: `uv run pytest`, plus manual `just --list`
  and a grep for stale `just pub`/`just dev`/`just build`/`just preview`
  references elsewhere in the repo.
