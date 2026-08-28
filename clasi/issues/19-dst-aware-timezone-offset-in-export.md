---
status: pending
---

# Exported dates carry a hard-coded -07:00 offset and are wrong outside DST

## Description

`partner_scrape/normalize/run.py:63` declares `_TZ_OFFSET = "-07:00"` and `_iso()` (line 115)
appends it to every naive datetime on its way into `Opportunity.date_start` / `date_end`:

```python
_TZ_OFFSET = "-07:00"

def _iso(dt: datetime | None) -> str:
    if dt is None:
        return ""
    if dt.tzinfo is not None:
        return dt.isoformat()
    return dt.isoformat() + _TZ_OFFSET
```

`-07:00` is Pacific **Daylight** Time. San Diego is `-08:00` (PST) from early November to mid-March.
For roughly four months a year every exported date is stamped with an offset one hour off from the
real local time.

Blast radius is every consumer of a date:
- `site/src/data/opportunities.json` — the site's own listings and calendar view.
- The `public/data/` export added in sprint 009, which issue 15 published as a
  self-describing contract other people are invited to consume.
- `export/writer.py::is_current_or_upcoming`, which decides what is "current" — so an event
  can be filtered in or out on the wrong side of a boundary.

## Cause

No adapter sets `tzinfo` (confirmed: `normalize/run.py` coerces every aware datetime to naive in one
place precisely because BiblioCommons and Lever emit aware datetimes and mixing them crashed
`min()`/`max()` in collapse/dedup). So a single offset had to be chosen for naive values, and a
constant was the simplest thing that worked when it was written — in a month when it happened to be
correct.

This was found during sprint 009's design-doc bootstrap and judged out of scope for that sprint: it
concerns exported date correctness but was orthogonal to both issues in play and unblocked neither.

## Proposed fix

Resolve the offset per-datetime from a real timezone rather than a constant:

- Use `zoneinfo.ZoneInfo("America/Los_Angeles")` (stdlib, no new dependency) and localize each naive
  datetime, letting it produce `-07:00` or `-08:00` as the date dictates.
- Keep the existing "an aware datetime's own offset is left untouched" behavior.
- Decide explicitly what to do with the ambiguous and non-existent local times inside the DST
  transition itself (the 1am-2am repeat in November, the missing hour in March). `fold` is the stdlib
  mechanism; picking a documented convention beats leaving it implicit.

## Verification

- Unit tests asserting a July datetime serializes with `-07:00` and a January one with `-08:00` —
  the test that would have caught this.
- A test for each DST-transition edge case, whatever convention is chosen.
- Confirm `is_current_or_upcoming` still partitions correctly across a boundary.
- Full suite green.

## Related

- `partner_scrape/normalize/run.py:63,115` — the constant and its only use.
- `partner_scrape/normalize/DESIGN.md` — documents the current behavior; update it.
- `partner_scrape/export/writer.py::is_current_or_upcoming` — the correctness consumer.
- Sprint 009 (`clasi/sprints/done/009-data-correctness-and-complete-export/`) — where this was found
  and deferred.
