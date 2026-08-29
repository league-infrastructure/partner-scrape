---
id: '004'
title: Sponsor extraction LLM client and cache
status: open
use-cases: [SUC-004]
depends-on: ['003']
github-issue: ''
issue: 21-scrape-team-sites-for-sponsors.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sponsor extraction LLM client and cache

## Description

This ticket builds the injectable LLM-classification infrastructure
ticket 005's orchestration will call — no orchestration logic here, only
the client protocol, its real and fixture implementations, and the
cache. Issue 21 names false positives as the dominant risk: an LLM asked
"what are this page's sponsors?" over open text will confidently return
the CMS vendor, the hosting provider, the school district, or the site's
own domain. The mitigation is architectural, not just prompt wording:
this client's contract is **classification of a given candidate list**,
never open-ended generation — see `sprint.md`'s Design Rationale for the
full reasoning.

Add `partner_scrape/teams/sponsor_llm.py`:
- `SponsorExtractionResult` (a small dataclass, `confirmed_sponsors:
  list[str]`).
- `SponsorLLMClient` protocol: `classify_sponsors(candidates: list[str],
  context: dict) -> SponsorExtractionResult`.
- A JSON-schema-from-dataclass generator, mirroring
  `enrich/llm_client.py`'s `_build_enrichment_json_schema()` pattern —
  **duplicate the small helper, do not import it.** `teams/` has a
  standing, explicitly documented invariant of zero edges into `enrich/`
  (`teams/DESIGN.md`'s Purpose/Constraints sections; `tests/teams/
  test_sources_base.py`'s forbidden-import precedent for `adapters.base`
  is the same spirit). Importing `enrich.llm_client` here — even for one
  small helper — would be the first crack in that boundary. See
  `sprint.md`'s Design Rationale ("sponsor extraction lives entirely
  inside `teams/`...") for the full alternatives-considered writeup.
- `AnthropicSponsorLLMClient`: the real implementation. Constructs
  `anthropic.Anthropic()` with no explicit `api_key` (matching
  `enrich.llm_client.AnthropicLLMClient`'s exact pattern — the SDK
  resolves `ANTHROPIC_API_KEY` itself; this is deliberately not a
  `config.py` accessor). `MODEL_ID = "claude-haiku-4-5-20251001"`
  (redefined locally, same value as `enrich.llm_client.MODEL_ID`, not
  imported). The system prompt must instruct the model to **select from**
  the given candidate list only, explicitly excluding the team's own
  organization name, the FIRST/FTC/FRC program names, and common
  CMS/hosting vendor names (Wix, Squarespace, WordPress, GoDaddy, Weebly,
  Google Sites, etc.) — `context` should carry the team's `organization`
  and page hostname so the prompt can name them explicitly.
- `FixtureSponsorLLMClient`: the test double, mirroring
  `enrich.llm_client.FixtureLLMClient`'s shape (canned responses keyed by
  a lookup function, a `calls` list recording every invocation for
  call-counting assertions).

Add `partner_scrape/teams/sponsor_cache.py`: `SponsorCache`, a
content-hash cache keyed by `(team_id, content_hash(candidates))`, one
JSON file per key under
`{SCRAPE_CACHE_DIR}/sponsor_extraction_cache/`, mirroring — again,
duplicating rather than importing — `enrich/cache.py`'s
`schema_version`-guarded, content-hash-invalidated shape. Keying on the
*candidate list's* content hash (not the raw page body's) means a page's
unrelated boilerplate changing (a footer copyright year, an unrelated
nav link) never forces a re-classification the candidate set itself
didn't change.

See `sprint.md`'s SUC-004 (the classification portion) and Design
Rationale, and `design/teams-DESIGN.diff.md`'s Interfaces/Design entries
for this ticket's exact module contracts.

## Acceptance Criteria

- [ ] `partner_scrape/teams/sponsor_llm.py` exists with
      `SponsorExtractionResult`, `SponsorLLMClient` (Protocol),
      `AnthropicSponsorLLMClient`, `FixtureSponsorLLMClient`, and a
      dataclass-derived JSON schema for `SponsorExtractionResult`.
- [ ] `partner_scrape/teams/sponsor_llm.py` contains **zero** imports
      from `partner_scrape.enrich` (verify with a grep/AST check, same
      spirit as `tests/teams/test_sources_base.py`'s forbidden-import
      scan).
- [ ] `AnthropicSponsorLLMClient`'s system prompt explicitly instructs
      the model to select only from the given candidates and to exclude
      the team's own organization name, program names, and named
      CMS/hosting vendors.
- [ ] `partner_scrape/teams/sponsor_cache.py` exists with `SponsorCache`,
      keyed by `(team_id, content_hash(candidates))`, under
      `{SCRAPE_CACHE_DIR}/sponsor_extraction_cache/`, with a
      `schema_version` guard matching `enrich/cache.py`'s
      stale-entry-is-a-miss convention.
- [ ] `partner_scrape/teams/sponsor_cache.py` also contains zero imports
      from `partner_scrape.enrich`.
- [ ] `FixtureSponsorLLMClient` records every call in an inspectable
      `calls` list for cache-hit call-counting tests (ticket 005 will use
      this).

## Testing

- **Existing tests to run**: `uv run pytest tests/teams/` and
  `uv run pytest tests/enrich/` — this ticket must not touch `enrich/`
  at all, so its existing suite should be unaffected; confirm.
- **New tests to write**:
  - `tests/teams/test_sponsor_llm.py`: the JSON schema generated from
    `SponsorExtractionResult` matches its dataclass fields (mirroring
    `tests/enrich/`'s own schema-drift test, if one exists, for the same
    guarantee); `FixtureSponsorLLMClient` returns canned results and
    records calls; a static-analysis test (AST scan or plain
    `grep`-equivalent in Python) asserting no `partner_scrape.enrich`
    import anywhere in `sponsor_llm.py`.
  - `tests/teams/test_sponsor_cache.py`: a cache miss on first lookup, a
    hit on an identical candidate list for the same team, a miss when
    the candidate list changes (different content hash) or when
    `schema_version` doesn't match (mirroring
    `tests/enrich/test_cache.py`'s equivalent cases); a static-analysis
    test asserting no `partner_scrape.enrich` import in
    `sponsor_cache.py`.
- **Verification command**: `uv run pytest`.
