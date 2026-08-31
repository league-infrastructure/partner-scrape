# Adapters

**Owner:** Eric Busboom · **Last reviewed:** 2026-08-28 · **Status:** stable

---

## 1. Purpose

`adapters/` owns the translation from *one registered source* into *canonical `Event`
records*. It is a subsystem because the codebase deliberately draws a seam between "how
you talk to a particular site or API" (endlessly varied, one implementation per vendor
shape, expected to grow) and everything downstream of it (which only ever sees `Event`).
That seam is what lets a new organization be onboarded by adding a TOML file plus, at
most, one new adapter class — never by editing the pipeline, the normalizer, or the
exporter. Nothing else in the system owns per-vendor protocol knowledge; if vendor
quirks appear outside this directory, the boundary has leaked.

## 2. Orientation

The public contract is `base.py`'s `Adapter` Protocol: three methods, `discover` →
`fetch` → `extract`, chained by the module-level `run(source, fetcher)` function.

- `discover(source, fetcher) -> Iterable[EventRef]` resolves a `SourceConfig` into the
  set of fetchable units. For a structured API that is usually "enumerate the pages",
  sometimes after a cheap probe call; for the HTML adapters it delegates to the
  `discovery/` subsystem.
- `fetch(ref, fetcher, source) -> RawResponse` retrieves one unit through the injected
  `Fetcher`. Adapters never open sockets themselves. **(Sprint 015 ticket 003)** gained
  the `source` parameter, matching `discover()`/`extract()`, which already received it
  — see below.
- `extract(raw, source) -> Iterable[Event]` maps one raw body into zero or more `Event`s.

**(Sprint 015 ticket 003)** `fetch()`'s `source` parameter exists so every
implementation can call the new `acquisition_kwargs(source) -> dict[str, Any]` helper
(also in `base.py`) and spread its result into its own `fetcher.get()` call(s):
`fetcher.get(url, **acquisition_kwargs(source))`. `acquisition_kwargs()` reads
`source.acquisition_policy["rate_limit_seconds"]`/`["respect_robots"]`, falling back to
`PoliteFetcher.get()`'s own defaults when a source sets neither — the same
default-merge pattern `run()`'s own `max_urls` handling already uses. Before this
ticket, `fetch()` took only `(ref, fetcher)`, so no adapter's fetch call could reach a
source's acquisition policy at all; every `fetcher.get()` call site in this package's
adapters and in `discovery/sitemap.py`/`discovery/listing.py` (which import
`acquisition_kwargs` from here the same way they already import `EventRef`) now passes
it through. This is what makes `leaguesync.toml`'s `respect_robots = false` — parsed
but previously never threaded anywhere — finally reach `PoliteFetcher.get()`. See
`fetch/DESIGN.md`'s own Sprint 015 addendum for the receiving side.

`run()` is the only chaining logic and is adapter-agnostic: it looks the class up in the
`ADAPTERS` dispatch dict, instantiates it, materializes `discover()`'s output, truncates
it to the source's `max_urls` cap, then loops fetch→extract accumulating events.

Ten adapter types are registered today, in two families:

| Family | Types | Shape |
|---|---|---|
| Structured API | `tec_rest`, `wp_rest`, `ical`, `localist`, `bibliocommons`, `greenhouse`, `lever`, `leaguesync` | Known endpoint, JSON/iCal parsing, `CONFIDENCE = 1.0` |
| HTML | `generic_html`, `listing_html` | URL discovery via `discovery/`, field recovery via `extract/`'s ladder |

`ats_filters.py` is a shared helper, not an adapter: the deterministic
internship / STEM / San-Diego-local classifier the two applicant-tracking-system adapters
(`greenhouse`, `lever`) use to decide whether a job posting becomes an `Event` at all.

## 3. Constraints and Invariants

- **Registration is one line in `adapters/__init__.py`.** New types are added by
  assigning into `ADAPTERS`; `base.py`'s `run()`/`get_adapter()` are never touched. If a
  change to `base.py` looks necessary to add an adapter, the new adapter is being written
  against the wrong contract — fix the adapter, not the dispatch.
- **`ADAPTERS` is populated in `__init__.py`, never in `base.py`.** Each concrete adapter
  imports from `base`, so populating the table inside `base` would create an import
  cycle.
- **Per-record error isolation inside `extract()`.** One malformed record in an otherwise
  good response is logged and skipped, never raised. This is distinct from `pipeline.py`'s
  per-*source* isolation: without it, a single bad row silently discards every other
  record in the same page.
- **`discover()` must return an eagerly-computed list, not a lazy generator with
  per-item side effects.** `run()` materializes and slices the result to enforce
  `max_urls`; a generator whose side effects only fire on iteration would have the cap
  applied after the work was already done.
- **The `max_urls` cap (`acquisition_policy.max_urls`, default 300) is enforced
  centrally and never silently.** It is the adapter-agnostic backstop against one
  pathological source (a "sitemap" that is really hundreds of blog posts) dominating a
  run's wall clock. Truncation logs the discovered count and the dropped count.
- **Adapters do not construct `Fetcher`s.** The `Fetcher` arrives as an argument, chosen
  per source by `pipeline.run()`. No adapter knows whether it is being served static
  `urllib` responses or a headless browser, and none should learn.
- **Adapters hold no instance state.** Instances are constructed fresh per `run()` call
  and every method takes what it needs explicitly. Caching anything on `self` breaks the
  assumption that a fresh instance is equivalent to a reused one.
- **Deliberate non-goal — no normalization, dedup, or taxonomy work here.** Adapters
  emit raw canonical `Event`s. Collapsing recurrences, cross-source merging, and
  controlled-vocabulary tagging belong to `normalize/`; doing any of it here would apply
  it inconsistently, only to whichever sources happened to implement it.

## 4. Design

**Data shapes.** `EventRef` is a URL plus a free-form `context` dict; it names one
fetchable unit, which for a paginated API is one *page*, not one event. `RawResponse`
carries the originating `ref` alongside `status` and `body`, so `extract()` can log which
page a malformed body came from. Both are inert dataclasses with no behavior.

**Why `discover()` exists at all.** For the structured-API adapters it is nearly trivial
— enumerate known page URLs. It is part of the contract anyway because it is the seam the
HTML adapters need: `generic_html` implements it as a sitemap diff and `listing_html` as
a listing-page crawl, both by delegating to `discovery/`, with no change to `base.py`. The
contract was designed for the harder case before that case existed.

**Confidence.** Structured-API adapters set `CONFIDENCE = 1.0` and record it through
`Event.set(field, value, source, confidence)`, populating `field_provenance`. That
provenance is what lets `normalize/`'s collapse and dedup stages pick the
best-supported record when two sources disagree. HTML adapters instead pass through the
per-field confidence tiers `extract/ladder.py` returns.

**HTML adapters are thin.** `generic_html.py` (88 lines) and `listing_html.py` (103
lines) each do only: call the matching `discovery/` entry point for URLs, fetch, hand the
body to `extract.extract_fields()`, and assemble an `Event` from the returned
`{field: (value, confidence)}` map. All the real extraction logic lives in `extract/`,
all the real URL-resolution logic in `discovery/` — this keeps the two HTML adapters
differing only in their discovery strategy, which is the actual distinction between them.

**ATS adapters are a filtered family.** `greenhouse` and `lever` read public job-board
JSON, then run `ats_filters.classify_posting()` to decide whether a posting is an
internship, is STEM, and is San Diego-local. Postings that survive become
`kind="internship"` Events, which are treated specially further downstream (they bypass
LLM enrichment and both normalize stages). Graduate/PhD-level postings are rejected
here; the project's audience is K-12.

**Why a Protocol rather than an ABC.** Structural typing keeps concrete adapters from
needing to inherit anything, and keeps test doubles trivial — a plain object with the
three methods is a valid `Adapter`.

## 5. Interfaces

### Exposes
- **`run(source: SourceConfig, fetcher: Fetcher) -> list[Event]`** — the whole
  subsystem's entry point. Dispatches on `source.adapter_type`, chains
  discover→fetch→extract, applies the `max_urls` cap. Raises `UnknownAdapterType` if the
  type is unregistered; per-record failures inside `extract()` are swallowed by the
  adapter itself, so this returns a possibly-short list rather than raising. A
  fetch-level failure surfaces as a `RawResponse` with a non-2xx or sentinel status,
  which `extract()` is responsible for handling.
- **`Adapter` Protocol, `EventRef`, `RawResponse`** — the contract a new adapter type
  implements.
- **`ADAPTERS: dict[str, type[Adapter]]`** — the dispatch table. Mutated exactly once per
  type, at import of `adapters/__init__.py`.
- **`get_adapter(adapter_type) -> Adapter`** — instantiates a registered adapter; raises
  `UnknownAdapterType` with the known-type list rather than a bare `KeyError`.
- **`ats_filters.classify_posting(...) -> PostingVerdict`** — shared internship/STEM/
  locality classification for the ATS adapters.
- **`acquisition_kwargs(source: SourceConfig) -> dict[str, Any]`** — **(Sprint 015
  ticket 003)** the `rate_limit_seconds`/`respect_robots` kwargs for `fetcher.get()`,
  read from `source.acquisition_policy`. Consumed by every `fetch()` implementation in
  this package and by `discovery/sitemap.py`/`discovery/listing.py`, which import it
  from here the same way they already import `EventRef` — see §2.

### Consumes
- **`Fetcher` (from `fetch/`)** — every remote read. Injected per call; see `fetch/DESIGN.md`.
- **`SourceConfig` and `DEFAULT_MAX_URLS_PER_SOURCE` (from `registry/`)** — the per-source
  data that drives dispatch and the URL cap. See `registry/DESIGN.md`.
- **`Event`, `Provenance` (from `model.py`)** — the output record. See the root
  `partner_scrape/DESIGN.md`.
- **`discover_changed_urls` / `discover_via_listing` (from `discovery/`)** — URL
  resolution for the two HTML adapters. See `discovery/DESIGN.md`.
- **`extract_fields` (from `extract/`)** — per-field values and confidences for the two
  HTML adapters. See `extract/DESIGN.md`.
- **`config.get_leaguesync_api_key` / `get_leaguesync_url` (from `config.py`)** — the
  `leaguesync` adapter's credentials, read through the one module allowed to touch
  `os.environ`.

## 6. Open Questions / Known Limitations

- There is a real circular-import hazard between `adapters.listing_html` and
  `discovery.listing`: each needs a name from the other's package. `cli.py` works around
  it by importing `partner_scrape.pipeline` before `partner_scrape.discovery`, with an
  explanatory comment. That is a load-order workaround, not a fix; the cycle should be
  broken properly (most likely by moving the shared path regex out of `discovery`).
- `EventRef.context` is an untyped `dict[str, Any]`. It works, but there is no schema and
  no cross-adapter convention for what goes in it.
- Every adapter re-implements its own `_strip_html`, `_parse_datetime`, and HTML-entity
  table. Five near-identical copies exist. Deduplication was deferred on the grounds that
  each adapter's version has drifted to fit its own source's quirks; that reasoning is
  worth re-testing.
- `bibliocommons`'s audience prefilter defaults `KEEP_IF_UNKNOWN_AUDIENCE = True`, which
  is deliberately permissive and relies on the downstream LLM relevance gate to catch
  what it lets through. If enrichment is disabled (`--no-enrich`), that safety net is
  absent.
