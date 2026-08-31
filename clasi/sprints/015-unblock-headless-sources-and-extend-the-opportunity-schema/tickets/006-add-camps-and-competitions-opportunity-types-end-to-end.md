---
id: '006'
title: Add Camps and Competitions opportunity types end-to-end
status: in-progress
use-cases:
- SUC-007
depends-on: []
github-issue: ''
issue: 27-taxonomy-camps-competitions-deadlines-eligibility.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add Camps and Competitions opportunity types end-to-end

## Description

The controlled `opportunity_type` vocabulary
(`enrich/llm_client.py`'s `_OPPORTUNITY_TYPE_VALUES`,
`normalize/taxonomy.py`'s keyword fallback) has no `Camps` and no
`Competitions` value; 96% of records currently land in the generic
"Out-of-school Programs" bucket. Add both values end-to-end: LLM
prompt vocabulary, keyword fallback (where a sufficiently conservative
pattern exists), export contract (automatic — `Opportunity.
opportunity_type` already flows through unchanged), and this repo's
`site/` filter UI.

## Fix shape

1. **`enrich/llm_client.py`**: add `"Camps"` and `"Competitions"` to
   `_OPPORTUNITY_TYPE_VALUES`. This is a prompt-semantics change (the
   classification criteria the model applies changes), so bump
   `PROMPT_VERSION` from 1 to 2 — the exact mechanism sprint 014 built
   for the relevance-gate widening, forcing exactly one re-evaluation
   per previously-cached event via `cache.py`'s independent
   `prompt_version` check. This is real, one-time Anthropic API spend,
   accepted per that sprint's precedent.
2. **`normalize/taxonomy.py`**: add a keyword rule for `Camps` to
   `OPPORTUNITY_TYPE_KEYWORDS` (e.g. `\bcamp\b`/`\bday camp\b`/
   `\bsummer camp\b` — conservative, unlikely to false-positive).
   For `Competitions`, only add a keyword rule if a sufficiently
   conservative pattern can be found without over-matching unrelated
   program text; if not, leave it LLM-only, matching this module's
   own existing precedent for `"Funding Opportunities"` (no keyword
   rule, because one was shown to false-positive on unrelated text —
   `OPPORTUNITY_TYPE_KEYWORDS`'s own documented rationale). Record
   whichever decision is made and why.
3. **`site/src/components/OpportunityFilters.astro`**: this file's
   `opportunityTypes` array is a hardcoded literal, not derived from
   `opportunities.json` — add `'Camps'` and `'Competitions'` to it.
   Facet *counts* are computed dynamically at build time and need no
   change; only the list of offered facet values is hand-maintained.

## Acceptance Criteria

- [x] `_OPPORTUNITY_TYPE_VALUES` includes `"Camps"` and
      `"Competitions"`; `PROMPT_VERSION` is bumped to 2.
- [x] `FixtureLLMClient` test cases cover both new values end-to-end
      through `LLMEnricher.enrich()`.
- [x] A cache-hit regression test proves a pre-bump
      (`prompt_version=1`) cache entry is treated as a miss under the
      new prompt version, forcing exactly one re-evaluation — mirrors
      sprint 014's existing `prompt_version` cache test shape.
- [x] `OPPORTUNITY_TYPE_KEYWORDS` gains a `Camps` rule with fixture
      tests proving it matches representative camp titles and does not
      false-positive against a representative sample of non-camp
      titles already in the test fixtures.
- [x] The `Competitions` keyword-fallback decision (added, or
      explicitly declined per the `Funding Opportunities` precedent)
      is recorded in this ticket's Notes with the reasoning, either
      way.
- [x] `normalize.run()`'s existing `field_provenance`-presence
      precedence (LLM/fallback value wins when enrichment ran, else
      `classify_opportunity_type()` directly) requires no code change
      — both new values flow through the existing mechanism unchanged.
- [x] `site/src/components/OpportunityFilters.astro`'s
      `opportunityTypes` array includes both new values.
- [x] Full test suite stays green.

## Testing

- **Existing tests to run**: full suite (`uv run pytest`), especially
  `enrich/`'s and `normalize/taxonomy.py`'s test modules.
- **New tests to write**: per Acceptance Criteria above.
- **Verification command**: `uv run pytest`.

## Implementation Plan

**Approach**: Vocabulary/prompt change first (the shared source of
truth both `enrich/` and the site depend on), then the keyword
fallback, then the one-line site facet-list edit.

**Files to modify**:
- `partner_scrape/enrich/llm_client.py` — vocabulary,
  `PROMPT_VERSION`.
- `partner_scrape/normalize/taxonomy.py` — `Camps` keyword rule (and
  `Competitions` if a safe pattern exists).
- `site/src/components/OpportunityFilters.astro` — facet list.
- Corresponding test files for `enrich/`, `normalize/taxonomy.py`.

**Testing plan**: see Testing above.

**Documentation updates**: `partner_scrape/enrich/DESIGN.md` and
`partner_scrape/normalize/DESIGN.md` each get a short sprint-015
addendum (matching the existing sprint 014 `prompt_version` addendum
convention). Note in both that the sibling `../stem-ecosystem`
checkout's own `OpportunityFilters.astro` carries the identical
hardcoded facet list and needs the same one-line edit there, on its
own schedule — out of this ticket's write scope (a different repo).

## Notes

**`Competitions` keyword-fallback decision: declined.** No keyword rule
was added for `Competitions` to `OPPORTUNITY_TYPE_KEYWORDS` — it is
LLM-only, matching the existing `"Funding Opportunities"` precedent.

Reasoning: the obvious keyword candidate, a `competit*` pattern
(competition/competitive), false-positives on a real title already
sitting in this project's own fixtures —
`tests/test_adapters_leaguesync.py`'s `"Competitive Robotics Summer
Warm Up"` is an ordinary registration-based League *class* (kind
`"event"`, one of leaguesync's Pike13-sourced offerings), not a
competition itself. That is exactly the same failure shape that killed
the `"Funding Opportunities"` keyword rule (a common word — there
"grant", here "competitive" — appears routinely in unrelated program
text). Other candidates considered:
- `tournament`, `hackathon`, `science fair` — none appears anywhere in
  this codebase's adapters, fixtures, or test titles to spot-check
  against, so there is no evidence either way that they're safe, and
  adding an unverified rule risks silently mis-tagging whatever real
  titles do contain them.
- A bare `fair` — already too ambiguous even before checking real
  data: county fair, health fair, book fair, and `career fair`/`job
  fair`/`college fair` (already claimed by the existing Career
  Connections rule) all share the word, and `"STEM Fair: Grades 6-8
  (Free!)"` (a real title in `tests/test_model.py`) shows a genuinely
  competition-shaped event can also just say "fair" — no substring of
  it is a safe standalone signal.

`Camps` did get a rule (`\bcamps?\b`), by contrast, because the
word-boundary pattern is naturally self-limiting (it cannot fire inside
"campus"/"campaign"/"campfire"/"campground"/"encampment" — none of
those has a word boundary immediately before/after the substring
"camp") and every real camp title checked against it
("Ocean Explorers Camp", "Summer Camp Registration Is Open!", "Farm
Camp", "Camp-o-Saurus", "Summer Camps@SFA") matches cleanly with no
competing false-positive found anywhere in the fixture corpus.

Both new values remain fully available via the LLM classification path
(`enrich/llm_client.py`'s `_OPPORTUNITY_TYPE_VALUES`) regardless of this
decision — `Competitions` is simply never produced by the deterministic
keyword fallback (`normalize/taxonomy.py`'s
`classify_opportunity_type()`), the same as `Funding Opportunities`
before it.
