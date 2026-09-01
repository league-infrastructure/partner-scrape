---
status: in-progress
sprint: '021'
tickets:
- 021-001
- 021-002
- 021-003
- 021-004
---

# Teams data: import discovered websites, extract descriptive text for teams.json

## Description

Stakeholder request (Eric, 2026-08-31), rescoped 2026-08-31 post-site-
consolidation. Originally filed as a two-part issue covering both the
teams pipeline (this repo) and the team detail page (`site/src/pages/
teams/[slug].astro`). Sprint 019 removed `site/` from partner-scrape
entirely — that page now lives exclusively in stem-ecosystem. This
issue is rescoped to the **pipeline-side half only**: producing the
data. The site-side half (link-visibility audit, rendering the new
blurb field with attribution) is now stem-ecosystem's issue, tracked in
their own backlog — handed off via cross-session message to
stem-ecosystem-8d on 2026-08-31 rather than silently dropped.

1. **Import the 31 agent-discovered team websites** from sprint 013's
   research (`clasi/sprints/done/013-.../research/
   discovered-websites.json` — re-verified HTTP 200 at the time, with
   host+path uniqueness caveats) into the teams data, if they were
   never imported (audit first — check whether this already happened).
   Curated static input, like the FLL roster precedent — not
   unattended search.

2. **Extract descriptive text from each team's website** so `teams.json`
   carries real content, not just roster metadata. An extraction pass
   over each fetched team site (the fetch machinery exists from sprint
   013's sponsor extraction) that produces a short "about this team"
   paragraph, stored as a new field on the team record. Follow the
   sponsor-extraction anti-hallucination pattern: deterministic content
   gathering first (headings, about/home page main text, meta
   descriptions — bounded input), then an LLM SUMMARIZES only that
   gathered text; store the blurb with provenance + fetch date so the
   consuming site can attribute it ("from the team's website"). A team
   whose site yields no usable text gets no blurb — never a generated
   one. Cache by content hash (enrichment-cache precedent) so re-runs
   are cheap; teams data refreshes ~yearly so cost is one-time-ish.

The new blurb field reaches stem-ecosystem through the existing
`teams.json` publish path (`teams/export.py`'s three write targets,
sprint 020) — no new transport needed.

Note teams/model.py's hard invariant: no email field, ever — the
extraction must not capture contact emails into the blurb.

## References

Sprint 013 (website surfacing + sponsor extraction) artifacts;
partner_scrape/teams/DESIGN.md; sprint 020 (teams.json's three write
targets, the path this issue's new field rides on); sprint 019 (removed
`site/`, motivating this rescope).

## Handoff

Site-side half (link-visibility audit on the team detail page; render
the new blurb with attribution once it lands in `teams.json`) handed to
stem-ecosystem-8d via cross-session message, 2026-08-31 — not tracked
as a partner-scrape issue since it isn't actionable in this repo.
