---
id: '003'
title: Thread acquisition_policy into every fetch call site
status: open
use-cases:
- SUC-004
depends-on:
- '001'
github-issue: ''
issue: 38-acquisition-policy-threading-and-feed-robots.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Thread acquisition_policy into every fetch call site

## Description

`fetch/cache.py`'s `PoliteFetcher.get()` accepts `rate_limit_seconds`
and `respect_robots` as per-call parameters, and its own docstring
documents the intended design: "callers that have a `SourceConfig`
pull the values out of its `acquisition_policy` dict themselves." No
adapter or discovery module actually does this — every call site
invokes `fetcher.get(url)` (or `fetcher.get(url, headers=...)`) with
no override, so `PoliteFetcher`'s hardcoded defaults
(`respect_robots=True`, `rate_limit_seconds=DEFAULT_RATE_LIMIT_SECONDS`)
always apply regardless of what a source's TOML says.
`leaguesync.toml`'s existing `respect_robots = false` has therefore
never had any effect (it happens to be harmless only because that
domain's `robots.txt` 404s live, treated as allow-all either way).

This ticket implements the pre-existing design, not a new one: every
`fetcher.get()` call site in `adapters/*.py` and the two `discovery/`
modules that call it directly reads its source's
`acquisition_policy` and passes the two keys through.

Depends on ticket 001 because both this ticket and ticket 001 touch
`discovery/sitemap.py`; sequencing after 001 avoids any merge overlap
in that file.

## Fix shape

To avoid duplicating the same
`acquisition_policy.get("rate_limit_seconds", DEFAULT_RATE_LIMIT_SECONDS)`
/ `acquisition_policy.get("respect_robots", True)` pair at each of the
13 call sites below, add one small helper to `adapters/base.py`:

```python
def acquisition_kwargs(source: SourceConfig) -> dict[str, Any]:
    """rate_limit_seconds/respect_robots kwargs for fetcher.get(),
    read from source.acquisition_policy with PoliteFetcher's own
    defaults as fallback."""
```

`adapters/base.py` already imports `SourceConfig` (the `adapters` →
`registry` edge) and `Fetcher`/fetch constants (the `adapters` →
`fetch` edge); `discovery/sitemap.py` and `discovery/listing.py`
already import `adapters.base.EventRef` directly
(`discovery/DESIGN.md`'s documented exception to the "discovery never
imports adapters" default), so importing one more name from the same
module adds no new inter-subsystem edge.

Every call site becomes `fetcher.get(url, **acquisition_kwargs(source))`
(or, where `headers=` is already passed — `leaguesync.py` — added
alongside it).

## Acceptance Criteria

- [ ] `adapters/base.py` gains `acquisition_kwargs(source) -> dict`,
      unit-tested directly for the default case (no
      `acquisition_policy` keys set), an explicit-override case, and
      the `leaguesync.toml`-shaped case (`respect_robots = false`).
- [ ] Every one of these call sites uses
      `**acquisition_kwargs(source)`: `adapters/generic_html.py`,
      `adapters/ical.py`, `adapters/greenhouse.py`,
      `adapters/bibliocommons.py` (both call sites), `adapters/lever.py`,
      `adapters/localist.py` (both call sites), `adapters/wordpress.py`,
      `adapters/leaguesync.py`, `adapters/tec.py` (both call sites),
      `adapters/listing_html.py`, `discovery/listing.py`,
      `discovery/sitemap.py` (all three call sites).
- [ ] A fixture `Fetcher` double proves at least one representative
      call site per adapter/module above receives the actual
      `rate_limit_seconds`/`respect_robots` values from its source's
      `acquisition_policy`.
- [ ] A regression test proves `leaguesync.toml`'s `respect_robots =
      false` now reaches `PoliteFetcher.get()` as `False`.
- [ ] `leaguesync.py`'s existing `headers=_auth_headers()` behavior is
      unchanged (both kwargs coexist on the same call).
- [ ] `PoliteFetcher.get()`'s own signature and default values are
      unchanged — this ticket is entirely about callers, not the
      fetch layer itself.
- [ ] Full test suite stays green.

## Testing

- **Existing tests to run**: full suite (`uv run pytest`), especially
  every adapter's own test module and both discovery test modules.
- **New tests to write**: `acquisition_kwargs()` unit tests;
  per-call-site fixture assertions per Acceptance Criteria; the
  `leaguesync` regression test.
- **Verification command**: `uv run pytest`.

## Implementation Plan

**Approach**: Add the helper first, then update each call site
mechanically — same pattern (`fetcher.get(url, **acquisition_kwargs(source))`)
repeated 13 times, no other logic change per file.

**Files to modify**:
- `partner_scrape/adapters/base.py` — new `acquisition_kwargs()`.
- `partner_scrape/adapters/generic_html.py`, `ical.py`, `greenhouse.py`,
  `bibliocommons.py`, `lever.py`, `localist.py`, `wordpress.py`,
  `leaguesync.py`, `tec.py`, `listing_html.py` — call-site updates.
- `partner_scrape/discovery/sitemap.py`, `discovery/listing.py` —
  call-site updates.
- Corresponding test files for each.

**Testing plan**: see Testing above.

**Documentation updates**: `partner_scrape/adapters/DESIGN.md` and
`partner_scrape/fetch/DESIGN.md` each get a short sprint-015 addendum
noting the new helper and that acquisition-policy threading is now
real (fetch/DESIGN.md's own docstring precedent for this design is
finally implemented, not changed).
