---
source_paths:
- /Volumes/Proj/proj/league-projects/infrastructure/partner-scrape/partner_scrape
---
# partner-scrape — System Design

**Owner:** Eric Busboom · **Last reviewed:** 2026-08-28 · **Status:** stable

This is the top-level design document for the `partner-scrape` repository. It covers
system-wide context, the subsystem map, and the global conventions every subsystem
document is allowed to assume without repeating.

---

## 1. What this project is

`partner-scrape` is the data engine behind **sdstemecosystem.org**, the San Diego STEM
Ecosystem's directory of STEM learning opportunities for K-12 youth.

It is one half of a two-repository architecture:

- **`partner-scrape`** (this repo) — a Python aggregator that visits ~100 partner
  organizations' websites and APIs, extracts events, programs, and internships,
  deduplicates and classifies them, and writes a JSON data contract.
- **`stem-ecosystem`** — an Astro static site that consumes that contract and renders the
  public directory.

The boundary between them is a small set of files written into the site checkout's
`src/data/` and `public/images/` directories. Nothing else crosses.

A run is scheduled, unattended, and expected to partially fail: with ~100 independent
third-party sources, some fraction is always broken, redesigned, or unreachable. The
system is built around that expectation — a partial result ships, and the gap is
*reported* rather than raised.

## 2. Repository layout

| Path | What it is |
|---|---|
| `partner_scrape/` | **The declared source root.** The whole engine. See [`partner_scrape/DESIGN.md`](../../partner_scrape/DESIGN.md) for the root overview and the top-level modules (`pipeline.py`, `cli.py`, `config.py`, `model.py`). |
| `tests/` | 905 fixture-based tests, one module per source module. No network. |
| `docs/` | This design set, plus `overview.md`, `specification.md`, `usecases.md`, and deployment notes. |
| `clasi/`, `.clasi/` | CLASI SE process artifacts — sprints, issues, reflections. |
| `site/` | This repo's own checkout of the Astro site (the beta the team develops against). |
| `dev/` | Pre-existing exploration scripts. Not a dependency of the package; logic was ported, not imported. |
| `config/` | Layered dotconfig `.env` files, assembled before the process starts. |

## 3. The pipeline

```
registry/       load_active_sources()            ~100 TOML files, one per organization
   ↓
adapters/       ThreadPoolExecutor(8):           per-source error isolation —
                discover → fetch → extract       a failure is logged and skipped
                   ↓         ↓        ↓
              discovery/  fetch/   extract/
   ↓
enrich/         LLMEnricher                      recover fields, classify, gate relevance
                                                 (fail-open; content-hash cache)
   ↓
normalize/      collapse → dedup → map           Event[] → Opportunity[]
   ↓
export/         opportunities.json, ads.json,    the cross-repo data contract
                images                           (+ mirror to extra checkouts, from cli.py)

observability/  runs alongside: per-source yield counts, deltas, alerts
store/          built, not wired in
```

**Sprint 011 addition — a second, independent pipeline.**
`partner_scrape/teams/` (own CLI subcommand: `partner-scrape teams`) is
deliberately **not** part of the flow above. It acquires San Diego FIRST
robotics team rosters (FTC via FTCScout, FRC via The Blue Alliance),
resolves cross-league identity, locates each team through an
offline-only geocoding ladder, and publishes `teams.json` alongside
`opportunities.json`/`ads.json`. It reuses `registry/`'s schema/loader,
`fetch/`'s `PoliteFetcher`, `config.py`, and one function of
`normalize/partners.py`, but never touches `adapters/`, `enrich/`,
`normalize.run()`, or `pipeline.run()` — a `Team` is a standing entity
with no date, and would be silently dropped by `export/`'s
current-and-upcoming filter if it were routed through `Opportunity`.
See [`partner_scrape/teams/DESIGN.md`](../../partner_scrape/teams/DESIGN.md).

## 4. Subsystem map

The source root itself carries an overview doc; each subsystem carries its own, co-located
in its own directory.

- [`partner_scrape/DESIGN.md`](../../partner_scrape/DESIGN.md) — **root overview**: the
  run end to end, the four top-level modules, and the shared conventions.
- [`partner_scrape/adapters/DESIGN.md`](../../partner_scrape/adapters/DESIGN.md) — ten
  per-vendor `discover → fetch → extract` strategies behind a one-line dispatch table.
- [`partner_scrape/discovery/DESIGN.md`](../../partner_scrape/discovery/DESIGN.md) —
  resolving sources into fetchable URLs; plus hub scanning for organization leads,
  structurally firewalled from the event pipeline.
- [`partner_scrape/enrich/DESIGN.md`](../../partner_scrape/enrich/DESIGN.md) — the LLM
  layer: field recovery, classification, relevance gating, cost-control cache.
- [`partner_scrape/export/DESIGN.md`](../../partner_scrape/export/DESIGN.md) — every write
  across the repo boundary, plus image self-hosting and multi-checkout mirroring.
- [`partner_scrape/extract/DESIGN.md`](../../partner_scrape/extract/DESIGN.md) — the
  confidence-ranked extraction ladder for arbitrary HTML.
- [`partner_scrape/fetch/DESIGN.md`](../../partner_scrape/fetch/DESIGN.md) — the only
  network access in the system: robots, throttling, caching, optional headless browser.
- [`partner_scrape/normalize/DESIGN.md`](../../partner_scrape/normalize/DESIGN.md) —
  recurrence collapse, cross-source dedup, taxonomy, partner join; owns `Opportunity`.
- [`partner_scrape/observability/DESIGN.md`](../../partner_scrape/observability/DESIGN.md)
  — per-source yield accounting and regression alerting.
- [`partner_scrape/registry/DESIGN.md`](../../partner_scrape/registry/DESIGN.md) — the
  data-driven catalog of sources, hubs, ads, and candidates.
- [`partner_scrape/store/DESIGN.md`](../../partner_scrape/store/DESIGN.md) — durable
  SQLite event table; built and tested, not wired into the pipeline.
- [`partner_scrape/teams/DESIGN.md`](../../partner_scrape/teams/DESIGN.md) — (sprint 011)
  a second, independent pipeline: scrapes, geocodes, and publishes San Diego FIRST
  robotics teams (FTC/FRC) as `teams.json`, structurally disjoint from the
  `Opportunity` pipeline above.

## 5. Global conventions

These hold throughout the codebase. Subsystem docs assume them and describe only their own
departures.

**Injectable protocols with fixture doubles.** Every boundary to the outside world is a
`typing.Protocol` passed in as an argument — `Fetcher`, `LLMClient`, `ImageFetcher`,
`HeadlessPage`, `Enricher`, `Reporter`. Production wiring happens at the outermost layer
(`cli.py`, `pipeline.run()`); tests inject doubles. This is why the whole suite runs with
no network and with the optional `playwright` dependency uninstalled.

**Structural satisfaction, never a backwards import.** Modules that satisfy
`pipeline.Enricher` or `pipeline.Reporter` do not import them. Python Protocols are
structural, so the import would buy nothing and would invert the dependency direction.

**One-way dependency direction.** `pipeline` → everything; `adapters` →
`discovery`/`extract`/`fetch`/`registry`; `export` → `normalize`; never the reverse.
`normalize/` never imports `export/`. `fetch/`, `extract/`, and `model.py` are leaves.

**Errors are isolated at the level that owns the unit.** Per-record inside an adapter's
`extract()`; per-source inside `pipeline.run()`; per-page inside discovery and the
extraction ladder; fail-open for LLM calls. A partial result ships; `observability/`
reports the gap.

**Provenance travels with values.** `Event.set(field, value, source, confidence)` records
origin and trust for every field. Structured APIs and JSON-LD are 1.0, the extraction
ladder descends to 0.2, LLM enrichment is 0.7, its keyword fallback 0.3. `normalize/` uses
those numbers to choose between competing records — so a confidence constant is a
project-wide contract.

**Configuration is data; environment is read in one place.** Onboarding an organization is
a new TOML file. `config.py` is the only module that touches `os.environ`.

**Datetimes are naive San Diego wall clock,** enforced by a single coercion in
`normalize.run()`.

**Minimal, deliberate dependencies.** `lxml`, `icalendar`, `python-dateutil`, `anthropic`,
`certifi`. HTTP is stdlib `urllib`, TOML is stdlib `tomllib`, the store is stdlib
`sqlite3`. `playwright` is an optional extra with a deferred import.

**Tests are fixture-based and hermetic** — 905 of them, one module per source module.

## 6. System-wide open questions

- `store/` is complete but unwired; the policy it implies (should a failed source keep
  publishing last run's data?) is undecided.
- The site data contract is unversioned and unvalidated in either direction.
- Yield alerts have no delivery channel beyond console output in the scheduled run's log.
- A circular import between `adapters.listing_html` and `discovery.listing` is worked
  around by import ordering rather than fixed.
- DST is unhandled: `normalize/run.py` hard-codes a `-07:00` offset.
- (Sprint 011) Whether `teams.json` is ever joined to the curated partner directory
  is an open product question, not resolved here: only 1 of 105 distinct team
  organizations is already a partner, while the other 104 are a candidate
  recruitment list for Fleet/League staff to act on, not an architectural decision.
