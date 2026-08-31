---
status: pending
---

# Team pages: always link the team's website, and extract descriptive text from it

## Description

Stakeholder request (Eric, 2026-08-31). Two improvements to the robot-team
detail pages (site/src/pages/teams/[slug].astro and the teams pipeline):

1. **When a team has a website, the team's page must link to it.**
   Today the link's visibility is inconsistent: sprint 013 added the
   card badge, "Has a Website" facet, and a dead-link guard on the
   detail page — audit whether the guard (website_status !=
   "confirmed") or the data path is suppressing links that should show.
   Also check whether the 31 agent-discovered team websites from sprint
   013's research (clasi/sprints/done/013-.../research/
   discovered-websites.json — re-verified HTTP 200 at the time, with
   host+path uniqueness caveats) were ever imported into the teams data;
   if not, importing them is part of this issue (curated static input,
   like the FLL roster precedent — not unattended search).

2. **Extract descriptive text from the team's website** so the page has
   real content, not just roster metadata. An extraction pass over each
   fetched team site (the fetch machinery exists from sprint 013's
   sponsor extraction) that produces a short "about this team"
   paragraph. Follow the sponsor-extraction anti-hallucination
   pattern: deterministic content gathering first (headings, about/home
   page main text, meta descriptions — bounded input), then an LLM
   SUMMARIZES only that gathered text; display with attribution ("from
   the team's website") and store provenance + fetch date. A team whose
   site yields no usable text gets no blurb — never a generated one.
   Cache by content hash (enrichment-cache precedent) so re-runs are
   cheap; teams data refreshes ~yearly so cost is one-time-ish.

Note teams/model.py's hard invariant: no email field, ever — the
extraction must not capture contact emails into the blurb.

## References

Sprint 013 (website surfacing + sponsor extraction) artifacts;
partner_scrape/teams/DESIGN.md; site/src/pages/teams/[slug].astro.
