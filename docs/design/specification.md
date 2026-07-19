# Specification — San Diego STEM Ecosystem Event Engine

Status: initial draft from stakeholder briefing (2026-07-18). Sections
marked **[OPEN]** are deliberately unresolved and are the agenda for the
design discussion that follows initiation — they are captured here so the
detail is not lost, not because they are decided.

---

## 1. Background and stakeholders

### 1.1 The site and the network

- **sdstemecosystem.org** is the web presence of the San Diego STEM
  Ecosystem, San Diego County's member of the national **STEM Learning
  Ecosystems Community of Practice**, which is designed and run by **TIES**
  (Teaching Institute for Excellence in STEM, tiesteach.org).
- The **Fleet Science Center** (1875 El Prado, Balboa Park, San Diego, CA
  92101; phone 619-238-1233) is the local **backbone / host** organization.
  The site is currently a Drupal site the Fleet pays a vendor to maintain.
- The ecosystem is a network of **150+ partner organizations** —
  museums, nature centers, libraries, aquariums, school districts,
  nonprofits, and companies offering STEM programs.

### 1.2 The problem

- The site depends on partners **manually posting** their own events and
  programs. In practice they rarely do, so the directory is stale and
  under-used. The lack of a consistent communication campaign to get
  partners to cross-promote is visible directly in the (thin) usage data.
- The Fleet was under **budget pressure**: ~$3,000/year for maintenance and
  hosting, and at the time this effort began it was **considering taking the
  site offline**. That specific pressure may have eased since, but the site
  remains unmaintained and nobody updates it. Treat "the site could be shut
  down or left to rot" as the core risk this project exists to counter.

### 1.3 Who's involved

- **The League of Amazing Programmers** ("the League", jointheleague.org) —
  builds and runs the scraper and the reinvigorated site. Executive
  Director: Eric Busboom. Business Development: Jed Stumpf.
- **Fleet Science Center** — host/decision-maker. Contact: Eric Meyer,
  Assistant Director of Education and Engagement (stem@rhfleet.org). Also
  Chris LaZich, VP for Advancement (fundraising).
- **Partner organizations** — the ~150 orgs whose events we scrape and whose
  programs we cross-promote.
- **End users** — San Diego families, students, and educators looking for
  STEM events, programs, and (newly) internships.

## 2. Goals and business model

### 2.1 Product goal

Make sdstemecosystem.org a **genuinely useful, always-fresh public directory
of STEM learning opportunities** in San Diego County, populated
automatically by scraping partners rather than by manual entry.

### 2.2 The League's model (why we invest the effort)

- The League builds and operates the scraper and keeps the directory
  populated **as goodwill** toward the ecosystem and the Fleet.
- In return, **the League's own content is featured** on the site (our
  events and programs appear in the directory alongside partners'), and
  **the sidebar advertising on the site is entirely the League's**. The ad
  space is the return on our investment. This is the explicit reason the
  League is doing this work.
- Keeping the Fleet's hosting cost near zero (static site on GitHub Pages
  vs. $3,000/year Drupal) is part of the pitch that keeps the site alive and
  the arrangement in place.

### 2.3 Sustainability goal

The whole system must run **unattended and cheaply**: a scheduled pipeline
that refreshes data with no per-event human effort, publishing to a static
host. Target ongoing cost: ~$0 hosting plus a few dollars of LLM usage per
refresh.

## 3. System architecture

Two repositories, one data flow:

```
partner-scrape (THIS REPO — the event engine)
  sources → scrape/cache → extract → normalize → merge/dedup → export
                                                                   │
                                                                   ▼
stem-ecosystem (the site)   src/data/opportunities.json + partners.json
  Astro static build → GitHub Pages (www.sdstemecosystem.org)
```

- **This repo owns**: source registry, fetching/caching, per-platform
  extraction, normalization to the site schema, dedup, and the export that
  writes `opportunities.json` into the site repo. Decided: the scraper lives
  here in `partner-scrape`, not in the site repo.
- **The site repo owns**: rendering, filtering UI, partner/opportunity
  pages, styling, deploy. Its internals are specified in
  `stem-ecosystem/docs/site-implementation-spec.md` and are out of scope
  here except as the contract for our export format.
- **Contract between them**: the `opportunities.json` schema (see §5) and
  `partners.json`. The export step (`dev/export_site.py`) is the seam.

### 3.1 Scrape cache

Scraped partner websites are cached under `SCRAPE_CACHE_DIR`
(`/Volumes/Cache/stem-ecosystem`, set via dotconfig `prod`). The cache holds
raw HTML and response metadata and is deliberately kept off the repo volume
and out of git — the mirror corpus is tens of GB.

### 3.2 Configuration

Environment configuration is managed by **dotconfig** (layered `.env` under
`config/`). The active deployment is `prod`. Secrets are SOPS-encrypted;
public config lives in `config/prod/public.env`.

## 4. Event sources and acquisition tiers

From the analysis in `dev/SCRAPER_GUIDELINES.md` (144 sites analyzed, ~7,000
records extracted). Acquisition strategy is tiered by what each site offers:

- **Tier 1 — Structured APIs (best).** WordPress + **The Events Calendar
  (TEC)** REST API (`/wp-json/tribe/events/v1/events/`) returns clean JSON
  with dates, venue, organizer, cost, categories, image. Currently ~6 sites
  (Coastal Roots Farm, The Living Coast, I Love A Clean San Diego /
  cleansd.org, Ocean Connectors, EEF Kids, and newly San Diego Children's
  Discovery Museum via visitcmod.org). Also the broader WordPress REST API
  and calendar platform APIs (e.g. UCSD **Localist** for Birch Aquarium).
- **Tier 2 — Sitemaps.** ~100 of 144 sites expose XML sitemaps. Fetch the
  sitemap, identify event/program URLs by path pattern, diff against the
  previous run's sitemap by `<lastmod>`, and fetch only changed pages.
- **Tier 3 — Full mirror + directory scan.** Sites without sitemaps: mirror
  and walk for event-like directories.
- **Tier 4 — Manual/undetermined.** Sites with no obvious events, needing
  keyword search or manual review — includes, notably, the **Fleet Science
  Center's own site**, whose events are currently NOT being captured.

Per-platform extractors already exist for BiblioCommons (San Diego County
Library, high volume, 100% dated), Drupal (sandiego.gov), title/URL-embedded
dates (Olivewood Gardens), and a generic fallback (JSON-LD Event schema,
`<time datetime>`, OpenGraph meta, URL date patterns).

### 4.1 Known source gaps (must fix)

- **Fleet Science Center's own events are absent.** A Fleet-hosted site with
  no Fleet events is the first thing the Fleet will notice. High priority.
- **Birch Aquarium (UCSD Localist API) produces nothing** — adapter
  incomplete.
- **Wix sites (9)** render client-side; mirrored HTML is nearly empty. Need
  a headless browser or server-render trigger.
- **Date coverage**: ~57% of extracted events have a real parsed date.
  Thousands have descriptions but no date. Planned fix: an **LLM extraction
  pass** (Claude, est. a few dollars for the corpus) plus JSON-LD and iCal
  parsing.

## 5. Data model — what an event/opportunity is

The site's contract schema (produced by `dev/export_site.py` into
`opportunities.json`). Each opportunity record has:

| Field | Meaning |
|-------|---------|
| `slug` | Stable unique id (`org_title_date`) |
| `title` | Event/program title (cleaned of embedded dates) |
| `partner_name`, `partner_id` | Owning org, joined to `partners.json` |
| `description` | Text description |
| `link` | Registration URL or canonical page URL |
| `availability` | Human string (times; "Repeats N times through …") |
| `date_start`, `date_end` | ISO datetime with San Diego offset |
| `age_grade_level` | Controlled: Pre-K, Grades 6-8, Grades 9-12, Adult, Family |
| `cost_range` | Controlled: Free, Less than $25/$50/$100/$200, Greater than $200 |
| `time_of_day` | Controlled: Morning, Afternoon, Evening, All Day |
| `opportunity_type` | e.g. Out-of-school Programs (**[OPEN]**: taxonomy needs internships, camps, field trips, company events) |
| `areas_of_interest` | Controlled science areas (Biology/Life Sciences, Earth Science/Ecology, Coding/CS/Cyber, Engineering, Physical Science, Mathematics, Chemistry, Physics, General Science) |
| `location`, `latitude`, `longitude` | Venue, geocoded |
| `contact_name/email/phone` | Optional |
| `logo_src` | Partner logo path |

Derived fields (`areas_of_interest`, `age_grade_level`, `time_of_day`,
`cost_range`) are currently inferred by **keyword rules** over title +
description + categories/tags. Recurring instances of the same (org, title)
are collapsed into one record spanning first-to-last date.

Only **current and upcoming** events are exported; historical data is used
for development but never ships.

**[OPEN] — the event model itself** is a primary discussion topic: how we
formally define "an event" vs. "a program" vs. "an internship", how we
decide where to find them per source, and how much of the classification
should move from keyword rules to LLM extraction.

## 6. Freshness, scheduling, and automation

- **Incremental, not full re-mirror.** The production scraper must refresh
  via API pulls and sitemap diffs, fetching only changed pages, rather than
  re-mirroring the whole corpus each run.
- **Suggested cadence** (from the roadmap): daily API pulls; weekly sitemap
  refresh + selective fetch; monthly full mirror for API-less sites.
- **Self-updating loop.** A scheduled job runs scrape → normalize → export →
  site rebuild → deploy with no human in the loop, and a visible
  "last updated" stamp on the site. Past events are pruned automatically.
- **[OPEN]** where the schedule runs (GitHub Actions in this repo committing
  to the site repo, vs. the League's Docker host) and how cross-repo commits
  are authenticated.

## 7. League content and advertising requirements

- The League's **own events and programs** must appear in the directory
  (the League is itself a partner org, jointheleague.org, with dated coding
  classes).
- The site must carry **League-owned sidebar advertising**. **[OPEN]**: ad
  placement, format, and whether ads are static or rotate — this touches the
  site repo, but the requirement originates here as a business constraint.

## 8. Extension — STEM companies, their events, and internships

A new expansion beyond the existing partner set:

- **Find San Diego companies related to STEM** (e.g. biotech, defense,
  software, aerospace, engineering firms).
- Scrape **any public events** they host (open houses, tours, talks,
  hackathons, career fairs).
- Scrape **internships** they offer (especially those open to students /
  early-career), as a career-pathway resource.

**[OPEN]** — the whole company/internship extension is a discussion topic:
how to source the company list, how to detect events vs. internships on
corporate sites (which rarely use TEC/sitemap event patterns and often use
ATS platforms like Greenhouse/Lever/Workday for jobs), how internships map
onto the opportunity schema (new `opportunity_type`, different date
semantics — application deadlines vs. event dates), and how to keep signal
high without scraping the entire corporate web.

## 9. Non-goals (for now)

- No server, database, CMS, or login on the public site — it stays static.
- No self-service event submission by partners (the whole point is that we
  scrape so they don't have to).
- No rebuild of the site's visual design beyond what `stem-ecosystem`
  already implements (the existing site is "good enough" to start).
- Not restating the site's internal build spec — that lives in the site repo.

## 10. Open questions carried into the design discussion

1. **Event model**: precise definitions and per-source discovery rules for
   event vs. program vs. internship; keyword rules vs. LLM classification.
2. **Additional event sources**: beyond partner sites — regional calendars,
   Eventbrite/Meetup, library systems, university calendars — which to add
   and how.
3. **Company/internship extension**: sourcing the company list, detecting
   corporate events and internships, schema changes, ATS handling.
4. **Automation home**: where the scheduled loop runs and how it deploys.
5. **Advertising**: format and placement of League sidebar ads.
