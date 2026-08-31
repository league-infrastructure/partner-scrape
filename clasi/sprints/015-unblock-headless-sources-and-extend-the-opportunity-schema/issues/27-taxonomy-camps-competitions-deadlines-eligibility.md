---
status: in-progress
sprint: '015'
tickets:
- 015-006
- 015-007
- 015-008
---

# Schema: Camps and Competitions types, deadline-first dates, eligibility flag

## Description

Three content shapes the gap analysis needs cannot be expressed today:

1. **`opportunity_type` values.** The controlled vocabulary
   (enrich/llm_client.py `_OPPORTUNITY_TYPE_VALUES`, normalize/taxonomy.py)
   has no `Camps` and no `Competitions`. 96% of records land in
   "Out-of-school Programs". Add both values end-to-end: LLM prompt,
   keyword fallback, export contract, site filters. Coordinate with the
   site repo (contract change).
2. **Deadline-first date semantics.** Internships/research programs and
   competition registrations are "apply by" items, not "attend on"
   items. `export/writer.py` already special-cases Work-based Learning
   (Apply-by/Rolling); generalize: any record may carry an application
   deadline that (a) keeps it exported while the deadline is future,
   (b) displays as "Apply by", (c) sorts sensibly. Surface Dec-Mar
   deadlines for Jun-Aug programs in winter.
3. **Eligibility flag.** Several of the best programs are closed
   pipelines: Northrop HIP (partner high schools), Scripps REACH (nine
   named schools), SBP Preuss program, Illumina/SD2, Zoo free field
   trips (SD County schools). Stakeholder decision 2026-08-30: show
   them honestly with an eligibility note rather than omit. Add an
   `eligibility` field to the record + export + card display.

Blocks (or is a dependency of) the camps, internships, and
competitions issues.

## References

Gap analysis 2026-08-30: https://claude.ai/code/artifact/02ba9c3e-61a2-40eb-a987-444463cd3266
