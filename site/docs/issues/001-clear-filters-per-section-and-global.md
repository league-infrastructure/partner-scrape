# Filters: per-section "Clear" links + a global "Clear all filters"

**Reported by stakeholder (Eric), 2026-07-20, from the live Opportunities page.**

Each filter section (Areas of Interest, Age/Grade, Cost, Opportunity Type,
Time of Day, …) needs a way to reset **just that section** back to default
(nothing selected). It should be a plain text **link** at the bottom of the
section — not a button.

Plus a single **"Clear all filters"** link at the bottom of the whole filter
list that resets every section to default.

- Component: `src/components/OpportunityFilters.astro` (markup) +
  `src/scripts/filters.js` (state reset + re-filter).
- Per-section clear resets only that facet group's checkboxes/inputs and
  re-runs filtering; global clear resets all.
