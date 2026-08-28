# Export

**Owner:** Eric Busboom · **Last reviewed:** 2026-08-28 · **Status:** in-flux

---

## 1. Purpose

`export/` publishes finished data across the repo boundary into the `stem-ecosystem`
Astro site's checkout(s). It is a subsystem because that boundary is a *data contract* with
another repository: file locations, JSON shapes, and field sets that the site consumes
verbatim. Concentrating every write to the site here means the contract is stated in one
place and cannot be violated by a stage that merely thought it knew the schema. It also
owns the "what is publishable" judgment — the current/upcoming filter — and the
self-hosting of remote images. Nothing upstream writes to the site.

## 2. Orientation

Four independent modules, each owning one output:

- `writer.py` · `export_opportunities(opportunities, site_dir=None, *, today=None,
  dry_run=False)` — the main contract. Filters to current+upcoming, runs a defensive
  slug-uniqueness pass, serializes exactly the site's field set (dropping
  `Opportunity.sources`), and writes `src/data/opportunities.json` and
  `src/data/scrape-meta.json`.
- `ads.py` · `export_ads(ad_configs, site_dir=None, *, dry_run=False)` plus
  `load_ad_configs(directory=None)` — a small, structurally parallel contract publishing
  hand-authored League ad-slot content as `src/data/ads.json`. Shares no code with
  `writer.py`.
- `images.py` · `EventImageDownloader(dest_dir, *, fetcher=None, min_dimension=80,
  max_bytes=5MB)` with `.download(image_url) -> str` — fetches an already-extracted remote
  image URL, quality-gates it, dedupes by content hash, and self-hosts a local copy under
  `public/images/opportunities/`.
- `mirror.py` · `mirror_site_data(primary_site_dir, target_site_dirs, *, dry_run=False)`
  — copies a *finished* export's output files (`opportunities.json`, `scrape-meta.json`,
  `ads.json`, plus the opportunity images) into additional site checkouts.

`pipeline.run()` calls `export_opportunities` and `export_ads`, and constructs the
`EventImageDownloader` it passes into `normalize.run()`. `mirror_site_data` is called by
`cli.py` *after* `run()` returns — it is not part of `pipeline.run()`.

## 3. Constraints and Invariants

- **A missing or unwritable `site_dir` fails loudly.** Both `export_opportunities` and
  `export_ads` raise rather than skipping. A silently-skipped export leaves the site
  serving stale data with no signal — the exact failure that went unnoticed for five weeks
  and motivated `mirror.py`.
- **Undated records are excluded.** An `Opportunity` with neither `date_start` nor
  `date_end` can never be judged "today or later" and does not ship. This is a filter,
  not an error.
- **`opportunity_type == "Work-based Learning"` uses a different currency rule.** An
  internship's `date_start` is the posting-observed date, routinely in the past; the
  ordinary rule would expire every still-open role. Such a record is current if
  `date_end` (the application deadline) is unset or still in the future. Every other type
  keeps the ordinary rule unchanged.
- **`export/` re-derives nothing.** No field mapping, no taxonomy, no dedup. Its inputs
  arrive finished from `normalize/`. Adding a derivation here would apply it after
  deduplication chose a winner, silently diverging from what the rest of the pipeline
  computed.
- **`Opportunity.sources` is dropped on serialization.** It is `normalize/`'s
  cross-source bookkeeping, not part of the site's Opportunities table.
- **`mirror.py` copies output; it never re-runs the pipeline.** A second run would
  re-fetch, re-enrich (paying for the LLM again), and — because `today` and every source's
  live content move between runs — could produce a *different* opportunity set per
  checkout. One export copied N times is the only way the checkouts are guaranteed to
  agree.
- **`mirror.py` copies only generated artifacts.** `partners.json` is an *input* curated
  per checkout; overwriting it would clobber one site's roster with another's.
  `yield-history.json` is per-run operational state belonging to the run that produced it.
  `MIRRORED_DATA_FILES` is the explicit allowlist.
- **`images.py` never interprets downloaded bytes as anything but a static asset,** and
  refuses any URL that is not `http(s)://` before performing any I/O — `file://`, `data:`,
  and everything else are rejected without a fetch.
- **`.download()` never raises.** A missing, unreachable, or rejected image returns `""`
  and the record exports normally with an empty `image_src`.
- **`dry_run` means no disk writes anywhere,** including image downloads. `pipeline.run()`
  does not even construct an `EventImageDownloader` under `dry_run`, and `cli.py` skips
  mirroring.
- **Deliberate non-goal — no UI, placement, or rotation decisions for ads.** `ads.json`
  is a flat, advertiser-agnostic array; how the site renders it is the site repo's own
  work.

## 4. Design

**Why `writer.py` is deliberately thin.** Its four responsibilities are filter, slug
uniqueness, serialize, write. The slug pass is defensive: `normalize/` already dedupes by
title+date+venue, but distinct records can still collide on a *truncated* slug (same org
and title on nearby dates). Fixing it properly belongs upstream; the pass here guarantees
the site never receives duplicate keys regardless.

**Why `ads.py` shares no code with `writer.py`.** They look parallel — load config,
serialize, write into `src/data/` — but they are different contracts with different
schemas and different lifecycles. The shared surface would be about six lines of JSON
writing; coupling them would mean an ad-schema change could break the opportunities
export.

**The image quality gate is ordered cheapest-first.** URL scheme → HTTP status and
non-empty body → `Content-Type` starts with `image/` → size cap → structural decode as
real PNG/JPEG/GIF/WebP → minimum dimension. The structural decode is the load-bearing
check: it catches non-image content wearing an image `Content-Type`, truncated downloads,
and HTML error pages, which a header check alone would pass. The dimension floor rejects
1×1 tracking pixels and spacer graphics.

**Deduping images by SHA-256 of raw bytes** matters because the common real case is one
generic partner-site banner reused across dozens of unrelated events. One
`EventImageDownloader` instance per run means that cache is shared across every source.

**Pixel downscaling is intentionally absent.** The recurring pipeline keeps zero external
binary dependencies (matching `fetch/`'s stdlib-only rationale), so neither Pillow nor an
ImageMagick shell-out was added. `MAX_IMAGE_BYTES` provides comparable size discipline.
The one-off partner-logo sourcing script does downscale, but it is explicitly not part of
the recurring pipeline.

**Why `mirror.py` exists, and why it is called from `cli.py`.** `export_opportunities`
writes to exactly one `site_dir`, and the pipeline resolves exactly one — the sibling
`stem-ecosystem` checkout the scheduled workflow publishes from. This repo's own `site/`
is a second, independent checkout of the same site, and nothing kept it in step: a scrape
refreshed production while the beta site the team develops against kept serving whatever
snapshot it was last handed (it sat at a five-week-old export). Mirroring is a
post-export copy, sequenced by the CLI after `run()` returns, so `pipeline.run()`'s
contract — "produce one export" — is unchanged.

**Image fetching uses its own `ImageFetcher` Protocol,** not `fetch.Fetcher`, because
images are `bytes` and `FetchResponse.body` is `str`. `UrllibImageFetcher` is the default;
tests inject a fixture.

## 5. Interfaces

### Exposes
- **`export_opportunities(opportunities, site_dir=None, *, today=None, dry_run=False) ->
  list[dict]`** — writes `src/data/opportunities.json` and `src/data/scrape-meta.json`;
  returns the payload it wrote (or would have written). Raises on an unwritable target.
- **`export_ads(ad_configs, site_dir=None, *, dry_run=False)`** — writes
  `src/data/ads.json`. Same loud-failure contract.
- **`load_ad_configs(directory=None) -> list[AdConfig]`** — parses ad TOML files
  (default `registry/ads/`). Raises `InvalidAdConfig` on a missing required field
  (`headline`, `body`, `link`, `logo_src`).
- **`EventImageDownloader(dest_dir, ...)` / `.download(image_url) -> str`** — returns the
  stored local filename, or `""` for anything rejected. Never raises. Instance-scoped
  content-hash dedup.
- **`mirror_site_data(primary_site_dir, target_site_dirs, *, dry_run=False)`** — copies
  `MIRRORED_DATA_FILES` and `public/images/opportunities/` into each target.
- **`AdConfig`, `ImageFetcher`, `UrllibImageFetcher`, `ImageFetchResponse`,
  `MIRRORED_DATA_FILES`.**

### Consumes
- **`Opportunity` (from `normalize/`)** — the input record. One-way: `export/` depends on
  `normalize/`, never the reverse. See `normalize/DESIGN.md`.
- **`config.get_site_dir()` (from `config.py`)** — the default target checkout, when the
  caller does not supply one.
- Standard library only for I/O; no dependency on `fetch/` (images use their own
  fetcher protocol).

## 6. Open Questions / Known Limitations

- Mirroring is a file copy with no verification that the target is actually a site
  checkout. Pointing `--mirror-site-dir` at the wrong directory writes JSON into it.
- The image store has no garbage collection: files for opportunities that have since
  expired are never removed from `public/images/opportunities/`.
- Image dedup is per `EventImageDownloader` instance, so it holds within a run but not
  across runs — a rerun re-downloads and rewrites identical files.
- `scrape-meta.json`'s shape is inherited from the pre-existing export script and is not
  documented anywhere in this repo.
- There is no schema validation against the site's expectations. A field rename on the
  site side surfaces as missing data on the rendered page, not as an export failure.
- `mirror.py` is recent and has not yet run through a full scheduled production cycle.
