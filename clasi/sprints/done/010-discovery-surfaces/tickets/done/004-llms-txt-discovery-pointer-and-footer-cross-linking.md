---
id: '004'
title: llms.txt discovery pointer and footer cross-linking
status: done
use-cases:
- SUC-001
depends-on:
- '001'
- '002'
- '003'
github-issue: ''
issue:
- 16-llms-txt-and-agent-discovery-pages.md
- 17-partner-event-publishing-strategy.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# llms.txt discovery pointer and footer cross-linking

## Description

Create `site/public/llms.txt` (the well-known discovery pointer, Design
Rationale D1/D6), linking to all three pages from tickets 001-003 plus
sprint 009's data files, and add a new footer link group in
`site/src/components/Footer.astro` pointing to all three pages (Design
Rationale D5). This is the sprint's final ticket — it needs every other
page's URL finalized first. Implements SUC-001 and the cross-linking/
wiring half of issues 16 and 17's connection.

## Acceptance Criteria

- [x] `site/public/llms.txt` exists, served at `/llms.txt` under both
      `just dev` and `just build`.
- [x] Follows the llms.txt convention: `# Title`, `>` one-paragraph
      summary, `##`-sectioned markdown link lists (Data / Documentation
      / Publishing).
- [x] AMENDED (was: absolute `https://www.sdstemecosystem.org/...`
      URLs per Design Rationale D6). Every link in `llms.txt` is an
      absolute `https://league-infrastructure.github.io/partner-scrape/...`
      URL instead — never base-relative, since `public/` files are
      copied byte-for-byte and are not templated. Reason: ticket 002
      already verified live (and flagged for this ticket to reconcile)
      that `www.sdstemecosystem.org` serves only a 417-byte HTML4
      `<frameset>` framing the github.io origin, and 404s on
      `/data/partners.json` — a plain HTTP client (an agent, not a
      frame-rendering browser) never reaches real content there. Using
      that domain in `llms.txt` would print URLs that never resolve.
      `for-agents.astro`'s own `DATA_ORIGIN` already made this switch;
      `llms.txt` is now consistent with it. Re-verified live by this
      ticket with `curl` (see completion report) — see also Design
      Rationale D6 correction note below.
- [x] Links present: `partners.json`, the documented
      `events.json`/`past-events.json` URL pattern, `/data-access`,
      `/for-agents`, `/publish-events`.
- [x] `llms.txt` is not mirrored under `/.well-known/` (Design
      Rationale D1). Verified: `curl -I http://localhost:4322/.well-known/llms.txt`
      -> 404 under `just dev`; no `.well-known` path exists in
      `site/dist/` after `just build`.
- [x] `Footer.astro` gains a new link group (e.g. "For Developers &
      Partners") linking to `/data-access`, `/for-agents`,
      `/publish-events`, added as a 5th grid column alongside the
      existing four, with the existing mobile single-column breakpoint
      extended to cover it.
- [x] `Header.astro`'s primary `navItems` are unchanged (Design
      Rationale D5).
- [x] `llms.txt` itself is not linked from the footer, matching how
      `robots.txt`/`sitemap.xml` are conventionally not linked from
      human nav.

## Amendment note (D6 correction)

Sprint 010's Design Rationale D6 assumed `www.sdstemecosystem.org` is
the canonical origin for `llms.txt`'s absolute URLs. It is not, verified
live: `https://www.sdstemecosystem.org/` returns 200 but the body is a
417-byte HTML4 `<frameset>` whose single frame points at
`https://league-infrastructure.github.io/partner-scrape/`; a plain HTTP
client never reaches real content, and
`https://www.sdstemecosystem.org/data/partners.json` 404s outright.
`https://league-infrastructure.github.io/partner-scrape/` (this repo's
own GitHub Pages deployment, per `.github/workflows/pages.yml`) returns
200 and is what the frameset itself resolves to. `llms.txt` therefore
uses the github.io origin, matching `for-agents.astro`'s `DATA_ORIGIN`
(ticket 002). A discovery file full of dead links is worse than no
discovery file, so reality overrides the stale D6 assumption here.

Separately: none of the five absolute URLs in `llms.txt` currently
return 200 in production. This is expected and matches this sprint's
own Migration Concerns precedent for the data files, extended here to
cover the three new pages and `llms.txt` itself: `sprint/010-discovery-surfaces`
has not yet been merged to `master`, and GitHub Pages only redeploys on
push to `master` (`.github/workflows/pages.yml`), so
`/data-access/`, `/for-agents/`, `/publish-events/`, and `/llms.txt`
all currently 404 on the live github.io origin purely because this
branch hasn't shipped yet — not because the URLs are wrong. Confirmed
by local build: `just build` produces `site/dist/llms.txt` (root),
`site/dist/data-access/index.html`, `site/dist/for-agents/index.html`,
and `site/dist/publish-events/index.html`, matching every path named in
`llms.txt` exactly (including the directory-index / trailing-slash
form GitHub Pages serves without a redirect hop). `data/partners.json`
additionally depends on the scraper pipeline having published to
`public/data/` at least once against the serving checkout (already
flagged as a pre-launch operational check by this sprint's own
Migration Concerns section, not a coded gap). All four will resolve
once this sprint merges to `master` and the pipeline has run.

Base-path/root-path limitation (documented honestly, not papered over):
the llms.txt convention (llmstxt.org) expects the file at the true site
root, `<domain>/llms.txt`. This repo's Pages deployment is a *project*
site (`league-infrastructure.github.io/partner-scrape/`, not a *user*
site), so `site/public/llms.txt` — copied verbatim by Astro into
`dist/llms.txt` — is served at
`https://league-infrastructure.github.io/partner-scrape/llms.txt`, one
path segment below the actual domain root
(`https://league-infrastructure.github.io/llms.txt`, which this repo
does not and cannot control — that root belongs to the
`league-infrastructure` GitHub org account, not this repository). This
is a consequence of GitHub Pages project-site hosting (compounded by
the `www.sdstemecosystem.org` frameset not being a working alternative
root either, per the D6 correction above), not something fixable from
within this repository. An agent that already knows this site's
specific origin (e.g. from a link on the page it arrived from) still
finds `llms.txt` at the expected path relative to that origin; an agent
that guesses only the bare `league-infrastructure.github.io` domain
root will not.

## Implementation Plan

**Approach**: This ticket runs last precisely because it is the index
that needs every other artifact's final URL (see `sprint.md`'s Tickets
table). Write `llms.txt` by hand following the llmstxt.org format. For
the footer change, adjust `.footer-inner`'s `grid-template-columns`
from `2fr 1fr 1fr 1fr` to `2fr 1fr 1fr 1fr 1fr` (or equivalent) and
confirm the existing `@media (max-width: 767px)` rule still stacks all
five columns to one — do not introduce a second breakpoint rule.

**Files to create**:
- `site/public/llms.txt`

**Files to modify**:
- `site/src/components/Footer.astro`

## Testing

- **Existing tests to run**: `uv run pytest` (unaffected, run to
  confirm no accidental regression).
- **New tests to write**: none — no Python surface.
- **Verification command**: `just build` and `just dev`; manually
  follow every link in `llms.txt` and the new footer group; visually
  check the footer at both desktop width and the existing mobile
  breakpoint.
