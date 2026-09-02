---
id: '006'
title: Verify issue 14's existing dated volunteer-event source registrations
status: done
use-cases:
- SUC-053
depends-on: []
github-issue: ''
issue: 14-improve-volunteer-opportunity-discovery.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Verify issue 14's existing dated volunteer-event source registrations

## Description

Independent of every other ticket in this sprint. Issue 14's own
2026-08-30 research update concluded that Strategy A (scraping
third-party volunteer-aggregator platforms) is dead, and that the
volunteer content which *is* scrapable already flows through the
normal pipeline once registered: UCSD Localist's Volunteer event type,
Coastkeeper TEC, Surfrider SD Google Calendar, and ILACSD. This ticket
**verifies these four sources' current registration state — it does
not register anything new.**

For each of the four: confirm it is registered, confirm its
`adapter_type` (`localist`/`tec_rest`/`ical`/`generic_html`, whichever
applies) and `enabled` state, and confirm it is actually yielding
`Volunteering`-typed records (`normalize/taxonomy.py` already supports
this `opportunity_type` value — this ticket does not touch taxonomy).
Where a source is found disabled, misconfigured, or zero-yield for a
reason fixable with a config edit, fix it. Where the gap needs more
than a config edit (a genuine adapter bug, a site change), document it
with a dated comment and leave it — this ticket's scope is
verification and config fixes, not new adapter development.

## Acceptance Criteria

- [x] UCSD Localist's Volunteer event type: confirmed registered,
      `enabled` state recorded, live-verified (or documented if not
      feasible) to yield `Volunteering`-typed records.
- [x] Coastkeeper TEC: same verification.
- [x] Surfrider SD Google Calendar: same verification.
- [x] ILACSD: same verification.
- [x] Any config-level fix applied (e.g. an `enabled = false` flipped
      to `true`, a stale URL corrected) is recorded with a dated
      comment in that source's own TOML, matching this codebase's
      existing self-documenting-registry convention.
- [x] No new source is registered by this ticket.
- [x] This ticket's own Notes section records the final state of all
      four sources (enabled/disabled, yield), so the sprint's Success
      Criteria can be checked off without re-deriving it.

## Testing

- **Existing tests to run**: `uv run pytest tests/registry/
  tests/adapters/` (confirm no regression from any config edit).
- **New tests to write**: none expected unless a config fix reveals an
  actual adapter bug worth a regression test — judgment call at
  execution time, not planned here.
- **Verification command**: `uv run pytest`; live yield verification
  (`uv run partner-scrape --source <source-id> --dry-run -v`,
  `dangerouslyDisableSandbox: true`) is a manual step, not a pytest
  test.

## Notes

Real, live verification (2026-09-02, real network, real
`AnthropicProgramLLMClient` where applicable — same standard as ticket
005) of all four sources named in issue 14's research update:

**1. UCSD Localist's Volunteer event type — NOT registered. A real
gap, not fixable with a config edit.** `calendar.ucsd.edu/api/2/events`
does support a `type=Volunteer` query filter live-confirmed today
(`curl 'https://calendar.ucsd.edu/api/2/events?type=Volunteer&days=180&pp=5'`
returns real records, including "Weed Warriors" — issue 14's own named
example, exactly). But no existing registration covers it: the five
UCSD Localist sources actually registered (`birch-aquarium`,
`ucsd-extended-studies-localist`, `ucsd-qualcomm-institute`,
`ucsd-jacobs-school`, `ucsd-physics`) all filter by `group_id` (a
department), and `LocalistAdapter.discover()`
(`partner_scrape/adapters/localist.py`) hard-requires
`config["group_id"]` with **no support for a `type` filter at all** —
there is no config key a TOML edit could set to reach this feed.
Registering it would need real adapter code (reading an optional
`config["type"]` and building the query URL without `group_id`, or
some equivalent), which is new adapter development, explicitly out of
this verification-only ticket's scope. Documented here (and pinned by
`tests/test_registry.py::TestVolunteerEventSourceVerification::
test_ucsd_localist_volunteer_type_is_not_registered`) as a real,
concrete gap for a future ticket, not silently dropped.

**2. Coastkeeper TEC — registered, enabled, live-yielding
`Volunteering`-typed records.** `registry/sources/sdcoastkeeper.toml`,
`adapter_type = "tec_rest"`, `enabled = true` (unchanged — no fix
needed). `uv run partner-scrape --source sdcoastkeeper --dry-run -v`:
`found=20 dated=20 new=0`, `wrote 9` in this run. Direct `extract()` +
`normalize.taxonomy.classify_opportunity_type()` inspection: 4 of 20
titles classify `Volunteering` (e.g. "California Coastal Cleanup Day –
Otay Valley Regional Park", "Community Science Plastic Pellet (Nurdle)
Cleanup 9/19/26") — matching issue 14's own named examples (cleanups,
water-quality monitoring) directly.

**3. Surfrider SD Google Calendar — registered, enabled,
live-yielding `Volunteering`-typed records at high volume.**
`registry/sources/surfrider-sd.toml`, `adapter_type = "ical"`,
`enabled = true` (unchanged — no fix needed). `uv run partner-scrape
--source surfrider-sd --dry-run -v`: `found=2188 dated=2188 new=15`,
`wrote 9` in this run — reproducing sprint 015's original 2188 count
exactly, confirming the feed and the known pre-existing
timezone-aware-`RRULE UNTIL` per-VEVENT skip are both unchanged. Direct
`extract()` + `classify_opportunity_type()` inspection across the full
feed: 583 of 2188 titles classify `Volunteering` (beach cleanups,
habitat restoration — e.g. "Beach Cleanup – Mission Beach – Belmont
Park (Coastkeeper hosts)", "TRAM Habitat Restoration on Monument
Mesa") — by far this pass's highest-volume confirmed yield.

**4. ILACSD — registered, disabled, still genuinely blocked; the
blocking mechanism has changed since 2026-08-30, so the TOML's own
comment is updated to report the current finding rather than leave the
stale one standing.** `registry/sources/ilacsd.toml`, `adapter_type =
"tec_rest"`, `enabled = false` (unchanged). The 2026-08-30 finding
(SiteGround `sg-captcha` CAPTCHA challenge) no longer reproduces:
`www.ilacsd.org`'s TEC REST endpoint now `HTTP 301`-redirects to
`cleansd.org`'s own endpoint (the bare `ilacsd.org` domain redirects
the same way — the two historically-split domains have consolidated
onto one), and following that redirect lands on `cleansd.toml`'s
already-documented Cloudflare bot-management block (`HTTP 403`,
`cf-ray`/`__cf_bm` headers) — re-confirmed live via `curl -L` today.
This independently corroborates ticket 002's same-day finding
(`www.ilacsd.org`/`cleansd.org` returning `HTTP 403` to both `curl` and
`WebFetch` while researching the volunteer-org-profile entry for this
same organization). End state is unchanged (still correctly disabled,
still not headless-fixable — a JSON API response, not an HTML page,
per `cleansd.toml`'s own reasoning), but the *current* failure mode is
a Cloudflare 403 via redirect to `cleansd.org`, not a SiteGround CAPTCHA
on `ilacsd.org` directly. `ilacsd.toml`'s header comment and disable
reason are updated accordingly, dated 2026-09-02, per this ticket's own
"report what you actually find" mandate.

**Summary for the sprint's Success Criteria**: 2 of 4 sources (Coastkeeper,
Surfrider) are confirmed enabled and actively yielding real
`Volunteering`-typed records today. ILACSD is confirmed still
genuinely blocked (mechanism re-verified, not merely re-stated). UCSD
Localist's Volunteer event type is confirmed to have no existing
registration and cannot be reached via a config-only fix under the
current adapter — a real, documented gap for a future ticket, not a
silent omission. No new source was registered; the only registry edit
this ticket makes is `ilacsd.toml`'s comment/reason-string update
(`enabled` state, `adapter_type`, and `config` all unchanged).

New test class `TestVolunteerEventSourceVerification` in
`tests/test_registry.py` pins all four findings (Coastkeeper/Surfrider
enabled+correct adapter_type, ILACSD disabled with the re-verified
reason text present, and the UCSD Localist gap — exactly 5 UCSD
Localist sources registered today, all `group_id`-filtered, none with a
`type` key). Full suite: 2316 passed (baseline 2306 + 6 ticket-005
tests + 4 ticket-006 tests).
