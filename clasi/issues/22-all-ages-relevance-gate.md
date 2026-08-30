---
status: pending
---

# Open the relevance gate to all ages

## Description

Stakeholder decision (Eric, 2026-08-30): the site is for **learners of all
ages**, matching the homepage ("learners of all ages"), the `Adult` age
facet, and the original Drupal site. The LLM relevance gate currently
enforces K-12-only: `enrich/llm_client.py`'s `_SYSTEM_PROMPT` says
relevant = "a STEM learning opportunity for youth (not an adult-only
program...)". Of 6,598 cached rejections, 1,027 are adult/professional
programs. This is why UC San Diego Extended Studies (300 found → 0
published), Salk (126 → 0), Qualcomm (49 → 0), sandiego.gov (299 → 0),
and partner series like Fleet Suds & Science / After Dark, Nat Talks,
and Birch Perspectives on Ocean Science publish nothing.

## Proposed fix

1. Rewrite the relevance instruction: relevant = a STEM learning
   opportunity for **any audience** (children, teens, families, adults,
   educators, college-bound students). Still reject noise: non-STEM
   recreation, fundraising galas, closure notices, press releases,
   navigation pages, records with no evaluable content.
2. **Cache invalidation is required.** `enrich/cache.py` keys on the
   event content hash, so 6,598 stored `relevant: false` verdicts will
   persist after the prompt change. Add a prompt-version component to
   the cache key (or clear `SCRAPE_CACHE_DIR/enrichment_cache`), and
   budget for the re-enrichment cost of ~9,700 records.
3. Keep the classifier populating `age_grade_level` with `Adult` so the
   site facet lets families filter adults-only content out.
4. Re-run and compare per-source yield before/after (observability
   already reports deltas); expect large jumps for extendedstudies-ucsd,
   extension-ucsd, salk, qualcomm, grossmont, sandiego-gov, wccsd.

## References

Gap analysis 2026-08-30: https://claude.ai/code/artifact/02ba9c3e-61a2-40eb-a987-444463cd3266
