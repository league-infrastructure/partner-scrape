---
id: '004'
title: Register verified nonprofit/institutional camp marketing-page providers
status: open
use-cases:
- SUC-038
- SUC-041
depends-on:
- '003'
github-issue: ''
issue: 29-camp-session-extraction.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Register verified nonprofit/institutional camp marketing-page providers

## Description

Registers the verified institutional/nonprofit camp marketing-page
providers named in issue 29 as `program_page_multi` sources (sprint 027's
"one page, N inline records" adapter type), each with `config.program_kind
= "program"` and `config.opportunity_type = "Camps"` — the same
operator-curated-override convention `sd-foundation-community-
scholarship.toml` already established for `"Funding Opportunities"`. No
new adapter code; this is a pure "onboarding is a data edit" ticket,
following sprint 027 ticket 005's precedent for registering many
individual pages in one ticket.

**Providers to register** (live-verify each; register `enabled = false`
with a reason comment, per sprint 027 tickets 005/006's precedent, for any
that turn out blocked):
- San Diego Zoo per-program pages (`zoo.sandiegozoo.org/kids-programs/*`)
  — register each of the 9 program pages individually (the exact URL list
  is confirmed live during this ticket, not enumerated in advance);
  per-page live verification determines whether `program_page` (one
  continuous session) or `program_page_multi` (N weekly sessions) is the
  right `adapter_type` for each.
- Living Coast (`thelivingcoast.org/camps`)
- Coastal Roots Farm (`coastalrootsfarm.org/farm-camp`)
- Elementary Institute of Science (`eisca.org/camps`)
- SD Model Railroad Museum (`sdmrm.org/summer-camps`) — this page's
  documented sold-out flags make it the natural live-verification target
  for ticket 003's sold-out-via-description mapping.
- Camp Invention per-program pages (`invent.org/program-search/...`) —
  same per-page live-verification approach as SD Zoo.
- CMOD (`visitcmod.org/camps` + seasonal pages)
- Southwestern College Y.E.S. (XenDirect, server-rendered)
- Birch's newsroom page (dates/prices; the main site 403s per issue 23,
  out of scope here)
- Fleet's marketing page — register `enabled = true` year-round (ticket
  003's empty-list handling covers the off-season case; do **not** gate
  this behind a disabled flag pending "season").

**Explicitly excluded from this ticket** (do not register):
- **Camp Galileo SD** — the commercial "Galileo" studio brand named in the
  roadmap `sprint.md`'s commercial-chain exclusion list, despite appearing
  in issue 29's own marketing-page list. See `sprint.md`'s "Camp Galileo
  tension" note.
- **Air & Space Museum** and **Helen Woodward** — registered only via the
  `activenet_camps` adapter (ticket 005), never also as a
  `program_page_multi` marketing-page source, to avoid the
  dual-registration risk `adapters/DESIGN.md` documents (two adapters
  covering the same org, both bypassing cross-source dedup by design).

## Acceptance Criteria

- [ ] Every listed provider (excluding Camp Galileo SD, Air & Space
      Museum, and Helen Woodward) is registered as a `program_page`/
      `program_page_multi` source with `config.opportunity_type =
      "Camps"`, live-verified to yield at least one correctly-dated,
      correctly-priced session record — or registered `enabled = false`
      with a documented reason if blocked.
- [ ] `registry/sources/` contains no Camp Galileo SD entry.
- [ ] `registry/sources/` contains no marketing-page (`program_page`/
      `program_page_multi`) entry for Air & Space Museum or Helen
      Woodward.
- [ ] At least one registered source exercises the sold-out-via-
      `description` mapping from ticket 003 (SD Model Railroad Museum is
      the expected candidate).
- [ ] Fleet is registered `enabled = true`.
- [ ] A dry-run check confirms every newly-registered `enabled = true`
      source yields correctly-shaped `Camps` records before this ticket
      is marked done.

## Testing

- **Existing tests to run**: `uv run pytest` (full suite).
- **New tests to write**: one fixture-based test per registered provider
  (saved HTML fixture + `FixtureProgramLLMClient`), following the existing
  per-source test convention — at minimum, one exercising a multi-session
  page (N week-rows) and one exercising a sold-out row.
- **Verification command**: `uv run pytest`, plus live dry-run commands
  for each newly-registered source (not part of the hermetic suite).
