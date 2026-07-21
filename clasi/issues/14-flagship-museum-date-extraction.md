---
status: pending
---

# Flagship museums under-yield: date extraction fails on their event pages

The recognizable STEM institutions are badly under-represented, which hurts
the demo (their names are what the Fleet/partners recognize). Diagnosed
2026-07-20 via `--source X --no-enrich`:

| Source | raw events found | exported (dated + upcoming) |
|--------|------------------|------------------------------|
| San Diego Natural History Museum (sdnhm) | 39 | **0** |
| San Diego Air & Space Museum | (yields) | **0** |
| Fleet Science Center (listing_html) | 11 | **1** ("STEM Camps") |
| Birch Aquarium (localist API) | — | 2 |

Root cause: the generic HTML extraction ladder (JSON-LD → `<time>` → OG →
URL date → body regex) isn't finding a usable **date** on these museums'
event pages, so the current+upcoming export filter drops them all as
undated. Their listing pages likely carry the event but not the date (date
is on the detail page), and/or the pages are JS-rendered.

## Proposed scope
- For listing_html/generic_html museum sources: follow through to the
  **detail page** for the date, or add JSON-LD/`<meta>` date extraction
  tuned to these platforms.
- Consider the headless fetch path (already built) for JS-rendered museum
  calendars.
- Possibly per-source date selectors for the top flagships (Fleet, SDNHM,
  Air & Space) — high value, small N.
- Success = Fleet/SDNHM/Air & Space each contribute a realistic count of
  dated upcoming events, not 0-1.
