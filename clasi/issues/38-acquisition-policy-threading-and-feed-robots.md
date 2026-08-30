---
status: pending
---

# Thread acquisition_policy into the fetcher; decide robots policy for feed endpoints; populate Fleet event location

## Description

Three follow-ups from sprint 014 ticket 004's live registration work
(full evidence in that ticket's Notes section):

1. **`acquisition_policy` is dead config.** No adapter threads
   `acquisition_policy.respect_robots` / `rate_limit_seconds` from the
   source TOML into `PoliteFetcher.get()`'s per-call parameters —
   including `leaguesync.py`, which sets `respect_robots = false` to no
   effect. Fix: thread the per-source policy through the fetch path (or
   into fetcher construction per source) with fixture tests.
2. **Robots policy for published feed endpoints — STAKEHOLDER
   DECISION.** Five live, high-yield, well-formed feeds are currently
   blocked solely by host robots.txt: SD County Parks (Tockify ICS, 553
   events), San Diego Astronomy Association + Mission Trails Foundation
   + Surfrider SD (calendar.google.com ICS), SWE San Diego (existing
   partner with no other source). These are subscription URLs designed
   to be polled by calendar clients; robots.txt on tockify/gcal targets
   crawlers. Whether partner-scrape treats an explicitly-published ICS
   subscription URL as feed-client traffic (fetch, politely, ignoring
   robots for that URL class) or keeps strict robots compliance is a
   policy call for Eric — decide before enabling (1) for these sources.
   Registration TOMLs for all five are drafted in ticket 014-004's
   notes and were NOT committed.
3. **Fleet listing_html never populates `Event.location`**, which is
   exactly what blocked the measured Balboa Park ↔ Fleet cross-source
   dedup collapse ("Educator Open House" 2026-09-24 matched on
   title+date, failed on venue). Populate location in the Fleet adapter
   path (the venue is constant: 1875 El Prado) and re-measure the
   Balboa Park overlap.

Also worth re-probing when touched: navalstem.us (TEC valid, total=0
this window — seasonal), cafirst.org (no TEC REST despite plugin
markup — needs a different approach; issue 30 covers FIRST events),
California DI / Cabrillo NM Foundation (Squarespace per-event ICS only
— a small multi-URL ical enhancement would unlock both).

## References

Sprint 014 ticket 004 notes; gap analysis:
https://claude.ai/code/artifact/02ba9c3e-61a2-40eb-a987-444463cd3266
