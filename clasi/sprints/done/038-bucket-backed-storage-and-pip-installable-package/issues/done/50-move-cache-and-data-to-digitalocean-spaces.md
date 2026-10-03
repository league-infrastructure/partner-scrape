---
status: done
sprint: 038
tickets:
- 038-001
- 038-002
- 038-003
- 038-004
- 038-005
- 038-006
- 038-007
- 038-008
- 038-009
- 038-011
---

# Move partner-scrape's cache and data into the DigitalOcean Spaces bucket

## Context

partner-scrape currently keeps state in three local places:
- the scrape cache, a folder on whichever machine runs it (`SCRAPE_CACHE_DIR`, `/Volumes/Cache/stem-ecosystem`, 1.6 GB, 22,853 files);
- its published output in git under `data/` (563 MB, mostly images and dead mirrors);
- configuration spread across `registry/`, `partner_scrape/teams/`, `partner_scrape/directory/`, and stem-ecosystem's curated `partners.json`.

Because of this, CI and laptops don't share the cache. CI throws away `partner_log/` every run, so past-events would be lost. The repo also carries generated data.

**Goal:** the repo holds only code. Everything else lives in bucket `jtl-stem-ecosystem-scrape` (region sfo3). Later, stem-ecosystem builds from the bucket. You chose to have the code read and write the bucket directly, with no sync step around each run, and to move all configuration out of the repo eventually.

This plan specifies **phase 1 (cache)** and **phase 2 (data output)** in detail, and outlines phases 3 and 4. It supersedes the open questions in `clasi/issues/49-move-scrape-cache-to-digitalocean-spaces.md`. That issue will be updated, and a second issue added for the data output. Execution runs as a CLASI sprint: sprint-planner writes the tickets, and a programmer executes them.

## Bucket layout

```
s3://jtl-stem-ecosystem-scrape/
  cache/                       # old SCRAPE_CACHE_DIR tree, reorganized (see rename table)
    hosts/<hostname>/<sha256(url)>.json   raw HTTP cache (fetch/cache.py)
    enrichment/<sha>.json                 LLM enrichment (expensive to rebuild)
    programs/<sha>.json                   program-page LLM extraction
    descriptions/<sha>.json               team description extraction
    sponsors/<sha>.json                   team sponsor extraction
    sitemaps/<source_id>.json             sitemap lastmod snapshots
    partner_log/<slug>/{partner.json,opportunities.jsonl}   # irreplaceable past-events history
  data/                        # byte-for-byte today's repo data/ (minus mirrors/)
    opportunities.json  scrape-meta.json  ads.json  partners.json
    partners/<slug>/{events,past-events}.json
    teams.json  clubs.json  places.json  offerings.json
    yield-history.json  SCHEMA.md
    images/opportunities/<sha16>.<ext>
  config/                      # phase 4 (outline only)
```

The top level of `cache/` holds only short named subfolders: no `_cache` or `extraction` in the names. The mapping from the old drive is:

| Old folder on `/Volumes/Cache/stem-ecosystem` | Bucket key under `cache/` | Constant to change |
|---|---|---|
| `<hostname>/` (243 folders) | `hosts/<hostname>/` | new `_HOSTS_SUBDIR` in `fetch/cache.py` |
| `enrichment_cache/` | `enrichment/` | `enrich/cache.py` |
| `program_extraction_cache/` | `programs/` | `adapters/program_cache.py` |
| `description_extraction_cache/` | `descriptions/` | `teams/description_cache.py` |
| `sponsor_extraction_cache/` | `sponsors/` | `teams/sponsor_cache.py` |
| `sitemap_snapshots/` | `sitemaps/` | `_SNAPSHOT_SUBDIR` in `discovery/sitemap.py` |
| `partner_log/` | `partner_log/` (unchanged) | `_LOG_SUBDIR` in `export/partner_log.py` and its copy in `export/publish.py` |

The files inside each folder keep their names and contents. A local cache in the old layout simply misses until it's re-fetched, which is fine because the bucket is now the cache. `data/mirrors/` comes from the deleted Scrapy prototype and no current code reads it, so it is not uploaded. `store/event_store.py` (SQLite) is not wired into anything and stays local-only.

## Step 0: one-time upload (right after approval, needs no code)

The aws CLI is already at `/opt/homebrew/bin/aws`. Set credentials from `.env` (`AWS_ACCESS_KEY_ID=$DO_SPACES_ACCESS_KEY`, `AWS_SECRET_ACCESS_KEY=$DO_SPACES_SECRET_KEY`) and use `--endpoint-url https://sfo3.digitaloceanspaces.com`:

1. Upload the cache following the rename table. Every run excludes `*.tmp` and `events.db`.
   - **Named caches:** for each old/new pair in the table, run `aws s3 sync /Volumes/Cache/stem-ecosystem/<old> s3://jtl-stem-ecosystem-scrape/cache/<new>/`.
   - **Host folders:** run `aws s3 sync /Volumes/Cache/stem-ecosystem s3://jtl-stem-ecosystem-scrape/cache/hosts/`, adding an `--exclude '<old>/*'` for each of the 6 named folders.
   - The local drive is left untouched.
2. `aws s3 sync data/ s3://jtl-stem-ecosystem-scrape/data/ --exclude 'mirrors/*'`. The CLI sets content types from file extensions.
3. Verify: object counts with `aws s3 ls --recursive --summarize` match `find -type f | wc -l` for each tree, and spot-check that a few files are byte-identical.

## Phase 1: cache reads and writes the bucket directly

**New module `partner_scrape/storage.py`:** a small `Store` protocol with `read_bytes(key) -> bytes | None` (None means missing), `write_bytes(key, data, content_type=None)`, `read_text`/`write_text`/`read_json`/`write_json` helpers, `exists(key)`, and `list(prefix)`. It has two implementations:
- **`LocalStore(root: Path)`** keeps today's behavior: it creates parent folders, and its writes are atomic (temp file, then `os.replace`). That rename helper moves here from `export/partner_log.py` (`_atomic_write_text`) so every local write gets it.
- **`S3Store(bucket, prefix, client)`** uses boto3 and maps `NoSuchKey`/404 to None. A single PUT is already atomic in S3.

`store_from_location(str | Path) -> Store` treats `s3://bucket/prefix` as an S3Store and anything else as a LocalStore. Add `boto3` to the dependencies and `moto[s3]` to the dev group.

**`config.py`:**
- `get_scrape_cache_store()` wraps `SCRAPE_CACHE_DIR`, which now accepts a local path or `s3://...`. It is still required.
- New `DO_SPACES_ENDPOINT` (the region endpoint `https://sfo3.digitaloceanspaces.com`), plus `DO_SPACES_ACCESS_KEY` and `DO_SPACES_SECRET_KEY`.
- One boto3 client is built lazily and reused, since boto3 clients are safe to share across threads.
- The current `.env` value has the bucket name in the endpoint URL. It moves into the `s3://` location instead.

**Rewire the 7 cache modules to use the Store:**
- Today each one does `path.exists()`, then `open`/`json.load`, and `mkdir`, then `json.dump`.
- Each becomes `store.read_json(key)` / `store.write_json(key, …)`. The folder part of each key changes per the rename table, the file names stay the same, and the JSON stays `indent=2` so objects match the uploaded files.
- Constructors keep accepting `cache_dir: Path | None`, and a Path is wrapped in a `LocalStore`. Most tests that pass `tmp_path` therefore need no changes.

The modules:
- **`fetch/cache.py`:** `cache_path`, `read_cache_entry`, `write_cache_entry`, `touch_fetch_timestamp` and `PoliteFetcher.__init__`.
  - The key becomes `hosts/<domain>/<sha256(url)>.json`, defined in one constant `_HOSTS_SUBDIR = "hosts"`.
  - Keep `cache_path()` and update the tests that check it (`test_fetch_cache.py` :222, :774, :799).
- **The five renamed folders:** change each module's folder constant per the table, and update any test that asserts the old folder name.
- **`enrich/cache.py`:** `EnrichmentCache`
- **`adapters/program_cache.py`:** `ProgramExtractionCache`
- **`teams/sponsor_cache.py`, `teams/description_cache.py`**
- **`discovery/sitemap.py`:** `_snapshot_path` / `_read_snapshot` / `_write_snapshot`. These currently call config inline; switch them to `get_scrape_cache_store()`.
- **`export/partner_log.py` and `export/publish.py`:** the `partner_log/` reads and writes, and `_default_log_dir`

**Settings and CI:**
- Make the settings permanent. The `DO_SPACES_*` values currently exist only in `.env` and would be wiped by the next `dotconfig load`.
  - `config/prod/public.env`: `SCRAPE_CACHE_DIR=s3://jtl-stem-ecosystem-scrape/cache` and `DO_SPACES_ENDPOINT`
  - `config/prod/secrets.env`, encrypted with SOPS: the two keys
- `scheduled-run.yml`:
  - pass the `DO_SPACES_*` secrets and the s3 `SCRAPE_CACHE_DIR`
  - delete the `actions/cache` restore and save steps for `enrichment_cache`
  - CI then keeps `partner_log` between runs, which fixes past-events being wiped in CI

## Phase 2: published output goes to the bucket's `data/`

**`config.py`:** `get_own_data_dir()` becomes `get_data_store()`. It reads a new `DATA_DIR`, a local path or `s3://...`, and defaults to `<repo>/data` so local dev and tests keep working. Prod config sets `DATA_DIR=s3://jtl-stem-ecosystem-scrape/data`.

**Writers to switch to `data_store.write_*`.** Same keys, and set Content-Type to `application/json` or `image/*`.
- `export/writer.py` (`opportunities.json`, `scrape-meta.json`)
- `export/ads.py`
- `export/publish.py` (`partners.json` and `partners/<slug>/*`)
- `export/images.py` (`EventImageDownloader`). It currently takes `dest_dir`; it should take a store plus the `images/opportunities/` prefix. Before uploading, it skips the write if `exists(key)`, since the names are content hashes.
- `teams/export.py`
- `directory/export.py`
- `observability/snapshot.py` (`load_snapshot` / `save_snapshot` of `yield-history.json`, the one file in `data/` that is read back as state)
- `dev/backfill_missing_images.py`, which hardcodes `REPO_ROOT/"data"`, moves to the store as well.

**Turn on bucket versioning** (`aws s3api put-bucket-versioning`) so `data/`, and especially `yield-history.json`, keep a history. Git history served that purpose until now.

**Remove `data/` from git:**
- `git rm -r --cached data/` and add `data/` to `.gitignore`.
- Move `data/SCHEMA.md` to `docs/data-schema.md` as the source copy, and publish it to `data/SCHEMA.md` in the bucket. Update issue 46 (drift guard) to point at the new location.
- Fix the text that says the data is committed to git: `data/SCHEMA.md` line 6, the `snapshot.py` docstring, and `docs/deploy/scheduled-run.md`.

**CI:** delete the "Publish refreshed data to partner-scrape's own data/" step (`git add data/` and push), and change `contents: write` to `read`.

**stem-ecosystem bridge, so the site doesn't go stale once `data/` leaves git:**
- `scripts/fetch-data.sh` gains a source mode: `aws s3 sync s3://…/data/` into a temp folder, then the existing explicit copy list and image check run unchanged.
- Its deploy workflow stays manual until phase 3.

## Later phases (outline only)

- **Phase 3:** stem-ecosystem's `build.yml` and `deploy.yml` sync from the bucket at build time, which re-applies the reverted `8b7ad08` with an s3 source. A finished scrape triggers a deploy (`repository_dispatch` or a schedule). The repo stops tracking generated `src/data/*` and `public/data/**`.
- **Phase 4, configuration into `config/` in the bucket:**
  - **What moves:** `registry/{sources,candidates,hubs,ads}`, `partner_scrape/teams/{registry,data}`, `partner_scrape/directory/{registry,data}`, and stem-ecosystem's curated `src/data/partners.json` plus `public/images/logos/`.
  - **New commands:** `partner-scrape config pull` and `partner-scrape config push` for editing.
  - **Tests:** some tests currently read the real committed config through `DEFAULT_SOURCES_DIR`, the teams/directory `DEFAULT_*` paths and the dataset-validity tests. They need fixture snapshots or an opt-in mark.
  - **Removals:** `SITE_DIR` and the read-only stem-ecosystem checkout in CI (`SITE_REPO_TOKEN`).

## Verification

- `uv run pytest`: the full suite (about 1,800 tests) passes with no network access, using LocalStore through `tmp_path`. New `tests/test_storage.py` covers both backends, with `moto` mocking S3: read of a missing key returns None, a write followed by a read returns the same bytes, keys are built correctly with a prefix, and content type is set.
- After phase 1, against the real bucket:
  - Run `uv run partner-scrape --source coastalrootsfarm` with the s3 `SCRAPE_CACHE_DIR`. It should hit cache entries that were uploaded from the old drive: the yield report shows cached responses and no new LLM calls for unchanged events.
  - The object count under `cache/` grows only by new URLs.
  - `aws s3 ls cache/partner_log/` shows that partner's updated log.
- After phase 2:
  - A full `uv run partner-scrape` writes `data/opportunities.json` and `scrape-meta.json` into the bucket with a fresh `last_updated`. `yield-history.json` gets a new version.
  - Run `scripts/fetch-data.sh` in stem-ecosystem from the bucket. Its image check passes, and `npm run build` succeeds.
  - `git status` in partner-scrape shows no `data/`.
