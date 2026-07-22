---
status: done
sprint: 008
tickets:
- 008-010
---

# Home page: "Our Partners" section featuring The League of Amazing Programmers

The home page (`site/src/pages/index.astro`) should have an **"Our Partners"**
section at the **bottom**, and **The League of Amazing Programmers** must
appear in it.

## Do
- Add an "Our Partners" section near the bottom of the home page (a partner
  logo/name grid or strip), matching the production
  (https://www.sdstemecosystem.org) treatment where applicable.
- Ensure **The League of Amazing Programmers** is included/featured there
  (it's an active partner in `site/src/data/partners.json` and the #-org for
  first-party League classes).
- Link partners to the Partners page / their entries as appropriate.

## Notes
- Part of the home-page work — build alongside
  [[22-home-page-from-sdstemecosystem]] (hero + cards) and
  [[24-home-upcoming-opportunities-next-week]]. Uses partner logos, so it
  benefits from [[18-partner-icons-images]] (fallback for logo-less
  partners).
- Applies to both beta (`partner-scrape/site`) and production
  (`stem-ecosystem`).
