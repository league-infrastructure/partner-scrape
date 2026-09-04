---
id: '003'
title: Tidy stale references, gitignore gaps, and empty config files
status: done
use-cases: []
depends-on: []
github-issue: ''
issue: 48-repo-cleanup-stale-cruft.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Tidy stale references, gitignore gaps, and empty config files

## Description

Four small, independent housekeeping items from issue 48 (items 4-7),
batched into one ticket since none has real code or a dedicated
verification gate of its own:

1. **Stale cross-references** (item 4): `partner_scrape/discovery/sitemap.py`
   and `partner_scrape/discovery/DESIGN.md` cite `dev/inventory_sitemaps.py`
   and `dev/lib/sitemap_parser.py` as the origin of their regex patterns.
   Both files were deleted long ago. Reword so the comments read as
   historical provenance rather than a live cross-reference to a file a
   reader could open.
2. **`.gitignore` gaps** (item 5): `.clasi/.clasi.db-wal`,
   `.clasi/.clasi.db-shm` (sqlite sidecars of the already-ignored
   `.clasi/.clasi.db`) and `.pytest_cache/` are not ignored and showed up
   in `git status` during the 2026-09-02 session.
3. **Redundant `.gitkeep`** (item 6): `docs/design/.gitkeep` no longer
   keeps anything — `docs/design/` already holds `design.md`,
   `overview.md`, `specification.md`, `usecases.md`.
4. **Four empty config files** (item 7): `config/dev/public.env`,
   `config/dev/secrets.env`, `config/local/eric/public.env`,
   `config/local/eric/secrets.env` are all 0 bytes; only `config/prod/*`
   carries real (SOPS-encrypted) content. **These may be `dotconfig`
   scaffolding** — `config/AGENTS.md` documents the expected layout as
   `config/{deploy}/public.env` + `secrets.env` per deploy name (dev,
   prod, ...) and `config/local/{username}/public.env` + `secrets.env`
   per developer, and `dotconfig load dev`, `dotconfig load -l eric`
   discover deploys/locals by scanning these directories. Verify before
   deleting: if removing them would break `dotconfig`'s view of
   available deploys or local overrides, **leave them and record why in
   issue 48** instead of forcing a deletion. "Kept, here's why" is a
   legitimate outcome for this item, not a fallback.

## Acceptance Criteria

- [x] `partner_scrape/discovery/sitemap.py`'s and
      `partner_scrape/discovery/DESIGN.md`'s references to
      `dev/inventory_sitemaps.py` / `dev/lib/sitemap_parser.py` are
      reworded to read as historical provenance (e.g. "ported from a
      since-deleted `dev/inventory_sitemaps.py`") rather than implying
      the files still exist to open.
- [x] `.gitignore` gains entries covering `.clasi/.clasi.db-wal`,
      `.clasi/.clasi.db-shm`, and `.pytest_cache/`. After running the
      test suite (which generates `.pytest_cache/`) and using CLASI
      normally (which generates the sqlite sidecars), `git status`
      shows none of the three as untracked.
- [x] `docs/design/.gitkeep` is removed (the directory is non-empty and
      stays non-empty without it).
- [x] For each of the four empty `config/` files: either (a) it is
      deleted, and a check against `dotconfig`'s deploy/local-discovery
      behavior (e.g. `dotconfig load dev` and/or `dotconfig load -l
      eric`, or an equivalent listing) after deletion confirms no
      deploy/local silently disappears from what `dotconfig` can load;
      or (b) it is kept, with the reason recorded in issue 48 (item 7)
      explaining what `dotconfig` behavior would break if it were
      removed.
- [x] The verification step for the config files actually ran (not just
      reasoned about) — the ticket records the command run and its
      outcome, not just an inference from reading `config/AGENTS.md`.
- [x] Full test suite green (`uv run pytest`, baseline 2531 passing) —
      none of these changes should affect test-covered code, but the
      `.gitignore`/`.pytest_cache/` change should be checked against a
      real `uv run pytest` run to confirm the ignore pattern actually
      matches.
- [x] No test touches the network, the live Anthropic API, or writes
      into the `stem-ecosystem` checkout (unaffected by this ticket, but
      re-confirm the suite is still clean on that front after `.gitignore`
      changes).

## Implementation Plan

**Approach**: Four independent, low-risk edits. Do the config-file
verification first (it's the only one with a real "don't break something"
risk and the only one that might change the ticket's outcome), then the
other three in any order.

**Files to modify**:
- `partner_scrape/discovery/sitemap.py` — reword the four comment
  references identified (lines ~21-22, 52, 56, 65, 74 as of this
  writing; re-grep before editing since line numbers may have shifted).
- `partner_scrape/discovery/DESIGN.md` — reword its corresponding
  reference(s) to the same deleted files.
- `.gitignore` — add `.clasi/.clasi.db-wal`, `.clasi/.clasi.db-shm`,
  `.pytest_cache/` (group near the existing `.clasi/.clasi.db` /
  `.clasi/log/` entries for locality).
- `docs/design/.gitkeep` — delete.
- `config/dev/public.env`, `config/dev/secrets.env`,
  `config/local/eric/public.env`, `config/local/eric/secrets.env` —
  delete only after the `dotconfig` verification step confirms it's
  safe; otherwise leave in place.
- `clasi/issues/48-repo-cleanup-stale-cruft.md` — append the recorded
  outcome/reasoning for item 7 under its existing "Verify before
  deleting" note.

**Testing plan**: No new automated tests (docs/config/ignore-file only).
Manual verification: run `uv run pytest` and confirm `.pytest_cache/`
and `.clasi/.clasi.db-*` no longer appear in `git status`; run whatever
`dotconfig` command demonstrates deploy/local discovery (`dotconfig load
dev`, `dotconfig load -l eric`, or equivalent) before and after the
config-file decision to confirm the outcome is safe.

**Documentation updates**: `clasi/issues/48-repo-cleanup-stale-cruft.md`
gets the recorded outcome for item 7 (kept-with-reason or
deleted-and-verified). No other doc updates beyond the reworded
comments in `sitemap.py`/`DESIGN.md`.

## Testing

- **Existing tests to run**: `uv run pytest` (full suite; no regression
  expected).
- **New tests to write**: none — this ticket is docs/config/ignore-file
  only, with no new code path.
- **Verification command**: `uv run pytest`, plus `git status` after a
  test run to confirm the `.gitignore` additions actually suppress the
  named artifacts, plus the `dotconfig` deploy/local-discovery check
  described above for the config-file decision.

## Notes

**(a) Stale references**: reworded all four `dev/inventory_sitemaps.py`
/ `dev/lib/sitemap_parser.py` comment references in
`partner_scrape/discovery/sitemap.py` (module docstring, `_NS`,
`EVENT_PATTERNS`, `PROGRAM_PATTERNS`, `EVENT_PATH_RE`) and the one in
`partner_scrape/discovery/DESIGN.md` (the "Two-level classification"
Design Rationale entry) to name the specific deleted files and point to
git history, instead of "the pre-existing `dev/` exploration scripts"
(which reads as if `dev/` still holds sitemap-related code).

**(b) `.gitignore`**: added `.clasi/.clasi.db-wal`,
`.clasi/.clasi.db-shm` next to the existing `.clasi/.clasi.db` entry,
and a new `.pytest_cache/` entry. Verified by running `uv run pytest`
(which generates `.pytest_cache/`) and then `git status` — `.pytest_cache/`
shows only under `git status --ignored` (`!!`), not as untracked. The
`-wal`/`-shm` sqlite sidecars were not present on disk at verification
time (SQLite only materializes them during an open write transaction),
but the ignore entries are exact-name matches identical in form to the
already-working `.clasi/.clasi.db` entry, so the same mechanism applies.

**(c) `docs/design/.gitkeep`**: deleted. `docs/design/` still holds
`design.md`, `overview.md`, `specification.md`, `usecases.md`.

**(d) Four empty `config/` files — verification actually run**: backed
up all four files, then deleted them and ran `dotconfig load dev
--stdout`:

```
$ rm config/dev/public.env config/dev/secrets.env \
     config/local/eric/public.env config/local/eric/secrets.env
$ dotconfig load dev --stdout
  ✗ deployment config file not found: config/dev/public.env
(exit 1)
```

`config/dev/public.env` is hard-required — `dotconfig load dev` fails
outright without it. Restored the four files via `git checkout --`
(confirmed `git status` clean on `config/` afterward, `dotconfig load
dev --stdout` succeeds again). Follow-up isolation checks (each also
restored immediately via `git checkout --`):
- `config/dev/secrets.env` alone missing: `dotconfig load dev` still
  succeeds (secrets section just empty).
- `config/local/eric/public.env` alone missing: `dotconfig load dev
  eric` succeeds with a warning (`local config file not found ...
  public-local section will be empty`).
- `config/local/eric/secrets.env` alone missing: `dotconfig load dev
  eric` succeeds with no warning.

**Decision: keep all four.** `config/dev/public.env` cannot be removed
without breaking `dotconfig load dev`. The other three are individually
removable without hard failure, but they are one documented scaffold
per `config/AGENTS.md`'s layout (a `public.env` + `secrets.env` pair per
deploy, and per developer under `config/local/`) — deleting three of
the four and keeping only `config/dev/public.env` would leave an
inconsistent, confusing partial scaffold for no real cleanup benefit
(these are already 0 bytes). Recorded in issue 48 item 7.

Full suite: 2538 passed (unchanged — this ticket touches no
test-covered code).
