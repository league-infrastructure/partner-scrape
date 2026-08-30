---
status: pending
---

# Partner roster expansion + data housekeeping

## Description

The 153-partner roster was inherited from the Drupal site and never
re-surveyed. Register the organizations the 2026-08-30 research found
(as sources where scrapable, and as partner-directory entries either
way — they are also a recruitment list for Fleet/League outreach):

**Parks/nature:** SD County Parks & Recreation, Mission Trails Regional
Park Foundation, Tijuana River NERR/Estuary, Cabrillo National Monument
(+ Foundation), San Diego Bird Alliance, San Diego Coastkeeper,
WILDCOAST, Surfrider SD, Torrey Pines Docent Society, Batiquitos Lagoon
Foundation, San Diego Botanic Garden, California Wolf Center, Helen
Woodward Animal Center, SD Humane Society, SEACAMP San Diego, CNPS SD.
**Astronomy:** San Diego Astronomy Association, Palomar Observatory,
SDSU Mount Laguna Observatory, Palomar College Planetarium.
**Museums:** Maritime Museum of San Diego, Comic-Con Museum, SD
Archaeological Center, SD Mineral & Gem Society, SDSU Biodiversity
Museum, New Children's Museum.
**Libraries:** Oceanside, Carlsbad, Escondido, Coronado, Chula Vista,
National City city libraries.
**Youth orgs:** 4-H San Diego (UCCE), Boys & Girls Clubs (4 councils),
YMCA of San Diego County, Girls Inc. of SD County, Scouting America
SD-Imperial, Lawrence Family JCC.
**Competitions/clubs:** Classroom of the Future Foundation, NDIA San
Diego, SD Cyber Center of Excellence, SD County Engineering Council,
SHPE San Diego, San Diego Math Circle, California DI (HQ in SD),
Hack Club chapters.
**Research/health:** SDSC, Jacobs School of Engineering, Sanford
Burnham Prebys, La Jolla Institute, Scripps Research, JCVI, NIWC
Pacific, NOAA SWFSC, Rady Children's (sdhealthscholars.org).
**Pipeline/adult:** Reality Changers, SD Workforce Partnership
(CONNECT2Careers), Barrio Logan College Institute, EAA Chapter 14
(Young Eagles, Brown Field), Scripps Research Front Row, Nerd Nite SD,
Taste of Science SD, Astronomy on Tap SD, United Way SD
(STEAM-to-Careers).

**Housekeeping (existing partner data):**
- Water Conservation Garden URL → thegarden.org (working TEC REST).
- SDSU MESA URL mep.sdsu.edu → mesa.sdsu.edu (301s today).
- batiquitosfoundation.org is HIJACKED (spam) — never link it; the real
  site is batiquitoslagoon.org. Audit other partner URLs for the same.
- Duplicate partner rows in partners_viable.csv (Living Coast ×2,
  EIS ×2, GSDSEF ×2, SDRPF ×2, Fleet ×2, Viasat ×2, Media Arts ×2,
  Ocean Connectors ×2, SD Futures ×2, Salk ×2) break the
  found→published join — dedupe or canonicalize.
- Defunct (mark, don't register): EarthFair, Maker Faire San Diego,
  Fab Lab SD, SD Makers Guild, SD Science Alliance, KidzToPros.
- Academic Connections canceled 2026; JCVI La Jolla internships paused
  2026 — record as negative signals so nobody re-registers them blind.

## References

Gap analysis 2026-08-30: https://claude.ai/code/artifact/02ba9c3e-61a2-40eb-a987-444463cd3266
