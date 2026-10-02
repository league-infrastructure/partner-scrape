---
status: draft
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 038 Use Cases

## SUC-001: Run the scrape against a shared bucket-backed cache
Parent: UC (scheduled unattended run)

- **Actor**: Scheduled CI run or an operator's laptop
- **Preconditions**: `SCRAPE_CACHE_DIR=s3://jtl-stem-ecosystem-scrape/cache`, `DO_SPACES_*` credentials set; cache already uploaded in the new layout.
- **Main Flow**:
  1. Pipeline resolves the cache location through config into a Store.
  2. Fetch, enrichment, program/description/sponsor extraction, sitemap snapshots and partner_log read and write through the Store.
  3. A second run on another machine hits the same entries.
- **Postconditions**: Cache and partner_log (past-events history) persist across CI runs and machines; no actions/cache needed.
- **Acceptance Criteria**:
  - [ ] All seven cache areas use the stakeholder-specified key layout.
  - [ ] Suite passes offline with LocalStore; S3Store covered by moto.
  - [ ] Program-extraction cache key includes the profile (issue 42).

## SUC-002: Publish data output to the bucket
Parent: UC (publish refreshed data)

- **Actor**: Scheduled CI run / operator
- **Preconditions**: `PARTNER_SCRAPE_DATA_DIR=s3://jtl-stem-ecosystem-scrape/data`.
- **Main Flow**:
  1. Writers emit the same keys as today's `data/` through the data Store, with content types.
  2. Images skip upload when the content-hash key exists.
  3. yield-history.json is read back and rewritten via the Store; bucket versioning keeps history.
  4. SCHEMA.md is published to `data/SCHEMA.md`.
- **Postconditions**: `data/` no longer in git; downstream (stem-ecosystem) can fetch from the bucket.
- **Acceptance Criteria**:
  - [ ] Output keys identical to the prior `data/` layout.
  - [ ] `git ls-files data/` is empty; CI has no git-publish step and `contents: read`.

## SUC-003: Consume bucket data from stem-ecosystem
Parent: UC (site build)

- **Actor**: stem-ecosystem maintainer
- **Main Flow**: run `scripts/fetch-data.sh` in bucket mode; it syncs `data/` to a temp dir then runs the existing copy list and image check.
- **Postconditions**: site builds from bucket data.
- **Acceptance Criteria**:
  - [ ] Bucket mode works; existing mode unchanged.

## SUC-004: Install and run partner-scrape from a wheel
Parent: UC (distribution)

- **Actor**: Any user with pip/pipx
- **Preconditions**: Only `SCRAPE_CACHE_DIR` (and optional location settings) set.
- **Main Flow**: `pipx install partner-scrape`; `partner-scrape --help`; dry run against the bundled registry.
- **Postconditions**: Works without a repo checkout; no module resolves defaults through `REPO_ROOT`.
- **Acceptance Criteria**:
  - [ ] CI smoke test builds the wheel, installs into a clean venv in a temp dir, runs `--help` and a dry run.
  - [ ] Tag-triggered trusted-publishing workflow exists (name claim and PyPI trusted-publisher setup are operator steps).

## SUC-005: Catch schema-doc drift
Parent: UC (data contract documentation)

- **Actor**: Developer adding a schema field
- **Main Flow**: add a field to a `*_SCHEMA_FIELDS` constant without updating `docs/data-schema.md`; suite fails naming the constant and field.
- **Acceptance Criteria**:
  - [ ] Test targets the docs location and covers the five constants (in order).
