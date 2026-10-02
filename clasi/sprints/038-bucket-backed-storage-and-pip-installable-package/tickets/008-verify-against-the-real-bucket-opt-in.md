---
id: 008
title: Verify against the real bucket (opt-in)
status: in-progress
use-cases:
- SUC-001
- SUC-002
depends-on:
- '007'
github-issue: ''
issue: 50-move-cache-and-data-to-digitalocean-spaces.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Verify against the real bucket (opt-in)

## Description

Verify code against the pre-uploaded bucket before data leaves git.

## Acceptance Criteria

- [ ] Opt-in pytest marker `bucket` (skipped by default) and `dev/verify_bucket.py`
- [ ] Object counts under each `cache/` folder and `data/` match expectations from the local trees (data/ minus mirrors/)
- [ ] Spot-check byte-identity of sample objects
- [ ] A one-source run (e.g. coastalrootsfarm) with the s3 cache shows cache hits and no new LLM calls for unchanged content; partner_log for that source updated
- [ ] Results recorded in the ticket; if credentials are unavailable, escalate to team-lead rather than skipping

## Implementation Plan

Read/limited-write against real bucket only through the opt-in path.
See design/ticket-plan.md and architecture-update.md. Update affected DESIGN.md files.

## Testing

- **Existing tests to run**: `uv run pytest` (all offline)
- **New tests to write**: as listed in acceptance criteria
- **Verification command**: `uv run pytest`

## Results (2026-10-02, real bucket s3://jtl-stem-ecosystem-scrape)

- `dev/verify_bucket.py check`: cache/ 22,852 objects (enrichment 17301, hosts 5113,
  partner_log 202, sitemaps 82, programs 67, descriptions 53, sponsors 34; baselines
  recorded since the local cache tree no longer exists, compared with >=). data/ 917
  objects == 917 local files minus mirrors/, none missing, none extra. All 917 local
  data files byte-identical (md5 == ETag); 25 sampled cache objects parse as JSON.
- Pytest marker `bucket` (`--run-bucket` / `RUN_BUCKET_TESTS=1`); default `uv run pytest`
  skips them: 2605 passed, 2 skipped. With the opt-in: 11 passed.
- Safety: the run's data Store is always `s3://.../verify/<ts>/data` (scratch, deleted
  afterwards); live data/ prefix refused by validation and a process-wide write guard;
  data/ ETags+LastModified of all 917 objects identical before/after.
- One-source runs (`--source`):
  - sandiegoarchaeology: 262 events; enrichment cache 241 hits / 21 misses; 21 LLM calls
    (exactly the misses, i.e. none for unchanged events); 7 page-cache hits (all 200,
    no ETag revalidation); +21 enrichment objects, 7 hosts entries rewritten;
    partner_log/san_diego_archaeological_center/{partner.json,opportunities.jsonl}
    updated; 9 opportunities.
  - coastalrootsfarm run 1: 3 events, 2 enrichment hits / 1 miss, 3 LLM calls (2 re-enriched:
    unversioned legacy entries or changed content); run 2: 3 hits, 0 LLM calls, 2 of 4
    HTTP fetches revalidated 304. 0 opportunities produced so no partner_log write.
- Note: ~17% of sampled enrichment entries lack schema_version/prompt_version (legacy) and
  will be re-enriched once, then are rewritten with versions.
