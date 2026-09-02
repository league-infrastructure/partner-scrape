---
status: pending
---

# Extraction quality guardrails: non-determinism and date fabrication

## Description

Sprint 029's live verification surfaced two distinct LLM-extraction
reliability problems in `partner_scrape/adapters/program_llm.py`'s
extraction path. Neither is a fetch or registration problem — the
pages fetch cleanly and the text reaching the model is correct.

**1. Non-determinism on unstructured pages.** SDCEC
(sandiegoengineers.org/stem) returned four different result sets from
four `extract_programs()` calls against byte-identical fetched text:
0, 17, 21, and 32 records. The page concatenates an unlabeled
current-cycle list with a decade of undated "Prior sTEm Events" archive
with no boundary the model can anchor on. The source is registered
`enabled = false` as a result.

**2. Date fabrication under the reference-date rule.** Sprint 029
ticket 006 added a `reference_date` injected into the user prompt so
the model can infer an implied year (fixing TritonHacks' wrong-year
extraction). Ticket 007 then observed one non-reproduced case where
`sdftc-league-play` — a page with no calendar date at all — came back
with a `date_start` fabricated equal to the injected `reference_date`.
The extraction was not trusted and its cache entry was deleted, but the
failure mode is inherent to the rule: give the model a date and a page
with none, and it may return the date you gave it.

## Proposed fix

- A determinism/confidence guard for multi-record extraction: e.g.
  extract twice and keep only records that agree, or require a record
  to cite the text it came from. Consider what this costs per run
  before committing to it.
- A fabrication guard for dates: reject a `date_start` that equals the
  injected `reference_date` unless that date is independently present
  in the reduced page text.
- Re-check `sdcec` and `sdftc-league-play` once landed.

## Verification

- Unit: a fixture page with no date yields no date even when a
  reference date is injected; a record whose date equals the reference
  date but is absent from the page text is rejected.
- Live: repeated `sdcec` extractions agree, or the source is
  legitimately rejected by the guard rather than by hand.
