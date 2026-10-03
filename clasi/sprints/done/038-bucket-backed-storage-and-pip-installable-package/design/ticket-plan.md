# Sprint 038 ticket plan (draft; create via create_ticket once stakeholder_approval gate passes)

Common: each ticket updates affected DESIGN.md per design/ overlays; runs `uv run pytest`; offline tests only.

001 Add storage module (issue 50). SUC-001/002. deps: none.
 - partner_scrape/storage.py: Store protocol (read_bytes->None on missing, write_bytes(key,data,content_type), read/write_text, read/write_json (indent=2), exists, list(prefix)); LocalStore(root) with atomic temp+os.replace (move _atomic_write_text from export/partner_log.py, keep re-export or update callers); S3Store(bucket,prefix,client) mapping NoSuchKey/404 to None; store_from_location(str|Path). storage must not import config.
 - pyproject: boto3 dep, moto[s3] dev. tests/test_storage.py both backends (moto): missing->None, round trip, prefix, content type, list, LocalStore atomicity/no .tmp left.
002 Config Store factories (50). deps 001.
 - config.py: DO_SPACES_ENDPOINT (region endpoint; validate not bucket-qualified), DO_SPACES_ACCESS_KEY/SECRET_KEY, lazy shared boto3 client, get_scrape_cache_store() (SCRAPE_CACHE_DIR path or s3://, defaults to s3://jtl-stem-ecosystem-scrape/cache; local only if set explicitly), get_data_store() reading PARTNER_SCRAPE_DATA_DIR (default s3://jtl-stem-ecosystem-scrape/data; keep get_own_data_dir only if still needed as thin wrapper). Missing DO_SPACES_* with an s3 location fails loudly with an actionable message naming the missing vars. tests/conftest.py autouse fixture sets both locations to tmp_path, plus a guard failing any test that builds an S3Store for the real bucket without moto. Tests with monkeypatch env + moto.
003 Rewire fetch/sitemap/partner_log (50). deps 002.
 - fetch/cache.py: _HOSTS_SUBDIR="hosts"; key hosts/<domain>/<sha>.json; keep cache_path(); read/write_cache_entry, touch_fetch_timestamp, PoliteFetcher.__init__ via Store; update test_fetch_cache.py ~:222,:774,:799.
 - discovery/sitemap.py: _SNAPSHOT_SUBDIR="sitemaps", use get_scrape_cache_store().
 - export/partner_log.py + export/publish.py: partner_log/ via Store, drop duplicate constant (single source), _default_log_dir.
 - Constructors keep cache_dir: Path|None wrapped in LocalStore.
004 Rewire LLM caches (50, 42). deps 002.
 - enrich/cache.py -> enrichment/; adapters/program_cache.py -> programs/ with profile in key; NO legacy-key read fallback (stakeholder decision); ~67 existing programs/ entries re-extract once; teams/description_cache.py -> descriptions/; teams/sponsor_cache.py -> sponsors/. Test: same URL+body under two profiles -> distinct entries. Resolve adapters/DESIGN.md Open Question. Completes issue 42.
005 Data output through data Store (50). deps 002.
 - export/writer.py, export/ads.py, export/publish.py, export/images.py (store + images/opportunities/ prefix, skip if exists, image content-type), teams/export.py, directory/export.py, observability/snapshot.py (yield-history.json), dev/backfill_missing_images.py, pipeline.py/cli.py call sites. Keys identical to today's data/. Content-Type application/json or image/*. Fix docstrings claiming data is committed.
006 Config redesign (51, 50). deps 005.
 - git mv registry/ -> partner_scrape/registry_data/ (sources,hubs,candidates,ads); PARTNER_SCRAPE_REGISTRY_DIR override (location string; local path only now); registry/loader.py, hub_schema.py, candidates.py, export/ads.py defaults; SITE_DIR required or CWD (no ../stem-ecosystem); cache/data locations default to the bucket (explicit local only), verify no test can hit the real bucket; remove REPO_ROOT and DEFAULT_OWN_DATA_DIR/DEFAULT_SITE_DIR; grep guard test "no REPO_ROOT in partner_scrape/". hatch include for data. Existing registry-reading tests keep passing. Update docs referencing registry/ paths and CI/just/scripts.
007 Persist settings + CI (50). deps 003-006.
 - config/prod/public.env: SCRAPE_CACHE_DIR=s3://jtl-stem-ecosystem-scrape/cache, (PARTNER_SCRAPE_DATA_DIR too, though matching defaults), DO_SPACES_ENDPOINT=https://sfo3.digitaloceanspaces.com. config/prod/secrets.env via sops: access/secret key (if sops key unavailable, document and hand to operator). scheduled-run.yml: remove actions/cache steps and the `git add data/` publish step, pass DO_SPACES_* secrets, contents: read. Update docs/deploy/scheduled-run.md. Note SITE_REPO_TOKEN missing is operator task.
008 Real-bucket verification (50). deps 007.
 - Opt-in pytest marker `bucket` (skipped by default) + dev/verify_bucket.py: object counts per cache folder/data vs expectations, spot byte comparison, one-source run with s3 cache shows cache hits and no new LLM calls; partner_log updated. Record results in ticket. If credentials unavailable, escalate to team-lead, do not skip silently.
009 Remove data/ from git (50). deps 008.
 - git rm -r --cached data/, .gitignore data/; git mv data/SCHEMA.md docs/data-schema.md; wheel-bundle it and publish to data/SCHEMA.md in the data Store at end of a run (or via small command); fix SCHEMA.md line 6 text, snapshot.py docstring, docs/deploy/scheduled-run.md.
010 Drift guard (46). deps 009.
 - tests parse docs/data-schema.md field lists vs SITE/TEAMS/PLACES/CLUBS/OFFERINGS_SCHEMA_FIELDS exact order, message names constant+field; do not pin classifier prompt lists; optional enum-backed vocabularies only if cheap.
011 stem-ecosystem bridge (50). deps 009. CROSS-REPO: edit /Users/eric/proj/league/infrastructure/stem-ecosystem/scripts/fetch-data.sh, commit in that repo.
 - bucket source mode: `aws s3 sync s3://jtl-stem-ecosystem-scrape/data/ <tmp>` then existing copy list + image check; existing mode unchanged; document usage. Deploy workflow stays manual.
012 Packaging (51). deps 006, 009.
 - Re-check requires-python; decide DESIGN.md in wheel; CI workflow: build wheel, fresh venv in temp dir, `partner-scrape --help` (no bucket credentials needed) + dry run with SCRAPE_CACHE_DIR and PARTNER_SCRAPE_DATA_DIR set explicitly to local temp dirs; tag-triggered trusted-publishing workflow (.github/workflows/publish.yml); README pip/pipx + playwright install chromium. Operator: claim PyPI name, configure trusted publisher.
