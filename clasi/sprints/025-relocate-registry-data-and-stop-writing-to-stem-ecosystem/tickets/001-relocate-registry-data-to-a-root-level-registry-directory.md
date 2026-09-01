---
id: '001'
title: Relocate registry data to a root-level registry/ directory
status: in-progress
use-cases:
- SUC-028
depends-on: []
github-issue: ''
issue: move-registry-data-to-repo-root.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Relocate registry data to a root-level registry/ directory

## Description

`partner_scrape/registry/` mixes code (`loader.py`, `schema.py`,
`hub_schema.py`, `candidates.py`, `validate_roster.py`, `__init__.py`,
`DESIGN.md`, `DO_NOT_SCRAPE.md`) and data (`sources/` — 122 files,
`hubs/` — 2 files, `candidates/` — 241 files, `ads/` — 1 file — 366 TOML
files total). Move the four data directories to a new root-level
`registry/` directory, sibling to `data/` and `partner_scrape/`. The
code stays exactly where it is; only the default-path constants that
point at this data change. See sprint.md's Architecture (Design
Rationale: "promote `_REPO_ROOT` to a public `REPO_ROOT`") for the full
reasoning behind the chosen approach.

## Acceptance Criteria

- [x] `registry/sources/`, `registry/hubs/`, `registry/candidates/`,
      `registry/ads/` exist at the repo root (sibling to `data/`,
      `partner_scrape/`) with all 366 files present, moved via `git mv`
      (preserving history).
- [x] `partner_scrape/registry/` contains no `.toml` files; only code
      and its two `.md` docs remain.
- [x] `config.py` exposes a new public `REPO_ROOT` constant (the
      existing private `_REPO_ROOT`, promoted — not a second,
      independently-computed constant).
- [x] `registry/loader.py`'s `DEFAULT_SOURCES_DIR`,
      `registry/hub_schema.py`'s `DEFAULT_HUBS_DIR`,
      `registry/candidates.py`'s `DEFAULT_CANDIDATES_DIR`, and
      `export/ads.py`'s `DEFAULT_ADS_DIR` each resolve to
      `REPO_ROOT / "registry" / "<subdir>"`, imported from `config.py`.
- [x] `partner_scrape/registry/DESIGN.md`, `DO_NOT_SCRAPE.md`, and
      `cli.py`'s `--registry-dir`/`--hubs-dir`/`--candidates-dir` help
      text no longer describe the old `partner_scrape/registry/...`
      location as current.
- [x] `uv run partner-scrape --dry-run --limit 5` and
      `uv run partner-scrape discover-candidates --no-enrich` both run
      cleanly with no path errors.
- [x] `uv run pytest -q` is green.

## Implementation Plan

**Approach**: this is a path relocation, not a behavior change — do
the move and the constant repoint together in one commit so there is
never an intermediate state where they disagree.

1. `git mv partner_scrape/registry/sources registry/sources` (and the
   same for `hubs`, `candidates`, `ads`).
2. In `config.py`, add `REPO_ROOT = _REPO_ROOT` (a public alias) near
   the existing `_REPO_ROOT` definition, with a short docstring noting
   it exists so other modules needing a root-relative default (e.g.
   registry data) don't each recompute their own parent-chain.
3. Update `registry/loader.py`: `from partner_scrape.config import
   REPO_ROOT`; `DEFAULT_SOURCES_DIR = REPO_ROOT / "registry" / "sources"`.
4. Update `registry/hub_schema.py` and `registry/candidates.py`
   identically for `DEFAULT_HUBS_DIR`/`DEFAULT_CANDIDATES_DIR`.
5. Update `export/ads.py`'s `DEFAULT_ADS_DIR` the same way (it already
   imports `config.py`, so this is just a changed constant, no new
   import).
6. Grep the whole tree for `partner_scrape/registry/sources`,
   `partner_scrape/registry/hubs`, `partner_scrape/registry/candidates`,
   `partner_scrape/registry/ads` (docstrings, `cli.py` help text,
   `DESIGN.md`, `DO_NOT_SCRAPE.md`) and update the load-bearing/
   user-facing ones (CLI help text, module docstrings that describe
   *current* behavior). Historical sprint docstrings describing past
   decisions are lower priority — don't chase every mention.
7. Audit (don't assume) every test file that references
   `DEFAULT_SOURCES_DIR`/`DEFAULT_HUBS_DIR`/`DEFAULT_CANDIDATES_DIR`/
   `DEFAULT_ADS_DIR` directly: `tests/test_registry.py`,
   `tests/test_registry_candidates.py`, `tests/test_registry_hub_schema.py`,
   `tests/test_export_ads.py`. Confirmed during planning: these assert
   `.name`/`.parent.name` (e.g. `DEFAULT_SOURCES_DIR.parent.name ==
   "registry"`), which stay true after the move — expect these to need
   no change, but verify each assertion doesn't also encode an absolute
   `partner_scrape/`-relative assumption.

**Files to modify**: `config.py`; `registry/loader.py`;
`registry/hub_schema.py`; `registry/candidates.py`; `export/ads.py`;
`cli.py` (help text only); `partner_scrape/registry/DESIGN.md`;
`partner_scrape/registry/DO_NOT_SCRAPE.md`; plus the `git mv` of the
four data directories.

**Testing plan**: run the full existing suite (`uv run pytest -q`) —
this ticket should require zero new tests, since loader *behavior* is
unchanged (only the on-disk location of its default input). If any
existing test breaks, it identifies a hardcoded path assumption this
ticket's own investigation missed — fix it here, not by working around
it. Manually run `uv run partner-scrape --dry-run --limit 5` and
`uv run partner-scrape discover-candidates --no-enrich` to confirm the
CLI's real (non-test) defaults resolve correctly post-move.

**Documentation updates**: `partner_scrape/registry/DESIGN.md` and
`DO_NOT_SCRAPE.md` path references (see Acceptance Criteria).
