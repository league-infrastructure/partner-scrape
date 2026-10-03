---
id: 038
title: Bucket-backed storage and pip-installable package
status: planning-docs
branch: sprint/038-bucket-backed-storage-and-pip-installable-package
use-cases:
- SUC-001
- SUC-002
- SUC-003
- SUC-004
- SUC-005
issues:
- 50-move-cache-and-data-to-digitalocean-spaces.md
- 49-move-scrape-cache-to-digitalocean-spaces.md
- 51-make-partner-scrape-a-pip-installable-standalone-package.md
- 46-schema-doc-drift-guard.md
- 42-program-extraction-cache-key-omits-profile.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 038: Bucket-backed storage and pip-installable package

## Goals

Make the repo hold only code: cache and published data live in the DigitalOcean Spaces bucket `s3://jtl-stem-ecosystem-scrape` (sfo3), read and written directly through a small Store abstraction; and make `partner-scrape` a pip-installable standalone package with no `REPO_ROOT`-relative defaults.

## Problem

State is spread over a machine-local cache folder, generated `data/` committed to git (563 MB), and repo-root-relative config. CI and laptops do not share the cache, CI discards `partner_log/` every run, and an installed wheel cannot find its registry or data dirs.

## Solution

1. New `partner_scrape/storage.py` (Store protocol, LocalStore, S3Store/boto3, `store_from_location`).
2. Rewire the seven cache modules to the stakeholder layout (`hosts/`, `enrichment/`, `programs/`, `descriptions/`, `sponsors/`, `sitemaps/`, `partner_log/`); program cache key gains the profile (issue 42) in the same change.
3. Route all `data/` writers through a data Store (`PARTNER_SCRAPE_DATA_DIR`, local path or `s3://`).
4. One coherent config redesign in `config.py`: every location is a setting, no REPO_ROOT defaults; registry bundled in the package with an override setting (issue 51 option c).
5. Persist settings in dotconfig, update CI, remove `data/` from git, move SCHEMA.md to `docs/data-schema.md`, add the drift guard (issue 46).
6. Cross-repo: stem-ecosystem `scripts/fetch-data.sh` bucket mode.
7. Wheel smoke test + trusted-publishing workflow + README.

## Success Criteria

- `uv run pytest` green and offline; moto covers S3Store.
- Real-bucket verification (opt-in) shows cache hits against the pre-uploaded cache and correct object counts.
- `git ls-files data/` empty; scheduled-run.yml has no actions/cache or git-publish step, `contents: read`.
- Wheel installed in a clean venv runs `--help` and a dry run with `--help` needing no credentials and a dry run using explicit local dirs.

## Scope

### In Scope

Issues 50 (phases 1-2), 49 (superseded), 51, 46, 42. Verification against the already-uploaded bucket contents. Cross-repo ticket in stem-ecosystem.

### Out of Scope

- The one-time `aws s3 sync` upload (done by stakeholder); enabling bucket versioning (operator `aws s3api put-bucket-versioning`).
- Issue 50 phases 3 and 4 (stem-ecosystem builds from bucket; `config/` in bucket; `config pull/push`). The registry override setting is designed so it could later point at the bucket, but bucket-backed registry loading is NOT implemented.
- `store/event_store.py` (SQLite, unwired) stays local-only.

### Operator tasks (not tickets)

- Enable bucket versioning on `jtl-stem-ecosystem-scrape`. This must be done with a full-access Spaces key: the bucket-scoped project key got AccessDenied on PutBucketVersioning.
- `SITE_REPO_TOKEN` will not be provisioned: partner-scrape is being consolidated with stem-ecosystem into one repo, so the weekly job's verify step will keep failing until then. The package is likewise not published to PyPI for the same reason.
- Correct the `.env` `DO_SPACES_ENDPOINT` (it is bucket-qualified); ticket 006 persists the correct value in dotconfig.
- Add `DO_SPACES_*` secrets to GitHub Actions.

## Test Strategy

Offline suite via LocalStore/tmp_path. `tests/test_storage.py` tests both backends (moto for S3: missing key -> None, round trip, prefix keys, content type). Existing cache tests updated for new folder names (test_fetch_cache.py ~:222, :774, :799). Registry-reading tests (test_registry.py, test_registry_candidates.py, teams/directory dataset-validity) must keep passing against the bundled registry. Real-bucket checks are an opt-in, default-skipped marker. Wheel smoke test in CI.

## Architecture Notes

See `architecture-update.md` and `design/` overlays. Key decisions: Store abstraction in a new leaf module; cache modules accept `cache_dir: Path | None` and wrap paths in LocalStore; data both locations default to the bucket (local dir only when set explicitly; tests forced local by an autouse fixture/guard; missing credentials fail loudly); registry bundled under `partner_scrape/registry_data/`; SCHEMA.md published from a wheel-bundled copy.

## GitHub Issues

None.

## Definition of Ready

- [x] Sprint planning documents are complete (sprint.md, use cases, architecture)
- [x] Architecture review passed
- [ ] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Depends On |
|---|-------|------------|
| 001 | Add storage module: Store protocol, LocalStore, S3Store | - |
| 002 | Config: Store factories, bucket defaults and DO_SPACES settings | 001 |
| 003 | Rewire fetch, sitemap and partner_log caches to Store and new layout | 002 |
| 004 | Rewire LLM caches to Store and new layout; profile in program key | 002 |
| 005 | Route data output through the data Store | 002 |
| 006 | Config redesign: bundled registry, no REPO_ROOT defaults | 005 |
| 007 | Persist settings in dotconfig and update scheduled-run CI | 003, 004, 005, 006 |
| 008 | Verify against the real bucket (opt-in) | 007 |
| 009 | Remove data/ from git; move SCHEMA.md and publish it | 008 |
| 010 | Schema doc drift guard | 009 |
| 011 | stem-ecosystem fetch-data.sh bucket mode (cross-repo) | 009 |
| 012 | Wheel smoke test, publish workflow, README | 006, 009 |
| 013 | Drop PyPI publishing | 012 |

Tickets execute serially in the order listed.
