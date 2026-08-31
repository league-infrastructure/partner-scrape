# partner-scrape

The San Diego STEM Ecosystem event aggregator engine: fetches and
normalizes opportunities from partner organizations' websites and
exports them into the `stem-ecosystem` site.

---

## Running the engine

`partner_scrape/` is the aggregator engine (sprint 001 onward). It reads
a data-driven Source Registry, politely fetches and caches each source,
ingests events via a per-source adapter (The Events Calendar REST,
WordPress REST, or iCal/RSS), normalizes and deduplicates them into the
site's opportunity schema, and exports current+upcoming opportunities
into the sibling `stem-ecosystem` repo.

### Install

```bash
uv sync
```

### Configure

Set `SCRAPE_CACHE_DIR` (required -- no safe default; see
`partner_scrape/config.py`) before running for real. `SITE_DIR` is
optional and defaults to `../stem-ecosystem`.

```bash
export SCRAPE_CACHE_DIR=/path/to/a/cache/dir
```

### Run

```bash
# Full run against the real seed registry and ../stem-ecosystem
uv run partner-scrape

# See the payload that would be written, without touching disk
uv run partner-scrape --dry-run

# Point at a different registry dir / site checkout
uv run partner-scrape --registry-dir path/to/sources --site-dir path/to/stem-ecosystem

# Smoke-test a single source, or just the first few
uv run partner-scrape --source coastalrootsfarm
uv run partner-scrape --limit 3

# -m works too, without the console script
uv run python -m partner_scrape.cli --dry-run
```

One source's adapter failing (network error, malformed response, ...) is
logged and skipped -- it never aborts the rest of the run.

### Test

```bash
uv run pytest
```

Every test runs against recorded fixtures under `tests/fixtures/` --
no network access, no `ANTHROPIC_API_KEY` usage, no writes to the real
`../stem-ecosystem` checkout.

### Beta preview

`partner-scrape` also hosts a GitHub Pages beta preview of the
`stem-ecosystem` site (`.github/workflows/pages.yml`). `site/` is
**not** tracked content in this repo -- the workflow's build job
checks out `league-infrastructure/stem-ecosystem` at `ref: master`
into `site/` at build time, so the beta always builds from
stem-ecosystem's actual current source. For local `just dev`/`just
build`, clone `stem-ecosystem` yourself into a gitignored `site/`
directory (or point the `justfile`'s `site :=` variable elsewhere);
see the `justfile` for details.

---

*A pre-`partner_scrape/` Scrapy-based prototype mirrored partner sites
for offline extraction before this package existed, along with a
standalone entry-point script and its Docker/Compose tooling. It has
been retired and removed from the working tree; see git history for
reference. `dev/refresh_school_directories.py` is unrelated and
remains -- it is a live, standalone maintenance script for the
`teams/` subsystem's offline geocoding data, documented in
`partner_scrape/teams/DESIGN.md`.*
