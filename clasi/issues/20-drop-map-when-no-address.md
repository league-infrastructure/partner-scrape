---
status: pending
---

# Drop the map when there isn't a mappable address

When an opportunity has no mappable address (no usable
latitude/longitude or geocodable location), don't show a map for it —
neither a broken/empty embed nor a stray marker at `(0,0)` / the map
center. The map should only appear when there's a real location to show.

## Where this applies
- **Detail page** (`site/src/pages/opportunities/[slug].astro`): if the
  opportunity has no lat/long (and no geocodable `location`), omit the map
  section entirely rather than rendering an empty/placeholder map.
- **Opportunities Map view** (`site/src/pages/opportunities/index.astro`,
  the `#map-container` / Map toggle): only plot opportunities that have
  real coordinates; unmappable ones simply don't get a marker. Consider
  whether to note "N of M shown on map" so it's clear some aren't plotted.

## Notes
- Opportunity records carry `latitude` / `longitude` / `location`; many are
  null/blank. Treat missing or `(0,0)`/nonsensical coordinates as
  unmappable.
- Keeps List/Calendar views unaffected (those items still appear there).
- Applies to both beta (`partner-scrape/site`) and production
  (`stem-ecosystem`).
