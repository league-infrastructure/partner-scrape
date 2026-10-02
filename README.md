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
into the data bucket that the `stem-ecosystem` site reads.

### Install

```bash
uv sync
```

### Configure

Cache and published data live in the DigitalOcean Spaces bucket
`jtl-stem-ecosystem-scrape` (`cache/` and `data/` prefixes) -- **not in
git**. For a real run set `DO_SPACES_ENDPOINT`, `DO_SPACES_ACCESS_KEY` and
`DO_SPACES_SECRET_KEY` (assembled into `.env` by `dotconfig load prod`;
`set -a; source .env; set +a`). To work locally instead, point
`SCRAPE_CACHE_DIR` and `PARTNER_SCRAPE_DATA_DIR` at local directories (a
path or an `s3://bucket/prefix` URL; see `partner_scrape/config.py`).
`SITE_DIR` is optional and defaults to the current directory (there is no
sibling checkout default). The seed registry ships inside the package
(`partner_scrape/registry_data/`); set `PARTNER_SCRAPE_REGISTRY_DIR` to a
local directory (with `sources/`, `hubs/`, `candidates/`, `ads/`) to
override it.

```bash
export SCRAPE_CACHE_DIR=/path/to/a/cache/dir
export PARTNER_SCRAPE_DATA_DIR=/path/to/a/data/dir
```

### Run

```bash
# Full run against the bundled seed registry and $SITE_DIR (or the CWD)
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

The CLI is `partner-scrape [flags]` -- there is no `run` subcommand;
`--source X` scopes the main run to one source. Other pipelines are the
`teams`, `directory` and `discover-candidates` subcommands.

Output schema: `docs/data-schema.md` (bundled in the wheel and published
to `data/SCHEMA.md` in the data bucket at the end of every non-dry-run).
`data/` is gitignored; a local `data/` is only a scratch copy.

One source's adapter failing (network error, malformed response, ...) is
logged and skipped -- it never aborts the rest of the run.

### Test

```bash
uv run pytest
```

Every test runs against recorded fixtures under `tests/fixtures/` --
no network access, no `ANTHROPIC_API_KEY` usage, no writes to the real
bucket or any `stem-ecosystem` checkout.

### Beta preview

`partner-scrape` used to host a GitHub Pages beta preview of the
`stem-ecosystem` site via `.github/workflows/pages.yml`. Publishing
from this repo was disabled 2026-09-03 (the workflow is
`disabled_manually`) when the stakeholder turned off website
publishing from this repo; the live site keeps serving its last
deploy, but no new deploy is triggered from here. The workflow file
itself is untouched and could be re-enabled in the future, but there
is currently no supported local `just dev`/`just build` workflow in
this repo for previewing it -- the repo-root `justfile` that drove
that workflow has been removed as dead weight (it `cd site/`d into a
directory that hasn't existed here since sprint 019 moved the site to
`stem-ecosystem`, and its `pub` recipe pushed `master` and dispatched
`pages.yml`, both no longer appropriate under the current push
freeze). To work on the site itself, clone
`league-infrastructure/stem-ecosystem` directly.

---

*A pre-`partner_scrape/` Scrapy-based prototype mirrored partner sites
for offline extraction before this package existed, along with a
standalone entry-point script and its Docker/Compose tooling. It has
been retired and removed from the working tree; see git history for
reference. `dev/refresh_school_directories.py` is unrelated and
remains -- it is a live, standalone maintenance script for the
`teams/` subsystem's offline geocoding data, documented in
`partner_scrape/teams/DESIGN.md`.*
