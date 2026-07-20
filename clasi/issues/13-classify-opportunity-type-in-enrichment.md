---
status: pending
---

# Classify opportunity_type during enrichment (fix empty type filters)

Every exported opportunity is stamped `opportunity_type = "Out-of-school
Programs"` — the blind default in `normalize/run.py`. The LLM enrichment
classifies `areas_of_interest` / `age_grade_level` / `cost_range` /
`time_of_day` but NOT `opportunity_type`, so the site's other 7 type
filters (School Programs, Career Connections, Work-based Learning,
Volunteering, Funding Opportunities, Online, Professional Development) are
always empty — clicking them shows nothing. Reported by the stakeholder
from the live site 2026-07-20.

## Proposed scope

- Add `opportunity_type` to `EnrichmentResult` + the LLM prompt, with the
  site's controlled vocab (see stem-ecosystem/docs/site-implementation-spec.md):
  Out-of-school Programs, Online, Professional Development / Conferences,
  School Programs, Career Connections, Work-based Learning, Volunteering,
  Funding Opportunities.
- Map the classified value onto the `Opportunity` in `normalize/run.py`
  (internships already force "Work-based Learning" — keep that).
- **Cache note:** adding a field to `EnrichmentResult` means existing cached
  results lack it. Bump an enrichment cache version (or include a schema
  version in the stored entry) so events re-enrich once to pick up
  `opportunity_type`, rather than serving stale results without it.
