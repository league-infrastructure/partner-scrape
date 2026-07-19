# Overview — San Diego STEM Ecosystem Event Engine

## Elevator pitch

Keep the San Diego STEM Ecosystem website alive and make it genuinely
useful by turning it into a **self-updating directory of STEM learning
opportunities** for San Diego County. Instead of waiting for ~150 partner
organizations to log in and post their own events (which they never
reliably did), we **scrape events and programs directly from the partners'
own websites**, normalize them into a common schema, and publish them to a
fast static site — with no ongoing human effort per event.

This repository (`partner-scrape`) is the **data engine**: the scraping,
extraction, normalization, and export pipeline. It feeds a sibling
repository (`stem-ecosystem`) that renders the public Astro static site.

## Why we are doing this

- **The site is at risk.** sdstemecosystem.org is hosted by the Fleet
  Science Center (Balboa Park), the local backbone organization for San
  Diego's member of the national STEM Learning Ecosystems Community of
  Practice (run by TIES, tiesteach.org). At the time this effort began the
  Fleet was under budget pressure — paying ~$3,000/year for maintenance and
  hosting and openly considering taking the site offline. That pressure may
  have eased, but the site remains under-maintained and nobody updates it.
- **We want to keep it going** as a public good: a place San Diego families,
  students, and educators can go to find science events and programs.
- **We (The League of Amazing Programmers) get value from it.** In exchange
  for the goodwill of building and running the scraper — and doing the
  marketing work of keeping the directory populated — the site carries
  **our own content and our sidebar advertising**. Our own events and
  programs are featured on it; the advertising space is ours. That is the
  business model that funds our effort.

## What already exists

- **A static site** (`stem-ecosystem`, Astro v6): 153 vetted partner
  organizations with logos and geocoding, plus filterable Opportunities and
  Partners directories with detail pages. Deploys to GitHub Pages at
  effectively $0/year.
- **A working pipeline** (this repo): a Scrapy site-mirroring system plus a
  `dev/` extraction pipeline that has already pulled ~7,000 event/program
  records from ~144 partner sites, including a clean path via The Events
  Calendar REST API. A recent end-to-end run produced ~107 upcoming
  opportunities and exported them into the site.
- **A roadmap document** (`dev/SCRAPER_GUIDELINES.md`) analyzing every
  partner site and describing an incremental production scraper.

## What we are building next

1. **A production event engine** — turn the one-off `dev/` scripts into a
   dependable, incremental, scheduled scraper that refreshes partner events
   without re-mirroring tens of gigabytes each run.
2. **Full coverage of the flagship sources** — including the Fleet Science
   Center's own events and Birch Aquarium, which are currently missing.
3. **A self-updating loop** — scheduled scrape → normalize → export →
   rebuild → deploy, so the site stays fresh unattended.
4. **An expanded definition of "opportunity"** — beyond partner events, add
   **San Diego STEM companies**: their public events and their
   **internships**, so the site becomes a career-pathway resource too.

## Success looks like

A public San Diego STEM directory that is fresh every week with zero
per-event human effort, shows the Fleet's and partners' events (plus the
League's), carries the League's advertising, costs almost nothing to run,
and is compelling enough that the Fleet keeps it online — and that other
ecosystems in the national network might want to copy.

## Scope note

This document and its siblings (`specification.md`, `usecases.md`) cover the
**event engine and product vision**. The public site's build details live in
`stem-ecosystem/docs/site-implementation-spec.md`; this project treats that
site as its downstream consumer and does not restate its internals.
