---
status: done
sprint: '024'
tickets:
- 024-001
- 024-002
---

# Hub registry: real discovery-only hubs + the do-not-scrape list

## Description

The hub mechanism (registry/hubs, scan_hub → OrgCandidate leads, never
republishes) has only a placeholder hub. Populate it with the hubs the
2026-08-30 research cleared, and codify the ones we must not touch.

**Register as discovery-only hubs (leads, not events):**
- KidsOutAndAbout San Diego (sandiego.kidsoutandabout.com) — STEM camp
  category, server-rendered HTML with dates+prices; best camp-provider
  discovery source. Read ToS before enabling.
- San Diego Moms camp directory (sandiegomoms.com).
- sandiegostemsummercamps.com ("251+ programs") — ToS check required.
- SDCEC youth STEM list (sandiegoengineers.org/stem) — hand-curated.
- San Diego Reader events listing (68 JSON-LD Events/page; "For Kids"
  category; do not use the robots-disallowed /events/search/).
- KPBS/TheFinestSD community calendar (per-event .ics; free public
  submissions).
- Macaroni Kid editions (chulavista, carlsbad, escondido, oceanside,
  sanmarcos) — HTML only, low yield; optional.

**Treat as sources, not hubs (stakeholder call 2026-08-30):** Balboa
Park calendar and UCSD Localist are institutional calendars of orgs we
list — register via issue 25 with cross-source dedup against the
member orgs' own feeds.

**Do-NOT-scrape list (codify in a checked-in doc or registry denylist,
with reasons, so future sessions don't re-litigate):**
- Eventbrite — ToS §13 forbids scraping; API token-only, search
  endpoint removed.
- Idealist / VolunteerMatch (now redirects to Idealist) — ToS forbids
  bots/scrapers.
- ActivityHero — ToS forbids scraping.
- Tinybeans — robots disallows /events/.
- SDCOE OMS (k12oms.org) — robots Disallow: /.
- Patch — robots blocks anthropic-ai/CCBot AI agents.
- SanDiego.org, CONNECT, StartupSD — bot walls (Cloudflare/captcha).
- ActiveNet apm REST — WAF-rejected (the campscui camps UI in issue 29
  is a different, permitted surface).
- JustServe / HandsOn San Diego / Points of Light — JS-only, no API
  (revisit only if they publish one).
- Meetup per-group iCal is robots-clean but ToS-unverified — hold until
  terms are read; adult-tech yield anyway.

## References

Gap analysis 2026-08-30: https://claude.ai/code/artifact/02ba9c3e-61a2-40eb-a987-444463cd3266
