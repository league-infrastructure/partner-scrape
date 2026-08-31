---
id: '002'
title: Convert site/ to a build-time checkout of stem-ecosystem in pages.yml
status: open
use-cases: [SUC-001]
depends-on: ['001']
github-issue: ''
issue: consolidate-partner-scrape-s-beta-site-into-stem-ecosystem-production.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Convert site/ to a build-time checkout of stem-ecosystem in pages.yml

## Description

`partner-scrape/site/` is currently a second, independently
git-tracked copy of the same Astro site `stem-ecosystem` now owns
canonically (that repo's `src/` was promoted wholesale from this one
tonight, per the parallel `stem-ecosystem-8d` session). Untrack it here
and make `pages.yml`'s beta build pull the real source at build time
instead, so partner-scrape's beta preview always builds from
stem-ecosystem's actual current `master` — never a snapshot that can
silently drift the way it did for months (the problem this sprint
exists to fix).

This is CI/config work, not something `uv run pytest` exercises — its
own Acceptance Criteria include a real, observed workflow run as the
verification step. Do not mark this ticket done without that run
actually having succeeded and been checked.

**Depends on ticket 001** (soft sequencing, not a file conflict — the
two tickets touch disjoint files): removing `MIRROR_SITE_DIRS` first
avoids a moment where its default target (`site/`) is about to
disappear from git tracking while the mechanism is still wired up to
mirror into it.

**Steps:**

1. **Untrack `site/`.** `git rm -r --cached site/` (or equivalent) so
   the directory is no longer tracked content in `partner-scrape`'s own
   history; the working-tree files can go too, since a fresh checkout is
   what CI now expects. Add `site/` to `.gitignore` as a whole-directory
   ignore, superseding (and replacing) the existing narrower
   `site/node_modules/`, `site/dist/`, `site/.astro/` entries — the
   whole directory is now either CI-ephemeral or, for local dev, a
   developer's own gitignored manual clone (see step 4).
2. **Add the build-time checkout to `pages.yml`.** In the `build` job,
   add a second `actions/checkout` step —
   `repository: league-infrastructure/stem-ecosystem`, `ref: master`,
   `path: site` — positioned after the existing self-checkout step and
   before `Setup Node.js`/`Install dependencies` (which already assume
   `working-directory: site` via the job's `defaults.run`). No token is
   needed: this is a public-repo, read-only checkout, unlike the
   deferred, credentialed `scheduled-run.yml` publish path — do not add
   any secret reference for it. No other build step changes; `npm ci`,
   the Astro build command, and `upload-pages-artifact`'s `path:
   site/dist` are all unaffected by where `site/`'s content came from.
3. **Fix the trigger.** Remove the `push: paths: ['site/**']` filter —
   nothing in this repo can match it once `site/` is untracked. Keep
   `workflow_dispatch`. Add a `push` trigger scoped to
   `paths: ['.github/workflows/pages.yml']` (still `branches: ['master']`)
   so an edit to the workflow file itself self-verifies. Do not add a
   trigger tied to `stem-ecosystem`'s own pushes (`repository_dispatch`)
   or to `scheduled-run.yml`'s data push — both are deliberately out of
   scope (see sprint.md's Design Rationale: the former needs a
   coordinating change in a repo this sprint doesn't touch, the latter
   isn't even running yet, per the stakeholder's deferral of
   `SITE_REPO_TOKEN` provisioning).
4. **Update comments/docs that describe the old relationship.**
   `pages.yml`'s header comment ("partner-scrape is the beta: the site +
   scraped data are iterated here...") currently implies `site/` is
   tracked, iterated-on content in this repo — rewrite it to describe
   the build-time-checkout relationship instead. Update the `justfile`'s
   header comment and `dev`/`build`/`preview` recipe comments to note
   that local use now requires a personal, gitignored manual clone of
   `stem-ecosystem` at `site/` (or an adjusted `site :=` path) — the
   recipes' actual commands (`cd site && npm run dev`, etc.) don't need
   to change, only the assumption they document. **Do not introduce any
   absolute `/fonts/` path** anywhere you touch — stem-ecosystem's fonts
   are Vite-processed and base-aware, served from `src/fonts/`, not
   `public/fonts/`; this only matters if you add or edit a comment/doc
   line that happens to mention fonts, but is called out explicitly
   since it's an easy, non-obvious mistake to reintroduce.
5. **Verify end-to-end, for real.** Trigger the new `pages.yml` (`gh
   workflow run pages.yml --repo league-infrastructure/partner-scrape`
   or `just pub`) and confirm: the build-time checkout step succeeds,
   the Astro build succeeds, the deploy succeeds, and
   `github.io/partner-scrape` renders correctly with current
   stem-ecosystem content when opened. Record the run URL (or
   equivalent evidence) in this ticket before marking it done — this
   verification is the ticket's own Acceptance Criteria, not a
   follow-up someone else does later.

README.md is intentionally **not** touched by this ticket — ticket 003
owns the full README pass (it already rewrites the legacy sections that
would otherwise need a second, conflicting edit here) and adds the
`site/`-is-now-a-checkout note there in the same pass.

## Acceptance Criteria

- [ ] `site/` is untracked from git; `.gitignore` ignores `site/` as a
      whole directory (the three narrower `site/node_modules|dist|.astro`
      entries are removed or subsumed).
- [ ] `pages.yml`'s `build` job includes a second `actions/checkout` step
      for `league-infrastructure/stem-ecosystem` (`ref: master`,
      `path: site`), positioned before `npm ci`, with no secret/token
      reference.
- [ ] `pages.yml`'s `push.paths` no longer includes `site/**`; a push
      trigger scoped to `.github/workflows/pages.yml` is present
      alongside the retained `workflow_dispatch`.
- [ ] `pages.yml`'s header comment and the `justfile`'s relevant comments
      describe the build-time-checkout relationship, not a tracked local
      copy; no absolute `/fonts/` path appears anywhere touched.
- [ ] A real `gh workflow run` (or `just pub`) against the new
      `pages.yml` succeeds end-to-end; `github.io/partner-scrape`
      renders correctly with current stem-ecosystem content — evidence
      (run URL/output) recorded in this ticket.
- [ ] Full `uv run pytest -q` remains green (no Python source is touched
      by this ticket; this is a regression guard, not new coverage).

## Testing

- **Existing tests to run**: `uv run pytest -q` (regression guard only —
  this ticket touches no Python source).
- **New tests to write**: none — CI workflow/YAML changes aren't
  pytest-exercisable; the real verification is step 5's live workflow
  run.
- **Verification command**: `gh workflow run pages.yml --repo
  league-infrastructure/partner-scrape` (or `just pub`), followed by
  `gh run watch <run-id> --exit-status`; then `uv run pytest -q` as the
  regression guard.
