---
status: pending
---

# High-school internship & research-program extraction (program pages, not ATS)

## Description

The site publishes zero internships, and the sprint 006 ATS bet missed
the target: San Diego's high-value HS programs are paid summer research
placements published as **prose program pages** — a date range, an
application window, eligibility, pay — on lab and university sites.
None are on an ATS. Deadlines cluster Dec-Mar for Jun-Aug programs.

**Seed sources (verified 2026-08-30):**
- UCSD Summer Program Finder — summer.ucsd.edu/program-finder — 21
  HS-eligible programs as cards with grade tags (COSMOS, ENLACE,
  OPTIMUS, Research Scholars, Sally Ride, SPARK, Upward Bound...).
  The single best listing page; scrape it as a listing source.
- SIO research internships table —
  scripps.ucsd.edu/education/research-internships — undergrad programs
  with explicit deadlines (JT-SURF Feb 27, MPL Jan 23, CW3E Jan 15...).
- Individual program pages: Salk Heithoff-Brody HS Scholars (paid, SD
  County 16+, apps Dec 1-Mar 1); SDSC REHS (apps open Feb 15); Sanford
  Burnham Prebys SPARK (paid, email apply); La Jolla Institute LJIdea;
  Scripps Research SRTI (deadline Mar 30) + REACH (partner schools);
  UCSD OPTIMUS / ENLACE / COSMOS; NIWC Pacific SEAP + NREIP
  (navalsteminterns.us, apps Aug-Nov 1); NOAA Hutton (HS); SDZWA
  fellowships (Feb 15) + InternQuest; SDSU ExpandAI robotics camp
  (free, NSF); Illumina/SD2 STEM Scholars (closed pipeline); Biocom
  Generation STEAM Pathways internships.
- San Diego Foundation Community Scholarship (150+ scholarships, one
  common app, opens winter) → `Funding Opportunities` type.

## Proposed fix

A "program page" extraction path: fetch each registered program page,
LLM-extract {program name, audience/grades, date range, application
window/deadline, paid/cost, eligibility, open/closed status}, emit
records with deadline-first semantics + eligibility flag (schema
issue). Records for closed windows stay out (or display as "opens ~X").
Route around the recurring-collapse and event dedup like internships
already are. `kind='internship'`/'program' bypasses the relevance gate
as trusted where the source is curated.

## References

Gap analysis 2026-08-30: https://claude.ai/code/artifact/02ba9c3e-61a2-40eb-a987-444463cd3266
