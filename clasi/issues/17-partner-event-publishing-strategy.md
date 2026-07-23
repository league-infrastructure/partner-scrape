---
status: pending
---

# Multi-pronged event-publishing strategy for partners (harmonized with the scraper)

Publish a page — human-readable and LLM-readable — that documents our
event schema and tells a partner **how to make their events easy for us
to ingest**. Offer several *standard* ways to publish; a partner picks
whichever fits their site. Every method here must map onto how the
scraper already works (the Adapter framework in
`partner_scrape/adapters/`, dispatched by `adapter_type` — registering a
new type is a one-line addition to the `ADAPTERS` table in
`adapters/base.py`). We are **not inventing formats** — where a standard
exists we use it.

Connects to **issue 16** (this is the page `llms.txt` points partners
and agents at) and **issue 15** (the schema/fields a published event
must carry, and the append-only per-partner storage that ingested
events land in).

## What the scraper already ingests well (harmonize with these)

These `adapter_type`s exist today (source counts from the registry):

- **`generic_html` / `listing_html`** (86 sources) — the workhorse.
  Sitemap/listing-page **discovery** (`discovery/sitemap.py`) plus an
  HTML **extraction ladder** that pulls events out of arbitrary pages.
- **`ical`** — iCalendar (`.ics`) / RSS feeds (RFC 5545). A partner just
  gives us a feed URL.
- **`tec_rest`** (7 sources) — **The Events Calendar (TEC)**: a very
  common WordPress events plugin that exposes events at a REST endpoint
  (`/wp-json/tribe/events/v1/events`). ("TEC" is that plugin — many
  nonprofit WordPress sites already run it, which is why it earns its
  own adapter.)
- **`wp_rest`** — the generic WordPress REST API.
- **`localist`** — the Localist calendar API (common at universities).
- **`bibliocommons`** (2) — BiblioCommons library-system events API.
- **`greenhouse`** (3) / **`lever`** — ATS job/internship boards.
- **`leaguesync`** — the League's own `sync.jtlapp.net` API.

So we're already strong at: **feeds** (iCal/RSS), **CMS/plugin REST
APIs** (TEC, WordPress, Localist, BiblioCommons), **ATS APIs**
(Greenhouse, Lever), and **sitemap-driven HTML extraction**.

## New partner-facing ways to publish (the multi-pronged strategy)

Ordered easiest-adoption first. Each note says how it harmonizes with an
adapter.

### A. `.well-known` discovery pointer
There is **no registered `.well-known` standard for events** — the
closest prior art is the `.well-known/feed-menu.json` feed-discovery
Internet-Draft and the older RSD (Really Simple Discovery) convention.
So rather than invent an event *payload* format under `.well-known`, use
a small **pointer file** there (the same pattern as `security.txt` /
`llms.txt`): it names the URL(s) of the partner's real event feed
(their `.ics`, their JSON-LD pages, their OpenActive feed, or a JSON
file in our schema). Our discovery step reads it, then hands the
referenced feed to the matching existing adapter. Low partner effort,
no plugin required.

### B. Sitemap + schema.org `Event` JSON-LD (the "semantic tags" idea)
The standard way to make event *pages* machine-readable: the partner
embeds **schema.org `Event`** structured data as JSON-LD
(`<script type="application/ld+json">`) on each event page, and lists
those pages in their `sitemap.xml`. This is exactly what Google's event
rich results (and increasingly ChatGPT/Perplexity) consume, so many
partners get it "for free" from their CMS. We **already read sitemaps**
and already run an extraction ladder — this is a new, high-priority
**rung on that ladder** (or a small dedicated adapter): fetch each
sitemap URL, parse JSON-LD `Event` objects. Convention: one event per
page (Google's guidance).

### C. iCalendar feed (already supported — just document it)
A partner publishes an `.ics` feed and gives us the URL; the existing
`ical` adapter ingests it unchanged. This costs us nothing new — it's
purely a documentation/onboarding item on the page. List it as the
lowest-friction option for anyone who already has a calendar.

### D. OpenActive feed (stretch — the purpose-built standard)
**OpenActive** is a real open-data standard *specifically for
"opportunity data"* — the same term this project uses — built on
schema.org with the RPDE (Realtime Paged Data Exchange) feed format. It
even defines a light publication level (just name/location/contact/
activities). Heaviest to adopt and few local partners will have it, but
it's the most domain-appropriate standard, so flag it as a candidate
new adapter (`openactive`/RPDE) rather than building it first.

### E. Our own documented JSON in our schema (universal fallback)
For a partner with no CMS plugin and no calendar: host a JSON file in
**our published schema** (issue 15) at a documented path, and reference
it from the `.well-known` pointer (A). A new tiny adapter reads it
directly. This guarantees *every* partner has at least one option.

## Harmonization requirement

Nothing above is a bespoke pipeline: each new method resolves to an
`adapter_type` (a new discovery pointer feeding existing adapters for A;
a JSON-LD extraction rung/adapter for B; existing `ical` for C; a new
`openactive` adapter for D; a small schema-JSON adapter for E). All of
them land in the **append-only per-partner store from issue 15**. The
published "LLM page" documents the schema once and then lists A–E
easiest-first, so a partner (or their AI agent) can self-serve.

## Open questions (for review)

- Which subset of A–E do we build first? (Proposed: **B (schema.org
  JSON-LD)** and **C (iCal, ~free)** first; **A (.well-known pointer)**
  to tie discovery together; **D/E** later.)
- For A, do we adopt the `feed-menu.json` draft shape as-is, or a
  smaller pointer of our own that references the issue-15 schema? (Draft
  is unratified — need a call.)
- schema.org `Event` → our opportunity schema: which fields map cleanly,
  and what's missing (age/grade, cost bands, NGSS, areas of interest are
  League-specific and won't be in vanilla schema.org)?
- Do partners self-declare which method they use, or does discovery
  probe (`.well-known` → sitemap JSON-LD → `.ics`) in order?
</content>
