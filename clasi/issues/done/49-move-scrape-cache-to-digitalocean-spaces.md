---
status: done
sprint: 038
tickets:
- NONE
---

# Move the scrape cache to a DigitalOcean Space

> Superseded by `50-move-cache-and-data-to-digitalocean-spaces.md`, the approved plan, which settles the open questions below.

## Description

The scrape cache currently lives on local disk at `SCRAPE_CACHE_DIR`
(required; read by `get_scrape_cache_dir()` in `partner_scrape/config.py`).
That only works on one machine: `config/prod/public.env` points it at a
local Mac path, and the scheduled GitHub Actions run uses a throwaway
runner temp dir, carrying only the LLM enrichment cache forward through
`actions/cache`. Runs from different machines (or CI) don't share the
fetched-HTML mirror, the LLM enrichment cache, or the program/team
description and sponsor caches, so each environment re-fetches and
re-pays for LLM calls the others already made.

Move the cache to a DigitalOcean Space so every run, local or CI, shares
one cache.

## Credentials

Credentials are in `.env` as:

- `DO_SPACES_ENDPOINT`: currently the bucket-qualified URL
  `https://jtl-stem-ecosystem-scrape.sfo3.digitaloceanspaces.com`, i.e. bucket
  `jtl-stem-ecosystem-scrape`, region `sfo3`. The S3 client needs the
  region endpoint (`https://sfo3.digitaloceanspaces.com`) plus the bucket
  name separately; decide whether to split this into
  `DO_SPACES_ENDPOINT` + `DO_SPACES_BUCKET` or parse it.
- `DO_SPACES_ACCESS_KEY`
- `DO_SPACES_SECRET_KEY`

CI will need the same values as repo secrets on partner-scrape.

## Code that touches the cache

These modules read or write under the cache dir and all need to go through
the new backend:

- `partner_scrape/fetch/cache.py`: raw HTML/fetch mirror
- `partner_scrape/enrich/cache.py`, `enrich/enricher.py`: LLM enrichment cache
- `partner_scrape/adapters/program_cache.py`: program-page LLM extraction cache
- `partner_scrape/teams/description_cache.py`, `teams/sponsor_cache.py`
- `partner_scrape/discovery/sitemap.py`
- `partner_scrape/store/event_store.py`
- `partner_scrape/export/publish.py`, `export/partner_log.py` (check
  whether these actually use the cache dir or only the output dir)

## Open questions

- **Backend shape:** use a storage abstraction (local-dir and S3 backends
  selected by config) so tests and offline runs keep working on local disk,
  or sync a local dir to and from the Space at the start and end of a run
  (`aws s3 sync` / `rclone`)? Syncing is much less code and keeps per-item
  I/O local, but it means downloading the whole cache every run.
- **What to share:** the enrichment and extraction caches matter most,
  because they cost money to rebuild. The CI workflow deliberately
  re-fetches raw HTML weekly, so decide whether the fetch mirror belongs
  in the Space at all.
- **Concurrency:** two runs (laptop and CI) writing at once. The
  `scheduled-run` concurrency group only covers CI.
- **CI:** once this lands, drop the `actions/cache` restore/save steps in
  `.github/workflows/scheduled-run.yml`.
- **Dependency:** `boto3` (or similar) is not currently a dependency.
- **Tests** must keep running with no network access (current guarantee in
  the README), so the S3 path needs a fake or a local backend in tests.
