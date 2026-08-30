---
status: pending
---

# Register the verified structured feeds (zero new adapters)

## Description

The 2026-08-30 research verified these feeds live. Every one fits an
adapter that already exists — this issue is TOML registration plus
partner-roster entries, not engineering. Highest coverage-per-hour item
in the backlog.

**TEC REST (existing `tec_rest` adapter):**
- balboapark.org — park-wide calendar, 170 upcoming (Workshop 62,
  Lecture 16, Kid Friendly 3). Covers every Balboa Park institution;
  dedupe against Fleet/Nat partner sources (cross-source dedup exists).
- cafirst.org — FIRST California: FRC San Diego District Event (Mar
  20-22 2026), FTC events, FLL CA-Southern qualifiers.
- sdcoastkeeper.org — cleanups, water-quality monitoring, Science to
  Stewardship (HS).
- ymcasd.org — verified REST; camps/events.
- comic-con.org/museum — STEAM makerspace events, ICS too.
- sandiegoarchaeology.org — free 2nd-Saturday programs, day camp.
- shpesd.org — Noche de Ciencias, SHPE Jr.
- navalstem.us — Navy STEM events (Miramar Air Show Student Day etc.).
- thegarden.org — Water Conservation Garden's real site (partner URL
  fix; working TEC REST).
- jasandiego.org — Junior Achievement (partner, currently unregistered;
  TEC verified, 1 event today).

**iCal (existing `ical` adapter):**
- SD County Parks: https://tockify.com/api/feeds/ics/sdparkscalendar —
  553 free ranger programs incl. 18 "Parks After Dark" star parties;
  countywide incl. East County. Single biggest free-programming feed.
- San Diego Astronomy Association Google Calendar (sdaa@sdaa.org) —
  677 events; free public star parties.
- Mission Trails Regional Park Foundation Google Calendar — 164 events.
- Surfrider SD Google Calendar — 2,313 events (filter to STEM-ish).
- SWE San Diego Google Calendar (embedded on swesandiego.org).
- California DI (caldi.org, Squarespace) — per-event ICS links.
- Oceanside Public Library — LibraryMarket
  https://oceansidepl.librarycalendar.com/events/feed/ical — weekly
  CSUSM-led STEM.
- Coronado Public Library — LibraryMarket ICS, same pattern.
- Cabrillo National Monument Foundation (Squarespace ?format=ical).

**Localist (existing `localist` adapter):**
- calendar.ucsd.edu — register additional group_ids beyond Birch:
  Physics outreach, Extended Studies, Jacobs School, SDSC, Qualcomm
  Institute; also type=Volunteer. K-12 yield modest; gate does the
  filtering.

**Needs a small new adapter (stretch, or split off):**
- LibCal (Carlsbad carlsbadca.libcal.com, Escondido cid=16268) — public
  iCal subscribe URLs exist; check whether the plain `ical` adapter can
  consume them directly before writing anything new.
- NPS events API for Cabrillo (developer.nps.gov, free key).

Register each org in the partner roster too where absent (see issue on
roster expansion). Respect robots (balboapark.org allows /wp-json;
crawl delays noted in research).

## References

Gap analysis 2026-08-30: https://claude.ai/code/artifact/02ba9c3e-61a2-40eb-a987-444463cd3266
