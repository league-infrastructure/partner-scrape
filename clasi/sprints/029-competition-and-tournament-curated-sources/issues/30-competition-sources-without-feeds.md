---
status: in-progress
sprint: 029
tickets:
- 029-001
- 029-002
- 029-003
- 029-004
- 029-005
---

# Competition & tournament sources without feeds

## Description

Beyond the feed-backed competitions (cafirst.org TEC → issue 25,
RobotEvents → issue 26), San Diego's annual competition calendar lives
on static pages. These are few, high-value, and slow-changing — a
listing/curated approach with an annual review beats forcing them
through sitemap discovery. All verified 2026-08-30 unless noted:

- San Diego Regional Science Olympiad — scilympiad.com/sdso — Div A/B
  Feb 7 2026 (Miramar College), Div C Feb 28 (USD); reg Sept 2-Dec 15.
- SDFTC league play — sdftc.org (Weebly) — meets Nov/Dec/Jan, League
  Tournament Feb 7-8, Regional Championship Mar 7.
- SeaPerch San Diego Regional — Classroom of the Future Foundation —
  Apr 4 2026, Kearny Mesa Pool; reg opens mid-Feb.
- MATHCOUNTS SD chapter — cspeef.org — Feb 28 2026, UCSD.
- San Diego Math Circle — sdmathcircle.org — Saturdays at UCSD;
  official AMC/AIME/ARML/Math Kangaroo site; master calendar is a
  public Google Sheet (fetchable).
- DOE National Science Bowl SD regionals — HS Feb at UCSD, MS virtual
  Jan; reg opens Oct.
- Garibaldi Bowl (NOSB, USD) — February.
- San Diego Brain Bee — Feb 14 2026, UCSD School of Medicine.
- CyberPatriot SD (AFA Cardenas chapter) + SoCal/Mayor's Cyber Cup
  (NDIA SD) — Oct-Mar season; ndia-sd.org is JS; sdccoe.org has a
  stale TEC.
- HS hackathons: TritonHacks (UCSD, May 16-17 2026), CipherHacks (SD
  Central Library, Jun 17-18 2026); hackathons.hackclub.com aggregates.
- Botball Greater SD (KIPR) — workshop at Wilson MS, tournament April.
- Congressional App Challenge (CA-48/49/50/51/52) — opens ~July, due
  ~Nov; house.gov 403s, congressionalappchallenge.us static.
- GSDSEF (already a partner, Wix): judging Mar 18, public day Mar 21
  2026 — make sure these dates surface.
- SD Festival of Science & Engineering / EXPO Day (partner): Mar 7 2026
  Petco Park; lovestemsd.org has DB-driven per-event pages for the
  ~35 festival-week events — worth a dedicated listing extraction.
- SDCEC (sandiegoengineers.org/stem) — hand-curated youth STEM event
  list + Engineers Week awards (Feb 20 2026) — use as a discovery
  cross-check, and register the org.

Mechanism: either registry entries with `listing_html` + generous
extraction, or a small curated-source file (org, URL, expected month,
last-verified) the pipeline re-checks and the LLM extracts dates from.
Depends on `Competitions` taxonomy value (schema issue).

## References

Gap analysis 2026-08-30: https://claude.ai/code/artifact/02ba9c3e-61a2-40eb-a987-444463cd3266
