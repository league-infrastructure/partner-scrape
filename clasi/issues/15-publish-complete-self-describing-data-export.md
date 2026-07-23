---
status: pending
---

# Publish a complete, self-describing data export (partners + per-partner event lists)

As part of normal site operation, publish the full dataset as JSON so
the entire site can be reconstructed from the published files alone.
This is a public data contract, not just the site's internal build
input.

## Desired shape (published)

- A top-level **`partners.json`** listing every partner. Each partner
  entry contains everything needed to render its page — the fields we
  already carry (`name`, `organization_type`, `description`, `location`,
  `latitude`/`longitude`, `website`, `phone`, `email`, socials,
  `logo_src`; see the current 153-entry `site/src/data/partners.json`).
- For **each partner**, its own event/opportunity files, and
  `partners.json` **refers to** those files (a path/URL per partner).
- Each partner has **two** event lists:
  - **past events** — anything whose date is in the past.
  - **`events.json`** — anything current/upcoming.
- Event entries carry everything needed to render (the current
  opportunity schema: `title`, `description`, `link`, dates,
  `age_grade_level`, `cost_range`, `time_of_day`, `opportunity_type`,
  `areas_of_interest`, `location`, lat/long, contact fields,
  `logo_src`, `image_src`, …).
- **Invariant:** given `partners.json` + each partner's event files, you
  can completely reconstruct the site — no other data source required.

## Storage model (revised — persistent, per-partner, append-only)

Change how we store the data so events persist across runs. In the data
directory:

1. **Per-partner directory keyed by slug.** Every partner gets a
   directory named after its slug.
2. **Per-partner partner JSON.** Each directory holds that partner's own
   JSON entry — i.e. break up the monolithic `partners.json` and split
   it into the per-partner directories. Scraping a partner writes into
   that partner's directory.
3. **Append-only opportunities JSON Lines log.** Each directory has a
   JSON Lines (`.jsonl`) file of opportunities. Each line carries a
   **`slug`** (stable event identity) and a **`content_hash`** (see
   "Event identity, dedup & update rule" below) alongside the event
   data. On each scrape:
   - Read the existing `.jsonl`.
   - Scrape the site for its current events; compute `(slug,
     content_hash)` for each.
   - **Skip** a scraped event when a line with the **same `slug` and the
     same `content_hash`** already exists (unchanged — do nothing).
   - **Append** a new line when the `slug` is new, or when the `slug`
     matches but the `content_hash` differs (the event changed).
   - This is strictly **append-only** — never read-modify-rewrite the
     file. Just append the new line set. (This is what makes past events
     persist: nothing is ever pruned, so history accumulates naturally.)
4. **Build-time projection.** When building the site (after scraping),
   collapse each `.jsonl` to one record per `slug` with **last line
   wins**, then generate the published per-partner **`events.json`** from
   the records whose dates are **in the future** (current/upcoming) and
   the **past-events** list from the past ones.

## Event identity, dedup & update rule (defined)

**Event identity (`slug`).** Compute a stable per-event slug, resolved
in this order (proposal — open to revision):

1. **Unique registration/detail link.** If the event has a link that
   uniquely identifies it (its own registration or detail URL, distinct
   from the listing page), slugify that URL. This is the strongest
   identity because it survives content edits.
2. **Title + date/time.** When several events share one page and have no
   per-event unique link, derive the slug from the normalized title plus
   start date/time.

Slugs are scoped to the partner directory, so the partner is already
implied — no need to include it in the slug.

**Known trade-off:** a title+date slug conflates identity with content,
so if a partner *renames* an event (case 2), it will look like a new
event rather than an update. Events with a stable registration link
(case 1) don't have this problem. Acceptable given there's no stable
partner-supplied id; noted so no one is surprised.

**Content hash.** Hash the normalized published event fields (title,
description, dates, location, cost, etc. — the schema fields, excluding
derived/volatile ones). This detects whether an event's content changed.

**Dedup + update rule (the whole thing in one place):**

- `slug` new → **append** (new event).
- `slug` matches, `content_hash` same → **skip** (unchanged; write
  nothing).
- `slug` matches, `content_hash` differs → **append** (event changed; a
  new line is added, the old line stays).
- **Assembly:** group by `slug`, **last line wins** — which only matters
  when a slug has multiple lines (i.e. the event changed over time).

Then the site build **reads all per-partner directories** (partner JSON
+ `.jsonl`) and assembles them into the publishable dataset
(`partners.json` + per-partner event files) so consumers can fetch the
JSON.

## Gap vs. today

The current exporter (`partner_scrape/export/writer.py`) does NOT work
this way yet:

- It writes a **single flat** `src/data/opportunities.json` (all opps in
  one array), not per-partner directories/files.
- It **drops past events**: `_is_current_or_upcoming()` filters to
  current+upcoming before writing, and each run overwrites — nothing
  persists. The append-only `.jsonl` model above is what fixes this.
- `partners.json` is **not** part of the export contract today (writer
  emits only `opportunities.json` + `scrape-meta.json`; `ads.py` emits
  `ads.json`), and it is a single monolithic file rather than split
  per-partner.

## Proposed scope

- Introduce the per-partner directory layout (`<data>/<slug>/`) with a
  partner JSON + append-only opportunities `.jsonl` per partner.
- Change the scrape/ingest step to read the existing `.jsonl`, dedup
  scraped events against it, and append only new lines (no rewrite).
- Add a build/assembly step that projects the `.jsonl` logs into the
  published `partners.json` + per-partner `events.json` (future) and
  past-events file, and that stitches per-partner partner JSON back
  together for consumers.
- Keep `scrape-meta.json` (last_updated) semantics.

## Open questions

- Directory/URL layout and the exact reference format in `partners.json`
  (relative path? full URL? the slug the consumer resolves?).
- Does the Astro site get refactored to consume this new per-partner
  shape, or is this an *additional* published artifact next to the
  existing build input?
- How far back do published "past events" go — all history, or a bounded
  window? (The `.jsonl` keeps everything regardless.)
- Where is this published/served from (the `stem-ecosystem` site dir, a
  separate public path)?
</content>
