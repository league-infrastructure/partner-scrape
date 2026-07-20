# Filters: show result counts per option; make empty options obvious

**Reported by stakeholder (Eric), 2026-07-20, from the live Opportunities page.**

The dataset is static (build-time `opportunities.json`), so we can compute
counts at build time and show the number in each filter label:

> Areas of Interest → "Earth Science / Ecology (77)", "Engineering (37)" …
> Cost → "Free (159)" …

Options with **0 matching opportunities** should be visually de-emphasized or
disabled, so a user knows *before* clicking that there's nothing there.
Today you can click a facet and get an empty list — frustrating.

- Component: `src/components/OpportunityFilters.astro` (render counts) +
  `src/scripts/filters.js` / the page's data import (compute counts).
- Counts can be static (total per value) to start; live "counts given the
  other active filters" is a nicer v2 but not required.
- **Related:** counts will make it obvious that 7 of 8 `opportunity_type`
  values are empty — root cause is the data (all events default to
  "Out-of-school Programs"); tracked in the `partner-scrape` repo issue
  "Classify opportunity_type during enrichment".
