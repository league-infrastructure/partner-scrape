---
status: pending
---

# ATS adapters: Workday, NEOGOV, SmartRecruiters, Workable

## Description

College/early-career internships for the career-pathway story. ATS
census of San Diego employers (verified 2026-08-30):

- **Workday** (biggest win): Northrop Grumman (incl. its HS Internship
  Program req), Cubic, Illumina, Dexcom; likely ResMed and
  Sempra/SDG&E. Pattern: POST /wday/cxs/{tenant}/{site}/jobs; needs
  browser-like headers (plain requests 403).
- **NEOGOV / governmentjobs.com** (one adapter, four agencies): County
  of SD, City of SD, SANDAG, Port of SD. Student/intern classes post
  seasonally — cadence matters more than parsing.
- **SmartRecruiters** (cheapest): ServiceNow — public GET
  api.smartrecruiters.com/v1/companies/ServiceNow/postings.
- **Workable**: SD County Regional Airport Authority
  (apply.workable.com, public JSON) — paid 9-week summer internships.
- **Existing greenhouse adapter**: add Sony Interactive Entertainment
  (board `sonyinteractiveentertainmentglobal`, verified 200).
- Unconfirmed ATS: Qualcomm (Eightfold-ish, 403), Solar Turbines,
  Teradata, BAE (Phenom), General Atomics (BrassRing), Intuit
  (Radancy) — probe before building anything bespoke.

Reuse ats_filters (internship + STEM + San Diego). Route as
Work-based Learning like greenhouse/lever. Expect long stretches of
zero matching postings — that is signal, not error.

## References

Gap analysis 2026-08-30: https://claude.ai/code/artifact/02ba9c3e-61a2-40eb-a987-444463cd3266
