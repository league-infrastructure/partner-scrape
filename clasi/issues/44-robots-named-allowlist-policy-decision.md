---
status: pending
---

# Policy decision: ATS sites whose robots.txt allows only named bots

**This is a stakeholder decision, not an engineering task.**

## The situation

Sprint 031 built five working ATS adapters. Five registered sources are
disabled — not because anything is broken, but because their
robots.txt allows only a named allow-list of crawlers (Googlebot,
bingbot, LinkedInBot and similar) and disallows everyone else. Under
this project's default `respect_robots = true`, the fetcher raises
`RobotsDisallowed`.

Disabled on these grounds:
- `servicenow.toml` — api.smartrecruiters.com (allows LinkedInBot only)
- `city-of-san-diego-careers.toml`
- `county-of-san-diego-careers.toml`
- `sandag-careers.toml`
- `port-of-san-diego-careers.toml` — all four on www.governmentjobs.com

The adapters are complete and fixture-tested. Flipping any of them on
is a one-line registry edit if the policy allows it.

Note the character of the content: these are public-sector job postings
(County of SD, City of SD, SANDAG, Port of SD) that the agencies want
found — the block is the ATS vendor's blanket policy, not the agency's.

## The question

Does the bright-line rule stand — robots.txt says no automated access,
so we exclude — or is there a reading under which a low-volume,
non-republishing, link-out-only fetch of public job postings is
acceptable?

This is the same question left open by sprint 024 for four ToS-blocked
hubs (see `partner_scrape/registry/DO_NOT_SCRAPE.md`). Deciding both
together would be better than deciding them one at a time.

## If the answer is "the rule stands"

Record it in `DO_NOT_SCRAPE.md` with the reasoning, so a future sprint
doesn't re-litigate it, and close this issue.

## If the answer is "allow it for these"

The mechanism already exists: `acquisition_policy` threading with a
per-source `respect_robots` (sprint 015). Set it per-source with a
comment naming this decision — do not change the global default.
