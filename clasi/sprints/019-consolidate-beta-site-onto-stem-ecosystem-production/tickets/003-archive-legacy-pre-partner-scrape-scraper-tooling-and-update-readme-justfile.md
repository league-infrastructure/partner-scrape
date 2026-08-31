---
id: '003'
title: Archive legacy pre-partner_scrape scraper tooling and update README/justfile
status: in-progress
use-cases:
- SUC-002
depends-on: []
github-issue: ''
issue: consolidate-partner-scrape-s-beta-site-into-stem-ecosystem-production.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Archive legacy pre-partner_scrape scraper tooling and update README/justfile

## Description

Before `partner_scrape/` (sprint 001) existed, this repo was a
Scrapy-based site mirroring tool. That system was superseded — this
repo's own `README.md` already says so ("the new aggregator engine
(sprint 001) that replaces the legacy `dev/`/`scraper/`/`run_mirrors.py`
mock-up described below") — but the superseded code, its Docker
tooling, and the README sections documenting it were never removed.
Sprint 019's site consolidation is the natural occasion to close this
out: it's the same kind of "we're carrying dead duplicate tooling"
problem this sprint exists to fix, just older.

**No file overlap with tickets 001 or 002** — this ticket touches only
the repo-root legacy tree and `README.md`; it has no real dependency on
either and can run in any order relative to them, though it is listed
last to match the issue's own item ordering.

**Investigate first, then remove** (per the issue's own instruction —
grep before removing anything):

1. Confirm nothing under `partner_scrape/`, `tests/`, or
   `.github/workflows/` imports or references `scrapy.cfg`,
   `scraper/` (as a Python package), `run_mirrors.py`,
   `Dockerfile`, `docker-compose.yml`, or `requirements.txt`. (A prior
   investigation for this sprint's planning already ran this grep and
   found no live references — `scraper/` and `run_mirrors.py` are not
   imported by `partner_scrape/`, and `Dockerfile`'s only reference to
   either is its own `ENTRYPOINT`. Re-confirm at implementation time in
   case anything changed.)
2. **Archive** (remove from the active tree — `git rm`, relying on git
   history for recovery; this repo has no existing `archive/`-style
   convention to follow, so don't invent one) `dev/`, `scraper/`,
   `run_mirrors.py`, `scrapy.cfg`.
3. **Also archive** `Dockerfile`, `docker-compose.yml`, and
   `requirements.txt` — beyond what the issue's Proposed Fix item 3 names
   explicitly, but inseparable from it: `Dockerfile`'s `ENTRYPOINT` runs
   `run_mirrors.py` directly, and `docker-compose.yml`'s only service
   builds that `Dockerfile`. Leaving them after step 2 would leave a
   broken, misleading Docker entry point pointing at code that no longer
   exists (see sprint.md's Design Rationale for this scope call).
4. **Rewrite `README.md`.** Remove the legacy sections that document the
   archived system: "Overview," "Quick Start" (both the Docker and Local
   Python options), "Project Layout," "CLI Reference," "Data Structure,"
   "Scrapy Settings Highlights," and "Future Work" — everything from the
   `---` after "Running the engine" (the `partner_scrape/` section,
   which stays) down to the end of the file describes the archived
   system and should go, replaced with at most a short historical note
   if useful (e.g., "the pre-`partner_scrape/` Scrapy-based prototype
   has been retired; see git history"). Keep the "Running the engine"
   section (Install/Configure/Run/Test) — it documents the live system
   and is unaffected. Add a brief note there (or immediately after) that
   `partner-scrape/site/` (the beta preview) is now a build-time-only
   checkout of `stem-ecosystem` in CI (ticket 002), not tracked content
   in this repo — this is the one place README.md needs to describe
   that change; ticket 002 deliberately left this to this ticket to
   avoid two tickets editing the same file's overlapping sections.
5. **Check the `justfile`** for any leftover reference to the archived
   tooling or to the removed mirror CLI flags (ticket 001/002's
   concern) — there should be none (its recipes are all
   `site`/Astro-related), but confirm rather than assume.

## Acceptance Criteria

- [ ] `git grep` for `scrapy.cfg`, `run_mirrors`, `scraper.settings`,
      `Dockerfile`, `docker-compose.yml`, and `requirements.txt`
      (excluding `clasi/` history) turns up nothing live under
      `partner_scrape/`, `tests/`, or `.github/workflows/` before
      removal — confirmed and noted in this ticket's implementation, not
      just assumed.
- [ ] `dev/`, `scraper/`, `run_mirrors.py`, `scrapy.cfg`, `Dockerfile`,
      `docker-compose.yml`, and `requirements.txt` no longer exist in
      the working tree.
- [ ] `README.md`'s legacy Overview/Quick Start/Project
      Layout/CLI Reference/Data Structure/Scrapy Settings/Future Work
      sections are removed; the live "Running the engine" section
      remains and gains a short note that `site/` is now a build-time
      checkout of `stem-ecosystem`, not tracked content.
- [ ] `justfile` has no reference to the archived tooling or to the
      removed `--mirror-site-dir`/`--no-mirror` flags.
- [ ] Full `uv run pytest -q` is green (the archived code was never
      imported by `partner_scrape/`, so this is a regression guard, not
      an expected-failure fix).
- [ ] `git grep -l 'scrapy.cfg\|run_mirrors\|MIRROR_SITE_DIRS'` outside
      `clasi/` returns nothing — this is the sprint's own final
      Success-Criteria check, and this ticket is what actually
      satisfies the `scrapy.cfg`/`run_mirrors` half of it (ticket 001
      satisfies the `MIRROR_SITE_DIRS` half).

## Testing

- **Existing tests to run**: `uv run pytest -q` (full suite — regression
  guard; no test is expected to reference the archived code, so this
  confirms that assumption rather than exercising new behavior).
- **New tests to write**: none — this ticket removes unreferenced code
  and rewrites documentation; there is nothing new to unit-test.
- **Verification command**: `uv run pytest -q`, plus
  `git grep -rn "scrapy.cfg\|run_mirrors\|scraper\.settings"` to confirm
  the removal is clean.
