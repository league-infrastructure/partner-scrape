# partner_scrape

**Owner:** Eric Busboom · **Last reviewed:** 2026-08-28 · **Status:** stable

---

## 1. Purpose

`partner_scrape/` is the whole aggregator engine: the Python package that visits ~100 San
Diego STEM partner organizations, extracts their events, programs, and internships,
deduplicates and classifies them, and publishes a single JSON data contract into the
`stem-ecosystem` Astro site. This directory is the declared source root; everything the
engine does lives under it. Its ten subdirectories are the pipeline's stages and
supporting services, and the four modules at this level are the orchestration and shared
vocabulary that hold them together.

This document is the map of that root: what the top-level modules are, one line per
subsystem, and the conventions every subsystem doc below may assume without restating.

## 2. Orientation

**The run, end to end.** `pipeline.run()` sequences it:

```
registry.load_active_sources()
  → ThreadPoolExecutor(8) × [ adapters.run(source, fetcher) ]     per-source isolation
      where adapters.run = discover → fetch → extract             (discovery/, fetch/, extract/)
  → enrichers  (enrich.LLMEnricher: recover fields, classify (incl. opportunity_type), gate relevance)
  → normalize.run(events, partners.json, image_resolver)          collapse → dedup → map
  → export.export_opportunities(...) + export.export_ads(...) + export.partner_log.record(...)
```

`cli.py` then, after `run()` returns, calls `export.publish.project(...)` (collapses the
accumulated per-partner logs into the published `public/data/` tree — sprint 009) and
`export.mirror_site_data(...)` (now also mirrors that tree), and prints the yield report
from `observability/`. The whole run touches the network only through `fetch/`.

**Sprint 009 addition.** `export.partner_log.record(...)` is a new call inside
`pipeline.run()`, alongside the existing `export_opportunities`/`export_ads` calls: it
persists this run's `Opportunity`s into a durable, per-partner, append-only log (never
overwritten, unlike the flat `opportunities.json`). `export.publish.project(...)` is a new,
separate, CLI-sequenced step (mirroring how `mirror_site_data` is already sequenced after
`run()` returns, not inside it) that reads *all* accumulated per-partner logs — not only
this run's — and projects them into the published `public/data/` contract. See
`export/DESIGN.md` for both.

**Root-level modules.**

- **`pipeline.py`** — the orchestrator. Loads active sources; runs each source's
  discover→fetch→extract chain in a bounded `ThreadPoolExecutor` (default 8 workers, or a
  plain sequential loop when `max_source_workers <= 1`); selects each source's `Fetcher`
  from its `acquisition_policy.fetch_strategy`, lazily constructing the headless one at
  most once per run; applies enrichers in order; normalizes; exports opportunities and
  ads. It defines two Protocols that other subsystems satisfy structurally without
  importing them — `Enricher` and `Reporter`. Its only real logic is sequencing,
  per-source `Fetcher` selection, and per-source error isolation.
- **`cli.py`** — the `partner-scrape` console script. `argparse` wrapper over
  `pipeline.run()`, plus the `discover-candidates` subcommand for the lead-generation
  flow. Constructs the default concrete implementations (`LLMEnricher` with
  `AnthropicLLMClient`, `YieldReporter`) and owns the mirror step and console output. No
  business decisions live here.
- **`config.py`** — the only module in the package that reads `os.environ`. Accessors for
  `SCRAPE_CACHE_DIR` (required, no default), `SITE_DIR`, `MIRROR_SITE_DIRS`,
  `LEAGUESYNC_API_KEY`, and `LEAGUESYNC_URL`. Values are assembled by dotconfig into
  layered `.env` files before the process starts; this module only reads what landed.
- **`model.py`** — the canonical `Event` record and the shared identity vocabulary. A flat
  dataclass (~26 fields, sprint 009: `opportunity_type` joins the classification fields
  alongside `areas_of_interest`/`age_grade_level`/`cost_range`/`time_of_day`) plus a
  side-car `field_provenance: dict[str, Provenance]` map; `Event.set(field, value, source,
  confidence)` writes both at once. Also owns `normalize_title`, `identity_key`/
  `Event.identity_key()` (acquisition identity: "have we seen this exact record from this
  source?"), `same_record`, and (sprint 009) `slugify` — a small, shared text-to-slug
  utility promoted here from `normalize/run.py` because sprint 009 needs it in two places
  (the per-event slug in `normalize/run.py`, the per-partner slug in the new
  `export/partner_log.py`) and this is the module every other module already treats as the
  home for shared identity primitives. `Kind` is `"event" | "program" | "internship"`.

## 3. Subsystem Map

Each has its own `DESIGN.md` in its own directory.

| Subsystem | One line |
|---|---|
| [`adapters/`](adapters/DESIGN.md) | Ten per-vendor strategies implementing `discover → fetch → extract`, dispatched by `adapter_type` through a one-line registration table. |
| [`discovery/`](discovery/DESIGN.md) | Resolving a source into fetchable URLs (sitemap diff, listing crawl) — plus hub scanning, which generates *organization* leads and is structurally forbidden from producing Events. |
| [`enrich/`](enrich/DESIGN.md) | The LLM layer: field recovery, controlled-vocabulary classification, and the relevance gate, behind a content-hash cache and a fail-open policy. |
| [`export/`](export/DESIGN.md) | Every write across the repo boundary into the site: `opportunities.json`, `ads.json`, self-hosted images, mirroring into additional checkouts, and (sprint 009) a persistent per-partner accumulation log plus the published `public/data/` partners-and-events contract projected from it. |
| [`extract/`](extract/DESIGN.md) | The confidence-ranked extraction ladder: one HTML page in, `{field: (value, confidence)}` out. Pure, no I/O. |
| [`fetch/`](fetch/DESIGN.md) | The only network access in the system: the `Fetcher` seam, robots.txt, per-domain throttling, on-disk conditional-GET cache, and the optional headless browser. |
| [`normalize/`](normalize/DESIGN.md) | Recurrence collapse, cross-source dedup, taxonomy derivation, partner join — `Event`s in, site-shaped `Opportunity` records out. |
| [`observability/`](observability/DESIGN.md) | Per-source yield accounting, run-over-run deltas, zero-yield and cliff alerts, and the `yield-history.json` snapshot. |
| [`registry/`](registry/DESIGN.md) | The data-driven catalog: one TOML file per organization, plus separate hub, ad, and candidate catalogs. Onboarding is a data edit. |
| [`store/`](store/DESIGN.md) | A durable SQLite table of canonical Events for future incremental scraping. Built and tested, **not wired into the pipeline**. |

## 4. Shared Conventions

Every subsystem doc under this root assumes the following without restating it.

**Injectable protocols with fixture doubles.** Every boundary to the outside world is a
`typing.Protocol` taken as a constructor or function argument: `Fetcher`, `LLMClient`,
`ImageFetcher`, `HeadlessPage`, plus `Enricher` and `Reporter` (defined in `pipeline.py`
and satisfied structurally, never by import). Production wiring picks the real
implementation at the outermost layer — `cli.py` and `pipeline.run()`; tests inject
fixture-backed doubles. This is why 905 tests run with no network access and with the
optional `playwright` dependency uninstalled.

**Structural satisfaction, never a backwards import.** A module that satisfies a Protocol
defined in `pipeline.py` does not import it. `enrich.enricher.LLMEnricher`,
`observability.reporter.YieldReporter`, and `discovery.candidate_pipeline`'s own
`RelevanceGate` all follow this. Python's structural typing makes the import unnecessary,
and taking it would invert the dependency direction.

**One-way dependency direction.** `pipeline` → `registry`/`adapters`/`enrich`/`normalize`/
`export`; `adapters` → `discovery`/`extract`/`fetch`/`registry`/`model`; `export` →
`normalize`; and never the reverse in any of these. `normalize/` in particular never
imports `export/` — the image downloader reaches it as a plain `Callable[[str], str]`
constructed by `pipeline.run()` precisely so that edge does not exist. `fetch/`,
`extract/`, and `model.py` are leaves.

**Errors are isolated at the level that owns the unit.** One malformed *record* is logged
and skipped inside an adapter's `extract()`. One failing *source* is logged and skipped by
`pipeline.run()`, which never lets it raise up. One unparseable *page* is logged and
skipped by discovery and by the extraction ladder. One failed *LLM call* falls back to
keyword taxonomy. The system's guiding failure principle is that a partial result ships
and the gap is *reported* by `observability/`, rather than the run aborting.

**Provenance travels with values.** `Event.set(field, value, source, confidence)` records
where every field came from and how much it is trusted. Structured APIs and JSON-LD are
1.0; the extraction ladder's lower rungs descend to 0.2; LLM enrichment is 0.7 and its
keyword fallback 0.3. `normalize/`'s collapse and dedup use those numbers to pick between
competing records, so a confidence constant is a project-wide contract, not a local
detail.

**Configuration is data, and environment is read in one place.** Adding an organization is
a new TOML file in `registry/sources/`. `config.py` is the only module that touches
`os.environ`.

**Datetimes are naive San Diego wall clock.** Adapters should emit them that way; several
structured-API adapters do not, so `normalize.run()` coerces any timezone-aware
`start`/`end` to naive in exactly one place, because mixing the two makes date comparison
raise and crashes the run.

**Dependencies are minimal and deliberate.** `lxml` for HTML, `icalendar` and
`python-dateutil` for dates, `anthropic` for enrichment, `certifi` for TLS. HTTP is stdlib
`urllib`; TOML is stdlib `tomllib`; the store is stdlib `sqlite3`. `playwright` is an
optional extra whose import is deferred to first real use.

**Tests are fixture-based and hermetic.** 905 tests, one test module per source module,
saved HTML/JSON fixtures under `tests/fixtures/`, no network, no API key required.

## 5. Interfaces

### Exposes
- **`partner-scrape`** — the console script (`partner_scrape.cli:main`). Flags include
  `--registry-dir`, `--site-dir`, `--mirror-site-dir` / `--no-mirror`, `--source`,
  `--limit`, `--dry-run`, `--no-enrich`, `--no-report`, `--yield-history`, `--verbose`;
  plus the `discover-candidates` subcommand.
- **`pipeline.run(...) -> list[dict]`** — the programmatic entry point; returns the
  exported opportunity payload.
- **`model.Event`, `Provenance`, `Kind`, `identity_key`, `normalize_title`,
  `same_record`** — the shared record vocabulary every subsystem speaks.
- **The site data contract** — `src/data/opportunities.json`, `src/data/scrape-meta.json`,
  `src/data/ads.json`, and `public/images/opportunities/*` written into the
  `stem-ecosystem` checkout(s); plus, since sprint 009, the additive public data contract
  `public/data/partners.json` and each partner's `public/data/partners/<slug>/events.json`
  / `past-events.json`, projected from the new persistent per-partner accumulation store
  (not written into `src/data/`, since `src/` is Astro's own build input and this is meant
  to be fetchable at runtime as a public API — see `export/DESIGN.md`).

### Consumes
- **`stem-ecosystem`'s `src/data/partners.json`** — read-only, for the partner join.
- **Environment** (via `config.py` only): `SCRAPE_CACHE_DIR` (required), `SITE_DIR`,
  `MIRROR_SITE_DIRS`, `LEAGUESYNC_API_KEY`, `LEAGUESYNC_URL`; and `ANTHROPIC_API_KEY`,
  resolved by the `anthropic` SDK itself.
- **~100 partner websites and APIs**, reached only through `fetch/`.

## 6. Open Questions / Known Limitations

- `store/` is built but unused. The policy question it implies — should a source that
  failed this run keep publishing what it published last run? — is unanswered.
- There is a circular import between `adapters.listing_html` and `discovery.listing`,
  currently worked around by import ordering in `cli.py`.
- The site data contract is unversioned and unvalidated. A field rename on the site side
  shows up as missing data on a rendered page, not as an export failure. This now applies
  to two parallel contracts (`src/data/opportunities.json` and, since sprint 009,
  `public/data/partners.json` + per-partner event files) — see `export/DESIGN.md`'s Open
  Questions for why the sprint kept them parallel rather than unifying them now.
- Yield alerts are printed to the console. A zero-yield source in a scheduled run is only
  noticed if someone reads the log.
- `_TZ_OFFSET` in `normalize/run.py` is the hard-coded literal `-07:00`, so exported
  timestamps are wrong across the DST boundary.
- `scrapy` and `w3lib` remain declared dependencies but the fetch path is stdlib
  `urllib`; the declarations should be audited.
