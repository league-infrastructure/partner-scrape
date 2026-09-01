---
id: '025'
title: Relocate Registry Data and Stop Writing to Stem-Ecosystem
status: done
branch: sprint/025-relocate-registry-data-and-stop-writing-to-stem-ecosystem
use-cases:
- SUC-028
- SUC-029
- SUC-030
issues:
- move-registry-data-to-repo-root.md
- stop-writing-to-stem-ecosystem-checkout.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 025: Relocate Registry Data and Stop Writing to Stem-Ecosystem

## Goals

1. Move the Source/Hub/Candidate/Ad Registry's **data** (`sources/`,
   `hubs/`, `candidates/`, `ads/` — 366 TOML files total) out of
   `partner_scrape/registry/` and into a new root-level `registry/`
   directory, sibling to `data/` and `partner_scrape/`. The Python code
   that owns this data stays in the package.
2. Stop every write partner-scrape makes into the sibling `stem-ecosystem`
   checkout. `data/` (this repo's own pipeline-output directory,
   established sprint 020) becomes the *only* place partner-scrape writes
   its own output — `stem-ecosystem` becomes a pull-based consumer of
   `data/`, not a push target.

## Problem

**Registry data location** (issue: `move-registry-data-to-repo-root.md`).
`partner_scrape/registry/` mixes CODE (`loader.py`, `schema.py`,
`hub_schema.py`, `candidates.py`, `validate_roster.py`, `__init__.py`,
`DESIGN.md`, `DO_NOT_SCRAPE.md`) and DATA (`sources/` — 122 files,
`hubs/` — 2 files, `candidates/` — 241 files, `ads/` — 1 file) in one
directory, buried three levels inside the Python package. Eric's stated
principle, repeated twice in tonight's conversation: "well-known data
lives in an easily discoverable root-level place, code lives in the
package." `data/` is the existing precedent.

**Stem-ecosystem writes** (issue:
`stop-writing-to-stem-ecosystem-checkout.md`). Eric, verbatim: "I want
you not to write to the stem ecosystem directory. I want the stem
ecosystem to get data from you, so you're not writing the stem ecosystem
anymore." He then asked for a full production scrape — which only makes
sense once this write-removal lands (a full run today still writes into
`../stem-ecosystem`, contradicting the directive). Every export module
already dual-writes as of sprint 020 (issue 60): once into
`{site_dir}/...` and once into `config.get_own_data_dir()`
(`<repo_root>/data`). This sprint removes the `{site_dir}/...` half of
each.

**Two write paths surfaced during this sprint's own investigation that
were not in Eric's original enumeration:**

1. `pipeline.py`'s `run()` constructs a real
   `export.images.EventImageDownloader` (whenever `image_resolver` is
   omitted) that writes downloaded opportunity images into
   `{site_dir}/public/images/opportunities/` — a write path with **no**
   `own_data_dir` equivalent at all, not part of sprint 020's dual-write
   pattern. stem-ecosystem's own measurement: 631 images, ~405MB, mean
   655KB/median 303KB, 147 files over 1MB accounting for 67% of total
   bytes (including a 5.2MB raw-camera-original JPEG served as a card
   thumbnail) — `EventImageDownloader` fetches and quality-gates images
   today but never resizes them.
2. `cli.py`'s `main()` reads the *previous* run's yield-history snapshot
   from `{site_dir}/src/data/yield-history.json` (via `load_snapshot()`,
   used to compute this run's found/dropped delta) before it ever writes
   anything — stopping only the write side would leave this read
   pointed at a file that stops being updated, silently freezing yield
   deltas at whatever the last site-written snapshot happened to be.

## Solution

**Registry data.** `git mv` the four TOML-bearing directories from
`partner_scrape/registry/{sources,hubs,candidates,ads}/` to
`registry/{sources,hubs,candidates,ads}/` at the repo root. Add a public
`REPO_ROOT` constant to `config.py` (promoting the existing private
`_REPO_ROOT`, already used for `DEFAULT_SITE_DIR`/`DEFAULT_OWN_DATA_DIR`)
and repoint `registry/loader.py`'s `DEFAULT_SOURCES_DIR`,
`registry/hub_schema.py`'s `DEFAULT_HUBS_DIR`,
`registry/candidates.py`'s `DEFAULT_CANDIDATES_DIR`, and
`export/ads.py`'s `DEFAULT_ADS_DIR` at it. The code stays exactly where
it is; only the four constants' values change, plus the docstrings/CLI
help text that name the old path.

**Stem-ecosystem writes.** Extend the same "own `data/` is the only
write target" pattern sprint 020 partially established to the last mile:
remove the `{site_dir}/...` write from `export_opportunities()`,
`export_ads()`, `export_teams()`, and `export_directory()` outright
(each keeps only its existing `own_data_dir` write); redirect
`export/publish.py`'s `project()` — a richer, per-partner data contract
sprint 020 never touched — to write into `own_data_dir` instead of
`{site_dir}/public/data/`; fold a resize-on-fetch step into
`EventImageDownloader` for newly-downloaded images and redirect its
write target to `data/images/opportunities/`; and consolidate
`cli.py`'s yield-history read *and* write onto a single `own_data_dir`
path, replacing the site_dir-defaulted one. `site_dir`/`--site-dir` is
removed from every function and CLI flag that no longer has any real
use for it; kept wherever it still resolves a genuine *read* (the
`partners.json` roster input, explicitly out of scope for removal).
`.github/workflows/scheduled-run.yml`'s now-permanently-dead
"publish to stem-ecosystem" step is removed.

## Success Criteria

- `registry/sources/`, `registry/hubs/`, `registry/candidates/`,
  `registry/ads/` exist at the repo root with all 366 files present;
  `partner_scrape/registry/` retains only code and its two `.md` docs.
  `uv run partner-scrape --dry-run --limit 5` runs cleanly against the
  new location with no path errors.
- A real (non-dry-run) full run of `partner-scrape` (the `run`
  subcommand), `partner-scrape teams`, and `partner-scrape directory`
  produces **zero** file changes anywhere under `../stem-ecosystem`
  (checksummed/mtime-compared before and after) while fully populating
  `data/`: `opportunities.json`, `scrape-meta.json`, `ads.json`,
  `teams.json`, `places.json`, `clubs.json`, `yield-history.json`,
  `partners.json` + `partners/<slug>/events.json` +
  `partners/<slug>/past-events.json` (from `publish.project()`), and
  `images/opportunities/*` (newly-downloaded images, resized).
  `../stem-ecosystem/src/data/partners.json` remains readable and is
  the only file under `../stem-ecosystem` this run ever opens.
  `data/` has a flat layout throughout — no `src/`/`public/` split —
  matching every sprint-020 export module's existing convention.
- A newly-downloaded opportunity image whose original exceeds the
  resize cap is written measurably smaller than its original fetch
  size; an image already under the cap is written byte-identical to
  its fetch (no unnecessary re-encode/quality loss).
- No test or source reference to `partner_scrape/registry/sources/`
  (etc.) as an absolute on-disk assumption survives outside historical
  docstring prose.
- `uv run pytest -q` green.

## Scope

### In Scope

- `config.py`: new public `REPO_ROOT` constant.
- `registry/loader.py`, `registry/hub_schema.py`, `registry/candidates.py`,
  `export/ads.py`: repoint `DEFAULT_*_DIR` constants at the root-level
  `registry/`.
- Moving `partner_scrape/registry/{sources,hubs,candidates,ads}/` to
  `registry/{sources,hubs,candidates,ads}/`.
- `partner_scrape/registry/DESIGN.md`, `DO_NOT_SCRAPE.md`, and `cli.py`
  help text: update path references.
- `export/images.py`: resize-on-fetch for newly-downloaded images
  (new `Pillow` dependency); dedup-by-hash recomputed from final bytes.
- `pipeline.py`: stop passing `site_dir` to `export_opportunities()`/
  `export_ads()`; redirect the Event Image Downloader's `dest_dir` to
  `data/images/opportunities/`.
- `export/writer.py`, `export/ads.py`, `teams/export.py`,
  `directory/export.py`: remove the `{site_dir}/...` write and the
  `site_dir` parameter from each.
- `teams/pipeline.py`: remove `run_teams()`'s now-dead `site_dir`
  parameter. `directory/pipeline.py`: keep `run_directory()`'s
  `site_dir` (still needed for the `partners.json` read), stop passing
  it into `export_directory()`.
- `cli.py`: remove the `teams` subcommand's `--site-dir` flag;
  consolidate the yield-history snapshot read+write onto a single
  `own_data_dir`-based default path (one `save_snapshot()` call, not
  two).
- `export/publish.py`: add `own_data_dir`; redirect `project()`'s write
  from `{site_dir}/public/data/` to `own_data_dir`; keep `site_dir` for
  default `partners_path` resolution.
- `.github/workflows/scheduled-run.yml`: remove the dead
  "Publish refreshed site data to stem-ecosystem" step; update the
  `SITE_REPO_TOKEN` verification step's message (this workflow now only
  *reads* `partners.json` from stem-ecosystem, never publishes to it).
- `pyproject.toml`: add `Pillow` as a new dependency.

### Out of Scope

- `teams/registry/` and `directory/registry/` — smaller, separate
  registries (4 and 2 TOML files) not named in Eric's directive. A
  candidate follow-up if the same root-level principle is ever extended
  to them; not decided here.
- `partners.json` — the read from `{site_dir}/src/data/partners.json`
  stays exactly as-is everywhere it happens (`pipeline.run()`'s roster
  validation/join checks, `directory/pipeline.py`'s
  `related_partner_id` check, `export/publish.py`'s default
  `partners_path`). Eric's directive was specifically about writes.
- Re-encoding/migrating the 631 legacy opportunity images already
  committed in stem-ecosystem's `public/images/opportunities/` — tracked
  as stem-ecosystem's own issue 58, a coordinated re-publish (resizing
  an existing image changes its content-hash filename, which changes
  every `image_src` reference to it in `opportunities.json`) explicitly
  out of scope here.
- Any distribution/build-time-fetch mechanism for how `stem-ecosystem`
  actually pulls from partner-scrape's `data/` — that is stem-ecosystem's
  own concern (mirrors sprint 020's identical scope boundary: "Anything
  in the `stem-ecosystem` repo ... owned by the parallel session").
  This sprint's job ends at making `data/` a complete, trustworthy,
  git-committed publish target.
- Downgrading `SITE_REPO_TOKEN`'s `contents:write` scope on
  stem-ecosystem to read-only — an operator credential change, flagged
  in Open Questions, not performed by this sprint.
- Any version bump (`close_sprint` handles that once, at sprint close).

## Test Strategy

Hermetic throughout, extending this project's established convention:
every export function's tests already pass an explicit `tmp_path`-backed
`site_dir`/`own_data_dir` rather than touching real checkouts; the same
tests are updated in place to assert the `{site_dir}/...` write no
longer happens (rather than asserting it does) and that the
`own_data_dir` write is now the sole target. `export/images.py`'s new
resize step gets dedicated fixture-based tests: an oversized synthetic
image (constructed in-memory, no network) is resized and re-encoded
smaller; an already-small image passes through byte-identical; dedup
correctly keys off final (post-resize) bytes.

**Required live verification** (this project's established convention,
most recently sprint 020/024): ticket 008 runs the real, non-dry-run
`partner-scrape` `run`, `teams`, and `directory` commands against the
real `registry/` (post-move) and the real sibling `../stem-ecosystem`
checkout. Unlike prior sprints' live verification — which confirmed
compatibility *with* `../stem-ecosystem` — this sprint's live
verification confirms the opposite: a checksum/mtime sweep of every file
under `../stem-ecosystem` taken immediately before and after the run
must show **zero** changes, while `data/` must be fully populated (see
Success Criteria for the exact file list). This is the only way to
truly confirm "stop writing to stem-ecosystem" holds, since a unit test
with a fixture `site_dir` cannot, by construction, prove nothing touches
the *real* one.

## Architecture

**Substantial** — this sprint touches every export module in the
codebase (`export/writer.py`, `export/ads.py`, `teams/export.py`,
`directory/export.py`, `export/publish.py`, `export/images.py`), their
owning pipelines (`pipeline.py`, `teams/pipeline.py`,
`directory/pipeline.py`), `cli.py`, `config.py`, three registry-code
modules, and CI wiring — well past the "one module" compact tier. It
also introduces a genuinely new cross-module dependency
(`registry/loader.py`, `registry/hub_schema.py`, `registry/candidates.py`
→ `config.py`, none of which import `config.py` today) and a new
external dependency (`Pillow`, for image resizing). No data-model
change (every payload's shape is unchanged; only write destinations and,
for images, byte size change) and no new external *service* integration
— so the full 7-step methodology applies, with a component diagram, but
no ERD.

### Architecture Overview

**Step 1 — Problem.** See Problem above: two independent stakeholder
directives (registry data location; stop cross-repo writes) plus two
write paths this sprint's own investigation surfaced that neither
directive named explicitly (the image downloader; the yield-history
read).

**Step 2 — Responsibilities.** Three independently-changing groups:

1. *Where registry/ad data lives on disk* — a pure path relocation,
   zero behavioral change to what the data means or how it's loaded.
2. *Where each export module writes its payload* — removing one of two
   (or three, for `teams.json`/`places.json`/`clubs.json`) existing
   write targets from five already-dual/triple-writing modules, plus
   redirecting a sixth (`publish.project()`) that predates sprint 020's
   pattern.
3. *What the Event Image Downloader does before writing* — a genuinely
   new capability (resize-on-fetch), coupled to the same "which
   directory" decision as group 2, but conceptually distinct (it changes
   the bytes written, not just their destination).

These three groups change for different reasons and at different times
(group 1 could ship without groups 2/3 ever happening; group 3 could be
skipped and group 2 would still be complete for every *other* export)
— which is why they're separate tickets below, not one large ticket.

**Step 3 — Modules.**

- **Config** (`config.py`) — purpose: centralize environment-derived and
  root-relative path configuration. Boundary: the only module that reads
  `os.environ` directly (unchanged); gains one new public constant,
  `REPO_ROOT`, so other modules needing a root-relative default no
  longer each recompute `Path(__file__).resolve().parent...` chains
  independently. Serves SUC-028.
- **Registry/Ad Data Loaders** (`registry/loader.py`,
  `registry/hub_schema.py`, `registry/candidates.py`, `export/ads.py`) —
  purpose (each, individually): load and validate one TOML-configured
  data directory. Boundary unchanged (still four separate, independently
  loadable directories with no cross-loading); each module's one
  `DEFAULT_*_DIR` constant now derives from `config.REPO_ROOT` instead
  of its own file-relative parent. Serves SUC-028.
- **Event Image Downloader** (`export/images.py`) — purpose: fetch,
  validate, quality-gate, and self-host one event's image. Boundary
  gains one new internal step (resize-on-fetch) between the existing
  quality gate and the existing dedup-by-hash step; still takes
  `dest_dir` as a plain constructor argument and knows nothing about
  `site_dir`/`own_data_dir` — the caller (`pipeline.py`) decides where.
  Serves SUC-030.
- **Pipeline/CLI orchestration** (`pipeline.py`) — purpose: sequence
  Registry → Adapters → Normalize → Export. Boundary unchanged; stops
  passing `site_dir` into `export_opportunities()`/`export_ads()` (they
  no longer accept it) and repoints the Event Image Downloader's
  `dest_dir` construction. Keeps its own `site_dir` parameter — still
  needed for the `partners.json` read. Serves SUC-029, SUC-030.
- **Opportunity Export** (`export/writer.py`), **Ad Export**
  (`export/ads.py`), **Teams Export** (`teams/export.py`), **Directory
  Export** (`directory/export.py`) — purpose (each): filter/serialize/
  publish one data contract. Boundary narrows: each loses its
  `site_dir` parameter and the write it powered; `own_data_dir` becomes
  each module's only write target. Serves SUC-029.
- **Teams Pipeline** (`teams/pipeline.py`) — purpose: sequence the Team
  Registry → acquisition → merge → geocode → export. Boundary narrows:
  drops its own now-meaningless pass-through `site_dir` parameter.
  Serves SUC-029.
- **Directory Pipeline** (`directory/pipeline.py`) — purpose: sequence
  the Directory Registry → acquisition → geocode → export. Boundary
  unchanged in shape (keeps `site_dir`, still needed for the
  `related_partner_id` → `partners.json` read) but stops forwarding it
  to `export_directory()`, which no longer accepts it. Serves SUC-029.
- **Publish Projection** (`export/publish.py`) — purpose: project every
  partner's accumulated per-partner log into a richer, self-describing
  published tree. Boundary gains `own_data_dir` as its write target,
  replacing `{site_dir}/public/data/`; keeps `site_dir` for its existing
  role resolving a default `partners_path` (a read, not a write). Serves
  SUC-029.
- **CLI** (`cli.py`) — purpose: parse flags, orchestrate. Loses the
  `teams` subcommand's now-meaningless `--site-dir` flag; its
  yield-history snapshot read+write collapses from a site_dir-defaulted
  path (read+written) plus a second own_data_dir-only write, onto a
  single own_data_dir-based default doing both. Serves SUC-029.
- **Scheduled Run** (`.github/workflows/scheduled-run.yml`) — purpose:
  run the pipeline unattended and publish its output. Loses its now-dead
  "commit and push to stem-ecosystem" step; keeps the stem-ecosystem
  checkout step (still needed to provide the `partners.json` read
  input) and its own existing "commit and push to partner-scrape's own
  `data/`" step (sprint 020 ticket 008, unchanged, now the only publish
  step). Serves SUC-029.

**Step 4 — Diagram.** Warranted: 3+ modules touched, and a genuinely new
cross-module dependency is introduced (the three registry-code modules
→ `config.py`). Solid edges are unchanged/new; dashed edges marked
`REMOVED` show what this sprint deletes.

```mermaid
graph LR
    CLI["CLI (cli.py)"]
    CFG["Config (config.py)<br/>NEW: REPO_ROOT"]
    REG["Registry/Ad Data Loaders<br/>(loader.py, hub_schema.py,<br/>candidates.py, export/ads.py)"]
    IMG["Event Image Downloader<br/>(export/images.py)<br/>NEW: resize-on-fetch"]
    OPP["Opportunity + Ad Export<br/>(export/writer.py, export/ads.py)"]
    TEAMS["Teams Export<br/>(teams/export.py)"]
    DIR["Directory Export<br/>(directory/export.py)"]
    PUB["Publish Projection<br/>(export/publish.py)"]
    REGROOT[("registry/<br/>repo root (NEW location)")]
    SITE[("../stem-ecosystem<br/>(read-only: partners.json)")]
    DATA[("data/<br/>this repo (SOLE write target)")]
    CI["scheduled-run.yml (CI)"]

    CLI -->|invokes| OPP
    CLI -->|invokes| TEAMS
    CLI -->|invokes| DIR
    CLI -->|invokes| PUB

    REG -->|NEW: reads REPO_ROOT| CFG
    REG -->|loads from| REGROOT

    OPP -.->|REMOVED: opportunities.json,<br/>scrape-meta.json, ads.json| SITE
    OPP -->|writes| DATA
    TEAMS -.->|REMOVED: teams.json x2| SITE
    TEAMS -->|writes| DATA
    DIR -.->|REMOVED: places.json,<br/>clubs.json x2| SITE
    DIR -->|writes| DATA
    PUB -.->|REMOVED: public/data/*| SITE
    PUB -->|writes| DATA
    PUB -->|reads partners.json<br/>(unchanged)| SITE
    IMG -.->|REMOVED: public/images/*| SITE
    IMG -->|writes resized images| DATA

    CI -->|checks out (read-only now)| SITE
    CI -->|commits/pushes| DATA
```

No ERD (no data-model change — `Opportunity`/`Team`/`Place`/`Club`
shapes are untouched; only write destinations, and image bytes, change).
No separate dependency graph beyond the one new edge already shown above
(`Registry/Ad Data Loaders` → `Config`) — every other module already
imported `config.py` before this sprint.

**Step 5 — What Changed / Why / Impact / Migration Concerns.** Covered
above (Solution, Problem) and in Migration Concerns below.

### Design Rationale

**Decision: promote `_REPO_ROOT` to a public `REPO_ROOT` in `config.py`,
rather than recomputing a parent-chain in each of the four
data-owning modules.**
- Context: `registry/loader.py`, `registry/hub_schema.py`,
  `registry/candidates.py`, and `export/ads.py` each define their own
  `DEFAULT_*_DIR` locally, today via `Path(__file__).resolve().parent /
  "<subdir>"`. Moving the data one level further away (to the repo
  root) means each needs a way to find the repo root.
- Alternatives considered: (a) each module independently computes
  `Path(__file__).resolve().parent.parent.parent` (or `.parent.parent`
  for `export/ads.py`, one level shallower) — no new dependency, but
  four separately-maintained relative-depth computations that silently
  drift if any of these files ever moves; (b) centralize the four
  `DEFAULT_*_DIR` constants themselves inside `config.py`, matching
  where `DEFAULT_SITE_DIR`/`DEFAULT_OWN_DATA_DIR` already live — more
  centralization, but forces every owning module to reach into
  `config.py` for even its own default, and duplicates a decision this
  project has *not* made for these four (unlike `SITE_DIR`, none of
  them need an env-var override) purely for symmetry.
- Why this choice: (a)'s risk is real — this codebase's docstrings
  themselves warn about exactly this kind of fragile relative-depth
  arithmetic (see `export/publish.py`'s own "one-way dependency" framing
  for the general principle this project already applies: one shared
  source of truth beats N independently-computed copies). (b) over-
  centralizes for no present benefit. `REPO_ROOT` as a single public
  constant lets each owning module keep authoring its own default (same
  as today, same file, same variable name) while removing the
  duplicated arithmetic.
- Consequences: `registry/loader.py`, `registry/hub_schema.py`, and
  `registry/candidates.py` gain a new import of `config.py` — the one
  real new dependency edge this sprint introduces (shown in the
  diagram). `export/ads.py` already imports `config.py`, so it gains no
  new edge, just a changed constant.

**Decision: remove `site_dir` from `export_opportunities()`,
`export_ads()`, `export_teams()`, `run_teams()`, `export_directory()`,
and the `teams` CLI subcommand's `--site-dir` flag; keep it on
`pipeline.run()`, `run_directory()`, `export/publish.py`'s `project()`,
and the `run`/`directory` CLI subcommands.**
- Context: every one of these currently accepts `site_dir`. Once its
  write is removed, some of these have *no remaining use* for the
  parameter at all; others still need it to resolve a real read
  (`partners.json`).
- Alternatives considered: (a) remove `site_dir` everywhere it no
  longer writes, including `pipeline.run()`/`run_directory()`/
  `project()` — maximally clean, but breaks the `partners.json` read
  those three still perform, which is explicitly out of scope to touch;
  (b) keep `site_dir` as an accepted-but-unused parameter everywhere,
  changing nothing about any signature — minimizes diff size and test
  churn, but leaves dead, misleading surface on `export_opportunities()`
  et al. forever (a future reader has no way to tell, from the
  signature alone, that passing `site_dir` now does nothing).
- Why this choice: a clean per-function rule — keep `site_dir` only
  where the function's body still reads something through it after this
  sprint, remove it everywhere else. This is not a blanket policy but a
  case-by-case application of "narrow interfaces" (this project's own
  Architecture Quality Principles): a parameter that does nothing is a
  footgun, not a convenience. Measured churn before deciding: existing
  test files reference `site_dir` in the hundreds across
  `test_export.py`, `test_pipeline_e2e*.py`, `test_export_publish.py`,
  `teams/test_export.py`, `teams/test_pipeline.py`,
  `directory/test_export.py` — but this is mechanical (delete a kwarg
  from a call, delete a `site_dir=tmp_path` fixture line, delete a
  handful of "file written under site_dir" assertions per test module),
  not conceptually hard, and each hermetic test already isolates its
  own `site_dir` fixture with no cross-test coupling.
- Consequences: `export_opportunities()`, `export_ads()`,
  `export_teams()`, `export_directory()` each become strictly simpler
  (fewer parameters, one write target, one thing to test). `run_teams()`
  loses a parameter with no compensating loss of capability (nothing
  ever read through it). `run_directory()`, `pipeline.run()`, and
  `project()` are unaffected in shape — they keep exactly the parameter
  they still use for a real purpose.

**Decision: redirect `export/publish.py`'s `project()` to
`own_data_dir` rather than deleting it or moving its logic into
stem-ecosystem.**
- Context: `project()` is structurally different from the other four
  export functions — it doesn't just serialize this run's output, it
  reads *every* partner's full accumulated history (via
  `export/partner_log.py`'s append-only per-partner `.jsonl` log,
  itself stored under `SCRAPE_CACHE_DIR`, never under `site_dir`) and
  projects a current/past split richer than the flat `opportunities.json`
  — self-describing per-partner event files no consumer can reconstruct
  from `opportunities.json` alone. It never got sprint 020's
  `own_data_dir` treatment because it predates that sprint's pattern by
  eleven sprints (sprint 009) and nobody had revisited it since.
- Alternatives considered: (a) delete `project()`/its CLI call entirely,
  treating its output as redundant with `opportunities.json` — rejected:
  it is not redundant, it carries the full accumulated per-partner
  history `opportunities.json`'s current-window filter deliberately
  discards; (b) move the projection logic into stem-ecosystem's own
  build (have the site read the raw per-partner `.jsonl` log itself and
  project it at build time) — rejected as genuinely new,
  cross-repo-coordinated work with its own design surface, far beyond
  "remove a write path," and it would require partner-scrape to publish
  the raw log somewhere stem-ecosystem's build can reach it anyway,
  which is exactly the problem redirecting to `own_data_dir` already
  solves more simply; (c) redirect to `own_data_dir`, mirroring the
  pattern already proven for the other four modules.
- Why this choice: (c) requires no new design, reuses a pattern this
  project has already built and tested four times, and produces exactly
  what Eric asked for — stem-ecosystem pulling data from partner-scrape,
  not partner-scrape pushing into it. `site_dir` stays on `project()`
  only because it still resolves a legitimate default read
  (`partners_path`), never because anything still gets written there.
- Consequences: `{own_data_dir}/partners.json` and
  `{own_data_dir}/partners/<slug>/{events,past-events}.json` become new,
  additional files under `data/` (on top of the five sprint-020 files),
  git-committed by the same existing weekly CI step.

**Decision: fold resize-on-fetch into `EventImageDownloader` for newly-
downloaded images only; do not touch the 631 already-published legacy
images; add `Pillow` as this project's first image-processing
dependency.**
- Context: surfaced only after investigation — the image write was not
  in Eric's original enumeration. First framing (before the sibling
  stem-ecosystem session's actual measurement came back) treated this as
  an open hosting/infrastructure question requiring Eric's input,
  because a naive "just redirect the write to `data/`" would relocate a
  believed-recurring ~405MB/week binary-churn problem into
  partner-scrape's own git history, which its scheduled CI already
  commits weekly. The actual measurement corrected the premise on both
  counts: filenames are content-hashed, so the git history shows only
  additions, never modifications — the 405MB is a one-time accumulation,
  not a recurring weekly cost; and it is mostly waste, not volume (mean
  655KB/median 303KB, but 147 of 631 files exceed 1MB and account for
  67% of all bytes — `EventImageDownloader` has never resized anything,
  including a 5.2MB raw-camera-original JPEG served as a card
  thumbnail). `export/images.py`'s own docstring, written at ticket 008
  (sprint 008), already anticipated this exact moment: "If genuine pixel
  downscaling becomes a real operational need, revisit adding an
  image-processing dependency in a follow-up ticket."
- Alternatives considered (from the corrected premise): (a) redirect to
  `data/images/opportunities/` unresized — simplest, but perpetuates the
  same oversized-original problem this sprint has the context to fix
  right now, one file at a time, going forward; (b) redirect to
  `data/images/opportunities/`, gitignored (matching `SCRAPE_CACHE_DIR`'s
  precedent) — avoids repo growth entirely, but leaves stem-ecosystem's
  planned build-time-pull mechanism with no git-trackable source at all,
  trading a real problem for a harder, undesigned one; (c) resize-on-
  fetch (long-edge cap + re-encode) for new downloads, redirected to
  `data/images/opportunities/`, tracked normally like every other
  `own_data_dir` file.
- Why this choice: (c) is what the corrected measurement actually calls
  for — the resize step directly fixes the thing that made images
  expensive (oversized originals), not just where they're written, and
  a resized new download is small enough (typically tens to low hundreds
  of KB, versus up to 5MB+ unresized) that the weekly `data/` commit
  this sprint's own CI step already performs stays proportionate to the
  small-JSON-diff cost profile it was built for. Re-encoding the
  existing 631 images is a *different*, coordinated problem (their
  filenames are content-hashes of their current bytes; resizing any of
  them changes its filename, which changes every `image_src` reference
  to it across `opportunities.json` and every already-published detail
  page) explicitly tracked as stem-ecosystem's own issue 58, not
  something this sprint's own scope or authority extends to.
- Long-edge cap and quality: 1600px long edge, JPEG quality 80. An image
  already at or under the cap is written through unchanged (original
  bytes, original format, original dedup-by-hash) — no unnecessary
  re-encode/quality loss for the common case, which is most images
  today (median 303KB is already well inside a reasonable card/detail
  display size at typical event-photo dimensions). Only PNG/JPEG/WebP
  are eligible for resize; an animated GIF (rare for scraped event
  photos, effectively unseen in this project's existing extraction
  paths) is passed through unresized rather than risk collapsing its
  animation to a single frame.
- Consequences: `Pillow` becomes a new, required (not optional/`extra`,
  unlike `playwright`) dependency — reverses `export/images.py`'s
  original sprint 008 "stdlib only, zero new dependencies" decision, now
  explicitly superseded by the real operational need that decision's own
  docstring said would justify revisiting. Dedup-by-hash is recomputed
  from the *final* (possibly resized) bytes rather than the original
  fetch — required for correctness (two visually-identical images
  arriving from different source URLs but the same original bytes must
  still dedupe to the same resized output), and a deliberate behavior
  change from today's "hash of raw fetched bytes."

**Decision: consolidate `cli.py`'s yield-history read *and* write onto
a single `own_data_dir`-based default, not just the write half Eric
named.**
- Context: found during investigation. `main()` reads the *previous*
  run's snapshot from `yield_history_path` (defaulted to
  `{resolved_site_dir}/src/data/yield-history.json`) before `run()` is
  even called, to compute this run's found/dropped delta; it separately
  writes the new snapshot to that same path, plus (sprint 020 ticket
  007) a second, independent write to `{own_data_dir}/yield-history.json`.
  Removing only the site_dir *write* (as literally enumerated) would
  leave the *read* pointed at a file that stops being updated — freezing
  every future delta computation against a stale, frozen snapshot
  forever, or eventually reading nothing at all if stem-ecosystem's own
  housekeeping ever removes it.
- Why this choice: the read and the write must point at the same file
  for the delta computation to mean anything — the moment the write
  target changes, the read target must change with it. Defaulting
  `yield_history_path` itself to `{own_data_dir}/yield-history.json`
  (with `--yield-history` still available as an explicit override) makes
  both correct, and collapses `main()`'s two `save_snapshot()` calls
  (site_dir + own_data_dir) into one.
- Consequences: the very first run after this sprint lands starts with
  no prior snapshot at the new default location (`load_snapshot()`
  already handles this — an empty dict, the documented "first run ever"
  baseline) — a one-time reset of the found/dropped delta to
  "everything is new," not a bug, and self-correcting on the next run.

### Migration Concerns

- **One-time image bootstrap.** The first real run after this sprint
  downloads and resizes every currently-surviving opportunity's image
  fresh into `data/images/opportunities/` (no pre-existing cache there);
  `EventImageDownloader`'s existing `mkdir(parents=True, exist_ok=True)`
  already handles a missing destination, no new handling needed.
- **`data/`'s weekly CI commit gains a new binary content category**
  (`images/opportunities/*.jpg`) on top of the existing five JSON files.
  Expected to stay proportionate post-resize (see Design Rationale); if
  it does not in practice, revisit in a follow-up sprint — not
  pre-solved speculatively here.
- **stem-ecosystem's existing 631 legacy images are untouched and will
  simply stop receiving new ones** once this sprint ships; they remain
  exactly as they are (stale but present) until stem-ecosystem's own
  issue 58 addresses them, independently.
- **`SITE_REPO_TOKEN`'s `contents:write` scope on stem-ecosystem is no
  longer exercised** by `scheduled-run.yml` once its publish-back step
  is removed (the checkout step still needs read access). Downgrading
  the fine-grained PAT to read-only is an operator credential change
  Eric may want to make at his convenience — not performed by this
  sprint (see Open Questions).
- **Backward compatibility**: every removed `site_dir`/`--site-dir`
  parameter is a breaking internal API change for any direct caller
  (tests, ad hoc scripts) that passed one expecting a write. This is an
  internal tool, not a published library — no deprecation period, ticket
  -level test updates cover every in-repo caller.
- **No data migration** for the registry directory move — `git mv`
  preserves file history; every constant repointed in the same ticket
  that moves the files, so there is no intermediate state where the two
  disagree.

## Use Cases

Sized to the change: three sprint-level use cases covering the three
independently-changing responsibility groups from Architecture Step 2.

### SUC-028: Operator finds and edits registry data at a well-known root-level location
Parent: UC-008 (Add a new partner source)

- **Actor**: Operator.
- **Preconditions**: A source, hub, candidate, or ad TOML file needs to
  be added, edited, or reviewed.
- **Main Flow**:
  1. Operator navigates to `<repo_root>/registry/sources/` (or
     `hubs/`/`candidates/`/`ads/`) directly from the repo root — no
     need to know or remember that this data used to live inside the
     Python package.
  2. Operator adds/edits/removes a `.toml` file.
  3. `load_sources()`/`load_hubs()`/`list_candidates()`/
     `load_ad_configs()` pick up the change on the next run with no code
     change, exactly as before the move.
- **Postconditions**: Registry data is discoverable at the repo root;
  every existing loader behavior (malformed-file skip, `enabled: false`
  handling, dedup) is unchanged.
- **Acceptance Criteria**:
  - [ ] `registry/sources/`, `registry/hubs/`, `registry/candidates/`,
        `registry/ads/` exist at the repo root with all 366 files
        present; `partner_scrape/registry/` contains no `.toml` files.
  - [ ] `DEFAULT_SOURCES_DIR`/`DEFAULT_HUBS_DIR`/`DEFAULT_CANDIDATES_DIR`/
        `DEFAULT_ADS_DIR` each resolve to the new root-level path via
        `config.REPO_ROOT`.
  - [ ] Every existing registry/candidates/ads test passes unmodified in
        its assertions about loader *behavior* (only path-construction
        details change).
  - [ ] `uv run partner-scrape --dry-run --limit 5` and
        `uv run partner-scrape discover-candidates --no-enrich` both run
        cleanly against the new location.

### SUC-029: partner-scrape publishes exclusively to its own repo; stem-ecosystem becomes a pull-based consumer
Parent: SUC-019 (sprint 020, "Pipeline output is published in
partner-scrape's own repo") — this sprint completes what that one
started: SUC-019 added `own_data_dir` as a second write target
alongside `site_dir`; this use case removes `site_dir` as a write
target entirely, everywhere.

- **Actor**: Operator / Engine.
- **Preconditions**: A production run of `partner-scrape` (`run`,
  `teams`, or `directory`) is about to execute against the real sibling
  `stem-ecosystem` checkout.
- **Main Flow**:
  1. Operator runs `partner-scrape` (or `teams`/`directory`), passing
     `--site-dir` pointing at the real `stem-ecosystem` checkout (or
     relying on the `SITE_DIR`/default resolution).
  2. The run reads `{site_dir}/src/data/partners.json` as an input
     (roster validation, join checks) — the only file under `site_dir`
     it ever opens.
  3. Every export writes exclusively into `data/` at the repo root:
     `opportunities.json`, `scrape-meta.json`, `ads.json`, `teams.json`,
     `places.json`, `clubs.json`, `yield-history.json`, `partners.json`
     + per-partner `events.json`/`past-events.json`
     (`publish.project()`), and resized opportunity images.
  4. Nothing under `{site_dir}/...` is created, modified, or deleted at
     any point in the run.
- **Postconditions**: `data/` fully reflects the run's output;
  `../stem-ecosystem` is bit-for-bit unchanged except for whatever a
  separate, independent stem-ecosystem-side process does to it later.
- **Error flows**: `{site_dir}/src/data/partners.json` missing or
  unreadable → fails loudly (unchanged existing behavior — this read was
  never in scope to soften).
- **Acceptance Criteria**:
  - [ ] `export_opportunities()`, `export_ads()`, `export_teams()`,
        `export_directory()` each accept no `site_dir` parameter and
        write only to `own_data_dir`.
  - [ ] `export/publish.py`'s `project()` writes
        `{own_data_dir}/partners.json` and
        `{own_data_dir}/partners/<slug>/{events,past-events}.json`;
        `{site_dir}/public/data/...` is never touched.
  - [ ] `cli.py`'s yield-history snapshot is read from and written to a
        single `own_data_dir`-based default path.
  - [ ] `.github/workflows/scheduled-run.yml` no longer commits or
        pushes to stem-ecosystem.
  - [ ] Live verification (ticket 008): a real, non-dry-run `run` +
        `teams` + `directory` invocation produces zero file changes
        anywhere under `../stem-ecosystem` (checksum/mtime swept before
        and after) while `data/` is fully populated per Success
        Criteria.

### SUC-030: A full pipeline run downloads and resizes new opportunity images into partner-scrape's own data directory
Parent: extends the Event Image Downloader established sprint 008
ticket 008 (issue 19); serves the same underlying export flow as UC-006
(Export upcoming opportunities to the site).

- **Actor**: Engine.
- **Preconditions**: An `Event` has a populated `image_url`; the image
  has not already been downloaded and cached (by content hash) this run.
- **Main Flow**:
  1. `EventImageDownloader.download()` fetches the image and runs its
     existing quality gate (scheme check, 2xx status, `Content-Type`,
     size cap, structural image-decode check, minimum dimensions) —
     unchanged from today.
  2. If the image's width or height exceeds the long-edge cap (1600px),
     it is resized (aspect-ratio preserved) and re-encoded (JPEG,
     quality 80); an image already within the cap passes through with
     its original bytes and format.
  3. A filename is derived from the SHA-256 of the *final* (possibly
     resized) bytes; an image whose final bytes already match a
     previously-written file this run reuses that filename rather than
     writing a duplicate.
  4. The final bytes are written under `data/images/opportunities/`
     (`config.get_own_data_dir()`-relative), never under
     `{site_dir}/public/images/opportunities/`.
- **Postconditions**: `Opportunity.image_src` holds the resized image's
  filename; the file exists under `data/images/opportunities/`; nothing
  is written under `../stem-ecosystem`.
- **Alternate Flow**: a missing, unreachable, or quality-gate-rejected
  image still returns `""` and leaves `image_src` empty — this sprint
  changes nothing about that existing contract.
- **Acceptance Criteria**:
  - [ ] A synthetic oversized fixture image (long edge > 1600px) is
        written measurably smaller than its original fetched size.
  - [ ] A synthetic fixture image already within the cap is written
        byte-identical to its fetched bytes (no unnecessary re-encode).
  - [ ] Two events whose fetched images produce identical final
        (post-resize) bytes dedupe to one written file.
  - [ ] `pipeline.run()`'s default `image_resolver` construction targets
        `data/images/opportunities/`, never `{site_dir}/public/images/
        opportunities/`.
  - [ ] `Pillow` is declared in `pyproject.toml`'s `dependencies`.

## GitHub Issues

(None filed — this sprint originates from a same-session stakeholder
directive, captured as two local CLASI issues; see this sprint's
`issues:` frontmatter.)

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [x] Sprint planning document is complete (sprint.md, including its
      Architecture and Use Cases sections)
- [x] Architecture review passed (or skipped, for changes with no
      architectural impact)
- [ ] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Depends On |
|---|-------|------------|
| 001 | Relocate registry data to a root-level `registry/` directory | — |
| 002 | Resize-on-fetch for the Event Image Downloader and redirect to `data/images/` | — |
| 003 | Remove the `site_dir` write from Opportunity and Ad export | 002 |
| 004 | Remove the `site_dir` write from Teams export | — |
| 005 | Remove the `site_dir` write from Directory export | — |
| 006 | Consolidate yield-history snapshot read/write onto `data/` | — |
| 007 | Redirect `publish.project()`'s per-partner projection to `data/` | — |
| 008 | Retire the dead stem-ecosystem CI publish step and live-verify the full write-removal | 001, 002, 003, 004, 005, 006, 007 |

Tickets execute serially in the order listed.
