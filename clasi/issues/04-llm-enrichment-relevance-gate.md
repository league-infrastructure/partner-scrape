---
status: pending
---

# LLM enrichment + relevance gate (keystone)

A single LLM pass over new/changed events that recovers what deterministic
extraction couldn't and decides what belongs on the site. This is the
highest-leverage piece — it unlocks the noisy long-tail and discovery
sources and retires the brittle keyword tables.

## Why

Only ~57% of extracted events have a real parsed date, and classification is
done with hand-written keyword regex. As an aggregator ingesting thousands of
records from hundreds of orgs, we need one reliable normalizer, not a
growing pile of regexes.

## Proposed scope

- **Date/field recovery** — extract dates, times, location, registration,
  cost from description text where structured extraction failed.
- **Controlled-vocab classification** — assign `areas_of_interest`,
  `age_grade_level`, `cost_range`, `time_of_day` directly.
- **Relevance verdict** — "is this a STEM learning opportunity for youth?"
  This gate is what makes libraries, Eventbrite/Meetup, and discovery
  sources safe to ingest without flooding the site with noise.
- Run only on new/changed records (keyed off cache/confidence) to control
  cost — a few dollars per full refresh at this volume.

## Sequence

Depends on: 01–03. Everything noisy downstream depends on this gate.

_Proposal / mock-up — rewrite freely._
