# Do Not Scrape

A checked-in reference of sites this project has investigated for
automated access (as a hub or a source) and decided **not** to scrape,
plus sites whose status is still open. Its purpose, per issue 36, is
narrow: so a future session checks here first, instead of re-litigating
a ToS or robots.txt finding this project has already settled.

This file is documentation only. Nothing in the pipeline loads or
parses it — see `DESIGN.md`'s §2 four-catalog table for what *is*
loaded. The registry is opt-in-by-construction (a hub or source exists
only once someone writes a TOML file for it), so this list's job is
informing a human before they write one, not gating one already
written.

Two provenance groups make up the exclusions below, kept distinguishable
per entry, plus a separate Deferred section for sites that are neither
excluded nor registered:

- **Per issue 36** — the original 10-entry do-not-scrape list from
  issue 36's 2026-08-30 research, reasons quoted verbatim from the
  issue.
- **Found during sprint 024 planning, 2026-08-31** — four additional
  candidates issue 36 named as pre-cleared or clearance-pending, which
  this sprint's own live re-verification of each site's ToS page found
  to be unambiguously ToS-blocked.

## Excluded — per issue 36

### Eventbrite
- **What**: general-purpose event listing/ticketing platform
  (eventbrite.com).
- **Reason**: "ToS §13 forbids scraping; API token-only, search
  endpoint removed."
- **Source**: issue 36, 2026-08-30 research.

### Idealist / VolunteerMatch
- **What**: volunteer-opportunity listing sites; VolunteerMatch now
  redirects to Idealist.
- **Reason**: "ToS forbids bots/scrapers."
- **Source**: issue 36, 2026-08-30 research.

### ActivityHero
- **What**: camp/class booking and discovery platform.
- **Reason**: "ToS forbids scraping."
- **Source**: issue 36, 2026-08-30 research.

### Tinybeans
- **What**: family-events listing site.
- **Reason**: "robots disallows /events/."
- **Source**: issue 36, 2026-08-30 research.

### SDCOE OMS (k12oms.org)
- **What**: San Diego County Office of Education's online meeting/event
  system.
- **Reason**: "robots Disallow: /."
- **Source**: issue 36, 2026-08-30 research.

### Patch
- **What**: hyperlocal community news and events site.
- **Reason**: "robots blocks anthropic-ai/CCBot AI agents."
- **Source**: issue 36, 2026-08-30 research.

### SanDiego.org, CONNECT, StartupSD
- **What**: regional tourism/business-community event listing sites.
- **Reason**: "bot walls (Cloudflare/captcha)."
- **Source**: issue 36, 2026-08-30 research.

### ActiveNet apm REST
- **What**: ActiveNet's `apm` REST endpoint (municipal recreation
  program listings).
- **Reason**: "WAF-rejected (the campscui camps UI in issue 29 is a
  different, permitted surface)."
- **Source**: issue 36, 2026-08-30 research.

### JustServe / HandsOn San Diego / Points of Light
- **What**: volunteer-opportunity listing network.
- **Reason**: "JS-only, no API (revisit only if they publish one)."
- **Source**: issue 36, 2026-08-30 research.

### Meetup per-group iCal
- **What**: per-group iCal feeds published by individual Meetup groups.
- **Reason**: "robots-clean but ToS-unverified — hold until terms are
  read; adult-tech yield anyway."
- **Source**: issue 36, 2026-08-30 research.

## Excluded — found during sprint 024 planning, 2026-08-31

Issue 36 named these four as pre-cleared (KidsOutAndAbout) or
clearance-pending (the other three); this sprint's own live read of
each site's ToS page on 2026-08-31 found each one unambiguous and
excluded all four rather than applying a permissive reading issue 36's
own do-not-scrape list does not extend to Eventbrite/ActivityHero's
equivalently-worded clauses. See `sprint.md`'s Architecture > Design
Rationale (first decision) and Open Question 2 for the full reasoning
and the option this sprint deliberately did not take.

### KidsOutAndAbout San Diego
- **What**: STEM-camp-focused family events/camp directory
  (sandiego.kidsoutandabout.com); issue 36 called it "the best
  camp-provider discovery source."
- **Reason**: ToS prohibits "access[ing]... any of our Resources
  through any automated, unethical or unconventional means."
- **Live-verified**: 2026-08-31 (sprint 024 planning).

### sandiegostemsummercamps.com
- **What**: STEM summer camp directory ("251+ programs").
- **Reason**: ToS prohibits "scrape, harvest, copy, or republish Site
  content."
- **Live-verified**: 2026-08-31 (sprint 024 planning).

### sandiegomoms.com
- **What**: San Diego Moms camp directory.
- **Reason**: ToS prohibits "use any robot, spider or other automatic
  device... to access the Website for any purpose, including
  monitoring or copying any of the material."
- **Live-verified**: 2026-08-31 (sprint 024 planning).

### San Diego Reader
- **What**: alt-weekly events listing (68 JSON-LD Events/page, "For
  Kids" category).
- **Reason**: ToS states plainly "You may not scrape or otherwise copy
  our content without permission."
- **Live-verified**: 2026-08-31 (sprint 024 planning).

## Exceptions

Unlike the Excluded groups above, an entry here is not a site this
project avoids — it is a narrow, precisely-scoped stakeholder override
of the bright-line rule for a specific, already-identified shape of
site. It exists so a future session does not read the bright-line rule
as absolute and re-litigate a case that has already been decided, and
— just as importantly — does not read it as a general license to
override robots.txt elsewhere. An exception here covers only the exact
scope stated; any other robots.txt- or ToS-blocked candidate, including
one that superficially resembles this shape, still falls under the
bright-line rule and needs its own stakeholder decision.

### Named-allowlist robots.txt on ATS/job-board vendors — per issue 44, 2026-09-02

- **Scope**: applies only to a **named-allowlist robots.txt** (robots.txt
  disallows all bots except a short, explicit named list — e.g.
  Googlebot, bingbot, LinkedInBot) on an **ATS/job-board vendor**, for
  **low-volume, non-republishing, link-out-only** fetching of **public
  job postings**. This is not a general robots-override license — it
  does not extend to any other vendor shape, any higher-volume or
  republishing use, or any non-job-board site, even one blocked by an
  identically-worded named-allowlist robots.txt. A new candidate outside
  this exact scope needs its own stakeholder decision.
- **Sources covered**: `servicenow` (api.smartrecruiters.com, whose
  robots.txt allows LinkedInBot only), `city-of-san-diego-careers`,
  `county-of-san-diego-careers`, `sandag-careers`, and
  `port-of-san-diego-careers` (the latter four all hosted on
  www.governmentjobs.com, whose robots.txt allows only Googlebot,
  bingbot, yahoobot, msnbot, gsa-crawler-www, NHN, Twitterbot, and
  facebookexternalhit).
- **Reasoning**: the four public-sector agencies behind these boards
  (County of San Diego, City of San Diego, SANDAG, and the Port of San
  Diego) want their job postings found by job-seekers — the robots
  block is the ATS vendor's (SmartRecruiters' or governmentjobs.com's)
  own blanket crawler policy, not a choice made by the agency whose
  postings are being fetched.
- **Decision**: Eric, 2026-09-02, verbatim: "for number one, issue 44,
  go ahead and scrape them." Recorded per issue 44
  (`issues/44-robots-named-allowlist-policy-decision.md`, sprint 035).
  Implemented via the existing per-source
  `acquisition_policy.respect_robots = false` override (the same
  mechanism as the iCal `respect_robots = false` precedent from issue
  38/sprint 015) on each of the five sources' TOML files — the
  project's global `respect_robots` default is unchanged.
- **Does not reopen sprint-024's hub exclusions**: KidsOutAndAbout,
  sandiegostemsummercamps.com, sandiegomoms.com, and San Diego Reader
  (see "Excluded — found during sprint 024 planning" above) remain
  excluded. Those were blocked by an actual ToS clause forbidding
  scraping — a different and unrelated grounds from a robots.txt
  named-allowlist — and this decision does not touch them.

## Deferred

Not excluded, not registered — open questions this sprint surfaced but
did not resolve. Distinct from the Excluded groups above: nothing here
is barred by a live ToS or robots.txt finding. Each is blocked by a
different, unresolved problem. See `sprint.md`'s Architecture > Design
Rationale (second decision) and Open Questions 1 and 3.

### KPBS community calendar
- **What**: KPBS's arts/culture events calendar, at `kpbs.org/arts`
  and `kpbs.org/events/all`. Issue 36 named this hub as
  "KPBS/TheFinestSD community calendar" ("per-event .ics; free public
  submissions"); `thefinestsd.com`, the domain issue 36 names, **does
  not resolve** — connection timeout confirmed from two independent
  network paths on 2026-08-31 — and is not a live site to link to.
  "The Finest" turned out to be a KPBS-branded calendar living at the
  two `kpbs.org` URLs above, not a standalone site.
- **Reason deferred**: both `kpbs.org` pages are legal and
  robots-clean — robots.txt only disallows `/venue/*` and `/place/*`,
  neither of which matches `/arts` or `/events/`, and the ToS page
  carries no scraping/bot restriction. But `discovery/hub_scan.py`
  scans a single hop only: it extracts outbound links from exactly the
  page(s) in `page_urls`, with no recursive crawl. Both KPBS listing
  pages' direct outbound links are entirely KPBS's own cross-properties
  (`donate.kpbs.org`, `kpbslegacy.org`, `plus.kpbs.org`, `pbskids.org`)
  and social platforms — zero organization-hosting-site domains. The
  organization actually presenting an event (confirmed by sampling one
  individual event detail page, which links out to
  `spreckelsorgan.org`) sits one hop deeper than any `page_urls` entry
  can reach. This is a mechanism gap, not a legal or robots one —
  registering the listing page today would only ever queue the same
  ~10 KPBS-owned/social-platform domains as candidates, permanently.
  Resolving it needs a bounded second hop in `discovery/hub_scan.py`
  (Open Question 1), out of scope for this registration-only sprint.
- **Live-verified**: 2026-08-31 (sprint 024 planning).

### Macaroni Kid
- **What**: Macaroni Kid local family-events editions (chulavista,
  carlsbad, escondido, oceanside, sanmarcos) — HTML only, already
  flagged "optional/low-yield" in issue 36.
- **Reason deferred**: ToS could not be verified this sprint. Its
  `/terms-conditions` route returned inconsistent 404/302 responses
  under a direct (non-JS) fetch, so no ToS text was ever successfully
  read. Not excluded on that basis — an unverifiable ToS is not the
  same finding as a verified prohibition — and not registered either,
  since the registration convention (sprints 014-016) requires ToS to
  be checked live before enabling. See Open Question 3.
- **Attempted**: 2026-08-31 (sprint 024 planning); unresolved.
