---
status: done
sprint: '030'
tickets:
- 030-001
- 030-003
- 030-004
- 030-005
---

# Educator layer: teacher PD + free/Title I school programs

## Description

Educators are a named audience of the site and get nothing. Two gaps:

1. **No machine-readable teacher-PD calendar exists in San Diego.**
   SDCOE's PD registrations live in k12oms.org whose robots.txt is
   `Disallow: /` (do not scrape); UCSD CREATE, SD Science Project,
   UCSD Math Project, Code.org regional partner, CSTA-SD, SDSU CRMSE,
   Fleet educator workshops, Salk STEM Educators Summit, Zoo teacher
   workshops are static pages and newsletters. Approach: curated
   registry of educator-program pages + LLM extraction (same mechanism
   as the internship program-page extractor), typed
   `Professional Development / Conferences`.
2. **Free/Title I school programs have no schema.** These are undated,
   bookable programs with eligibility rules — arguably the highest-
   equity content in the county: Zoo FREE field trips for SD County
   schools (CDE-listed, 4-week lead); the Nat's Museum Access Fund
   (Title I: no-cost workshops/tours/outreach + transport, goal 6,000
   students/yr); Living Coast Title 1 aid + CVESD free-transport
   partnership; Birch financial aid (2026-27 open); Fleet discounted
   trips / Science to Go / Family Science Nights; Qualcomm Thinkabit
   Lab (SDUSD + Sweetwater sites); Biocom Life Science Station +
   Innov8Ed. Needs an "educator program" record shape (org, program,
   eligibility, how to book, last-verified) rendered as a For-Educators
   section — a standing-entity page like teams, not a dated event.

Also: SD Botanic Garden Teacher Resource Fair (Oct 6) and Salk HS
Science Day are dated educator events that arrive via issues 25/32.
Grants/speakers have no live source (SDG&E closed, DonorsChoose
robots-restricted, Pathful licensed) — note and skip.

## References

Gap analysis 2026-08-30: https://claude.ai/code/artifact/02ba9c3e-61a2-40eb-a987-444463cd3266
