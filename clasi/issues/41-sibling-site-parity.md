---
status: pending
---

# Bring the production stem-ecosystem site to parity with the beta site/ checkout

## Description

The beta Astro checkout in this repo (site/) and the production sibling
repo (../stem-ecosystem, deploys to GitHub Pages) have drifted. Found
during sprint 016 ticket 005: the sibling has NO teams feature at all —
no teams pages, no teams.json — the entire robot-teams directory
(sprints 011-013) was only ever built in the beta checkout. The full
parity gap now includes:

- Teams pages (index, [slug], TeamCard, TeamFilters) + teams.json
  (note: number field is now a string as of 016-005 — port the
  natural-sort comparator with it, not just the pages).
- OpportunityFilters.astro's hardcoded opportunityTypes array needs
  Camps + Competitions (sprint 015 flag).
- Opportunity detail page's eligibility <dt>/<dd> row (sprint 015).
- data-access.astro schema table (eligibility field).
- Any sponsor-extraction UI from sprint 013 present only in site/.

Approach: diff site/src against ../stem-ecosystem/src and port
deliberately (the beta is the source of truth for features; the sibling
may have its own hotfixes — e.g. contact-page changes committed there
directly — so this is a merge, not a copy). Out of partner-scrape's
CLASI write scope for the sibling repo; treat as an operator/site-repo
work item this issue merely tracks.

## References

Sprint 016 ticket 005 Notes; sprint 015 tickets 006/008 flags.
