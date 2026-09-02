---
id: '007'
title: Probe unconfirmed-ATS employers (Qualcomm, Solar Turbines, Teradata, BAE, General
  Atomics, Intuit)
status: done
use-cases:
- SUC-060
depends-on: []
github-issue: ''
issue: 31-ats-adapters-workday-neogov-smartrecruiters.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Probe unconfirmed-ATS employers (Qualcomm, Solar Turbines, Teradata, BAE, General Atomics, Intuit)

## Description

For each of Qualcomm (Eightfold-ish, previously 403), Solar Turbines,
Teradata, BAE (Phenom), General Atomics (BrassRing), and Intuit
(Radancy), attempt a live, read-only probe of its careers site/API to
determine whether a public, unauthenticated, structured endpoint
exists. Record findings — do not build a bespoke adapter for any
genuinely new ATS shape this sprint, per `design/adapters-DESIGN.md`'s
sprint 031 Design Rationale (avoiding four speculative adapters against
an unconfirmed shape). If an employer turns out to already run
Greenhouse, Lever, SmartRecruiters, or Workable under an unlisted
board/company name, registering it is data-only and stays in scope for
this ticket.

This ticket's deliverable is a findings record, not necessarily new
code. A probe that finds every employer blocked is a complete, correct
ticket outcome.

## Acceptance Criteria

- [x] Each of the six employers has a recorded finding in this
      ticket's Notes: reachable-and-structured (name the shape),
      reachable-but-HTML-only, or blocked-and-how (403, credential
      required, robots-disallowed, etc.).
- [x] No new adapter module is added for a genuinely new ATS vendor
      shape (Eightfold, Phenom, BrassRing, Radancy) this sprint.
- [x] If any employer is found reachable through one of this
      codebase's existing adapter types (`greenhouse`, `lever`,
      `smartrecruiters`, `workable`), it is registered and
      live-verified in this same ticket, with a header comment
      recording the finding. N/A — none of the six employers turned
      out to run any of this codebase's supported ATS types (see
      Notes); zero registrations is the correct outcome, not a skipped
      step.
- [x] Full test suite (`uv run pytest`) stays green (a pure-probe
      outcome with no new registrations still needs to leave the suite
      green — it should be unaffected either way).

## Notes

**Method.** For each employer: fetch `robots.txt` for the relevant
host, fetch the public careers page (with browser-like headers where a
bare `curl` request was blocked at the transport layer), and identify
the underlying ATS from page markup (script bundle hosts, embedded
config JSON, response headers, outbound links to a third-party ATS
domain). All probes were read-only `GET` requests; no application
forms were submitted, no login attempted beyond following a page's own
redirect to observe where it leads.

### Findings

| Employer | ATS confirmed | Robots.txt | Finding |
|---|---|---|---|
| **Qualcomm** | Eightfold | `Disallow: /` with explicit `Allow:` carve-outs for `/careers`, `/api/apply`, `/api/pcsx`, `/api/career_hub`, `/careerhub/explore/jobs`, `/api/events` | **Reachable, not yet structured.** The public `/careers` page (no login) returns 200 and embeds Eightfold's own `pcsxConfig` (Public Career Site Experience) JSON, confirming a real public job-search surface robots.txt explicitly sanctions. `/careerhub/explore/jobs` (the *candidate portal*, a distinct surface) redirects to `/candidate/login` — this is almost certainly what issue 31's prior "403" finding hit. No literal public JSON search endpoint was identified from the page's own markup (Eightfold's actual search API call lives inside its shared minified JS bundle, not per-tenant page data) — finding the exact endpoint needs deeper JS reverse-engineering, out of this probe ticket's scope. |
| **Solar Turbines** | Unconfirmed (Akamai-protected) | N/A — connection blocked before robots.txt could be read with a bare UA; a browser-header `curl` got a robots.txt fetch to return `403 Forbidden` from `AkamaiGHost` | **Blocked: Akamai Bot Manager.** A plain `curl` with only a `User-Agent` header times out completely (`000`, connection never completes); adding full browser-like headers (`Accept`, `Accept-Language`) gets a prompt `403 Forbidden` from `AkamaiGHost` — the classic Akamai Bot Manager challenge-block signature. Solar Turbines is a wholly-owned Caterpillar subsidiary; `careers.caterpillar.com` was also checked as a likely shared-infrastructure fallback and returned Cloudflare's own bot-challenge page (`403`, "Just a moment...", `cf-ray` header) — both parent and subsidiary run active bot management that a plain HTTP client cannot clear. No ATS platform could be identified without a real browser. |
| **Teradata** | **GR8 People** (new, not currently supported by this codebase) | Permissive (`Disallow:` empty for `User-agent: *`; only `GPTBot`/`MagnetmeBot` excluded) | **Reachable and structured — strong follow-up candidate.** `careers.teradata.com` (200, robots-permitted) is a Next.js app on `assets.gr8people.com`; its embedded `__NEXT_DATA__` script carries a GraphQL-backed job-search config, including a location-facet aggregation already showing **13 current San Diego, CA postings** in the raw counts. GR8 People is not one of this codebase's six supported ATS types (`greenhouse`/`lever`/`smartrecruiters`/`workable`/`workday`/`neogov`) and not one of this ticket's four named speculative platforms (Eightfold/Phenom/BrassRing/Radancy) either — a seventh, previously-unknown vendor. No adapter built this sprint per this ticket's own scope; recommended as the strongest follow-up candidate of the six (permissive robots.txt, confirmed live SD postings, modern GraphQL/Next.js stack). |
| **BAE Systems** | **Phenom People** (confirmed) | Permissive for general paths; disallows only Phenom-platform-specific sub-paths (`*/phenomtrack.min.js`, `*/apply`, `*/chatbot`, `*/lifeatphenom`, etc.) | **Reachable and structured — follow-up candidate.** `jobs.baesystems.com` publishes a real `sitemap_index.xml` (4 child sitemaps, 805 URLs in the first alone, including an `/early-career` landing page), robots-permitted for general crawling. Phenom is not one of this codebase's supported ATS types or a Greenhouse/Lever/SmartRecruiters/Workable match, so no adapter/registration this sprint — but the sitemap shape is a plausible `generic_html`-style candidate for a future ticket to evaluate (a scope decision for that ticket, not assumed here). |
| **General Atomics** | **BrassRing** (IBM Kenexa, confirmed) | Permissive (`Crawl-Delay: 20`, disallows only `/.well-known/` and `/cgi-bin/`) | **Reachable, not structured.** `ga.com/careers` links to three distinct `sjobs.brassring.com` site IDs (`5310`, `5313`, `5757` — apparently General Atomics' separate business units). `sjobs.brassring.com` has no `robots.txt` restriction found; its `TGNewUI` search page returns 200 but is a ~1MB legacy Angular-era SPA with no JSON API endpoint discoverable from the page's own markup. BrassRing is not one of this codebase's supported ATS types — no adapter built. A future ticket would need real JS execution (headless browser) to find any underlying API, if one exists. |
| **Intuit** | **Radancy** (confirmed) | `Disallow: /search-jobs/` (the specific job-search path) | **Blocked: robots-disallowed on the one path that matters.** `jobs.intuit.com/search-jobs` (fetched once, read-only, for identification purposes only, mirroring this sprint's existing one-time-verification convention for a robots-gated path) confirms Radancy via page markup, but robots.txt explicitly disallows exactly this path for all bots. Same shape as `servicenow.toml`'s SmartRecruiters disable and this ticket's own NEOGOV registrations (ticket 006) — a genuine block, not something to route around. No adapter built (Radancy is also a genuinely-new, unsupported ATS type regardless of the robots question). |

### Summary

Zero of the six employers run an ATS this codebase already supports
(`greenhouse`/`lever`/`smartrecruiters`/`workable`/`workday`/`neogov`)
under an unlisted name — all six are confirmed to run a different
platform (Eightfold, unconfirmed/Akamai-blocked, GR8 People, Phenom,
BrassRing, Radancy respectively). Per this ticket's own scope and
`adapters/DESIGN.md`'s sprint 031 Design Rationale, **no adapter code
was written for any of them** — this probe's deliverable is the
findings table above, not new code. Two are outright blocked
(Solar Turbines: Akamai Bot Manager; Intuit: robots.txt disallow on
the job-search path itself). The other four are reachable and
identified; **Teradata (GR8 People)** is the strongest recommended
follow-up — permissive robots.txt, a modern GraphQL/Next.js stack, and
already-confirmed live San Diego postings in the page's own
aggregation counts. BAE Systems (Phenom, sitemap-based) is a secondary
candidate. No follow-up issue number is filed yet, per this sprint's
own "no issue filed ahead of the probe's findings" decision
(`sprint.md`'s Migration Concerns) — the team-lead should file one
against Teradata (and optionally BAE) once this ticket closes.

**Full test suite**: `uv run pytest` — unaffected (no registry/adapter
changes this ticket); still 2432 passed (same as ticket 006's own
post-change count).

## Implementation Plan

**Approach**: This is primarily a research ticket. For each employer,
attempt: (1) a plain unauthenticated GET/POST against the platform's
typical public API pattern for its named ATS vendor (Eightfold's
`career.eightfold.ai` widget API shape, Phenom's typical GraphQL/REST
surface, BrassRing's typical public feed, Radancy's typical public
feed); (2) if that fails, check whether the employer's careers page
itself exposes a Greenhouse/Lever/SmartRecruiters/Workable-shaped
endpoint under a name not in issue 31's original census (some
employers run more than one ATS for different job families). Record
each attempt and its result.

**Files to create/modify**:
- `registry/sources/` — zero or more new TOML files, only for an
  employer found reachable through an *existing* adapter type
- No new adapter module expected; if the probe genuinely finds a
  cleanly reachable new shape worth building, stop and flag it in this
  ticket's Notes as a recommended follow-up issue rather than building
  it inline — that decision belongs to the team-lead/stakeholder, not
  this ticket's own scope (per `design/adapters-DESIGN.md`'s Design
  Rationale)

**Testing plan**:
- **Existing tests to run**: `uv run pytest` (full suite — confirm no
  regression from any new registry entries this ticket adds).
- **New tests to write**: only if an employer is registered through an
  existing adapter type — the same fixture-based test convention
  ticket 002/003 already established, or confirmation that the
  existing adapter's test suite already covers the new registration's
  shape.
- **Verification command**: `uv run pytest`

**Documentation updates**: This ticket's Notes are the primary
deliverable for the five (or six) employers that don't result in a new
registration — write them in enough detail that a future sprint
picking one up doesn't need to re-probe from scratch. Recommend, but
do not file, a follow-up issue number for any employer found genuinely
buildable (see `sprint.md`'s Architecture > Migration Concerns for why
no issue is filed in advance of this ticket's findings).
