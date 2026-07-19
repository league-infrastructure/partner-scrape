---
id: '005'
title: League ad-slot data contract (ads.json export)
status: done
use-cases:
- SUC-004
depends-on: []
github-issue: ''
issue: 12-league-content-and-advertising.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# League ad-slot data contract (ads.json export)

## Description

Deliver the League's sidebar ad placement as a data contract, per
sprint.md's Architecture > Design Rationale ("League's ad slot is
delivered as a data contract plus a documented site requirement, not as
a UI commit into `stem-ecosystem`"). `stem-ecosystem` is a separate git
repo, not under this CLASI process; its own
`docs/site-implementation-spec.md` confirms the site currently has no
ad-slot concept, no CMS, and is a fully static, JSON-data-driven Astro
build. This ticket does **not** touch `stem-ecosystem` — it only writes
into that repo's `src/data/` directory, the same boundary
`export/writer.py` already crosses for `opportunities.json`.

1. **`partner_scrape/registry/ads/league.toml`** — hand-authored ad
   content: `headline`, `body` (short pitch text), `link` (e.g.
   `https://www.jointheleague.org/`), and a `logo_src` reference (can
   reuse the League's existing partner logo filename from
   `stem-ecosystem`'s `partners.json` entry, id 287, so the ad and the
   partner listing stay visually consistent). This is standalone,
   hand-authored content — not scraped from jointheleague.org — since ad
   copy the League wants to run (e.g. a seasonal enrollment pitch) is a
   different concern from what's literally published on their site.
2. **`partner_scrape/export/ads.py`** — `export_ads(ad_configs, site_dir,
   *, dry_run=False) -> list[dict]`, structurally mirroring
   `export/writer.py`'s `export_opportunities()`: reads the ad config(s),
   writes `{site_dir}/src/data/ads.json` in a documented schema (a JSON
   array of `{headline, body, link, logo_src}` objects — extensible to
   multiple advertisers later without a schema break), fails loudly
   (`RuntimeError`) if `site_dir`'s `src/data` isn't writable, and
   supports `dry_run` the same way `export_opportunities` does.
3. Wire one new call into `pipeline.run()` (after the existing Site
   Export call) so `ads.json` stays fresh on every normal
   `partner-scrape` run, matching sprint.md's Impact on Existing
   Components note (Pipeline's fan-out reaching 5, justified as "the same
   kind of responsibility" as the existing Site Export call).
4. **Document the data contract** in this ticket's own record (see
   Acceptance Criteria) for a human to carry into a separate
   `stem-ecosystem` follow-up: `ads.json`'s exact schema, and a
   recommended integration note — e.g. render it as a card in whatever
   sidebar surface the site eventually adds (the opportunities/partners
   listing pages' existing filter sidebar is filter-only today; a
   dedicated ad slot is new site-side design work, not fixed here per
   sprint.md's Open Question 2).

## Data Contract (for a `stem-ecosystem` follow-up)

**File**: `{site_dir}/src/data/ads.json` (written next to `opportunities.json`
and `scrape-meta.json`; site repo's default `site_dir` is the sibling
`../stem-ecosystem` checkout, or `$SITE_DIR`).

**Shape**: a JSON array — one object per advertiser, extensible without a
schema break:

```json
[
  {
    "headline": "Give Your Kid a Head Start in Code",
    "body": "The LEAGUE of Amazing Programmers teaches real Java programming to San Diego County kids in grades 5-12 through after-school classes and camps -- building toward an industry-recognized certification, not just a coding intro. Enroll today at jointheleague.org.",
    "link": "https://www.jointheleague.org/",
    "logo_src": "the_league_of_amazing.png"
  }
]
```

- `headline` (string) — short, punchy ad title.
- `body` (string) — 1-2 sentence pitch/description.
- `link` (string) — absolute URL the ad should link to.
- `logo_src` (string) — logo image filename, using the same convention
  `Opportunity.logo_src`/`partners.json` already use (here, reusing
  partner id 287's own `the_league_of_amazing.png` so the ad and the
  partner listing stay visually consistent).

**Freshness**: written on every normal `partner-scrape` run (wired into
`pipeline.run()`, right after the existing Site Export call), so it never
goes stale relative to `opportunities.json`.

**Recommended site-side integration** (not implemented by this ticket —
`stem-ecosystem` is a separate, non-CLASI repo): render each array entry
as a card in the site's sidebar — `headline` as the card title, `body` as
its copy, `logo_src` resolved the same way `Opportunity.logo_src` already
resolves an image, the whole card wrapped in an anchor to `link`. The
opportunities/partners listing pages' existing sidebar is filter-only
today, so adding an ad slot there is new site-side UI work (placement,
static-vs-rotating, responsive behavior) — intentionally left open per
sprint.md's Open Question 2, since over-specifying it here would
constrain a decision the site repo's own review should make. A human can
open a `stem-ecosystem` issue/PR directly from this section.

## Acceptance Criteria

- [x] `registry/ads/league.toml` exists with `headline`, `body`, `link`,
      `logo_src`.
- [x] `export/ads.py`'s `export_ads()` writes `{site_dir}/src/data/
      ads.json` as a JSON array matching the documented schema.
- [x] An unwritable `site_dir` (or missing `src/data`) raises
      `RuntimeError` with a message naming the path — never a silent
      skip, matching `export_opportunities`'s existing contract.
- [x] `dry_run=True` returns the would-be payload without writing to
      disk.
- [x] `pipeline.run()` calls `export_ads()` once per run, after the
      existing `export_opportunities()` call; existing `run()` callers/
      tests that don't care about ads are unaffected (additive change).
- [x] The ticket's own text (this file) states the `ads.json` schema and
      a placement recommendation clearly enough that a human can open a
      `stem-ecosystem` issue/PR from it directly — **no file in
      `stem-ecosystem` is created or modified by this ticket**.

## Testing

- **Existing tests to run**: `tests/test_export.py`,
  `tests/test_pipeline_e2e.py`.
- **New tests to write**:
  - `tests/test_export_ads.py` — mirrors `tests/test_export.py`'s
    existing pattern: a `tmp_path` site dir, asserts `ads.json`'s written
    shape and content, asserts `RuntimeError` on an unwritable dir,
    asserts `dry_run` behavior.
  - An addition to `tests/test_pipeline_e2e.py` (or a new
    `test_pipeline_e2e_ads.py`) asserting a full `run()` call against a
    `tmp_path` site dir produces both `opportunities.json` and
    `ads.json`.
- **Verification command**: `uv run pytest`
