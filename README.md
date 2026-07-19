# partner-scrape

Docker-based system that mirrors partner websites and saves full HTML content plus response headers for offline data extraction.

---

## Running the engine

`partner_scrape/` is the new aggregator engine (sprint 001) that
replaces the legacy `dev/`/`scraper/`/`run_mirrors.py` mock-up described
below. It reads a data-driven Source Registry, politely fetches and
caches each source, ingests events via a per-source adapter (The Events
Calendar REST, WordPress REST, or iCal/RSS), normalizes and deduplicates
them into the site's opportunity schema, and exports current+upcoming
opportunities into the sibling `stem-ecosystem` repo.

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

---

## Overview

`partner-scrape` crawls each partner's website (listed in `data/partners_viable.csv`), saves every text-based page as two files, and stores them in a structured mirror directory:

```
data/mirrors/
└── www.example.com/
    ├── _index/
    │   ├── content.html   ← raw HTML body
    │   └── meta.json      ← URL, HTTP status, all response headers, timestamp
    ├── about/
    │   ├── content.html
    │   └── meta.json
    └── programs/youth-education/
        ├── content.html
        └── meta.json
```

Binary resources (images, video, audio, fonts, archives, …) are intentionally **skipped** – only HTML and other text-based pages are saved.

---

## Quick Start

### Option A – Docker (recommended)

```bash
# Build the image
docker compose build

# Mirror all 153 partner sites
docker compose run scraper

# Mirror only the first 5 sites (smoke test)
docker compose run scraper --limit 5

# Resume a previously interrupted run
docker compose run scraper --resume

# Mirror a single URL
docker compose run scraper --url https://www.example.com
```

Mirrored files are written to `./data/mirrors/` on the host (volume-mounted into the container).

### Option B – Local Python

```bash
# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Mirror all partners
python run_mirrors.py

# Mirror only the first 3 (quick test)
python run_mirrors.py --limit 3

# Mirror a single URL
python run_mirrors.py --url https://www.aguahedionda.org/
```

---

## Project Layout

```
partner-scrape/
├── Dockerfile                 # Container build instructions
├── docker-compose.yml         # Compose service definition
├── requirements.txt           # Python dependencies
├── scrapy.cfg                 # Scrapy project config
├── run_mirrors.py             # Main entry-point (reads CSV, schedules crawls)
├── scraper/
│   ├── settings.py            # Scrapy settings (throttling, concurrency, …)
│   └── spiders/
│       └── mirror_spider.py   # MirrorSpider – crawls one domain, saves pages
└── data/
    ├── partners_viable.csv    # Source of truth: partner names + website URLs
    └── mirrors/               # Generated at runtime (git-ignored)
```

---

## CLI Reference

```
python run_mirrors.py [options]

Options:
  --csv PATH        Path to the partners CSV (default: data/partners_viable.csv)
  --output-dir DIR  Root directory for mirrored content (default: data/mirrors)
  --limit N         Mirror only the first N partners
  --resume          Skip partners whose mirror directory already has content
  --url URL         Mirror a single URL (bypasses the CSV)
  -h, --help        Show this help message
```

---

## Data Structure

Each crawled page produces two files inside `data/mirrors/{domain}/{url_path}/`:

| File | Contents |
|------|----------|
| `content.html` | Raw HTTP response body (HTML, plain text, XML, …) |
| `meta.json` | `url`, `status`, `headers` (full response headers), `timestamp` |

### Example `meta.json`

```json
{
  "url": "https://www.aguahedionda.org/",
  "status": 200,
  "headers": {
    "Content-Type": ["text/html; charset=UTF-8"],
    "X-Frame-Options": ["SAMEORIGIN"]
  },
  "timestamp": "2024-01-15T12:34:56.789012+00:00"
}
```

---

## Scrapy Settings Highlights

| Setting | Value | Purpose |
|---------|-------|---------|
| `ROBOTSTXT_OBEY` | `True` | Respect each site's robots.txt |
| `DOWNLOAD_DELAY` | `1 s` | Minimum delay between requests to the same domain |
| `AUTOTHROTTLE_ENABLED` | `True` | Automatically slow down when the server is under load |
| `CONCURRENT_REQUESTS_PER_DOMAIN` | `4` | Limits parallel requests per host |
| `DOWNLOAD_MAXSIZE` | `10 MB` | Skip responses larger than 10 MB |
| `DEPTH_LIMIT` | `20` | Maximum link depth per domain |

---

## Future Work

A parallel `data/scrapers/{domain}/` directory (next phase) will contain AI-generated extractor scripts that read the mirrored HTML and pull out:

- Upcoming events
- Organisation description and metadata
- Logo image URLs (for a subsequent download pass)
