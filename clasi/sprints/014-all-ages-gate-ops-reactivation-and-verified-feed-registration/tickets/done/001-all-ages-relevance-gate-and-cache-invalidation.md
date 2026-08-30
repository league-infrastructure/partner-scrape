---
id: '001'
title: All-ages relevance gate and cache invalidation
status: done
use-cases:
- SUC-001
- SUC-002
- SUC-003
depends-on: []
github-issue: ''
issue: 22-all-ages-relevance-gate.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# All-ages relevance gate and cache invalidation

## Description

Widen `enrich/llm_client.py`'s relevance-gate prompt from "STEM learning
opportunity for youth (not an adult-only program)" to "STEM learning
opportunity for any audience," matching the site's own "learners of all
ages" framing and its existing `Adult` age facet, while leaving noise
rejection (non-STEM recreation, galas, closure notices, nav pages)
unchanged. Because `enrich/cache.py`'s content hash deliberately covers
only an event's input fields, not the prompt, add an independent
`PROMPT_VERSION` cache-key component so the ~9,700 pre-existing cache
entries — written under the old, narrower prompt — each get exactly one
forced re-evaluation on the next run, rather than staying permanent,
silent hits under the new prompt. See `sprint.md`'s Architecture section
and `design/enrich-DESIGN.md` for the full design and rationale.

Stakeholder decision (Eric, 2026-08-30): all ages, not K-12-only. Of
6,598 cached `relevant: false` verdicts, 1,027 are adult/professional
programs — the reason UC San Diego Extended Studies (300 found -> 0
published), Salk (126 -> 0), Qualcomm (49 -> 0), sandiego.gov (299 -> 0),
and Fleet's own adult partner series publish nothing today, despite the
adapters already finding them.

## Acceptance Criteria

- [ ] `enrich/llm_client.py`'s `_SYSTEM_PROMPT` judges `relevant` as "a
      STEM learning opportunity for any audience (children, teens,
      families, adults, educators, college-bound students)"; noise
      rejection language (non-STEM recreation, galas, closure notices,
      press releases, nav pages, no-content records) is unchanged.
- [ ] A new `PROMPT_VERSION` constant exists in `llm_client.py`, bumped
      by this change.
- [ ] `enrich/cache.py`'s `EnrichmentCache` entries store `prompt_version`
      alongside the existing `schema_version`/`content_hash`; `.lookup()`
      treats a missing or mismatched `prompt_version` as a miss,
      independently of the `schema_version`/`content_hash` checks (never
      conflated into `_CACHE_SCHEMA_VERSION`).
- [ ] Fixture test: an adult-audience-worded event (e.g. "a professional
      development workshop for working engineers") enriches
      `relevant=True` with `Adult` in `age_grade_level`.
- [ ] Fixture test: an existing noise fixture (gala, closure notice, nav
      page) still enriches `relevant=False`.
- [ ] Fixture test: a cache entry written at the old `PROMPT_VERSION` is
      a miss under the new one even though its `content_hash` is
      unchanged — the LLM client is called exactly once more for that
      event, proven by a call-counting assertion (matching
      `_CACHE_SCHEMA_VERSION`'s existing test convention).
- [ ] Fixture test: a cache entry already at the current `PROMPT_VERSION`
      remains a hit (no spurious re-enrichment).
- [ ] Fixture test: `prompt_version` and `schema_version` are checked
      independently — bumping one without the other forces exactly the
      intended re-check, not both or neither.
- [ ] `kind="internship"` events still bypass this subsystem entirely,
      unchanged (they were never routed through the relevance prompt
      either way).
- [ ] `event.trusted` still overrides the relevance gate, unchanged.
- [ ] Full test suite stays green.

## Testing

- **Existing tests to run**: full suite (`uv run pytest`), with
  particular attention to `tests/enrich/test_llm_client.py` and
  `tests/enrich/test_cache.py` (or their current equivalents) and any
  existing gate/cache-versioning tests from sprint 009's
  `_CACHE_SCHEMA_VERSION` work — the new `prompt_version` check must
  mirror that convention, not diverge from it.
- **New tests to write**: fixture-based, per the Acceptance Criteria
  above — adult-audience-relevant, noise-still-rejected, prompt-version
  miss/hit, and independence-from-schema-version cases. All via
  `FixtureLLMClient`/`EnrichmentCache(cache_dir=tmp_path)`, no network.
- **Verification command**: `uv run pytest`

## Implementation Plan

**Approach**: A small, contained change confined to two files in
`enrich/`. No other subsystem is touched — `normalize/taxonomy.py`'s
keyword fallback is unaffected (it already defaults `relevant=True` on
any LLM failure, so it was never K-12-restrictive) and needs no change.

**Files to modify**:
- `partner_scrape/enrich/llm_client.py` — `_SYSTEM_PROMPT` rewrite; new
  `PROMPT_VERSION` constant.
- `partner_scrape/enrich/cache.py` — `EnrichmentCache` entries gain a
  `prompt_version` field (imported from `llm_client.PROMPT_VERSION`);
  `.lookup()`/`.store()` read/write it, independent of
  `_CACHE_SCHEMA_VERSION`.

**Testing plan**: see Testing above.

**Documentation updates**: This ticket implements
`design/enrich-DESIGN.md`'s sprint 014 section, already written during
planning — no further design-doc authoring is expected from this
ticket beyond keeping the implementation consistent with it. If
implementation reveals the planned design needs adjustment, update
`design/enrich-DESIGN.md` in place (do not create a second overlay
file) and note the revision.

**Budget note**: this change forces roughly one fresh Anthropic API
call per previously-cached event (~9,700 at sprint start) on the first
run after merge — a real, one-time, accepted cost (see `sprint.md`'s
Migration Concerns). Do not attempt to avoid or throttle this; it is
the direct, intended effect of the gate correction.
