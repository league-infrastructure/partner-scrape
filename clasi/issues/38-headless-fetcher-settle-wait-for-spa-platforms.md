---
status: pending
---

# Headless fetcher needs a settle wait for SPA platforms

## Description

Sprint 028 ticket 005 built the `activenet_camps` adapter for
`campscui.active.com` and then could not enable either of its two
sources, because the shared headless fetcher does not wait long enough
for the page to render.

`partner_scrape/fetch/headless.py`'s `PlaywrightFetcher` uses
`wait_until="load"` with no settle wait. ActiveNet is a
JS-fingerprint-gated SPA: a live dry run captured only the pre-render
loading shell (0 events), while a one-off script with a longer wait
reached the real session list. No credential is needed — only time.

Left disabled by this:
- `registry/sources/helen-woodward-camps.toml`
- `registry/sources/sandiego-air-space-camps.toml`

Both are `fetch_strategy = "headless"` with the finding recorded in
their TOML comments and in `partner_scrape/adapters/activenet_camps.py`'s
module docstring.

Not the same problem as CampBrain (sprint 028 ticket 006), which is a
genuine server-side login wall no fetcher change can clear.

## Proposed fix

Give `PlaywrightFetcher` a configurable wait strategy — `networkidle`
and/or an explicit settle delay and/or a wait-for-selector — settable
per source in the registry so slow SPAs can opt into it without
slowing every headless fetch. Then re-verify and enable the two
ActiveNet sources.

Note when picking a default: sprint 014 reactivated the Playwright
cron path, so any change here affects existing headless sources too —
keep the current behavior as the default and make the longer wait
opt-in.

## Verification

- Unit: the fetcher honors a per-source wait configuration.
- Live: `uv run partner-scrape --source helen-woodward-camps --dry-run -v`
  yields dated camp sessions, and both ActiveNet sources are
  `enabled = true`.

Note that San Diego Air & Space's ActiveNet page currently exposes only
a non-camp "Birthday Parties" season (Summer Camp 2026 concluded, 2027
not yet open) — enabling it needs a season check so birthday-party
bookings are not mis-tagged as `Camps`.
