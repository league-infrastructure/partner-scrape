---
status: pending
---

# Scrape team websites for sponsors, and show which teams have one

## Description

Two related gaps in the teams directory shipped by sprints 011 and 012.

**1. You cannot tell which teams have a website.** `TeamCard.astro` declares `website` in its Props
interface but never renders it, and `TeamFilters.astro` has no facet for it. Only the detail page
shows the link — so finding the 53 teams worth clicking means opening 278 pages. Add a visible
indicator on the card and a "Has a website" filter.

**2. We have never fetched a single team page.** Measured against the current 278-team export:

| | Count | Where it came from |
|---|---|---|
| Teams with a `website` | **53** (all FRC) | TBA's structured field |
| Teams with `sponsors` | **49** (all FTC) | FTCScout's structured field |
| Team pages fetched | **0** | — |
| `website_status` populated | **0 of 278** | field exists, never written |
| `organization_website` | 97 | the matched CDE school row |

The two populated sets barely overlap: FRC teams have sites but no sponsor data, FTC teams have
sponsor data but no sites. Nobody has looked at the 53 pages we already know about.

The sponsor data we do have is already interesting — **Qualcomm sponsors 18 of 49 teams**, then BAE
Systems 4, DoD STEM 3, Teradata 3, Gene Haas Foundation 3, Carlsbad Educational Foundation 3, across
87 distinct sponsor strings. Knowing which companies fund youth robotics in San Diego is directly
useful for partner recruitment, and the 53 unscraped FRC sites are where the rest of that picture is.

## Cause

Sprint 011 deliberately shipped deterministic sources only. The robot-teams issue was explicit that
unattended *search* for unknown team websites is unreliable and prone to attaching the wrong site to a
team — that judgment still stands and is not what this issue revisits.

This is the narrower, tractable case: we already **know** these 53 URLs from TBA. Fetching a URL a
team publicly declared as its own is ordinary scraping, exactly what the engine already does for 101
partner sources. No search, no guessing, no attribution risk.

## Proposed fix

### Site surfacing (cheap, do first)
- Render a website indicator on `TeamCard.astro` — an icon or badge, using the existing `SocialIcon`
  component's `website` platform rather than a new asset.
- Add a "Has a website" facet to `TeamFilters.astro`, following its build-time `tally()` pattern.
- Populate `website_status` so the field stops being dead weight: `confirmed` once fetched with a 2xx,
  `unverified` for a declared-but-unfetched URL, `none` where we have nothing.

### Scraping and sponsor extraction
- A new step in the teams pipeline that fetches each known `website` through **`PoliteFetcher`** —
  robots.txt respected, per-domain throttled, conditional-GET disk cached. 53 URLs is a small, polite
  crawl. Never bypass robots for these.
- A dead or non-2xx link demotes `website_status` to `unverified` and is logged — a broken link
  published on a public directory is worse than no link.
- Extract sponsors from the fetched HTML. **This is the hard part and deserves an honest design.**
  Sponsors on a robotics team site are typically a footer logo wall: `<img>` tags whose `alt` text or
  filename carries the name, sometimes a "Sponsors" or "Our Partners" heading followed by a list.
  There is no schema.org vocabulary for it, so the existing `extract/ladder.py` does not apply.
  Consider a deterministic first pass (headings + `alt`/`title` text + link hostnames) and only then
  an LLM pass over the extracted candidate block — `enrich/llm_client.py`'s JSON-schema-constrained
  pattern and `enrich/cache.py`'s content-hash caching both fit, and 53 pages is affordable.
- **Normalize sponsor names.** The 87 existing strings already contain near-duplicates; scraped names
  will be worse ("Qualcomm" / "Qualcomm Inc." / "Qualcomm Incorporated"). Reuse
  `normalize/partners.py::normalize_org_name` for the match key and keep a display form. Do not write
  a second normalizer.
- Record provenance per sponsor: which came from a structured API field versus scraped from a page.
  A scraped name is a weaker claim and consumers should be able to tell.

### What to be careful about
- **Do not invent sponsors.** An LLM over a page footer will happily return the site host, the CMS
  vendor, or the school district as "sponsors". Constrain and verify; a wrong sponsor attributed to a
  real company is worse than an empty list.
- FLL teams have no websites at all (0 of 48) — this issue does nothing for them, by construction.

## Verification

- Fixture-based, no network at test time. **Fixtures must be captured from real team pages**, not
  hand-authored — sprint 011's TBA defect (a hand-written fixture using `"CA"` when the API returns
  `"California"`) dropped 59 of 78 FRC teams and passed every unit test.
- A test proving a non-2xx or unreachable site demotes `website_status` rather than publishing a dead
  link.
- A test proving robots.txt disallow is honored.
- The existing export privacy test (no email pattern anywhere in `teams.json`) must still pass —
  scraped pages are a new vector for picking up a coach's address.
- A live run reporting: pages fetched, 2xx rate, teams gaining sponsors, and the new distinct-sponsor
  count. Eyeball a sample of extracted sponsors for false positives before closing.
- `just build`; team detail page count still equals the team count.

## Related

- `partner_scrape/teams/` — the subsystem this extends; `DESIGN.md` is current.
- `partner_scrape/fetch/cache.py::PoliteFetcher` — the mandatory fetch path.
- `partner_scrape/enrich/{llm_client,cache}.py` — the JSON-schema + content-hash patterns to follow.
- `partner_scrape/normalize/partners.py::normalize_org_name` — the sponsor match key.
- `site/src/components/{TeamCard,TeamFilters}.astro` — the surfacing work.
