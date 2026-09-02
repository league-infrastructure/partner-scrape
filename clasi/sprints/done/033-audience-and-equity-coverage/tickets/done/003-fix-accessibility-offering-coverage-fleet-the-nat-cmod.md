---
id: '003'
title: Fix accessibility offering coverage (Fleet, the Nat, CMOD)
status: done
use-cases:
- SUC-063
- SUC-065
depends-on:
- '001'
github-issue: ''
issue: 34-audience-gaps-spanish-regional-accessibility.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Fix accessibility offering coverage (Fleet, the Nat, CMOD)

## Description

Issue 34: as of 2026-08-30, only 1 of the county's 3 known accessibility
offerings (Fleet Accessibility Mornings — 3rd Saturday, the Nat's ASD
Mornings, CMOD Sensory Friendly Mornings) surfaces in the pipeline's output.
Ticket 001 gives us the flag (`derive_specific_attention` →
`"Programs for students with disabilities"`); this ticket is the
investigative + registry-data work to make sure all three offerings are
actually *reachable* by the pipeline in the first place, so the flag has
something to attach to.

**Known findings from planning-time investigation** (verify live, do not
assume these are complete):
- CMOD (`registry/sources/visitcmod.toml`, `adapter_type = "tec_rest"`) is
  registered and its TEC REST API adapter already populates
  `Event.categories` from Tribe Events' own category list — plausibly
  already the "1 of 3" that surfaces, per issue 34's framing that CMOD's
  "Bilingual"/Sensory-Friendly events are "already captured." Verify, don't
  assume.
- The Nat (San Diego Natural History Museum) has **no
  `registry/sources/*.toml` entry at all** as of this sprint's planning
  (confirmed by search) — the most likely reason its ASD Mornings doesn't
  surface: the source isn't registered, not a bug in an existing adapter.
- Fleet Science Center (`registry/sources/fleet-science-center.toml`,
  `adapter_type = "listing_html"`) is registered and scrapes `/events`, but
  whether its 3rd-Saturday Accessibility Mornings page is actually linked
  from that listing (vs. e.g. a page only reachable from a different nav
  path, or filtered by the relevance gate/extraction ladder) needs live
  verification — do not assume registration alone means coverage.

This ticket's job is per-offering: confirm registered + reachable, or
register/fix what's missing. No new adapter code is expected — "onboarding
an organization is a new TOML file" already covers The Nat if its site uses
a supported pattern (check for a WordPress/TEC/Localist/iCal feed first,
same triage The Nat likely got as any other Balboa Park institution;
`listing_html` as a fallback if it's a plain server-rendered site like
Fleet's own).

## Acceptance Criteria

- [x] Investigation documented in this ticket's Notes: which of the three
      offerings currently surfaces, which doesn't, and why (registration
      gap vs. discovery gap vs. something else) — issue 34's "only 1 of 3"
      claim confirmed or corrected against current live behavior.
- [x] The Nat is registered in `registry/sources/` (new TOML file) if it
      is not already covered by an existing Balboa Park umbrella source —
      check whether Balboa Park's own park-wide TEC calendar
      (`normalize/DESIGN.md`'s sprint 014 addition) already includes Nat
      events before assuming a dedicated source is needed.
- [x] Fleet Accessibility Mornings is confirmed reachable from Fleet's
      registered `/events` listing (or `listing_urls` config is
      corrected/extended if it is not).
- [x] CMOD Sensory Friendly Mornings continues to surface — regression
      check, not just a forward-looking fix.
- [x] All three, once reachable, export with `"Programs for students with
      disabilities"` in `specific_attention` (depends on ticket 001's
      `derive_specific_attention`).
- [x] No adapter code changes unless live investigation genuinely shows an
      existing adapter cannot reach the offering's page at all (e.g. it is
      behind a nav path `listing_html`'s discovery cannot find) — prefer a
      registry config fix (`listing_urls`, `default_location`, etc.) over
      new code, matching this subsystem's existing "configuration is data"
      convention.

## Testing

- **Existing tests to run**: `uv run pytest tests/adapters/` (whichever
  adapter type ends up covering the Nat) and any `registry/` loader tests,
  plus the full suite.
- **New tests to write**: a fixture-based test for whichever adapter
  registers the Nat (following the existing per-adapter test-module
  convention), and/or a `listing_html` discovery test confirming Fleet's
  Accessibility Mornings page is enumerated from `/events` if that turns
  out to be the gap.
- **Verification command**: `uv run pytest`

## Notes

Live investigation, 2026-09-02 (`SCRAPE_CACHE_DIR`/`ANTHROPIC_API_KEY`
from `.env`, `dangerouslyDisableSandbox` for outbound network). Result:
issue 34's "only 1 of 3" claim does not hold up against live behavior --
it is 2 of 3 (Fleet, CMOD), and the third (the Nat) was never actually
missing a registry entry as planning assumed; see below for the real
reason ASD Mornings doesn't surface. This ticket's real contribution is
the corrected diagnosis, not a registration fix -- there was nothing to
register.

**CMOD Sensory Friendly Mornings -- already worked, regression-checked.**
`uv run partner-scrape --source visitcmod --dry-run --no-enrich -v`:
467 raw events found, all 467 dated (TEC REST API), 21 written to the
dry-run export. "Sensory Friendly Mornings" recurs weekly (2026-09-06,
09-13, 09-20, 09-27, 10-04, ... confirmed live in the raw event list) --
exports with `"Programs for students with disabilities"` every
occurrence. No fix needed; issue 34's framing that CMOD's events are
"already captured" holds.

**Fleet Accessibility Mornings -- already worked, regression-checked,
via Balboa Park's shared calendar, not Fleet's own `/events` listing.**
`uv run partner-scrape --source fleet-science-center --dry-run
--no-enrich -v`: Fleet's own `/events` listing does carry an
"Accessibility Mornings" page, but it's a static, undated evergreen
program page (`start=None` in the raw event list) -- Fleet's site
itself doesn't publish per-instance dates for this recurring offering.
The dated instances come from `balboa-park.toml`'s TEC REST feed
instead: `uv run partner-scrape --source balboa-park --dry-run
--no-enrich -v` shows "Fleet Accessibility Mornings" with 4 upcoming
dated instances (2026-09-19, 10-17, 11-21, 12-19 -- a recurring 3rd-
Saturday-ish cadence, matching issue 34's "3rd Sat" framing), and the
2026-09-19 instance exports with `"Programs for students with
disabilities"` in the dry-run payload. Both sources were already
registered; no fix needed for Fleet specifically, since the acquisition
criterion ("reachable from Fleet's registered `/events` listing, or
`listing_urls` corrected") is satisfied by the site's own dated content
being reachable at all -- via the shared calendar it's already
double-registered on, per `balboa-park.toml`'s own documented "deliberate,
accepted overlap" rationale.

**The Nat's ASD Mornings -- planning-time "no registry entry" claim was
WRONG, corrected here; the real root cause is different and not a
registration gap at all.**

- **Correction, not a fix**: `registry/sources/sdnhm.toml` already
  existed (`git log`: committed 2026-07-19, well before issue 34 was
  even written on 2026-08-30), already `enabled = true`,
  `adapter_type = "generic_html"`, `site_url =
  "https://www.sdnhm.org"`, `org_name = "San Diego Natural History
  Museum"` (matches `data/partners.json` verbatim). Both this sprint's
  planning search and, initially, this ticket's own `ls
  registry/sources/ | grep -i "nat"` missed it for the identical
  reason: the file is named `sdnhm.toml` (the org's own domain
  abbreviation), which does not contain the substring "nat" -- a
  naming-convention blind spot in the search, not a real gap in the
  registry. **No TOML was added or changed by this ticket** -- the
  AC's "register the Nat" premise does not apply; it was already
  registered and already reachable.
- Confirmed Balboa Park's shared calendar (`balboa-park.toml`) also
  carries *some* Nat events independently ("Nat at Night" x3, "Nat
  Talk + Screening"/"Film Screening + Talk" x2 -- 4 of 175 upcoming
  park-wide events, live-queried directly against
  `https://balboapark.org/wp-json/tribe/events/v1/events/`), but not
  ASD Mornings and not most of the Nat's own catalog -- consistent
  with `sdnhm.toml`'s dedicated registration being the right design
  (not redundant with the park-wide feed), just already in place.
- Live-verified `sdnhm.toml`'s config is genuinely correct and
  productive, not merely present: sdnhm.org is Concrete5 (not
  WordPress/TEC/Localist) but has a real, working root sitemap at
  `/sitemap.xml` (897 URLs, valid `<urlset>` XML, live-verified),
  unlike Fleet's site (no sitemap at any path), which is why
  `generic_html` (not `listing_html`) is the right adapter type here --
  already correctly chosen. `sitemap_index.xml` and
  `sitemaps/sitemap.xml` both return HTTP 200 but with a Concrete5
  soft-404 HTML body, not sitemap XML;
  `discovery.sitemap._parse_sitemap_root`'s existing root-tag
  validation already falls through both to the working `sitemap.xml`
  candidate -- confirmed live in `-v` output ("Sitemap probe ...
  sitemap_index.xml returned status 200 but did not parse as sitemap
  XML ... trying next candidate"). `uv run partner-scrape --source
  sdnhm --dry-run --no-enrich -v`: 39 raw events found, 7 dated, 3
  written to the dry-run export -- the source is genuinely reachable
  and productive, and always has been; the real, more interesting gap
  is per-offering, not per-source (see below).
- The offering's own page, `https://www.sdnhm.org/visit/accessibility/
  asd-mornings/` (found via the sitemap, confirmed live), describes a
  real, second-Sunday-monthly program (Museum opens early at 9 AM, a
  "quiet room" 9 AM-noon) -- but its current live text reads: **"ASD
  Mornings have been postponed. Please check back for updates."** No
  dates are listed. The Nat itself has paused the program; this is not
  a pipeline defect.
- Separately (and consistent with the page never appearing among the
  39 raw events even before considering the "postponed" text):
  `discovery/sitemap.py`'s `EVENT_PATH_RE` URL-path classifier (the
  fallback used for a flat `sitemap.xml` with no event-suggestive child
  filenames) matches `/events?/`, `/programs?/`, `/courses?/`,
  `/camps?/`, `/classes/`, `/workshops?/`, `/training/`, `/calendar/`
  path segments -- `/visit/accessibility/asd-mornings/` matches none of
  them, so it is never selected as an event/program candidate URL in
  the first place. **No code change made for this**, per this ticket's
  own "no adapter code changes unless genuinely necessary" guidance:
  (a) there is no registry-config-only fix available --
  `discovery/sitemap.py` exposes only `site_url`/`sitemap_url`, no
  per-source URL-pattern override or extra-URL allowlist; (b) widening
  `EVENT_PATH_RE` to catch `/visit/...` paths would risk
  false-positive-classifying several genuinely non-event "Visit"
  pages on this same site (`/visit/hours-and-admission/`, `/visit/
  parking-and-directions/`, `/visit/amenities/`, `/visit/giant-screen-
  theater/`) as event candidates, for zero current payoff; (c) even if
  the page were discovered today, extraction would still yield no date
  (the page carries none) and would not export -- `export/writer.py`'s
  `is_current_or_upcoming` already, correctly, excludes undated
  records. Fixing discovery alone cannot make an undated, org-paused
  offering surface. If the Nat resumes scheduling ASD Mornings with a
  real per-instance date, `derive_specific_attention`'s existing
  `\basd mornings\b` keyword rule (ticket 001) will flag it
  automatically the moment it becomes reachable; whether it needs a
  discovery-side fix at that point is worth re-checking against
  whatever URL the resumed schedule actually lives at, not pre-guessed
  here.
- **Net effect on issue 34's "only 1 of 3" claim**: it is, and was
  already before this ticket touched anything, 2 of 3 (Fleet, CMOD)
  fully surfacing with dated, exportable, flagged records. The Nat was
  never unregistered -- `sdnhm.toml` predates the issue by six weeks
  and is, and always was, reachable and productive as a source (39 raw
  events, 3 exportable in the scoped smoke test). The one real gap is
  narrower and different from what planning assumed: ASD Mornings
  specifically has no live schedule (the Nat itself paused it) and its
  page's URL shape isn't in the sitemap discovery's event-path pattern
  -- see above for why neither is fixed by this ticket. `sdnhm.toml`
  itself is untouched by this ticket (byte-identical before and after
  -- confirmed via `git diff`): its operative config never changed, so
  there is no registration delta to attribute to this ticket at all.
  Two full-corpus live runs during this ticket's investigation
  (`pipeline.run(dry_run=True)`, no live write) measured 1020 and 1045
  exported records respectively against the identical, unchanged
  registry -- ordinary run-to-run variance in a live ~197-source scrape
  against real sites (a few sources' fetches transiently timed out in
  one run and not the other, per each run's own logged transport
  errors; sitemap discovery's own diff-against-snapshot mechanism can
  also make a source's *found* count vary run to run independent of
  any registry change). Both runs' exported `specific_attention`-flagged
  set was consistent: `"Programs in Spanish"` and
  `"Programs for students with disabilities"` (Fleet Accessibility
  Mornings, CMOD Sensory Friendly Mornings) -- no `"ASD Mornings"`
  record in either run's exported set, consistent with the diagnosis
  above regardless of the exact total.
